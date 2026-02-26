from __future__ import annotations

from app.db.database import Database
from app.repositories.orders_repo import OrdersRepo
from app.repositories.settings_repo import SettingsRepo

MODE_STRICT = 1
MODE_MEDIUM = 2
MODE_FREE = 3
FREE_MODE_LIMIT = 3


async def get_courier_capacity_mode(db: Database) -> int:
    raw_mode = await SettingsRepo(db).get("courier_capacity_mode", "1")
    try:
        mode = int(raw_mode)
    except (TypeError, ValueError):
        mode = MODE_STRICT
    if mode not in {MODE_STRICT, MODE_MEDIUM, MODE_FREE}:
        return MODE_STRICT
    return mode


async def can_accept_order(db: Database, courier_user_id: int) -> tuple[bool, str]:
    mode = await get_courier_capacity_mode(db)
    active = await OrdersRepo(db).list_active_for_courier(courier_user_id)
    active_count = len(active)

    if mode == MODE_STRICT:
        if active_count == 0:
            return True, ""
        return False, "У вас уже есть активный заказ. Завершите его перед принятием нового."

    if mode == MODE_MEDIUM:
        if active_count == 0:
            return True, ""
        if active_count >= 2:
            return False, "Достигнут лимит активных заказов (2)."
        status = str(active[0].get("courier_status") or "").strip().lower()
        if status == "arrived":
            return True, ""
        return False, "Второй заказ доступен только после статуса «Прибыл» по текущему заказу."

    if active_count >= FREE_MODE_LIMIT:
        return False, f"Достигнут лимит активных заказов ({FREE_MODE_LIMIT})."
    return True, ""
