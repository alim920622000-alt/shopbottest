from __future__ import annotations

import logging
from datetime import datetime, timedelta
from app.utils.tz import utcnow, ensure_utc
import random

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.config import CANCEL_WINDOW_MINUTES
from app.db.database import Database
from app.handlers_client.kb import kb_client_main, kb_orders_list, kb_chat_orders, kb_back
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo
from app.repositories.chat_repo import ChatRepo
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.admins_repo import AdminsRepo
from app.services.admin_notifications import notify_admins_order_canceled
from app.services.chat_ui import (
    PAGE_SIZE,
    build_chat_screen_kb,
    build_chat_screen_text,
    calc_total_pages,
    remember_client_hint,
)
from app.services.chat_reminders import cancel_chat_reminder, schedule_chat_reminder, is_chat_reminder_text
from app.services.screen import clear_state_keep_screen, show_screen
from app.services.chat_screen_controller import ChatScreenController
from app.services.client_ui_state import remember_client_screen
from app.services.notification_center import parse_notif_context, NOTIF_SRC_MSGS
from app.services.order_statuses import compose_client_status_key
from app.services.order_chat_access import can_access_order_chat, CLOSED_STATUSES
from app.handlers_client.catalog import render_cart
from app.i18n.client.translator import t
from app.utils.tg_safe import safe_delete_cq_message
from app.services.pagination import calc_page, pager_row

LIST_PAGE_SIZE = 8

router = Router()
logger = logging.getLogger(__name__)

DONE_STATUSES = ["finished", "canceled", "delivered"]
CANCELABLE_STATUSES = ["new"]


class ClientChatStates(StatesGroup):
    active = State()


