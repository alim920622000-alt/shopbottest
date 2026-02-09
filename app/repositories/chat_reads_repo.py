from __future__ import annotations

from typing import Sequence

from app.db.database import Database


class ChatReadsRepo:
    def __init__(self, db: Database):
        self.db = db

    async def get_last_read_at(self, order_id: int, viewer_role: str, viewer_user_id: int) -> str | None:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT last_read_at
                FROM order_chat_reads
                WHERE order_id=? AND viewer_role=? AND viewer_user_id=?
                """,
                (order_id, viewer_role, viewer_user_id),
            )
            row = await cur.fetchone()
            return str(row["last_read_at"]) if row else None

    async def set_last_read_at(
        self,
        order_id: int,
        viewer_role: str,
        viewer_user_id: int,
        last_read_at: str | None = None,
    ) -> None:
        async with self.db.conn() as conn:
            if last_read_at:
                await conn.execute(
                    """
                    INSERT INTO order_chat_reads(order_id, viewer_role, viewer_user_id, last_read_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(order_id, viewer_role, viewer_user_id) DO UPDATE SET
                        last_read_at=excluded.last_read_at
                    """,
                    (order_id, viewer_role, viewer_user_id, last_read_at),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO order_chat_reads(order_id, viewer_role, viewer_user_id, last_read_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(order_id, viewer_role, viewer_user_id) DO UPDATE SET
                        last_read_at=CURRENT_TIMESTAMP
                    """,
                    (order_id, viewer_role, viewer_user_id),
                )
            await conn.commit()

    async def get_unread_count_for_order(self, order_id: int, viewer_role: str, viewer_user_id: int) -> int:
        last_read_at = await self.get_last_read_at(order_id, viewer_role, viewer_user_id)
        async with self.db.conn() as conn:
            if last_read_at:
                cur = await conn.execute(
                    """
                    SELECT COUNT(*) as cnt
                    FROM order_chat_messages
                    WHERE order_id=? AND sender_user_id != ? AND created_at > ?
                    """,
                    (order_id, viewer_user_id, last_read_at),
                )
            else:
                cur = await conn.execute(
                    """
                    SELECT COUNT(*) as cnt
                    FROM order_chat_messages
                    WHERE order_id=? AND sender_user_id != ?
                    """,
                    (order_id, viewer_user_id),
                )
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_orders_with_unread(
        self,
        viewer_role: str,
        viewer_user_id: int,
        limit: int,
        offset: int,
    ) -> Sequence[int]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT m.order_id, COUNT(*) as cnt
                FROM order_chat_messages m
                LEFT JOIN order_chat_reads r
                    ON r.order_id = m.order_id
                    AND r.viewer_role = ?
                    AND r.viewer_user_id = ?
                WHERE m.sender_user_id != ?
                  AND (r.last_read_at IS NULL OR m.created_at > r.last_read_at)
                GROUP BY m.order_id
                HAVING cnt > 0
                ORDER BY m.order_id DESC
                LIMIT ? OFFSET ?
                """,
                (viewer_role, viewer_user_id, viewer_user_id, limit, offset),
            )
            rows = await cur.fetchall()
            return [int(row["order_id"]) for row in rows]

    async def get_total_unread_count(self, viewer_role: str, viewer_user_id: int) -> int:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM order_chat_messages m
                LEFT JOIN order_chat_reads r
                    ON r.order_id = m.order_id
                    AND r.viewer_role = ?
                    AND r.viewer_user_id = ?
                WHERE m.sender_user_id != ?
                  AND (r.last_read_at IS NULL OR m.created_at > r.last_read_at)
                """,
                (viewer_role, viewer_user_id, viewer_user_id),
            )
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0
