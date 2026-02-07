from __future__ import annotations

from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware

from app.db.database import Database
from app.i18n.client.translator import t as translate
from app.repositories.client_user_settings_repo import ClientUserSettingsRepo


class ClientI18nMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        db: Database = data["db"]
        from_user = data.get("event_from_user") or getattr(event, "from_user", None)
        locale = "ru"
        if from_user is not None:
            repo = ClientUserSettingsRepo(db)
            stored_locale = await repo.get_locale(from_user.id)
            if stored_locale:
                locale = stored_locale
            else:
                language_code = (from_user.language_code or "").lower()
                if language_code.startswith("ru"):
                    locale = "ru"
                elif language_code.startswith("uz"):
                    locale = "uz"
                else:
                    locale = "ru"
                await repo.set_locale(from_user.id, locale)

        data["locale"] = locale
        data["t"] = translate
        return await handler(event, data)
