from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.exceptions import TelegramBadRequest

from app.db.database import Database
from app.handlers_admin_shop.utils import get_admin_shop_ids, is_shop_admin
from app.repositories.chat_repo import ChatRepo
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.handlers_admin_shop.start import kb_admin_main
from app.ui.nav import kb_nav
from app.services.chat_ui import (
    PAGE_SIZE,
    build_chat_screen_kb,
    build_chat_screen_text,
    calc_total_pages,
)
from app.services.chat_reminders import cancel_chat_reminder, schedule_chat_reminder, is_chat_reminder_text
from app.services.notification_center import remember_admin_prev_target, parse_notif_context, NOTIF_SRC_MSGS
from app.services.screen import clear_state_keep_screen, set_screen_message_id, show_screen
from app.services.chat_screen_controller import ChatScreenController
from app.services.order_chat_access import can_access_order_chat
from app.utils.tg_safe import safe_delete_cq_message
from app.services.pagination import calc_page, pager_row

router = Router()


class AdminShopChatStates(StatesGroup):
    active = State()


def kb_chat_list(order_ids: list[int]) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"a:chat:{oid}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_chat_nav_rows(back_target: str) -> list[list[InlineKeyboardButton]]:
    nav = kb_nav(home_cb="a:home", back_cb=back_target)
    return [list(row) for row in nav.inline_keyboard]


def make_chat_render_fn(db: Database, state: FSMContext):
    async def render():
        data = await state.get_data()
        order_id = int(data.get("chat_order_id") or 0)
        page = int(data.get("chat_page") or 1)
        back_target = data.get("chat_back_target") or "a:chat"
        return await build_chat_payload(db, order_id, page=page, back_target=back_target)

    return render


@router.callback_query(F.data.startswith("a:chat:p:"))
async def list_chats_page(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    await list_chats_render(cq, db, state, page)


@router.callback_query(F.data == "a:chat")
async def list_chats(cq: CallbackQuery, db: Database, state: FSMContext):
    await list_chats_render(cq, db, state, 0)


async def list_chats_render(cq: CallbackQuery, db: Database, state: FSMContext, page: int):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
    await remember_admin_prev_target(db, "admin_shop", cq.from_user.id, "a:chat")
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not shop_ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_admin_main())
        await cq.answer()
        return

    chat = ChatRepo(db)
    total = await chat.count_order_ids_with_chat(shop_id=shop_ids[0])
    if total <= 0:
        await cq.message.edit_text("Активных чатов нет.", reply_markup=kb_admin_main())
        await cq.answer()
        return

    pi = calc_page(total=total, page=page, page_size=8)
    order_ids = await chat.list_order_ids_with_chat_page(shop_id=shop_ids[0], limit=pi.limit, offset=pi.offset)
    kb = kb_chat_list(order_ids)
    pager = pager_row("a:chat", pi.page, pi.total_pages)
    if pager:
        kb.inline_keyboard.append(pager)
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="a:back:main"),
    ])
    await cq.message.edit_text("Чаты по заказам:", reply_markup=kb)
    await cq.answer()


