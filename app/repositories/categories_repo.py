from __future__ import annotations

from typing import Optional, Sequence

from app.db.database import Database
from app.repositories.shops_repo import ShopsRepo
from app.services.search_utils import normalize_text


class CategoriesRepo:
    def __init__(self, db: Database):
        self.db = db

    async def create(self, shop_id: int, name: str, sort: int = 0) -> int:
        name_norm = normalize_text(name)
        shop = await ShopsRepo(self.db).get(shop_id)
        if not shop:
            raise ValueError(f"Магазин/ресторан с id={shop_id} не найден")

        business_type = shop["business_type"]

        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT id FROM categories WHERE business_type=? AND name_norm=?",
                (business_type, name_norm),
            )
            existing = await cur.fetchone()
            if existing:
                return int(existing["id"])

            cur = await conn.execute(
                "INSERT INTO categories (business_type, name, name_norm, sort) VALUES (?, ?, ?, ?)",
                (business_type, name, name_norm, sort),
            )
            await conn.commit()
            return int(cur.lastrowid)

    async def rename(self, category_id: int, new_name: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                "UPDATE categories SET name=?, name_norm=? WHERE id=?",
                (new_name, normalize_text(new_name), category_id),
            )
            await conn.commit()

    async def set_active(self, category_id: int, is_active: bool) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                "UPDATE categories SET is_active=? WHERE id=?",
                (1 if is_active else 0, category_id),
            )
            await conn.commit()

    async def list_for_business_type(self, business_type: str, active_only: bool = True) -> Sequence[dict]:
        q = "SELECT * FROM categories WHERE business_type=?"
        params = [business_type]
        if active_only:
            q += " AND is_active=1"
        q += " ORDER BY sort ASC, id ASC"

        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_for_shop(self, shop_id: int, active_only: bool = True) -> Sequence[dict]:
        shop = await ShopsRepo(self.db).get(shop_id)
        if not shop:
            return []

        q = """
            SELECT c.*
            FROM categories c
            WHERE c.business_type=?
              AND EXISTS (
                SELECT 1
                FROM products p
                WHERE p.shop_id=?
                  AND p.category_id=c.id
              )
        """
        params = [shop["business_type"], shop_id]
        if active_only:
            q += " AND c.is_active=1"
        q += " ORDER BY c.sort ASC, c.id ASC"

        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get(self, category_id: int) -> Optional[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT * FROM categories WHERE id=?", (category_id,))
            row = await cur.fetchone()
            return dict(row) if row else None
