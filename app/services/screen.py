from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest

from app.db.database import Database
from app.repositories.ui_screen_repo import UiScreenRepo

SCREEN_MESSAGE_ID_KEY = "screen_message_id"
logger = logging.getLogger(__name__)


async def get_screen_message_id(
    state: FSMContext,
    db: Database,
    bot_kind: str,
    chat_id: int,
    use_fsm_fallback: bool = True,
) -> int | None:
    repo = UiScreenRepo(db)
    screen_message_id_db = await repo.get(bot_kind, chat_id)
    if screen_message_id_db:
        await state.update_data({SCREEN_MESSAGE_ID_KEY: screen_message_id_db})
        return int(screen_message_id_db)

    if not use_fsm_fallback:
        return None

    # Источником истины для screen_message_id является таблица ui_screens,
    # FSM используется только как временный fallback.
    data = await state.get_data()
    screen_message_id_fsm = data.get(SCREEN_MESSAGE_ID_KEY)
    if screen_message_id_fsm:
        return int(screen_message_id_fsm)
    return None


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
    screen_name: str | None = None,
    use_fsm_fallback: bool = True,
) -> int:
    repo = UiScreenRepo(db)
    db_message_id = await repo.get(bot_kind, chat_id)
    state_data = await state.get_data()
    fsm_message_id = state_data.get(SCREEN_MESSAGE_ID_KEY)
    logger.debug(
        "[SCREEN] bot=%s chat=%s screen=%s db_id=%s fsm_id=%s",
        bot_kind,
        chat_id,
        screen_name or state_data.get("ui_screen") or "unknown",
        db_message_id,
        fsm_message_id,
    )

    screen_message_id = db_message_id
    if not screen_message_id and use_fsm_fallback:
        screen_message_id = await get_screen_message_id(
            state,
            db,
            bot_kind,
            chat_id,
            use_fsm_fallback=True,
        )

    if screen_message_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=screen_message_id)
        except TelegramBadRequest as exc:
            error_text = str(exc).lower()
            if (
                "message to delete not found" in error_text
                or "message can't be deleted" in error_text
            ):
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