def kb_order_card(
    locale: str,
    order_id: int,
    back_cb: str,
    can_cancel: bool = False,
    can_chat: bool = True,
    can_repeat: bool = False,
) -> InlineKeyboardMarkup:
    kb = []
    if can_chat:
        kb.append([InlineKeyboardButton(text=t(locale, "order_card.chat"), callback_data=f"c:chat:{order_id}")])
    if can_repeat:
        kb.append([InlineKeyboardButton(text=t(locale, "order.repeat"), callback_data=f"c:order_repeat:{order_id}")])
    if can_cancel:
        kb.append([InlineKeyboardButton(text=t(locale, "order.cancel"), callback_data=f"c:cancel:{order_id}")])
    kb.append([
        InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home"),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=back_cb),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def _parse_created_at(value: object) -> datetime | None:
    dt: datetime | None = None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        if dt is None:
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
    else:
        return None

    return ensure_utc(dt)


def _can_cancel_order(order: dict | None, now: datetime | None = None) -> bool:
    if not order or order.get("status") not in CANCELABLE_STATUSES:
        return False
    created_at = _parse_created_at(order.get("created_at"))
    if not created_at:
        return False
    now = now or utcnow()
    return now - created_at <= timedelta(minutes=CANCEL_WINDOW_MINUTES)


def _build_order_text(locale: str, order: dict, items: list[dict], shop_name: str) -> str:
    comment = (order.get("comment") or "").strip()
    comment_line = comment or t(locale, "cabinet.empty_value")
    lines = [
        t(locale, "orders.item_tpl", order_id=order["id"]),
        t(locale, "order.shop", shop_name=shop_name),
        t(locale, "order.status", status=t(locale, compose_client_status_key(order.get("merchant_status"), order.get("courier_status")))),
        t(locale, "order.total", total=order["total_amount"]),
        t(locale, "order.comment", comment=comment_line),
        "",
        t(locale, "order.items_title"),
    ]
    for it in items:
        lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")
    return "\n".join(lines)


async def _render_order_card(
    cq: CallbackQuery,
    state: FSMContext,
    db: Database,
    locale: str,
    order: dict,
    items: list[dict],
    shop_name: str,
) -> None:
    back_cb = "c:history" if order["status"] in DONE_STATUSES else "c:orders"
    text = _build_order_text(locale, order, items, shop_name)
    can_cancel = _can_cancel_order(order)
    can_chat = await can_access_order_chat(db, order)
    can_repeat = str(order.get("status") or "").strip().lower() in CLOSED_STATUSES
    reply_markup = kb_order_card(locale, int(order["id"]), back_cb, can_cancel, can_chat, can_repeat)
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Для напоминания сначала удаляем сообщение, потом показываем карточку.
        await safe_delete_cq_message(cq)
        await show_screen(
            bot=cq.bot,
            chat_id=cq.from_user.id,
            state=state,
            db=db,
            bot_kind="client",
            text=text,
            reply_markup=reply_markup,
        )
    else:
        await cq.message.edit_text(text, reply_markup=reply_markup)


def kb_chat_nav_rows(locale: str, order_id: int, back_target: str | None = None) -> list[list[InlineKeyboardButton]]:
    back_cb = back_target or f"c:order:{order_id}"
    return [
        [
            InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home"),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=back_cb),
        ],
    ]

def make_chat_render_fn(db: Database, state: FSMContext, locale: str):
    async def render():
        data = await state.get_data()
        order_id = int(data.get("chat_order_id") or 0)
        back_target = data.get("chat_back_target")

        orders = OrdersRepo(db)
        order = await orders.get_order(order_id)
        shop = ShopsRepo(db)
        shop_info = await shop.get(int(order["shop_id"])) if order else None
        shop_name = shop_info["name"] if shop_info else None
        business_type = shop_info["business_type"] if shop_info else "shop"

        chat = ChatRepo(db)
        total_messages = await chat.count_messages(order_id)
        total_pages = calc_total_pages(total_messages, PAGE_SIZE)
        total_pages = max(1, total_pages)

        # текущая страница из state (если нет — последняя)
        page = int(data.get("chat_page") or total_pages)
        page = max(1, min(page, total_pages))

        offset = (total_pages - page) * PAGE_SIZE
        messages = await chat.list_messages(order_id, limit=PAGE_SIZE, offset=offset)

        # Рендер чата должен быть в том же locale, что и остальной клиентский UI.
        text = build_chat_screen_text(
            order_id,
            messages,
            False,
            business_type,
            locale,
            "client",
            shop_name=shop_name,
        )
        kb = build_chat_screen_kb(order_id, page, total_pages, "c", kb_chat_nav_rows(locale, order_id, back_target))
        return text, kb

    return render


@router.callback_query(F.data.startswith("c:orders:p:"))
async def list_orders_page(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    page = int(cq.data.split(":")[-1])
    await list_orders_render(cq, db, state, locale, page)


@router.callback_query(F.data == "c:orders")
async def list_orders(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    await list_orders_render(cq, db, state, locale, 0)


async def list_orders_render(cq: CallbackQuery, db: Database, state: FSMContext, locale: str, page: int):
    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "orders", {})
    orders = OrdersRepo(db)
    total = await orders.count_for_client_excluding(cq.from_user.id, DONE_STATUSES)
    if total <= 0:
        await cq.message.edit_text(t(locale, "orders.empty"), reply_markup=kb_client_main(locale))
        await cq.answer()
        return

    pi = calc_page(total=total, page=page, page_size=LIST_PAGE_SIZE)
    rows = await orders.list_for_client_page_excluding(cq.from_user.id, DONE_STATUSES, limit=pi.limit, offset=pi.offset)
    kb = kb_orders_list(locale, rows)
    pager = pager_row("c:orders", pi.page, pi.total_pages)
    if pager:
        kb.inline_keyboard.append(pager)
    kb.inline_keyboard.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:main")])
    await cq.message.edit_text(t(locale, "orders.title"), reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("c:history:p:"))
async def list_history_page(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    page = int(cq.data.split(":")[-1])
    await list_history_render(cq, db, state, locale, page)


@router.callback_query(F.data == "c:history")
async def list_history(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    await list_history_render(cq, db, state, locale, 0)


async def list_history_render(cq: CallbackQuery, db: Database, state: FSMContext, locale: str, page: int):
    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "history", {})
    orders = OrdersRepo(db)
    total = await orders.count_for_client(cq.from_user.id, statuses=DONE_STATUSES)
    if total <= 0:
        await cq.message.edit_text(t(locale, "orders.history.empty"), reply_markup=kb_back(locale, "order_menu"))
        await cq.answer()
        return

    pi = calc_page(total=total, page=page, page_size=LIST_PAGE_SIZE)
    rows = await orders.list_for_client_page(cq.from_user.id, statuses=DONE_STATUSES, limit=pi.limit, offset=pi.offset)
    kb = kb_orders_list(locale, rows, back_target="order_menu")
    pager = pager_row("c:history", pi.page, pi.total_pages)
    if pager:
        kb.inline_keyboard.append(pager)
    kb.inline_keyboard.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:order_menu")])
    await cq.message.edit_text(t(locale, "orders.history.title"), reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("c:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
    order_id = int(cq.data.split(":")[2])
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "order_card", {"order_id": order_id})
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        if is_chat_reminder_text(cq.message.text if cq.message else None):
            # Напоминание удаляем и показываем экран без редактирования старого сообщения.
            await safe_delete_cq_message(cq)
            await show_screen(
                bot=cq.bot,
                chat_id=cq.from_user.id,
                state=state,
                db=db,
                bot_kind="client",
                text=t(locale, "order.not_found"),
                reply_markup=kb_client_main(locale),
            )
        else:
            await cq.message.edit_text(t(locale, "order.not_found"), reply_markup=kb_client_main(locale))
        await cq.answer()
        return

    if o.get("courier_status") == "arrived" and int(o.get("handoff_confirmed") or 0) == 0:
        await _show_arrival_screen(cq, db, locale, o)
        await cq.answer()
        return

    items = await orders.get_order_items(order_id)
    shop = ShopsRepo(db)
    shop_info = await shop.get(int(o["shop_id"]))
    shop_name = shop_info["name"] if shop_info else f"#{o['shop_id']}"

    await _render_order_card(cq, state, db, locale, o, items, shop_name)
    await cq.answer()


@router.callback_query(F.data.startswith("c:cancel:"))
async def cancel_order(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
    order_id = int(cq.data.split(":")[2])
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        if is_chat_reminder_text(cq.message.text if cq.message else None):
            # Напоминание удаляем и показываем экран без редактирования старого сообщения.
            await safe_delete_cq_message(cq)
            await show_screen(
                bot=cq.bot,
                chat_id=cq.from_user.id,
                state=state,
                db=db,
                bot_kind="client",
                text=t(locale, "order.not_found"),
                reply_markup=kb_client_main(locale),
            )
        else:
            await cq.message.edit_text(t(locale, "order.not_found"), reply_markup=kb_client_main(locale))
        await cq.answer()
        return

    now = utcnow()
    created_at = _parse_created_at(o.get("created_at"))
    if o.get("status") == "canceled":
        await cq.answer(t(locale, "order.cancel.already"), show_alert=True)
    elif o.get("status") not in CANCELABLE_STATUSES:
        await cq.answer(t(locale, "order.cancel.unavailable"), show_alert=True)
    elif not created_at or now - created_at > timedelta(minutes=CANCEL_WINDOW_MINUTES):
        await cq.answer(t(locale, "order.cancel.expired"), show_alert=True)
    else:
        await orders.set_merchant_status(order_id, "canceled")
        await orders.set_courier_status(order_id, "canceled")
        o["status"] = "canceled"
        o["merchant_status"] = "canceled"
        o["courier_status"] = "canceled"
        try:
            await notify_admins_order_canceled(db, order_id=order_id, shop_id=int(o["shop_id"]))
        except Exception:
            logger.warning("Не удалось отправить уведомление об отмене заказа %s", order_id, exc_info=True)
        await cq.answer(t(locale, "order.cancel.success"))

    if o.get("courier_status") == "arrived" and int(o.get("handoff_confirmed") or 0) == 0:
        await _show_arrival_screen(cq, db, locale, o)
        await cq.answer()
        return

    items = await orders.get_order_items(order_id)
    shop = ShopsRepo(db)
    shop_info = await shop.get(int(o["shop_id"]))
    shop_name = shop_info["name"] if shop_info else f"#{o['shop_id']}"
    await _render_order_card(cq, state, db, locale, o, items, shop_name)




def kb_arrival_first(locale: str, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "order_card.chat"), callback_data=f"c:chat:{order_id}")],
        [InlineKeyboardButton(text=t(locale, "order.arrival.confirm_button"), callback_data=f"c:arrival:confirm:{order_id}")],
        [InlineKeyboardButton(text=t(locale, "order.arrival.back"), callback_data="c:orders")],
    ])


def kb_arrival_second(locale: str, order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "order.arrival.confirm_final"), callback_data=f"c:arrival:done:{order_id}")],
        [InlineKeyboardButton(text=t(locale, "order.arrival.cancel"), callback_data=f"c:order:{order_id}")],
    ])


