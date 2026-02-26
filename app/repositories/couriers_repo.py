from __future__ import annotations

from app.db.database import Database


class CouriersRepo:
    def __init__(self, db: Database):
        self.db = db

    async def ensure(self, user_id: int) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                "INSERT INTO couriers (user_id, is_online, accept_all_zones) VALUES (?, 0, 1) ON CONFLICT(user_id) DO NOTHING",
                (user_id,),
            )
            await conn.commit()

    async def get(self, user_id: int) -> dict | None:
        await self.ensure(user_id)
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT * FROM couriers WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def set_online(self, user_id: int, is_online: bool) -> None:
        await self.ensure(user_id)
        async with self.db.conn() as conn:
            await conn.execute("UPDATE couriers SET is_online=? WHERE user_id=?", (1 if is_online else 0, user_id))
            await conn.commit()

    async def set_accept_all_zones(self, user_id: int, accept_all: bool) -> None:
        await self.ensure(user_id)
        async with self.db.conn() as conn:
            await conn.execute("UPDATE couriers SET accept_all_zones=? WHERE user_id=?", (1 if accept_all else 0, user_id))
            await conn.commit()

    async def list_online_ids(self) -> list[int]:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT user_id FROM couriers WHERE is_online=1")
            rows = await cur.fetchall()
            return [int(r["user_id"]) for r in rows]


    async def set_transport(self, user_id: int, transport_type: str) -> None:
        await self.ensure(user_id)
        async with self.db.conn() as conn:
            await conn.execute("UPDATE couriers SET transport_type=? WHERE user_id=?", (transport_type, user_id))
            await conn.commit()
