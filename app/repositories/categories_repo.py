from __future__ import annotations

from typing import Optional, Sequence

from app.db.database import Database
from app.repositories.shops_repo import ShopsRepo
from app.services.search_utils import normalize_text


class CategoriesRepo:
    def __init__(self, db: Database):
        self.db = db

    async def create(
        self,
        shop_id: int,
        name_ru: str,
        name_uz: str | None = None,
        name_tj: str | None = None,
        sort: int = 0,
    ) -> int:
        shop = await ShopsRepo(self.db).get(shop_id)
        if not shop:
            raise ValueError(f"Shop not found: {shop_id}")
    
        business_type = shop["business_type"]
        name_norm = normalize_text(name_ru)
    
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT id FROM categories WHERE business_type=? AND name_norm=?",
                (business_type, name_norm),
            )
            row = await cur.fetchone()
            if row:
                return int(row["id"])
    
            cur = await conn.execute(
                """
                INSERT INTO categories
                (business_type, name, name_ru, name_uz, name_tj, name_norm, sort)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    business_type,
                    name_ru,
                    name_ru,
                    name_uz,
                    name_tj,
                    name_norm,
                    sort,
                ),
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


    async def count_for_business_type(self, business_type: str, active_only: bool = True) -> int:
        q = "SELECT COUNT(*) AS cnt FROM categories WHERE business_type=?"
        params = [business_type]
        if active_only:
            q += " AND is_active=1"
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_for_business_type_page(
        self,
        business_type: str,
        *,
        limit: int,
        offset: int,
        active_only: bool = True,
    ) -> Sequence[dict]:
        q = "SELECT * FROM categories WHERE business_type=?"
        params = [business_type]
        if active_only:
            q += " AND is_active=1"
        q += " ORDER BY sort ASC, id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def count_for_shop(self, shop_id: int, active_only: bool = True) -> int:
        shop = await ShopsRepo(self.db).get(shop_id)
        if not shop:
            return 0
        business_type = shop["business_type"]
        q = """
        SELECT COUNT(*) AS cnt
        FROM categories c
        WHERE c.business_type=?
          AND EXISTS (
            SELECT 1
            FROM products p
            WHERE p.shop_id=?
              AND p.category_id=c.id
          )
        """
        params = [business_type, shop_id]
        if active_only:
            q += " AND c.is_active=1"
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_for_shop_page(
        self,
        shop_id: int,
        *,
        limit: int,
        offset: int,
        active_only: bool = True,
    ) -> Sequence[dict]:
        shop = await ShopsRepo(self.db).get(shop_id)
        if not shop:
            return []

        business_type = shop["business_type"]

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
        params = [business_type, shop_id]

        if active_only:
            q += " AND c.is_active=1"

        q += " ORDER BY c.sort ASC, c.id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def list_for_shop(self, shop_id: int, active_only: bool = True) -> Sequence[dict]:
        """
        Для клиентского UI: показываем только категории, где есть товары конкретного shop_id,
        но категории берём из общего списка по business_type.
        """
        shop = await ShopsRepo(self.db).get(shop_id)
        if not shop:
            return []

        business_type = shop["business_type"]

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
        params = [business_type, shop_id]

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
