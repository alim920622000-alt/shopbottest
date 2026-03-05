from __future__ import annotations

MERCHANT_STATUSES = {"new", "accepted", "preparing", "ready", "completed", "canceled"}
COURIER_STATUSES = {"searching", "assigned", "picked_up", "arrived", "delivered", "canceled"}


def map_from_legacy(status: str | None) -> tuple[str, str]:
    value = (status or "").strip().lower()
    mapping = {
        "new": ("new", "searching"),
        "preparing": ("preparing", "searching"),
        "ready": ("ready", "assigned"),
        "on_the_way": ("ready", "picked_up"),
        "delivered": ("completed", "delivered"),
        "finished": ("completed", "delivered"),
        "canceled": ("canceled", "canceled"),
    }
    return mapping.get(value, ("new", "searching"))


def map_to_legacy(merchant_status: str | None, courier_status: str | None) -> str:
    m = (merchant_status or "").strip().lower()
    c = (courier_status or "").strip().lower()
    if m == "canceled" or c == "canceled":
        return "canceled"
    if c == "delivered" or m == "completed":
        return "delivered"
    if c == "picked_up":
        return "on_the_way"
    if m == "ready":
        return "ready"
    if m == "preparing":
        return "preparing"
    return "new"


def compose_client_status_key(merchant_status: str | None, courier_status: str | None) -> str:
    if (merchant_status or "").strip().lower() == "canceled" or (courier_status or "").strip().lower() == "canceled":
        return "order.status.canceled"
    if (courier_status or "").strip().lower() == "arrived":
        return "order.status.arrived"
    legacy = map_to_legacy(merchant_status, courier_status)
    if legacy == "preparing":
        return "order.status.preparing"
    if legacy == "ready":
        return "order.status.ready"
    if legacy == "on_the_way":
        return "order.status.picked_up"
    if legacy == "delivered":
        return "order.status.delivered"
    return "order.status.new"


def compose_ux_status(merchant_status: str | None, courier_status: str | None) -> tuple[str, str]:
    merchant = (merchant_status or "").strip().lower()
    courier = (courier_status or "").strip().lower()
    if merchant == "canceled" or courier == "canceled":
        return "❌", "Отменён"
    if courier == "arrived":
        return "📍", "Прибыл"
    if courier == "picked_up":
        return "🚚", "В пути"
    if courier == "delivered" or merchant == "completed":
        return "✅", "Доставлен"
    if merchant == "ready":
        return "🟢", "Готово"
    if merchant in {"preparing", "accepted"}:
        return "⏳", "Готовится"
    return "🟡", "Новый"
