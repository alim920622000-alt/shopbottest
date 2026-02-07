from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.db.database import Database


@dataclass(frozen=True)
class ChatReminder:
    id: int
    order_id: int
    recipient_user_id: int
    recipient_kind: str
    last_message_at: str
    last_message_preview: str
    scheduled_at: str
    status: str


class ChatRemindersRepo:
    def __init__(self, db: Database):
        self.db = db

    async def upsert_pending(
        self,
        order_id: int,
        recipient_user_id: int,
        recipient_kind: str,
        last_message_at: datetime,
        last_message_preview: str,
        scheduled_at: datetime,
    ) -> None:
        async with self.db.conn() as connection:
            await connection.execute(
                """
                INSERT INTO chat_message_reminders (
                    order_id,
                    recipient_user_id,
                    recipient_kind,
                    last_message_at,
                    last_message_preview,
                    scheduled_at,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
                ON CONFLICT(order_id, recipient_user_id, recipient_kind)
                DO UPDATE SET
                    last_message_at=excluded.last_message_at,
                    last_message_preview=excluded.last_message_preview,
                    scheduled_at=excluded.scheduled_at,
                    status='pending'
                """,
                (
                    order_id,
                    recipient_user_id,
                    recipient_kind,
                    last_message_at.isoformat(timespec="seconds"),
                    last_message_preview,
                    scheduled_at.isoformat(timespec="seconds"),
                ),
            )
            await connection.commit()

    async def cancel_pending(self, order_id: int, recipient_user_id: int, recipient_kind: str) -> None:
        async with self.db.conn() as connection:
            await connection.execute(
                """
                UPDATE chat_message_reminders
                SET status='canceled'
                WHERE order_id=? AND recipient_user_id=? AND recipient_kind=? AND status='pending'
                """,
                (order_id, recipient_user_id, recipient_kind),
            )
            await connection.commit()

    async def list_due(self, recipient_kind: str, now: datetime) -> list[ChatReminder]:
        async with self.db.conn() as connection:
            cursor = await connection.execute(
                """
                SELECT id, order_id, recipient_user_id, recipient_kind,
                       last_message_at, last_message_preview, scheduled_at, status
                FROM chat_message_reminders
                WHERE recipient_kind=? AND status='pending' AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                """,
                (recipient_kind, now.isoformat(timespec="seconds")),
            )
            rows = await cursor.fetchall()

        return [
            ChatReminder(
                id=int(row["id"]),
                order_id=int(row["order_id"]),
                recipient_user_id=int(row["recipient_user_id"]),
                recipient_kind=row["recipient_kind"],
                last_message_at=row["last_message_at"],
                last_message_preview=row["last_message_preview"],
                scheduled_at=row["scheduled_at"],
                status=row["status"],
            )
            for row in rows
        ]

    async def mark_sent(self, reminder_id: int) -> None:
        async with self.db.conn() as connection:
            await connection.execute(
                """
                UPDATE chat_message_reminders
                SET status='sent'
                WHERE id=?
                """,
                (reminder_id,),
            )
            await connection.commit()

    async def mark_canceled(self, reminder_id: int) -> None:
        async with self.db.conn() as connection:
            await connection.execute(
                """
                UPDATE chat_message_reminders
                SET status='canceled'
                WHERE id=?
                """,
                (reminder_id,),
            )
            await connection.commit()
