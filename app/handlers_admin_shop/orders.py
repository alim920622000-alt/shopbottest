from aiogram.exceptions import TelegramBadRequest
from app.utils.tg_safe import safe_edit_text, safe_delete_cq_message
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.handlers_admin_shop.start import kb_admin_main  # добавь импорт
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_shop.utils import get_admin_shop_ids
from app.repositories.orders_repo import OrdersRepo
from app.repositories.order_seen_repo import OrderSeenRepo
from app.services.chat_reminders import is_chat_reminder_text
from app.services.order_chat_access import can_access_order_chat
from app.services.screen import clear_state_keep_screen, show_main_menu, show_screen
from app.services.notification_center import remember_admin_prev_target, parse_notif_context, NOTIF_SRC_ORDERS
from app.services.pagination import calc_page, pager_row

PAGE_SIZE = 8

router = Router()

def _format_fulfillment_type(value: str | None) -> str:
    mapping = {
        "courier": "🚚 Доставка",
        "pickup": "🏬 Самовывоз",
        "dine_in": "🍽 В зале",
    }
    return mapping.get((value or "").strip(), "🚚 Доставка")



def kb_back_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="a:back:main")]
    ])


def kb_orders_list(order_ids: list[int]) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"a:order:{oid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_order_card(order_id: int, can_chat: bool = True) -> InlineKeyboardMarkup:
    return kb_order_card_with_back(order_id, "a:orders", can_chat)


