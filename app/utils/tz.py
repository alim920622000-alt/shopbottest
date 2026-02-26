from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("Asia/Dushanbe")

def ensure_utc(dt: datetime) -> datetime:
    # created_at из SQLite часто naive -> считаем, что это UTC
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def to_local(dt: datetime) -> datetime:
    return ensure_utc(dt).astimezone(APP_TZ)

def fmt_hm(dt: datetime) -> str:
    return to_local(dt).strftime("%H:%M")

def utcnow() -> datetime:
    # если тебе нужно "текущее время", всегда бери tz-aware UTC
    return datetime.now(timezone.utc)