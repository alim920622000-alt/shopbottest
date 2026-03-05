from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from html import escape

from app.i18n.client.translator import t
from app.services.order_statuses import compose_client_status_key


RECEIPT_WIDTH = 34


def _business_emoji(business_type: str | None) -> str:
    return "🍽️" if str(business_type or "").strip().lower() == "restaurant" else "🛒"


def _money(value: object) -> str:
    try:
        return f"{Decimal(str(value or 0)):.2f}"
    except (InvalidOperation, ValueError):
        return str(value or 0)


def _time_hhmm(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    if isinstance(value, str) and len(value) >= 16 and value[10] in {" ", "T"}:
        return value[11:16]
    return ""


def _dotted(left: str, right: str) -> str:
    dots = max(1, RECEIPT_WIDTH - len(left) - len(right))
    return f"{left}{'.' * dots}{right}"


def build_receipt(items: list[dict], total: object) -> str:
    # Единый рендер чека через pre.
    lines = ["<pre>", "--------------------------------"]
    for item in items:
        qty = int(item.get("quantity") or 0)
        name = escape(str(item.get("name") or "—"))
        price = f"{_money(item.get('price_at_moment'))} с."
        lines.append(_dotted(f"{qty} x {name} ", price))
    lines.append("--------------------------------")
    lines.append(_dotted("ИТОГО ", f"{_money(total)} с."))
    lines.append("</pre>")
    return "\n".join(lines)


def build_client_order_card(locale: str, order: dict, items: list[dict], shop_name: str, shop_phone: str = "") -> str:
    # Карточка клиента.
    emoji = _business_emoji(order.get("business_type"))
    status = t(locale, compose_client_status_key(order.get("merchant_status"), order.get("courier_status")))
    header = f"{emoji} Заказ #{order.get('id')}  ({status})"
    hhmm = _time_hhmm(order.get("created_at"))
    if hhmm:
        header = f"{header}  {hhmm}"

    comment = escape(str((order.get("comment") or "").strip())) or t(locale, "checkout.comment_empty")
    merchant_status = str(order.get("merchant_status") or "").strip().lower()
    courier_status = str(order.get("courier_status") or "").strip().lower()
    courier_name = escape(str(order.get("courier_name") or "").strip())
    courier_phone = escape(str(order.get("courier_phone") or "").strip())

    lines = [
        header,
        "",
        f"{emoji} {escape(str(shop_name or '—'))}",
    ]
    if shop_phone:
        lines.append(f"📞 {escape(str(shop_phone))}")

    if merchant_status != "new":
        lines.append("")
        lines.append(f"🛵 Курьер: {courier_name or 'назначается'}")
        if courier_phone and courier_status in {"picked_up", "arrived"}:
            lines.append(f"📞 {courier_phone}")

    lines.extend(["", "💬 Комментарий", comment, "", build_receipt(items, order.get("total_amount"))])
    return "\n".join(lines)


def build_admin_order_card(locale: str, order: dict, items: list[dict], shop_name: str) -> str:
    # Карточка админа.
    emoji = _business_emoji(order.get("business_type"))
    status = t(locale, compose_client_status_key(order.get("merchant_status"), order.get("courier_status")))
    type_map = {"courier": "Доставка", "pickup": "Самовывоз", "dine_in": "В зале"}
    comment = escape(str((order.get("comment") or "").strip())) or t(locale, "checkout.comment_empty")

    lines = [
        f"{emoji} Заказ #{order.get('id')}  ({status})",
        "",
        f"{emoji} {escape(str(shop_name or '—'))}",
        "",
        f"👤 {escape(str(order.get('client_name') or '—'))}",
        f"📞 {escape(str(order.get('client_phone') or '—'))}",
        f"📍 {escape(str(order.get('client_address') or '—'))}",
        "",
        f"🚚 Тип: {type_map.get(str(order.get('fulfillment_type') or 'courier'), 'Доставка')}",
        f"🛵 Курьер: {escape(str(order.get('courier_name') or 'назначается'))}",
        f"📞 {escape(str(order.get('courier_phone') or '—'))}",
        "",
        "💬 Комментарий",
        comment,
        "",
        build_receipt(items, order.get("total_amount")),
    ]
    return "\n".join(lines)


def build_courier_order_card(locale: str, order: dict, items: list[dict], show_client_block: bool = False) -> str:
    # Карточка курьера.
    emoji = _business_emoji(order.get("business_type"))
    status = t(locale, compose_client_status_key(order.get("merchant_status"), order.get("courier_status")))
    delivery_address = escape(str(order.get("delivery_address") or "—"))

    lines = [
        f"{emoji} Заказ #{order.get('id')}  ({status})",
        "",
        f"{emoji} {escape(str(order.get('shop_name') or '—'))}",
        "",
        f"📍 Забрать: {escape(str(order.get('pickup_address') or order.get('shop_name') or '—'))}",
        "⬇️",
        f"📍 Доставить: {delivery_address}",
    ]

    if show_client_block:
        lines.extend([
            "",
            f"👤 {escape(str(order.get('client_name') or '—'))}",
            f"📞 {escape(str(order.get('client_phone') or '—'))}",
            f"📍 {delivery_address}",
        ])

    lines.extend(["", build_receipt(items, order.get("total_amount"))])
    return "\n".join(lines)