async def _show_arrival_screen(cq: CallbackQuery, db: Database, locale: str, order: dict) -> None:
    text = (
        f"{t(locale, 'order.arrival.title')}\n"
        f"{t(locale, 'orders.item_tpl', order_id=order['id'])}\n"
        f"{t(locale, 'order.total', total=order['total_amount'])}\n"
        f"{t(locale, 'order.arrival.code_label', code=(order.get('handoff_code') or '----'))}"
    )
    await cq.message.edit_text(text, reply_markup=kb_arrival_first(locale, int(order['id'])))


@router.callback_query(F.data.startswith("c:arrival:confirm:"))
async def arrival_confirm(cq: CallbackQuery, db: Database, locale: str = "ru"):
    order_id = int(cq.data.split(":")[-1])
    o = await OrdersRepo(db).get_order(order_id)
    if not o or int(o.get("client_user_id") or 0) != cq.from_user.id:
        await cq.answer(t(locale, "order.not_found"), show_alert=True)
        return
    await cq.message.edit_text(t(locale, "order.arrival.title"), reply_markup=kb_arrival_second(locale, order_id))
    await cq.answer()


@router.callback_query(F.data.startswith("c:arrival:done:"))
async def arrival_done(cq: CallbackQuery, db: Database, locale: str = "ru"):
    order_id = int(cq.data.split(":")[-1])
    repo = OrdersRepo(db)
    o = await repo.get_order(order_id)
    if not o or int(o.get("client_user_id") or 0) != cq.from_user.id:
        await cq.answer(t(locale, "order.not_found"), show_alert=True)
        return
    await repo.confirm_client_handoff(order_id)
    await cq.answer(t(locale, "order.arrival.done"), show_alert=True)
    updated = await repo.get_order(order_id)
    items = await repo.get_order_items(order_id)
    shop_info = await ShopsRepo(db).get(int(updated["shop_id"]))
    shop_name = shop_info["name"] if shop_info else f"#{updated['shop_id']}"
    text = _build_order_text(locale, updated, items, shop_name)
    await cq.message.edit_text(text, reply_markup=kb_order_card(locale, order_id, "c:history", can_cancel=False, can_chat=False, can_repeat=True))

