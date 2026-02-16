from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, status

from app.api.security import decode_access_token
from app.db.database import Database


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    role: str


def get_db(request: Request) -> Database:
    db = getattr(request.app.state, "db", None)
    if not db:
        raise RuntimeError("Database is not initialized")
    return db


def get_token_from_header(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Отсутствует заголовок Authorization")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Ожидается Bearer токен")
    return parts[1].strip()


def get_current_user(token: str = Depends(get_token_from_header)) -> CurrentUser:
    payload = decode_access_token(token)
    user_id = int(payload.get("sub", 0))
    role = str(payload.get("role", "")).strip()
    if user_id <= 0 or role not in {"client", "admin_shop", "admin_restaurant"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректный токен")
    return CurrentUser(user_id=user_id, role=role)
