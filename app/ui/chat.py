from __future__ import annotations

from datetime import datetime

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

CHAT_PAGE_SIZE = 6
CLIENT_INDENT = " " * 8


def build_chat_screen_text(
    order_id: int,
    messages: list[dict],
    show_hint: bool,
    business_type: str,
    page: int,
    page_size: int,
) -> str:
    lines: list[str] = [f"💬 Чат по заказу #{order_id}", ""]
    if show_hint:
        lines.append("ℹ️ Просто напишите сообщение в поле ниже и отправьте.")
        lines.append("────────────────────────")
        lines.append("")

    if not messages:
        lines.append("Сообщений пока нет.")
        return "\n".join(lines)

    for msg in messages:
        sender_role = msg.get("sender_role")
        is_client = sender_role == "client"
        role_label, role_icon = _get_role_label(sender_role, business_type)
        time_str = _format_time(msg.get("created_at"))
        indent = CLIENT_INDENT if is_client else ""
        lines.append(f"{indent}{role_icon} {role_label} · {time_str}")
        text_lines = (msg.get("message_text") or "").splitlines() or [""]
        for line in text_lines:
            lines.append(f"{indent}{line}")
        lines.append("")

    return "\n".join(lines).rstrip()


def build_chat_screen_kb(
    order_id: int,
    page: int,
    total_pages: int,
    prefix: str,
    home_cb: str,
    back_cb: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        nav_row: list[InlineKeyboardButton] = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(
                text="◀️",
                callback_data=f"{prefix}:chatp:{order_id}:{page - 1}",
            ))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(
                text="▶️",
                callback_data=f"{prefix}:chatp:{order_id}:{page + 1}",
            ))
        if nav_row:
            rows.append(nav_row)
    rows.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data=home_cb),
        InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _format_time(created_at: str | None) -> str:
    if not created_at:
        return "--:--"
    try:
        dt = datetime.fromisoformat(created_at)
    except ValueError:
        return "--:--"
    return dt.strftime("%H:%M")


def _get_role_label(sender_role: str | None, business_type: str) -> tuple[str, str]:
    if sender_role == "client":
        return "Клиент", "🟢"
    if business_type == "restaurant":
        return "Ресторан", "🧑‍🍳"
    return "Магазин", "🛒"
