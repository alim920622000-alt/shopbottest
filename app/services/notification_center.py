from __future__ import annotations

from datetime import datetime
from math import ceil

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey, BaseStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.database import Database
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.order_seen_repo import OrderSeenRepo
from app.services.client_ui_state import remember_client_screen
from app.services.chat_screen_controller import ChatScreenController
from app.services.screen import show_screen

PAGE_SIZE = 6
ADMIN_PREV_TARGET_KEY = "admin_prev_target"
NOTIF_PREV_TARGET_KEY = "notif_prev_target"
NOTIF_PREV_SCREEN_KEY = "notif_prev_ui_screen"
NOTIF_PREV_PAYLOAD_KEY = "notif_prev_ui_payload"
NOTIF_SCREEN_KEY = "notif_screen"


def _calc_total_pages(total: int, page_size: int = PAGE_SIZE) -> int:
    if total <= 0:
        return 1
    return max(1, ceil(total / page_size))


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


def _prefix_for_role(role: str) -> str:
    if role == "client":
        return "c"
    if role == "admin_shop":
        return "a"
    if role == "admin_restaurant":
        return "r"
    raise ValueError(f"Unknown role: {role}")


def _order_label(role: str) -> str:
    if role == "admin_shop":
        return "🧾"
    if role == "admin_restaurant":
        return "🍽"
    return "🧾"


def _build_pagination(prefix: str, base: str, page: int, total_pages: int) -> list[InlineKeyboardButton]:
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"{prefix}:{base}:{page - 1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="➡️ Следующая", callback_data=f"{prefix}:{base}:{page + 1}"))
    return buttons


async def build_client_center_payload(db: Database, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    unread_orders = await ChatReadsRepo(db).count_unread_orders("client", user_id)
    text = f"🔔 Уведомления\n\n💬 Новые сообщения: {unread_orders}"
    rows: list[list[InlineKeyboardButton]] = []
    if unread_orders > 0:
        rows.append([InlineKeyboardButton(text="💬 Сообщения", callback_data="c:notif:msgs")])
    rows.append([InlineKeyboardButton(text="↩️ Вернуться", callback_data="c:notif:return")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def build_client_messages_payload(
    db: Database,
    user_id: int,
    page: int,
) -> tuple[str, InlineKeyboardMarkup]:
    repo = ChatReadsRepo(db)
    total = await repo.count_unread_orders("client", user_id)
    total_pages = _calc_total_pages(total)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PAGE_SIZE
    rows_data = await repo.list_orders_with_unread("client", user_id, PAGE_SIZE, offset)

    rows: list[list[InlineKeyboardButton]] = []
    for item in rows_data:
        order_id = int(item["order_id"])
        unread_count = int(item["unread_count"])
        suffix = "новых"
        rows.append([
            InlineKeyboardButton(
                text=f"💬 Заказ #{order_id} · {unread_count} {suffix}",
                callback_data=f"c:chat:{order_id}",
            )
        ])

    pagination = _build_pagination("c", "notif:msgp", page, total_pages)
    if pagination:
        rows.append(pagination)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="c:notif:back")])
    return "💬 Новые сообщения", InlineKeyboardMarkup(inline_keyboard=rows)


async def build_admin_center_payload(
    db: Database,
    role: str,
    user_id: int,
) -> tuple[str, InlineKeyboardMarkup]:
    new_orders = await OrderSeenRepo(db).count_new_orders(role, user_id)
    unread_orders = await ChatReadsRepo(db).count_unread_orders(role, user_id)
    order_label = _order_label(role)
    text = (
        "🔔 Центр уведомлений\n\n"
        f"{order_label} Новые заказы: {new_orders}\n"
        f"💬 Новые сообщения: {unread_orders}"
    )
    prefix = _prefix_for_role(role)
    rows: list[list[InlineKeyboardButton]] = []
    if new_orders > 0:
        rows.append([InlineKeyboardButton(text=f"{order_label} Заказы", callback_data=f"{prefix}:notif:orders")])
    if unread_orders > 0:
        rows.append([InlineKeyboardButton(text="💬 Сообщения", callback_data=f"{prefix}:notif:msgs")])
    rows.append([InlineKeyboardButton(text="↩️ Вернуться", callback_data=f"{prefix}:notif:return")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


async def build_admin_orders_payload(
    db: Database,
    role: str,
    user_id: int,
    page: int,
) -> tuple[str, InlineKeyboardMarkup]:
    repo = OrderSeenRepo(db)
    total = await repo.count_new_orders(role, user_id)
    total_pages = _calc_total_pages(total)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PAGE_SIZE
    rows_data = await repo.list_new_orders(role, user_id, PAGE_SIZE, offset)

    prefix = _prefix_for_role(role)
    order_label = _order_label(role)
    rows: list[list[InlineKeyboardButton]] = []
    for item in rows_data:
        order_id = int(item["id"])
        time_str = _format_time(item.get("created_at"))
        rows.append([
            InlineKeyboardButton(
                text=f"{order_label} Заказ #{order_id} · {time_str}",
                callback_data=f"{prefix}:order:{order_id}",
            )
        ])

    pagination = _build_pagination(prefix, "notif:op", page, total_pages)
    if pagination:
        rows.append(pagination)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"{prefix}:notif:back")])
    return "🆕 Новые заказы", InlineKeyboardMarkup(inline_keyboard=rows)