@router.callback_query(F.data.startswith("c:chat:p:"))
async def chat_list_page(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    page = int(cq.data.split(":")[-1])
    await chat_list_render(cq, db, state, locale, page)


@router.callback_query(F.data == "c:chat")
async def chat_list(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    await chat_list_render(cq, db, state, locale, 0)


async def chat_list_render(cq: CallbackQuery, db: Database, state: FSMContext, locale: str, page: int):
    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "chat_list", {})
    chats = ChatRepo(db)
    total = await chats.count_order_ids_with_chat(user_id=cq.from_user.id)
    if total <= 0:
        await cq.message.edit_text(t(locale, "chat.none"), reply_markup=kb_client_main(locale))
        await cq.answer()
        return

    pi = calc_page(total=total, page=page, page_size=LIST_PAGE_SIZE)
    order_ids = await chats.list_order_ids_with_chat_page(user_id=cq.from_user.id, limit=pi.limit, offset=pi.offset)
    brief_rows = await OrdersRepo(db).list_brief_by_ids(order_ids)
    kb = kb_chat_orders(locale, brief_rows, "c")
    pager = pager_row("c:chat", pi.page, pi.total_pages)
    if pager:
        kb.inline_keyboard.append(pager)
    kb.inline_keyboard.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:main")])
    await cq.message.edit_text(t(locale, "chat.list_title"), reply_markup=kb)
    await cq.answer()


async def render_chat(
    cq: CallbackQuery,
    db: Database,
    order_id: int,
    page: int,
    show_hint: bool,
    locale: str,
    back_target: str | None = None,
) -> None:
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    shop = ShopsRepo(db)
    shop_info = await shop.get(int(order["shop_id"])) if order else None
    business_type = shop_info["business_type"] if shop_info else "shop"

    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = calc_total_pages(total_messages, PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (total_pages - page) * PAGE_SIZE
    messages = await chat.list_messages(order_id, limit=PAGE_SIZE, offset=offset)

    text = build_chat_screen_text(
        order_id,
        messages,
        show_hint,
        business_type,
        locale,
        "client",
        shop_name=shop_info["name"] if shop_info else None,
    )
    kb = build_chat_screen_kb(order_id, page, total_pages, "c", kb_chat_nav_rows(locale, order_id, back_target))
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("c:chat:"))
@router.callback_query(F.data.startswith("c:chat:"))
async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database, locale: str = "ru"):
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Для напоминания сначала удаляем сообщение.
        await safe_delete_cq_message(cq)
    order_id = int(cq.data.split(":")[2])
    src, page = parse_notif_context(cq.data)
    back_target = None
    if src == NOTIF_SRC_MSGS:
        page = max(1, page or 1)
        back_target = "c:notif:msgs" if page == 1 else f"c:notif:msgp:{page}"
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        await cq.message.edit_text(t(locale, "chat.not_found"), reply_markup=kb_client_main(locale))
        await cq.answer()
        return
    if not await can_access_order_chat(db, o):
        await cq.answer(t(locale, "chat.closed"), show_alert=True)
        return

    await cancel_chat_reminder(db, order_id, cq.from_user.id, "client")
    await state.set_state(ClientChatStates.active)
    await state.update_data(chat_order_id=order_id, chat_back_target=back_target)

    # сразу ставим страницу на последнюю
    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
    await state.update_data(chat_page=total_pages)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(
        state,
        "chat",
        {"order_id": order_id, "page": total_pages, "back_target": back_target},
    )

    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=make_chat_render_fn(db, state, locale),
        db=db,
        bot_kind="client",
    )
    await controller.refresh()
    await ChatReadsRepo(db).mark_read(order_id, "client", cq.from_user.id)
    await cq.answer()


