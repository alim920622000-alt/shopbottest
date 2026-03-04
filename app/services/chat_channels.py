from __future__ import annotations

CHANNEL_CLIENT_MERCHANT = "client_merchant"
CHANNEL_CLIENT_COURIER = "client_courier"
CHANNEL_MERCHANT_COURIER = "merchant_courier"

# legacy thread значения (оставлены для обратной совместимости callback/prefs)
THREAD_MERCHANT_CLIENT = "merchant"
THREAD_MERCHANT_COURIER = "courier"
THREAD_COURIER_CLIENT = "courier_client"


def map_legacy_thread_to_channel(actor_role: str, thread: str | None) -> str:
    """Преобразует старый thread в новый channel c учетом роли бота."""
    value = (thread or "").strip()
    if actor_role == "client":
        if value == "courier_client":
            return CHANNEL_CLIENT_COURIER
        return CHANNEL_CLIENT_MERCHANT
    if actor_role in {"merchant", "admin_shop", "admin_restaurant"}:
        if value == "courier":
            return CHANNEL_MERCHANT_COURIER
        return CHANNEL_CLIENT_MERCHANT
    if actor_role == "courier":
        if value == "merchant":
            return CHANNEL_MERCHANT_COURIER
        return CHANNEL_CLIENT_COURIER
    return CHANNEL_CLIENT_MERCHANT


def normalize_thread_for_actor(actor_role: str, thread: str | None) -> str:
    """Возвращает допустимый legacy-thread для роли интерфейса."""
    value = (thread or "").strip()
    if actor_role in {"client", "courier"}:
        if value in {THREAD_MERCHANT_CLIENT, THREAD_COURIER_CLIENT}:
            return value
        if value == THREAD_MERCHANT_COURIER:
            return THREAD_COURIER_CLIENT
        return THREAD_MERCHANT_CLIENT
    if actor_role in {"merchant", "admin_shop", "admin_restaurant"}:
        if value in {THREAD_MERCHANT_CLIENT, THREAD_MERCHANT_COURIER}:
            return value
        return THREAD_MERCHANT_CLIENT
    return THREAD_MERCHANT_CLIENT


def map_channel_to_legacy_thread(actor_role: str, channel: str | None) -> str:
    """Оставляет обратную совместимость callback-значений chat_thread."""
    value = (channel or "").strip()
    if actor_role == "client":
        if value == CHANNEL_CLIENT_COURIER:
            return "courier_client"
        return "merchant"
    if actor_role in {"merchant", "admin_shop", "admin_restaurant"}:
        if value == CHANNEL_MERCHANT_COURIER:
            return "courier"
        return "merchant"
    if actor_role == "courier":
        if value == CHANNEL_MERCHANT_COURIER:
            return "merchant"
        return "courier_client"
    return "merchant"
