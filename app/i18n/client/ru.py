# Все тексты клиентского бота (RU)
# Важно: ключи должны использоваться в клавиатурах и экранах вместо "жёстких" строк.

TEXTS: dict[str, str] = {
    # Главное меню (kb_client_main)
    "main.order": "🛍 Заказать",
    "main.orders": "📦 Заказы",
    "main.chat": "💬 Чат",
    "main.cabinet": "👤 Кабинет",

    # Меню "Заказать" (kb_order_menu)
    "order_menu.shops": "🛒 Магазины",
    "order_menu.restaurants": "🍽 Рестораны",
    "order_menu.cart": "🧺 Корзина",
    "order_menu.history": "🕓 История",
    "nav.home": "🏠 Главная",

    # Навигация
    "nav.back": "🔙 Назад",
    "nav.home_alt": "🏠 Домой",
    "nav.to_main": "🏠 В главное меню",

    # Поиск
    "search.open_inline": "🔎 Открыть inline",
    "search.search": "🔎 Поиск",
    "search.at_search": "🔎 @Поиск",

    # Карточка товара
    "product.add_to_cart": "➕ Добавить в корзину",

    # Корзина
    "cart.checkout": "🧾 Оформить заказ",
    "cart.qty_suffix": "шт",  # используется в шаблоне количества: "{qty} {suffix}"
    "cart.del_item_tpl": "❌ Удалить {name}",

    # Оформление заказа
    "checkout.choose_shop_tpl": "Оформить для точки ID {shop_id}",
    "checkout.confirm": "✅ Подтвердить",

    # Корзина по типам (kb_cart_menu)
    "cart_menu.shop": "🛒 Корзина магазинов",
    "cart_menu.restaurant": "🍽 Корзина ресторанов",

    # Списки заказов/чатов
    "orders.item_tpl": "Заказ #{order_id}",

    # Карточка заказа (orders.py)
    "order_card.chat": "💬 Чат по заказу",

    # Кабинет (cabinet.py)
    "cabinet.edit_name": "✏️ ФИО",
    "cabinet.edit_phone": "📞 Телефон",
    "cabinet.edit_address": "📍 Адрес",
    "cabinet.language": "🌐 Язык",

    # Экран выбора языка
    "language.select_title": "Выберите язык:",
    "language.ru": "Русский",
    "language.tj": "Тоҷикӣ",
    "language.uz": "Ўзбекча",

    # Общие экраны
    "main.select_section": "Выберите раздел:",
    "order_menu.prompt": "Что будем заказывать?",
    "cart.select": "Выберите корзину:",

    # Магазины/рестораны/категории
    "shops.empty": "Магазинов пока нет.",
    "restaurants.empty": "Ресторанов пока нет.",
    "shops.select": "Выберите магазин:",
    "restaurants.select": "Выберите ресторан:",
    "shop.not_found": "Точка не найдена.",
    "categories.empty": "Категорий пока нет.",
    "categories.shop_title": "Категории магазина:",
    "categories.restaurant_title": "Категории ресторана:",

    # Товары
    "products.empty": "В этой категории пока нет товаров.",
    "products.list_title": "Список товаров:",
    "product.not_found": "Товар не найден.",
    "product.price": "Цена: {price}",
    "product.description": "Описание: {description}",
    "product.open_failed": "Не удалось открыть товар",

    # Корзина
    "cart.empty": "Корзина пуста.",
    "cart.empty_for_shop": "Корзина пуста для этой точки.",
    "cart.title": "🧺 Корзина",
    "cart.title.shop": "🧺 Корзина магазинов",
    "cart.title.restaurant": "🧺 Корзина ресторанов",
    "cart.total": "Итого: {total}",
    "cart.added": "Добавлено в корзину",
    "cart.inc_ok": "Ок",
    "cart.dec_none": "Нет в корзине",
    "cart.deleted": "Удалено",

    # Оформление заказа
    "checkout.multiple_shops": "В корзине товары из разных магазинов/ресторанов. Выберите, для какой точки оформить заказ:",
    "checkout.confirm_title": "Подтвердите оформление заказа:",
    "checkout.create_failed": "Не удалось создать заказ: корзина пуста или заказ уже создан для этой точки.",
    "checkout.created": "✅ Заказ успешно создан!\nНомер заказа: {order_id}\nСтатус: {status}",

    # Заказы
    "orders.history.empty": "История заказов пуста.",
    "orders.empty": "Заказов пока нет.",
    "orders.history.title": "История заказов:",
    "orders.title": "Ваши заказы:",
    "order.not_found": "Заказ не найден.",
    "order.shop": "Точка: {shop_name}",
    "order.status": "Статус: {status}",
    "order.total": "Сумма: {total}",
    "order.items_title": "Состав:",

    # Чаты
    "chat.none": "Активных чатов нет.",
    "chat.list_title": "Чаты по заказам:",
    "chat.not_found": "Чат не найден.",
    "chat.unavailable": "Чат недоступен.",
    "chat.send_prompt": "Введите сообщение текстом.",
    "chat.admin_message_tpl": "💬 Сообщение по заказу #{order_id}\n{text}",

    # Экран чата (chat_ui)
    "chat.title": "💬 Чат по заказу #{order_id}",
    "chat.hint": "ℹ️ Просто напишите сообщение в поле ниже и отправьте.",
    "chat.separator": "────────────────────────",
    "chat.no_messages": "Пока сообщений нет.",
    "chat.role.client": "Клиент",
    "chat.role.shop": "Магазин",
    "chat.role.restaurant": "Ресторан",

    # Кабинет
    "cabinet.title": "👤 Кабинет",
    "cabinet.full_name": "ФИО",
    "cabinet.phone": "Телефон",
    "cabinet.address": "Адрес",
    "cabinet.empty_value": "—",
    "cabinet.enter_name": "Введите ФИО:",
    "cabinet.enter_phone": "Введите телефон:",
    "cabinet.enter_address": "Введите адрес:",
    "cabinet.name_required": "ФИО не может быть пустым.",
    "cabinet.phone_required": "Телефон не может быть пустым.",
    "cabinet.address_required": "Адрес не может быть пустым.",
    "cabinet.name_saved": "ФИО сохранено.",
    "cabinet.phone_saved": "Телефон сохранён.",
    "cabinet.address_saved": "Адрес сохранён.",

    # Навигация/ошибки
    "nav.unknown": "Неизвестный переход",
    "screen.update_failed": "Не удалось обновить сообщение",

    # Поиск
    "search.prompt": "Введите текст для поиска. Я буду показывать результаты по мере ввода.",
    "search.inline_unavailable": "Inline-поиск доступен только для магазинов.",
    "search.inline_hint": (
        "Чтобы искать через @, откройте любое поле ввода и напишите:\n\n"
        "@{username} <название товара>\n"
        "Например: @{username} молоко\n\n"
        "После выбора результата карточка отправится в чат."
    ),
    "search.enter_text": "Введите текст для поиска.",
    "search.not_found": "Ничего не найдено. Попробуйте другой запрос.",
    "search.results_title": "Найденные товары:",

    # Inline-поиск
    "inline.price": "Цена: {price}",
    "inline.product_fallback": "Товар",

    # Fallback
    "msg.unknown_command": "Я не понял команду. Используйте меню ниже.",
}
