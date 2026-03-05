from __future__ import annotations

from datetime import datetime


def business_emoji(business_type: str | None) -> str:
    return "🛒" if (business_type or "").strip().lower() == "shop" else "🍽️"


def map_status_to_ux(merchant_status: str | None, courier_status: str | None) -> tuple[str, str]:
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


def should_show_client_courier_phone(merchant_status: str | None, courier_status: str | None) -> bool:
    status_emoji, _ = map_status_to_ux(merchant_status, courier_status)
    return status_emoji in {"🚚", "📍"}


def courier_action_line(merchant_status: str | None, courier_status: str | None) -> str:
    status_emoji, _ = map_status_to_ux(merchant_status, courier_status)
    mapping = {
        "🟡": "ℹ️ Доступен для принятия",
        "⏳": "⏳ Дождитесь готовности заказа",
        "🟢": "⚠️ Заберите заказ в магазине",
        "🚚": "➡️ Доставьте заказ клиенту",
        "📍": "⚠️ Отдайте заказ клиенту и попросите 4-значный код",
        "✅": "✅ Заказ доставлен",
        "❌": "❌ Заказ отменён",
    }
    return mapping.get(status_emoji, "ℹ️ Доступен для принятия")


def admin_action_line(business_type: str | None, merchant_status: str | None, courier_status: str | None) -> str:
    status_emoji, _ = map_status_to_ux(merchant_status, courier_status)
    if status_emoji == "🟡":
        return "⚠️ Подтвердите и соберите заказ" if (business_type or "").strip().lower() == "shop" else "⚠️ Подтвердите и начните готовить заказ"
    if status_emoji == "⏳":
        return "⏳ Соберите заказ" if (business_type or "").strip().lower() == "shop" else "⏳ Заказ готовится"
    if status_emoji == "🟢":
        return "⚠️ Передайте заказ курьеру"
    if status_emoji == "🚚":
        return "➡️ Курьер доставляет заказ клиенту"
    if status_emoji == "📍":
        return "📍 Курьер прибыл к клиенту"
    if status_emoji == "✅":
        return "✅ Заказ доставлен"
    return "❌ Заказ отменён"


def format_order_hhmm(created_at: object) -> str:
    dt: datetime | None = None
    if isinstance(created_at, datetime):
        dt = created_at
    elif isinstance(created_at, str):
        try:
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    dt = datetime.strptime(created_at, fmt)
                    break
                except ValueError:
                    continue
    if not dt:
        return "--:--"
    return dt.strftime("%H:%M")
