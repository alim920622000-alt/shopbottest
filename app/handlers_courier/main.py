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
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.repositories.couriers_repo import CouriersRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.settings_repo import SettingsRepo
from app.repositories.zones_repo import ZonesRepo

router = Router()
ZONE_PAGE_SIZE = 8
logger = logging.getLogger(__name__)


class CourierStates(StatesGroup):
    zone_add = State()
    zone_rename = State()
    cabinet_phone = State()
    order_chat = State()


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
    return [InlineKeyboardButton(text="Назад", callback_data="cr:back")]


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


def _kb_menu(online: bool) -> InlineKeyboardMarkup:
    if online:
        rows = [
            [InlineKeyboardButton(text="🚚 Доступные", callback_data="cr:available")],
            [InlineKeyboardButton(text="🧾 Мои активные", callback_data="cr:active")],
            [InlineKeyboardButton(text="📚 История", callback_data="cr:history")],
            [InlineKeyboardButton(text="🗺 Зоны", callback_data="cr:zone")],
            [InlineKeyboardButton(text="👤 Кабинет", callback_data="cr:cabinet")],
            [InlineKeyboardButton(text="[Статус: На линии]", callback_data="cr:toggle_online")],
        ]
    else:
        rows = [
            [InlineKeyboardButton(text="🚚 Доступные", callback_data="cr:available")],
            [InlineKeyboardButton(text="🧾 Мои активные", callback_data="cr:active")],
            [InlineKeyboardButton(text="📚 История", callback_data="cr:history")],
            [InlineKeyboardButton(text="🗺 Зоны", callback_data="cr:zone")],
            [InlineKeyboardButton(text="👤 Кабинет", callback_data="cr:cabinet")],
            [InlineKeyboardButton(text="[Статус: Не на линии]", callback_data="cr:toggle_online")],
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


async def _render_orders_list(cq: CallbackQuery, db: Database, state: FSMContext, mode: str) -> None:
    orders_repo = OrdersRepo(db)
    if mode == "available":
        title = "Доступные заказы"
        rows = await orders_repo.list_available_for_courier(cq.from_user.id)
    elif mode == "active":
        title = "Мои активные"
        rows = await orders_repo.list_active_for_courier(cq.from_user.id)
    else:
        title = "История"
        rows = await orders_repo.list_history_for_courier(cq.from_user.id)

    kb_rows = [[InlineKeyboardButton(text=f"Заказ #{r['id']}", callback_data=f"cr:order:{r['id']}")] for r in rows]
    kb_rows.append(_back_row())
    await _save_current_view(state, mode)
    await cq.message.edit_text(title, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


async def _build_order_card(order: dict) -> tuple[str, InlineKeyboardMarkup]:
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
    if order.get("courier_status") == "searching":
        rows.append([InlineKeyboardButton(text="✅ Принять доставку", callback_data=f"cr:accept:{order['id']}")])
    if order.get("courier_status") == "assigned" and order.get("merchant_status") == "ready":
        rows.append([InlineKeyboardButton(text="📦 Забрал заказ", callback_data=f"cr:pickup:{order['id']}")])
    if order.get("courier_status") == "picked_up":
        rows.append([InlineKeyboardButton(text="📍 Прибыл", callback_data=f"cr:arrived:{order['id']}")])
    if order.get("courier_status") in {"arrived", "delivered"}:
        rows.append([InlineKeyboardButton(text="✅ Завершить", callback_data=f"cr:finish:{order['id']}")])
    if order.get("courier_status") in {"assigned", "picked_up", "arrived"}:
        rows.append([InlineKeyboardButton(text="💬 Чат по заказу", callback_data=f"cr:chat:{order['id']}:0")])
    rows.append(_back_row())
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_order_card(cq: CallbackQuery, db: Database, state: FSMContext, order_id: int) -> bool:
    o = await OrdersRepo(db).get_order(order_id)
    if not o:
        await cq.answer("Заказ не найден", show_alert=True)
        return False
    text, kb = await _build_order_card(o)
    await _save_current_view(state, "order", {"order_id": order_id})
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
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
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
            _back_row(),
        ]
    )
    await _save_current_view(state, "cabinet")
    await cq.message.edit_text(text, reply_markup=kb)


