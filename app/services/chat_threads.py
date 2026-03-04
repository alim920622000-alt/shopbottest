from __future__ import annotations

# Потоки чатов в БД. Значения строк не меняем для существующих потоков.
THREAD_MERCHANT_CLIENT = "merchant"
THREAD_MERCHANT_COURIER = "courier"
THREAD_COURIER_CLIENT = "courier_client"


def normalize_thread_for_actor(actor_role: str, thread: str | None) -> str:
    """Возвращает корректный поток для роли интерфейса.

    Для client/courier сохраняем обратную совместимость: старое значение
    "courier" трактуем как поток courier↔client.
    """
    value = (thread or "").strip()
    if actor_role in {"client", "courier"}:
        if value in {THREAD_MERCHANT_CLIENT, THREAD_COURIER_CLIENT}:
            return value
        if value == THREAD_MERCHANT_COURIER:
            return THREAD_COURIER_CLIENT
        return THREAD_MERCHANT_CLIENT
    if actor_role == "merchant":
        if value in {THREAD_MERCHANT_CLIENT, THREAD_MERCHANT_COURIER}:
            return value
        return THREAD_MERCHANT_CLIENT
    return THREAD_MERCHANT_CLIENT

