from aiogram.exceptions import TelegramBadRequest
from app.utils.tg_safe import safe_edit_text
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from app.handlers_admin_shop.start import kb_admin_main  # добавь импорт

from app.db.database import Database
from app.handlers_admin_shop.utils import get_admin_shop_ids
from app.repositories.orders_repo import OrdersRepo

router = Router()


def kb_back_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="a:back:main")]
    ])


def kb_orders_list(order_ids: list[int]) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"a:order:{oid}")])

    kb.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="a:back:main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_order_card(order_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Готовится", callback_data=f"a:st:{order_id}:preparing")],
        [InlineKeyboardButton(text="📦 Готово", callback_data=f"a:st:{order_id}:ready")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"a:st:{order_id}:canceled")],
        [InlineKeyboardButton(text="💬 Чат по заказу", callback_data=f"a:chat:{order_id}")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="a:orders"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.callback_query(F.data == "a:home")
async def admin_home(cq: CallbackQuery, db: Database):
    await safe_edit_text(cq.message, "Админ-меню магазина:", reply_markup=kb_admin_main())

    await cq.answer()


@router.callback_query(F.data == "a:orders")
async def list_orders(cq: CallbackQuery, db: Database):
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not shop_ids:
        await safe_edit_text(cq.message, "Нет доступа.", reply_markup=kb_back_admin())
        await cq.answer()
        return

    # MVP: показываем заказы первого магазина админа
    shop_id = shop_ids[0]

    orders = OrdersRepo(db)
    rows = await orders.list_current_for_shop(shop_id=shop_id, statuses=["new", "preparing", "ready"])
    if not rows:
        await safe_edit_text(
            cq.message,
            f"Текущие заказы (shop_id={shop_id}):",
            reply_markup=kb_orders_list(order_ids),
        )
        await cq.answer()
        return

    order_ids = [int(r["id"]) for r in rows]
    await cq.message.edit_text(f"Текущие заказы (shop_id={shop_id}):", reply_markup=kb_orders_list(order_ids))
    await cq.answer()


@router.callback_query(F.data.startswith("a:order:"))
async def order_card(cq: CallbackQuery, db: Database):
    order_id = int(cq.data.split(":")[2])

    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o:
        await safe_edit_text(cq.message, "Заказ не найден.", reply_markup=kb_back_admin())
        await cq.answer()
        return

    items = await orders.get_order_items(order_id)
    lines = [f"Заказ #{o['id']}", f"Статус: {o['status']}", f"Сумма: {o['total_amount']}", "", "Состав:"]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")

    await safe_edit_text(cq.message, "\n".join(lines), reply_markup=kb_order_card(order_id))
    await cq.answer()


@router.callback_query(F.data.startswith("a:st:"))
async def set_status(cq: CallbackQuery, db: Database):
    # a:st:{order_id}:{status}
    _, _, order_id_str, status = cq.data.split(":", 3)
    order_id = int(order_id_str)

    orders = OrdersRepo(db)
    await orders.set_status(order_id, status)

    await cq.answer("Статус обновлён")
    # перерисуем карточку заказа
    o = await orders.get_order(order_id)
    items = await orders.get_order_items(order_id)
    lines = [f"Заказ #{o['id']}", f"Статус: {o['status']}", f"Сумма: {o['total_amount']}", "", "Состав:"]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")
    await safe_edit_text(cq.message, "\n".join(lines), reply_markup=kb_order_card(order_id))


@router.callback_query(F.data == "a:back:main")
async def back_main(cq: CallbackQuery):
    await safe_edit_text(cq.message, "Админ-меню магазина:", reply_markup=kb_admin_main())
    await cq.answer()
