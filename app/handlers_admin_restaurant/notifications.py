from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_restaurant.orders import list_orders as render_orders, render_order_card_by_id
from app.handlers_admin_restaurant.extra import chat_list as render_chats, open_chat_by_order_id
from app.handlers_admin_restaurant.products import list_categories as render_categories
from app.handlers_admin_restaurant.start import kb_admin_main
from app.repositories.admin_nav_repo import AdminNavRepo
from app.repositories.notif_center_repo import NotifCenterRepo
from app.services.notification_center import (
    build_admin_center_payload,
    build_admin_orders_payload,
    build_admin_messages_payload,
    NOTIF_SCREEN_KEY,
    get_notif_center_lock,
)
from app.services.screen import show_main_menu, show_screen

router = Router()


async def _render_center(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    text, kb = await build_admin_center_payload(db, "admin_restaurant", cq.from_user.id)
    await state.update_data({NOTIF_SCREEN_KEY: "center"})
    lock = get_notif_center_lock("admin_restaurant", cq.from_user.id)
    async with lock:
        message_id = await show_screen(cq.bot, cq.from_user.id, state, db, "admin_restaurant", text, kb)
        await NotifCenterRepo(db).set_message_id("admin_restaurant", cq.from_user.id, message_id)


async def _render_orders(cq: CallbackQuery, db: Database, state: FSMContext, page: int) -> None:
    text, kb = await build_admin_orders_payload(db, "admin_restaurant", cq.from_user.id, page)
    await state.update_data({NOTIF_SCREEN_KEY: "orders"})
    await show_screen(cq.bot, cq.from_user.id, state, db, "admin_restaurant", text, kb)


async def _render_messages(cq: CallbackQuery, db: Database, state: FSMContext, page: int) -> None:
    text, kb = await build_admin_messages_payload(db, "admin_restaurant", cq.from_user.id, page)
    await state.update_data({NOTIF_SCREEN_KEY: "messages"})
    await show_screen(cq.bot, cq.from_user.id, state, db, "admin_restaurant", text, kb)


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
        repo = NotifCenterRepo(db)
        message_id = await repo.get_message_id("admin_restaurant", cq.from_user.id)
        if message_id:
            try:
                await cq.bot.delete_message(chat_id=cq.from_user.id, message_id=message_id)
            except Exception:
                pass
        await repo.clear("admin_restaurant", cq.from_user.id)
    target = await AdminNavRepo(db).get_prev_target("admin_restaurant", cq.from_user.id)
    await state.update_data({NOTIF_SCREEN_KEY: None})
    if not target or target == "r:home":
        await show_main_menu(
            cq.bot,
            cq.from_user.id,
            state,
            db,
            "admin_restaurant",
            "Админ-меню ресторана:",
            kb_admin_main(),
        )
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
        await render_order_card_by_id(cq, db, state, order_id)
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
    await show_main_menu(
        cq.bot,
        cq.from_user.id,
        state,
        db,
        "admin_restaurant",
        "Админ-меню ресторана:",
        kb_admin_main(),
    )
    await cq.answer()
