from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.ui.nav import kb_nav


def kb_client_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 Заказать", callback_data="c:order_menu")],
        [InlineKeyboardButton(text="📦 Заказы", callback_data="c:orders")],
        [InlineKeyboardButton(text="💬 Чат", callback_data="c:chat")],
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="c:cabinet")],
    ])


def kb_order_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Магазины", callback_data="c:shops")],
        [InlineKeyboardButton(text="🍽 Рестораны", callback_data="c:restaurants")],
        [InlineKeyboardButton(text="🧺 Корзина", callback_data="c:cart_menu")],
        [InlineKeyboardButton(text="🕓 История", callback_data="c:history")],
        [InlineKeyboardButton(text="🏠 Главная", callback_data="c:home")],
    ])


def kb_back(to: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"c:back:{to}")]
    ])


def kb_shops_list(items: list[dict], kind: str) -> InlineKeyboardMarkup:
    """
    kind: 'shop' | 'restaurant'
    callback: c:pick:{kind}:{shop_id}
    """
    kb = []
    for x in items:
        kb.append([InlineKeyboardButton(text=x["name"], callback_data=f"c:pick:{kind}:{x['id']}")])
    kb.append([
        InlineKeyboardButton(text="🏠 Домой", callback_data="c:home"),
        InlineKeyboardButton(text="🧺 Корзина", callback_data=f"c:cart:{kind}:shops_list"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="c:back:order_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_categories_list(categories: list[dict], kind: str, shop_id: int) -> InlineKeyboardMarkup:
    """
    callback: c:cat:{shop_id}:{category_id}
    """
    kb = []
    for c in categories:
        kb.append([InlineKeyboardButton(text=c["name"], callback_data=f"c:cat:{shop_id}:{c['id']}")])
    kb.append([InlineKeyboardButton(text="🔎 Поиск", callback_data=f"c:search:{kind}:{shop_id}")])
    kb.append([
        InlineKeyboardButton(text="🏠 Домой", callback_data="c:home"),
        InlineKeyboardButton(text="🧺 Корзина", callback_data=f"c:cart:{kind}:categories:{kind}:{shop_id}"),
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"c:back:{kind}_list"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_products_list(products: list[dict], shop_id: int, category_id: int) -> InlineKeyboardMarkup:
    """
    callback: c:prod:{product_id}
    """
    kb = []
    for p in products:
        price = p["price"]
        kb.append([InlineKeyboardButton(
            text=f"{p['name']} — {price}",
            callback_data=f"c:prod:{p['id']}"
        )])
    kb.append([
        InlineKeyboardButton(text="🏠 Домой", callback_data="c:home"),
        InlineKeyboardButton(
            text="🧺 Корзина",
            callback_data=f"c:cart:auto:products:{shop_id}:{category_id}",
        ),
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"c:pickback:{shop_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_product_card(product_id: int, shop_id: int, category_id: int) -> InlineKeyboardMarkup:
    """
    callback:
      c:add:{product_id} — добавить в корзину
      c:cat:{shop_id}:{category_id} — назад в товары категории
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить в корзину", callback_data=f"c:add:{product_id}")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="c:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"c:cat:{shop_id}:{category_id}"),
        ],
    ])


def _cart_back_callback(back_target: str | None) -> str:
    if back_target:
        return f"c:back:from_cart:{back_target}"
    return "c:back:from_cart"


def kb_cart(items: list[dict], back_target: str | None = None) -> InlineKeyboardMarkup:
    """
    items: [{'product_id','quantity','name','price','shop_id'}, ...]
    callback:
      c:cart_dec:{product_id}
      c:cart_inc:{product_id}
      c:cart_del:{product_id}
      c:checkout
      c:back:main
    """
    kb = []
    for it in items:
        pid = it["product_id"]
        kb.append([
            InlineKeyboardButton(text="➖", callback_data=f"c:cart_dec:{pid}"),
            InlineKeyboardButton(text=f"{it['quantity']} шт", callback_data="c:noop"),
            InlineKeyboardButton(text="➕", callback_data=f"c:cart_inc:{pid}"),
        ])
        kb.append([
            InlineKeyboardButton(text=f"❌ Удалить {it['name']}", callback_data=f"c:cart_del:{pid}")
        ])

    kb.append([InlineKeyboardButton(text="🧾 Оформить заказ", callback_data="c:checkout")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=_cart_back_callback(back_target))])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_cart_empty(back_target: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=_cart_back_callback(back_target))]
    ])


def kb_checkout_choose_shop(shop_ids: list[int]) -> InlineKeyboardMarkup:
    """
    Если в корзине товары из разных точек, даём выбрать, для какого shop_id оформить заказ.
    callback: c:checkout_preview:{shop_id}
    """
    kb = []
    for sid in shop_ids:
        kb.append([InlineKeyboardButton(text=f"Оформить для точки ID {sid}", callback_data=f"c:checkout_preview:{sid}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="c:cart")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_checkout_confirm(shop_id: int, has_comment: bool = False) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"c:checkout_confirm:{shop_id}")],
        [InlineKeyboardButton(text="✍️ Комментарий", callback_data=f"c:checkout_comment:{shop_id}")],
    ]
    if has_comment:
        kb.append([InlineKeyboardButton(text="🗑 Удалить комментарий", callback_data=f"c:checkout_comment_clear:{shop_id}")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data=f"c:checkout_cancel:{shop_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_after_order() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="c:back:main")]
    ])


def kb_cart_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Корзина магазинов", callback_data="c:cart:shop:cart_menu")],
        [InlineKeyboardButton(text="🍽 Корзина ресторанов", callback_data="c:cart:restaurant:cart_menu")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="c:back:order_menu")],
    ])


def kb_chat_orders(order_ids: list[int], prefix: str) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"{prefix}:chat:{oid}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="c:back:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_orders_list(order_ids: list[int], back_target: str = "main") -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"c:order:{oid}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"c:back:{back_target}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
