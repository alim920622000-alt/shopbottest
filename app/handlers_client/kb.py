from __future__ import annotations

from typing import Callable

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def kb_client_main(locale: str, t: Callable[[str, str], str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "main.order"), callback_data="c:order_menu")],
        [InlineKeyboardButton(text=t(locale, "main.orders"), callback_data="c:orders")],
        [InlineKeyboardButton(text=t(locale, "main.chat"), callback_data="c:chat")],
        [InlineKeyboardButton(text=t(locale, "main.cabinet"), callback_data="c:cabinet")],
    ])


def kb_order_menu(locale: str, t: Callable[[str, str], str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "order_menu.shops"), callback_data="c:shops")],
        [InlineKeyboardButton(text=t(locale, "order_menu.restaurants"), callback_data="c:restaurants")],
        [InlineKeyboardButton(text=t(locale, "order_menu.cart"), callback_data="c:cart_menu")],
        [InlineKeyboardButton(text=t(locale, "order_menu.history"), callback_data="c:history")],
        [InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home")],
    ])


def kb_back(locale: str, t: Callable[[str, str], str], to: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:back:{to}")]
    ])


def kb_inline_search(locale: str, t: Callable[[str, str], str], back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "search.open_inline"), switch_inline_query_current_chat="")],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=back_cb)],
    ])


def kb_shops_list(
    locale: str,
    t: Callable[[str, str], str],
    items: list[dict],
    kind: str,
) -> InlineKeyboardMarkup:
    """
    kind: 'shop' | 'restaurant'
    callback: c:pick:{kind}:{shop_id}
    """
    kb = []
    for x in items:
        kb.append([InlineKeyboardButton(text=x["name"], callback_data=f"c:pick:{kind}:{x['id']}")])
    kb.append([
        InlineKeyboardButton(text=t(locale, "nav.home_alt"), callback_data="c:home"),
        InlineKeyboardButton(text=t(locale, "order_menu.cart"), callback_data=f"c:cart:{kind}:shops_list"),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:order_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_categories_list(
    locale: str,
    t: Callable[[str, str], str],
    categories: list[dict],
    kind: str,
    shop_id: int,
) -> InlineKeyboardMarkup:
    """
    callback: c:cat:{shop_id}:{category_id}
    """
    kb = []
    for c in categories:
        kb.append([InlineKeyboardButton(text=c["name"], callback_data=f"c:cat:{shop_id}:{c['id']}")])
    kb.append([InlineKeyboardButton(text=t(locale, "search.search"), callback_data=f"c:search:{kind}:{shop_id}")])
    kb.append([InlineKeyboardButton(text=t(locale, "search.at_search"), callback_data=f"c:at_search:{kind}:{shop_id}")])
    kb.append([
        InlineKeyboardButton(text=t(locale, "nav.home_alt"), callback_data="c:home"),
        InlineKeyboardButton(text=t(locale, "order_menu.cart"), callback_data=f"c:cart:{kind}:categories:{kind}:{shop_id}"),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:back:{kind}_list"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_products_list(
    locale: str,
    t: Callable[[str, str], str],
    products: list[dict],
    shop_id: int,
    category_id: int,
) -> InlineKeyboardMarkup:
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
        InlineKeyboardButton(text=t(locale, "nav.home_alt"), callback_data="c:home"),
        InlineKeyboardButton(
            text=t(locale, "order_menu.cart"),
            callback_data=f"c:cart:auto:products:{shop_id}:{category_id}",
        ),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:pickback:{shop_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)




def kb_products_list_shop(
    locale: str,
    t: Callable[[str, str], str],
    products: list[dict],
    shop_id: int,
    category_id: int,
) -> InlineKeyboardMarkup:
    """
    callback: c:prodsku:{shop_id}:{sku}
    """
    kb = []
    for p in products:
        sku = (p.get("sku") or "").strip().upper()
        if not sku:
            continue
        price = p["price"]
        kb.append([InlineKeyboardButton(
            text=f"{p['name']} — {price}",
            callback_data=f"c:prodsku:{shop_id}:{sku}"
        )])
    kb.append([
        InlineKeyboardButton(text=t(locale, "nav.home_alt"), callback_data="c:home"),
        InlineKeyboardButton(
            text=t(locale, "order_menu.cart"),
            callback_data=f"c:cart:auto:products:{shop_id}:{category_id}",
        ),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:pickback:{shop_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_product_card_shop(
    locale: str,
    t: Callable[[str, str], str],
    shop_id: int,
    category_id: int,
    sku: str,
) -> InlineKeyboardMarkup:
    """
    callback:
      c:addsku:{shop_id}:{sku} — добавить в корзину
      c:cat:{shop_id}:{category_id} — назад в товары категории
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "product.add_to_cart"), callback_data=f"c:addsku:{shop_id}:{sku}")],
        [
            InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home"),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:cat:{shop_id}:{category_id}"),
        ],
    ])

def kb_product_card(
    locale: str,
    t: Callable[[str, str], str],
    product_id: int,
    shop_id: int,
    category_id: int,
) -> InlineKeyboardMarkup:
    """
    callback:
      c:add:{product_id} — добавить в корзину
      c:cat:{shop_id}:{category_id} — назад в товары категории
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "product.add_to_cart"), callback_data=f"c:add:{product_id}")],
        [
            InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home"),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:cat:{shop_id}:{category_id}"),
        ],
    ])


