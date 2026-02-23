from app.repositories.shops_repo import ShopsRepo
from app.config import get_settings
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from aiogram.types import Message
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from app.services.pagination import calc_page, pager_row
from aiogram.types import InlineKeyboardButton

from app.db.database import Database
from app.handlers_admin_restaurant.utils import get_admin_restaurant_ids
from app.repositories.categories_repo import CategoriesRepo
from app.repositories.products_repo import ProductsRepo
from app.services.search_utils import normalize_text, build_keywords
from app.services.screen import clear_state_keep_screen
from app.services.notification_center import remember_admin_prev_target

PAGE_SIZE = 8
router = Router()
class ProductFSM(StatesGroup):
    add_name = State()
    add_price = State()
    add_desc = State()

    edit_name = State()
    edit_price = State()
    edit_desc = State()
    
    add_category = State()
    

def is_superadmin(user_id: int) -> bool:
    s = get_settings()
    return user_id in set(s.superadmin_ids)
    
    
def nav(home_cb: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏠 Главная", callback_data=home_cb),
        InlineKeyboardButton(text="🔙 Назад", callback_data=back_cb),
    ]])


def kb_cancel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="r:cancel")]
    ])


def kb_categories(
    categories: list[dict],
    restaurant_id: int,
    user_id: int,
    *,
    include_add: bool = True,
    include_nav: bool = True,
) -> InlineKeyboardMarkup:
    kb: list[list[InlineKeyboardButton]] = []

    for c in categories:
        kb.append([InlineKeyboardButton(
            text=c["name"],
            callback_data=f"r:cat:{restaurant_id}:{c['id']}"
        )])

    if include_add and is_superadmin(user_id):
        kb.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="r:addcat")])

    if include_nav:
        kb.append([
            InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def parse_triple_name(text: str) -> tuple[str, str, str] | None:
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    data: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().lower()
        v = v.strip()
        if k in ("ru", "uz", "tj") and v:
            data[k] = v
    if "ru" in data and "uz" in data and "tj" in data:
        return data["ru"], data["uz"], data["tj"]
    return None


def kb_products(products: list[dict], restaurant_id: int, category_id: int) -> InlineKeyboardMarkup:
    kb = []
    for p in products:
        status = "✅" if int(p.get("is_active", 1)) == 1 else "⛔"
        kb.append([InlineKeyboardButton(
            text=f"{status} {p['name']} — {p['price']}",
            callback_data=f"r:prod:{restaurant_id}:{category_id}:{p['id']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_product_card(restaurant_id: int, category_id: int, product_id: int, is_active: int) -> InlineKeyboardMarkup:
    toggle_text = "⛔ Деактивировать" if is_active == 1 else "✅ Активировать"
    kb = [
        [InlineKeyboardButton(text="✏️ Изменить название", callback_data=f"r:edit_name:{product_id}")],
        [InlineKeyboardButton(text="💰 Изменить цену", callback_data=f"r:edit_price:{product_id}")],
        [InlineKeyboardButton(text="📝 Изменить описание", callback_data=f"r:edit_desc:{product_id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"r:toggle:{product_id}")],
        
        [InlineKeyboardButton(
            text="◀️ К списку позиций",
            callback_data=f"r:cat:{restaurant_id}:{category_id}"
        )],

        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"r:cat:{restaurant_id}:{category_id}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def render_products_list(message, db: Database, restaurant_id: int, category_id: int):
    prod = ProductsRepo(db)
    products = await prod.list_by_category(category_id, active_only=False)

    try:
        await message.edit_text(
            "Позиции в категории:",
            reply_markup=kb_products(products, restaurant_id, category_id),
        )
    except TelegramBadRequest as e:
        # Telegram ругается, если текст и клавиатура не изменились
        if "message is not modified" in str(e):
            return
        raise


async def render_products_list_edit(
    bot,
    chat_id: int,
    message_id: int,
    db: Database,
    restaurant_id: int,
    category_id: int,
):
    prod = ProductsRepo(db)
    products = await prod.list_by_category(category_id, active_only=False)

    try:
        await bot.edit_message_text(
            "Позиции в категории:",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=kb_products(products, restaurant_id, category_id),
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            return
        raise


async def render_product_card_edit(
    bot,
    chat_id: int,
    message_id: int,
    db: Database,
    restaurant_id: int,
    category_id: int,
    product_id: int
):
    prod = ProductsRepo(db)
    p = await prod.get(product_id)
    if not p:
        await bot.edit_message_text(
            "Позиция не найдена.",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=nav("r:home", f"r:cat:{restaurant_id}:{category_id}")
        )
        return

    is_active = int(p.get("is_active", 1))
    text = f"{p['name']}\nЦена: {p['price']}\n"
    if p.get("description"):
        text += f"\nОписание:\n{p['description']}\n"
    text += f"\nАктивна: {'да' if is_active == 1 else 'нет'}"

    await bot.edit_message_text(
        text,
        chat_id=chat_id,
        message_id=message_id,
        reply_markup=kb_product_card(restaurant_id, category_id, product_id, is_active),
    )



@router.callback_query(F.data.startswith("r:add:"))
async def add_product_start(cq: CallbackQuery, state: FSMContext):
    # r:add:{restaurant_id}:{category_id}
    _, _, restaurant_id_str, category_id_str = cq.data.split(":", 3)
    await state.update_data(
        restaurant_id=int(restaurant_id_str),
        category_id=int(category_id_str),
        origin_chat_id=cq.message.chat.id,
        origin_message_id=cq.message.message_id,
    )
    await state.set_state(ProductFSM.add_name)

    await cq.message.edit_text("Введите название новой позиции:", reply_markup=kb_cancel())
    await cq.answer()


@router.message(StateFilter(ProductFSM.add_name))
async def add_product_name(message: Message, state: FSMContext, db: Database):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Введите название:")
        return

    await state.update_data(name=name)
    await state.set_state(ProductFSM.add_price)
    await message.answer("Введите цену (например 25.50):", reply_markup=None)


@router.message(StateFilter(ProductFSM.add_price))
async def add_product_price(message: Message, state: FSMContext, db: Database):
    raw = (message.text or "").strip().replace(",", ".")
    try:
        price = float(raw)
        if price < 0:
            raise ValueError()
    except Exception:
        await message.answer("Неверный формат цены. Введите число, например 25.50:")
        return

    await state.update_data(price=price)
    await state.set_state(ProductFSM.add_desc)
    await message.answer("Введите описание или отправьте '-' чтобы пропустить:")
    return
    

@router.message(StateFilter(ProductFSM.add_desc))
async def add_product_desc(message: Message, state: FSMContext, db: Database):
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""  # пропуск описания
    # пустое описание тоже разрешаем

    data = await state.get_data()
    restaurant_id = int(data["restaurant_id"])
    category_id = int(data["category_id"])
    name = (data["name"] or "").strip()
    price = float(data["price"])

    # сохраняем позицию
    async with db.conn() as conn:
        await conn.execute(
            """
            INSERT INTO products (shop_id, category_id, name, description, price, is_active, name_norm, keywords_norm)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (restaurant_id, category_id, name, desc, price, normalize_text(name), build_keywords(name, desc)),
        )
        await conn.commit()

    # ВАЖНО: очищаем FSM, чтобы не спрашивало описание снова
    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)

    # Чтобы кнопки были ВНИЗУ, делаем новый список сообщением (а не edit старого)
    prod = ProductsRepo(db)
    products = await prod.list_by_category(category_id, active_only=False)

    await message.answer(
        "Позиции в категории:",
        reply_markup=kb_products(products, restaurant_id, category_id),
    )

    # (опционально) чистим сообщение пользователя с описанием
    try:
        await message.delete()
    except Exception:
        pass


@router.callback_query(F.data.startswith("r:edit_name:"))
async def edit_name_start(cq: CallbackQuery, state: FSMContext, db: Database):
    product_id = int(cq.data.split(":")[2])
    prod = ProductsRepo(db)
    p = await prod.get(product_id)
    if not p:
        await cq.answer("Не найдено", show_alert=True)
        return
    await state.update_data(
        product_id=product_id,
        restaurant_id=int(p["shop_id"]),
        category_id=int(p["category_id"]),
        origin_chat_id=cq.message.chat.id,
        origin_message_id=cq.message.message_id,
    )
    await state.set_state(ProductFSM.edit_name)
    await cq.message.edit_text(f"Текущее название: {p['name']}\nВведите новое название:", reply_markup=kb_cancel())
    await cq.answer()


@router.callback_query(F.data.startswith("r:edit_price:"))
async def edit_price_start(cq: CallbackQuery, state: FSMContext, db: Database):
    product_id = int(cq.data.split(":")[2])
    prod = ProductsRepo(db)
    p = await prod.get(product_id)
    if not p:
        await cq.answer("Не найдено", show_alert=True)
        return
    await state.update_data(
        product_id=product_id,
        restaurant_id=int(p["shop_id"]),
        category_id=int(p["category_id"]),
        origin_chat_id=cq.message.chat.id,
        origin_message_id=cq.message.message_id,
    )
    await state.set_state(ProductFSM.edit_price)
    await cq.message.edit_text(f"Текущая цена: {p['price']}\nВведите новую цену (например 25.50):", reply_markup=kb_cancel())
    await cq.answer()


@router.callback_query(F.data.startswith("r:edit_desc:"))
async def edit_desc_start(cq: CallbackQuery, state: FSMContext, db: Database):
    product_id = int(cq.data.split(":")[2])
    prod = ProductsRepo(db)
    p = await prod.get(product_id)
    if not p:
        await cq.answer("Не найдено", show_alert=True)
        return
    await state.update_data(
        product_id=product_id,
        restaurant_id=int(p["shop_id"]),
        category_id=int(p["category_id"]),
        origin_chat_id=cq.message.chat.id,
        origin_message_id=cq.message.message_id,
    )
    await state.set_state(ProductFSM.edit_desc)
    cur = p.get("description") or ""
    await cq.message.edit_text(f"Текущее описание:\n{cur}\n\nВведите новое описание или '-' чтобы очистить:", reply_markup=kb_cancel())
    await cq.answer()


@router.message(StateFilter(ProductFSM.edit_name))
async def edit_name_apply(message: Message, state: FSMContext, db: Database):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Название не может быть пустым. Введите новое название:")
        return

    data = await state.get_data()
    product_id = int(data["product_id"])
    restaurant_id = int(data["restaurant_id"])
    category_id = int(data["category_id"])
    chat_id = int(data["origin_chat_id"])
    msg_id = int(data["origin_message_id"])

    prod = ProductsRepo(db)
    await prod.update(product_id, name=name)

    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)

    await render_product_card_edit(
        message.bot,
        chat_id,
        msg_id,
        db,
        restaurant_id,
        category_id,
        product_id,
    )

    try:
        await message.delete()
    except Exception:
        pass


@router.message(StateFilter(ProductFSM.edit_price))
async def edit_price_apply(message: Message, state: FSMContext, db: Database):
    raw = (message.text or "").strip().replace(",", ".")
    try:
        price = float(raw)
        if price < 0:
            raise ValueError()
    except Exception:
        await message.answer("Неверный формат цены. Введите число, например 25.50:")
        return

    data = await state.get_data()
    product_id = int(data["product_id"])
    restaurant_id = int(data["restaurant_id"])
    category_id = int(data["category_id"])
    chat_id = int(data["origin_chat_id"])
    msg_id = int(data["origin_message_id"])

    prod = ProductsRepo(db)
    await prod.update(product_id, price=price)

    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)

    await render_product_card_edit(
        message.bot,
        chat_id,
        msg_id,
        db,
        restaurant_id,
        category_id,
        product_id,
    )

    # необязательно, но чистит чат
    try:
        await message.delete()
    except Exception:
        pass



@router.message(StateFilter(ProductFSM.edit_desc))
async def edit_desc_apply(message: Message, state: FSMContext, db: Database):
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""

    data = await state.get_data()
    product_id = int(data["product_id"])
    restaurant_id = int(data["restaurant_id"])
    category_id = int(data["category_id"])
    chat_id = int(data["origin_chat_id"])
    msg_id = int(data["origin_message_id"])

    prod = ProductsRepo(db)
    await prod.update(product_id, description=desc)

    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)

    await render_product_card_edit(
        message.bot,
        chat_id,
        msg_id,
        db,
        restaurant_id,
        category_id,
        product_id,
    )

    try:
        await message.delete()
    except Exception:
        pass

@router.callback_query(F.data.startswith("r:cats:p:"))
async def list_categories_page(cq: CallbackQuery, db: Database, state: FSMContext):
    page = int(cq.data.split(":")[-1])
    await list_categories_render(cq, db, state, page=page)


@router.callback_query(F.data == "r:cats")
async def list_categories(cq: CallbackQuery, db: Database, state: FSMContext):
    await list_categories_render(cq, db, state, page=0)


async def list_categories_render(cq: CallbackQuery, db: Database, state: FSMContext, page: int):
    # сохранить "назад" и доступ как было
    await remember_admin_prev_target(db, "admin_restaurant", cq.from_user.id, "r:cats")

    ids = await get_admin_restaurant_ids(db, cq.from_user.id)
    if not ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=nav("r:home", "r:back:main"))
        await cq.answer()
        return

    restaurant_id = ids[0]  # MVP: первый ресторан админа

    cats = CategoriesRepo(db)
    shop = await ShopsRepo(db).get(restaurant_id)
    business_type = shop["business_type"]
    
    categories = await cats.list_for_business_type(
        business_type,
        active_only=False
    )


    if not categories:
        await cq.message.edit_text(
            "В ресторане пока нет категорий (создаёт суперадмин).",
            reply_markup=nav("r:home", "r:back:main")
        )
        await cq.answer()
        return

    # пагинация
    total = len(categories)
    pi = calc_page(total=total, page=page, page_size=PAGE_SIZE)
    page_items = categories[pi.offset: pi.offset + pi.limit]

    kb = kb_categories(page_items, restaurant_id, cq.from_user.id, include_add=False, include_nav=False)

    # 1) пагинация сразу после списка
    pager = pager_row("r:cats", pi.page, pi.total_pages)
    if pager:
        kb.inline_keyboard.append(pager)
    
    # 2) добавить категорию
    if is_superadmin(cq.from_user.id):
        kb.inline_keyboard.append([
            InlineKeyboardButton(text="➕ Добавить категорию", callback_data="r:addcat")
        ])
    
    # 3) главная/назад в самом низу
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="r:back:main"),
    ])



    await cq.message.edit_text("Выберите категорию:", reply_markup=kb)
    await cq.answer()
    
    
@router.callback_query(F.data == "noop")
async def noop(cq: CallbackQuery):
    await cq.answer()


@router.callback_query(F.data == "r:addcat")
async def add_category_prompt(cq: CallbackQuery, state: FSMContext):
    if not is_superadmin(cq.from_user.id):
        await cq.answer("Только супер-админ может добавлять категории.", show_alert=True)
        return

    await state.set_state(ProductFSM.add_category)
    await cq.message.edit_text(
        "Введите 3 строки:\n"
        "RU: ...\n"
        "UZ: ...\n"
        "TJ: ...\n\n"
        "Пример:\n"
        "RU: Овощи\n"
        "UZ: Sabzavot\n"
        "TJ: Сабзавот",
        reply_markup=kb_cancel(),
    )
    await cq.answer()

@router.message(StateFilter(ProductFSM.add_category))
async def add_category_save(message: Message, state: FSMContext, db: Database):
    if not is_superadmin(message.from_user.id):
        await message.answer("Только супер-админ может добавлять категории.")
        await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
        return

    raw = (message.text or "").strip()
    parsed = parse_triple_name(raw)
    if not parsed:
        await message.answer("Неверный формат. Введите 3 строки:\nRU: ...\nUZ: ...\nTJ: ...")
        return

    name_ru, name_uz, name_tj = parsed

    ids = await get_admin_restaurant_ids(db, message.from_user.id)
    if not ids:
        await message.answer("Нет доступа.")
        await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
        return

    restaurant_id = int(ids[0])  # как shop_id ресторана

    await CategoriesRepo(db).create(
        shop_id=restaurant_id,
        name_ru=name_ru,
        name_uz=name_uz,
        name_tj=name_tj,
        sort=0,
    )

    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
    await message.answer("Категория добавлена ✅\nОткройте «Меню → Категории» заново.")


@router.callback_query(F.data.startswith("r:cat:") & F.data.contains(":p:"))
async def open_category_page(cq: CallbackQuery, db: Database):
    parts = cq.data.split(":")
    restaurant_id = int(parts[2])
    category_id = int(parts[3])
    page = int(parts[5])
    await render_category_products(cq, db, restaurant_id, category_id, page)
    await cq.answer()


async def render_category_products(cq: CallbackQuery, db: Database, restaurant_id: int, category_id: int, page: int):
    prod = ProductsRepo(db)
    total = await prod.count_by_category_any(shop_id=restaurant_id, category_id=category_id)
    pi = calc_page(total=total, page=page, page_size=PAGE_SIZE)
    products = await prod.list_by_category_any_page(shop_id=restaurant_id, category_id=category_id, limit=pi.limit, offset=pi.offset)

    kb = kb_products(products, restaurant_id, category_id)
    pager = pager_row(f"r:cat:{restaurant_id}:{category_id}", pi.page, pi.total_pages)
    if pager:
        kb.inline_keyboard.append(pager)
    kb.inline_keyboard.append([InlineKeyboardButton(text="➕ Добавить позицию", callback_data=f"r:add:{restaurant_id}:{category_id}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data=f"r:refresh:{restaurant_id}:{category_id}")])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="r:cats"),
    ])

    await cq.message.edit_text("Позиции в категории:", reply_markup=kb)

@router.callback_query(F.data.startswith("r:cat:"))
async def open_category(cq: CallbackQuery, db: Database):
    # r:cat:{restaurant_id}:{category_id}
    #if ":p:" in cq.data:
     #   return
    _, _, restaurant_id_str, category_id_str = cq.data.split(":", 3)
    restaurant_id = int(restaurant_id_str)
    category_id = int(category_id_str)

    await render_category_products(cq, db, restaurant_id, category_id, 0)
    await cq.answer()


@router.callback_query(F.data.startswith("r:prod:"))
async def open_product(cq: CallbackQuery, db: Database):
    # r:prod:{restaurant_id}:{category_id}:{product_id}
    parts = cq.data.split(":")
    restaurant_id = int(parts[2])
    category_id = int(parts[3])
    product_id = int(parts[4])

    prod = ProductsRepo(db)
    p = await prod.get(product_id)
    if not p:
        await cq.message.edit_text("Позиция не найдена.", reply_markup=nav("r:home", f"r:cat:{restaurant_id}:{category_id}"))
        await cq.answer()
        return

    is_active = int(p.get("is_active", 1))
    text = f"{p['name']}\nЦена: {p['price']}\n"
    if p.get("description"):
        text += f"\nОписание:\n{p['description']}\n"
    text += f"\nАктивна: {'да' if is_active == 1 else 'нет'}"

    await cq.message.edit_text(
        text,
        reply_markup=kb_product_card(restaurant_id, category_id, product_id, is_active)
    )
    await cq.answer()


@router.callback_query(F.data == "r:cancel")
async def cancel_fsm(cq: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    await clear_state_keep_screen(state, db, "admin_restaurant", cq.message.chat.id)

    # если знаем, откуда пришли — возвращаем в список позиций категории
    restaurant_id = data.get("restaurant_id")
    category_id = data.get("category_id")
    if restaurant_id and category_id:
        await cq.message.edit_text(
            "Действие отменено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="◀️ К списку позиций", callback_data=f"r:cat:{restaurant_id}:{category_id}"),
                InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
            ]])
        )
    else:
        await cq.message.edit_text(
            "Действие отменено.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🏠 Главная", callback_data="r:home"),
                InlineKeyboardButton(text="🔙 Назад", callback_data="r:cats"),
            ]])
        )

    await cq.answer()


@router.callback_query(F.data.startswith("r:refresh:"))
async def refresh_list(cq: CallbackQuery, db: Database):
    _, _, restaurant_id_str, category_id_str = cq.data.split(":", 3)
    restaurant_id = int(restaurant_id_str)
    category_id = int(category_id_str)

    await render_products_list(cq.message, db, restaurant_id, category_id)
    await cq.answer("Ок")


@router.callback_query(F.data.startswith("r:toggle:"))
async def toggle_product(cq: CallbackQuery, db: Database):
    product_id = int(cq.data.split(":")[2])
    prod = ProductsRepo(db)
    p = await prod.get(product_id)
    if not p:
        await cq.answer("Не найдено", show_alert=True)
        return

    new_active = 0 if int(p.get("is_active", 1)) == 1 else 1
    # предполагаем, что в ProductsRepo есть метод set_active; если нет — добавим ниже
    if hasattr(prod, "set_active"):
        await prod.set_active(product_id, new_active)
    else:
        async with db.conn() as conn:
            await conn.execute("UPDATE products SET is_active=? WHERE id=?", (new_active, product_id))
            await conn.commit()

    await cq.answer("Ок")
    # обновим карточку (перерисуем)
    # безопасно: просто попросим пользователя нажать назад/открыть заново
    await cq.message.edit_text("Статус изменён. Откройте позицию заново.", reply_markup=nav("r:home", "r:cats"))
