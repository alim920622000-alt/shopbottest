from __future__ import annotations
from typing import Optional, Sequence
from app.db.database import Database


class ShopsRepo:
    def __init__(self, db: Database):
        self.db = db

    async def create_shop(self, name: str, business_type: str, phone: str | None = None,
                          address: str | None = None, about: str | None = None,
                          logo_url: str | None = None) -> int:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                """INSERT INTO shops (name, business_type, phone, address, about, logo_url)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, business_type, phone, address, about, logo_url),
            )
            await conn.commit()
            return int(cur.lastrowid)

    async def list_active(self, business_type: Optional[str] = None) -> Sequence[dict]:
        q = "SELECT * FROM shops WHERE is_active=1"
        params = []
        if business_type:
            q += " AND business_type=?"
            params.append(business_type)
        q += " ORDER BY id DESC"

        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def count_active(self, business_type: Optional[str] = None) -> int:
        q = "SELECT COUNT(*) AS cnt FROM shops WHERE is_active=1"
        params: list = []
        if business_type:
            q += " AND business_type=?"
            params.append(business_type)
        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_active_page(
        self,
        business_type: Optional[str] = None,
        *,
        limit: int,
        offset: int,
    ) -> Sequence[dict]:
        q = "SELECT * FROM shops WHERE is_active=1"
        params: list = []
        if business_type:
            q += " AND business_type=?"
            params.append(business_type)
        q += " ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with self.db.conn() as conn:
            cur = await conn.execute(q, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get(self, shop_id: int) -> Optional[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT * FROM shops WHERE id=?", (shop_id,))
            row = await cur.fetchone()
            return dict(row) if row else None
