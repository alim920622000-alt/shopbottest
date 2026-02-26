from __future__ import annotations

from app.db.database import Database


class SettingsRepo:
    def __init__(self, db: Database):
        self.db = db

    async def get(self, key: str, default: str) -> str:
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT value FROM app_settings WHERE key=?", (key,))
            row = await cur.fetchone()
            return str(row["value"]) if row else default

    async def set(self, key: str, value: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
            await conn.commit()
