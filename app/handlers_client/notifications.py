from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.services.chat_screen_controller import ChatScreenController
from app.services.client_ui_renderer import render_client_screen
from app.services.client_ui_state import remember_client_screen
from app.services.notification_center import NOTIF_PREV_PAYLOAD_KEY, NOTIF_PREV_SCREEN_KEY

router = Router()


async def _refresh_client_screen(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=lambda: render_client_screen(db, state),
        db=db,
        bot_kind="client",
    )
    await controller.refresh()


@router.callback_query(F.data == "c:notif")
async def notif_center(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "notif_center", {})
    await _refresh_client_screen(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "c:notif:msgs")
async def notif_messages(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "notif_messages", {"page": 1})
    await _refresh_client_screen(cq, db, state)
    await cq.answer()


@router.callback_query(F.data.startswith("c:notif:msgp:"))
async def notif_messages_page(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    page = int(cq.data.split(":")[3])
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "notif_messages", {"page": page})
    await _refresh_client_screen(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "c:notif:back")
async def notif_back(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "notif_center", {})
    await _refresh_client_screen(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "c:notif:return")
async def notif_return(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    data = await state.get_data()
    prev_screen = data.get(NOTIF_PREV_SCREEN_KEY) or "main"
    prev_payload = data.get(NOTIF_PREV_PAYLOAD_KEY) or {}
    await state.update_data(
        {
            NOTIF_PREV_SCREEN_KEY: None,
            NOTIF_PREV_PAYLOAD_KEY: None,
        }
    )
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, prev_screen, prev_payload)
    await _refresh_client_screen(cq, db, state)
    await cq.answer()
