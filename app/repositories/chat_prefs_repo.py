from __future__ import annotations

from app.db.database import Database


class ChatPrefsRepo:
    def __init__(self, db: Database):
        self.db = db

    async def get(self, order_id: int, actor_role: str, actor_id: int) -> str | None:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT thread
                FROM chat_prefs
                WHERE order_id=? AND actor_role=? AND actor_id=?
                """,
                (order_id, actor_role, actor_id),
            )
            row = await cur.fetchone()
            return str(row["thread"]) if row else None

    async def set(self, order_id: int, actor_role: str, actor_id: int, thread: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """
                INSERT INTO chat_prefs(order_id, actor_role, actor_id, thread, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(order_id, actor_role, actor_id)
                DO UPDATE SET thread=excluded.thread, updated_at=CURRENT_TIMESTAMP
                """,
                (order_id, actor_role, actor_id, thread),
            )
            await conn.commit()
