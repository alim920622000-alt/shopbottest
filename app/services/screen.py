from __future__ import annotations

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

from app.db.database import Database
from app.repositories.ui_screen_repo import UiScreenRepo

SCREEN_MESSAGE_ID_KEY = "screen_message_id"


async def get_screen_message_id(
    state: FSMContext,
    db: Database,
    bot_kind: str,
    chat_id: int,
) -> int | None:
    data = await state.get_data()
    screen_message_id = data.get(SCREEN_MESSAGE_ID_KEY)
    if screen_message_id:
        return int(screen_message_id)
    repo = UiScreenRepo(db)
    screen_message_id = await repo.get(bot_kind, chat_id)
    if screen_message_id:
        await state.update_data({SCREEN_MESSAGE_ID_KEY: screen_message_id})
    return screen_message_id


async def set_screen_message_id(
    state: FSMContext,
    db: Database,
    bot_kind: str,
    chat_id: int,
    message_id: int,
) -> None:
    await state.update_data({SCREEN_MESSAGE_ID_KEY: message_id})
    repo = UiScreenRepo(db)
    await repo.set(bot_kind, chat_id, message_id)


async def clear_screen_message_id(state: FSMContext, db: Database, bot_kind: str, chat_id: int) -> None:
    await state.update_data({SCREEN_MESSAGE_ID_KEY: None})
    repo = UiScreenRepo(db)
    await repo.clear(bot_kind, chat_id)


async def clear_state_keep_screen(state: FSMContext, db: Database, bot_kind: str, chat_id: int) -> None:
    screen_message_id = await get_screen_message_id(state, db, bot_kind, chat_id)
    await state.clear()
    if screen_message_id:
        await set_screen_message_id(state, db, bot_kind, chat_id, screen_message_id)


async def delete_screen(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    db: Database,
    bot_kind: str,
) -> None:
    screen_message_id = await get_screen_message_id(state, db, bot_kind, chat_id)
    if screen_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=screen_message_id)
        except Exception:
            # Безопасно игнорируем, чтобы не зациклиться на недоступном сообщении.
            pass
    await clear_screen_message_id(state, db, bot_kind, chat_id)


async def show_screen(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    db: Database,
    bot_kind: str,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> int:
    screen_message_id = await get_screen_message_id(state, db, bot_kind, chat_id)
    if screen_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=screen_message_id)
        except TelegramBadRequest:
            pass
        except Exception:
            pass

    message = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    await set_screen_message_id(state, db, bot_kind, chat_id, message.message_id)
    return message.message_id


async def show_main_menu(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    db: Database,
    bot_kind: str,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> int:
    return await show_screen(
        bot=bot,
        chat_id=chat_id,
        state=state,
        db=db,
        bot_kind=bot_kind,
        text=text,
        reply_markup=reply_markup,
    )


async def safe_edit_text(cq, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    # Безопасное обновление обычного или inline-сообщения.
    try:
        if cq.message is not None:
            await cq.message.edit_text(text, reply_markup=reply_markup)
            return
        if cq.inline_message_id:
            await cq.bot.edit_message_text(
                text=text,
                inline_message_id=cq.inline_message_id,
                reply_markup=reply_markup,
            )
            return
        await cq.answer("Не удалось обновить сообщение")
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        raise
