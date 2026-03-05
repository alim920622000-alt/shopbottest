from __future__ import annotations

from typing import Optional
from app.db.database import Database
from app.i18n.client.translator import _normalize_locale


class ClientProfilesRepo:
    def __init__(self, db: Database):
        self.db = db

    async def ensure_profile(self, user_id: int) -> None:
        """Гарантирует существование профиля клиента с locale по умолчанию."""
        async with self.db.conn() as conn:
            await conn.execute(
                """
                INSERT INTO client_profiles(user_id, full_name, phone, address, locale)
                VALUES (?, '', '', '', 'ru')
                ON CONFLICT(user_id) DO NOTHING
                """,
                (user_id,),
            )
            await conn.commit()

    async def get(self, user_id: int) -> Optional[dict]:
        await self.ensure_profile(user_id)
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT user_id, full_name, phone, address, locale FROM client_profiles WHERE user_id=?",
                (user_id,),
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_locale(self, user_id: int) -> str:
        await self.ensure_profile(user_id)
        async with self.db.conn() as conn:
            cur = await conn.execute("SELECT locale FROM client_profiles WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return _normalize_locale(row["locale"] if row else "ru")

    async def set_locale(self, user_id: int, locale: str) -> None:
        await self.ensure_profile(user_id)
        norm_locale = _normalize_locale(locale)
        async with self.db.conn() as conn:
            await conn.execute("UPDATE client_profiles SET locale=? WHERE user_id=?", (norm_locale, user_id))
            await conn.commit()

    async def upsert(
        self,
        user_id: int,
        full_name: str | None = None,
        phone: str | None = None,
        address: str | None = None,
    ) -> None:
        await self.ensure_profile(user_id)
        async with self.db.conn() as conn:
            cur = await conn.execute(
                "SELECT user_id, full_name, phone, address FROM client_profiles WHERE user_id=?",
                (user_id,),
            )
            row = await cur.fetchone()
            if row:
                new_full_name = full_name if full_name is not None else row["full_name"]
                new_phone = phone if phone is not None else row["phone"]
                new_address = address if address is not None else row["address"]
                await conn.execute(
                    """
                    UPDATE client_profiles
                    SET full_name=?, phone=?, address=?
                    WHERE user_id=?
                    """,
                    (new_full_name, new_phone, new_address, user_id),
                )
            await conn.commit()
