import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_shop.utils import get_admin_shop_ids, is_shop_admin
from app.handlers_admin_shop.start import kb_admin_main
from app.repositories.products_repo import ProductsRepo
from app.repositories.shops_repo import ShopsRepo
from app.services.search_service import SearchService
from app.services.search_utils import normalize_text
from app.config import get_settings
from app.services.screen import clear_state_keep_screen, show_main_menu
from app.repositories.categories_repo import CategoriesRepo


def is_superadmin(user_id: int) -> bool:
    s = get_settings()
    return user_id in set(s.superadmin_ids)


router = Router()
logger = logging.getLogger(__name__)


class ProductStates(StatesGroup):
    add_category = State()
    add_product = State()
    search = State()
    bulk_import = State()


def kb_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главная", callback_data="a:home")]
    ])


def kb_categories(cats: list[dict], user_id: int) -> InlineKeyboardMarkup:
    kb = []
    for c in cats:
        status = "✅" if int(c["is_active"]) == 1 else "⛔"
        kb.append([InlineKeyboardButton(
            text=f"{status} {c['name']}",
            callback_data=f"a:pcat:{c['id']}"
        )])

    kb.append([InlineKeyboardButton(text="🔎 Поиск по товарам", callback_data="a:psearch")])
    if is_superadmin(user_id):
        kb.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="a:paddcat")])
    kb.append([InlineKeyboardButton(text="🏠 Главная", callback_data="a:home")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_products(cat_id: int, items: list[dict]) -> InlineKeyboardMarkup:
    kb = []
    for p in items:
        status = "✅" if int(p["is_active"]) == 1 else "⛔"
        kb.append([InlineKeyboardButton(
            text=f"{status} {p['name']} — {p['price']}",
            callback_data=f"a:pprod:{cat_id}:{p['id']}"
        )])

    kb.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data=f"a:paddprod:{cat_id}")])
    kb.append([InlineKeyboardButton(text="📥 Массовое добавление", callback_data=f"a:bulk:{cat_id}")])
    kb.append([
        InlineKeyboardButton(text="🔙 Категории", callback_data="a:products"),
        InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_product_card(cat_id: int, product_id: int, is_active: int) -> InlineKeyboardMarkup:
    toggle_text = "⛔ Выключить" if int(is_active) == 1 else "✅ Включить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data=f"a:ptoggle:{cat_id}:{product_id}")],
        [
            InlineKeyboardButton(text="🔙 Назад", callback_data=f"a:pcat:{cat_id}"),
            InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
        ],
    ])


def kb_search_results(items: list[dict]) -> InlineKeyboardMarkup:
    kb = []
    for p in items:
        kb.append([InlineKeyboardButton(
            text=f"{p['name']} — {p['price']}",
            callback_data=f"a:pprod:{p['category_id']}:{p['id']}"
        )])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="a:products")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def kb_bulk_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Импортировать", callback_data="a:bulk:confirm")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="a:bulk:cancel")],
    ])


def bulk_format_hint() -> str:
    return (
        "Ожидаемый формат:\n"
        "Название; Цена; Описание (опционально); SKU (опционально)\n"
        "или: Название; Цена; SKU\n"
        "Пример:\n"
        "Банан; 12.5; Спелый банан; SKU-1A2B3C4D"
    )


async def _get_shop_id_for_admin(db: Database, user_id: int) -> int | None:
    shop_ids = await get_admin_shop_ids(db, user_id)
    return shop_ids[0] if shop_ids else None


