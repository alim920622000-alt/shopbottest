import logging
import re
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from app.db.database import Database
from app.repositories.shops_repo import ShopsRepo
from app.repositories.categories_repo import CategoriesRepo
from app.repositories.products_repo import ProductsRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.cart_repo import CartRepo
from app.services.search_service import SearchService
from app.services.admin_notifications import notify_admins_new_order
from app.services.screen import (
    clear_state_keep_screen,
    delete_screen,
    get_screen_message_id,
    safe_edit_text,
    set_screen_message_id,
    show_main_menu,
)
from app.services.client_ui_state import remember_client_screen
from app.services.chat_reminders import is_chat_reminder_text
from app.utils.tg_safe import safe_delete_cq_message
from app.handlers_client.kb import (
    kb_client_main,
    kb_order_menu,
    kb_cart_menu,
    kb_back,
    kb_shops_list,
    kb_categories_list,
    kb_products_list,
    kb_products_list_shop,
    kb_product_card,
    kb_product_card_shop,
    kb_cart,
    kb_cart_empty,
    kb_checkout_choose_shop,
    kb_checkout_confirm,
    kb_after_order,
    kb_inline_search,
)

router = Router()
logger = logging.getLogger(__name__)

SKU_RE = re.compile(r"^SKU-[0-9A-F]{8}$")


class ClientCatalogStates(StatesGroup):
    search = State()
    waiting_order_comment = State()


SKU_PATTERN = re.compile(r"^SKU-[A-Z0-9]{4,64}$")


def _build_product_card_text(product: dict) -> str:
    text = f"{product['name']}\n\nЦена: {product['price']}\n"
    if product.get("description"):
        text += f"\nОписание: {product['description']}\n"
    return text


def _parse_sku_from_message(text: str | None) -> str | None:
    normalized = (text or "").strip().upper()
    if not normalized or not SKU_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _parse_cart_back_target(parts: list[str]) -> dict | None:
    if not parts:
        return None
    name = parts[0]
    if name == "shops_list":
        return {"name": "shops_list"}
    if name == "restaurants_list":
        return {"name": "restaurants_list"}
    if name == "categories" and len(parts) >= 3:
        return {"name": "categories", "kind": parts[1], "shop_id": int(parts[2])}
    if name == "products" and len(parts) >= 3:
        return {"name": "products", "shop_id": int(parts[1]), "category_id": int(parts[2])}
    if name == "cart_menu":
        return {"name": "cart_menu"}
    if name == "order_menu":
        return {"name": "order_menu"}
    return None


@router.message(F.via_bot.is_not(None), F.text.regexp(SKU_RE))
async def open_product_from_inline_sku(message: Message, db: Database, state: FSMContext):


    sku = _parse_sku_from_message(message.text)
    if not sku:
        return

    products_repo = ProductsRepo(db)
    product = await products_repo.get_by_sku_any(sku)
    if not product:
        return

    shop = await ShopsRepo(db).get(int(product["shop_id"]))
    if not shop or shop.get("business_type") != "shop":
        return

    # Удаляем только текущее экранное сообщение бота. Inline-сообщение не трогаем.
    await delete_screen(message.bot, message.chat.id, state, db, "client")

    text = _build_product_card_text(product)
    sent = await message.answer(
        text,
        reply_markup=kb_product_card_shop(
            shop_id=int(product["shop_id"]),
            category_id=int(product["category_id"]),
            sku=sku,
        ),
    )
    await set_screen_message_id(state, db, "client", message.chat.id, sent.message_id)
    await state.update_data(
        last_kind="shop",
        last_view={
            "name": "products",
            "shop_id": int(product["shop_id"]),
            "category_id": int(product["category_id"]),
        },
        user_id=message.from_user.id,
    )
    await remember_client_screen(
        state,
        "product_card_shop",
        {"shop_id": int(product["shop_id"]), "sku": sku},
    )


@router.callback_query(F.data == "c:shops")
async def list_shops(cq: CallbackQuery, db: Database, state: FSMContext):
    repo = ShopsRepo(db)
    items = await repo.list_active(business_type="shop")

    if not items:
        await cq.message.edit_text("Магазинов пока нет.", reply_markup=kb_back("order_menu"))
        await cq.answer()
        return

    await state.update_data(last_kind="shop", last_view={"name": "shops_list"})
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "shops", {})
    await cq.message.edit_text("Выберите магазин:", reply_markup=kb_shops_list(items, "shop"))
    await cq.answer()


