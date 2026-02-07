from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.db.database import Database
from app.handlers_admin_restaurant.utils import is_restaurant_admin, get_admin_restaurant_ids
from app.handlers_admin_restaurant.start import kb_admin_main
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo
from app.repositories.promotions_repo import PromotionsRepo
from app.repositories.categories_repo import CategoriesRepo
from app.repositories.products_repo import ProductsRepo
from app.repositories.chat_repo import ChatRepo
from app.services.chat_ui import (
    PAGE_SIZE,
    build_chat_screen_kb,
    build_chat_screen_text,
    calc_total_pages,
)
from app.services.chat_reminders import cancel_chat_reminder, schedule_chat_reminder
from app.services.screen import clear_state_keep_screen, show_main_menu, set_screen_message_id
from app.ui.nav import kb_nav

router = Router()

DONE_STATUSES = ["finished", "canceled", "delivered", "ready"]


class PromoStates(StatesGroup):
    add_title = State()
    add_description = State()


class RestaurantChatStates(StatesGroup):
    active = State()


def kb_back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главная", callback_data="r:home")]
    ])


@router.callback_query(F.data == "r:history")
async def history(cq: CallbackQuery, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return
    orders = OrdersRepo(db)
    rows = await orders.list_history_for_shop(ids[0], statuses=DONE_STATUSES)
    if not rows:
        await cq.message.edit_text("История заказов пуста.", reply_markup=kb_back_home())
        await cq.answer()
        return
    kb = []
    for o in rows:
        kb.append([InlineKeyboardButton(text=f"Заказ #{o['id']} ({o['status']})", callback_data=f"r:order:{o['id']}")])
    kb.append([InlineKeyboardButton(text="🏠 Главная", callback_data="r:home")])
    await cq.message.edit_text("🕓 История заказов:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cq.answer()


@router.callback_query(F.data == "r:promos")
async def promos(cq: CallbackQuery, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return
    repo = PromotionsRepo(db)
    promos = await repo.list_for_shop(ids[0])
    kb = []
    for promo in promos:
        kb.append([InlineKeyboardButton(text=promo["title"], callback_data=f"r:promo:{promo['id']}")])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="r:promo_add")])
    kb.append([InlineKeyboardButton(text="🏠 Главная", callback_data="r:home")])
    await cq.message.edit_text("🎁 Акции:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cq.answer()


@router.callback_query(F.data == "r:cabinet")
async def cabinet(cq: CallbackQuery, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return
    shops = ShopsRepo(db)
    shop = await shops.get(ids[0])
    if not shop:
        await cq.message.edit_text("Ресторан не найден.", reply_markup=kb_back_home())
        await cq.answer()
        return
    text = (
        "👤 Кабинет ресторана (только просмотр)\n\n"
        f"Телефон: {shop.get('phone') or '—'}\n"
        f"Адрес: {shop.get('address') or '—'}\n"
        f"Лого: {shop.get('logo_url') or '—'}\n"
        f"О компании: {shop.get('about') or '—'}"
    )
    await cq.message.edit_text(text, reply_markup=kb_back_home())
    await cq.answer()


@router.callback_query(F.data == "r:promo_add")
async def promo_add_start(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(PromoStates.add_title)
    await cq.message.edit_text("Введите название акции:", reply_markup=kb_back_home())
    await cq.answer()


@router.message(PromoStates.add_title)
async def promo_add_title(message: Message, state: FSMContext, db: Database):
    if not await is_restaurant_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("Слишком короткое название.")
        return
    await state.update_data(promo_title=title)
    await state.set_state(PromoStates.add_description)
    await message.answer("Введите описание акции или '-' чтобы пропустить:")


@router.message(PromoStates.add_description)
async def promo_add_description(message: Message, state: FSMContext, db: Database):
    if not await is_restaurant_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""
    data = await state.get_data()
    title = data.get("promo_title") or ""
    ids = await get_admin_restaurant_ids(db, message.from_user.id)
    if not ids:
        await message.answer("Нет доступа.")
        return
    repo = PromotionsRepo(db)
    await repo.create(ids[0], title=title, description=desc)
    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
    await message.answer("Акция добавлена ✅")
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        db,
        "admin_restaurant",
        "Админ-меню ресторана:",
        kb_admin_main(),
    )


@router.callback_query(F.data.startswith("r:promo:"))
async def promo_card(cq: CallbackQuery, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    promo_id = int(cq.data.split(":")[2])
    repo = PromotionsRepo(db)
    promo = await repo.get(promo_id)
    if not promo:
        await cq.message.edit_text("Акция не найдена.", reply_markup=kb_back_home())
        await cq.answer()
        return
    items = await repo.list_items(promo_id)
    lines = [
        f"🎁 {promo['title']}",
        promo.get("description") or "",
        "",
        "Позиции:",
    ]
    if not items:
        lines.append("— пока нет")
    else:
        for it in items:
            lines.append(f"- {it['name']} — {it['price']}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📌 Выбрать позиции", callback_data=f"r:promo_pick:{promo_id}")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="r:promos"),
        ],
    ])
    await cq.message.edit_text("\n".join(lines), reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("r:promo_pick:"))
