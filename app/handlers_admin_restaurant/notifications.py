from __future__ import annotations

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_restaurant.orders import (
    list_orders as render_orders,
    build_order_card_payload,
)
from app.handlers_admin_restaurant.extra import chat_list as render_chats, open_chat_by_order_id
from app.handlers_admin_restaurant.products import list_categories as render_categories
from app.handlers_admin_restaurant.start import kb_admin_main
from app.repositories.admin_nav_repo import AdminNavRepo
from app.repositories.notif_center_repo import NotifCenterRepo
from app.repositories.order_seen_repo import OrderSeenRepo
from app.services.notification_center import (
    build_admin_center_payload,
    build_admin_orders_payload,
    build_admin_messages_payload,
    NOTIF_SCREEN_KEY,
    get_notif_center_lock,
)
from app.services.screen import get_screen_message_id, safe_edit_text, set_screen_message_id

router = Router()


async def _edit_current_screen(
    cq: CallbackQuery,
    db: Database,
    state: FSMContext,
    text: str,
    role: str,
    reply_markup,
) -> int:
    current_screen_id = await get_screen_message_id(state, db, role, cq.from_user.id)
    callback_message_id = cq.message.message_id if cq.message else None
    target_message_id = current_screen_id or callback_message_id

    if target_message_id is None:
        message = await cq.bot.send_message(chat_id=cq.from_user.id, text=text, reply_markup=reply_markup)
        await set_screen_message_id(state, db, role, cq.from_user.id, message.message_id)
        return message.message_id

    try:
        if callback_message_id and callback_message_id == target_message_id and cq.message is not None:
            await safe_edit_text(cq, text, reply_markup=reply_markup)
        else:
            await cq.bot.edit_message_text(
                chat_id=cq.from_user.id,
                message_id=target_message_id,
                text=text,
                reply_markup=reply_markup,
            )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise

    await set_screen_message_id(state, db, role, cq.from_user.id, target_message_id)
    return target_message_id


async def _render_center(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    text, kb = await build_admin_center_payload(db, "admin_restaurant", cq.from_user.id)
    await state.update_data({NOTIF_SCREEN_KEY: "center"})
    lock = get_notif_center_lock("admin_restaurant", cq.from_user.id)
    async with lock:
        message_id = await _edit_current_screen(cq, db, state, text, "admin_restaurant", kb)
        await NotifCenterRepo(db).set_message_id("admin_restaurant", cq.from_user.id, message_id)


async def _render_orders(cq: CallbackQuery, db: Database, state: FSMContext, page: int) -> None:
    text, kb = await build_admin_orders_payload(db, "admin_restaurant", cq.from_user.id, page)
    await state.update_data({NOTIF_SCREEN_KEY: "orders"})
    lock = get_notif_center_lock("admin_restaurant", cq.from_user.id)
    async with lock:
        message_id = await _edit_current_screen(cq, db, state, text, "admin_restaurant", kb)
        await NotifCenterRepo(db).set_message_id("admin_restaurant", cq.from_user.id, message_id)


async def _render_messages(cq: CallbackQuery, db: Database, state: FSMContext, page: int) -> None:
    text, kb = await build_admin_messages_payload(db, "admin_restaurant", cq.from_user.id, page)
    await state.update_data({NOTIF_SCREEN_KEY: "messages"})
    lock = get_notif_center_lock("admin_restaurant", cq.from_user.id)
    async with lock:
        message_id = await _edit_current_screen(cq, db, state, text, "admin_restaurant", kb)
        await NotifCenterRepo(db).set_message_id("admin_restaurant", cq.from_user.id, message_id)


@router.callback_query(F.data == "r:notif")
async def notif_center(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await _render_center(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "r:notif:orders")
async def notif_orders(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await _render_orders(cq, db, state, page=1)
    await cq.answer()


@router.callback_query(F.data.startswith("r:notif:op:"))
async def notif_orders_page(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    page = int(cq.data.split(":")[3])
    await _render_orders(cq, db, state, page=page)
    await cq.answer()


@router.callback_query(F.data == "r:notif:msgs")
async def notif_messages(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await _render_messages(cq, db, state, page=1)
    await cq.answer()


@router.callback_query(F.data.startswith("r:notif:mp:"))
async def notif_messages_page(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    page = int(cq.data.split(":")[3])
    await _render_messages(cq, db, state, page=page)
    await cq.answer()


@router.callback_query(F.data == "r:notif:back")
async def notif_back(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await _render_center(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "r:notif:return")
async def notif_return(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    lock = get_notif_center_lock("admin_restaurant", cq.from_user.id)
    async with lock:
        target = await AdminNavRepo(db).get_prev_target("admin_restaurant", cq.from_user.id)
        await state.update_data({NOTIF_SCREEN_KEY: None})

        if not target or target == "r:home":
            message_id = await _edit_current_screen(
                cq,
                db,
                state,
                "Админ-меню ресторана:",
                "admin_restaurant",
                kb_admin_main(),
            )
            await NotifCenterRepo(db).set_message_id("admin_restaurant", cq.from_user.id, message_id)
            await cq.answer()
            return

        if target == "r:orders":
            await render_orders(cq, db, state)
            await cq.answer()
            return

        if target == "r:cats":
            await render_categories(cq, db)
            await cq.answer()
            return

        if target.startswith("r:order:"):
            order_id = int(target.split(":")[2])
            text, kb = await build_order_card_payload(db, order_id, "r:orders")
            message_id = await _edit_current_screen(cq, db, state, text, "admin_restaurant", kb)
            await NotifCenterRepo(db).set_message_id("admin_restaurant", cq.from_user.id, message_id)
            await OrderSeenRepo(db).mark_order_seen(order_id, "admin_restaurant", cq.from_user.id)
            await cq.answer()
            return

        if target == "r:chat":
            await render_chats(cq, db, state)
            await cq.answer()
            return

        if target.startswith("r:chat:"):
            order_id = int(target.split(":")[2])
            await open_chat_by_order_id(cq, state, db, order_id, "r:chat")
            await cq.answer()
            return

        message_id = await _edit_current_screen(
            cq,
            db,
            state,
            "Админ-меню ресторана:",
            "admin_restaurant",
            kb_admin_main(),
        )
        await NotifCenterRepo(db).set_message_id("admin_restaurant", cq.from_user.id, message_id)

    await cq.answer()
