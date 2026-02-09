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

    async def mark_read(self, order_id: int, viewer_role: str, viewer_user_id: int) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """
                INSERT INTO order_chat_reads(order_id, viewer_role, viewer_user_id, last_read_at)
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(order_id, viewer_role, viewer_user_id) DO UPDATE SET
                    last_read_at=datetime('now')
                """,
                (order_id, viewer_role, viewer_user_id),
            )
            await conn.commit()

    async def get_unread_count_for_order(self, order_id: int, viewer_role: str, viewer_user_id: int) -> int:
        last_read_at = await self.get_last_read_at(order_id, viewer_role, viewer_user_id)
        last_read_at = last_read_at or "1970-01-01"
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM order_chat_messages
                WHERE order_id=?
                  AND NOT (sender_role = ? AND sender_user_id = ?)
                  AND created_at > ?
                """,
                (order_id, viewer_role, viewer_user_id, last_read_at),
            )
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_orders_with_unread(
        self,
        viewer_role: str,
        viewer_user_id: int,
        limit: int,
        offset: int,
    ) -> Sequence[dict]:
        access_join, access_where, access_params = self._build_access_filter(viewer_role, viewer_user_id)
        async with self.db.conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT m.order_id, COUNT(*) as cnt
                FROM order_chat_messages m
                LEFT JOIN order_chat_reads r
                    ON r.order_id = m.order_id
                    AND r.viewer_role = ?
                    AND r.viewer_user_id = ?
                -- фильтры доступа: не показываем чужие чаты
                {access_join}
                WHERE NOT (m.sender_role = ? AND m.sender_user_id = ?)
                  AND m.created_at > COALESCE(r.last_read_at, '1970-01-01')
                  {access_where}
                GROUP BY m.order_id
                HAVING cnt > 0
                ORDER BY m.order_id DESC
                LIMIT ? OFFSET ?
                """,
                (
                    viewer_role,
                    viewer_user_id,
                    viewer_role,
                    viewer_user_id,
                    *access_params,
                    limit,
                    offset,
                ),
            )
            rows = await cur.fetchall()
            return [
                {"order_id": int(row["order_id"]), "unread_count": int(row["cnt"])}
                for row in rows
            ]

    async def get_total_unread_count(self, viewer_role: str, viewer_user_id: int) -> int:
        access_join, access_where, access_params = self._build_access_filter(viewer_role, viewer_user_id)
        async with self.db.conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT COUNT(*) as cnt
                FROM order_chat_messages m
                LEFT JOIN order_chat_reads r
                    ON r.order_id = m.order_id
                    AND r.viewer_role = ?
                    AND r.viewer_user_id = ?
                -- фильтры доступа: не показываем чужие чаты
                {access_join}
                WHERE NOT (m.sender_role = ? AND m.sender_user_id = ?)
                  AND m.created_at > COALESCE(r.last_read_at, '1970-01-01')
                  {access_where}
                """,
                (viewer_role, viewer_user_id, viewer_role, viewer_user_id, *access_params),
            )
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def count_unread_orders(self, viewer_role: str, viewer_user_id: int) -> int:
        access_join, access_where, access_params = self._build_access_filter(viewer_role, viewer_user_id)
        async with self.db.conn() as conn:
            cur = await conn.execute(
                f"""
                SELECT COUNT(*) as cnt
                FROM (
                    SELECT m.order_id
                    FROM order_chat_messages m
                    LEFT JOIN order_chat_reads r
                        ON r.order_id = m.order_id
                        AND r.viewer_role = ?
                        AND r.viewer_user_id = ?
                    -- фильтры доступа: не показываем чужие чаты
                    {access_join}
                    WHERE NOT (m.sender_role = ? AND m.sender_user_id = ?)
                      AND m.created_at > COALESCE(r.last_read_at, '1970-01-01')
                      {access_where}
                    GROUP BY m.order_id
                )
                """,
                (viewer_role, viewer_user_id, viewer_role, viewer_user_id, *access_params),
            )
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    def _build_access_filter(self, viewer_role: str, viewer_user_id: int) -> tuple[str, str, list]:
        # Фильтры доступа, чтобы не показывать чужие чаты в центре уведомлений.
        if viewer_role == "client":
            return (
                "JOIN orders o ON o.id = m.order_id",
                "AND o.client_user_id = ?",
                [viewer_user_id],
            )
        if viewer_role in {"admin_shop", "admin_restaurant"}:
            business_type = "shop" if viewer_role == "admin_shop" else "restaurant"
            return (
                "JOIN orders o ON o.id = m.order_id "
                "JOIN shops s ON s.id = o.shop_id "
                "JOIN shop_admins sa ON sa.shop_id = s.id",
                "AND sa.user_id = ? AND s.business_type = ?",
                [viewer_user_id, business_type],
            )
        return ("", "", [])