@router.callback_query(F.data == "a:products")
async def products_root(cq: CallbackQuery, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    shop_id = await _get_shop_id_for_admin(db, cq.from_user.id)
    if not shop_id:
        await cq.message.edit_text("Нет привязанного магазина.", reply_markup=kb_home())
        await cq.answer()
        return

    async with db.conn() as conn:
        shop = await ShopsRepo(db).get(shop_id)
        if not shop:
            await cq.message.edit_text("Магазин не найден.", reply_markup=kb_home())
            await cq.answer()
            return

    cats = await CategoriesRepo(db).list_for_business_type(shop["business_type"], active_only=True)


    if not cats:
        is_root = is_superadmin(cq.from_user.id)
        text = "🧺 Продукты\n\nКатегорий пока нет."
        if is_root:
            text += "\nНажми «➕ Добавить категорию»."

        buttons = []
        if is_root:
            buttons.append([InlineKeyboardButton(text="➕ Добавить категорию", callback_data="a:paddcat")])
        buttons.append([InlineKeyboardButton(text="🏠 Главная", callback_data="a:home")])

        await cq.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
        await cq.answer()
        return

    await cq.message.edit_text("🧺 Категории:", reply_markup=kb_categories(cats, cq.from_user.id))
    await cq.answer()


@router.callback_query(F.data == "a:paddcat")
async def add_category_prompt(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    
    if not is_superadmin(cq.from_user.id):
        await cq.answer("Только супер-админ может добавлять категории.", show_alert=True)
        return

    await state.set_state(ProductStates.add_category)
    await cq.message.edit_text("Введите название категории (например: Овощи):", reply_markup=kb_home())
    await cq.answer()


@router.message(ProductStates.add_category)
async def add_category_save(message: Message, state: FSMContext, db: Database):
    if not await is_shop_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return
    
    if not is_superadmin(message.from_user.id):
        await message.answer("Только супер-админ может добавлять категории.")
        await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
        return

    shop_id = await _get_shop_id_for_admin(db, message.from_user.id)
    if not shop_id:
        await message.answer("Нет привязанного магазина.")
        await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
        await show_main_menu(
            message.bot,
            message.chat.id,
            state,
            db,
            "admin_shop",
            "Админ-меню магазина:",
            kb_admin_main(),
        )
        return

    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Слишком коротко. Введите название категории ещё раз:")
        return

    await CategoriesRepo(db).create(shop_id=shop_id, name=name, sort=0)

    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
    await message.answer("Категория добавлена ✅")
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        db,
        "admin_shop",
        "Админ-меню магазина:",
        kb_admin_main(),
    )


@router.callback_query(F.data.startswith("a:pcat:"))
async def open_category(cq: CallbackQuery, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    shop_id = await _get_shop_id_for_admin(db, cq.from_user.id)
    if not shop_id:
        await cq.message.edit_text("Нет привязанного магазина.", reply_markup=kb_home())
        await cq.answer()
        return

    cat_id = int(cq.data.split(":")[2])

    repo = ProductsRepo(db)
    items = await repo.list_by_category_any(shop_id=shop_id, category_id=cat_id)

    title = f"🧺 Товары в категории #{cat_id}:"
    await cq.message.edit_text(title, reply_markup=kb_products(cat_id, items))
    await cq.answer()


@router.callback_query(F.data.startswith("a:paddprod:"))
async def add_product_prompt(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    cat_id = int(cq.data.split(":")[2])
    await state.set_state(ProductStates.add_product)
    await state.update_data(category_id=cat_id)
    await cq.message.edit_text(
        "Введите товар в формате:\n"
        "Название; Цена\n\n"
        "Пример:\n"
        "Молоко 2.5%; 12.5",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
                InlineKeyboardButton(text="🔙 Назад", callback_data=f"a:pcat:{cat_id}"),
            ],
        ])
    )
    await cq.answer()


@router.message(ProductStates.add_product)
async def add_product_save(message: Message, state: FSMContext, db: Database):
    if not await is_shop_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return

    shop_id = await _get_shop_id_for_admin(db, message.from_user.id)
    if not shop_id:
        await message.answer("Нет привязанного магазина.")
        await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
        await show_main_menu(
            message.bot,
            message.chat.id,
            state,
            db,
            "admin_shop",
            "Админ-меню магазина:",
            kb_admin_main(),
        )
        return

    data = await state.get_data()
    cat_id = int(data["category_id"])

    text = (message.text or "").strip()
    if ";" not in text:
        await message.answer("Неверный формат. Нужно: Название; Цена\nПример: Хлеб; 7")
        return

    name, price_str = [x.strip() for x in text.split(";", 1)]
    try:
        price = float(price_str.replace(",", "."))
    except ValueError:
        await message.answer("Цена должна быть числом. Пример: 12.5")
        return

    repo = ProductsRepo(db)
    await repo.create(shop_id=shop_id, category_id=cat_id, name=name, price=price)

    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
    await message.answer("Товар добавлен ✅")
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        db,
        "admin_shop",
        "Админ-меню магазина:",
        kb_admin_main(),
    )


