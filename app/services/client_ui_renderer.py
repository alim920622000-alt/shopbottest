from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_client.kb import (
    kb_back,
    kb_cart,
    kb_cart_empty,
    kb_cart_menu,
    kb_categories_list,
    kb_chat_orders,
    kb_client_main,
    kb_order_menu,
    kb_orders_list,
    kb_product_card,
    kb_product_card_shop,
    kb_products_list,
    kb_products_list_shop,
    kb_shops_list,
    kb_cabinet,
    kb_language_select,
)
from app.handlers_client.orders import DONE_STATUSES, kb_order_card, kb_chat_nav_rows
from app.i18n.client.translator import t
from app.repositories.cart_repo import CartRepo
from app.repositories.categories_repo import CategoriesRepo
from app.repositories.chat_repo import ChatRepo
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.products_repo import ProductsRepo
from app.repositories.shops_repo import ShopsRepo
from app.services.chat_ui import PAGE_SIZE, build_chat_screen_kb, build_chat_screen_text, calc_total_pages
from app.services.badges import get_unread_order_ids_for_view
from app.services.notification_center import build_client_center_payload, build_client_messages_payload
from app.services.order_chat_access import can_access_order_chat, CLOSED_STATUSES
from app.services.chat_channels import CHANNEL_CLIENT_MERCHANT, map_channel_to_legacy_thread, map_legacy_thread_to_channel
from app.services.client_main_menu import build_client_main_kb_dynamic
from app.services.order_card_formatter import build_client_order_card
from app.repositories.client_profiles_repo import ClientProfilesRepo


async def _render_main(db: Database, locale: str, user_id: int | None) -> tuple[str, InlineKeyboardMarkup | None]:
    return t(locale, "main.select_section"), await build_client_main_kb_dynamic(db, locale, user_id)


