from __future__ import annotations

from datetime import datetime
from math import ceil
from typing import Sequence
from app.utils.tz import fmt_hm

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n.client.translator import t

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


def build_chat_screen_text(
    order_id: int,
    messages: Sequence[dict],
    show_hint: bool,
    business_type: str,
    locale: str = "ru",
    viewer: str = "client",
    shop_name: str | None = None,
    client_name: str | None = None,
) -> str:
    lines: list[str] = [t(locale, "chat.title", order_id=order_id), ""]
    if show_hint:
        lines.append(t(locale, "chat.hint"))
    lines.append(t(locale, "chat.separator"))

    if not messages:
        lines.append("")
        lines.append(t(locale, "chat.no_messages"))
        return "\n".join(lines)

    lines.append("")
    for msg in messages:
        sender_role = msg.get("sender_role")
        is_client = sender_role == "client"
        indent = CLIENT_INDENT if is_client else ""
        if is_client:
            icon = "👤"
            if viewer == "client":
                role = t(locale, "chat.role.me")
            else:
                role = client_name or t(locale, "chat.role.client")
        else:
            if business_type == "restaurant":
                icon = "🍽️"
                role = shop_name or t(locale, "chat.role.restaurant")
            else:
                icon = "🛒"
                role = shop_name or t(locale, "chat.role.shop")
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
