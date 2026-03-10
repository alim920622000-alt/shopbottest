from __future__ import annotations

import asyncio

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import Message


async def delete_later(bot: Bot, chat_id: int, message_id: int, delay: int = 4) -> None:
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return


async def send_temp_message(message: Message, text: str, seconds: int = 3, delete_user: bool = False):
    sent = await message.answer(text)

    if delete_user:
        try:
            await message.delete()
        except Exception:
            pass

    await asyncio.sleep(seconds)

    try:
        await sent.delete()
    except Exception:
        pass