from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.db.database import Database
from app.i18n.client.translator import t
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.services.chat_screen_controller import ChatScreenController
from app.services.screen import clear_state_keep_screen, show_main_menu
from app.services.client_main_menu import build_client_main_kb_dynamic
from app.services.client_ui_renderer import render_client_screen
from app.services.client_ui_state import remember_client_screen

router = Router()


class CabinetStates(StatesGroup):
    edit_full_name = State()
    edit_phone = State()
    edit_address = State()


async def _refresh(cq: CallbackQuery, db: Database, state: FSMContext) -> None:
    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=lambda: render_client_screen(db, state),
        db=db,
        bot_kind="client",
    )
    await controller.refresh()


@router.callback_query(F.data == "c:cabinet")
async def open_cabinet(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "cabinet", {})
    await _refresh(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:language")
async def open_language(cq: CallbackQuery, state: FSMContext, db: Database):
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "language_select", {})
    await _refresh(cq, db, state)
    await cq.answer()


@router.callback_query(F.data.startswith("c:set_locale:"))
async def set_locale(cq: CallbackQuery, state: FSMContext, db: Database):
    locale = cq.data.split(":")[2]
    repo = ClientProfilesRepo(db)
    await repo.set_locale(cq.from_user.id, locale)
    await state.update_data(locale=locale)
    await remember_client_screen(state, "main", {})
    await _refresh(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_name")
async def edit_name(cq: CallbackQuery, state: FSMContext, locale: str = "ru"):
    await state.set_state(CabinetStates.edit_full_name)
    await cq.message.edit_text(t(locale, "cabinet.enter_name"))
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_phone")
async def edit_phone(cq: CallbackQuery, state: FSMContext, locale: str = "ru"):
    await state.set_state(CabinetStates.edit_phone)
    await cq.message.edit_text(t(locale, "cabinet.enter_phone"))
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_address")
async def edit_address(cq: CallbackQuery, state: FSMContext, locale: str = "ru"):
    await state.set_state(CabinetStates.edit_address)
    await cq.message.edit_text(t(locale, "cabinet.enter_address"))
    await cq.answer()


@router.message(CabinetStates.edit_full_name)
async def save_full_name(message: Message, state: FSMContext, db: Database, locale: str = "ru"):
    name = (message.text or "").strip()
    if not name:
        await message.answer(t(locale, "cabinet.name_required"))
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, full_name=name)
    await clear_state_keep_screen(state, db, "client", message.chat.id)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer(t(locale, "cabinet.name_saved"))
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        db,
        "client",
        t(locale, "main.select_section"),
        await build_client_main_kb_dynamic(db, locale, message.from_user.id),
    )


@router.message(CabinetStates.edit_phone)
async def save_phone(message: Message, state: FSMContext, db: Database, locale: str = "ru"):
    phone = (message.text or "").strip()
    if not phone:
        await message.answer(t(locale, "cabinet.phone_required"))
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, phone=phone)
    await clear_state_keep_screen(state, db, "client", message.chat.id)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer(t(locale, "cabinet.phone_saved"))
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        db,
        "client",
        t(locale, "main.select_section"),
        await build_client_main_kb_dynamic(db, locale, message.from_user.id),
    )


@router.message(CabinetStates.edit_address)
async def save_address(message: Message, state: FSMContext, db: Database, locale: str = "ru"):
    address = (message.text or "").strip()
    if not address:
        await message.answer(t(locale, "cabinet.address_required"))
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, address=address)
    await clear_state_keep_screen(state, db, "client", message.chat.id)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer(t(locale, "cabinet.address_saved"))
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        db,
        "client",
        t(locale, "main.select_section"),
        await build_client_main_kb_dynamic(db, locale, message.from_user.id),
    )
