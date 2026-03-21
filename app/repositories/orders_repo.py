from __future__ import annotations
from typing import Optional, Sequence
from app.db.database import Database
from app.repositories.cart_repo import CartRepo


class OrdersRepo:
    def __init__(self, db: Database):
        self.db = db

    async def create_order_from_cart(self, shop_id: int, client_user_id: int, comment: str = "", fulfillment_type: str = "courier") -> int:
        """
        Создает заказ и позиции из таблицы cart для указанного shop_id.
        Возвращает order_id.
        """
        async with self.db.conn() as conn:
            await conn.execute("BEGIN;")

            # берем корзину только по выбранному shop_id
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

            cur2 = await conn.execute(
                """INSERT INTO orders (shop_id, client_user_id, status, total_amount, comment, fulfillment_type, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (shop_id, client_user_id, "new", total, comment, fulfillment_type),
            )
            order_id = int(cur2.lastrowid)

            for r in items:
                await conn.execute(
                    """INSERT INTO order_items (order_id, product_id, quantity, price_at_moment)
                       VALUES (?, ?, ?, ?)""",
                    (order_id, int(r["product_id"]), int(r["quantity"]), float(r["price"])),
                )

            # чистим корзину только по этому shop
            await conn.execute(
                """DELETE FROM cart
                   WHERE user_id=? AND product_id IN (
                       SELECT id FROM products WHERE shop_id=?
                   )""",
                (client_user_id, shop_id),
            )

            await conn.commit()
            return order_id

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

    async def set_status(self, order_id: int, new_status: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                "UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (new_status, order_id),
            )
            await conn.commit()

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
        q += " ORDER BY o.created_at DESC"
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def repeat_order_to_cart(self, order_id: int, client_user_id: int) -> dict:
        """Восстанавливает позиции старого заказа в корзину клиента."""
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

        return {
            "shop_id": int(order["shop_id"]),
            "added_count": added_count,
            "skipped_names": skipped_names,
        }

    async def create_order_with_items(
        self,
        shop_id: int,
        client_user_id: int,
        items: list[tuple[int, int]],
        comment: str = '',
        fulfillment_type: str = 'courier',
    ) -> int:
        async with self.db.conn() as conn:
            total = 0.0
            collected = []
            for product_id, quantity in items:
                cur = await conn.execute(
                    "SELECT price, shop_id FROM products WHERE id=? AND is_active=1",
                    (product_id,),
                )
                row = await cur.fetchone()
                if not row:
                    raise ValueError(f"Товар {product_id} не найден")
                price = float(row["price"])
                total += price * quantity
                collected.append((product_id, quantity, price))

            cur2 = await conn.execute(
                "INSERT INTO orders (shop_id, client_user_id, status, total_amount, comment, fulfillment_type, updated_at, merchant_status, courier_status) VALUES (?, ?, 'new', ?, ?, ?, CURRENT_TIMESTAMP, 'new', 'searching')",
                (shop_id, client_user_id, total, comment, fulfillment_type),
            )
            order_id = int(cur2.lastrowid)

            for product_id, quantity, price in collected:
                await conn.execute(
                    "INSERT INTO order_items (order_id, product_id, quantity, price_at_moment) VALUES (?, ?, ?, ?)",
                    (order_id, product_id, quantity, price),
                )
            await conn.commit()
        return order_id
