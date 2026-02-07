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
}