@router.callback_query(F.data == "c:home")
async def client_home(cq: CallbackQuery, db: Database, state: FSMContext):
    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "main", {})
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Для напоминания сначала удаляем сообщение, потом показываем экран заново.
        await safe_delete_cq_message(cq)
        await show_main_menu(
            bot=cq.bot,
            chat_id=cq.from_user.id,
            state=state,
            db=db,
            bot_kind="client",
            text="Выберите раздел:",
            reply_markup=kb_client_main(),
        )
    else:
        await cq.message.edit_text("Выберите раздел:", reply_markup=kb_client_main())
    await cq.answer()

@router.callback_query(F.data == "c:order_menu")
async def order_menu(cq: CallbackQuery, db: Database, state: FSMContext):
    await clear_state_keep_screen(state, db, "client", cq.from_user.id)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "order_menu", {})
    await cq.message.edit_text("Что будем заказывать?", reply_markup=kb_order_menu())
    await cq.answer()

@router.callback_query(F.data == "c:cart_menu")
async def cart_menu(cq: CallbackQuery, state: FSMContext):
    await state.update_data(last_view={"name": "cart_menu"})
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "cart_menu", {})
    await cq.message.edit_text("Выберите корзину:", reply_markup=kb_cart_menu())
    await cq.answer()

@router.callback_query(F.data == "c:restaurants")
async def list_restaurants(cq: CallbackQuery, db: Database, state: FSMContext):
    repo = ShopsRepo(db)
    items = await repo.list_active(business_type="restaurant")

    if not items:
        await cq.message.edit_text("Ресторанов пока нет.", reply_markup=kb_back("order_menu"))
        await cq.answer()
        return

    await state.update_data(last_kind="restaurant", last_view={"name": "restaurants_list"})
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "restaurants", {})
    await cq.message.edit_text("Выберите ресторан:", reply_markup=kb_shops_list(items, "restaurant"))
    await cq.answer()


@router.callback_query(F.data.startswith("c:pick:"))
async def pick_shop(cq: CallbackQuery, db: Database, state: FSMContext):
    # c:pick:{kind}:{shop_id}
    _, _, kind, shop_id_str = cq.data.split(":", 3)
    shop_id = int(shop_id_str)

    await state.update_data(
        last_kind=kind,
        last_view={"name": "categories", "kind": kind, "shop_id": shop_id},
        user_id=cq.from_user.id,
    )
    await remember_client_screen(state, "categories", {"kind": kind, "shop_id": shop_id})

    await show_categories(cq.message, db, kind, shop_id)
    await cq.answer()


async def show_categories(message: Message, db: Database, kind: str, shop_id: int):
    cats = CategoriesRepo(db)
    categories = await cats.list_for_shop(shop_id, active_only=True)
    if not categories:
        await message.edit_text("Категорий пока нет.", reply_markup=kb_back(f"{kind}_list"))
        return

    title = "Категории магазина:" if kind == "shop" else "Категории ресторана:"
    await message.edit_text(title, reply_markup=kb_categories_list(categories, kind, shop_id))


@router.callback_query(F.data.startswith("c:cat:"))
async def open_category(cq: CallbackQuery, db: Database, state: FSMContext):
    # c:cat:{shop_id}:{category_id}
    _, _, shop_id_str, category_id_str = cq.data.split(":", 3)
    shop_id = int(shop_id_str)
    category_id = int(category_id_str)

    await show_category_products(cq.message, db, state, shop_id, category_id)
    await cq.answer()


async def show_category_products(
    message: Message,
    db: Database,
    state: FSMContext,
    shop_id: int,
    category_id: int,
):
    prod = ProductsRepo(db)
    products = await prod.list_by_category_for_shop(shop_id, category_id, active_only=True)

    if not products:
        data = await state.get_data()
        last_kind = data.get("last_kind")
        if not last_kind:
            shops = ShopsRepo(db)
            shop = await shops.get(shop_id)
            last_kind = shop["business_type"] if shop else None
        back_target = f"categories:{last_kind}:{shop_id}" if last_kind else "order_menu"
        await message.edit_text("В этой категории пока нет товаров.", reply_markup=kb_back(back_target))
        return

    await state.update_data(last_view={"name": "products", "shop_id": shop_id, "category_id": category_id})
    data = await state.get_data()
    kind = data.get("last_kind") or "shop"
    await remember_client_screen(
        state,
        "products",
        {"shop_id": shop_id, "category_id": category_id, "kind": kind},
    )
    products_kb = kb_products_list_shop(products, shop_id, category_id) if kind == "shop" else kb_products_list(products, shop_id, category_id)

    await message.edit_text(
        "Список товаров:",
        reply_markup=products_kb
    )


