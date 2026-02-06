from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Tuple

from aiogram.types import InlineKeyboardMarkup, Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError


RenderResult = Tuple[str, Optional[InlineKeyboardMarkup]]
RenderFn = Callable[[], Awaitable[RenderResult]]


@dataclass
class ChatScreenController:
#    """
 #   Контроллер "экранного меню" для чата.
#
 #   Идея:
  #  - Экран чата = одно сообщение БОТА (screen_message_id в FSM)
   # - Любое обновление: удалить старый экран -> отправить новый экран
   # - Сообщения пользователя в режиме чата стараемся удалять после обработки (чтобы не копились снизу)
    #"""
    bot: any
    chat_id: int
    state: any  # FSMContext
    render: RenderFn

    SCREEN_KEY: str = "screen_message_id"

    async def _safe_delete(self, message_id: int) -> None:
        try:
            await self.bot.delete_message(self.chat_id, message_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            # В личке/без прав/если уже удалено — просто игнорируем
            return
        except Exception:
            # Не ломаем UX из-за удаления
            return

    async def delete_user_message(self, message: Message) -> None:
 #       """Пытаемся удалить сообщение пользователя (чтобы чат был 'одним окном')."""
        try:
            await self.bot.delete_message(self.chat_id, message.message_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            return
        except Exception:
            return

    async def delete_screen(self) -> None:
#        """Удалить текущий экран (сообщение бота), если есть."""
        data = await self.state.get_data()
        prev_id = data.get(self.SCREEN_KEY)
        if prev_id:
            await self._safe_delete(int(prev_id))
            await self.state.update_data(**{self.SCREEN_KEY: None})

    async def refresh(self) -> int:
 #       """
  #        """
        data = await self.state.get_data()
        prev_id = data.get(self.SCREEN_KEY)
        if prev_id:
            await self._safe_delete(int(prev_id))

        text, markup = await self.render()
        sent = await self.bot.send_message(self.chat_id, text, reply_markup=markup)

        await self.state.update_data(**{self.SCREEN_KEY: sent.message_id})
        return sent.message_id

    async def refresh_after_user_message(self, message: Message) -> int:
 #       """
 #       Обработали текст пользователя в чате:
 #       - попытаться удалить сообщение пользователя
 #       - перерисовать экран (новое сообщение бота будет последним)
 #       """
        await self.delete_user_message(message)
        return await self.refresh()
