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
from app.services.chat_ui import (
    PAGE_SIZE,
    build_chat_screen_kb,
    build_chat_screen_text,
    calc_total_pages,
    remember_client_hint,
)
from app.services.screen import clear_state_keep_screen, set_screen_message_id
from app.services.chat_screen_controller import ChatScreenController

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


def kb_chat_nav_rows(order_id: int) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="c:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"c:order:{order_id}"),
        ],
    ]

def make_chat_render_fn(db: Database, state: FSMContext):
    async def render():
        data = await state.get_data()
        order_id = int(data.get("chat_order_id") or 0)

        orders = OrdersRepo(db)
        order = await orders.get_order(order_id)
        shop = ShopsRepo(db)
        shop_info = await shop.get(int(order["shop_id"])) if order else None
        business_type = shop_info["business_type"] if shop_info else "shop"

        chat = ChatRepo(db)
        total_messages = await chat.count_messages(order_id)
        total_pages = calc_total_pages(total_messages, PAGE_SIZE)
        total_pages = max(1, total_pages)

        # текущая страница из state (если нет — последняя)
        page = int(data.get("chat_page") or total_pages)
        page = max(1, min(page, total_pages))

        offset = (total_pages - page) * PAGE_SIZE
        messages = await chat.list_messages(order_id, limit=PAGE_SIZE, offset=offset)

        text = build_chat_screen_text(order_id, messages, False, business_type)
        kb = build_chat_screen_kb(order_id, page, total_pages, "c", kb_chat_nav_rows(order_id))
        return text, kb

    return render


@router.callback_query(F.data == "c:orders")
async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext):
    await clear_state_keep_screen(state)
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
    await clear_state_keep_screen(state)
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
    await clear_state_keep_screen(state)
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
    await clear_state_keep_screen(state)
    chats = ChatRepo(db)
    order_ids = await chats.list_order_ids_with_chat(user_id=cq.from_user.id)
    if not order_ids:
        await cq.message.edit_text("Активных чатов нет.", reply_markup=kb_client_main())
        await cq.answer()
        return

    await cq.message.edit_text("Чаты по заказам:", reply_markup=kb_chat_orders(order_ids, "c"))
    await cq.answer()


async def render_chat(
    cq: CallbackQuery,
    db: Database,
    order_id: int,
    page: int,
    show_hint: bool,
) -> None:
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    shop = ShopsRepo(db)
    shop_info = await shop.get(int(order["shop_id"])) if order else None
    business_type = shop_info["business_type"] if shop_info else "shop"

    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = calc_total_pages(total_messages, PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (total_pages - page) * PAGE_SIZE
    messages = await chat.list_messages(order_id, limit=PAGE_SIZE, offset=offset)

    text = build_chat_screen_text(order_id, messages, show_hint, business_type)
    kb = build_chat_screen_kb(order_id, page, total_pages, "c", kb_chat_nav_rows(order_id))
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("c:chat:"))
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
    await state.update_data(chat_order_id=order_id)

    # сразу ставим страницу на последнюю
    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
    await state.update_data(chat_page=total_pages)

    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=make_chat_render_fn(db, state),
    )
    await controller.refresh()
    await cq.answer()


@router.callback_query(F.data.startswith("c:chatp:"))
@router.callback_query(F.data.startswith("c:chatp:"))
async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    order_id = int(cq.data.split(":")[2])
    page = int(cq.data.split(":")[3])

    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        await cq.answer("Чат недоступен.", show_alert=True)
        return

    await state.update_data(chat_order_id=order_id, chat_page=page)

    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=make_chat_render_fn(db, state),
    )
    await controller.refresh()
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
    # 3) после добавления — пересчитать последнюю страницу
    total_messages = await chat.count_messages(order_id)
    total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
    await state.update_data(chat_page=total_pages)

    # 4) удалить сообщение пользователя + пересоздать экран
    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=make_chat_render_fn(db, state),
    )
    await controller.refresh_after_user_message(message)