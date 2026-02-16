from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RoleType = Literal["client", "admin_shop", "admin_restaurant"]
BusinessType = Literal["shop", "restaurant"]


class TelegramAuthRequest(BaseModel):
    telegram_user_id: int = Field(gt=0)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CursorPage(BaseModel):
    items: list[dict]
    next_cursor: str | None


class OrderItemCreate(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class CreateOrderRequest(BaseModel):
    shop_id: int = Field(gt=0)
    comment: str = ""
    fulfillment_type: str = "courier"
    items: list[OrderItemCreate] | None = None


class SendChatMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
