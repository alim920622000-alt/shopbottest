import logging

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.db.database import Database
from app.repositories.admins_repo import AdminsRepo
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.repositories.orders_repo import OrdersRepo

logger = logging.getLogger(__name__)


def _build_admin_order_keyboard(order_id: int, business_type: str) -> InlineKeyboardMarkup:
    prefix = "a" if business_type == "shop" else "r"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"#{order_id}", callback_data=f"{prefix}:order:{order_id}")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data=f"{prefix}:home"),
            InlineKeyboardButton(text="📋 К заказам", callback_data=f"{prefix}:orders"),
        ],
    ])


async def notify_admins_new_order(
    *,
    bot,
    db: Database,
    order_id: int,
    shop_id: int,
    business_type: str,
) -> None:
    """Отправляет уведомления о новом заказе администраторам конкретной точки."""
    if business_type not in ("shop", "restaurant"):
        logger.warning("Неизвестный тип точки для уведомления о заказе %s: %s", order_id, business_type)
        return
    admins = AdminsRepo(db)
    admin_ids = await admins.list_admin_user_ids(shop_id)
    if not admin_ids:
        return

    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    items = await orders.get_order_items(order_id)

    total_qty = sum(int(item["quantity"]) for item in items) if items else 0
    total_amount = order.get("total_amount") if order else None

    profile = None
    if order:
        profiles = ClientProfilesRepo(db)
        profile = await profiles.get(int(order["client_user_id"]))

    lines = [f"🔔 Новый заказ #{order_id}"]
    if total_amount is not None:
        lines.append(f"Сумма: {total_amount}")
    if total_qty:
        lines.append(f"Позиций: {total_qty}")
    if profile:
        if profile.get("full_name"):
            lines.append(f"Клиент: {profile['full_name']}")
        if profile.get("phone"):
            lines.append(f"Телефон: {profile['phone']}")
        if profile.get("address"):
            lines.append(f"Адрес: {profile['address']}")

    text = "\n".join(lines)
    keyboard = _build_admin_order_keyboard(order_id, business_type)

    for admin_id in admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=keyboard)
        except Exception:
            # Ошибка отправки отдельному админу не должна мешать остальным
            logger.exception("Не удалось отправить уведомление о заказе %s админу %s", order_id, admin_id)
