from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.i18n.client.translator import t

def _pick_category_name(cat: dict, locale: str) -> str:
    if locale == "uz":
        return cat.get("name_uz") or cat.get("name_ru") or cat.get("name")
    if locale == "tj":
        return cat.get("name_tj") or cat.get("name_ru") or cat.get("name")
    return cat.get("name_ru") or cat.get("name")


def _order_type_emoji(business_type: str | None) -> str:
    return "🍽️" if business_type == "restaurant" else "🛒"


def _order_button_text(row: dict) -> str:
    order_id = row["id"]
    shop_name = (row.get("shop_name") or "").strip()
    if not shop_name:
        shop_id = row.get("shop_id")
        shop_name = f"#{shop_id}" if shop_id is not None else ""
    emoji = _order_type_emoji(row.get("business_type"))
    return f"{emoji} {order_id} · {shop_name}"

def kb_client_main(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "main.order"), callback_data="c:order_menu")],
        [InlineKeyboardButton(text=t(locale, "main.orders"), callback_data="c:orders")],
        [InlineKeyboardButton(text=t(locale, "main.chat"), callback_data="c:chat")],
        [InlineKeyboardButton(text=t(locale, "main.cabinet"), callback_data="c:cabinet")],
    ])


def kb_order_menu(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "order_menu.shops"), callback_data="c:shops")],
        [InlineKeyboardButton(text=t(locale, "order_menu.restaurants"), callback_data="c:restaurants")],
        [InlineKeyboardButton(text=t(locale, "order_menu.cart"), callback_data="c:cart_menu")],
        [InlineKeyboardButton(text=t(locale, "order_menu.history"), callback_data="c:history")],
        [InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home")],
    ])


def kb_back(locale: str, to: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:back:{to}")]
    ])


def kb_inline_search(locale: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "search.open_inline"), switch_inline_query_current_chat="")],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=back_cb)],
    ])


def kb_shops_list(locale: str, items: list[dict], kind: str) -> InlineKeyboardMarkup:
    kb = []
    for x in items:
        kb.append([InlineKeyboardButton(text=x["name"], callback_data=f"c:pick:{kind}:{x['id']}")])
    kb.append([
        InlineKeyboardButton(text=t(locale, "nav.home_alt"), callback_data="c:home"),
        InlineKeyboardButton(text=t(locale, "order_menu.cart"), callback_data=f"c:cart:{kind}:shops_list"),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:order_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_categories_list(locale: str, categories: list[dict], kind: str, shop_id: int) -> InlineKeyboardMarkup:
    kb = []
    for c in categories:
        title = _pick_category_name(c, locale)
        kb.append([InlineKeyboardButton(text=title, callback_data=f"c:cat:{shop_id}:{c['id']}")])

 #  kb.append([InlineKeyboardButton(text=t(locale, "search.search"), callback_data=f"c:search:{kind}:{shop_id}")])
    kb.append([InlineKeyboardButton(text=t(locale, "search.at_search"), callback_data=f"c:at_search:{kind}:{shop_id}")])
    kb.append([
        InlineKeyboardButton(text=t(locale, "nav.home_alt"), callback_data="c:home"),
        InlineKeyboardButton(text=t(locale, "order_menu.cart"), callback_data=f"c:cart:{kind}:categories:{kind}:{shop_id}"),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:back:{kind}_list"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_products_list(locale: str, products: list[dict], shop_id: int, category_id: int) -> InlineKeyboardMarkup:
    kb = []
    for p in products:
        kb.append([InlineKeyboardButton(text=f"{p['name']} — {p['price']}", callback_data=f"c:prod:{p['id']}")])
    kb.append([
        InlineKeyboardButton(text=t(locale, "nav.home_alt"), callback_data="c:home"),
        InlineKeyboardButton(text=t(locale, "order_menu.cart"), callback_data=f"c:cart:auto:products:{shop_id}:{category_id}"),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:pickback:{shop_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_products_list_shop(locale: str, products: list[dict], shop_id: int, category_id: int) -> InlineKeyboardMarkup:
    kb = []
    for p in products:
        sku = (p.get("sku") or "").strip().upper()
        if not sku:
            continue
        kb.append([InlineKeyboardButton(text=f"{p['name']} — {p['price']}", callback_data=f"c:prodsku:{shop_id}:{sku}")])
    kb.append([
        InlineKeyboardButton(text=t(locale, "nav.home_alt"), callback_data="c:home"),
        InlineKeyboardButton(text=t(locale, "order_menu.cart"), callback_data=f"c:cart:auto:products:{shop_id}:{category_id}"),
        InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:pickback:{shop_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_product_card_shop(locale: str, shop_id: int, category_id: int, sku: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "product.add_to_cart"), callback_data=f"c:addsku:{shop_id}:{sku}")],
        [
            InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home"),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=f"c:cat:{shop_id}:{category_id}"),
        ],
    ])


def kb_product_card(locale: str, product_id: int, shop_id: int, category_id: int) -> InlineKeyboardMarkup:
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


def kb_cart(locale: str, items: list[dict], back_target: str | None = None) -> InlineKeyboardMarkup:
    kb = []
    qty_suffix = t(locale, "cart.qty_suffix")
    for it in items:
        pid = it["product_id"]
        kb.append([
            InlineKeyboardButton(text="➖", callback_data=f"c:cart_dec:{pid}"),
            InlineKeyboardButton(text=f"{it['quantity']} {qty_suffix}", callback_data="c:noop"),
            InlineKeyboardButton(text="➕", callback_data=f"c:cart_inc:{pid}"),
        ])
        #kb.append([
         #   InlineKeyboardButton(text=t(locale, "cart.del_item_tpl", name=it["name"]), callback_data=f"c:cart_del:{pid}")
       # ])

    kb.append([InlineKeyboardButton(text=t(locale, "cart.checkout"), callback_data="c:checkout")])
    kb.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=_cart_back_callback(back_target))])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_cart_empty(locale: str, back_target: str | None = None) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=_cart_back_callback(back_target))]
    ])


