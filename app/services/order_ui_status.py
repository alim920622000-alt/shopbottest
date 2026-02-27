from __future__ import annotations

from datetime import datetime


def _parse_created_at(value: str | None) -> int:
    if not value:
        return 0
    raw = value.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return int(datetime.strptime(raw, fmt).timestamp())
        except ValueError:
            continue
    return 0


def _normalize(value: str | None) -> str:
    return str(value or "").strip().lower()


def admin_order_status_emoji(order: dict) -> str:
    merchant_status = _normalize(order.get("merchant_status"))
    courier_status = _normalize(order.get("courier_status"))

    if merchant_status == "new":
        return "🆕"
    if courier_status == "searching":
        return "🔎"
    if courier_status == "assigned":
        return "👤"
    if merchant_status == "preparing":
        return "⏳"
    if merchant_status == "ready":
        return "📦"
    if courier_status == "picked_up":
        return "🚚"
    if courier_status == "arrived":
        return "📍"
    return "🆕"


def admin_order_sort_key(order: dict) -> tuple[int, int]:
    merchant_status = _normalize(order.get("merchant_status"))
    courier_status = _normalize(order.get("courier_status"))

    if merchant_status == "new":
        priority = 1
    elif courier_status == "searching":
        priority = 2
    elif courier_status == "assigned":
        priority = 3
    elif merchant_status == "preparing":
        priority = 4
    elif merchant_status == "ready":
        priority = 5
    elif courier_status == "picked_up":
        priority = 6
    elif courier_status == "arrived":
        priority = 7
    else:
        priority = 99

    return priority, -_parse_created_at(order.get("created_at"))


def history_order_status_emoji(order: dict) -> str:
    merchant_status = _normalize(order.get("merchant_status"))
    courier_status = _normalize(order.get("courier_status"))
    legacy_status = _normalize(order.get("status"))

    delivered = courier_status == "delivered" or merchant_status == "completed" or legacy_status == "delivered"
    canceled = courier_status == "canceled" or merchant_status == "canceled" or legacy_status == "canceled"
    if delivered:
        return "✅"
    if canceled:
        return "❌"
    return "📦"
