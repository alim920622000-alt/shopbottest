from __future__ import annotations

import logging
import random

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup

from app.config import get_settings
from app.db.database import Database
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.chat_repo import ChatRepo
from app.repositories.chat_prefs_repo import ChatPrefsRepo
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.repositories.couriers_repo import CouriersRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.settings_repo import SettingsRepo
from app.repositories.zones_repo import ZonesRepo
from app.services.chat_ui import PAGE_SIZE as CHAT_PAGE_SIZE, build_chat_screen_kb, build_chat_screen_text, calc_total_pages
from app.services.courier_capacity import MODE_FREE, MODE_MEDIUM, MODE_STRICT, can_accept_order, get_courier_capacity_mode
from app.services.order_chat_access import can_access_order_chat
from app.services.pagination import calc_page

router = Router()
ZONE_PAGE_SIZE = 8
ORDERS_PAGE_SIZE = 10
logger = logging.getLogger(__name__)

THREAD_MERCHANT = "merchant"
THREAD_COURIER = "courier"


class CourierStates(StatesGroup):
    zone_add = State()
    zone_rename = State()
    cabinet_phone = State()
    order_chat = State()
    complete_code_wait = State()


def _push(stack: list[str], view: str) -> list[str]:
    if not stack or stack[-1] != view:
        stack.append(view)
    return stack[-20:]


def _current_view_key(view: str) -> str:
    return f"view:{view}"


async def _save_current_view(state: FSMContext, view: str, payload: dict | None = None) -> None:
    data = await state.get_data()
    stack = list(data.get("back_stack") or ["menu"])
    stack = _push(stack, _current_view_key(view))
    views = dict(data.get("views") or {})
    views[view] = payload or {}
    await state.update_data(back_stack=stack, views=views)


async def _push_and_render(state: FSMContext, from_view: str, to_view: str, payload: dict | None = None) -> None:
    data = await state.get_data()
    stack = list(data.get("back_stack") or ["menu"])
    if not stack:
        stack = ["menu"]
    if stack[-1] != _current_view_key(from_view):
        stack = _push(stack, _current_view_key(from_view))
    stack = _push(stack, _current_view_key(to_view))
    views = dict(data.get("views") or {})
    views[to_view] = payload or {}
    await state.update_data(back_stack=stack, views=views)


def _back_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="⬅️ Назад", callback_data="cr:back")]


def _home_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="🏠 Главная", callback_data="cr:home")]


def _is_superadmin(user_id: int) -> bool:
    return user_id in get_settings().superadmin_ids


def _cabinet_transport_name(value: str) -> str:
    mapping = {
        "auto": "авто",
        "moto": "мото",
        "scooter": "скутер",
        "foot": "пешком",
    }
    return mapping.get((value or "").strip(), "не выбран")


def build_pagination_controls(page: int, total_pages: int, base_cb: str) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(InlineKeyboardButton(text="◀️ Назад стр.", callback_data=f"{base_cb}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"Стр. {page + 1}/{total_pages}", callback_data="cr:noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"{base_cb}:{page + 1}"))
    return row