@router.callback_query(F.data.startswith("c:chatp:"))
@router.callback_query(F.data.startswith("c:chatp:"))
async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database, locale: str = "ru"):
    order_id = int(cq.data.split(":")[2])
    page = int(cq.data.split(":")[3])

    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != cq.from_user.id:
        await cq.answer(t(locale, "chat.unavailable"), show_alert=True)
        return
    if not await can_access_order_chat(db, o):
        await cq.answer(t(locale, "chat.closed"), show_alert=True)
        return

    data = await state.get_data()
    back_target = data.get("chat_back_target")
    await state.update_data(chat_order_id=order_id, chat_page=page, chat_back_target=back_target)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(
        state,
        "chat",
        {"order_id": order_id, "page": page, "back_target": back_target},
    )

    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.from_user.id,
        state=state,
        render=make_chat_render_fn(db, state, locale),
        db=db,
        bot_kind="client",
    )
    await controller.refresh()
    await cq.answer()


@router.message(ClientChatStates.active)
async def send_chat_message(message: Message, state: FSMContext, db: Database, locale: str = "ru"):
    text = (message.text or "").strip()
    if not text:
        await message.answer(t(locale, "chat.send_prompt"))
        return

    data = await state.get_data()
    order_id = int(data.get("chat_order_id") or 0)
    orders = OrdersRepo(db)
    o = await orders.get_order(order_id)
    if not o or int(o["client_user_id"]) != message.from_user.id:
        await message.answer(t(locale, "chat.unavailable"))
        return
    if not await can_access_order_chat(db, o):
        await message.answer(t(locale, "chat.closed"))
        return

    chat = ChatRepo(db)
    await chat.add_message(order_id, message.from_user.id, "client", text)

    await cancel_chat_reminder(db, order_id, message.from_user.id, "client")
    admins = AdminsRepo(db)
    admin_ids = await admins.list_admin_user_ids(int(o["shop_id"]))
    shops = ShopsRepo(db)
    shop = await shops.get(int(o["shop_id"]))
    admin_kind = "admin_shop"
    if shop and shop.get("business_type") == "restaurant":
        admin_kind = "admin_restaurant"
    for uid in admin_ids:
        await schedule_chat_reminder(db, order_id, uid, admin_kind, text)
    # 3) после добавления — пересчитать последнюю страницу
    total_messages = await chat.count_messages(order_id)
    total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
    await state.update_data(chat_page=total_pages)
    await state.update_data(user_id=message.from_user.id)
    back_target = data.get("chat_back_target")
    await remember_client_screen(
        state,
        "chat",
        {"order_id": order_id, "page": total_pages, "back_target": back_target},
    )

    # 4) удалить сообщение пользователя + пересоздать экран
    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=make_chat_render_fn(db, state, locale),
        db=db,
        bot_kind="client",
    )
    await controller.refresh_after_user_message(message)


