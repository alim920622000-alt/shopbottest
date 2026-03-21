from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_db
from app.api.schemas import LogoutRequest, RefreshTokenRequest, TelegramAuthRequest, TelegramWidgetRequest, TokenResponse
from app.api.security import (
    JWT_EXPIRE_SECONDS,
    REFRESH_TOKEN_EXPIRE_SECONDS,
    create_access_token,
    create_refresh_token,
)
from app.db.database import Database
from app.handlers_admin_restaurant.utils import get_admin_restaurant_ids
from app.handlers_admin_shop.utils import get_admin_shop_ids

router = APIRouter(prefix="/auth", tags=["auth"])


def _verify_telegram_widget(data: dict) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    received_hash = data.get("hash", "")
    auth_date = int(data.get("auth_date", 0))

    # Проверяем что данные не старше 24 часов
    if time.time() - auth_date > 86400:
        return False

    # Строим строку для проверки
    check_fields = {k: v for k, v in data.items() if k != "hash"}
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_fields.items()))

    # Вычисляем секретный ключ
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_hash, received_hash)


async def _resolve_role(db: Database, user_id: int) -> str:
    shop_ids = await get_admin_shop_ids(db, user_id)
    if shop_ids:
        return "admin_shop"
    restaurant_ids = await get_admin_restaurant_ids(db, user_id)
    if restaurant_ids:
        return "admin_restaurant"
    return "client"


async def _issue_tokens(db: Database, telegram_user_id: int, first_name: str = "", username: str = "") -> TokenResponse:
    role = await _resolve_role(db, telegram_user_id)
    db_role = "admin" if role in {"admin_shop", "admin_restaurant"} else "client"
    refresh_token = create_refresh_token()
    expires_at = datetime.utcnow() + timedelta(seconds=REFRESH_TOKEN_EXPIRE_SECONDS)

    async with db.conn() as conn:
        await conn.execute(
            """
            INSERT INTO users(user_id, role)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role=excluded.role
            """,
            (telegram_user_id, db_role),
        )
        # Обновляем профиль если есть имя
        if first_name:
            await conn.execute(
                """
                INSERT INTO client_profiles(user_id, full_name)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name
                """,
                (telegram_user_id, first_name),
            )
        await conn.execute(
            """
            INSERT INTO refresh_tokens(user_id, token, expires_at, revoked)
            VALUES (?, ?, ?, 0)
            """,
            (telegram_user_id, refresh_token, expires_at),
        )
        await conn.commit()

    access_token = create_access_token({"sub": telegram_user_id, "role": role})
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_in=JWT_EXPIRE_SECONDS)


@router.post("/telegram-widget", response_model=TokenResponse)
async def auth_telegram_widget(payload: TelegramWidgetRequest, db: Database = Depends(get_db)) -> TokenResponse:
    """Вход через Telegram Login Widget — с проверкой подписи."""
    data = payload.dict()
    if not _verify_telegram_widget(data):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверная подпись Telegram")
    return await _issue_tokens(
        db=db,
        telegram_user_id=payload.id,
        first_name=payload.first_name or "",
        username=payload.username or "",
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: TelegramAuthRequest, db: Database = Depends(get_db)) -> TokenResponse:
    return await _issue_tokens(db=db, telegram_user_id=payload.telegram_user_id)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(payload: RefreshTokenRequest, db: Database = Depends(get_db)) -> TokenResponse:
    async with db.conn() as conn:
        cur = await conn.execute(
            "SELECT user_id, expires_at, revoked FROM refresh_tokens WHERE token=?",
            (payload.refresh_token,),
        )
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh токен не найден")
    if int(row["revoked"]) == 1:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh токен отозван")

    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at <= datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Срок действия refresh токена истёк")

    user_id = int(row["user_id"])
    role = await _resolve_role(db, user_id)
    access_token = create_access_token({"sub": user_id, "role": role})
    return TokenResponse(access_token=access_token, refresh_token=payload.refresh_token, expires_in=JWT_EXPIRE_SECONDS)


@router.post("/logout")
async def logout(payload: LogoutRequest, db: Database = Depends(get_db)) -> dict[str, bool]:
    async with db.conn() as conn:
        await conn.execute("UPDATE refresh_tokens SET revoked=1 WHERE token=?", (payload.refresh_token,))
        await conn.commit()
    return {"ok": True}
