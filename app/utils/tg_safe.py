from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup, Message, CallbackQuery


async def safe_edit_text(
    msg: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
   # """
    #Áåçîïàñíî ðåäàêòèðóåò ñîîáùåíèå.
    #Âîçâðàùàåò True åñëè îòðåäàêòèðîâàëè, False åñëè Telegram îòâåòèë 'message is not modified'.
    #"""
    try:
        await msg.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return False
        raise


async def safe_delete_cq_message(cq: CallbackQuery) -> None:
    # Безопасно удаляет сообщение callback-запроса.
    try:
        if cq.message:
            await cq.message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
