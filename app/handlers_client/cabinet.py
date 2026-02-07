from __future__ import annotations

from aiogram import Router, F
from typing import Callable

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.db.database import Database
from app.handlers_client.kb import kb_client_main
from app.repositories.client_user_settings_repo import ClientUserSettingsRepo
from app.services.chat_screen_controller import ChatScreenController
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.services.screen import clear_state_keep_screen, show_main_menu
from app.services.client_ui_state import remember_client_screen

router = Router()


class CabinetStates(StatesGroup):
    edit_full_name = State()
    edit_phone = State()
    edit_address = State()


def kb_cabinet(locale: str, t: Callable[[str, str], str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "cabinet.edit_name"), callback_data="c:cabinet:edit_name")],
        [InlineKeyboardButton(text=t(locale, "cabinet.edit_phone"), callback_data="c:cabinet:edit_phone")],
        [InlineKeyboardButton(text=t(locale, "cabinet.edit_address"), callback_data="c:cabinet:edit_address")],
        [InlineKeyboardButton(text=t(locale, "cabinet.language"), callback_data="c:cabinet:language")],
        [InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home")],
    ])

def kb_language(locale: str, t: Callable[[str, str], str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "language.ru"), callback_data="c:lang:ru")],
        [InlineKeyboardButton(text=t(locale, "language.tj"), callback_data="c:lang:tj")],
        [InlineKeyboardButton(text=t(locale, "language.uz"), callback_data="c:lang:uz")],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:cabinet")],
    ])

@router.callback_query(F.data == "c:cabinet")
async def open_cabinet(cq: CallbackQuery, db: Database, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    repo = ClientProfilesRepo(db)
    profile = await repo.get(cq.from_user.id)
    full_name = profile["full_name"] if profile else ""
    phone = profile["phone"] if profile else ""
    address = profile["address"] if profile else ""

    empty_value = t(locale, "cabinet.empty_value")
    text = (
        f"{t(locale, 'cabinet.title')}\n\n"
        f"{t(locale, 'cabinet.full_name')}: {full_name or empty_value}\n"
        f"{t(locale, 'cabinet.phone')}: {phone or empty_value}\n"
        f"{t(locale, 'cabinet.address')}: {address or empty_value}"
    )
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "cabinet", {})
    await cq.message.edit_text(text, reply_markup=kb_cabinet(locale, t))
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_name")
async def edit_name(cq: CallbackQuery, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    await state.set_state(CabinetStates.edit_full_name)
    await cq.message.edit_text(t(locale, "cabinet.enter_name"))
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_phone")
async def edit_phone(cq: CallbackQuery, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    await state.set_state(CabinetStates.edit_phone)
    await cq.message.edit_text(t(locale, "cabinet.enter_phone"))
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_address")
async def edit_address(cq: CallbackQuery, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    await state.set_state(CabinetStates.edit_address)
    await cq.message.edit_text(t(locale, "cabinet.enter_address"))
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:language")
async def open_language(cq: CallbackQuery, state: FSMContext, locale: str, t: Callable[[str, str], str]):
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "language", {})
    await cq.message.edit_text(t(locale, "language.select_title"), reply_markup=kb_language(locale, t))
    await cq.answer()


@router.callback_query(F.data.startswith("c:lang:"))
async def set_language(cq: CallbackQuery, db: Database, state: FSMContext, t: Callable[[str, str], str]):
    from app.services.client_ui_renderer import render_client_screen

    locale = cq.data.split(":")[2]
    if locale not in ("ru", "tj", "uz"):
        locale = "ru"
    repo = ClientUserSettingsRepo(db)
    await repo.set_locale(cq.from_user.id, locale)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "cabinet", {})

    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=lambda: render_client_screen(db, state, locale, t),
    )
    await controller.refresh()
    await cq.answer()


@router.message(CabinetStates.edit_full_name)
async def save_full_name(message: Message, state: FSMContext, db: Database, locale: str, t: Callable[[str, str], str]):
    name = (message.text or "").strip()
    if not name:
        await message.answer(t(locale, "cabinet.name_required"))
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, full_name=name)
    await clear_state_keep_screen(state)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer(t(locale, "cabinet.name_saved"))
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        t(locale, "main.select_section"),
        kb_client_main(locale, t),
    )


@router.message(CabinetStates.edit_phone)
async def save_phone(message: Message, state: FSMContext, db: Database, locale: str, t: Callable[[str, str], str]):
    phone = (message.text or "").strip()
    if not phone:
        await message.answer(t(locale, "cabinet.phone_required"))
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, phone=phone)
    await clear_state_keep_screen(state)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer(t(locale, "cabinet.phone_saved"))
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        t(locale, "main.select_section"),
        kb_client_main(locale, t),
    )


@router.message(CabinetStates.edit_address)
async def save_address(message: Message, state: FSMContext, db: Database, locale: str, t: Callable[[str, str], str]):
    address = (message.text or "").strip()
    if not address:
        await message.answer(t(locale, "cabinet.address_required"))
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, address=address)
    await clear_state_keep_screen(state)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer(t(locale, "cabinet.address_saved"))
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        t(locale, "main.select_section"),
        kb_client_main(locale, t),
    )
