from __future__ import annotations

from typing import Sequence

from app.db.database import Database


class OrderSeenRepo:
    def __init__(self, db: Database):
        self.db = db

    async def mark_order_seen(
        self,
        order_id: int,
        viewer_role: str,
        viewer_user_id: int,
        seen_at: str | None = None,
    ) -> None:
        async with self.db.conn() as conn:
            if seen_at:
                await conn.execute(
                    """
                    INSERT INTO order_seen(order_id, viewer_role, viewer_user_id, seen_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(order_id, viewer_role, viewer_user_id) DO UPDATE SET
                        seen_at=excluded.seen_at
                    """,
                    (order_id, viewer_role, viewer_user_id, seen_at),
                )
            else:
                await conn.execute(
                    """
                    INSERT INTO order_seen(order_id, viewer_role, viewer_user_id, seen_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(order_id, viewer_role, viewer_user_id) DO UPDATE SET
                        seen_at=CURRENT_TIMESTAMP
                    """,
                    (order_id, viewer_role, viewer_user_id),
                )
            await conn.commit()

    async def is_order_seen(self, order_id: int, viewer_role: str, viewer_user_id: int) -> bool:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT 1
                FROM order_seen
                WHERE order_id=? AND viewer_role=? AND viewer_user_id=?
                LIMIT 1
                """,
                (order_id, viewer_role, viewer_user_id),
            )
            row = await cur.fetchone()
            return row is not None

    async def count_new_orders(self, viewer_role: str, viewer_user_id: int) -> int:
        business_type = self._business_type(viewer_role)
        if not business_type:
            return 0
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM orders o
                JOIN shops s ON s.id = o.shop_id
                JOIN shop_admins sa ON sa.shop_id = o.shop_id AND sa.user_id = ?
                WHERE s.business_type = ?
                  AND o.status = 'new'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM order_seen os
                      WHERE os.order_id = o.id
                        AND os.viewer_role = ?
                        AND os.viewer_user_id = ?
                  )
                """,
                (viewer_user_id, business_type, viewer_role, viewer_user_id),
            )
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_new_orders(
        self,
        viewer_role: str,
        viewer_user_id: int,
        limit: int,
        offset: int,
    ) -> Sequence[int]:
        business_type = self._business_type(viewer_role)
        if not business_type:
            return []
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT o.id
                FROM orders o
                JOIN shops s ON s.id = o.shop_id
                JOIN shop_admins sa ON sa.shop_id = o.shop_id AND sa.user_id = ?
                WHERE s.business_type = ?
                  AND o.status = 'new'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM order_seen os
                      WHERE os.order_id = o.id
                        AND os.viewer_role = ?
                        AND os.viewer_user_id = ?
                  )
                ORDER BY o.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (viewer_user_id, business_type, viewer_role, viewer_user_id, limit, offset),
            )
            rows = await cur.fetchall()
            return [int(row["id"]) for row in rows]

    def _business_type(self, viewer_role: str) -> str | None:
        if viewer_role == "admin_shop":
            return "shop"
        if viewer_role == "admin_restaurant":
            return "restaurant"
        return None
