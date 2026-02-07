# Client bot учун барча матнлар (Ўзбек тили, кириллица)
# Эслатма: агар калит топилмаса, RU fallback бўлиши керак (translator.py).

TEXTS: dict[str, str] = {
    # Асосий меню
    "main.order": "🛍 Буюртма",
    "main.orders": "📦 Буюртмалар",
    "main.chat": "💬 Чат",
    "main.cabinet": "👤 Кабинет",

    # "Буюртма" менюси
    "order_menu.shops": "🛒 Дўконлар",
    "order_menu.restaurants": "🍽 Ресторанлар",
    "order_menu.cart": "🧺 Сават",
    "order_menu.history": "🕓 Тарих",
    "nav.home": "🏠 Бош саҳифа",

    # Навигация
    "nav.back": "🔙 Орқага",
    "nav.home_alt": "🏠 Бош саҳифа",
    "nav.to_main": "🏠 Асосий меню",

    # Қидирув
    "search.open_inline": "🔎 Inline очиш",
    "search.search": "🔎 Қидирув",
    "search.at_search": "🔎 @Қидирув",

    # Маҳсулот карточкаси
    "product.add_to_cart": "➕ Саватга қўшиш",

    # Сават
    "cart.checkout": "🧾 Буюртма бериш",
    "cart.qty_suffix": "дона",
    "cart.del_item_tpl": "❌ Ўчириш: {name}",

    # Буюртмани расмийлаштириш
    "checkout.choose_shop_tpl": "ID {shop_id} нуқтага буюртма бериш",
    "checkout.confirm": "✅ Тасдиқлаш",

    # Сават тури бўйича
    "cart_menu.shop": "🛒 Дўкон савати",
    "cart_menu.restaurant": "🍽 Ресторан савати",

    # Буюртмалар / чатлар рўйхати
    "orders.item_tpl": "Буюртма №{order_id}",

    # Буюртма карточкаси
    "order_card.chat": "💬 Буюртма бўйича чат",

    # Кабинет
    "cabinet.edit_name": "✏️ Исм-фамилия",
    "cabinet.edit_phone": "📞 Телефон",
    "cabinet.edit_address": "📍 Манзил",
}