async def promo_pick_category(cq: CallbackQuery, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    promo_id = int(cq.data.split(":")[2])
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return
    cats = CategoriesRepo(db)
    categories = await cats.list_for_shop(ids[0], active_only=True)
    if not categories:
        await cq.message.edit_text("Нет категорий.", reply_markup=kb_back_home())
        await cq.answer()
        return
    kb = []
    for c in categories:
        kb.append([InlineKeyboardButton(text=c["name"], callback_data=f"r:promo_cat:{promo_id}:{c['id']}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"r:promo:{promo_id}")])
    await cq.message.edit_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cq.answer()


@router.callback_query(F.data.startswith("r:promo_cat:"))
async def promo_pick_product(cq: CallbackQuery, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    _, _, promo_id_str, cat_id_str = cq.data.split(":")
    promo_id = int(promo_id_str)
    cat_id = int(cat_id_str)
    repo = ProductsRepo(db)
    products = await repo.list_by_category(cat_id, active_only=False)
    if not products:
        await cq.message.edit_text("В категории нет позиций.", reply_markup=kb_back_home())
        await cq.answer()
        return
    kb = []
    for p in products:
        kb.append([InlineKeyboardButton(text=p["name"], callback_data=f"r:promo_add_item:{promo_id}:{p['id']}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"r:promo_pick:{promo_id}")])
    await cq.message.edit_text("Выберите позицию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cq.answer()


@router.callback_query(F.data.startswith("r:promo_add_item:"))
async def promo_add_item(cq: CallbackQuery, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    _, _, promo_id_str, product_id_str = cq.data.split(":")
    promo_id = int(promo_id_str)
    product_id = int(product_id_str)
    repo = PromotionsRepo(db)
    await repo.attach_product(promo_id, product_id)
    await cq.answer("Добавлено")
    await cq.message.edit_text("Позиция добавлена в акцию.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
            InlineKeyboardButton(text="🔙 Назад к акции", callback_data=f"r:promo:{promo_id}"),
        ],
    ]))


def kb_chat_list(order_ids: list[int]) -> InlineKeyboardMarkup:
    kb = []
    for oid in order_ids:
        kb.append([InlineKeyboardButton(text=f"Заказ #{oid}", callback_data=f"r:chat:{oid}")])
    kb.append([InlineKeyboardButton(text="🏠 Главная", callback_data="r:home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_chat_nav_rows() -> list[list[InlineKeyboardButton]]:
    nav = kb_nav(home_cb="r:home", back_cb="r:chat")
    return [list(row) for row in nav.inline_keyboard]


@router.callback_query(F.data == "r:chat")
async def chat_list(cq: CallbackQuery, db: Database, state: FSMContext):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    await clear_state_keep_screen(state, db, "admin_restaurant", cq.message.chat.id)
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return
    chat = ChatRepo(db)
    order_ids = await chat.list_order_ids_with_chat(shop_id=ids[0])
    if not order_ids:
        await cq.message.edit_text("Активных чатов нет.", reply_markup=kb_admin_main())
        await cq.answer()
        return
    await cq.message.edit_text("Чаты по заказам:", reply_markup=kb_chat_list(order_ids))
    await cq.answer()


async def render_chat(cq: CallbackQuery, db: Database, order_id: int, page: int) -> None:
    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = calc_total_pages(total_messages, PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (total_pages - page) * PAGE_SIZE
    messages = await chat.list_messages(order_id, limit=PAGE_SIZE, offset=offset)

    text = build_chat_screen_text(order_id, messages, False, "restaurant")
    kb = build_chat_screen_kb(order_id, page, total_pages, "r", kb_chat_nav_rows())
    await cq.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("r:chat:"))
async def open_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cq.data.split(":")[2])
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not order or int(order["shop_id"]) not in ids:
        await cq.message.edit_text("Чат недоступен.", reply_markup=kb_admin_main())
        await cq.answer()
        return
    await cancel_chat_reminder(db, order_id, cq.from_user.id, "admin_restaurant")
    await state.set_state(RestaurantChatStates.active)
    await state.update_data(chat_order_id=order_id, chat_message_id=cq.message.message_id)
    await set_screen_message_id(state, db, "admin_restaurant", cq.message.chat.id, cq.message.message_id)
    await render_chat(cq, db, order_id, page=10**9)
    await cq.answer()


@router.callback_query(F.data.startswith("r:chatp:"))
async def paginate_chat(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_restaurant_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cq.data.split(":")[2])
    page = int(cq.data.split(":")[3])
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not order or int(order["shop_id"]) not in ids:
        await cq.answer("Чат недоступен.", show_alert=True)
        return
    await state.update_data(chat_order_id=order_id, chat_message_id=cq.message.message_id)
    await set_screen_message_id(state, db, "admin_restaurant", cq.message.chat.id, cq.message.message_id)
    await render_chat(cq, db, order_id, page=page)
    await cq.answer()


@router.message(RestaurantChatStates.active)
async def send_chat_message(message: Message, state: FSMContext, db: Database):
    if not await is_restaurant_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Введите сообщение текстом.")
        return
    data = await state.get_data()
    order_id = int(data.get("chat_order_id") or 0)
    orders = OrdersRepo(db)
    order = await orders.get_order(order_id)
    ids = await get_admin_restaurant_ids(db, message.from_user.id)
    if not order or int(order["shop_id"]) not in ids:
        await message.answer("Чат недоступен.")
        return
    chat = ChatRepo(db)
    await chat.add_message(order_id, message.from_user.id, "admin", text)
    await cancel_chat_reminder(db, order_id, message.from_user.id, "admin_restaurant")
    if order.get("client_user_id"):
        await schedule_chat_reminder(db, order_id, int(order["client_user_id"]), "client", text)
    data = await state.get_data()
    chat_message_id = data.get("chat_message_id")
    chat = ChatRepo(db)
    total_messages = await chat.count_messages(order_id)
    total_pages = calc_total_pages(total_messages, PAGE_SIZE)
    page = total_pages
    offset = (total_pages - page) * PAGE_SIZE
    messages = await chat.list_messages(order_id, limit=PAGE_SIZE, offset=offset)
    text = build_chat_screen_text(order_id, messages, False, "restaurant")
    kb = build_chat_screen_kb(order_id, page, total_pages, "r", kb_chat_nav_rows())
    if chat_message_id:
        try:
            await message.bot.edit_message_text(
                text,
                chat_id=message.chat.id,
                message_id=int(chat_message_id),
                reply_markup=kb,
            )
            await set_screen_message_id(state, db, "admin_restaurant", message.chat.id, int(chat_message_id))
        except Exception:
            new_message = await message.answer(text, reply_markup=kb)
            await state.update_data(chat_message_id=new_message.message_id)
            await set_screen_message_id(state, db, "admin_restaurant", message.chat.id, new_message.message_id)
    else:
        new_message = await message.answer(text, reply_markup=kb)
        await state.update_data(chat_message_id=new_message.message_id)
        await set_screen_message_id(state, db, "admin_restaurant", message.chat.id, new_message.message_id)