def _kb_menu(online: bool) -> InlineKeyboardMarkup:
    status_text = "[Статус: На линии]" if online else "[Статус: Не на линии]"
    rows = [
        [InlineKeyboardButton(text="🚚 Доступные", callback_data="cr:available")],
        [InlineKeyboardButton(text="🧾 Мои активные", callback_data="cr:active")],
        [InlineKeyboardButton(text="📚 История", callback_data="cr:history")],
        [InlineKeyboardButton(text="🗺 Зоны", callback_data="cr:zone")],
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="cr:cabinet")],
        [InlineKeyboardButton(text=status_text, callback_data="cr:toggle_online")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_menu(message: Message | CallbackQuery, db: Database, user_id: int):
    c = await CouriersRepo(db).get(user_id)
    online = int((c or {}).get("is_online") or 0) == 1
    text = "Курьер-бот"
    kb = _kb_menu(online)
    if isinstance(message, Message):
        await message.answer(text, reply_markup=kb)
    else:
        await message.message.edit_text(text, reply_markup=kb)


async def _render_orders_list(cq: CallbackQuery, db: Database, state: FSMContext, mode: str, page: int = 0) -> None:
    orders_repo = OrdersRepo(db)
    if mode == "available":
        title = "Доступные заказы"
        total = await orders_repo.count_available_for_courier(cq.from_user.id)
        pi = calc_page(total=total, page=page, page_size=ORDERS_PAGE_SIZE)
        rows = await orders_repo.list_available_for_courier_page(cq.from_user.id, limit=pi.limit, offset=pi.offset)
    elif mode == "active":
        title = "Мои активные"
        total = await orders_repo.count_active_for_courier(cq.from_user.id)
        pi = calc_page(total=total, page=page, page_size=ORDERS_PAGE_SIZE)
        rows = await orders_repo.list_active_for_courier_page(cq.from_user.id, limit=pi.limit, offset=pi.offset)
    else:
        title = "История"
        total = await orders_repo.count_history_for_courier(cq.from_user.id)
        pi = calc_page(total=total, page=page, page_size=ORDERS_PAGE_SIZE)
        rows = await orders_repo.list_history_for_courier_page(cq.from_user.id, limit=pi.limit, offset=pi.offset)

    if mode == "active" and total == 0:
        await _save_current_view(state, mode, {"page": 0})
        await cq.message.edit_text(
            "У вас нет активных заказов",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[_back_row(), _home_row()]),
        )
        return

    kb_rows = [
        [InlineKeyboardButton(text=f"Заказ #{r['id']}", callback_data=f"cr:order:{r['id']}:{mode}:{pi.page}")]
        for r in rows
    ]
    if mode == "active" and total == 1 and rows:
        await _render_order_card(cq, db, state, int(rows[0]["id"]), "active", pi.page)
        return
    if not kb_rows:
        kb_rows.append([InlineKeyboardButton(text="Список пуст", callback_data="cr:noop")])
    if pi.total_pages > 1:
        kb_rows.append(build_pagination_controls(pi.page, pi.total_pages, f"cr:{mode}:page"))
    kb_rows.append(_back_row())
    await _save_current_view(state, mode, {"page": pi.page})
    await cq.message.edit_text(title, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


def _is_order_closed(order: dict) -> bool:
    courier_status = str(order.get("courier_status") or "").strip().lower()
    merchant_status = str(order.get("merchant_status") or "").strip().lower()
    return courier_status in {"delivered", "completed", "canceled", "cancelled"} or merchant_status in {"completed", "cancelled", "canceled"}


async def _build_order_card(order: dict, source: str, page: int) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        f"Заказ #{order['id']}",
        f"Магазин: {order.get('shop_name') or '—'}",
        f"Статус точки: {order.get('merchant_status')}",
        f"Статус курьера: {order.get('courier_status')}",
        f"Сумма: {order.get('total_amount')}",
    ]
    if order.get("handoff_code"):
        lines.append(f"Код выдачи: {order['handoff_code']}")

    rows: list[list[InlineKeyboardButton]] = []
    closed = _is_order_closed(order)
    courier_status = str(order.get("courier_status") or "").strip().lower()
    merchant_status = str(order.get("merchant_status") or "").strip().lower()

    if not closed and courier_status == "searching":
        rows.append([InlineKeyboardButton(text="✅ Принять доставку", callback_data=f"cr:accept:{order['id']}:{source}:{page}")])
    if not closed and courier_status == "assigned" and merchant_status == "ready":
        rows.append([InlineKeyboardButton(text="📦 Забрать заказ", callback_data=f"cr:pickup:{order['id']}:{source}:{page}")])
    if not closed and courier_status == "picked_up":
        rows.append([InlineKeyboardButton(text="📍 Прибыл", callback_data=f"cr:arrived:{order['id']}:{source}:{page}")])
    if not closed and courier_status == "arrived":
        rows.append([InlineKeyboardButton(text="✅ Завершить заказ", callback_data=f"cr:finish:{order['id']}:{source}:{page}")])
    if not closed and courier_status in {"assigned", "picked_up", "arrived"}:
        rows.append([InlineKeyboardButton(text="💬 Чат по заказу", callback_data=f"cr:chat:{order['id']}:1:{source}:{page}")])
    rows.append(_back_row())
    rows.append(_home_row())
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


def _mode_label(mode: int) -> str:
    if mode == MODE_MEDIUM:
        return "Средний (2 активных заказа)"
    if mode == MODE_FREE:
        return "Свободный (3 активных заказа)"
    return "Строгий (1 активный заказ)"


def _mode_text(mode: int, current_mode: int) -> str:
    mark = "✅ " if mode == current_mode else ""
    if mode == MODE_MEDIUM:
        return f"{mark}Режим 2: Средний (2 активных заказа)"
    if mode == MODE_FREE:
        return f"{mark}Режим 3: Свободный (3 активных заказа)"
    return f"{mark}Режим 1: Строгий (1 активный заказ)"


