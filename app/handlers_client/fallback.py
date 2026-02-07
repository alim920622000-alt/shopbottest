from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.services.chat_screen_controller import ChatScreenController
from app.services.client_ui_renderer import render_client_screen

router = Router()


@router.message(F.text)
async def fallback_handler(message: Message, state: FSMContext, db: Database):
    if message.via_bot is not None:
        return

    if message.text and message.text.startswith("/"):
        return

    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=lambda: render_client_screen(db, state),
        db=db,
        bot_kind="client",
    )

    await controller.delete_user_message(message)
    await message.answer("Я не понял команду. Используйте меню ниже.")
    await controller.refresh()
