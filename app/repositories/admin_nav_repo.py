from __future__ import annotations

from typing import Optional

from app.db.database import Database


class AdminNavRepo:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def set_prev_target(self, bot_kind: str, user_id: int, prev_target: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """
                INSERT INTO admin_nav_state (bot_kind, user_id, prev_target, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(bot_kind, user_id)
                DO UPDATE SET prev_target=excluded.prev_target, updated_at=CURRENT_TIMESTAMP
                """,
                (bot_kind, user_id, prev_target),
            )
            await conn.commit()

    async def get_prev_target(self, bot_kind: str, user_id: int) -> Optional[str]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT prev_target FROM admin_nav_state WHERE bot_kind=? AND user_id=?",
                (bot_kind, user_id),
            )
            row = await cur.fetchone()
        return row["prev_target"] if row else None
