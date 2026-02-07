from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.services.chat_screen_controller import ChatScreenController
from app.services.client_ui_renderer import render_client_screen
from app.services.client_ui_state import remember_client_screen
from app.services.screen import clear_state_keep_screen

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, db: Database):
    await clear_state_keep_screen(state)
    await remember_client_screen(state, "main", {})
    await state.update_data(user_id=message.from_user.id)

    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=lambda: render_client_screen(db, state),
    )
    await controller.delete_user_message(message)
    await controller.refresh()