@router.callback_query(F.data.startswith("c:prod:"))
async def open_product(cq: CallbackQuery, db: Database, state: FSMContext):
    # c:prod:{product_id}
    product_id = int(cq.data.split(":")[2])

    prod = ProductsRepo(db)
    p = await prod.get(product_id)

    if not p:
        text = "Товар не найден."
        markup = kb_back("order_menu")
        # ✅ В inline-режиме cq.message может быть None
        try:
            if cq.message:
                await cq.message.edit_text(text, reply_markup=markup)
            elif cq.inline_message_id:
                await cq.bot.edit_message_text(
                    inline_message_id=cq.inline_message_id,
                    text=text,
                    reply_markup=markup,
                )
        except TelegramBadRequest as e:
            # "message is not modified" — не ошибка для нас
            if "message is not modified" not in str(e):
                raise
        await cq.answer()
        return

    text = _build_product_card_text(p)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "product_card", {"product_id": product_id})

    markup = kb_product_card(
        product_id=product_id,
        shop_id=p["shop_id"],
        category_id=p["category_id"],
    )

    try:
        if cq.message:
            await cq.message.edit_text(text, reply_markup=markup)
        elif cq.inline_message_id:
            # ✅ Это и есть правильный способ обновить inline-сообщение
            await cq.bot.edit_message_text(
                inline_message_id=cq.inline_message_id,
                text=text,
                reply_markup=markup,
            )
        else:
            # Теоретически почти не бывает, но лучше не падать
            await cq.answer("Не удалось открыть товар", show_alert=True)
            return
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

    await cq.answer()




@router.callback_query(F.data.startswith("c:prodsku:"))
async def open_product_by_sku(cq: CallbackQuery, db: Database, state: FSMContext):
    # c:prodsku:{shop_id}:{sku}
    _, _, shop_id_str, sku = cq.data.split(":", 3)
    shop_id = int(shop_id_str)

    shop = await ShopsRepo(db).get(shop_id)
    if not shop or shop.get("business_type") != "shop":
        await safe_edit_text(cq, "Товар не найден.", reply_markup=kb_back("order_menu"))
        await cq.answer()
        return

    prod = ProductsRepo(db)
    p = await prod.get_by_sku(shop_id=shop_id, sku=sku)
    if not p:
        await safe_edit_text(cq, "Товар не найден.", reply_markup=kb_back("order_menu"))
        await cq.answer()
        return

    text = _build_product_card_text(p)
    await state.update_data(user_id=cq.from_user.id)
    await remember_client_screen(state, "product_card_shop", {"shop_id": shop_id, "sku": sku})

    await safe_edit_text(
        cq,
        text,
        reply_markup=kb_product_card_shop(shop_id=shop_id, category_id=p["category_id"], sku=sku),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("c:addsku:"))
async def add_to_cart_by_sku(cq: CallbackQuery, db: Database):
    # c:addsku:{shop_id}:{sku}
    _, _, shop_id_str, sku = cq.data.split(":", 3)
    shop_id = int(shop_id_str)

    shop = await ShopsRepo(db).get(shop_id)
    if not shop or shop.get("business_type") != "shop":
        await cq.answer("Товар не найден", show_alert=True)
        return

    prod = ProductsRepo(db)
    p = await prod.get_by_sku(shop_id=shop_id, sku=sku)
    if not p:
        await cq.answer("Товар не найден", show_alert=True)
        return

    cart = CartRepo(db)
    await cart.add(user_id=cq.from_user.id, product_id=int(p["id"]), qty=1)
    await cq.answer("Добавлено в корзину")

@router.callback_query(F.data.startswith("c:add:"))
async def add_to_cart(cq: CallbackQuery, db: Database):
    # c:add:{product_id}
    product_id = int(cq.data.split(":")[2])

    prod = ProductsRepo(db)
    p = await prod.get(product_id)
    if not p:
        await cq.answer("Товар не найден", show_alert=True)
        return

    cart = CartRepo(db)
    await cart.add(user_id=cq.from_user.id, product_id=product_id, qty=1)

    await cq.answer("Добавлено в корзину")