@router.callback_query(F.data.startswith("c:order_repeat:"))
async def repeat_order(cq: CallbackQuery, db: Database, state: FSMContext, locale: str = "ru"):
    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
    order_id = int(cq.data.split(":")[2])
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    if not order or int(order.get("client_user_id") or 0) != cq.from_user.id:
        await cq.answer(t(locale, "common.no_access"), show_alert=True)
        return

    if str(order.get("status") or "").strip().lower() not in CLOSED_STATUSES:
        await cq.answer(t(locale, "order.repeat.unavailable"), show_alert=True)
        return

    result = await orders.repeat_order_to_cart(order_id, cq.from_user.id)
    shop = ShopsRepo(db)
    shop_info = await shop.get(int(result["shop_id"]))
    business_type = shop_info["business_type"] if shop_info else None
    await state.update_data(cart_kind=business_type)

    lines = [t(locale, "order.repeat.added", count=result["added_count"])]
    if result["skipped_names"]:
        lines.append(t(locale, "order.repeat.skipped", names=", ".join(result["skipped_names"])))
    await cq.answer("\n".join(lines), show_alert=True)

    await state.update_data(user_id=cq.from_user.id, cart_kind=business_type, cart_back_target="order_menu")
    await remember_client_screen(
        state,
        "cart",
        {"business_type": business_type, "back_target": "order_menu"},
    )
    await render_cart(
        cq.message,
        cq.from_user.id,
        db,
        business_type=business_type,
        back_target="order_menu",
        locale=locale,
    )
