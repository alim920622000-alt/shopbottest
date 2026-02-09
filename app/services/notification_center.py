from __future__ import annotations

from datetime import datetime
import asyncio
from math import ceil

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey, BaseStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.database import Database
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.order_seen_repo import OrderSeenRepo
from app.repositories.admin_nav_repo import AdminNavRepo
from app.services.client_ui_state import remember_client_screen
from app.services.chat_screen_controller import ChatScreenController
from app.services.screen import show_screen
from app.repositories.ui_screen_repo import UiScreenRepo

PAGE_SIZE = 6
NOTIF_PREV_SCREEN_KEY = "notif_prev_ui_screen"
NOTIF_PREV_PAYLOAD_KEY = "notif_prev_ui_payload"
NOTIF_SCREEN_KEY = "notif_screen"
NOTIF_SRC_ORDERS = "notif_orders"
NOTIF_SRC_MSGS = "notif_msgs"

_ADMIN_SCREEN_LOCKS: dict[tuple[str, int], asyncio.Lock] = {}


def get_admin_screen_lock(bot_kind: str, user_id: int) -> asyncio.Lock:
    key = (bot_kind, user_id)
    if key not in _ADMIN_SCREEN_LOCKS:
        _ADMIN_SCREEN_LOCKS[key] = asyncio.Lock()
    return _ADMIN_SCREEN_LOCKS[key]


async def _safe_delete_message(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        # Безопасно игнорируем ошибки удаления.
        return


async def _try_edit_message(
    bot: Bot,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: InlineKeyboardMarkup | None,
) -> bool:
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
        )
        return True
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return True
        return False
    except Exception:
        return False


async def ensure_admin_screen_state(
    db: Database,
    bot_kind: str,
    user_id: int,
    fallback_message_id: int | None = None,
) -> None:
    repo = UiScreenRepo(db)
    screen_message_id, _ = await repo.get_info(bot_kind, user_id)
    if not screen_message_id and fallback_message_id:
        screen_message_id = fallback_message_id
    if screen_message_id:
        await repo.set(bot_kind, user_id, screen_message_id, "screen")


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


def _with_notif_context(base: str, src: str, page: int) -> str:
    return f"{base}:src={src}:p={page}"


def parse_notif_context(callback_data: str) -> tuple[str | None, int | None]:
    src = None
    page = None
    for part in callback_data.split(":")[3:]:
        if part.startswith("src="):
            src = part.split("=", 1)[1]
        elif part.startswith("p="):
            value = part.split("=", 1)[1]
            if value.isdigit():
                page = int(value)
    return src, page


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
                callback_data=_with_notif_context(f"c:chat:{order_id}", NOTIF_SRC_MSGS, page),
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
                callback_data=_with_notif_context(f"{prefix}:order:{order_id}", NOTIF_SRC_ORDERS, page),
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
                callback_data=_with_notif_context(f"{prefix}:chat:{order_id}", NOTIF_SRC_MSGS, page),
            )
        ])

    pagination = _build_pagination(prefix, "notif:mp", page, total_pages)
    if pagination:
        rows.append(pagination)
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"{prefix}:notif:back")])
    return "💬 Новые сообщения", InlineKeyboardMarkup(inline_keyboard=rows)


async def remember_admin_prev_target(db: Database, bot_kind: str, user_id: int, target: str) -> None:
    await AdminNavRepo(db).set_prev_target(bot_kind, user_id, target)


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
    # Для админов центр уведомлений управляется отдельно, без FSM.
    await show_notification_center_for_user(
        bot=bot,
        db=db,
        bot_kind=bot_kind,
        user_id=user_id,
        storage=state.storage,
    )


async def show_notification_center_for_user(
    bot: Bot,
    db: Database,
    bot_kind: str,
    user_id: int,
    storage: BaseStorage,
) -> None:
    if bot_kind == "client":
        state = FSMContext(
            storage=storage,
            key=StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id),
        )
        await show_notification_center(bot, db, bot_kind, state, user_id, store_prev=True)
        return

    lock = get_admin_screen_lock(bot_kind, user_id)
    async with lock:
        repo = UiScreenRepo(db)
        screen_message_id, screen_kind = await repo.get_info(bot_kind, user_id)
        text, kb = await build_admin_center_payload(db, bot_kind, user_id)
        if screen_kind == "notif_center" and screen_message_id:
            updated = await _try_edit_message(bot, user_id, screen_message_id, text, kb)
            if updated:
                await repo.set(bot_kind, user_id, screen_message_id, "notif_center")
                return
        if screen_message_id:
            await _safe_delete_message(bot, user_id, screen_message_id)
        message = await bot.send_message(chat_id=user_id, text=text, reply_markup=kb)
        await repo.set(bot_kind, user_id, message.message_id, "notif_center")
