from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.db.database import Database
from app.handlers_client.kb import kb_client_main, kb_orders_list, kb_chat_orders, kb_back
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo
from app.repositories.chat_repo import ChatRepo
from app.repositories.admins_repo import AdminsRepo
from app.ui.chat import build_chat_screen_text, build_chat_screen_kb, CHAT_PAGE_SIZE

router = Router()

DONE_STATUSES = ["ready", "finished", "canceled", "delivered"]


class ClientChatStates(StatesGroup):
    active = State()


def kb_order_card(order_id: int, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Чат по заказу", callback_data=f"c:chat:{order_id}")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="c:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb),
        ],
    ])


def kb_chat_nav(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="c:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"c:order:{order_id}"),
        ],
    ])


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


@router.callback_query(F.data == "c:orders")
async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext):
    await state.clear()
    orders = OrdersRepo(db)
    rows = await orders.list_for_client(cq.from_user.id)
    if not rows:
        await cq.message.edit_text("Заказов пока нет.", reply_markup=kb_client_main())
        await cq.answer()
        return

    order_ids = [int(r["id"]) for r in rows]
    await cq.message.edit_text("Ваши заказы:", reply_markup=kb_orders_list(order_ids))
    await cq.answer()


@router.callback_query(F.data == "c:history")
async def list_history(cq: CallbackQuery, db: Database, state: FSMContext):
    await state.clear()
    orders = OrdersRepo(db)
    rows = await orders.list_for_client(cq.from_user.id, statuses=DONE_STATUSES)
    if not rows:
        await cq.message.edit_text("История заказов пуста.", reply_markup=kb_back("order_menu"))
        await cq.answer()
        return

    order_ids = [int(r["id"]) for r in rows]
    await cq.message.edit_text("История заказов:", reply_markup=kb_orders_list(order_ids, back_target="order_menu"))
    await cq.answer()


@router.callback_query(F.data.startswith("c:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
    await state.clear()
    order_id = int(cq.data.split(":")[2])
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        await cq.message.edit_text("Заказ не найден.", reply_markup=kb_client_main())
        await cq.answer()
        return

    items = await orders.get_order_items(order_id)
    shop = ShopsRepo(db)
    shop_info = await shop.get(int(o["shop_id"]))
    shop_name = shop_info["name"] if shop_info else f"#{o['shop_id']}"

    lines = [
        f"Заказ #{o['id']}",
        f"Точка: {shop_name}",
        f"Статус: {o['status']}",
        f"Сумма: {o['total_amount']}",
        "",
        "Состав:",
    ]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")

    back_cb = "c:history" if o["status"] in DONE_STATUSES else "c:orders"
    await cq.message.edit_text("\n".join(lines), reply_markup=kb_order_card(order_id, back_cb))
    await cq.answer()


@router.callback_query(F.data == "c:chat")
async def chat_list(cq: CallbackQuery, db: Database, state: FSMContext):
    await state.clear()
    chats = ChatRepo(db)
    order_ids = await chats.list_order_ids_with_chat(user_id=cq.from_user.id)
    if not order_ids:
        await cq.message.edit_text("Активных чатов нет.", reply_markup=kb_client_main())
        await cq.answer()
        return

    await cq.message.edit_text("Чаты по заказам:", reply_markup=kb_chat_orders(order_ids, "c"))
    await cq.answer()


async def render_chat(cq: CallbackQuery, db: Database, order_id: int):
    await render_chat_page(
        cq.message.bot,
        cq.message.chat.id,
        cq.message.message_id,
        db,
        order_id,
        page=None,
        show_hint=False,
    )


async def render_chat_page(
    bot,
    chat_id: int,
    message_id: int | None,
    db: Database,
    order_id: int,
    page: int | None,
    show_hint: bool,
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
        show_hint=show_hint,
        business_type=business_type,
        page=current_page,
        page_size=CHAT_PAGE_SIZE,
    )
    kb = build_chat_screen_kb(
        order_id=order_id,
        page=current_page,
        total_pages=total_pages,
        prefix="c",
        home_cb="c:home",
        back_cb=f"c:order:{order_id}",
    )
    if message_id is not None:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=kb,
        )
    return text, kb


@router.callback_query(F.data.startswith("c:chat:"))
async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    order_id = int(cq.data.split(":")[2])
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        await cq.message.edit_text("Чат не найден.", reply_markup=kb_client_main())
        await cq.answer()
        return

    await state.set_state(ClientChatStates.active)
    data = await state.get_data()
    shown_orders = set(data.get("chat_hint_orders") or [])
    show_hint = order_id not in shown_orders
    if show_hint:
        shown_orders.add(order_id)
    await state.update_data(
        chat_order_id=order_id,
        chat_message_id=cq.message.message_id,
        chat_message_chat_id=cq.message.chat.id,
        chat_page=None,
        chat_hint_orders=list(shown_orders),
    )
    await render_chat_page(
        cq.message.bot,
        cq.message.chat.id,
        cq.message.message_id,
        db,
        order_id,
        page=None,
        show_hint=show_hint,
    )
    await cq.answer()


@router.callback_query(F.data.startswith("c:chatp:"))
async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    _, _, order_id_str, page_str = cq.data.split(":")
    order_id = int(order_id_str)
    page = int(page_str)
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    if not order or int(order["client_user_id"]) != cq.from_user.id:
        await cq.message.edit_text("Чат недоступен.", reply_markup=kb_client_main())
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
        show_hint=False,
    )
    await cq.answer()


@router.message(ClientChatStates.active)
async def send_chat_message(message: Message, state: FSMContext, db: Database):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите сообщение текстом.")
        return

    data = await state.get_data()
    order_id = int(data.get("chat_order_id") or 0)
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != message.from_user.id:
        await message.answer("Чат недоступен.")
        return

    chat = ChatRepo(db)
    await chat.add_message(order_id, message.from_user.id, "client", text)

    admins = AdminsRepo(db)
    admin_ids = await admins.list_admin_user_ids(int(o["shop_id"]))
    for uid in admin_ids:
        try:
            await message.bot.send_message(uid, f"💬 Сообщение по заказу #{order_id}\n{text}")
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
            show_hint=False,
        )
    else:
        text, kb = await render_chat_page(
            message.bot,
            message.chat.id,
            None,
            db,
            order_id,
            page=None,
            show_hint=False,
        )
        sent = await message.answer(text, reply_markup=kb)
        await state.update_data(
            chat_message_id=sent.message_id,
            chat_message_chat_id=sent.chat.id,
        )
