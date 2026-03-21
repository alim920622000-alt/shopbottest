from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.api.deps import get_current_user, get_db
from app.db.database import Database
from app.repositories.client_profiles_repo import ClientProfilesRepo

router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileResponse(BaseModel):
    user_id: int
    full_name: str
    phone: str
    address: str
    locale: str


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> ProfileResponse:
    repo = ClientProfilesRepo(db)
    profile = await repo.get(user.user_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль не найден")
    return ProfileResponse(**profile)


@router.patch("", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> ProfileResponse:
    repo = ClientProfilesRepo(db)
    await repo.upsert(
        user_id=user.user_id,
        full_name=payload.full_name,
        phone=payload.phone,
        address=payload.address,
    )
    profile = await repo.get(user.user_id)
    return ProfileResponse(**profile)