@router.callback_query(F.data.startswith("a:pprod:"))
async def product_card(cq: CallbackQuery, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    _, _, cat_id_s, prod_id_s = cq.data.split(":")
    cat_id = int(cat_id_s)
    product_id = int(prod_id_s)

    repo = ProductsRepo(db)
    p = await repo.get(product_id)
    if not p:
        await cq.message.edit_text("Товар не найден.", reply_markup=kb_home())
        await cq.answer()
        return

    text = (
        f"📦 {p['name']}\n"
        f"Цена: {p['price']}\n"
        f"Статус: {'✅ Активен' if int(p['is_active'])==1 else '⛔ Выключен'}\n"
    )
    await cq.message.edit_text(text, reply_markup=kb_product_card(cat_id, product_id, p["is_active"]))
    await cq.answer()


@router.callback_query(F.data.startswith("a:ptoggle:"))
async def toggle_product(cq: CallbackQuery, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    _, _, cat_id_s, prod_id_s = cq.data.split(":")
    cat_id = int(cat_id_s)
    product_id = int(prod_id_s)

    shop_id = await _get_shop_id_for_admin(db, cq.from_user.id)
    if not shop_id:
        await cq.answer("Нет магазина", show_alert=True)
        return

    repo = ProductsRepo(db)
    new_state = await repo.toggle_active(shop_id=shop_id, product_id=product_id)
    if new_state is None:
        await cq.answer("Товар не найден", show_alert=True)
        return

    await cq.answer("Готово ✅")
    # перерисуем карточку
    p = await repo.get(product_id)
    text = (
        f"📦 {p['name']}\n"
        f"Цена: {p['price']}\n"
        f"Статус: {'✅ Активен' if int(p['is_active'])==1 else '⛔ Выключен'}\n"
    )
    await cq.message.edit_text(text, reply_markup=kb_product_card(cat_id, product_id, p["is_active"]))


@router.callback_query(F.data == "a:psearch")
async def search_prompt(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    shop_id = await _get_shop_id_for_admin(db, cq.from_user.id)
    if not shop_id:
        await cq.message.edit_text("Нет привязанного магазина.", reply_markup=kb_home())
        await cq.answer()
        return

    await state.set_state(ProductStates.search)
    await state.update_data(search_shop_id=shop_id)
    await cq.message.edit_text("Введите текст для поиска товара:", reply_markup=kb_home())
    await cq.answer()


@router.message(ProductStates.search)
async def search_products(message: Message, state: FSMContext, db: Database):
    if not await is_shop_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return

    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите текст для поиска.")
        return

    data = await state.get_data()
    shop_id = int(data.get("search_shop_id") or 0)

    service = SearchService(db)
    results = await service.search_products(shop_id=shop_id, query=query, active_only=False)
    if not results:
        await message.answer("Ничего не найдено.")
        return

    products = [r.product for r in results]
    await message.answer("Результаты поиска:", reply_markup=kb_search_results(products))


@router.callback_query(F.data.startswith("a:bulk:"))
async def bulk_import_prompt(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await is_shop_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return

    parts = cq.data.split(":")
    action = parts[2] if len(parts) > 2 else ""
    if action == "confirm":
        logger.info("Bulk import confirm pressed by admin %s", cq.from_user.id)
        data = await state.get_data()
        items = data.get("bulk_items") or []
        errors = data.get("bulk_errors") or []
        cat_id = int(data.get("category_id") or 0)
        shop_id = await _get_shop_id_for_admin(db, cq.from_user.id)
        if data.get("bulk_import_started"):
            await cq.answer("Импорт уже запускается.", show_alert=True)
            return
        if not items or not cat_id or not shop_id:
            await cq.message.edit_text("Нет данных для импорта.", reply_markup=kb_home())
            await cq.answer()
            return

        shop = await ShopsRepo(db).get(shop_id)
        if not shop or shop.get("business_type") != "shop":
            await cq.message.edit_text("Массовая загрузка доступна только для магазинов.", reply_markup=kb_home())
            await cq.answer()
            return

        await state.update_data(bulk_import_started=True)
        try:
            await cq.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.warning("Failed to remove bulk import keyboard", exc_info=True)

        try:
            repo = ProductsRepo(db)
            for it in items:
                sku = (it.get("sku") or "").strip().upper()
                if sku:
                    existing_by_sku = await repo.get_by_sku(shop_id=shop_id, sku=sku)
                    if existing_by_sku:
                        await repo.update(
                            product_id=int(existing_by_sku["id"]),
                            name=it["name"],
                            description=it.get("description") or "",
                            price=float(it["price"]),
                        )
                    else:
                        await repo.create(
                            shop_id=shop_id,
                            category_id=cat_id,
                            name=it["name"],
                            price=float(it["price"]),
                            description=it.get("description") or "",
                            sku=sku,
                        )
                    continue

                name_norm = normalize_text(it["name"])
                existing_by_name = await repo.find_by_natural_key(
                    shop_id=shop_id,
                    category_id=cat_id,
                    name_norm=name_norm,
                )
                if existing_by_name:
                    product_id = int(existing_by_name["id"])
                    await repo.update(
                        product_id=product_id,
                        name=it["name"],
                        description=it.get("description") or "",
                        price=float(it["price"]),
                    )
                    await repo.ensure_sku(product_id)
                else:
                    await repo.create(
                        shop_id=shop_id,
                        category_id=cat_id,
                        name=it["name"],
                        price=float(it["price"]),
                        description=it.get("description") or "",
                        sku=None,
                    )
        except Exception:
            logger.error("Bulk import failed for admin %s", cq.from_user.id, exc_info=True)
            await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
            await cq.message.edit_text(
                "Ошибка во время импорта. Проверьте файл и попробуйте снова.",
                reply_markup=kb_admin_main(),
            )
            await cq.answer()
            return

        imported_count = len(items)
        skipped_count = len(errors)
        summary_lines = [
            f"Импортировано: {imported_count} ✅",
            f"Пропущено строк: {skipped_count}",
        ]
        if errors:
            shown = errors[:5]
            summary_lines.append("Ошибки:")
            summary_lines.extend(f"- {err}" for err in shown)
            if len(errors) > 5:
                summary_lines.append(f"... и ещё {len(errors) - 5} ошибок")

        await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
        await cq.message.edit_text("\n".join(summary_lines), reply_markup=kb_admin_main())
        await cq.answer()
        return

    if action == "cancel":
        logger.info("Bulk import canceled by admin %s", cq.from_user.id)
        await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
        await cq.message.edit_text("Импорт отменён.", reply_markup=kb_admin_main())
        await cq.answer()
        return

    if len(parts) == 3:
        try:
            cat_id = int(parts[2])
        except ValueError:
            await cq.answer("Неизвестное действие.", show_alert=True)
            return
        await state.set_state(ProductStates.bulk_import)
        await state.update_data(category_id=cat_id, bulk_import_started=False)
        await cq.message.edit_text(
            "Загрузите CSV файл с товарами.\n"
            "Формат строк: Название; Цена; Описание (опционально); SKU (опционально).",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
                    InlineKeyboardButton(text="🔙 Назад", callback_data=f"a:pcat:{cat_id}"),
                ],
            ]),
        )
        await cq.answer()
        return


@router.message(ProductStates.bulk_import)
async def bulk_import_file(message: Message, state: FSMContext, db: Database):
    from app.services.import_service import parse_products_csv

    if not await is_shop_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return

    if not message.document:
        await message.answer("Отправьте CSV файл документом.")
        return

    filename = (message.document.file_name or "").lower()
    if not filename.endswith(".csv"):
        await message.answer("Нужен CSV файл.\n\n" + bulk_format_hint())
        return

    logger.info("Bulk import file received from admin %s: %s", message.from_user.id, filename)

    file = await message.bot.get_file(message.document.file_id)
    data = await message.bot.download_file(file.file_path)
    content = data.read()

    shop_id = await _get_shop_id_for_admin(db, message.from_user.id)
    shop = await ShopsRepo(db).get(shop_id) if shop_id else None
    if not shop or shop.get("business_type") != "shop":
        await message.answer("Массовая загрузка доступна только для магазинов.")
        return

    preview = parse_products_csv(content)
    errors = preview.errors

    data_state = await state.get_data()
    cat_id = int(data_state.get("category_id") or 0)
    items = list(preview.items)
    if cat_id:
        async with db.conn() as conn:
            cur = await conn.execute(
                "SELECT name_norm FROM products WHERE shop_id=? AND category_id=?",
                (shop_id, cat_id),
            )
            existing = {str(r["name_norm"] or "") for r in await cur.fetchall()}
        filtered_items = []
        for item in items:
            if not (item.sku or "").strip() and item.name and normalize_text(item.name) in existing:
                errors.append(f"Дубликат в базе: {item.name}")
                continue
            filtered_items.append(item)
        items = filtered_items

    if not items:
        errors_text = ""
        if errors:
            errors_text = (
                "Ошибки:\n"
                + "\n".join(errors[:5])
                + ("\n... и ещё ошибки" if len(errors) > 5 else "")
                + "\n\n"
            )
        await message.answer(
            "Файл не содержит новых товаров.\n"
            + errors_text
            + bulk_format_hint()
        )
        return

    await state.update_data(
        bulk_items=[{"name": i.name, "price": i.price, "description": i.description, "sku": i.sku} for i in items],
        bulk_errors=errors,
        bulk_import_started=False,
    )

    preview_lines = []
    for idx, it in enumerate(items[:5], start=1):
        preview_lines.append(f"{idx}. {it.name} — {it.price}")
    if len(items) > 5:
        preview_lines.append(f"... и ещё {len(items) - 5} строк")

    warning_text = ""
    if errors:
        shown = errors[:5]
        warning_lines = ["\nОбнаружены ошибки, они будут пропущены:"]
        warning_lines.extend(f"- {err}" for err in shown)
        if len(errors) > 5:
            warning_lines.append(f"... и ещё {len(errors) - 5} ошибок")
        warning_text = "\n".join(warning_lines)

    await message.answer(
        "Предпросмотр импорта:\n"
        + "\n".join(preview_lines)
        + warning_text,
        reply_markup=kb_bulk_confirm(),
    )
