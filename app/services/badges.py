from __future__ import annotations

from app.db.database import Database


async def get_unread_order_ids_for_view(
    db: Database,
    viewer_role: str,
    viewer_user_id: int,
    order_ids: list[int],
) -> set[int]:
    if not order_ids:
        return set()

    unique_ids = sorted({int(order_id) for order_id in order_ids})
    placeholders = ",".join(["?"] * len(unique_ids))
    async with db.conn() as conn:
        cur = await conn.execute(
            f"""
            SELECT m.order_id
            FROM order_chat_messages m
            LEFT JOIN order_chat_reads r
                ON r.order_id = m.order_id
                AND r.viewer_role = ?
                AND r.viewer_user_id = ?
            WHERE m.order_id IN ({placeholders})
              AND NOT (m.sender_role = ? AND m.sender_user_id = ?)
              AND m.created_at > COALESCE(r.last_read_at, '1970-01-01')
            GROUP BY m.order_id
            HAVING COUNT(*) > 0
            """,
            [viewer_role, viewer_user_id, *unique_ids, viewer_role, viewer_user_id],
        )
        rows = await cur.fetchall()
    return {int(row["order_id"]) for row in rows}
