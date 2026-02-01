from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.db.database import Database
from app.handlers_admin_shop.utils import get_admin_shop_ids, is_shop_admin
from app.repositories.chat_repo import ChatRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo
from app.handlers_admin_shop.start import kb_admin_main
from app.ui.nav import kb_nav
from app.ui.chat import build_chat_screen_text, build_chat_screen_kb, CHAT_PAGE_SIZE

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
    return kb_nav(home_cb="a:home", back_cb="a:chat")


def _calc_total_pages(total_messages: int, page_size: int) -> int:
    if total_messages <= 0:
        return 1
    return (total_messages + page_size - 1) // page_size


async def _get_business_type(db: Database, order_id: int) -> str:
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    if not order:
        return "shop"
    shops = ShopsRepo(db)
    shop = await shops.get(int(order["shop_id"]))
    return shop.get("business_type") if shop else "shop"


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
    await render_chat_page(
        cq.message.bot,
        cq.message.chat.id,
        cq.message.message_id,
        db,
        order_id,
        page=None,
    )


async def render_chat_page(
    bot,
    chat_id: int,
    message_id: int | None,
    db: Database,
    order_id: int,
    page: int | None,
):
    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = _calc_total_pages(total_messages, CHAT_PAGE_SIZE)
    current_page = page or total_pages
    if current_page < 1:
        current_page = 1
    if current_page > total_pages:
        current_page = total_pages
    offset = (current_page - 1) * CHAT_PAGE_SIZE
    messages = await chat.list_messages_page(order_id, limit=CHAT_PAGE_SIZE, offset=offset)
    business_type = await _get_business_type(db, order_id)
    text = build_chat_screen_text(
        order_id=order_id,
        messages=list(messages),
        show_hint=False,
        business_type=business_type,
        page=current_page,
        page_size=CHAT_PAGE_SIZE,
    )
    kb = build_chat_screen_kb(
        order_id=order_id,
        page=current_page,
        total_pages=total_pages,
        prefix="a",
        home_cb="a:home",
        back_cb="a:chat",
    )
    if message_id is not None:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=kb,
        )
    return text, kb


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
    await state.update_data(
        chat_order_id=order_id,
        chat_message_id=cq.message.message_id,
        chat_message_chat_id=cq.message.chat.id,
        chat_page=None,
    )
    await render_chat_page(
        cq.message.bot,
        cq.message.chat.id,
        cq.message.message_id,
        db,
        order_id,
        page=None,
    )
    await cq.answer()


@router.callback_query(F.data.startswith("a:chatp:"))
async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    _, _, order_id_str, page_str = cq.data.split(":")
    order_id = int(order_id_str)
    page = int(page_str)
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not order or int(order["shop_id"]) not in shop_ids:
        await cq.message.edit_text("Чат недоступен.", reply_markup=kb_admin_main())
        await cq.answer()
        return
    await state.update_data(chat_order_id=order_id, chat_page=page)
    await render_chat_page(
        cq.message.bot,
        cq.message.chat.id,
        cq.message.message_id,
        db,
        order_id,
        page=page,
    )
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

    data = await state.get_data()
    chat_message_id = data.get("chat_message_id")
    chat_message_chat_id = data.get("chat_message_chat_id")
    if chat_message_id and chat_message_chat_id:
        await render_chat_page(
            message.bot,
            int(chat_message_chat_id),
            int(chat_message_id),
            db,
            order_id,
            page=None,
        )
    else:
        text, kb = await render_chat_page(
            message.bot,
            message.chat.id,
            None,
            db,
            order_id,
            page=None,
        )
        sent = await message.answer(text, reply_markup=kb)
        await state.update_data(
            chat_message_id=sent.message_id,
            chat_message_chat_id=sent.chat.id,
        )
