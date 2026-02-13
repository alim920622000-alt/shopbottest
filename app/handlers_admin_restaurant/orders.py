from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from app.handlers_admin_restaurant.start import kb_admin_main  # добавь импорт

from app.db.database import Database
from app.handlers_admin_restaurant.utils import get_admin_restaurant_ids
from app.repositories.orders_repo import OrdersRepo
from app.repositories.order_seen_repo import OrderSeenRepo
from app.services.chat_reminders import is_chat_reminder_text
from app.services.order_chat_access import can_access_order_chat
from app.services.notification_center import remember_admin_prev_target, parse_notif_context, NOTIF_SRC_ORDERS
from app.services.screen import clear_state_keep_screen, show_screen
from app.services.pagination import build_pager_row, normalize_page, slice_page
from app.utils.tg_safe import safe_delete_cq_message

router = Router()

def _format_fulfillment_type(value: str | None) -> str:
    mapping = {
        "courier": "🚚 Доставка",
        "pickup": "🏬 Самовывоз",
        "dine_in": "🍽 В зале",
    }
    return mapping.get((value or "").strip(), "🚚 Доставка")


CURRENT = ["new", "preparing", "on_the_way"]
DONE = ["finished", "canceled"]


def kb_orders_list(order_ids: list[int], page: int = 0) -> InlineKeyboardMarkup:
    kb = []
    page_items, total_pages = slice_page(order_ids, page, 8)
    page = normalize_page(page, total_pages)
    for oid in page_items:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"r:order:{oid}")])

    pager_row = build_pager_row("r:orders", page, total_pages)
    if pager_row:
        kb.append(pager_row)

    kb.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_order_card(order_id: int, can_chat: bool = True) -> InlineKeyboardMarkup:
    return kb_order_card_with_back(order_id, "r:orders", can_chat)


def kb_order_card_with_back(order_id: int, back_target: str, can_chat: bool = True) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="👨‍🍳 Готовится", callback_data=f"r:st:{order_id}:preparing")],
        [InlineKeyboardButton(text="🚚 В пути", callback_data=f"r:st:{order_id}:on_the_way")],
        [InlineKeyboardButton(text="✅ Завершён", callback_data=f"r:st:{order_id}:finished")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"r:st:{order_id}:canceled")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data=back_target),
        ],
    ]
    if can_chat:
        kb.insert(4, [InlineKeyboardButton(text="💬 Чат по заказу", callback_data=f"r:chat:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def build_order_card_payload(
    db: Database,
    order_id: int,
    back_target: str,
) -> tuple[str, InlineKeyboardMarkup]:
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o:
        return (
            "Заказ не найден.",
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
                        InlineKeyboardButton(text="🔙 Назад", callback_data=back_target),
                    ]
                ]
            ),
        )

    items = await orders.get_order_items(order_id)
    comment = (o.get("comment") or "").strip()
    comment_line = comment or "— не добавлен —"
    lines = [
        f"Заказ #{o['id']}",
        f"Статус: {o['status']}",
        f"Сумма: {o['total_amount']}",
        f"Получение: {_format_fulfillment_type(o.get('fulfillment_type'))}",
        f"Комментарий: {comment_line}",
        "",
        "Состав:",
    ]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")

    can_chat = await can_access_order_chat(db, o)
    return "\n".join(lines), kb_order_card_with_back(order_id, back_target, can_chat)


async def render_order_card_by_id(cq: CallbackQuery, db: Database, state: FSMContext, order_id: int) -> None:
    text, kb = await build_order_card_payload(db, order_id, "r:orders")
    await show_screen(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        db=db,
        bot_kind="admin_restaurant",
        text=text,
        reply_markup=kb,
    )
    await OrderSeenRepo(db).mark_order_seen(order_id, "admin_restaurant", cq.from_user.id)


async def render_order_card(cq: CallbackQuery, db: Database, order_id: int):
    text, kb = await build_order_card_payload(db, order_id, "r:orders")
    await cq.message.edit_text(text, reply_markup=kb)


async def _render_orders(cq: CallbackQuery, db: Database, page: int) -> None:
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
        ]]))
        return

    restaurant_id = ids[0]
    orders = OrdersRepo(db)
    rows = await orders.list_current_for_shop(shop_id=restaurant_id, statuses=CURRENT)
    if not rows:
        await cq.message.edit_text(
            f"Текущих заказов нет (restaurant_id={restaurant_id}).",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
            ]]),
        )
        return

    order_ids = [int(r["id"]) for r in rows]
    await cq.message.edit_text(f"Текущие заказы (restaurant_id={restaurant_id}):", reply_markup=kb_orders_list(order_ids, page=page))


@router.callback_query(F.data == "r:orders")
async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext):
    await remember_admin_prev_target(db, "admin_restaurant", cq.from_user.id, "r:orders")
    await _render_orders(cq, db, page=0)
    await cq.answer()


@router.callback_query(F.data.startswith("r:orders:p:"))
async def list_orders_page(cq: CallbackQuery, db: Database):
    page = int(cq.data.rsplit(":", 1)[1])
    await _render_orders(cq, db, page=page)
    await cq.answer()


@router.callback_query(F.data.startswith("r:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[2])
    await remember_admin_prev_target(db, "admin_restaurant", cq.from_user.id, f"r:order:{order_id}")
    src, page = parse_notif_context(cq.data)
    back_target = "r:orders"
    if src == NOTIF_SRC_ORDERS:
        page = max(1, page or 1)
        back_target = f"r:notif:orders" if page == 1 else f"r:notif:op:{page}"
    await state.update_data(order_back_target=back_target)
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Напоминание удаляем и показываем карточку через screen.py.
        await clear_state_keep_screen(state, db, "admin_restaurant", cq.from_user.id)
        await safe_delete_cq_message(cq)
        text, kb = await build_order_card_payload(db, order_id, back_target)
        await show_screen(
            bot=cq.bot,
            chat_id=cq.from_user.id,
            state=state,
            db=db,
            bot_kind="admin_restaurant",
            text=text,
            reply_markup=kb,
        )
    else:
        text, kb = await build_order_card_payload(db, order_id, back_target)
        await cq.message.edit_text(text, reply_markup=kb)
    await OrderSeenRepo(db).mark_order_seen(order_id, "admin_restaurant", cq.from_user.id)
    await cq.answer()


@router.callback_query(F.data.startswith("r:st:"))
async def set_status(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, order_id_str, status = cq.data.split(":", 3)
    order_id = int(order_id_str)

    orders = OrdersRepo(db)
    await orders.set_status(order_id, status)

    await cq.answer("Статус обновлён")
    data = await state.get_data()
    back_target = data.get("order_back_target") or "r:orders"
    text, kb = await build_order_card_payload(db, order_id, back_target)
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "r:back:main")
async def back_main(cq: CallbackQuery):
    await cq.message.edit_text("Админ-меню ресторана:", reply_markup=kb_admin_main())
    await cq.answer()
