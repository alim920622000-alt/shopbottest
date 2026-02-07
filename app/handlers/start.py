from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from app.states import MenuStates
from app.keyboards import kb_main
from app.services.screen import clear_state_keep_screen, show_main_menu
from app.db.database import Database

router = Router()

@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, auth_role: str, db: Database):
    if auth_role == "none":
        await message.answer("Доступ запрещён. Ваш user_id не добавлен в список администраторов.")
        return

    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
    await state.set_state(MenuStates.main)
    await show_main_menu(message.bot, message.chat.id, state, db, "admin_shop", "Главное меню:", kb_main())
