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
    "cabinet.language": "🌐 Тил",

    # Тил танлаш
    "language.select_title": "Тилни танланг:",
    "language.ru": "Русский",
    "language.tj": "Тоҷикӣ",
    "language.uz": "Ўзбекча",

    # Умумий экранлар
    "main.select_section": "Бўлимни танланг:",
    "order_menu.prompt": "Нима буюртамиз?",
    "cart.select": "Саватни танланг:",

    # Дўконлар/ресторанлар/категориялар
    "shops.empty": "Ҳозирча дўконлар йўқ.",
    "restaurants.empty": "Ҳозирча ресторанлар йўқ.",
    "shops.select": "Дўконни танланг:",
    "restaurants.select": "Ресторанни танланг:",
    "shop.not_found": "Нуқта топилмади.",
    "categories.empty": "Ҳозирча категориялар йўқ.",
    "categories.shop_title": "Дўкон категориялари:",
    "categories.restaurant_title": "Ресторан категориялари:",

    # Маҳсулотлар
    "products.empty": "Ушбу категорияда ҳозирча маҳсулот йўқ.",
    "products.list_title": "Маҳсулотлар рўйхати:",
    "product.not_found": "Маҳсулот топилмади.",
    "product.price": "Нарх: {price}",
    "product.description": "Тавсиф: {description}",
    "product.open_failed": "Маҳсулотни очиб бўлмади",

    # Сават
    "cart.empty": "Сават бўш.",
    "cart.empty_for_shop": "Бу нуқта учун сават бўш.",
    "cart.title": "🧺 Сават",
    "cart.title.shop": "🧺 Дўкон савати",
    "cart.title.restaurant": "🧺 Ресторан савати",
    "cart.total": "Жами: {total}",
    "cart.added": "Саватга қўшилди",
    "cart.inc_ok": "Ок",
    "cart.dec_none": "Саватда йўқ",
    "cart.deleted": "Ўчирилди",

    # Буюртмани расмийлаштириш
    "checkout.multiple_shops": "Саватда турли дўконлар/ресторанлардан маҳсулот бор. Қайси нуқта учун буюртма берилади?",
    "checkout.confirm_title": "Буюртмани тасдиқланг:",
    "checkout.create_failed": "Буюртма яратиб бўлмади: сават бўш ёки бу нуқта учун буюртма аллақачон яратилган.",
    "checkout.created": "✅ Буюртма муваффақиятли яратилди!\nБуюртма рақами: {order_id}\nҲолат: {status}",

    # Буюртмалар
    "orders.history.empty": "Буюртмалар тарихи бўш.",
    "orders.empty": "Ҳозирча буюртмалар йўқ.",
    "orders.history.title": "Буюртмалар тарихи:",
    "orders.title": "Сизнинг буюртмаларингиз:",
    "order.not_found": "Буюртма топилмади.",
    "order.shop": "Нуқта: {shop_name}",
    "order.status": "Ҳолат: {status}",
    "order.total": "Жами: {total}",
    "order.items_title": "Таркиб:",

    # Чатлар
    "chat.none": "Фаол чатлар йўқ.",
    "chat.list_title": "Буюртмалар бўйича чатлар:",
    "chat.not_found": "Чат топилмади.",
    "chat.unavailable": "Чат мавжуд эмас.",
    "chat.send_prompt": "Хабарни матн кўринишида киритинг.",
    "chat.admin_message_tpl": "💬 Буюртма бўйича хабар #{order_id}\n{text}",

    # Чат экрани (chat_ui)
    "chat.title": "💬 Буюртма бўйича чат #{order_id}",
    "chat.hint": "ℹ️ Қуйида хабар ёзиб, юборинг.",
    "chat.separator": "────────────────────────",
    "chat.no_messages": "Ҳозирча хабарлар йўқ.",
    "chat.role.client": "Мижоз",
    "chat.role.shop": "Дўкон",
    "chat.role.restaurant": "Ресторан",

    # Кабинет
    "cabinet.title": "👤 Кабинет",
    "cabinet.full_name": "Исм-фамилия",
    "cabinet.phone": "Телефон",
    "cabinet.address": "Манзил",
    "cabinet.empty_value": "—",
    "cabinet.enter_name": "Исм-фамилияни киритинг:",
    "cabinet.enter_phone": "Телефонни киритинг:",
    "cabinet.enter_address": "Манзилни киритинг:",
    "cabinet.name_required": "Исм-фамилия бўш бўлиши мумкин эмас.",
    "cabinet.phone_required": "Телефон бўш бўлиши мумкин эмас.",
    "cabinet.address_required": "Манзил бўш бўлиши мумкин эмас.",
    "cabinet.name_saved": "Исм-фамилия сақланди.",
    "cabinet.phone_saved": "Телефон сақланди.",
    "cabinet.address_saved": "Манзил сақланди.",

    # Навигация/хатолар
    "nav.unknown": "Номаълум ўтиш",
    "screen.update_failed": "Хабарни янгилаб бўлмади",

    # Қидирув
    "search.prompt": "Қидирув матнини киритинг. Мен натижаларни киритиш давомида кўрсатаман.",
    "search.inline_unavailable": "Inline-қидирув фақат дўконлар учун мавжуд.",
    "search.inline_hint": (
        "@ орқали қидириш учун, исталган киритиш майдонига ёзинг:\n\n"
        "@{username} <маҳсулот номи>\n"
        "Масалан: @{username} сут\n\n"
        "Натижани танласангиз, карточка чатга юборилади."
    ),
    "search.enter_text": "Қидирув матнини киритинг.",
    "search.not_found": "Ҳеч нарса топилмади. Бошқа сўровни синаб кўринг.",
    "search.results_title": "Топилган маҳсулотлар:",

    # Inline-қидирув
    "inline.price": "Нарх: {price}",
    "inline.product_fallback": "Маҳсулот",

    # Fallback
    "msg.unknown_command": "Фармонни тушунмадим. Қуйидаги менюдан фойдаланинг.",
}
