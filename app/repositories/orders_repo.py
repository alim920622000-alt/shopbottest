from __future__ import annotations
from typing import Optional, Sequence

from app.db.database import Database
from app.repositories.cart_repo import CartRepo
from app.services.order_statuses import map_to_legacy


ACTIVE_COURIER_STATUSES = ("assigned", "picked_up", "arrived")
HISTORY_COURIER_STATUSES = ("delivered", "canceled")


class OrdersRepo:
    def __init__(self, db: Database):
        self.db = db

    async def create_order_from_cart(self, shop_id: int, client_user_id: int, comment: str = "", fulfillment_type: str = "courier") -> int:
        async with self.db.conn() as conn:
            await conn.execute("BEGIN;")
            cur = await conn.execute(
                """SELECT c.product_id, c.quantity, p.price
                   FROM cart c
                   JOIN products p ON p.id=c.product_id
                   WHERE c.user_id=? AND p.shop_id=? AND p.is_active=1""",
                (client_user_id, shop_id),
            )
            items = await cur.fetchall()
            if not items:
                await conn.execute("ROLLBACK;")
                raise ValueError("Cart is empty for this shop")

            total = 0.0
            for r in items:
                total += float(r["price"]) * int(r["quantity"])

            legacy_status = map_to_legacy("new", "searching")
            cur2 = await conn.execute(
                """INSERT INTO orders (
                    shop_id, client_user_id, status, merchant_status, courier_status,
                    total_amount, comment, fulfillment_type, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (shop_id, client_user_id, legacy_status, "new", "searching", total, comment, fulfillment_type),
            )
            order_id = int(cur2.lastrowid)

            for r in items:
                await conn.execute(
                    """INSERT INTO order_items (order_id, product_id, quantity, price_at_moment)
                       VALUES (?, ?, ?, ?)""",
                    (order_id, int(r["product_id"]), int(r["quantity"]), float(r["price"])),
                )

            await conn.execute(
                """DELETE FROM cart
                   WHERE user_id=? AND product_id IN (
                       SELECT id FROM products WHERE shop_id=?
                   )""",
                (client_user_id, shop_id),
            )

            await conn.commit()
            return order_id

    async def _sync_legacy_status(self, conn, order_id: int) -> None:
        cur = await conn.execute("SELECT merchant_status, courier_status FROM orders WHERE id=?", (order_id,))
        row = await cur.fetchone()
        if not row:
            return
        legacy = map_to_legacy(row["merchant_status"], row["courier_status"])
        await conn.execute("UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (legacy, order_id))

    async def set_merchant_status(self, order_id: int, status: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute("UPDATE orders SET merchant_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, order_id))
            await self._sync_legacy_status(conn, order_id)
            await conn.commit()

    async def set_courier_status(self, order_id: int, status: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute("UPDATE orders SET courier_status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, order_id))
            await self._sync_legacy_status(conn, order_id)
            await conn.commit()

    async def set_status(self, order_id: int, new_status: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute("UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (new_status, order_id))
            await conn.commit()

    async def set_handoff_code_if_empty(self, order_id: int, code: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                "UPDATE orders SET handoff_code=COALESCE(NULLIF(handoff_code, ''), ?), updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (code, order_id),
            )
            await conn.commit()

    async def confirm_client_handoff(self, order_id: int) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """UPDATE orders
                   SET handoff_confirmed=1, merchant_status='completed', courier_status='delivered', updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (order_id,),
            )
            await self._sync_legacy_status(conn, order_id)
            await conn.commit()

    async def set_client_arrival_message_id(self, order_id: int, message_id: int) -> None:
        async with self.db.conn() as conn:
            await conn.execute("UPDATE orders SET client_arrival_message_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (message_id, order_id))
            await conn.commit()

    async def assign_courier_atomic(self, order_id: int, courier_user_id: int) -> bool:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """UPDATE orders
                   SET courier_user_id=?, courier_status='assigned', updated_at=CURRENT_TIMESTAMP
                   WHERE id=? AND courier_status='searching'""",
                (courier_user_id, order_id),
            )
            updated = cur.rowcount > 0
            if updated:
                await self._sync_legacy_status(conn, order_id)
            await conn.commit()
            return updated

    async def list_current_for_shop(self, shop_id: int, statuses: Sequence[str]) -> Sequence[dict]:
        placeholders = ",".join(["?"] * len(statuses))
        q = f"""SELECT * FROM orders
                WHERE shop_id=? AND status IN ({placeholders})
                ORDER BY created_at DESC"""
        params = [shop_id, *statuses]
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_history_for_shop(self, shop_id: int, statuses: Sequence[str]) -> Sequence[dict]:
        return await self.list_current_for_shop(shop_id, statuses)

    async def count_for_shop(self, shop_id: int, statuses: Sequence[str]) -> int:
        placeholders = ",".join(["?"] * len(statuses))
        q = f"""SELECT COUNT(*) AS cnt FROM orders
                WHERE shop_id=? AND status IN ({placeholders})"""
        params = [shop_id, *statuses]
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_current_for_shop_page(self, shop_id: int, statuses: Sequence[str], *, limit: int, offset: int) -> Sequence[dict]:
        placeholders = ",".join(["?"] * len(statuses))
        q = f"""SELECT * FROM orders
                WHERE shop_id=? AND status IN ({placeholders})
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?"""
        params = [shop_id, *statuses, limit, offset]
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def count_for_client(self, client_user_id: int, statuses: Sequence[str] | None = None) -> int:
        q = "SELECT COUNT(*) AS cnt FROM orders WHERE client_user_id=?"
        params: list = [client_user_id]
        if statuses:
            placeholders = ",".join(["?"] * len(statuses))
            q += f" AND status IN ({placeholders})"
            params.extend(statuses)
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_for_client_page(self, client_user_id: int, statuses: Sequence[str] | None = None, *, limit: int, offset: int) -> Sequence[dict]:
        q = """
            SELECT o.*, s.name AS shop_name, s.business_type
            FROM orders o
            JOIN shops s ON s.id = o.shop_id
            WHERE o.client_user_id=?
        """
        params: list = [client_user_id]
        if statuses:
            placeholders = ",".join(["?"] * len(statuses))
            q += f" AND o.status IN ({placeholders})"
            params.extend(statuses)
        q += " ORDER BY CASE WHEN o.courier_status='arrived' THEN 0 ELSE 1 END, o.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_brief_by_ids(self, order_ids: Sequence[int]) -> Sequence[dict]:
        if not order_ids:
            return []
        placeholders = ",".join(["?"] * len(order_ids))
        q = f"""
            SELECT o.id, o.shop_id, s.name AS shop_name, s.business_type
            FROM orders o
            JOIN shops s ON s.id = o.shop_id
            WHERE o.id IN ({placeholders})
        """
        async with self.db.conn() as conn:
            cur = await conn.execute(q, [int(oid) for oid in order_ids])
            rows = await cur.fetchall()
        rows_by_id = {int(row["id"]): dict(row) for row in rows}
        return [rows_by_id[int(oid)] for oid in order_ids if int(oid) in rows_by_id]

    async def get_order(self, order_id: int) -> Optional[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT * FROM orders WHERE id=?", (order_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_order_items(self, order_id: int) -> Sequence[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """SELECT oi.product_id, oi.quantity, oi.price_at_moment, p.name
                   FROM order_items oi
                   JOIN products p ON p.id=oi.product_id
                   WHERE oi.order_id=?""",
                (order_id,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_for_client(self, client_user_id: int, statuses: Sequence[str] | None = None) -> Sequence[dict]:
        q = """
            SELECT o.*, s.name AS shop_name, s.business_type
            FROM orders o
            JOIN shops s ON s.id = o.shop_id
            WHERE o.client_user_id=?
        """
        params: list = [client_user_id]
        if statuses:
            placeholders = ",".join(["?"] * len(statuses))
            q += f" AND o.status IN ({placeholders})"
            params.extend(statuses)
        q += " ORDER BY CASE WHEN o.courier_status='arrived' THEN 0 ELSE 1 END, o.created_at DESC"
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_available_for_courier(self, courier_user_id: int) -> Sequence[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT accept_all_zones FROM couriers WHERE user_id=?", (courier_user_id,))
            courier = await cur.fetchone()
            if not courier:
                return []
            accept_all = int(courier["accept_all_zones"] or 0) == 1
            q = """
                SELECT o.*, s.name AS shop_name
                FROM orders o
                JOIN shops s ON s.id=o.shop_id
                WHERE o.courier_status='searching'
            """
            params: list = []
            if not accept_all:
                q += """
                  AND (
                    o.zone_id IS NULL OR o.zone_id IN (
                        SELECT zone_id FROM courier_zones WHERE courier_user_id=?
                    )
                  )
                """
                params.append(courier_user_id)
            q += " ORDER BY o.created_at DESC"
            cur2 = await conn.execute(q, params)
            rows = await cur2.fetchall()
            return [dict(r) for r in rows]

    async def list_active_for_courier(self, courier_user_id: int) -> Sequence[dict]:
        placeholders = ",".join("?" for _ in ACTIVE_COURIER_STATUSES)
        async with self.db.conn() as conn:
            cur = await conn.execute(
                f"SELECT o.*, s.name AS shop_name FROM orders o JOIN shops s ON s.id=o.shop_id WHERE o.courier_user_id=? AND o.courier_status IN ({placeholders}) ORDER BY o.updated_at DESC",
                [courier_user_id, *ACTIVE_COURIER_STATUSES],
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_history_for_courier(self, courier_user_id: int) -> Sequence[dict]:
        placeholders = ",".join("?" for _ in HISTORY_COURIER_STATUSES)
        async with self.db.conn() as conn:
            cur = await conn.execute(
                f"SELECT o.*, s.name AS shop_name FROM orders o JOIN shops s ON s.id=o.shop_id WHERE o.courier_user_id=? AND o.courier_status IN ({placeholders}) ORDER BY o.updated_at DESC",
                [courier_user_id, *HISTORY_COURIER_STATUSES],
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def repeat_order_to_cart(self, order_id: int, client_user_id: int) -> dict:
        order = await self.get_order(order_id)
        if not order or int(order.get("client_user_id") or 0) != client_user_id:
            raise PermissionError("Нет доступа к заказу")

        async with self.db.conn() as conn:
            cur = await conn.execute(
                """
                SELECT oi.product_id, oi.quantity, p.name, p.is_active
                FROM order_items oi
                LEFT JOIN products p ON p.id = oi.product_id
                WHERE oi.order_id=?
                """,
                (order_id,),
            )
            rows = await cur.fetchall()

        cart = CartRepo(self.db)
        added_count = 0
        skipped_names: list[str] = []

        for row in rows:
            product_name = row["name"] if row["name"] else f"ID {row['product_id']}"
            if row["name"] is None or int(row["is_active"] or 0) != 1:
                skipped_names.append(product_name)
                continue
            qty = int(row["quantity"] or 0)
            if qty <= 0:
                continue
            await cart.add(user_id=client_user_id, product_id=int(row["product_id"]), qty=qty)
            added_count += qty

        return {"shop_id": int(order["shop_id"]), "added_count": added_count, "skipped_names": skipped_names}