@router.callback_query(F.data.startswith("c:pickback:"))
async def back_to_categories(cq: CallbackQuery, db: Database):
    # c:pickback:{shop_id}
    shop_id = int(cq.data.split(":")[2])

    # Определяем тип точки, чтобы правильный заголовок показать
    shops = ShopsRepo(db)
    shop = await shops.get(shop_id)
    if not shop:
        await cq.message.edit_text("Точка не найдена.", reply_markup=kb_back("order_menu"))
        await cq.answer()
        return

    cats = CategoriesRepo(db)
    categories = await cats.list_for_shop(shop_id, active_only=True)
    if not categories:
        await cq.message.edit_text("Категорий пока нет.", reply_markup=kb_back("order_menu"))
        await cq.answer()
        return

    title = "Категории магазина:" if shop["business_type"] == "shop" else "Категории ресторана:"
    await cq.message.edit_text(title, reply_markup=kb_categories_list(categories, shop["business_type"], shop_id))
    await cq.answer()


@router.callback_query(F.data.startswith("c:back:"))
async def back(cq: CallbackQuery, db: Database, state: FSMContext):
    parts = cq.data.split(":")
    target = parts[2] if len(parts) > 2 else ""
    data = await state.get_data()

    if target == "from_cart":
        back_parts = parts[3:] if len(parts) > 3 else []
        return_view = _parse_cart_back_target(back_parts) if back_parts else data.get("cart_return_view")
        if (
            return_view
            and return_view.get("name") == "products"
            and return_view.get("shop_id") is not None
            and return_view.get("category_id") is not None
        ):
            await show_category_products(
                cq.message,
                db,
                state,
                return_view.get("shop_id"),
                return_view.get("category_id"),
            )
            await cq.answer()
            return
        if (
            return_view
            and return_view.get("name") == "categories"
            and return_view.get("kind") is not None
            and return_view.get("shop_id") is not None
        ):
            await show_categories(
                cq.message,
                db,
                return_view.get("kind"),
                return_view.get("shop_id"),
            )
            await cq.answer()
            return
        if return_view and return_view.get("name") == "cart_menu":
            await cq.message.edit_text("Выберите корзину:", reply_markup=kb_cart_menu())
            await cq.answer()
            return
        if return_view and return_view.get("name") == "order_menu":
            await cq.message.edit_text("Что будем заказывать?", reply_markup=kb_order_menu())
            await cq.answer()
            return
        if return_view and return_view.get("name") == "shops_list":
            await list_shops(cq, db, state)
            return
        if return_view and return_view.get("name") == "restaurants_list":
            await list_restaurants(cq, db, state)
            return
        await cq.message.edit_text("Что будем заказывать?", reply_markup=kb_order_menu())
        await cq.answer()
        return

    await clear_state_keep_screen(state, db, "client", cq.from_user.id)

    if target == "main":
        await cq.message.edit_text("Выберите раздел:", reply_markup=kb_client_main())
        await cq.answer()
        return

    if target == "shop_list":
        # вернуться в список магазинов
        await cq.message.edit_text("Что будем заказывать?", reply_markup=kb_order_menu())
        await cq.answer()
        return

    if target == "restaurant_list":
        await cq.message.edit_text("Что будем заказывать?", reply_markup=kb_order_menu())
        await cq.answer()
        return

    if target == "order_menu":
        await cq.message.edit_text("Что будем заказывать?", reply_markup=kb_order_menu())
        await cq.answer()
        return

    if target == "categories":
        if len(parts) >= 5:
            kind = parts[3]
            shop_id = int(parts[4])
            await show_categories(cq.message, db, kind, shop_id)
            await cq.answer()
            return

    if target == "cart":
        await render_cart(
            cq.message,
            cq.from_user.id,
            db,
            business_type=data.get("cart_kind"),
            back_target=data.get("cart_back_target"),
        )
        await cq.answer()
        return

    if target == "cart_menu":
        await cq.message.edit_text("Выберите корзину:", reply_markup=kb_cart_menu())
        await cq.answer()
        return

    await cq.answer("Неизвестный переход", show_alert=True)


