from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.db.database import Database
from app.handlers_admin_shop.utils import get_admin_shop_ids, is_shop_admin
from app.repositories.chat_repo import ChatRepo
from app.repositories.orders_repo import OrdersRepo
from app.handlers_admin_shop.start import kb_admin_main

router = Router()


class AdminShopChatStates(StatesGroup):
    active = State()


def kb_chat_list(order_ids: list[int]) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"a:chat:{oid}")])
    kb.append([InlineKeyboardButton(text="🏠 Главная", callback_data="a:home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_chat_nav(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="a:chat"),
        ],
    ])


@router.callback_query(F.data == "a:chat")
async def list_chats(cq: CallbackQuery, db: Database, state: FSMContext):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    await state.clear()
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not shop_ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_admin_main())
        await cq.answer()
        return

    chat = ChatRepo(db)
    order_ids = await chat.list_order_ids_with_chat(shop_id=shop_ids[0])
    if not order_ids:
        await cq.message.edit_text("Активных чатов нет.", reply_markup=kb_admin_main())
        await cq.answer()
        return

    await cq.message.edit_text("Чаты по заказам:", reply_markup=kb_chat_list(order_ids))
    await cq.answer()


async def render_chat(cq: CallbackQuery, db: Database, order_id: int):
    chat = ChatRepo(db)
    messages = await chat.list_messages(order_id, limit=20)
    if not messages:
        text = "Чат пуст. Напишите сообщение клиенту."
    else:
        lines = ["💬 Чат по заказу:"]
        for msg in messages:
            role = "Клиент" if msg["sender_role"] == "client" else "Вы"
            lines.append(f"{role}: {msg['message_text']}")
        text = "\n".join(lines)
    await cq.message.edit_text(text, reply_markup=kb_chat_nav(order_id))


@router.callback_query(F.data.startswith("a:chat:"))
async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    order_id = int(cq.data.split(":")[2])
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not order or int(order["shop_id"]) not in shop_ids:
        await cq.message.edit_text("Чат недоступен.", reply_markup=kb_admin_main())
        await cq.answer()
        return
    await state.set_state(AdminShopChatStates.active)
    await state.update_data(chat_order_id=order_id)
    await render_chat(cq, db, order_id)
    await cq.answer()


@router.message(AdminShopChatStates.active)
async def send_chat_message(message: Message, state: FSMContext, db: Database):
    if not await is_shop_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return

    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите сообщение текстом.")
        return

    data = await state.get_data()
    order_id = int(data.get("chat_order_id") or 0)
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    shop_ids = await get_admin_shop_ids(db, message.from_user.id)
    if not order or int(order["shop_id"]) not in shop_ids:
        await message.answer("Чат недоступен.")
        return

    chat = ChatRepo(db)
    await chat.add_message(order_id, message.from_user.id, "admin", text)

    try:
        await message.bot.send_message(int(order["client_user_id"]), f"💬 Сообщение по заказу #{order_id}\n{text}")
    except Exception:
        pass

    await message.answer("Сообщение отправлено.", reply_markup=kb_chat_nav(order_id))
