from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.db.database import Database
from app.handlers_client.kb import kb_client_main
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.services.screen import clear_state_keep_screen, show_main_menu
from app.services.client_ui_state import remember_client_screen

router = Router()


class CabinetStates(StatesGroup):
    edit_full_name = State()
    edit_phone = State()
    edit_address = State()


def kb_cabinet() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ФИО", callback_data="c:cabinet:edit_name")],
        [InlineKeyboardButton(text="📞 Телефон", callback_data="c:cabinet:edit_phone")],
        [InlineKeyboardButton(text="📍 Адрес", callback_data="c:cabinet:edit_address")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="c:home")],
    ])


@router.callback_query(F.data == "c:cabinet")
async def open_cabinet(cq: CallbackQuery, db: Database, state: FSMContext):
    repo = ClientProfilesRepo(db)
    profile = await repo.get(cq.from_user.id)
    full_name = profile["full_name"] if profile else ""
    phone = profile["phone"] if profile else ""
    address = profile["address"] if profile else ""

    text = (
        "👤 Кабинет\n\n"
        f"ФИО: {full_name or '—'}\n"
        f"Телефон: {phone or '—'}\n"
        f"Адрес: {address or '—'}"
    )
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "cabinet", {})
    await cq.message.edit_text(text, reply_markup=kb_cabinet())
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_name")
async def edit_name(cq: CallbackQuery, state: FSMContext):
    await state.set_state(CabinetStates.edit_full_name)
    await cq.message.edit_text("Введите ФИО:")
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_phone")
async def edit_phone(cq: CallbackQuery, state: FSMContext):
    await state.set_state(CabinetStates.edit_phone)
    await cq.message.edit_text("Введите телефон:")
    await cq.answer()


@router.callback_query(F.data == "c:cabinet:edit_address")
async def edit_address(cq: CallbackQuery, state: FSMContext):
    await state.set_state(CabinetStates.edit_address)
    await cq.message.edit_text("Введите адрес:")
    await cq.answer()


@router.message(CabinetStates.edit_full_name)
async def save_full_name(message: Message, state: FSMContext, db: Database):
    name = (message.text or "").strip()
    if not name:
        await message.answer("ФИО не может быть пустым.")
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, full_name=name)
    await clear_state_keep_screen(state)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer("ФИО сохранено.")
    await show_main_menu(message.bot, message.chat.id, state, "Выберите раздел:", kb_client_main())


@router.message(CabinetStates.edit_phone)
async def save_phone(message: Message, state: FSMContext, db: Database):
    phone = (message.text or "").strip()
    if not phone:
        await message.answer("Телефон не может быть пустым.")
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, phone=phone)
    await clear_state_keep_screen(state)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer("Телефон сохранён.")
    await show_main_menu(message.bot, message.chat.id, state, "Выберите раздел:", kb_client_main())


@router.message(CabinetStates.edit_address)
async def save_address(message: Message, state: FSMContext, db: Database):
    address = (message.text or "").strip()
    if not address:
        await message.answer("Адрес не может быть пустым.")
        return
    repo = ClientProfilesRepo(db)
    await repo.upsert(message.from_user.id, address=address)
    await clear_state_keep_screen(state)
    await state.update_data(user_id=message.from_user.id)
    await remember_client_screen(state, "main", {})
    await message.answer("Адрес сохранён.")
    await show_main_menu(message.bot, message.chat.id, state, "Выберите раздел:", kb_client_main())
