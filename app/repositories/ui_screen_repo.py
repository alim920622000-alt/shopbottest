from __future__ import annotations

from typing import Optional

from app.db.database import Database


class UiScreenRepo:
    def __init__(self, db: Database):
        self.db = db

    async def get(self, bot_kind: str, chat_id: int) -> Optional[int]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT screen_message_id
                FROM ui_screens
                WHERE bot_kind=? AND chat_id=?
                """,
                (bot_kind, chat_id),
            )
            row = await cur.fetchone()
            if row and row["screen_message_id"] is not None:
                return int(row["screen_message_id"])
            return None

    async def get_info(self, bot_kind: str, chat_id: int) -> tuple[Optional[int], Optional[str]]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT screen_message_id, screen_kind
                FROM ui_screens
                WHERE bot_kind=? AND chat_id=?
                """,
                (bot_kind, chat_id),
            )
            row = await cur.fetchone()
            if not row:
                return None, None
            screen_message_id = row["screen_message_id"]
            screen_kind = row["screen_kind"]
            return (
                int(screen_message_id) if screen_message_id is not None else None,
                str(screen_kind) if screen_kind is not None else None,
            )

    async def set(
        self,
        bot_kind: str,
        chat_id: int,
        screen_message_id: int,
        screen_kind: Optional[str] = None,
    ) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """
                INSERT INTO ui_screens (bot_kind, chat_id, screen_message_id, screen_kind, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bot_kind, chat_id) DO UPDATE SET
                    screen_message_id=excluded.screen_message_id,
                    screen_kind=excluded.screen_kind,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (bot_kind, chat_id, screen_message_id, screen_kind),
            )
            await conn.commit()

    async def clear(self, bot_kind: str, chat_id: int) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """
                UPDATE ui_screens
                SET screen_message_id=NULL, screen_kind=NULL, updated_at=CURRENT_TIMESTAMP
                WHERE bot_kind=? AND chat_id=?
                """,
                (bot_kind, chat_id),
            )
            await conn.commit()
