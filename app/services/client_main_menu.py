from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup

from app.db.database import Database
from app.handlers_client.kb import kb_client_main
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.orders_repo import OrdersRepo


async def build_client_main_kb_dynamic(db: Database, locale: str, user_id: int | None) -> InlineKeyboardMarkup:
    has_arrived = False
    unread_threads = 0
    if user_id:
        rows = await OrdersRepo(db).list_for_client(int(user_id))
        has_arrived = any(
            str(r.get("courier_status") or "").strip().lower() == "arrived" and int(r.get("handoff_confirmed") or 0) == 0
            for r in rows
        )
        unread_threads = await ChatReadsRepo(db).count_unread_orders("client", int(user_id))
    return kb_client_main(locale, has_arrived_order=has_arrived, chat_unread_threads=unread_threads)