async def build_chat_payload(
    db: Database,
    order_id: int,
    page: int,
    back_target: str,
) -> tuple[str, InlineKeyboardMarkup]:
    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = calc_total_pages(total_messages, PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (total_pages - page) * PAGE_SIZE
    messages = await chat.list_messages(order_id, limit=PAGE_SIZE, offset=offset)

    order = await OrdersRepo(db).get_order(order_id)
    shop_info = await ShopsRepo(db).get(order["shop_id"]) if order else None
    profile = await ClientProfilesRepo(db).get(order["client_user_id"]) if order else None

    shop_name = shop_info["name"] if shop_info else None
    client_name = profile["full_name"] if profile else None
    business_type = shop_info["business_type"] if shop_info else "shop"

    text = build_chat_screen_text(
        order_id,
        messages,
        False,
        business_type,
        "ru",
        "admin",
        shop_name=shop_name,
        client_name=client_name,
    )
    kb = build_chat_screen_kb(order_id, page, total_pages, "a", kb_chat_nav_rows(back_target))
    return text, kb


async def render_chat(cq: CallbackQuery, db: Database, order_id: int, page: int, back_target: str, state: FSMContext | None = None) -> None:
    text, kb = await build_chat_payload(db, order_id, page, back_target)

    try:
        if cq.message:
            await cq.message.edit_text(text, reply_markup=kb)
            return
    except TelegramBadRequest:
        pass

    # если редактировать нельзя — рисуем новый экран
    msg = await cq.bot.send_message(cq.from_user.id, text, reply_markup=kb)
    if state is not None:
        await state.update_data(chat_message_id=msg.message_id)
        await set_screen_message_id(state, db, "admin_shop", msg.chat.id, msg.message_id)


async def open_chat_by_order_id(
    cq: CallbackQuery,
    state: FSMContext,
    db: Database,
    order_id: int,
    back_target: str,
) -> None:
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    await remember_admin_prev_target(db, "admin_shop", cq.from_user.id, f"a:chat:{order_id}")
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not order or int(order["shop_id"]) not in shop_ids:
        await cq.message.edit_text("Чат недоступен.", reply_markup=kb_admin_main())
        await cq.answer()
        return
    if not await can_access_order_chat(db, order):
        await cq.answer("Чат закрыт.", show_alert=True)
        return
    await cancel_chat_reminder(db, order_id, cq.from_user.id, "admin_shop")
    await state.set_state(AdminShopChatStates.active)
    await state.update_data(chat_order_id=order_id, chat_back_target=back_target)
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Для напоминания удаляем сообщение и рисуем чат новым экраном.
        await safe_delete_cq_message(cq)
        text, kb = await build_chat_payload(db, order_id, page=10**9, back_target=back_target)
        message_id = await show_screen(
            bot=cq.bot,
            chat_id=cq.message.chat.id,
            state=state,
            db=db,
            bot_kind="admin_shop",
            text=text,
            reply_markup=kb,
        )
        await state.update_data(chat_message_id=message_id)
    else:
        chat = ChatRepo(db)
        total_messages = await chat.count_messages(order_id)
        total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
        await state.update_data(chat_page=total_pages)
        await state.update_data(chat_message_id=cq.message.message_id)
        await set_screen_message_id(state, db, "admin_shop", cq.message.chat.id, cq.message.message_id)
        await render_chat(cq, db, order_id, page=10**9, back_target=back_target)
    await ChatReadsRepo(db).mark_read(order_id, "admin_shop", cq.from_user.id)
    await cq.answer()


@router.callback_query(F.data.startswith("a:chat:"))
async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    order_id = int(cq.data.split(":")[2])
    src, page = parse_notif_context(cq.data)
    back_target = "a:chat"
    if src == NOTIF_SRC_MSGS:
        page = max(1, page or 1)
        back_target = f"a:notif:msgs" if page == 1 else f"a:notif:mp:{page}"
    await open_chat_by_order_id(cq, state, db, order_id, back_target)


@router.callback_query(F.data.startswith("a:chatp:"))
async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cq.data.split(":")[2])
    page = int(cq.data.split(":")[3])
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not order or int(order["shop_id"]) not in shop_ids:
        await cq.answer("Чат недоступен.", show_alert=True)
        return
    if not await can_access_order_chat(db, order):
        await cq.answer("Чат закрыт.", show_alert=True)
        return
    data = await state.get_data()
    back_target = data.get("chat_back_target") or "a:chat"
    await state.update_data(
        chat_order_id=order_id,
        chat_page=page,
        chat_message_id=cq.message.message_id,
        chat_back_target=back_target,
    )
    await set_screen_message_id(state, db, "admin_shop", cq.message.chat.id, cq.message.message_id)
    await render_chat(cq, db, order_id, page=page, back_target=back_target)
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
    if not await can_access_order_chat(db, order):
        await message.answer("Чат закрыт.")
        return

    chat = ChatRepo(db)
    await chat.add_message(order_id, message.from_user.id, "admin", text)

    await cancel_chat_reminder(db, order_id, message.from_user.id, "admin_shop")
    if order.get("client_user_id"):
        await schedule_chat_reminder(db, order_id, int(order["client_user_id"]), "client", text)
    total_messages = await chat.count_messages(order_id)
    total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
    await state.update_data(chat_page=total_pages)

    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=make_chat_render_fn(db, state),
        db=db,
        bot_kind="admin_shop",
    )
    await controller.refresh_after_user_message(message)
