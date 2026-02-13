from __future__ import annotations

from aiogram.types import InlineKeyboardButton

PAGE_SIZE_DEFAULT = 8


def normalize_page(page: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 0
    return max(0, min(page, total_pages - 1))


def slice_page(items: list, page: int, page_size: int = PAGE_SIZE_DEFAULT) -> tuple[list, int]:
    if page_size <= 0:
        page_size = PAGE_SIZE_DEFAULT
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = normalize_page(page, total_pages)
    start = page * page_size
    end = start + page_size
    return items[start:end], total_pages


def build_pager_row(prefix: str, page: int, total_pages: int, extra: str = "") -> list[InlineKeyboardButton]:
    if total_pages <= 1:
        return []
    page = normalize_page(page, total_pages)
    row: list[InlineKeyboardButton] = []
    if page > 0:
        row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"{prefix}{extra}:p:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"{prefix}{extra}:p:{page + 1}"))
    return row
