import logging
import os

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.db.database import Database
from app.repositories.admins_repo import AdminsRepo
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo

logger = logging.getLogger(__name__)


def _build_admin_keyboard(order_id: int, business_type: str) -> InlineKeyboardMarkup:
    prefix = "a" if business_type == "shop" else "r"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"#{order_id}", callback_data=f"{prefix}:order:{order_id}")],
            [
                InlineKeyboardButton(text="🏠 Главная", callback_data=f"{prefix}:home"),
                InlineKeyboardButton(text="📋 К заказам", callback_data=f"{prefix}:orders"),
            ],
        ]
    )


async def notify_admins_new_order(db: Database, order_id: int, shop_id: int) -> None:
    # Определяем тип точки, чтобы выбрать правильный админ-бот и callbacks.
    shops = ShopsRepo(db)
    shop = await shops.get(shop_id)
    if not shop:
        logger.warning("Shop %s not found for order %s", shop_id, order_id)
        return

    business_type = shop.get("business_type")
    if business_type not in ("shop", "restaurant"):
        return

    token_env = "ADMIN_SHOP_BOT_TOKEN" if business_type == "shop" else "ADMIN_RESTAURANT_BOT_TOKEN"
    token = os.getenv(token_env, "").strip()
    if not token:
        logger.warning("Admin bot token %s is empty, skip order notify", token_env)
        return

    admins = AdminsRepo(db)
    admin_ids = await admins.list_admin_user_ids(shop_id)
    if not admin_ids:
        return

    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    items = await orders.get_order_items(order_id)

    lines = [f"🔔 Новый заказ #{order_id}"]
    if order and order.get("total_amount") is not None:
        lines.append(f"Сумма: {order['total_amount']}")
    if items:
        total_qty = sum(int(i["quantity"]) for i in items)
        lines.append(f"Кол-во позиций: {total_qty}")

    if order and order.get("client_user_id"):
        profiles = ClientProfilesRepo(db)
        profile = await profiles.get(int(order["client_user_id"]))
        if profile:
            if (profile.get("full_name") or "").strip():
                lines.append(f"Клиент: {profile['full_name']}")
            if (profile.get("phone") or "").strip():
                lines.append(f"Телефон: {profile['phone']}")
            if (profile.get("address") or "").strip():
                lines.append(f"Адрес: {profile['address']}")

    text = "\n".join(lines)
    reply_markup = _build_admin_keyboard(order_id, business_type)

    bot = Bot(token=token)
    try:
        for uid in admin_ids:
            try:
                await bot.send_message(uid, text, reply_markup=reply_markup)
            except Exception:
                logger.warning(
                    "Не удалось отправить уведомление админу %s по заказу %s",
                    uid,
                    order_id,
                    exc_info=True,
                )
    finally:
        await bot.session.close()


async def notify_admins_order_canceled(db: Database, order_id: int, shop_id: int) -> None:
    shops = ShopsRepo(db)
    shop = await shops.get(shop_id)
    if not shop:
        logger.warning("Shop %s not found for order %s", shop_id, order_id)
        return

    business_type = shop.get("business_type")
    if business_type not in ("shop", "restaurant"):
        return

    token_env = "ADMIN_SHOP_BOT_TOKEN" if business_type == "shop" else "ADMIN_RESTAURANT_BOT_TOKEN"
    token = os.getenv(token_env, "").strip()
    if not token:
        logger.warning("Admin bot token %s is empty, skip order notify", token_env)
        return

    admins = AdminsRepo(db)
    admin_ids = await admins.list_admin_user_ids(shop_id)
    if not admin_ids:
        return

    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)

    lines = [f"❌ Клиент отменил заказ #{order_id}"]
    if order and order.get("total_amount") is not None:
        lines.append(f"Сумма: {order['total_amount']}")

    text = "\n".join(lines)
    reply_markup = _build_admin_keyboard(order_id, business_type)

    bot = Bot(token=token)
    try:
        for uid in admin_ids:
            try:
                await bot.send_message(uid, text, reply_markup=reply_markup)
            except Exception:
                logger.warning(
                    "Не удалось отправить уведомление админу %s по заказу %s",
                    uid,
                    order_id,
                    exc_info=True,
                )
    finally:
        await bot.session.close()
