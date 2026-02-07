from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Sequence, Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.client import ru

CLIENT_INDENT = " " * 8
PAGE_SIZE = 6
_client_hint_shown: dict[int, set[int]] = {}


def remember_client_hint(user_id: int, order_id: int) -> bool:
    """Возвращает True, если подсказку нужно показать, и помечает её как показанную."""
    shown = _client_hint_shown.setdefault(user_id, set())
    if order_id in shown:
        return False
    shown.add(order_id)
    return True


def calc_total_pages(total_messages: int, page_size: int = PAGE_SIZE) -> int:
    if total_messages <= 0:
        return 1
    return max(1, ceil(total_messages / page_size))


def _chat_text(
    locale: str | None,
    t: Callable[[str, str], str] | None,
    key: str,
    **kwargs: object,
) -> str:
    if t and locale:
        return t(locale, key, **kwargs)
    value = ru.TEXTS.get(key, key)
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    return value


def build_chat_screen_text(
    order_id: int,
    messages: Sequence[dict],
    show_hint: bool,
    business_type: str,
    locale: str | None = None,
    t: Callable[[str, str], str] | None = None,
) -> str:
    lines: list[str] = [_chat_text(locale, t, "chat.title", order_id=order_id), ""]
    if show_hint:
        lines.append(_chat_text(locale, t, "chat.hint"))
    lines.append(_chat_text(locale, t, "chat.separator"))

    if not messages:
        lines.append("")
        lines.append(_chat_text(locale, t, "chat.no_messages"))
        return "\n".join(lines)

    lines.append("")
    for msg in messages:
        is_client = msg.get("sender_role") == "client"
        indent = CLIENT_INDENT if is_client else ""
        if is_client:
            icon = "🟢"
            role = _chat_text(locale, t, "chat.role.client")
        else:
            if business_type == "restaurant":
                icon = "🧑‍🍳"
                role = _chat_text(locale, t, "chat.role.restaurant")
            else:
                icon = "🛒"
                role = _chat_text(locale, t, "chat.role.shop")
        time_str = _format_time(msg.get("created_at"))
        lines.append(f"{indent}{icon} {role} · {time_str}")
        text = str(msg.get("message_text") or "")
        if indent:
            text = text.replace("\n", f"\n{indent}")
        lines.append(f"{indent}{text}")
        lines.append("")

    return "\n".join(lines)


def build_chat_screen_kb(
    order_id: int,
    page: int,
    total_pages: int,
    prefix: str,
    nav_rows: Sequence[Sequence[InlineKeyboardButton]],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pagination: list[InlineKeyboardButton] = []
    if page > 1:
        pagination.append(InlineKeyboardButton(text="◀️", callback_data=f"{prefix}:chatp:{order_id}:{page - 1}"))
    if page < total_pages:
        pagination.append(InlineKeyboardButton(text="▶️", callback_data=f"{prefix}:chatp:{order_id}:{page + 1}"))
    if pagination:
        rows.append(pagination)
    rows.extend([list(r) for r in nav_rows])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _format_time(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(value, fmt).strftime("%H:%M")
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value).strftime("%H:%M")
        except ValueError:
            return "??:??"
    return "??:??"
