from __future__ import annotations

from app.db.database import Database


class ZonesRepo:
    def __init__(self, db: Database):
        self.db = db

    async def list_active(self, *, limit: int = 20, offset: int = 0) -> list[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT * FROM zones WHERE is_active=1 ORDER BY id ASC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def count_active(self) -> int:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT COUNT(*) AS cnt FROM zones WHERE is_active=1")
            row = await cur.fetchone()
            return int(row["cnt"]) if row else 0

    async def list_for_courier(self, courier_user_id: int) -> set[int]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT zone_id FROM courier_zones WHERE courier_user_id=?", (courier_user_id,))
            rows = await cur.fetchall()
            return {int(r["zone_id"]) for r in rows}

    async def toggle_for_courier(self, courier_user_id: int, zone_id: int) -> None:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT 1 FROM courier_zones WHERE courier_user_id=? AND zone_id=?",
                (courier_user_id, zone_id),
            )
            row = await cur.fetchone()
            if row:
                await conn.execute(
                    "DELETE FROM courier_zones WHERE courier_user_id=? AND zone_id=?",
                    (courier_user_id, zone_id),
                )
            else:
                await conn.execute(
                    "INSERT INTO courier_zones (courier_user_id, zone_id) VALUES (?, ?)",
                    (courier_user_id, zone_id),
                )
            await conn.commit()