async def render_cart(
    message,
    user_id: int,
    db: Database,
    business_type: str | None = None,
    back_target: str | None = None,
):
    cart = CartRepo(db)
    items = await cart.list_items(user_id, business_type=business_type)

    if not items:
        await message.edit_text("Корзина пуста.", reply_markup=kb_cart_empty(back_target))
        return

    cart_title = "🧺 Корзина"
    if business_type == "shop":
        cart_title = "🧺 Корзина магазинов"
    if business_type == "restaurant":
        cart_title = "🧺 Корзина ресторанов"

    total = sum(float(i["price"]) * int(i["quantity"]) for i in items)
    text_lines = [f"{cart_title}:"]
    for i in items:
        line_total = float(i["price"]) * int(i["quantity"])
        text_lines.append(f"- {i['name']} x{i['quantity']} = {line_total}")
    text_lines.append(f"\nИтого: {total}")

    await message.edit_text("\n".join(text_lines), reply_markup=kb_cart(items, back_target))


# Фильтр с точным совпадением и префиксом через ":" нужен, чтобы не перехватывать c:cart_inc/dec/del.
@router.callback_query((F.data == "c:cart") | (F.data.startswith("c:cart:")))
async def open_cart(cq: CallbackQuery, db: Database, state: FSMContext):
    data = await state.get_data()
    parts = cq.data.split(":")
    kind = parts[2] if len(parts) > 2 else "auto"
    back_parts = parts[3:] if len(parts) > 3 else []
    if kind == "auto":
        kind = data.get("last_kind") or ""
    business_type = kind if kind in ("shop", "restaurant") else None
    return_view = _parse_cart_back_target(back_parts) or data.get("last_view")
    await state.update_data(
        cart_return_view=return_view,
        cart_back_target=":".join(back_parts) if back_parts else None,
        user_id=cq.from_user.id,
    )
    if business_type:
        await state.update_data(cart_kind=business_type)
    await remember_client_screen(
        state,
        "cart",
        {
            "business_type": business_type,
            "back_target": ":".join(back_parts) if back_parts else None,
        },
    )
    await render_cart(
        cq.message,
        cq.from_user.id,
        db,
        business_type=business_type,
        back_target=":".join(back_parts) if back_parts else None,
    )
    await cq.answer()


@router.callback_query(F.data == "c:noop")
async def noop(cq: CallbackQuery):
    await cq.answer()


@router.callback_query(F.data.startswith("c:search:"))
async def search_prompt(cq: CallbackQuery, state: FSMContext):
    # c:search:{kind}:{shop_id}
    _, _, kind, shop_id_str = cq.data.split(":", 3)
    await state.set_state(ClientCatalogStates.search)
    await state.update_data(search_shop_id=int(shop_id_str), search_kind=kind)
    await cq.message.edit_text(
        "Введите текст для поиска. Я буду показывать результаты по мере ввода.",
        reply_markup=kb_back(f"categories:{kind}:{shop_id_str}"),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("c:at_search:"))
async def inline_search_prompt(cq: CallbackQuery):
    _, _, kind, shop_id_str = cq.data.split(":", 3)
    if kind != "shop":
        await cq.message.edit_text(
            "Inline-поиск доступен только для магазинов.",
            reply_markup=kb_back(f"categories:{kind}:{shop_id_str}"),
        )
        await cq.answer()
        return

    me = await cq.bot.get_me()
    username = me.username or "ваш_бот"
    text = (
        "Чтобы искать через @, откройте любое поле ввода и напишите:\n\n"
        f"@{username} <название товара>\n"
        f"Например: @{username} молоко\n\n"
        "После выбора результата карточка отправится в чат."
    )
    await cq.message.edit_text(
        text,
        reply_markup=kb_inline_search(f"c:back:categories:{kind}:{shop_id_str}"),
    )
    await cq.answer()


@router.message(ClientCatalogStates.search)
async def search_input(message: Message, state: FSMContext, db: Database):
    data = await state.get_data()
    shop_id = int(data.get("search_shop_id") or 0)
    kind = data.get("search_kind") or "shop"
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите текст для поиска.")
        return

    service = SearchService(db)
    results = await service.search_products(shop_id=shop_id, query=query, active_only=True)
    if not results:
        await message.answer("Ничего не найдено. Попробуйте другой запрос.")
        return

    products = [r.product for r in results]
    reply_markup = (
        kb_products_list_shop(products, shop_id, products[0]["category_id"])
        if kind == "shop"
        else kb_products_list(products, shop_id, products[0]["category_id"])
    )
    await message.answer(
        "Найденные товары:",
        reply_markup=reply_markup,
    )