def kb_checkout_choose_shop(locale: str, shops: list[dict]):
    kb = []

    for s in shops:
        sid = int(s["id"])
        name = (s.get("name") or "").strip() or f"ID {sid}"
        bt = s.get("business_type")
        emoji = "🍽️" if bt == "restaurant" else "🏬"

        kb.append([
            InlineKeyboardButton(
                text=f"{emoji} {name}",
                callback_data=f"c:checkout_shop:{sid}",
            )
        ])

    kb.append([InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:cart_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
    

def kb_checkout_confirm(
    locale: str,
    confirm_cb: str,
    back_cb: str,
    business_type: str,
    selected_fulfillment: str | None,
    shop_id: int,
) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []
    if business_type == "shop":
        pickup_text = t(locale, "pickup")
        if selected_fulfillment == "pickup":
            pickup_text = f"✅ {pickup_text}"
        kb.append([
            InlineKeyboardButton(text=t(locale, "checkout.comment"), callback_data="c:checkout_comment"),
            InlineKeyboardButton(
                text=pickup_text,
                callback_data=f"c:checkout_fulfill:{shop_id}:pickup_toggle",
            ),
        ])
        kb.append([
            InlineKeyboardButton(text=t(locale, "checkout.confirm"), callback_data=confirm_cb),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=back_cb),
        ])
        return InlineKeyboardMarkup(inline_keyboard=kb)

    kb.append([InlineKeyboardButton(text=t(locale, "checkout.comment"), callback_data="c:checkout_comment")])
    variants = [
        ("courier", t(locale, "delivery")),
        ("pickup", t(locale, "pickup")),
        ("dine_in", t(locale, "dine_in")),
    ]
    row: list[InlineKeyboardButton] = []
    for value, label in variants:
        text = f"✅ {label}" if selected_fulfillment == value else label
        row.append(
            InlineKeyboardButton(
                text=text,
                callback_data=f"c:checkout_fulfill:{shop_id}:{value}",
            )
        )
    kb.append(row)
    if selected_fulfillment:
        kb.append([
            InlineKeyboardButton(text=t(locale, "checkout.confirm"), callback_data=confirm_cb),
            InlineKeyboardButton(text=t(locale, "nav.back"), callback_data=back_cb),
        ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_after_order(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "nav.to_main"), callback_data="c:back:main")]
    ])


def kb_cart_menu(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "cart_menu.shop"), callback_data="c:cart:shop:cart_menu")],
        [InlineKeyboardButton(text=t(locale, "cart_menu.restaurant"), callback_data="c:cart:restaurant:cart_menu")],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:back:order_menu")],
    ])


def kb_chat_orders(locale: str, rows: list[dict], prefix: str) -> InlineKeyboardMarkup:
    kb = []
    for row in rows:
        order_id = row["id"]
        kb.append([InlineKeyboardButton(text=_order_button_text(row), callback_data=f"{prefix}:chat:{order_id}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_orders_list(
    locale: str,
    rows: list[dict],
    back_target: str = "main",
) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []

    for row in rows:
        order_id = row["id"]
        kb.append([InlineKeyboardButton(
            text=_order_button_text(row),
            callback_data=f"c:order:{order_id}"
        )])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_cabinet(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "cabinet.edit_name"), callback_data="c:cabinet:edit_name")],
        [InlineKeyboardButton(text=t(locale, "cabinet.edit_phone"), callback_data="c:cabinet:edit_phone")],
        [InlineKeyboardButton(text=t(locale, "cabinet.edit_address"), callback_data="c:cabinet:edit_address")],
        [InlineKeyboardButton(text=t(locale, "cabinet.language"), callback_data="c:cabinet:language")],
        [InlineKeyboardButton(text=t(locale, "nav.home"), callback_data="c:home")],
    ])


def kb_language_select(locale: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(locale, "language.ru"), callback_data="c:set_locale:ru")],
        [InlineKeyboardButton(text=t(locale, "language.tj"), callback_data="c:set_locale:tj")],
        [InlineKeyboardButton(text=t(locale, "language.uz"), callback_data="c:set_locale:uz")],
        [InlineKeyboardButton(text=t(locale, "nav.back"), callback_data="c:cabinet")],
    ])
