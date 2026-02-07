from __future__ import annotations
import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Tuple

from aiogram.types import InlineKeyboardMarkup, Message
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from app.db.database import Database
from app.repositories.ui_screen_repo import UiScreenRepo

RenderResult = Tuple[str, Optional[InlineKeyboardMarkup]]
RenderFn = Callable[[], RenderResult | Awaitable[RenderResult]]


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
    db: Database
    bot_kind: str

    SCREEN_KEY: str = "screen_message_id"

    @property
    def _repo(self) -> UiScreenRepo:
        return UiScreenRepo(self.db)

    async def _get_screen_id(self) -> Optional[int]:
        data = await self.state.get_data()
        prev_id = data.get(self.SCREEN_KEY)
        if prev_id:
            return int(prev_id)
        prev_id = await self._repo.get(self.bot_kind, self.chat_id)
        if prev_id:
            await self.state.update_data(**{self.SCREEN_KEY: prev_id})
        return prev_id

    async def _set_screen_id(self, message_id: int) -> None:
        await self.state.update_data(**{self.SCREEN_KEY: message_id})
        await self._repo.set(self.bot_kind, self.chat_id, message_id)

    async def _clear_screen_id(self) -> None:
        await self.state.update_data(**{self.SCREEN_KEY: None})
        await self._repo.clear(self.bot_kind, self.chat_id)

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
        prev_id = await self._get_screen_id()
        if prev_id:
            await self._safe_delete(int(prev_id))
        await self._clear_screen_id()

    async def refresh(self) -> int:
        prev_id = await self._get_screen_id()
        if prev_id:
            await self._safe_delete(int(prev_id))
    
        result = self.render()
        if inspect.isawaitable(result):
            result = await result
    
        text, markup = result
    
        sent = await self.bot.send_message(
            self.chat_id,
            text,
            reply_markup=markup,
        )
    
        await self._set_screen_id(sent.message_id)
        return sent.message_id

    async def refresh_after_user_message(self, message: Message) -> int:
 #       """
 #       Обработали текст пользователя в чате:
 #       - попытаться удалить сообщение пользователя
 #       - перерисовать экран (новое сообщение бота будет последним)
 #       """
        await self.delete_user_message(message)
        return await self.refresh()
