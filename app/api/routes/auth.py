from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.api.schemas import TelegramAuthRequest, TokenResponse
from app.api.security import create_access_token
from app.db.database import Database
from app.handlers_admin_restaurant.utils import get_admin_restaurant_ids
from app.handlers_admin_shop.utils import get_admin_shop_ids

router = APIRouter(prefix="/auth", tags=["auth"])


async def _resolve_role(db: Database, user_id: int) -> str:
    shop_ids = await get_admin_shop_ids(db, user_id)
    if shop_ids:
        return "admin_shop"
    restaurant_ids = await get_admin_restaurant_ids(db, user_id)
    if restaurant_ids:
        return "admin_restaurant"
    return "client"


@router.post("/telegram", response_model=TokenResponse)
async def auth_by_telegram(payload: TelegramAuthRequest, db: Database = Depends(get_db)) -> TokenResponse:
    role = await _resolve_role(db, payload.telegram_user_id)
    db_role = "admin" if role in {"admin_shop", "admin_restaurant"} else "client"

    async with db.conn() as conn:
        await conn.execute(
            """
            INSERT INTO users(user_id, role)
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET role=excluded.role
            """,
            (payload.telegram_user_id, db_role),
        )
        await conn.commit()

    token = create_access_token({"sub": payload.telegram_user_id, "role": role})
    return TokenResponse(access_token=token)