@router.callback_query(F.data.startswith("c:cart_inc:"))
async def cart_inc(cq: CallbackQuery, db: Database, state: FSMContext):
    product_id = int(cq.data.split(":")[2])
    cart = CartRepo(db)
    await cart.add(user_id=cq.from_user.id, product_id=product_id, qty=1)
    await cq.answer("Ок")
    # обновим экран корзины
    data = await state.get_data()
    await render_cart(
        cq.message,
        cq.from_user.id,
        db,
        business_type=data.get("cart_kind"),
        back_target=data.get("cart_back_target"),
    )


@router.callback_query(F.data.startswith("c:cart_dec:"))
async def cart_dec(cq: CallbackQuery, db: Database, state: FSMContext):
    product_id = int(cq.data.split(":")[2])
    cart = CartRepo(db)
    data = await state.get_data()
    items = await cart.list_items(cq.from_user.id, business_type=data.get("cart_kind"))
    current = next((x for x in items if x["product_id"] == product_id), None)
    if not current:
        await cq.answer("Нет в корзине", show_alert=True)
        return
    new_qty = int(current["quantity"]) - 1
    await cart.set_qty(user_id=cq.from_user.id, product_id=product_id, qty=new_qty)
    await cq.answer("Ок")
    await render_cart(
        cq.message,
        cq.from_user.id,
        db,
        business_type=data.get("cart_kind"),
        back_target=data.get("cart_back_target"),
    )


@router.callback_query(F.data.startswith("c:cart_del:"))
async def cart_del(cq: CallbackQuery, db: Database, state: FSMContext):
    product_id = int(cq.data.split(":")[2])
    cart = CartRepo(db)
    await cart.set_qty(user_id=cq.from_user.id, product_id=product_id, qty=0)
    await cq.answer("Удалено")
    data = await state.get_data()
    await render_cart(
        cq.message,
        cq.from_user.id,
        db,
        business_type=data.get("cart_kind"),
        back_target=data.get("cart_back_target"),
    )


@router.callback_query(F.data == "c:checkout")
async def checkout(cq: CallbackQuery, db: Database, state: FSMContext):
    cart = CartRepo(db)
    data = await state.get_data()
    items = await cart.list_items(cq.from_user.id, business_type=data.get("cart_kind"))
    if not items:
        await cq.message.edit_text("Корзина пуста.", reply_markup=kb_back("cart_menu"))
        await cq.answer()
        return

    shop_ids = sorted({int(i["shop_id"]) for i in items})
    await state.update_data(checkout_shop_ids=shop_ids, order_comment="")
    if len(shop_ids) == 1:
        await _render_checkout_confirm(cq, db, state, shop_ids[0], back_cb="c:back:cart")
        return

    # если в корзине товары из разных точек — выбрать
    await cq.message.edit_text(
        "В корзине товары из разных магазинов/ресторанов. Выберите, для какой точки оформить заказ:",
        reply_markup=kb_checkout_choose_shop(shop_ids),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("c:checkout_shop:"))
async def checkout_pick_shop(cq: CallbackQuery, db: Database, state: FSMContext):
    shop_id = int(cq.data.split(":")[2])
    await _render_checkout_confirm(cq, db, state, shop_id, back_cb="c:checkout_back")