def kb_order_card_with_back(order_id: int, back_target: str, can_chat: bool = True, show_preparing: bool = True) -> InlineKeyboardMarkup:
    kb = []
    if show_preparing:
        kb.append([InlineKeyboardButton(text="✅ Готовится", callback_data=f"a:st:{order_id}:preparing")])
    kb += [
        [InlineKeyboardButton(text="📦 Готово", callback_data=f"a:st:{order_id}:ready")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"a:st:{order_id}:canceled")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data=back_target),
        ],
    ]
    if can_chat:
        kb.insert(3, [InlineKeyboardButton(text="💬 Чат по заказу", callback_data=f"a:chat:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def build_order_card_payload(
    db: Database,
    order_id: int,
    back_target: str,
) -> tuple[str, InlineKeyboardMarkup, bool]:
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o:
        return "Заказ не найден.", kb_back_admin(), False
    items = await orders.get_order_items(order_id)
    comment = (o.get("comment") or "").strip()
    comment_line = comment or "— не добавлен —"
    shop_info = await __import__("app.repositories.shops_repo", fromlist=["ShopsRepo"]).ShopsRepo(db).get(int(o["shop_id"]))
    reserve = "Да" if int((shop_info or {}).get("allow_prepare_before_courier") or 0) == 1 else "Нет"
    lines = [
        f"Заказ #{o['id']}",
        f"🛟 Резервные курьеры: {reserve}",
        f"Статус (legacy): {o['status']}",
        f"Сумма: {o['total_amount']}",
        f"Получение: {_format_fulfillment_type(o.get('fulfillment_type'))}",
        f"Комментарий: {comment_line}",
        "",
        "Состав:",
    ]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")
    can_chat = await can_access_order_chat(db, o)
    return "\n".join(lines), kb_order_card_with_back(order_id, back_target, can_chat), True


async def render_order_card_by_id(cq: CallbackQuery, db: Database, state: FSMContext, order_id: int) -> None:
    text, kb, _ = await build_order_card_payload(db, order_id, "a:orders")
    await show_screen(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        db=db,
        bot_kind="admin_shop",
        text=text,
        reply_markup=kb,
    )


@router.callback_query(F.data == "a:home")
async def admin_home(cq: CallbackQuery, db: Database, state: FSMContext):
    await remember_admin_prev_target(db, "admin_shop", cq.from_user.id, "a:home")
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Напоминание удаляем и показываем домашний экран через screen.py.
        await clear_state_keep_screen(state, db, "admin_shop", cq.from_user.id)
        await safe_delete_cq_message(cq)
        await show_main_menu(
            bot=cq.bot,
            chat_id=cq.from_user.id,
            state=state,
            db=db,
            bot_kind="admin_shop",
            text="Админ-меню магазина:",
            reply_markup=kb_admin_main(),
        )
    else:
        await safe_edit_text(cq.message, "Админ-меню магазина:", reply_markup=kb_admin_main())

    await cq.answer()


@router.callback_query(F.data.startswith("a:orders:p:"))
async def list_orders_page(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    await list_orders_render(cq, db, state, page)


@router.callback_query(F.data == "a:orders")
async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext):
    await list_orders_render(cq, db, state, 0)


async def list_orders_render(cq: CallbackQuery, db: Database, state: FSMContext, page: int):
    await remember_admin_prev_target(db, "admin_shop", cq.from_user.id, "a:orders")
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not shop_ids:
        await safe_edit_text(cq.message, "Нет доступа.", reply_markup=kb_back_admin())
        await cq.answer()
        return

    shop_id = shop_ids[0]
    orders = OrdersRepo(db)
    statuses = ["new", "preparing", "ready"]
    total = await orders.count_for_shop(shop_id, statuses)
    if total <= 0:
        await safe_edit_text(cq.message, f"Текущих заказов нет (shop_id={shop_id}).", reply_markup=kb_back_admin())
        await cq.answer()
        return

    pi = calc_page(total=total, page=page, page_size=PAGE_SIZE)
    rows = await orders.list_current_for_shop_page(shop_id=shop_id, statuses=statuses, limit=pi.limit, offset=pi.offset)
    order_ids = [int(r["id"]) for r in rows]
    kb = kb_orders_list(order_ids)
    pager = pager_row("a:orders", pi.page, pi.total_pages)
    if pager:
        kb.inline_keyboard.append(pager)
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="a:back:main"),
    ])
    await cq.message.edit_text(f"Текущие заказы (shop_id={shop_id}):", reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("a:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[2])
    await remember_admin_prev_target(db, "admin_shop", cq.from_user.id, f"a:order:{order_id}")
    src, page = parse_notif_context(cq.data)
    back_target = "a:orders"
    if src == NOTIF_SRC_ORDERS:
        page = max(1, page or 1)
        back_target = f"a:notif:orders" if page == 1 else f"a:notif:op:{page}"
    await state.update_data(order_back_target=back_target)

    text, kb, found = await build_order_card_payload(db, order_id, back_target)
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Напоминание удаляем и показываем карточку заказа заново.
        await clear_state_keep_screen(state, db, "admin_shop", cq.from_user.id)
        await safe_delete_cq_message(cq)
        await show_screen(
            bot=cq.bot,
            chat_id=cq.from_user.id,
            state=state,
            db=db,
            bot_kind="admin_shop",
            text=text,
            reply_markup=kb,
        )
    else:
        await safe_edit_text(cq.message, text, reply_markup=kb)
    if found:
        await OrderSeenRepo(db).mark_order_seen(order_id, "admin_shop", cq.from_user.id)
    await cq.answer()


@router.callback_query(F.data.startswith("a:st:"))
async def set_status(cq: CallbackQuery, db: Database, state: FSMContext):
    # a:st:{order_id}:{status}
    _, _, order_id_str, status = cq.data.split(":", 3)
    order_id = int(order_id_str)

    orders = OrdersRepo(db)
    await orders.set_merchant_status(order_id, status)

    await cq.answer("Статус обновлён")
    # перерисуем карточку заказа
    o = await orders.get_order(order_id)
    items = await orders.get_order_items(order_id)
    comment = (o.get("comment") or "").strip()
    comment_line = comment or "— не добавлен —"
    shop_info = await __import__("app.repositories.shops_repo", fromlist=["ShopsRepo"]).ShopsRepo(db).get(int(o["shop_id"]))
    reserve = "Да" if int((shop_info or {}).get("allow_prepare_before_courier") or 0) == 1 else "Нет"
    lines = [
        f"Заказ #{o['id']}",
        f"🛟 Резервные курьеры: {reserve}",
        f"Статус (legacy): {o['status']}",
        f"Сумма: {o['total_amount']}",
        f"Получение: {_format_fulfillment_type(o.get('fulfillment_type'))}",
        f"Комментарий: {comment_line}",
        "",
        "Состав:",
    ]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")
    data = await state.get_data()
    back_target = data.get("order_back_target") or "a:orders"
    await safe_edit_text(
        cq.message,
        "\n".join(lines),
        reply_markup=kb_order_card_with_back(order_id, back_target, await can_access_order_chat(db, o)),
    )


@router.callback_query(F.data == "a:back:main")
async def back_main(cq: CallbackQuery):
    await safe_edit_text(cq.message, "Админ-меню магазина:", reply_markup=kb_admin_main())
    await cq.answer()
