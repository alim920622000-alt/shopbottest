import logging
import os

from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.db.database import Database
from app.repositories.admins_repo import AdminsRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo
from app.repositories.couriers_repo import CouriersRepo
from app.repositories.settings_repo import SettingsRepo
from app.services.notification_center import show_notification_center_for_user

logger = logging.getLogger(__name__)


def _format_fulfillment_type_ru(value: str | None) -> str:
    mapping = {
        "courier": "🚚 Доставка",
        "pickup": "🏬 Самовывоз",
        "dine_in": "🍽 В зале",
    }
    return mapping.get((value or "").strip(), "🚚 Доставка")


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


async def notify_admins_new_order(
    db: Database,
    order_id: int,
    shop_id: int,
    storage: BaseStorage,
) -> None:
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

    bot_kind = "admin_shop" if business_type == "shop" else "admin_restaurant"

    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)

    lines = [f"🆕 Новый заказ #{order_id}"]
    if order and order.get("total_amount") is not None:
        lines.append(f"Сумма: {order['total_amount']}")
    lines.append(f"Получение: {_format_fulfillment_type_ru(order.get('fulfillment_type') if order else None)}")
    text = "\n".join(lines)
    reply_markup = _build_admin_keyboard(order_id, business_type)

    bot = Bot(token=token)
    try:
        for uid in admin_ids:
    
            try:
                #await bot.send_message(uid, text, reply_markup=reply_markup)
                await show_notification_center_for_user(
                    bot=bot,
                    db=db,
                    bot_kind=bot_kind,
                    user_id=uid,
                    storage=storage,
                )
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


async def _courier_can_accept(db: Database, courier_user_id: int) -> bool:
    settings = SettingsRepo(db)
    mode = int(await settings.get("courier_capacity_mode", "1"))
    max_active = int(await settings.get("max_active_orders", "2"))
    active = await OrdersRepo(db).list_active_for_courier(courier_user_id)
    if mode == 1:
        return len(active) < 1
    if mode == 2:
        return len(active) < max_active
    if mode == 3:
        if len(active) == 0:
            return True
        if len(active) > 1:
            return False
        return str(active[0].get("courier_status") or "") == "arrived"
    return False


async def notify_couriers_new_order(db: Database, order_id: int) -> None:
    token = os.getenv("COURIER_BOT_TOKEN", "").strip()
    if not token:
        return
    online_ids = await CouriersRepo(db).list_online_ids()
    if not online_ids:
        return
    bot = Bot(token=token)
    try:
        for uid in online_ids:
            if not await _courier_can_accept(db, uid):
                continue
            visible = await OrdersRepo(db).list_available_for_courier(uid)
            if not any(int(r["id"]) == int(order_id) for r in visible):
                continue
            try:
                await bot.send_message(uid, f"🆕 Доступен заказ #{order_id}\nОткройте раздел 'Доступные'.")
            except Exception:
                logger.warning("Не удалось отправить пуш курьеру %s по заказу %s", uid, order_id, exc_info=True)
    finally:
        await bot.session.close()
