# Ҳамаи матнҳои бот (Тоҷикӣ) — танҳо барои client
# Эзоҳ: агар калид нест, бояд ба RU fallback шавад (дар translator.py).

TEXTS: dict[str, str] = {
    # Менюи асосӣ
    "main.order": "🛍 Фармоиш",
    "main.orders": "📦 Фармоишҳо",
    "main.chat": "💬 Чат",
    "main.cabinet": "👤 Кабинет",

    # Менюи "Фармоиш"
    "order_menu.shops": "🛒 Мағозаҳо",
    "order_menu.restaurants": "🍽 Тарабхонаҳо",
    "order_menu.cart": "🧺 Сабад",
    "order_menu.history": "🕓 Таърих",
    "nav.home": "🏠 Асосӣ",

    # Навигатсия
    "nav.back": "🔙 Бозгашт",
    "nav.home_alt": "🏠 Асосӣ",
    "nav.to_main": "🏠 Ба менюи асосӣ",

    # Ҷустуҷӯ
    "search.open_inline": "🔎 Inline-ро кушодан",
    "search.search": "🔎 Ҷустуҷӯ",
    "search.at_search": "🔎 @Ҷустуҷӯ",

    # Корти маҳсулот
    "product.add_to_cart": "➕ Ба сабад илова кардан",

    # Сабад
    "cart.checkout": "🧾 Фармоиш додан",
    "cart.qty_suffix": "дона",
    "cart.del_item_tpl": "❌ Нест кардан: {name}",

    # Оформкунии фармоиш
    "checkout.choose_shop_tpl": "Барои нуқтаи ID {shop_id} фармоиш додан",
    "checkout.confirm": "✅ Тасдиқ",

    # Сабадҳо аз рӯи намуд
    "cart_menu.shop": "🛒 Сабади мағозаҳо",
    "cart_menu.restaurant": "🍽 Сабади тарабхонаҳо",

    # Рӯйхати фармоишҳо/чатҳо
    "orders.item_tpl": "Фармоиш №{order_id}",

    # Карточкаи фармоиш
    "order_card.chat": "💬 Чат оид ба фармоиш",

    # Кабинет
    "cabinet.edit_name": "✏️ Ному насаб",
    "cabinet.edit_phone": "📞 Телефон",
    "cabinet.edit_address": "📍 Суроға",
}