async def build_admin_messages_payload(
    db: Database,
    role: str,
    user_id: int,
    page: int,
) -> tuple[str, InlineKeyboardMarkup]:
    repo = ChatReadsRepo(db)
    total = await repo.count_unread_orders(role, user_id)
    total_pages = _calc_total_pages(total)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * PAGE_SIZE
    rows_data = await repo.list_orders_with_unread(role, user_id, PAGE_SIZE, offset)

    prefix = _prefix_for_role(role)
    rows: list[list[InlineKeyboardButton]] = []
    for item in rows_data:
        order_id = int(item["order_id"])
        unread_count = int(item["unread_count"])
        rows.append([
            InlineKeyboardButton(
                text=f"💬 Заказ #{order_id} · {unread_count} новых",
                callback_data=f"{prefix}:chat:{order_id}",
            )
        ])

    pagination = _build_pagination(prefix, "notif:mp", page, total_pages)
    if pagination:
        rows.append(pagination)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"{prefix}:notif:back")])
    return "💬 Новые сообщения", InlineKeyboardMarkup(inline_keyboard=rows)


async def remember_admin_prev_target(state: FSMContext, target: str) -> None:
    await state.update_data({ADMIN_PREV_TARGET_KEY: target})


async def show_notification_center(
    bot: Bot,
    db: Database,
    bot_kind: str,
    state: FSMContext,
    user_id: int,
    store_prev: bool = True,
) -> None:
    if bot_kind == "client":
        data = await state.get_data()
        if store_prev and data.get("ui_screen") != "notif_center":
            await state.update_data(
                {
                    NOTIF_PREV_SCREEN_KEY: data.get("ui_screen") or "main",
                    NOTIF_PREV_PAYLOAD_KEY: data.get("ui_payload") or {},
                }
            )
        await state.update_data(user_id=user_id)
        await remember_client_screen(state, "notif_center", {})
        from app.services.client_ui_renderer import render_client_screen
        controller = ChatScreenController(
            bot=bot,
            chat_id=user_id,
            state=state,
            render=lambda: render_client_screen(db, state),
            db=db,
            bot_kind="client",
        )
        await controller.refresh()
        return

    role = bot_kind
    if store_prev:
        data = await state.get_data()
        if data.get(NOTIF_SCREEN_KEY) != "center":
            prev_target = data.get(ADMIN_PREV_TARGET_KEY) or f"{_prefix_for_role(role)}:home"
            await state.update_data({NOTIF_PREV_TARGET_KEY: prev_target})
    await state.update_data(user_id=user_id)
    await state.update_data({NOTIF_SCREEN_KEY: "center"})
    text, kb = await build_admin_center_payload(db, role, user_id)
    if bot_kind == "admin_shop":
        await show_screen(bot, user_id, state, db, "admin_shop", text, kb)
    else:
        await show_screen(bot, user_id, state, db, "admin_restaurant", text, kb)


async def show_notification_center_for_user(
    bot: Bot,
    db: Database,
    bot_kind: str,
    user_id: int,
    storage: BaseStorage,
) -> None:
    state = FSMContext(
        storage=storage,
        key=StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id),
    )
    await show_notification_center(bot, db, bot_kind, state, user_id, store_prev=True)