@router.callback_query(F.data == "c:checkout_back")
async def checkout_back(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    shop_ids = data.get("checkout_shop_ids") or []
    if shop_ids:
        await cq.message.edit_text(
            "В корзине товары из разных магазинов/ресторанов. Выберите, для какой точки оформить заказ:",
            reply_markup=kb_checkout_choose_shop(shop_ids),
        )
        await cq.answer()
        return
    await cq.message.edit_text("Корзина пуста.", reply_markup=kb_back("cart_menu"))
    await cq.answer()


@router.callback_query(F.data.startswith("c:checkout_confirm:"))
async def checkout_confirm(cq: CallbackQuery, db: Database, state: FSMContext):
    shop_id = int(cq.data.split(":")[2])
    await _create_order_for_shop(cq, db, state, shop_id)


@router.callback_query(F.data == "c:checkout_comment")
async def checkout_comment(cq: CallbackQuery, state: FSMContext, db: Database):
    await set_screen_message_id(state, db, "client", cq.message.chat.id, cq.message.message_id)
    await state.set_state(ClientCatalogStates.waiting_order_comment)
    await cq.message.edit_text("Напишите комментарий к заказу обычным текстом:")
    await cq.answer()


async def _render_checkout_confirm(
    cq: CallbackQuery,
    db: Database,
    state: FSMContext,
    shop_id: int,
    back_cb: str,
):
    await state.update_data(
        checkout_confirm_shop_id=shop_id,
        checkout_confirm_back_cb=back_cb,
    )
    text, reply_markup = await _build_checkout_confirm_payload(
        db=db,
        state=state,
        user_id=cq.from_user.id,
        shop_id=shop_id,
        back_cb=back_cb,
    )
    await cq.message.edit_text(text, reply_markup=reply_markup)
    await cq.answer()


async def _build_checkout_confirm_payload(
    db: Database,
    state: FSMContext,
    user_id: int,
    shop_id: int,
    back_cb: str,
):
    cart = CartRepo(db)
    data = await state.get_data()
    items = await cart.list_items(user_id, business_type=data.get("cart_kind"))
    shop_items = [it for it in items if int(it["shop_id"]) == shop_id]
    if not shop_items:
        return "Корзина пуста для этой точки.", kb_back("cart_menu")
    total = sum(float(i["price"]) * int(i["quantity"]) for i in shop_items)
    lines = ["Подтвердите оформление заказа:"]
    for i in shop_items:
        line_total = float(i["price"]) * int(i["quantity"])
        lines.append(f"- {i['name']} x{i['quantity']} = {line_total}")
    lines.append(f"\nИтого: {total}")
    comment = (data.get("order_comment") or "").strip()
    lines.append("📝 Комментарий:")
    lines.append(comment or "— не добавлен —")
    return (
        "\n".join(lines),
        kb_checkout_confirm(
            confirm_cb=f"c:checkout_confirm:{shop_id}",
            back_cb=back_cb,
        ),
    )


@router.message(ClientCatalogStates.waiting_order_comment)
async def save_order_comment(message: Message, state: FSMContext, db: Database):
    if not message.text:
        await message.answer("Отправьте комментарий текстом.")
        return
    comment = message.text.strip()
    await state.update_data(order_comment=comment)
    await state.set_state(None)

    data = await state.get_data()
    shop_id = data.get("checkout_confirm_shop_id")
    back_cb = data.get("checkout_confirm_back_cb") or "c:back:cart"
    if not shop_id:
        await message.answer("Не удалось обновить комментарий. Попробуйте снова.")
        return

    text, reply_markup = await _build_checkout_confirm_payload(
        db=db,
        state=state,
        user_id=message.from_user.id,
        shop_id=int(shop_id),
        back_cb=back_cb,
    )
    screen_message_id = await get_screen_message_id(state, db, "client", message.chat.id)
    if screen_message_id:
        await message.bot.edit_message_text(
            text=text,
            chat_id=message.chat.id,
            message_id=screen_message_id,
            reply_markup=reply_markup,
        )
    else:
        await message.answer(text, reply_markup=reply_markup)


async def _create_order_for_shop(cq: CallbackQuery, db: Database, state: FSMContext, shop_id: int):
    orders = OrdersRepo(db)
    data = await state.get_data()
    comment = (data.get("order_comment") or "").strip()

    # 1) создаём заказ
    try:
        order_id = await orders.create_order_from_cart(
            shop_id=shop_id,
            client_user_id=cq.from_user.id,
            comment=comment,
        )
    except ValueError:
        await cq.message.edit_text(
            "Не удалось создать заказ: корзина пуста или заказ уже создан для этой точки.",
            reply_markup=kb_back("main"),
        )
        await cq.answer()
        return

    # 2) уведомляем админов точки, но не ломаем оформление заказа при ошибках
    try:
        await notify_admins_new_order(db, order_id=order_id, shop_id=shop_id, storage=state.storage)
    except Exception:
        logger.warning("Не удалось отправить уведомление админам по заказу %s", order_id, exc_info=True)

    # 3) ответ клиенту
    await cq.message.edit_text(
        f"✅ Заказ успешно создан!\nНомер заказа: {order_id}\nСтатус: new",
        reply_markup=kb_after_order(),
    )
    await state.update_data(
        order_comment="",
        checkout_confirm_shop_id=None,
        checkout_confirm_back_cb=None,
    )
    await cq.answer()