async def _render_zones(cq: CallbackQuery, db: Database, state: FSMContext, page: int = 0) -> None:
    zrepo = ZonesRepo(db)
    crepo = CouriersRepo(db)
    c = await crepo.get(cq.from_user.id)
    selected = await zrepo.list_for_courier(cq.from_user.id)
    is_superadmin = _is_superadmin(cq.from_user.id)

    rows = await (zrepo.list_all() if is_superadmin else zrepo.list_active(limit=ZONE_PAGE_SIZE, offset=page * ZONE_PAGE_SIZE))
    kb_rows: list[list[InlineKeyboardButton]] = []
    if not rows:
        kb_rows.append([InlineKeyboardButton(text="Зон пока нет", callback_data="cr:noop")])

    for z in rows:
        zid = int(z["id"])
        is_active = int(z.get("is_active") or 0) == 1
        if not is_superadmin and not is_active:
            continue
        mark = "✅" if zid in selected else "⬜"
        suffix = " (неактивна)" if not is_active else ""
        kb_rows.append([InlineKeyboardButton(text=f"{mark} {z['name']}{suffix}", callback_data=f"cr:zone_toggle:{zid}:{page}")])
        if is_superadmin:
            action = "Деактивировать" if is_active else "Активировать"
            action_icon = "🚫" if is_active else "✅"
            kb_rows.append([
                InlineKeyboardButton(text=f"✏️ {z['name']}", callback_data=f"cr:zone_rename_start:{zid}"),
                InlineKeyboardButton(text=f"{action_icon} {action}", callback_data=f"cr:zone_toggle_active:{zid}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"cr:zone_delete:{zid}"),
            ])

    aa = int((c or {}).get("accept_all_zones") or 0) == 1
    kb_rows.append([InlineKeyboardButton(text=f"Все зоны: {'✅' if aa else '⬜'}", callback_data="cr:zone_all")])
    if is_superadmin:
        kb_rows.append([InlineKeyboardButton(text="➕ Добавить зону", callback_data="cr:zone_add_start")])
    kb_rows.append(_back_row())

    await _save_current_view(state, "zone", {"page": page})
    await cq.message.edit_text("Зоны", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))


def _phone_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def _render_chat(cq: CallbackQuery, db: Database, state: FSMContext, order_id: int, page: int) -> None:
    chat = ChatRepo(db)
    reads = ChatReadsRepo(db)
    messages = await chat.list_messages(order_id, limit=10, offset=page * 10)
    await reads.mark_read(order_id, "courier", cq.from_user.id)
    if messages:
        lines = [f"💬 Чат по заказу #{order_id}", ""]
        for msg in messages:
            role = msg.get("sender_role")
            who = "Клиент" if role == "client" else ("Точка" if role in {"admin_shop", "admin_restaurant"} else "Курьер")
            lines.append(f"{who}: {msg.get('message_text')}")
        text = "\n".join(lines)
    else:
        text = f"💬 Чат по заказу #{order_id}\n\nПока сообщений нет."

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✉️ Отправить сообщение", callback_data=f"cr:chat_send:{order_id}")],
            _back_row(),
        ]
    )
    await _save_current_view(state, "order_chat", {"order_id": order_id, "page": page})
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "cr:noop")
async def noop(cq: CallbackQuery):
    await cq.answer()


@router.message(CommandStart())
async def start_cmd(message: Message, db: Database, state: FSMContext):
    await CouriersRepo(db).ensure(message.from_user.id)
    await CouriersRepo(db).set_online(message.from_user.id, True)
    await state.clear()
    await state.update_data(back_stack=["menu"])  # стартовая точка назад
    await _render_menu(message, db, message.from_user.id)


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
        await state.update_data(back_stack=["menu"])
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
        await _render_orders_list(cq, db, state, "available")
    elif target == _current_view_key("active"):
        await _render_orders_list(cq, db, state, "active")
    elif target == _current_view_key("history"):
        await _render_orders_list(cq, db, state, "history")
    elif target == _current_view_key("cabinet"):
        await _render_cabinet(cq, db, state)
    elif target == _current_view_key("order"):
        order_id = int((data.get("views") or {}).get("order", {}).get("order_id") or 0)
        if order_id:
            await _render_order_card(cq, db, state, order_id)
        else:
            await _render_menu(cq, db, cq.from_user.id)
    await cq.answer()


