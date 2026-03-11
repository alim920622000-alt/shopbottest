import logging
import os

from aiogram import Bot
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.services.screen import show_screen

from app.db.database import Database
from app.repositories.admins_repo import AdminsRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo
from app.repositories.couriers_repo import CouriersRepo
from app.services.notification_center import show_notification_center_for_user
from app.services.courier_capacity import can_accept_order
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.services.order_card_formatter import build_courier_order_card

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


async def notify_couriers_new_order(db: Database, order_id: int, storage: BaseStorage) -> None:
    token = os.getenv("COURIER_BOT_TOKEN", "").strip()
    if not token:
        return
    online_ids = await CouriersRepo(db).list_online_ids()
    if not online_ids:
        return
    bot = Bot(token=token)
    try:
        for uid in online_ids:
            can_accept, _ = await can_accept_order(db, uid)
            if not can_accept:
                continue
            visible = await OrdersRepo(db).list_available_for_courier(uid)
            print("COURIER_NOTIFY", {
            "uid": uid,
            "order_id": order_id,
            "can_accept": can_accept,
            "visible_ids": [int(r["id"]) for r in visible],
            "available_count": len(visible),
        })
            if not any(int(r["id"]) == int(order_id) for r in visible):
                continue
            try:
                state = FSMContext(storage=storage, key=StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid))
                data = await state.get_data()
                # Сохраняем предыдущее состояние экрана курьера, чтобы можно было вернуться кнопкой «Назад».
                await state.update_data(
                    notif_return_stack=list(data.get("back_stack") or ["menu"]),
                    notif_return_views=dict(data.get("views") or {}),
                )
                available_count = len(visible)
                if available_count <= 1:
                    print("COURIER_NOTIFY_SINGLE_BRANCH", {
                        "uid": uid,
                        "order_id": order_id,
                    })
                    order = await OrdersRepo(db).get_order(int(order_id))
                    if not order:
                        continue
                    
                    items = list(await OrdersRepo(db).get_order_items(int(order_id)))
                    shop = await ShopsRepo(db).get(int(order.get("shop_id") or 0)) if order.get("shop_id") else None
                    client = await ClientProfilesRepo(db).get(int(order.get("client_user_id") or 0)) if order.get("client_user_id") else None
                    
                    order_for_card = dict(order)
                    order_for_card["shop_name"] = order_for_card.get("shop_name") or (shop or {}).get("name") or "—"
                    order_for_card["shop_phone"] = (shop or {}).get("phone") or ""
                    order_for_card["business_type"] = (shop or {}).get("business_type") or "shop"
                    order_for_card["pickup_address"] = (shop or {}).get("address") or order_for_card.get("shop_name") or "—"
                    order_for_card["delivery_address"] = (client or {}).get("address") or "—"
                    order_for_card["client_name"] = (client or {}).get("full_name") or "—"
                    order_for_card["client_phone"] = (client or {}).get("phone") or "—"
                    
                    text = build_courier_order_card("ru", order_for_card, items, show_client_block=False)
                    
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Принять доставку", callback_data=f"cr:accept:{order_id}:available:0")],
                            [
                                InlineKeyboardButton(text="🏠 Главная", callback_data="cr:home"),
                                InlineKeyboardButton(text="⬅️ Назад", callback_data="cr:back"),
                            ],
                    ])
                    await state.update_data(
                        back_stack=["view:available", "view:order"],
                        views={"available": {"page": 0}, "order": {"order_id": int(order_id), "source": "available", "page": 0}},
                    )
                    print("COURIER_NOTIFY_SINGLE_SHOW_SCREEN", {
                        "uid": uid,
                        "order_id": order_id,
                        "text": text,
                    })
                    await show_screen(
                        bot,
                        uid,
                        state,
                        db,
                        "courier",
                        text,
                        kb,
                        parse_mode="HTML",
                    )
                else:
                    rows = []
                    for row in visible[:10]:
                        oid = int(row["id"])
                        business_type = str(row.get("business_type") or "").strip().lower()
                        emoji = "🍽" if business_type == "restaurant" else "🛒"
                        shop_name = (row.get("shop_name") or "").strip() or "—"
                    
                        title = f"{emoji} Заказ #{oid} · {shop_name}"
                        if oid == int(order_id):
                            title = f"🆕 {title}"
                    
                        rows.append([
                            InlineKeyboardButton(
                                text=title,
                                callback_data=f"cr:order:{oid}:available:0"
                            )
                        ])
                    
                    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="cr:back")])
                    text = f"Появился новый заказ #{order_id}\n\nДоступные заказы"
                    await state.update_data(back_stack=["view:available"], views={"available": {"page": 0}})
                    await show_screen(
                        bot,
                        uid,
                        state,
                        db,
                        "courier",
                        text,
                        InlineKeyboardMarkup(inline_keyboard=rows),
                    )
            except Exception as e:
                print("COURIER_NOTIFY_ERROR", uid, order_id, repr(e))
                logger.warning("Не удалось отправить пуш курьеру %s по заказу %s", uid, order_id, exc_info=True)
    finally:
        await bot.session.close()
