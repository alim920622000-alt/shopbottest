from __future__ import annotations

from aiogram import Router, F
from typing import Callable

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
)
from app.services.screen import clear_state_keep_screen, set_screen_message_id
from app.services.chat_screen_controller import ChatScreenController
from app.services.client_ui_state import remember_client_screen

router = Router()

DONE_STATUSES = ["ready", "finished", "canceled", "delivered"]


class ClientChatStates(StatesGroup):
    active = State()


def kb_order_card(locale: str, t: Callable[[str, str], str], order_id: int, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "order_card.chat"), callback_data=f"c:chat:{order_id}")],
        [
            InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home"),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=back_cb),
        ],
    ])


def kb_chat_nav_rows(locale: str, t: Callable[[str, str], str], order_id: int) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home"),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:order:{order_id}"),
        ],
    ]

def make_chat_render_fn(db: Database, state: FSMContext, locale: str, t: Callable[[str, str], str]):
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

        text = build_chat_screen_text(order_id, messages, False, business_type, locale=locale, t=t)
        kb = build_chat_screen_kb(order_id, page, total_pages, "c", kb_chat_nav_rows(locale, t, order_id))
        return text, kb

    return render


@router.callback_query(F.data == "c:orders")
async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    await clear_state_keep_screen(state)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "orders", {})
    orders = OrdersRepo(db)
    rows = await orders.list_for_client(cq.from_user.id)
    if not rows:
        await cq.message.edit_text(t(locale, "orders.empty"), reply_markup=kb_client_main(locale, t))
        await cq.answer()
        return

    order_ids = [int(r["id"]) for r in rows]
    await cq.message.edit_text(t(locale, "orders.title"), reply_markup=kb_orders_list(locale, t, order_ids))
    await cq.answer()


@router.callback_query(F.data == "c:history")
async def list_history(cq: CallbackQuery, db: Database, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    await clear_state_keep_screen(state)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "history", {})
    orders = OrdersRepo(db)
    rows = await orders.list_for_client(cq.from_user.id, statuses=DONE_STATUSES)
    if not rows:
        await cq.message.edit_text(t(locale, "orders.history.empty"), reply_markup=kb_back(locale, t, "order_menu"))
        await cq.answer()
        return

    order_ids = [int(r["id"]) for r in rows]
    await cq.message.edit_text(
        t(locale, "orders.history.title"),
        reply_markup=kb_orders_list(locale, t, order_ids, back_target="order_menu"),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("c:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    await clear_state_keep_screen(state)
    order_id = int(cq.data.split(":")[2])
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "order_card", {"order_id": order_id})
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        await cq.message.edit_text(t(locale, "order.not_found"), reply_markup=kb_client_main(locale, t))
        await cq.answer()
        return

    items = await orders.get_order_items(order_id)
    shop = ShopsRepo(db)
    shop_info = await shop.get(int(o["shop_id"]))
    shop_name = shop_info["name"] if shop_info else f"#{o['shop_id']}"

    lines = [
        t(locale, "orders.item_tpl", order_id=o["id"]),
        t(locale, "order.shop", shop_name=shop_name),
        t(locale, "order.status", status=o["status"]),
        t(locale, "order.total", total=o["total_amount"]),
        "",
        t(locale, "order.items_title"),
    ]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")

    back_cb = "c:history" if o["status"] in DONE_STATUSES else "c:orders"
    await cq.message.edit_text("\n".join(lines), reply_markup=kb_order_card(locale, t, order_id, back_cb))
    await cq.answer()


@router.callback_query(F.data == "c:chat")
async def chat_list(cq: CallbackQuery, db: Database, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    await clear_state_keep_screen(state)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "chat_list", {})
    chats = ChatRepo(db)
    order_ids = await chats.list_order_ids_with_chat(user_id=cq.from_user.id)
    if not order_ids:
        await cq.message.edit_text(t(locale, "chat.none"), reply_markup=kb_client_main(locale, t))
        await cq.answer()
        return

    await cq.message.edit_text(t(locale, "chat.list_title"), reply_markup=kb_chat_orders(locale, t, order_ids, "c"))
    await cq.answer()


async def render_chat(
    cq: CallbackQuery,
    db: Database,
    order_id: int,
    page: int,
    show_hint: bool,
    locale: str,
    t: Callable[[str, str], str],
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

    text = build_chat_screen_text(order_id, messages, show_hint, business_type, locale=locale, t=t)
    kb = build_chat_screen_kb(order_id, page, total_pages, "c", kb_chat_nav_rows(locale, t, order_id))
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("c:chat:"))
@router.callback_query(F.data.startswith("c:chat:"))
async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database, locale: str, t: Callable[[str, str], str]):
    order_id = int(cq.data.split(":")[2])
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        await cq.message.edit_text(t(locale, "chat.not_found"), reply_markup=kb_client_main(locale, t))
        await cq.answer()
        return

    await state.set_state(ClientChatStates.active)
    await state.update_data(chat_order_id=order_id)

    # сразу ставим страницу на последнюю
    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
    await state.update_data(chat_page=total_pages)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "chat", {"order_id": order_id, "page": total_pages})

    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=make_chat_render_fn(db, state, locale, t),
    )
    await controller.refresh()
    await cq.answer()


@router.callback_query(F.data.startswith("c:chatp:"))
@router.callback_query(F.data.startswith("c:chatp:"))
async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database, locale: str, t: Callable[[str, str], str]):
    order_id = int(cq.data.split(":")[2])
    page = int(cq.data.split(":")[3])

    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        await cq.answer(t(locale, "chat.unavailable"), show_alert=True)
        return

    await state.update_data(chat_order_id=order_id, chat_page=page)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "chat", {"order_id": order_id, "page": page})

    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=make_chat_render_fn(db, state, locale, t),
    )
    await controller.refresh()
    await cq.answer()


@router.message(ClientChatStates.active)
async def send_chat_message(message: Message, state: FSMContext, db: Database, locale: str, t: Callable[[str, str], str]):
    text = (message.text or "").strip()
    if not text:
        await message.answer(t(locale, "chat.send_prompt"))
        return

    data = await state.get_data()
    order_id = int(data.get("chat_order_id") or 0)
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != message.from_user.id:
        await message.answer(t(locale, "chat.unavailable"))
        return

    chat = ChatRepo(db)
    await chat.add_message(order_id, message.from_user.id, "client", text)

    admins = AdminsRepo(db)
    admin_ids = await admins.list_admin_user_ids(int(o["shop_id"]))
    for uid in admin_ids:
        try:
            await message.bot.send_message(uid, t(locale, "chat.admin_message_tpl", order_id=order_id, text=text))
        except Exception:
            pass
    # 3) после добавления — пересчитать последнюю страницу
    total_messages = await chat.count_messages(order_id)
    total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
    await state.update_data(chat_page=total_pages)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "chat", {"order_id": order_id, "page": total_pages})

    # 4) удалить сообщение пользователя + пересоздать экран
    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=make_chat_render_fn(db, state, locale, t),
    )
    await controller.refresh_after_user_message(message)