@router.callback_query(F.data == "cr:available")
async def available(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "available")
    await _render_orders_list(cq, db, state, "available")
    await cq.answer()


@router.callback_query(F.data == "cr:active")
async def active(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "active")
    await _render_orders_list(cq, db, state, "active")
    await cq.answer()


@router.callback_query(F.data == "cr:history")
async def history(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "history")
    await _render_orders_list(cq, db, state, "history")
    await cq.answer()


@router.callback_query(F.data.startswith("cr:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[-1])
    await _push_and_render(state, "available", "order", {"order_id": order_id})
    await _render_order_card(cq, db, state, order_id)
    await cq.answer()


async def _can_accept(db: Database, courier_user_id: int) -> bool:
    settings = SettingsRepo(db)
    mode = int(await settings.get("courier_capacity_mode", "1"))
    max_active = int(await settings.get("max_active_orders", "2"))
    active = await OrdersRepo(db).list_active_for_courier(courier_user_id)
    if mode == 1:
        return len(active) < 1
    if mode == 2:
        return len(active) < max_active
    if mode == 3:
        if len(active) == 0:
            return True
        if len(active) > 1:
            return False
        return str(active[0].get("courier_status") or "") == "arrived"
    return False


@router.callback_query(F.data.startswith("cr:accept:"))
async def accept(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[-1])
    if not await _can_accept(db, cq.from_user.id):
        await cq.answer("Превышен лимит активных заказов", show_alert=True)
        return
    ok = await OrdersRepo(db).assign_courier_atomic(order_id, cq.from_user.id)
    await _render_order_card(cq, db, state, order_id)
    await cq.answer("Принято" if ok else "Уже занят", show_alert=not ok)


@router.callback_query(F.data.startswith("cr:pickup:"))
async def pickup(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[-1])
    await OrdersRepo(db).set_courier_status(order_id, "picked_up")
    await _render_order_card(cq, db, state, order_id)
    await cq.answer("Статус: забрал")


@router.callback_query(F.data.startswith("cr:arrived:"))
async def arrived(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[-1])
    repo = OrdersRepo(db)
    code = f"{random.randint(1000, 9999)}"
    await repo.set_handoff_code_if_empty(order_id, code)
    await repo.set_courier_status(order_id, "arrived")
    await _render_order_card(cq, db, state, order_id)
    await cq.answer("Курьер прибыл")


@router.callback_query(F.data.startswith("cr:finish:"))
async def finish(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[-1])
    await OrdersRepo(db).set_courier_status(order_id, "delivered")
    await _render_order_card(cq, db, state, order_id)
    await cq.answer("Заказ завершён")


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
    await ClientProfilesRepo(db).upsert(
        user_id=message.from_user.id,
        phone=message.contact.phone_number,
    )
    await state.clear()
    await message.answer("Телефон сохранён.")


@router.callback_query(F.data == "cr:zone")
async def zone(cq: CallbackQuery, db: Database, state: FSMContext):
    await _push_and_render(state, "menu", "zone", {"page": 0})
    await _render_zones(cq, db, state, 0)
    await cq.answer()


@router.callback_query(F.data.startswith("cr:zone_toggle:"))
async def zone_toggle(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, zid, page = cq.data.split(":")
    await ZonesRepo(db).toggle_for_courier(cq.from_user.id, int(zid))
    await _render_zones(cq, db, state, int(page))
    await cq.answer("Обновлено")


@router.callback_query(F.data == "cr:zone_all")
async def zone_all(cq: CallbackQuery, db: Database, state: FSMContext):
    c = await CouriersRepo(db).get(cq.from_user.id)
    await CouriersRepo(db).set_accept_all_zones(cq.from_user.id, int((c or {}).get("accept_all_zones") or 0) != 1)
    await _render_zones(cq, db, state, 0)
    await cq.answer("Обновлено")


@router.callback_query(F.data == "cr:zone_add_start")
async def zone_add_start(cq: CallbackQuery, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    await state.set_state(CourierStates.zone_add)
    await cq.message.answer("Введите название новой зоны.")
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
    await message.answer("Зона добавлена.")


@router.callback_query(F.data.startswith("cr:zone_rename_start:"))
async def zone_rename_start(cq: CallbackQuery, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    zone_id = int(cq.data.split(":")[-1])
    await state.update_data(zone_rename_id=zone_id)
    await state.set_state(CourierStates.zone_rename)
    await cq.message.answer("Введите новое имя зоны.")
    await cq.answer()


@router.message(CourierStates.zone_rename)
async def zone_rename_name(message: Message, db: Database, state: FSMContext):
    if not _is_superadmin(message.from_user.id):
        return
    zone_id = int((await state.get_data()).get("zone_rename_id") or 0)
    if not zone_id:
        await state.clear()
        return
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Название слишком короткое.")
        return
    await ZonesRepo(db).rename(zone_id, name)
    await state.clear()
    await message.answer("Зона переименована.")


@router.callback_query(F.data.startswith("cr:zone_toggle_active:"))
async def zone_toggle_active(cq: CallbackQuery, db: Database, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    zone_id = int(cq.data.split(":")[-1])
    repo = ZonesRepo(db)
    zone_obj = await repo.get(zone_id)
    if not zone_obj:
        await cq.answer("Зона не найдена", show_alert=True)
        return
    is_active = int(zone_obj.get("is_active") or 0) == 1
    await repo.set_active(zone_id, not is_active)
    await _render_zones(cq, db, state, 0)
    await cq.answer("Статус зоны обновлён")


@router.callback_query(F.data.startswith("cr:zone_delete:"))
async def zone_delete(cq: CallbackQuery, db: Database, state: FSMContext):
    if not _is_superadmin(cq.from_user.id):
        await cq.answer("Недостаточно прав", show_alert=True)
        return
    zone_id = int(cq.data.split(":")[-1])
    await ZonesRepo(db).set_active(zone_id, False)
    await _render_zones(cq, db, state, 0)
    await cq.answer("Зона деактивирована")


@router.callback_query(F.data.startswith("cr:chat:"))
async def order_chat(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id, page = cq.data.split(":")
    await _push_and_render(state, "order", "order_chat", {"order_id": int(order_id), "page": int(page)})
    await _render_chat(cq, db, state, int(order_id), int(page))
    await cq.answer()


@router.callback_query(F.data.startswith("cr:chat_send:"))
async def order_chat_send(cq: CallbackQuery, state: FSMContext):
    order_id = int(cq.data.split(":")[-1])
    await state.update_data(chat_order_id=order_id)
    await state.set_state(CourierStates.order_chat)
    await cq.message.answer("Введите сообщение для чата заказа.")
    await cq.answer()


@router.message(CourierStates.order_chat)
async def order_chat_message(message: Message, db: Database, state: FSMContext):
    order_id = int((await state.get_data()).get("chat_order_id") or 0)
    text = (message.text or "").strip()
    if not order_id or not text:
        await message.answer("Не удалось отправить сообщение.")
        return
    await ChatRepo(db).add_message(order_id, message.from_user.id, "courier", text)
    await ChatReadsRepo(db).mark_read(order_id, "courier", message.from_user.id)
    await state.set_state(CourierStates.order_chat)
    await message.answer("Сообщение отправлено.")


@router.callback_query(F.data == "cr:capacity")
async def capacity_menu(cq: CallbackQuery, db: Database):
    await cq.message.edit_text(
        "Режим вместимости",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="mode1", callback_data="cr:cap_set:1")],
            [InlineKeyboardButton(text="mode2", callback_data="cr:cap_set:2")],
            [InlineKeyboardButton(text="mode3", callback_data="cr:cap_set:3")],
            _back_row(),
        ]),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("cr:cap_set:"))
async def cap_set(cq: CallbackQuery, db: Database):
    mode = cq.data.split(":")[-1]
    await SettingsRepo(db).set("courier_capacity_mode", mode)
    logger.info("Режим вместимости курьеров обновлён: %s", mode)
    await cq.answer("Режим сохранён")
