from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from app.handlers_admin_restaurant.start import kb_admin_main  # добавь импорт

from app.db.database import Database
from app.handlers_admin_restaurant.utils import get_admin_restaurant_ids
from app.repositories.orders_repo import OrdersRepo
from app.services.chat_reminders import is_chat_reminder_text
from app.services.screen import clear_state_keep_screen, show_screen
from app.utils.tg_safe import safe_delete_cq_message

router = Router()

CURRENT = ["new", "preparing", "on_the_way"]
DONE = ["finished", "canceled"]


def kb_orders_list(order_ids: list[int]) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"r:order:{oid}")])

    kb.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_order_card(order_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="👨‍🍳 Готовится", callback_data=f"r:st:{order_id}:preparing")],
        [InlineKeyboardButton(text="🚚 В пути", callback_data=f"r:st:{order_id}:on_the_way")],
        [InlineKeyboardButton(text="✅ Завершён", callback_data=f"r:st:{order_id}:finished")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"r:st:{order_id}:canceled")],
        [InlineKeyboardButton(text="💬 Чат по заказу", callback_data=f"r:chat:{order_id}")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="r:orders"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def build_order_card_payload(db: Database, order_id: int) -> tuple[str, InlineKeyboardMarkup]:
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o:
        return (
            "Заказ не найден.",
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
                        InlineKeyboardButton(text="🔙 Назад", callback_data="r:orders"),
                    ]
                ]
            ),
        )

    items = await orders.get_order_items(order_id)
    lines = [
        f"Заказ #{o['id']}",
        f"Статус: {o['status']}",
        f"Сумма: {o['total_amount']}",
        "",
        "Состав:",
    ]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")

    return "\n".join(lines), kb_order_card(order_id)


async def render_order_card(cq: CallbackQuery, db: Database, order_id: int):
    text, kb = await build_order_card_payload(db, order_id)
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "r:orders")
async def list_orders(cq: CallbackQuery, db: Database):
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

    restaurant_id = ids[0]  # MVP: первый ресторан админа

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
        await cq.answer()
        return

    order_ids = [int(r["id"]) for r in rows]
    await cq.message.edit_text(
        f"Текущие заказы (restaurant_id={restaurant_id}):",
        reply_markup=kb_orders_list(order_ids),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("r:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[2])
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Напоминание удаляем и показываем карточку через screen.py.
        await clear_state_keep_screen(state, db, "admin_restaurant", cq.from_user.id)
        await safe_delete_cq_message(cq)
        text, kb = await build_order_card_payload(db, order_id)
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
        await render_order_card(cq, db, order_id)
    await cq.answer()


@router.callback_query(F.data.startswith("r:st:"))
async def set_status(cq: CallbackQuery, db: Database):
    _, _, order_id_str, status = cq.data.split(":", 3)
    order_id = int(order_id_str)

    orders = OrdersRepo(db)
    await orders.set_status(order_id, status)

    await cq.answer("Статус обновлён")
    await render_order_card(cq, db, order_id)


@router.callback_query(F.data == "r:back:main")
async def back_main(cq: CallbackQuery):
    await cq.message.edit_text("Админ-меню ресторана:", reply_markup=kb_admin_main())
    await cq.answer()
