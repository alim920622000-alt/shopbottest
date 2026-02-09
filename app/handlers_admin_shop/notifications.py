from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_shop.orders import list_orders as render_orders, render_order_card_by_id
from app.handlers_admin_shop.chat import list_chats as render_chats, open_chat_by_order_id
from app.handlers_admin_shop.start import kb_admin_main
from app.services.notification_center import (
    build_admin_center_payload,
    build_admin_orders_payload,
    build_admin_messages_payload,
    NOTIF_PREV_TARGET_KEY,
    NOTIF_SCREEN_KEY,
)
from app.services.screen import show_main_menu, show_screen

router = Router()


async def _render_center(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    text, kb = await build_admin_center_payload(db, "admin_shop", cq.from_user.id)
    await state.update_data({NOTIF_SCREEN_KEY: "center"})
    await show_screen(cq.bot, cq.from_user.id, state, db, "admin_shop", text, kb)


async def _render_orders(cq: CallbackQuery, db: Database, state: FSMContext, page: int) -> None:
    text, kb = await build_admin_orders_payload(db, "admin_shop", cq.from_user.id, page)
    await state.update_data({NOTIF_SCREEN_KEY: "orders"})
    await show_screen(cq.bot, cq.from_user.id, state, db, "admin_shop", text, kb)


async def _render_messages(cq: CallbackQuery, db: Database, state: FSMContext, page: int) -> None:
    text, kb = await build_admin_messages_payload(db, "admin_shop", cq.from_user.id, page)
    await state.update_data({NOTIF_SCREEN_KEY: "messages"})
    await show_screen(cq.bot, cq.from_user.id, state, db, "admin_shop", text, kb)


@router.callback_query(F.data == "a:notif")
async def notif_center(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await _render_center(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "a:notif:orders")
async def notif_orders(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await _render_orders(cq, db, state, page=1)
    await cq.answer()


@router.callback_query(F.data.startswith("a:notif:op:"))
async def notif_orders_page(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    page = int(cq.data.split(":")[3])
    await _render_orders(cq, db, state, page=page)
    await cq.answer()


@router.callback_query(F.data == "a:notif:msgs")
async def notif_messages(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await _render_messages(cq, db, state, page=1)
    await cq.answer()


@router.callback_query(F.data.startswith("a:notif:mp:"))
async def notif_messages_page(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    page = int(cq.data.split(":")[3])
    await _render_messages(cq, db, state, page=page)
    await cq.answer()


@router.callback_query(F.data == "a:notif:back")
async def notif_back(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await _render_center(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "a:notif:return")
async def notif_return(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    target = data.get(NOTIF_PREV_TARGET_KEY)
    await state.update_data({NOTIF_PREV_TARGET_KEY: None, NOTIF_SCREEN_KEY: None})
    if not target or target == "a:home":
        await show_main_menu(
            cq.bot,
            cq.from_user.id,
            state,
            db,
            "admin_shop",
            "Админ-меню магазина:",
            kb_admin_main(),
        )
        await cq.answer()
        return
    if target == "a:orders":
        await render_orders(cq, db, state)
        await cq.answer()
        return
    if target.startswith("a:order:"):
        order_id = int(target.split(":")[2])
        await render_order_card_by_id(cq, db, state, order_id)
        await cq.answer()
        return
    if target == "a:chat":
        await render_chats(cq, db, state)
        await cq.answer()
        return
    if target.startswith("a:chat:"):
        order_id = int(target.split(":")[2])
        await open_chat_by_order_id(cq, state, db, order_id)
        await cq.answer()
        return
    await show_main_menu(
        cq.bot,
        cq.from_user.id,
        state,
        db,
        "admin_shop",
        "Админ-меню магазина:",
        kb_admin_main(),
    )
    await cq.answer()
