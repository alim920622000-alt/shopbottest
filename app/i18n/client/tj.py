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
    "cabinet.language": "🌐 Забон",

    # Интихоби забон
    "language.select_title": "Забонро интихоб кунед:",
    "language.ru": "Русский",
    "language.tj": "Тоҷикӣ",
    "language.uz": "Ўзбекча",

    # Экранҳои умумӣ
    "main.select_section": "Қисмро интихоб кунед:",
    "order_menu.prompt": "Чӣ фармоиш медиҳем?",
    "cart.select": "Сабадро интихоб кунед:",

    # Мағозаҳо/тарабхонаҳо/категорияҳо
    "shops.empty": "Ҳоло мағозаҳо нестанд.",
    "restaurants.empty": "Ҳоло тарабхонаҳо нестанд.",
    "shops.select": "Мағозаро интихоб кунед:",
    "restaurants.select": "Тарабхонаро интихоб кунед:",
    "shop.not_found": "Нуқта ёфт нашуд.",
    "categories.empty": "Ҳоло категорияҳо нестанд.",
    "categories.shop_title": "Категорияҳои мағоза:",
    "categories.restaurant_title": "Категорияҳои тарабхона:",

    # Маҳсулот
    "products.empty": "Дар ин категория ҳоло маҳсулот нест.",
    "products.list_title": "Рӯйхати маҳсулот:",
    "product.not_found": "Маҳсулот ёфт нашуд.",
    "product.price": "Нарх: {price}",
    "product.description": "Тавсиф: {description}",
    "product.open_failed": "Маҳсулотро кушода нашуд",

    # Сабад
    "cart.empty": "Сабад холӣ аст.",
    "cart.empty_for_shop": "Сабад барои ин нуқта холӣ аст.",
    "cart.title": "🧺 Сабад",
    "cart.title.shop": "🧺 Сабади мағозаҳо",
    "cart.title.restaurant": "🧺 Сабади тарабхонаҳо",
    "cart.total": "Ҳамагӣ: {total}",
    "cart.added": "Ба сабад илова шуд",
    "cart.inc_ok": "Ок",
    "cart.dec_none": "Дар сабад нест",
    "cart.deleted": "Ҳазф шуд",

    # Оформкунии фармоиш
    "checkout.multiple_shops": "Дар сабад маҳсулот аз мағозаҳо/тарабхонаҳои гуногун аст. Барои кадом нуқта фармоиш диҳем?",
    "checkout.confirm_title": "Фармоишро тасдиқ кунед:",
    "checkout.create_failed": "Фармоиш сохта нашуд: сабад холӣ аст ё барои ин нуқта аллакай фармоиш мавҷуд аст.",
    "checkout.created": "✅ Фармоиш муваффақона сохта шуд!\nРақами фармоиш: {order_id}\nҲолат: {status}",

    # Фармоишҳо
    "orders.history.empty": "Таърихи фармоишҳо холӣ аст.",
    "orders.empty": "Ҳоло фармоишҳо нестанд.",
    "orders.history.title": "Таърихи фармоишҳо:",
    "orders.title": "Фармоишҳои шумо:",
    "order.not_found": "Фармоиш ёфт нашуд.",
    "order.shop": "Нуқта: {shop_name}",
    "order.status": "Ҳолат: {status}",
    "order.total": "Ҳамагӣ: {total}",
    "order.items_title": "Таркиб:",

    # Чатҳо
    "chat.none": "Чатҳои фаъол нестанд.",
    "chat.list_title": "Чатҳо аз рӯи фармоишҳо:",
    "chat.not_found": "Чат ёфт нашуд.",
    "chat.unavailable": "Чат дастнорас аст.",
    "chat.send_prompt": "Паёмро бо матн ворид кунед.",
    "chat.admin_message_tpl": "💬 Паём аз рӯи фармоиш #{order_id}\n{text}",

    # Экран чата (chat_ui)
    "chat.title": "💬 Чат оид ба фармоиш #{order_id}",
    "chat.hint": "ℹ️ Дар поён паём нависед ва фиристед.",
    "chat.separator": "────────────────────────",
    "chat.no_messages": "Ҳоло паёмҳо нестанд.",
    "chat.role.client": "Муштарӣ",
    "chat.role.shop": "Мағоза",
    "chat.role.restaurant": "Тарабхона",

    # Кабинет
    "cabinet.title": "👤 Кабинет",
    "cabinet.full_name": "Ному насаб",
    "cabinet.phone": "Телефон",
    "cabinet.address": "Суроға",
    "cabinet.empty_value": "—",
    "cabinet.enter_name": "Ному насабро ворид кунед:",
    "cabinet.enter_phone": "Телефонро ворид кунед:",
    "cabinet.enter_address": "Суроғаро ворид кунед:",
    "cabinet.name_required": "Ному насаб холӣ буда наметавонад.",
    "cabinet.phone_required": "Телефон холӣ буда наметавонад.",
    "cabinet.address_required": "Суроға холӣ буда наметавонад.",
    "cabinet.name_saved": "Ному насаб нигоҳ дошта шуд.",
    "cabinet.phone_saved": "Телефон нигоҳ дошта шуд.",
    "cabinet.address_saved": "Суроға нигоҳ дошта шуд.",

    # Навигатсия/хатогиҳо
    "nav.unknown": "Гузариши номаълум",
    "screen.update_failed": "Навсозии паём имконнопазир аст",

    # Ҷустуҷӯ
    "search.prompt": "Матни ҷустуҷӯро ворид кунед. Ман натиҷаҳоро ҳангоми воридкунӣ нишон медиҳам.",
    "search.inline_unavailable": "Inline-ҷустуҷӯ танҳо барои мағозаҳо дастрас аст.",
    "search.inline_hint": (
        "Барои ҷустуҷӯ тавассути @, дар ягон майдон нависед:\n\n"
        "@{username} <номи маҳсулот>\n"
        "Масалан: @{username} шир\n\n"
        "Пас аз интихоб карточка ба чат меояд."
    ),
    "search.enter_text": "Матни ҷустуҷӯро ворид кунед.",
    "search.not_found": "Ҳеҷ чиз ёфт нашуд. Дархости дигарро кӯшиш кунед.",
    "search.results_title": "Маҳсулотҳои ёфтшуда:",

    # Inline-ҷустуҷӯ
    "inline.price": "Нарх: {price}",
    "inline.product_fallback": "Маҳсулот",

    # Fallback
    "msg.unknown_command": "Фармонро нафаҳмидам. Аз менюи поён истифода баред.",
}
