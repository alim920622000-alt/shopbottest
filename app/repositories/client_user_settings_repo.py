from __future__ import annotations

from typing import Optional

from app.db.database import Database


class ClientUserSettingsRepo:
    def __init__(self, db: Database):
        self.db = db

    async def get_locale(self, user_id: int) -> Optional[str]:
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT locale FROM client_user_settings WHERE user_id=?",
                (user_id,),
            )
            row = await cur.fetchone()
            return row["locale"] if row else None

    async def set_locale(self, user_id: int, locale: str) -> None:
        async with self.db.conn() as conn:
            await conn.execute(
                """
                INSERT INTO client_user_settings (user_id, locale, updated_at)
                VALUES (?, ?, DATETIME('now'))
                ON CONFLICT(user_id) DO UPDATE SET
                    locale=excluded.locale,
                    updated_at=excluded.updated_at
                """,
                (user_id, locale),
            )
            await conn.commit()
