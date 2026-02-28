from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from app.handlers_admin_restaurant.start import build_admin_restaurant_main_kb

from app.db.database import Database
from app.handlers_admin_restaurant.utils import get_admin_restaurant_ids
from app.repositories.orders_repo import OrdersRepo
from app.repositories.order_seen_repo import OrderSeenRepo
from app.services.chat_reminders import is_chat_reminder_text
from app.services.order_chat_access import can_access_order_chat
from app.services.notification_center import remember_admin_prev_target, parse_notif_context, NOTIF_SRC_ORDERS
from app.services.screen import clear_state_keep_screen, show_screen
from app.utils.tg_safe import safe_delete_cq_message
from app.services.pagination import calc_page, pager_row
from app.services.order_ui_status import admin_order_sort_key, admin_order_status_emoji

PAGE_SIZE = 8

router = Router()

def _format_fulfillment_type(value: str | None) -> str:
    mapping = {
        "courier": "🚚 Доставка",
        "pickup": "🏬 Самовывоз",
        "dine_in": "🍽 В зале",
    }
    return mapping.get((value or "").strip(), "🚚 Доставка")


CURRENT = ["new", "preparing", "ready"]
DONE = ["delivered", "canceled", "finished"]


def kb_orders_list(rows: list[dict]) -> InlineKeyboardMarkup:
    kb = []
    for row in rows:
        oid = int(row["id"])
        emoji = admin_order_status_emoji(row)
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}  {emoji}", callback_data=f"r:order:{oid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_order_card(order_id: int, can_chat: bool = True) -> InlineKeyboardMarkup:
    return kb_order_card_with_back(order_id, "r:orders", can_chat)


def kb_order_card_with_back(order_id: int, back_target: str, can_chat: bool = True, show_status_actions: bool = True) -> InlineKeyboardMarkup:
    kb = []
    if show_status_actions:
        kb.extend([
            [InlineKeyboardButton(text="👨‍🍳 Готовится", callback_data=f"r:st:{order_id}:preparing")],
            [InlineKeyboardButton(text="📦 Готово", callback_data=f"r:st:{order_id}:ready")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"r:st:{order_id}:canceled")],
        ])
    if can_chat:
        kb.append([InlineKeyboardButton(text="💬 Чат по заказу", callback_data=f"r:chat:{order_id}")])
    kb.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data=back_target),
    ])
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
    merchant_status = str(o.get("merchant_status") or "")
    show_actions = merchant_status in {"new", "preparing"}
    return "\n".join(lines), kb_order_card_with_back(order_id, back_target, can_chat, show_status_actions=show_actions)


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




async def render_orders_list(cq: CallbackQuery, db: Database, restaurant_id: int, page: int) -> None:
    orders = OrdersRepo(db)
    total = await orders.count_active_for_shop(restaurant_id)
    if total <= 0:
        await cq.message.edit_text(
            f"Текущих заказов нет (restaurant_id={restaurant_id}).",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
            ]]),
        )
        return

    pi = calc_page(total=total, page=page, page_size=PAGE_SIZE)
    rows = await orders.list_active_for_shop_page(shop_id=restaurant_id, limit=total, offset=0)
    sorted_rows = sorted(rows, key=admin_order_sort_key)
    page_rows = sorted_rows[pi.offset:pi.offset + pi.limit]
    kb = kb_orders_list(page_rows)
    pager = pager_row("r:orders", pi.page, pi.total_pages)
    if pager:
        kb.inline_keyboard.append(pager)
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
    ])
    await cq.message.edit_text(f"Текущие заказы (restaurant_id={restaurant_id}):", reply_markup=kb)

async def render_order_card(cq: CallbackQuery, db: Database, order_id: int):
    text, kb = await build_order_card_payload(db, order_id, "r:orders")
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("r:orders:p:"))
async def list_orders_page(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    await list_orders_render(cq, db, state, page=page)


@router.callback_query(F.data == "r:orders")
async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext):
    await list_orders_render(cq, db, state, page=0)


async def list_orders_render(cq: CallbackQuery, db: Database, state: FSMContext, page: int):
    await remember_admin_prev_target(db, "admin_restaurant", cq.from_user.id, "r:orders")
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not ids:
        await cq.message.edit_text(
            "Нет доступа.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
            ]]),
        )
        await cq.answer()
        return

    restaurant_id = ids[0]
    await render_orders_list(cq, db, restaurant_id, page)
    await cq.answer()


@router.callback_query(F.data.startswith("r:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
    parts = cq.data.split(":")
    order_id = int(parts[2])
    await remember_admin_prev_target(db, "admin_restaurant", cq.from_user.id, f"r:order:{order_id}")
    src, page = parse_notif_context(cq.data)
    back_target = ":".join(parts[3:]) if len(parts) > 3 else "r:orders"
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
    await orders.set_merchant_status(order_id, status)

    await cq.answer("Статус обновлён")
    data = await state.get_data()
    back_target = data.get("order_back_target") or "r:orders"
    text, kb = await build_order_card_payload(db, order_id, back_target)
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "r:back:main")
async def back_main(cq: CallbackQuery, db: Database):
    await cq.message.edit_text("Админ-меню ресторана:", reply_markup=await build_admin_restaurant_main_kb(db, cq.from_user.id))
    await cq.answer()
