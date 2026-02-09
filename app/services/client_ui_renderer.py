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
)
from app.handlers_client.orders import DONE_STATUSES, kb_order_card, kb_chat_nav_rows
from app.handlers_client.cabinet import kb_cabinet
from app.repositories.cart_repo import CartRepo
from app.repositories.categories_repo import CategoriesRepo
from app.repositories.chat_repo import ChatRepo
from app.repositories.client_profiles_repo import ClientProfilesRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.products_repo import ProductsRepo
from app.repositories.shops_repo import ShopsRepo
from app.services.chat_ui import PAGE_SIZE, build_chat_screen_kb, build_chat_screen_text, calc_total_pages
from app.services.notification_center import build_client_center_payload, build_client_messages_payload


async def _render_main() -> tuple[str, InlineKeyboardMarkup | None]:
    return "Выберите раздел:", kb_client_main()


async def render_client_screen(db: Database, state: FSMContext) -> tuple[str, InlineKeyboardMarkup | None]:
    data = await state.get_data()
    screen = data.get("ui_screen")
    payload = data.get("ui_payload") or {}
    user_id = data.get("user_id")

    if screen == "order_menu":
        return "Что будем заказывать?", kb_order_menu()

    if screen in ("shops", "restaurants"):
        business_type = "shop" if screen == "shops" else "restaurant"
        items = await ShopsRepo(db).list_active(business_type=business_type)
        if not items:
            text = "Магазинов пока нет." if business_type == "shop" else "Ресторанов пока нет."
            return text, kb_back("order_menu")
        return (
            "Выберите магазин:" if business_type == "shop" else "Выберите ресторан:",
            kb_shops_list(items, business_type),
        )

    if screen == "categories":
        shop_id = int(payload.get("shop_id") or 0)
        kind = (payload.get("kind") or "shop").strip()
        categories = await CategoriesRepo(db).list_for_shop(shop_id, active_only=True)
        if not categories:
            return "Категорий пока нет.", kb_back(f"{kind}_list")
        title = "Категории магазина:" if kind == "shop" else "Категории ресторана:"
        return title, kb_categories_list(categories, kind, shop_id)

    if screen == "products":
        shop_id = int(payload.get("shop_id") or 0)
        category_id = int(payload.get("category_id") or 0)
        kind = payload.get("kind") or "shop"
        products = await ProductsRepo(db).list_by_category_for_shop(shop_id, category_id, active_only=True)
        if not products:
            back_target = f"categories:{kind}:{shop_id}"
            return "В этой категории пока нет товаров.", kb_back(back_target)
        kb = kb_products_list_shop(products, shop_id, category_id) if kind == "shop" else kb_products_list(products, shop_id, category_id)
        return "Список товаров:", kb

    if screen == "product_card":
        product_id = int(payload.get("product_id") or 0)
        product = await ProductsRepo(db).get(product_id)
        if not product:
            return "Товар не найден.", kb_back("order_menu")
        text = f"{product['name']}\n\nЦена: {product['price']}\n"
        if product.get("description"):
            text += f"\nОписание: {product['description']}\n"
        return text, kb_product_card(product_id=product_id, shop_id=product["shop_id"], category_id=product["category_id"])

    if screen == "product_card_shop":
        shop_id = int(payload.get("shop_id") or 0)
        sku = (payload.get("sku") or "").strip().upper()
        product = await ProductsRepo(db).get_by_sku(shop_id=shop_id, sku=sku)
        if not product:
            return "Товар не найден.", kb_back("order_menu")
        text = f"{product['name']}\n\nЦена: {product['price']}\n"
        if product.get("description"):
            text += f"\nОписание: {product['description']}\n"
        return text, kb_product_card_shop(shop_id=shop_id, category_id=product["category_id"], sku=sku)

    if screen == "cart_menu":
        return "Выберите корзину:", kb_cart_menu()

    if screen == "cart":
        if not user_id:
            return await _render_main()
        business_type = payload.get("business_type")
        back_target = payload.get("back_target")
        items = await CartRepo(db).list_items(int(user_id), business_type=business_type)
        if not items:
            return "Корзина пуста.", kb_cart_empty(back_target)
        title = "🧺 Корзина"
        if business_type == "shop":
            title = "🧺 Корзина магазинов"
        elif business_type == "restaurant":
            title = "🧺 Корзина ресторанов"
        total = sum(float(i["price"]) * int(i["quantity"]) for i in items)
        lines = [f"{title}:"]
        for i in items:
            lines.append(f"- {i['name']} x{i['quantity']} = {float(i['price']) * int(i['quantity'])}")
        lines.append(f"\nИтого: {total}")
        return "\n".join(lines), kb_cart(items, back_target)

    if screen in ("orders", "history"):
        if not user_id:
            return await _render_main()
        statuses = DONE_STATUSES if screen == "history" else None
        rows = await OrdersRepo(db).list_for_client(int(user_id), statuses=statuses)
        if not rows:
            text = "История заказов пуста." if screen == "history" else "Заказов пока нет."
            back = kb_back("order_menu") if screen == "history" else kb_client_main()
            return text, back
        order_ids = [int(r["id"]) for r in rows]
        title = "История заказов:" if screen == "history" else "Ваши заказы:"
        back_target = "order_menu" if screen == "history" else "main"
        return title, kb_orders_list(order_ids, back_target=back_target)

    if screen == "order_card":
        order_id = int(payload.get("order_id") or 0)
        if not user_id:
            return await _render_main()
        orders = OrdersRepo(db)
        order = await orders.get_order(order_id)
        if not order or int(order["client_user_id"]) != int(user_id):
            return "Заказ не найден.", kb_client_main()
        items = await orders.get_order_items(order_id)
        shop = await ShopsRepo(db).get(int(order["shop_id"]))
        shop_name = shop["name"] if shop else f"#{order['shop_id']}"
        lines = [
            f"Заказ #{order['id']}",
            f"Точка: {shop_name}",
            f"Статус: {order['status']}",
            f"Сумма: {order['total_amount']}",
            "",
            "Состав:",
        ]
        for it in items:
            lines.append(f"- {it['name']} x{it['quantity']} = {it['price_at_moment']}")
        back_cb = "c:history" if order["status"] in DONE_STATUSES else "c:orders"
        return "\n".join(lines), kb_order_card(order_id, back_cb)

    if screen == "chat_list":
        if not user_id:
            return await _render_main()
        order_ids = await ChatRepo(db).list_order_ids_with_chat(user_id=int(user_id))
        if not order_ids:
            return "Активных чатов нет.", kb_client_main()
        return "Чаты по заказам:", kb_chat_orders(order_ids, "c")

    if screen == "chat":
        order_id = int(payload.get("order_id") or data.get("chat_order_id") or 0)
        back_target = payload.get("back_target") or data.get("chat_back_target")
        orders = OrdersRepo(db)
        order = await orders.get_order(order_id)
        shop_info = await ShopsRepo(db).get(int(order["shop_id"])) if order else None
        business_type = shop_info["business_type"] if shop_info else "shop"
        chat = ChatRepo(db)
        total_messages = await chat.count_messages(order_id)
        total_pages = max(1, calc_total_pages(total_messages, PAGE_SIZE))
        page = int(payload.get("page") or data.get("chat_page") or total_pages)
        page = max(1, min(page, total_pages))
        offset = (total_pages - page) * PAGE_SIZE
        messages = await chat.list_messages(order_id, limit=PAGE_SIZE, offset=offset)
        text = build_chat_screen_text(order_id, messages, False, business_type)
        kb = build_chat_screen_kb(order_id, page, total_pages, "c", kb_chat_nav_rows(order_id, back_target))
        return text, kb

    if screen == "notif_center":
        if not user_id:
            return await _render_main()
        return await build_client_center_payload(db, int(user_id))

    if screen == "notif_messages":
        if not user_id:
            return await _render_main()
        page = int(payload.get("page") or 1)
        return await build_client_messages_payload(db, int(user_id), page)

    if screen == "cabinet":
        if not user_id:
            return await _render_main()
        profile = await ClientProfilesRepo(db).get(int(user_id))
        full_name = profile["full_name"] if profile else ""
        phone = profile["phone"] if profile else ""
        address = profile["address"] if profile else ""
        text = (
            "👤 Кабинет\n\n"
            f"ФИО: {full_name or '—'}\n"
            f"Телефон: {phone or '—'}\n"
            f"Адрес: {address or '—'}"
        )
        return text, kb_cabinet()

    return await _render_main()
