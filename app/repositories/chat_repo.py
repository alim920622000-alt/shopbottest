from __future__ import annotations

from typing import Sequence

from app.db.database import Database


class ChatRepo:
    def __init__(self, db: Database):
        self.db = db

    async def add_message(self, order_id: int, sender_user_id: int, sender_role: str, message_text: str) -> int:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                INSERT INTO order_chat_messages(order_id, sender_user_id, sender_role, message_text)
                VALUES (?, ?, ?, ?)
                """,
                (order_id, sender_user_id, sender_role, message_text),
            )
            await conn.commit()
            return int(cur.lastrowid)

    async def list_messages(self, order_id: int, limit: int = 20, offset: int = 0) -> Sequence[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT sender_user_id, sender_role, message_text, created_at
                FROM order_chat_messages
                WHERE order_id=?
                ORDER BY created_at DESC
                LIMIT ?
                OFFSET ?
                """,
                (order_id, limit, offset),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows][::-1]

    async def count_messages(self, order_id: int) -> int:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM order_chat_messages
                WHERE order_id=?
                """,
                (order_id,),
            )
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0


    async def count_order_ids_with_chat(self, user_id: int | None = None, shop_id: int | None = None) -> int:
        if not user_id and not shop_id:
            return 0
        if user_id:
            q = """
                SELECT COUNT(*) AS cnt
                FROM (
                    SELECT DISTINCT o.id
                    FROM orders o
                    JOIN order_chat_messages m ON m.order_id = o.id
                    WHERE o.client_user_id=?
                ) x
            """
            params = (user_id,)
        else:
            q = """
                SELECT COUNT(*) AS cnt
                FROM (
                    SELECT DISTINCT o.id
                    FROM orders o
                    JOIN order_chat_messages m ON m.order_id = o.id
                    WHERE o.shop_id=?
                ) x
            """
            params = (shop_id,)
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_order_ids_with_chat_page(
        self,
        *,
        user_id: int | None = None,
        shop_id: int | None = None,
        limit: int,
        offset: int,
    ) -> list[int]:
        if not user_id and not shop_id:
            return []
        if user_id:
            q = """
                SELECT DISTINCT o.id
                FROM orders o
                JOIN order_chat_messages m ON m.order_id = o.id
                WHERE o.client_user_id=?
                ORDER BY o.created_at DESC
                LIMIT ? OFFSET ?
            """
            params = (user_id, limit, offset)
        else:
            q = """
                SELECT DISTINCT o.id
                FROM orders o
                JOIN order_chat_messages m ON m.order_id = o.id
                WHERE o.shop_id=?
                ORDER BY o.created_at DESC
                LIMIT ? OFFSET ?
            """
            params = (shop_id, limit, offset)
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [int(r["id"]) for r in rows]

    async def list_order_ids_with_chat(self, user_id: int | None = None, shop_id: int | None = None) -> list[int]:
        if not user_id and not shop_id:
            return []
        if user_id:
            q = """
                SELECT DISTINCT o.id
                FROM orders o
                JOIN order_chat_messages m ON m.order_id = o.id
                WHERE o.client_user_id=?
                ORDER BY o.created_at DESC
            """
            params = (user_id,)
        else:
            q = """
                SELECT DISTINCT o.id
                FROM orders o
                JOIN order_chat_messages m ON m.order_id = o.id
                WHERE o.shop_id=?
                ORDER BY o.created_at DESC
            """
            params = (shop_id,)
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [int(r["id"]) for r in rows]
