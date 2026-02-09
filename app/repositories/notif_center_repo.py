from __future__ import annotations

from typing import Optional

from app.db.database import Database


class NotifCenterRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def get_message_id(self, bot_kind: str, chat_id: int) -> Optional[int]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT message_id
                FROM notif_center_state
                WHERE bot_kind=? AND chat_id=?
                """,
                (bot_kind, chat_id),
            )
            row = await cur.fetchone()
            if row and row["message_id"] is not None:
                return int(row["message_id"])
            return None

    async def set_message_id(self, bot_kind: str, chat_id: int, message_id: int) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """
                INSERT INTO notif_center_state (bot_kind, chat_id, message_id, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bot_kind, chat_id) DO UPDATE SET
                    message_id=excluded.message_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (bot_kind, chat_id, message_id),
            )
            await conn.commit()

    async def clear(self, bot_kind: str, chat_id: int) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """
                DELETE FROM notif_center_state
                WHERE bot_kind=? AND chat_id=?
                """,
                (bot_kind, chat_id),
            )
            await conn.commit()
