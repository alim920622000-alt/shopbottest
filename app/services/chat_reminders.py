from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.database import Database
from app.repositories.chat_reminders_repo import ChatRemindersRepo, ChatReminder

logger = logging.getLogger(__name__)

PREVIEW_LIMIT = 260


def _normalize_preview(text: str, limit: int = PREVIEW_LIMIT) -> str:
    compact = " ".join((text or "").split())
    if len(compact) > limit:
        return f"{compact[: limit - 1].rstrip()}…"
    return compact


def _prefix_for_kind(bot_kind: str) -> str:
    if bot_kind == "client":
        return "c"
    if bot_kind == "admin_shop":
        return "a"
    if bot_kind == "admin_restaurant":
        return "r"
    raise ValueError(f"Неизвестный тип бота: {bot_kind}")


def _build_reminder_keyboard(order_id: int, bot_kind: str) -> InlineKeyboardMarkup:
    prefix = _prefix_for_kind(bot_kind)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Открыть чат", callback_data=f"{prefix}:chat:{order_id}")],
            [
                InlineKeyboardButton(text="🏠 Главная", callback_data=f"{prefix}:home"),
                InlineKeyboardButton(
                    text=f"📦 К заказу #{order_id}",
                    callback_data=f"{prefix}:order:{order_id}",
                ),
            ],
        ]
    )


async def schedule_chat_reminder(
    db: Database,
    order_id: int,
    recipient_user_id: int,
    recipient_kind: str,
    message_text: str,
    delay_seconds: int = 180,
) -> None:
    repo = ChatRemindersRepo(db)
    now = datetime.utcnow()
    preview = _normalize_preview(message_text)
    scheduled_at = now + timedelta(seconds=delay_seconds)
    await repo.upsert_pending(
        order_id=order_id,
        recipient_user_id=recipient_user_id,
        recipient_kind=recipient_kind,
        last_message_at=now,
        last_message_preview=preview,
        scheduled_at=scheduled_at,
    )


async def cancel_chat_reminder(
    db: Database,
    order_id: int,
    recipient_user_id: int,
    recipient_kind: str,
) -> None:
    repo = ChatRemindersRepo(db)
    await repo.cancel_pending(order_id, recipient_user_id, recipient_kind)


async def _send_reminder(bot: Bot, reminder: ChatReminder) -> bool:
    text = (
        f"Новое сообщение по заказу #{reminder.order_id}\n"
        f"{_normalize_preview(reminder.last_message_preview)}"
    )
    reply_markup = _build_reminder_keyboard(reminder.order_id, reminder.recipient_kind)
    try:
        await bot.send_message(reminder.recipient_user_id, text, reply_markup=reply_markup)
        return True
    except (TelegramBadRequest, TelegramForbiddenError):
        return False


async def run_chat_reminder_worker(
    bot: Bot,
    db: Database,
    bot_kind: str,
    poll_interval: int = 25,
) -> None:
    repo = ChatRemindersRepo(db)
    while True:
        try:
            now = datetime.utcnow()
            reminders = await repo.list_due(bot_kind, now)
            for reminder in reminders:
                sent = await _send_reminder(bot, reminder)
                if sent:
                    await repo.mark_sent(reminder.id)
                else:
                    await repo.mark_canceled(reminder.id)
        except Exception:
            logger.warning("Ошибка отправки напоминаний", exc_info=True)
        await asyncio.sleep(poll_interval)