def _cart_back_callback(back_target: str | None) -> str:
    if back_target:
        return f"c:back:from_cart:{back_target}"
    return "c:back:from_cart"


def kb_cart(
    locale: str,
    t: Callable[[str, str], str],
    items: list[dict],
    back_target: str | None = None,
) -> InlineKeyboardMarkup:
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
            InlineKeyboardButton(
                text=f"{it['quantity']} {t(locale, 'cart.qty_suffix')}",
                callback_data="c:noop",
            ),
            InlineKeyboardButton(text="➕", callback_data=f"c:cart_inc:{pid}"),
        ])
        kb.append([
            InlineKeyboardButton(
                text=t(locale, "cart.del_item_tpl", name=it["name"]),
                callback_data=f"c:cart_del:{pid}",
            )
        ])

    kb.append([InlineKeyboardButton(text=t(locale, "cart.checkout"), callback_data="c:checkout")])
    kb.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=_cart_back_callback(back_target))])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_cart_empty(locale: str, t: Callable[[str, str], str], back_target: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=_cart_back_callback(back_target))]
    ])


def kb_checkout_choose_shop(
    locale: str,
    t: Callable[[str, str], str],
    shop_ids: list[int],
) -> InlineKeyboardMarkup:
    """
    Если в корзине товары из разных точек, даём выбрать, для какого shop_id оформить заказ.
    callback: c:checkout_shop:{shop_id}
    """
    kb = []
    for sid in shop_ids:
        kb.append([
            InlineKeyboardButton(
                text=t(locale, "checkout.choose_shop_tpl", shop_id=sid),
                callback_data=f"c:checkout_shop:{sid}",
            )
        ])
    kb.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:cart")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_checkout_confirm(
    locale: str,
    t: Callable[[str, str], str],
    confirm_cb: str,
    back_cb: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(locale, "checkout.confirm"), callback_data=confirm_cb),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=back_cb),
        ]
    ])


def kb_after_order(locale: str, t: Callable[[str, str], str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "nav.to_main"), callback_data="c:back:main")]
    ])


def kb_cart_menu(locale: str, t: Callable[[str, str], str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "cart_menu.shop"), callback_data="c:cart:shop:cart_menu")],
        [InlineKeyboardButton(text=t(locale, "cart_menu.restaurant"), callback_data="c:cart:restaurant:cart_menu")],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:order_menu")],
    ])


def kb_chat_orders(
    locale: str,
    t: Callable[[str, str], str],
    order_ids: list[int],
    prefix: str,
) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=t(locale, "orders.item_tpl", order_id=oid), callback_data=f"{prefix}:chat:{oid}")])
    kb.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_orders_list(
    locale: str,
    t: Callable[[str, str], str],
    order_ids: list[int],
    back_target: str = "main",
) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=t(locale, "orders.item_tpl", order_id=oid), callback_data=f"c:order:{oid}")])
    kb.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:back:{back_target}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