async def _render_order_card(cq: CallbackQuery, db: Database, state: FSMContext, order_id: int, source: str, page: int) -> bool:
    o = await OrdersRepo(db).get_order(order_id)
    if not o:
        await cq.answer("Заказ не найден", show_alert=True)
        return False
    text, kb = await _build_order_card(o, source, page)
    await _save_current_view(state, "order", {"order_id": order_id, "source": source, "page": page})
    await cq.message.edit_text(text, reply_markup=kb)
    return True


async def _render_cabinet(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    courier = await CouriersRepo(db).get(cq.from_user.id) or {}
    profile = await ClientProfilesRepo(db).get(cq.from_user.id) or {}
    full_name = (cq.from_user.full_name or "").strip() or "—"
    phone = (profile.get("phone") or "").strip() or "—"
    transport = _cabinet_transport_name(courier.get("transport_type") or "")
    online = "Да" if int(courier.get("is_online") or 0) == 1 else "Нет"
    text = (
        "👤 Кабинет курьера\n\n"
        f"Имя: {full_name}\n"
        f"Телефон: {phone}\n"
        f"Транспорт: {transport}\n"
        f"На линии: {online}"
    )
    kb_rows = [
        [InlineKeyboardButton(text="📞 Указать телефон", callback_data="cr:cabinet_phone")],
        [
            InlineKeyboardButton(text="🚗 Авто", callback_data="cr:transport:auto"),
            InlineKeyboardButton(text="🏍 Мото", callback_data="cr:transport:moto"),
        ],
        [
            InlineKeyboardButton(text="🛵 Скутер", callback_data="cr:transport:scooter"),
            InlineKeyboardButton(text="🚶 Пешком", callback_data="cr:transport:foot"),
        ],
        [InlineKeyboardButton(text="🔁 На линии / Не на линии", callback_data="cr:toggle_online")],
    ]
    if _is_superadmin(cq.from_user.id):
        mode = await get_courier_capacity_mode(db)
        text += f"\n\n⚙️ Режим заказов курьера: {_mode_label(mode)}"
        kb_rows.extend(
            [
                [InlineKeyboardButton(text=_mode_text(MODE_STRICT, mode), callback_data=f"cr:cap_set:{MODE_STRICT}")],
                [InlineKeyboardButton(text=_mode_text(MODE_MEDIUM, mode), callback_data=f"cr:cap_set:{MODE_MEDIUM}")],
                [InlineKeyboardButton(text=_mode_text(MODE_FREE, mode), callback_data=f"cr:cap_set:{MODE_FREE}")],
            ]
        )
    kb_rows.append(_back_row())
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await _save_current_view(state, "cabinet")
    await cq.message.edit_text(text, reply_markup=kb)


async def _render_zones(cq: CallbackQuery, db: Database, state: FSMContext, page: int = 0) -> None:
    zrepo = ZonesRepo(db)
    crepo = CouriersRepo(db)
    c = await crepo.get(cq.from_user.id)
    selected = await zrepo.list_for_courier(cq.from_user.id)
    is_superadmin = _is_superadmin(cq.from_user.id)

    all_rows = await zrepo.list_all() if is_superadmin else await zrepo.list_active(limit=1000, offset=0)
    visible_rows = [r for r in all_rows if is_superadmin or int(r.get("is_active") or 0) == 1]
    pi = calc_page(total=len(visible_rows), page=page, page_size=ZONE_PAGE_SIZE)
    rows = visible_rows[pi.offset: pi.offset + pi.limit]

    kb_rows: list[list[InlineKeyboardButton]] = []
    if not rows:
        kb_rows.append([InlineKeyboardButton(text="Зон пока нет", callback_data="cr:noop")])

    for z in rows:
        zid = int(z["id"])
        is_active = int(z.get("is_active") or 0) == 1
        mark = "✅" if zid in selected else "⬜"
        suffix = " (неактивна)" if not is_active else ""
        kb_rows.append([InlineKeyboardButton(text=f"{mark} {z['name']}{suffix}", callback_data=f"cr:zone_toggle:{zid}:{pi.page}")])
        if is_superadmin:
            action = "Деактивировать" if is_active else "Активировать"
            action_icon = "🚫" if is_active else "✅"
            kb_rows.append([
                InlineKeyboardButton(text=f"✏️ {z['name']}", callback_data=f"cr:zone_rename_start:{zid}:{pi.page}"),
                InlineKeyboardButton(text=f"{action_icon} {action}", callback_data=f"cr:zone_toggle_active:{zid}:{pi.page}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"cr:zone_delete:{zid}:{pi.page}"),
            ])

    aa = int((c or {}).get("accept_all_zones") or 0) == 1
    kb_rows.append([InlineKeyboardButton(text=f"Все зоны: {'✅' if aa else '⬜'}", callback_data=f"cr:zone_all:{pi.page}")])
    if is_superadmin:
        kb_rows.append([InlineKeyboardButton(text="➕ Добавить зону", callback_data=f"cr:zone_add_start:{pi.page}")])
    if pi.total_pages > 1:
        kb_rows.append(build_pagination_controls(pi.page, pi.total_pages, "cr:zones:page"))
    kb_rows.append(_back_row())

    await _save_current_view(state, "zone", {"page": pi.page})
    await cq.message.edit_text("Зоны", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


def _phone_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _chat_nav_rows(order_id: int, source: str, source_page: int, thread: str) -> list[list[InlineKeyboardButton]]:
    switch_to = THREAD_COURIER if thread == THREAD_MERCHANT else THREAD_MERCHANT
    switch_text = "✍️ Написать клиенту" if thread == THREAD_MERCHANT else "✍️ Написать магазину/ресторану"
    return [
        [InlineKeyboardButton(text=switch_text, callback_data=f"cr:chat_thread:{order_id}:{switch_to}")],
        [InlineKeyboardButton(text="✍️ Написать сообщение", callback_data=f"cr:chat_send:{order_id}:{source}:{source_page}")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"cr:chat_refresh:{order_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="cr:back")],
        _home_row(),
    ]


async def _render_chat(cq: CallbackQuery, db: Database, state: FSMContext, order_id: int, page: int, source: str, source_page: int) -> None:
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    if not order:
        await cq.answer("Заказ не найден", show_alert=True)
        return
    if not await can_access_order_chat(db, order):
        await cq.answer("Чат недоступен для этого заказа", show_alert=True)
        return

    chat = ChatRepo(db)
    reads = ChatReadsRepo(db)
    data = await state.get_data()
    thread = str(data.get("chat_thread") or THREAD_MERCHANT)
    total_messages = await chat.count_messages(order_id, thread=thread)
    total_pages = max(1, calc_total_pages(total_messages, CHAT_PAGE_SIZE))
    current_page = max(1, min(page, total_pages))
    offset = (total_pages - current_page) * CHAT_PAGE_SIZE
    messages = await chat.list_messages(order_id, thread=thread, limit=CHAT_PAGE_SIZE, offset=offset)
    await reads.mark_read(order_id, "courier", cq.from_user.id)

    text = build_chat_screen_text(order_id, messages, False, str(order.get("business_type") or "shop"), "ru", "courier", shop_name=order.get("shop_name"))
    kb = build_chat_screen_kb(order_id, current_page, total_pages, "cr", _chat_nav_rows(order_id, source, source_page, thread))
    await _save_current_view(state, "order_chat", {"order_id": order_id, "page": current_page, "source": source, "source_page": source_page})
    await state.update_data(chat_order_id=order_id, chat_page=current_page, chat_source=source, chat_source_page=source_page, chat_thread=thread)
    await cq.message.edit_text(text, reply_markup=kb)


async def _render_chat_from_message(message: Message, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    order_id = int(data.get("chat_order_id") or 0)
    source = str(data.get("chat_source") or "active")
    source_page = int(data.get("chat_source_page") or 0)
    page = int(data.get("chat_page") or 1)
    if not order_id:
        await _render_menu(message, db, message.from_user.id)
        return

    order = await OrdersRepo(db).get_order(order_id)
    if not order:
        await message.answer("Заказ не найден", reply_markup=_kb_menu(True))
        return

    chat = ChatRepo(db)
    data = await state.get_data()
    thread = str(data.get("chat_thread") or THREAD_MERCHANT)
    total_messages = await chat.count_messages(order_id, thread=thread)
    total_pages = max(1, calc_total_pages(total_messages, CHAT_PAGE_SIZE))
    page = max(1, min(page, total_pages))
    offset = (total_pages - page) * CHAT_PAGE_SIZE
    messages = await chat.list_messages(order_id, thread=thread, limit=CHAT_PAGE_SIZE, offset=offset)
    text = build_chat_screen_text(order_id, messages, False, str(order.get("business_type") or "shop"), "ru", "courier", shop_name=order.get("shop_name"))
    kb = build_chat_screen_kb(order_id, page, total_pages, "cr", _chat_nav_rows(order_id, source, source_page, thread))
    await state.update_data(chat_page=page)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "cr:noop")
async def noop(cq: CallbackQuery):
    await cq.answer()


@router.message(CommandStart())
async def start_cmd(message: Message, db: Database, state: FSMContext):
    await CouriersRepo(db).ensure(message.from_user.id)
    await state.clear()
    await state.update_data(back_stack=["menu"])
    await _render_menu(message, db, message.from_user.id)


@router.callback_query(F.data == "cr:home")
async def home(cq: CallbackQuery, db: Database, state: FSMContext):
    await state.clear()
    await state.update_data(back_stack=["menu"])
    await _render_menu(cq, db, cq.from_user.id)
    await cq.answer()


@router.callback_query(F.data == "cr:toggle_online")
async def toggle_online(cq: CallbackQuery, db: Database, state: FSMContext):
    repo = CouriersRepo(db)
    data = await repo.get(cq.from_user.id)
    online = int((data or {}).get("is_online") or 0) == 1
    await repo.set_online(cq.from_user.id, not online)

    state_data = await state.get_data()
    stack = list(state_data.get("back_stack") or ["menu"])
    current = stack[-1] if stack else "menu"
    if current == _current_view_key("cabinet"):
        await _render_cabinet(cq, db, state)
    else:
        await _render_menu(cq, db, cq.from_user.id)
    await cq.answer("Статус обновлён")


@router.callback_query(F.data == "cr:back")
async def back(cq: CallbackQuery, db: Database, state: FSMContext):
    data = await state.get_data()
    stack = list(data.get("back_stack") or ["menu"])
    if len(stack) > 1:
        stack.pop()
    target = stack[-1] if stack else "menu"
    await state.update_data(back_stack=stack)

    if target == "menu" or target == _current_view_key("menu"):
        await _render_menu(cq, db, cq.from_user.id)
    elif target == _current_view_key("zone"):
        page = int((data.get("views") or {}).get("zone", {}).get("page") or 0)
        await _render_zones(cq, db, state, page)
    elif target == _current_view_key("available"):
        page = int((data.get("views") or {}).get("available", {}).get("page") or 0)
        await _render_orders_list(cq, db, state, "available", page)
    elif target == _current_view_key("active"):
        page = int((data.get("views") or {}).get("active", {}).get("page") or 0)
        await _render_orders_list(cq, db, state, "active", page)
    elif target == _current_view_key("history"):
        page = int((data.get("views") or {}).get("history", {}).get("page") or 0)
        await _render_orders_list(cq, db, state, "history", page)
    elif target == _current_view_key("cabinet"):
        await _render_cabinet(cq, db, state)
    elif target == _current_view_key("order"):
        payload = (data.get("views") or {}).get("order", {})
        order_id = int(payload.get("order_id") or 0)
        source = str(payload.get("source") or "available")
        page = int(payload.get("page") or 0)
        if order_id:
            await _render_order_card(cq, db, state, order_id, source, page)
        else:
            await _render_menu(cq, db, cq.from_user.id)
    await cq.answer()


@router.callback_query(F.data == "cr:available")
async def available(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "available", {"page": 0})
    await _render_orders_list(cq, db, state, "available", 0)
    await cq.answer()


@router.callback_query(F.data == "cr:active")
async def active(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "active", {"page": 0})
    await _render_orders_list(cq, db, state, "active", 0)
    await cq.answer()


@router.callback_query(F.data == "cr:history")
async def history(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "history", {"page": 0})
    await _render_orders_list(cq, db, state, "history", 0)
    await cq.answer()


@router.callback_query(F.data.startswith("cr:available:page:"))
async def available_page(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    await _render_orders_list(cq, db, state, "available", page)
    await cq.answer()


@router.callback_query(F.data.startswith("cr:active:page:"))
async def active_page(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    await _render_orders_list(cq, db, state, "active", page)
    await cq.answer()


@router.callback_query(F.data.startswith("cr:history:page:"))
async def history_page(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    await _render_orders_list(cq, db, state, "history", page)
    await cq.answer()


@router.callback_query(F.data.startswith("cr:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, source, page = cq.data.split(":")
    await _push_and_render(state, source, "order", {"order_id": int(order_id), "source": source, "page": int(page)})
    await _render_order_card(cq, db, state, int(order_id), source, int(page))
    await cq.answer()


@router.callback_query(F.data.startswith("cr:accept:"))
async def accept(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, source, page = cq.data.split(":")
    can_accept, reason = await can_accept_order(db, cq.from_user.id)
    if not can_accept:
        await cq.answer(reason, show_alert=True)
        return
    ok = await OrdersRepo(db).assign_courier_atomic(int(order_id), cq.from_user.id)
    await _render_order_card(cq, db, state, int(order_id), source, int(page))
    await cq.answer("Принято" if ok else "Заказ уже занят.", show_alert=not ok)


@router.callback_query(F.data.startswith("cr:pickup:"))
async def pickup(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, source, page = cq.data.split(":")
    await OrdersRepo(db).set_courier_status(int(order_id), "picked_up")
    await _render_order_card(cq, db, state, int(order_id), source, int(page))
    await cq.answer("Статус: забрал")


@router.callback_query(F.data.startswith("cr:arrived:"))
async def arrived(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, source, page = cq.data.split(":")
    repo = OrdersRepo(db)
    code = f"{random.randint(1000, 9999)}"
    await repo.set_handoff_code_if_empty(int(order_id), code)
    await repo.set_courier_status(int(order_id), "arrived")
    await _render_order_card(cq, db, state, int(order_id), source, int(page))
    await cq.answer("Курьер прибыл")


@router.callback_query(F.data.startswith("cr:finish:"))
async def finish(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, source, page = cq.data.split(":")
    order = await OrdersRepo(db).get_order(int(order_id))
    if not order or int(order.get("courier_user_id") or 0) != cq.from_user.id:
        await cq.answer("Заказ не найден", show_alert=True)
        return
    if str(order.get("courier_status") or "").strip().lower() != "arrived":
        await _render_order_card(cq, db, state, int(order_id), source, int(page))
        await cq.answer("Завершение доступно только после статуса «Прибыл».", show_alert=True)
        return
    await state.set_state(CourierStates.complete_code_wait)
    await state.update_data(complete_order_id=int(order_id), complete_source=source, complete_page=int(page), complete_message_id=cq.message.message_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cr:finish_cancel:{order_id}:{source}:{page}")],
        _home_row(),
    ])
    await cq.message.edit_text(
        "Попросите клиента сообщить 4-значный код для завершения заказа.\nВведите 4-значный код:",
        reply_markup=kb,
    )
    await cq.answer()


@router.callback_query(F.data.startswith("cr:finish_cancel:"))
async def finish_cancel(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, source, page = cq.data.split(":")
    await state.set_state(None)
    await _push_and_render(state, source, "order", {"order_id": int(order_id), "source": source, "page": int(page)})
    await _render_order_card(cq, db, state, int(order_id), source, int(page))
    await cq.answer("Возврат в карточку")


@router.callback_query(F.data == "cr:cabinet")
async def cabinet(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "cabinet")
    await _render_cabinet(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "cr:cabinet_phone")
async def cabinet_phone(cq: CallbackQuery, state: FSMContext):
    await state.set_state(CourierStates.cabinet_phone)
    await cq.message.answer("Отправьте номер телефона контактом.", reply_markup=_phone_request_keyboard())
    await cq.answer()


@router.callback_query(F.data.startswith("cr:transport:"))
async def set_transport(cq: CallbackQuery, db: Database, state: FSMContext):
    transport = cq.data.split(":")[-1]
    await CouriersRepo(db).set_transport(cq.from_user.id, transport)
    await _render_cabinet(cq, db, state)
    await cq.answer("Транспорт обновлён")


@router.message(CourierStates.cabinet_phone, F.contact)
async def cabinet_phone_contact(message: Message, db: Database, state: FSMContext):
    await ClientProfilesRepo(db).upsert(user_id=message.from_user.id, phone=message.contact.phone_number)
    await state.clear()
    await message.answer("Телефон сохранён.")
    await _render_menu(message, db, message.from_user.id)


@router.callback_query(F.data == "cr:zone")
async def zone(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "zone", {"page": 0})
    await _render_zones(cq, db, state, 0)
    await cq.answer()


@router.callback_query(F.data.startswith("cr:zones:page:"))
async def zones_page(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    await _render_zones(cq, db, state, page)
    await cq.answer()


@router.callback_query(F.data.startswith("cr:zone_toggle:"))
async def zone_toggle(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, zid, page = cq.data.split(":")
    await ZonesRepo(db).toggle_for_courier(cq.from_user.id, int(zid))
    await _render_zones(cq, db, state, int(page))
    await cq.answer("Обновлено")


@router.callback_query(F.data.startswith("cr:zone_all:"))
async def zone_all(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    c = await CouriersRepo(db).get(cq.from_user.id)
    await CouriersRepo(db).set_accept_all_zones(cq.from_user.id, int((c or {}).get("accept_all_zones") or 0) != 1)
    await _render_zones(cq, db, state, page)
    await cq.answer("Обновлено")


@router.callback_query(F.data.startswith("cr:zone_add_start:"))
async def zone_add_start(cq: CallbackQuery, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    page = int(cq.data.split(":")[-1])
    await state.update_data(zone_page=page)
    await state.set_state(CourierStates.zone_add)
    kb = InlineKeyboardMarkup(inline_keyboard=[_back_row(), _home_row()])
    await cq.message.answer("Введите название новой зоны.", reply_markup=kb)
    await cq.answer()


@router.message(CourierStates.zone_add)
async def zone_add_name(message: Message, db: Database, state: FSMContext):
    if not _is_superadmin(message.from_user.id):
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое.")
        return
    await ZonesRepo(db).create(name)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[_back_row()[0], _home_row()[0]]])
    await message.answer("Зона добавлена ✅", reply_markup=kb)


@router.callback_query(F.data.startswith("cr:zone_rename_start:"))
async def zone_rename_start(cq: CallbackQuery, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    _, _, _, zone_id, page = cq.data.split(":")
    await state.update_data(zone_rename_id=int(zone_id), zone_page=int(page))
    await state.set_state(CourierStates.zone_rename)
    kb = InlineKeyboardMarkup(inline_keyboard=[_back_row(), _home_row()])
    await cq.message.answer("Введите новое имя зоны.", reply_markup=kb)
    await cq.answer()


@router.message(CourierStates.zone_rename)
async def zone_rename_name(message: Message, db: Database, state: FSMContext):
    if not _is_superadmin(message.from_user.id):
        return
    sdata = await state.get_data()
    zone_id = int(sdata.get("zone_rename_id") or 0)
    page = int(sdata.get("zone_page") or 0)
    if not zone_id:
        await state.clear()
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое.")
        return
    await ZonesRepo(db).rename(zone_id, name)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[_back_row()[0], _home_row()[0]]])
    await message.answer("Зона переименована ✅", reply_markup=kb)


@router.callback_query(F.data.startswith("cr:zone_toggle_active:"))
async def zone_toggle_active(cq: CallbackQuery, db: Database, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    _, _, _, zone_id, page = cq.data.split(":")
    repo = ZonesRepo(db)
    zone_obj = await repo.get(int(zone_id))
    if not zone_obj:
        await cq.answer("Зона не найдена", show_alert=True)
        return
    is_active = int(zone_obj.get("is_active") or 0) == 1
    await repo.set_active(int(zone_id), not is_active)
    await _render_zones(cq, db, state, int(page))
    await cq.answer("Статус зоны обновлён")


@router.callback_query(F.data.startswith("cr:zone_delete:"))
async def zone_delete(cq: CallbackQuery, db: Database, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    _, _, _, zone_id, page = cq.data.split(":")
    await ZonesRepo(db).set_active(int(zone_id), False)
    await _render_zones(cq, db, state, int(page))
    await cq.answer("Зона деактивирована")


@router.callback_query(F.data.startswith("cr:chat:"))
async def order_chat(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, page, source, source_page = cq.data.split(":")
    pref = await ChatPrefsRepo(db).get(int(order_id), "courier", cq.from_user.id)
    if not pref:
        pref = THREAD_MERCHANT
        await ChatPrefsRepo(db).set(int(order_id), "courier", cq.from_user.id, pref)
    await state.update_data(chat_thread=pref)
    await _push_and_render(
        state,
        "order",
        "order_chat",
        {"order_id": int(order_id), "page": int(page), "source": source, "source_page": int(source_page)},
    )
    await _render_chat(cq, db, state, int(order_id), int(page), source, int(source_page))
    await cq.answer()


@router.callback_query(F.data.startswith("cr:chatp:"))
async def order_chat_page(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, page = cq.data.split(":")
    data = await state.get_data()
    source = str(data.get("chat_source") or "active")
    source_page = int(data.get("chat_source_page") or 0)
    await _render_chat(cq, db, state, int(order_id), int(page), source, source_page)
    await cq.answer()


@router.callback_query(F.data.startswith("cr:chat_send:"))
async def order_chat_send(cq: CallbackQuery, state: FSMContext):
    _, _, order_id, source, source_page = cq.data.split(":")
    await state.update_data(chat_order_id=int(order_id), chat_source=source, chat_source_page=int(source_page))
    await state.set_state(CourierStates.order_chat)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cr:chat:{order_id}:1:{source}:{source_page}")],
        _home_row(),
    ])
    await cq.message.answer("Введите сообщение для чата заказа", reply_markup=kb)
    await cq.answer()


@router.message(CourierStates.order_chat)
async def order_chat_message(message: Message, db: Database, state: FSMContext):
    data = await state.get_data()
    order_id = int(data.get("chat_order_id") or 0)
    text = (message.text or "").strip()
    if not order_id or not text:
        await message.answer("Не удалось отправить сообщение.")
        return

    order = await OrdersRepo(db).get_order(order_id)
    if not order or int(order.get("courier_user_id") or 0) != message.from_user.id:
        await message.answer("Чат недоступен.")
        return

    thread = str(data.get("chat_thread") or THREAD_MERCHANT)
    await ChatRepo(db).add_message(order_id, message.from_user.id, "courier", text, thread=thread)
    await ChatReadsRepo(db).mark_read(order_id, "courier", message.from_user.id)
    total = await ChatRepo(db).count_messages(order_id, thread=thread)
    await state.update_data(chat_page=max(1, calc_total_pages(total, CHAT_PAGE_SIZE)))
    await _render_chat_from_message(message, db, state)


@router.callback_query(F.data == "cr:capacity")
async def capacity_menu(cq: CallbackQuery, db: Database):
    await cq.message.edit_text(
        "Режим вместимости",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="mode1", callback_data="cr:cap_set:1")],
                [InlineKeyboardButton(text="mode2", callback_data="cr:cap_set:2")],
                [InlineKeyboardButton(text="mode3", callback_data="cr:cap_set:3")],
                _back_row(),
            ]
        ),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("cr:cap_set:"))
async def cap_set(cq: CallbackQuery, db: Database, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    mode = cq.data.split(":")[-1]
    await SettingsRepo(db).set("courier_capacity_mode", mode)
    logger.info("Режим вместимости курьеров обновлён: %s", mode)
    await _render_cabinet(cq, db, state)
    await cq.answer("Режим сохранён")


@router.message(CourierStates.complete_code_wait)
async def finish_code_input(message: Message, db: Database, state: FSMContext):
    data = await state.get_data()
    order_id = int(data.get("complete_order_id") or 0)
    source = str(data.get("complete_source") or "active")
    page = int(data.get("complete_page") or 0)
    message_id = int(data.get("complete_message_id") or 0)
    code = (message.text or "").strip()
    if not order_id:
        await state.clear()
        await _render_menu(message, db, message.from_user.id)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"cr:finish_cancel:{order_id}:{source}:{page}")],
        _home_row(),
    ])
    if not (len(code) == 4 and code.isdigit()):
        await message.answer("Введите 4 цифры", reply_markup=kb)
        return

    order = await OrdersRepo(db).get_order(order_id)
    if not order or int(order.get("courier_user_id") or 0) != message.from_user.id:
        await state.clear()
        await message.answer("Заказ не найден")
        return

    if str(order.get("handoff_code") or "") != code:
        await message.answer("Неверный код. Попробуйте ещё раз.", reply_markup=kb)
        return

    await OrdersRepo(db).confirm_client_handoff(order_id)
    await state.set_state(None)
    order_view = await OrdersRepo(db).get_order(order_id)
    if order_view and message_id:
        text, card_kb = await _build_order_card(order_view, source, page)
        await message.bot.edit_message_text(text=text, chat_id=message.chat.id, message_id=message_id, reply_markup=card_kb)
    elif order_view:
        text, card_kb = await _build_order_card(order_view, source, page)
        await message.answer(text, reply_markup=card_kb)
    await message.answer("Заказ завершён ✅")


@router.message(F.text)
async def fallback_text(message: Message, state: FSMContext, db: Database):
    if await state.get_state() in {CourierStates.zone_add.state, CourierStates.zone_rename.state, CourierStates.order_chat.state, CourierStates.cabinet_phone.state, CourierStates.complete_code_wait.state}:
        return
    await message.answer("Команда неверна, используйте меню ниже.")
    await _render_menu(message, db, message.from_user.id)