async def render_client_screen(db: Database, state: FSMContext) -> tuple[str, InlineKeyboardMarkup | None]:
    data = await state.get_data()
    screen = data.get("ui_screen")
    payload = data.get("ui_payload") or {}
    user_id = data.get("user_id")
    locale = data.get("locale") or "ru"

    if screen == "order_menu":
        return t(locale, "order_menu.prompt"), kb_order_menu(locale)

    if screen in ("shops", "restaurants"):
        business_type = "shop" if screen == "shops" else "restaurant"
        items = await ShopsRepo(db).list_active(business_type=business_type)
        if not items:
            text = t(locale, "shops.empty") if business_type == "shop" else t(locale, "restaurants.empty")
            return text, kb_back(locale, "order_menu")
        return (
            t(locale, "shops.select") if business_type == "shop" else t(locale, "restaurants.select"),
            kb_shops_list(locale, items, business_type),
        )

    if screen == "categories":
        shop_id = int(payload.get("shop_id") or 0)
        kind = (payload.get("kind") or "shop").strip()
        categories = await CategoriesRepo(db).list_for_shop(shop_id, active_only=True)
        if not categories:
            return t(locale, "categories.empty"), kb_back(locale, f"{kind}_list")
        title = t(locale, "categories.shop_title") if kind == "shop" else t(locale, "categories.restaurant_title")
        return title, kb_categories_list(locale, categories, kind, shop_id)

    if screen == "products":
        shop_id = int(payload.get("shop_id") or 0)
        category_id = int(payload.get("category_id") or 0)
        kind = payload.get("kind") or "shop"
        products = await ProductsRepo(db).list_by_category_for_shop(shop_id, category_id, active_only=True)
        if not products:
            back_target = f"categories:{kind}:{shop_id}"
            return t(locale, "products.empty"), kb_back(locale, back_target)
        kb = kb_products_list_shop(locale, products, shop_id, category_id) if kind == "shop" else kb_products_list(locale, products, shop_id, category_id)
        return t(locale, "products.list_title"), kb

    if screen == "product_card":
        product_id = int(payload.get("product_id") or 0)
        product = await ProductsRepo(db).get(product_id)
        if not product:
            return t(locale, "product.not_found"), kb_back(locale, "order_menu")
        text = f"{product['name']}\n\n{t(locale, 'product.price', price=product['price'])}\n"
        if product.get("description"):
            text += f"\n{t(locale, 'product.description', description=product['description'])}\n"
        return text, kb_product_card(locale, product_id=product_id, shop_id=product["shop_id"], category_id=product["category_id"])

    if screen == "product_card_shop":
        shop_id = int(payload.get("shop_id") or 0)
        sku = (payload.get("sku") or "").strip().upper()
        product = await ProductsRepo(db).get_by_sku(shop_id=shop_id, sku=sku)
        if not product:
            return t(locale, "product.not_found"), kb_back(locale, "order_menu")
        text = f"{product['name']}\n\n{t(locale, 'product.price', price=product['price'])}\n"
        if product.get("description"):
            text += f"\n{t(locale, 'product.description', description=product['description'])}\n"
        return text, kb_product_card_shop(locale, shop_id=shop_id, category_id=product["category_id"], sku=sku)

    if screen == "cart_menu":
        return t(locale, "cart.select"), kb_cart_menu(locale)

    if screen == "cart":
        if not user_id:
            return await _render_main(db, locale, user_id)
        business_type = payload.get("business_type")
        back_target = payload.get("back_target")
        items = await CartRepo(db).list_items(int(user_id), business_type=business_type)
        if not items:
            return t(locale, "cart.empty"), kb_cart_empty(locale, back_target)
        title = t(locale, "cart.title")
        if business_type == "shop":
            title = t(locale, "cart.title.shop")
        elif business_type == "restaurant":
            title = t(locale, "cart.title.restaurant")
        total = sum(float(i["price"]) * int(i["quantity"]) for i in items)
        lines = [f"{title}:"]
        for i in items:
            lines.append(f"- {i['name']} x{i['quantity']} = {float(i['price']) * int(i['quantity'])}")
        lines.append(f"\n{t(locale, 'cart.total', total=total)}")
        return "\n".join(lines), kb_cart(locale, items, back_target)

    if screen in ("orders", "history"):
        if not user_id:
            return await _render_main(db, locale, user_id)
        statuses = DONE_STATUSES if screen == "history" else None
        rows = await OrdersRepo(db).list_for_client(int(user_id), statuses=statuses)
        if not rows:
            text = t(locale, "orders.history.empty") if screen == "history" else t(locale, "orders.empty")
            back = kb_back(locale, "order_menu") if screen == "history" else kb_client_main(locale)
            return text, back
        title = t(locale, "orders.history.title") if screen == "history" else t(locale, "orders.title")
        back_target = "order_menu" if screen == "history" else "main"
        return title, kb_orders_list(locale, rows, back_target=back_target)

    if screen == "order_card":
        order_id = int(payload.get("order_id") or 0)
        if not user_id:
            return await _render_main(db, locale, user_id)
        orders = OrdersRepo(db)
        order = await orders.get_order(order_id)
        if not order or int(order["client_user_id"]) != int(user_id):
            return t(locale, "order.not_found"), kb_client_main(locale)
        items = await orders.get_order_items(order_id)
        shop = await ShopsRepo(db).get(int(order["shop_id"]))
        shop_name = shop["name"] if shop else f"#{order['shop_id']}"
        courier = await ClientProfilesRepo(db).get(int(order.get("courier_user_id") or 0)) if order.get("courier_user_id") else None
        order_for_card = dict(order)
        order_for_card["business_type"] = (shop or {}).get("business_type") or "shop"
        order_for_card["courier_name"] = (courier or {}).get("full_name") or ""
        order_for_card["courier_phone"] = (courier or {}).get("phone") or ""
        back_cb = "c:history" if order["status"] in DONE_STATUSES else "c:orders"
        can_chat = await can_access_order_chat(db, order)
        can_repeat = str(order.get("status") or "").strip().lower() in CLOSED_STATUSES
        return build_client_order_card(locale, order_for_card, list(items), shop_name, (shop or {}).get("phone") or ""), kb_order_card(locale, order_id, back_cb, False, can_chat, can_repeat)

    if screen == "chat_list":
        if not user_id:
            return await _render_main(db, locale, user_id)
        order_ids = await ChatRepo(db).list_order_ids_with_chat(user_id=int(user_id))
        if not order_ids:
            return t(locale, "chat.none"), kb_client_main(locale)
        brief_rows = await OrdersRepo(db).list_brief_by_ids(order_ids)
        unread_order_ids = await get_unread_order_ids_for_view(db, "client", int(user_id), [int(row["id"]) for row in brief_rows])
        return t(locale, "chat.list_title"), kb_chat_orders(locale, brief_rows, "c", unread_order_ids=unread_order_ids)

    if screen == "chat":
        order_id = int(payload.get("order_id") or data.get("chat_order_id") or 0)
        back_target = payload.get("back_target") or data.get("chat_back_target")
        # Поток всегда передаём явно, чтобы при восстановлении экрана не утекали чужие переписки.
        legacy_thread = str(payload.get("thread") or "")
        channel = str(payload.get("channel") or data.get("chat_channel") or map_legacy_thread_to_channel("client", legacy_thread or "merchant") or CHANNEL_CLIENT_MERCHANT)
        thread = map_channel_to_legacy_thread("client", channel)
        orders = OrdersRepo(db)
        order = await orders.get_order(order_id)
        shop_info = await ShopsRepo(db).get(int(order["shop_id"])) if order else None
        business_type = shop_info["business_type"] if shop_info else "shop"
        chat = ChatRepo(db)
        total_messages = await chat.count_messages(order_id, channel=channel)
        total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
        page = int(payload.get("page") or data.get("chat_page") or total_pages)
        page = max(1, min(page, total_pages))
        offset = (total_pages - page) * PAGE_SIZE
        messages = await chat.list_messages(order_id, channel=channel, limit=PAGE_SIZE, offset=offset)
        text = build_chat_screen_text(
            order_id,
            messages,
            False,
            business_type,
            locale,
            "client",
            shop_name=shop_info["name"] if shop_info else None,
        )
        kb = build_chat_screen_kb(order_id, page, total_pages, "c", kb_chat_nav_rows(locale, order_id, thread, back_target))
        return text, kb

    if screen == "notif_center":
        if not user_id:
            return await _render_main(db, locale, user_id)
        return await build_client_center_payload(db, int(user_id), locale)

    if screen == "notif_messages":
        if not user_id:
            return await _render_main(db, locale, user_id)
        page = int(payload.get("page") or 1)
        return await build_client_messages_payload(db, int(user_id), page, locale)

    if screen == "cabinet":
        if not user_id:
            return await _render_main(db, locale, user_id)
        profile = await ClientProfilesRepo(db).get(int(user_id))
        full_name = profile["full_name"] if profile else ""
        phone = profile["phone"] if profile else ""
        address = profile["address"] if profile else ""
        empty_value = t(locale, "cabinet.empty_value")
        text = (
            f"{t(locale, 'cabinet.title')}\n\n"
            f"{t(locale, 'cabinet.full_name')}: {full_name or empty_value}\n"
            f"{t(locale, 'cabinet.phone')}: {phone or empty_value}\n"
            f"{t(locale, 'cabinet.address')}: {address or empty_value}"
        )
        return text, kb_cabinet(locale)

    if screen == "language_select":
        return t(locale, "language.select_title"), kb_language_select(locale)

    return await _render_main(db, locale, user_id)
