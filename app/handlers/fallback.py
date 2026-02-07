import asyncio

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.keyboards import kb_main
from app.services.screen import delete_screen, show_main_menu
from app.db.database import Database
from app.services.message_cleanup import delete_later

router = Router()


@router.message(F.text)
async def fallback_handler(message: Message, state: FSMContext, auth_role: str, db: Database):
    if await state.get_state() is not None:
        return
    if message.text and message.text.startswith("/"):
        return
    if auth_role == "none":
        await message.answer("Доступ запрещён. Ваш user_id не добавлен в список администраторов.")
        return
    await delete_screen(message.bot, message.chat.id, state, db, "admin_shop")
    notice = await message.answer("Команда неверна. Используйте меню ниже.")
    asyncio.create_task(delete_later(message.bot, message.chat.id, notice.message_id, delay=4))
    await show_main_menu(message.bot, message.chat.id, state, db, "admin_shop", "Главное меню:", kb_main())
