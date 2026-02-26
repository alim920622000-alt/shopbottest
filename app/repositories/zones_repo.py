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

    async def list_all(self) -> list[dict]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT * FROM zones ORDER BY is_active DESC, name COLLATE NOCASE ASC")
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def create(self, name: str) -> int:
        async with self.db.conn() as conn:
            cur = await conn.execute("INSERT INTO zones (name, is_active) VALUES (?, 1)", (name.strip(),))
            await conn.commit()
            return int(cur.lastrowid)

    async def rename(self, zone_id: int, name: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute("UPDATE zones SET name=? WHERE id=?", (name.strip(), zone_id))
            await conn.commit()

    async def set_active(self, zone_id: int, is_active: bool) -> None:
        async with self.db.conn() as conn:
            await conn.execute("UPDATE zones SET is_active=? WHERE id=?", (1 if is_active else 0, zone_id))
            if not is_active:
                await conn.execute("DELETE FROM courier_zones WHERE zone_id=?", (zone_id,))
            await conn.commit()

    async def get(self, zone_id: int) -> dict | None:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT * FROM zones WHERE id=?", (zone_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

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
