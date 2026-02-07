from __future__ import annotations

import secrets
from sqlite3 import IntegrityError
from typing import Optional, Sequence

from app.db.database import Database
from app.services.search_utils import normalize_text, build_keywords


class ProductsRepo:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _generate_sku() -> str:
        # Публичный SKU в формате SKU-XXXXXXXX (8 hex uppercase).
        return f"SKU-{secrets.token_hex(4).upper()}"

    async def _get_business_type(self, conn, shop_id: int) -> str | None:
        cur = await conn.execute("SELECT business_type FROM shops WHERE id=?", (shop_id,))
        row = await cur.fetchone()
        return row["business_type"] if row else None

    async def _reserve_sku(self, conn, shop_id: int, product_id: int, sku: str | None = None, attempts: int = 25) -> None:
        # Для ресторанов SKU не назначаем.
        business_type = await self._get_business_type(conn, shop_id)
        if business_type != "shop":
            return

        # Генерируем SKU с повторами при конфликте уникальности.
        for _ in range(attempts):
            candidate = (sku or self._generate_sku()).strip().upper()
            if not candidate:
                candidate = self._generate_sku()
            try:
                await conn.execute(
                    "UPDATE products SET sku=? WHERE id=? AND (sku IS NULL OR sku='')",
                    (candidate, product_id),
                )
                return
            except IntegrityError:
                if sku:
                    raise
                continue
        raise RuntimeError("Не удалось назначить уникальный SKU")

    async def create(
        self,
        shop_id: int,
        category_id: int,
        name: str,
        price: float,
        description: str | None = None,
        photo_url: str | None = None,
        sku: str | None = None,
    ) -> int:
        name_norm = normalize_text(name)
        keywords_norm = build_keywords(name, description or "")
        prepared_sku = (sku or "").strip().upper() or None

        async with self.db.conn() as conn:
            cur = await conn.execute(
                """INSERT INTO products (shop_id, category_id, name, description, price, photo_url, name_norm, keywords_norm, sku)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (shop_id, category_id, name, description, price, photo_url, name_norm, keywords_norm, prepared_sku),
            )
            product_id = int(cur.lastrowid)
            if prepared_sku is None:
                await self._reserve_sku(conn, shop_id=shop_id, product_id=product_id)
            await conn.commit()
            return product_id

    async def update(self, product_id: int, name: str | None = None, description: str | None = None,
                     price: float | None = None, is_active: bool | None = None) -> None:
        fields = []
        params = []
        if name is not None:
            fields.append("name=?"); params.append(name)
            fields.append("name_norm=?"); params.append(normalize_text(name))
        if description is not None:
            fields.append("description=?"); params.append(description)
        if price is not None:
            fields.append("price=?"); params.append(price)
        if is_active is not None:
            fields.append("is_active=?"); params.append(1 if is_active else 0)

        if not fields:
            return

        if name is not None or description is not None:
            base_name = name
            base_desc = description
            if base_name is None or base_desc is None:
                async with self.db.conn() as conn:
                    cur = await conn.execute(
                        "SELECT name, description FROM products WHERE id=?",
                        (product_id,),
                    )
                    row = await cur.fetchone()
                    if row:
                        if base_name is None:
                            base_name = row["name"]
                        if base_desc is None:
                            base_desc = row["description"] or ""
            fields.append("keywords_norm=?")
            params.append(build_keywords(base_name or "", base_desc or ""))

        params.append(product_id)
        q = "UPDATE products SET " + ", ".join(fields) + " WHERE id=?"

        async with self.db.conn() as conn:
            await conn.execute(q, params)
            await conn.commit()

    async def list_by_category(self, category_id: int, active_only: bool = True) -> Sequence[dict]:
        q = "SELECT * FROM products WHERE category_id=?"
        params = [category_id]
        if active_only:
            q += " AND is_active=1"
        q += " ORDER BY id DESC"

        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
   
    async def list_by_category_for_shop(
        self,
        shop_id: int,
        category_id: int,
        active_only: bool = True,
    ) -> list[dict]:
        q = """
        SELECT *
        FROM products
        WHERE shop_id = ?
          AND category_id = ?
        """
        params = [shop_id, category_id]

        if active_only:
            q += " AND is_active = 1"
    
        q += " ORDER BY id ASC"
    
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


    async def get(self, product_id: int) -> Optional[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT * FROM products WHERE id=?", (product_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_by_sku(self, shop_id: int, sku: str) -> Optional[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT * FROM products WHERE shop_id=? AND sku=?",
                (shop_id, (sku or "").strip().upper()),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_by_sku_any(self, sku: str) -> Optional[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT * FROM products WHERE sku=? LIMIT 1",
                ((sku or "").strip().upper(),),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def find_by_natural_key(self, shop_id: int, category_id: int, name_norm: str) -> Optional[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT * FROM products WHERE shop_id=? AND category_id=? AND name_norm=? LIMIT 1",
                (shop_id, category_id, name_norm),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def set_sku_if_missing(self, product_id: int, sku: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                "UPDATE products SET sku=? WHERE id=? AND (sku IS NULL OR sku='')",
                ((sku or "").strip().upper(), product_id),
            )
            await conn.commit()

    async def ensure_sku(self, product_id: int, attempts: int = 25) -> Optional[str]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT id, shop_id, sku FROM products WHERE id=?", (product_id,))
            row = await cur.fetchone()
            if not row:
                return None
            if row["sku"]:
                return str(row["sku"])
            await self._reserve_sku(conn, shop_id=int(row["shop_id"]), product_id=product_id, attempts=attempts)
            cur = await conn.execute("SELECT sku FROM products WHERE id=?", (product_id,))
            updated = await cur.fetchone()
            await conn.commit()
            return str(updated["sku"]) if updated and updated["sku"] else None

    async def list_by_category_any(self, shop_id: int, category_id: int) -> Sequence[dict]:
        """Список товаров категории, включая неактивные (для админки)."""
        q = "SELECT * FROM products WHERE shop_id=? AND category_id=? ORDER BY id DESC"
        async with self.db.conn() as conn:
            cur = await conn.execute(q, (shop_id, category_id))
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def toggle_active(self, shop_id: int, product_id: int) -> Optional[bool]:
        """Переключить is_active. Возвращает новое состояние или None если товара нет."""
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT is_active FROM products WHERE shop_id=? AND id=?",
                (shop_id, product_id),
            )
            row = await cur.fetchone()
            if not row:
                return None

            new_val = 0 if int(row["is_active"]) == 1 else 1
            await conn.execute(
                "UPDATE products SET is_active=? WHERE shop_id=? AND id=?",
                (new_val, shop_id, product_id),
            )
            await conn.commit()
            return bool(new_val)

    async def search(self, shop_id: int, query: str, limit: int = 20, active_only: bool = True) -> Sequence[dict]:
        """Поиск товаров (это потом напрямую пойдёт в клиентский бот)."""
        q = "SELECT * FROM products WHERE shop_id=?"
        params = [shop_id]

        if active_only:
            q += " AND is_active=1"

        # пока простой LIKE по name/description (потом улучшим на name_norm/FTS)
        q += " AND (lower(name) LIKE ? OR lower(COALESCE(description,'')) LIKE ?)"
        like = f"%{query.strip().lower()}%"
        params.extend([like, like])

        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
