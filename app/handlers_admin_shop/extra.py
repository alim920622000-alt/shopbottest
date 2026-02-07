from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from app.db.database import Database
from app.handlers_admin_shop.start import kb_admin_main
from app.handlers_admin_shop.utils import is_shop_admin
from app.handlers_admin_shop.utils import get_admin_shop_ids
from app.repositories.orders_repo import OrdersRepo
from app.repositories.shops_repo import ShopsRepo
from app.repositories.promotions_repo import PromotionsRepo
from app.repositories.categories_repo import CategoriesRepo
from app.repositories.products_repo import ProductsRepo
from app.services.screen import clear_state_keep_screen, show_main_menu

router = Router()

DONE_STATUSES = ["ready", "canceled", "finished", "delivered"]

class PromoStates(StatesGroup):
    add_title = State()
    add_description = State()

def kb_back_home() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главная", callback_data="a:home")]
    ])

async def _guard_admin(db: Database, user_id: int) -> bool:
    return await is_shop_admin(db, user_id)

#@router.callback_query(F.data == "a:home")
#async def home(cq: CallbackQuery, db: Database):
#    if not await _guard_admin(db, cq.from_user.id):
 #       await cq.answer("Нет доступа", show_alert=True)
  #      return
   # await cq.message.edit_text("Админ-меню магазина:", reply_markup=kb_admin_main())
    #await cq.answer()

@router.callback_query(F.data == "a:history")
async def history(cq: CallbackQuery, db: Database):
    if not await _guard_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not shop_ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return

    orders = OrdersRepo(db)
    rows = await orders.list_history_for_shop(shop_ids[0], statuses=DONE_STATUSES)
    if not rows:
        await cq.message.edit_text("История заказов пуста.", reply_markup=kb_back_home())
        await cq.answer()
        return

    kb = []
    for o in rows:
        kb.append([InlineKeyboardButton(text=f"Заказ #{o['id']} ({o['status']})", callback_data=f"a:order:{o['id']}")])
    kb.append([InlineKeyboardButton(text="🏠 Главная", callback_data="a:home")])
    await cq.message.edit_text("🕓 История заказов:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cq.answer()

@router.callback_query(F.data == "a:promos")
async def promos(cq: CallbackQuery, db: Database):
    if not await _guard_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not shop_ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return

    repo = PromotionsRepo(db)
    promos = await repo.list_for_shop(shop_ids[0])
    kb = []
    for promo in promos:
        kb.append([InlineKeyboardButton(text=promo["title"], callback_data=f"a:promo:{promo['id']}")])
    kb.append([InlineKeyboardButton(text="➕ Добавить", callback_data="a:promo_add")])
    kb.append([InlineKeyboardButton(text="🏠 Главная", callback_data="a:home")])
    await cq.message.edit_text("🎁 Акции:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cq.answer()

@router.callback_query(F.data == "a:cabinet")
async def cabinet(cq: CallbackQuery, db: Database):
    if not await _guard_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not shop_ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return

    shops = ShopsRepo(db)
    shop = await shops.get(shop_ids[0])
    if not shop:
        await cq.message.edit_text("Магазин не найден.", reply_markup=kb_back_home())
        await cq.answer()
        return

    text = (
        "👤 Кабинет магазина (только просмотр)\n\n"
        f"Телефон: {shop.get('phone') or '—'}\n"
        f"Адрес: {shop.get('address') or '—'}\n"
        f"Лого: {shop.get('logo_url') or '—'}\n"
        f"О компании: {shop.get('about') or '—'}"
    )
    await cq.message.edit_text(text, reply_markup=kb_back_home())
    await cq.answer()


@router.callback_query(F.data == "a:promo_add")
async def promo_add_start(cq: CallbackQuery, state: FSMContext, db: Database):
    if not await _guard_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    await state.set_state(PromoStates.add_title)
    await cq.message.edit_text("Введите название акции:", reply_markup=kb_back_home())
    await cq.answer()


@router.message(PromoStates.add_title)
async def promo_add_title(message: Message, state: FSMContext, db: Database):
    if not await _guard_admin(db, message.from_user.id):
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
    if not await _guard_admin(db, message.from_user.id):
        await message.answer("Нет доступа.")
        return
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""
    data = await state.get_data()
    title = data.get("promo_title") or ""
    shop_ids = await get_admin_shop_ids(db, message.from_user.id)
    if not shop_ids:
        await message.answer("Нет доступа.")
        return
    repo = PromotionsRepo(db)
    await repo.create(shop_ids[0], title=title, description=desc)
    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
    await message.answer("Акция добавлена ✅")
    await show_main_menu(
        message.bot,
        message.chat.id,
        state,
        db,
        "admin_shop",
        "Админ-меню магазина:",
        kb_admin_main(),
    )


@router.callback_query(F.data.startswith("a:promo:"))
async def promo_card(cq: CallbackQuery, db: Database):
    if not await _guard_admin(db, cq.from_user.id):
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
        [InlineKeyboardButton(text="📌 Выбрать позиции", callback_data=f"a:promo_pick:{promo_id}")],
        [
            InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
            InlineKeyboardButton(text="🔙 Назад", callback_data="a:promos"),
        ],
    ])
    await cq.message.edit_text("\n".join(lines), reply_markup=kb)
    await cq.answer()


@router.callback_query(F.data.startswith("a:promo_pick:"))
async def promo_pick_category(cq: CallbackQuery, db: Database):
    if not await _guard_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    promo_id = int(cq.data.split(":")[2])
    shop_ids = await get_admin_shop_ids(db, cq.from_user.id)
    if not shop_ids:
        await cq.message.edit_text("Нет доступа.", reply_markup=kb_back_home())
        await cq.answer()
        return
    cats = CategoriesRepo(db)
    shop = await ShopsRepo(db).get(shop_ids[0])
    categories = await cats.list_for_business_type(shop["business_type"], active_only=True)

    if not categories:
        await cq.message.edit_text("Нет категорий для выбора.", reply_markup=kb_back_home())
        await cq.answer()
        return
    kb = []
    for c in categories:
        kb.append([InlineKeyboardButton(text=c["name"], callback_data=f"a:promo_cat:{promo_id}:{c['id']}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"a:promo:{promo_id}")])
    await cq.message.edit_text("Выберите категорию:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cq.answer()


@router.callback_query(F.data.startswith("a:promo_cat:"))
async def promo_pick_product(cq: CallbackQuery, db: Database):
    if not await _guard_admin(db, cq.from_user.id):
        await cq.answer("Нет доступа", show_alert=True)
        return
    _, _, promo_id_str, cat_id_str = cq.data.split(":")
    promo_id = int(promo_id_str)
    cat_id = int(cat_id_str)
    repo = ProductsRepo(db)
    products = await repo.list_by_category(cat_id, active_only=False)
    if not products:
        await cq.message.edit_text("В категории нет товаров.", reply_markup=kb_back_home())
        await cq.answer()
        return
    kb = []
    for p in products:
        kb.append([InlineKeyboardButton(text=p["name"], callback_data=f"a:promo_add_item:{promo_id}:{p['id']}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"a:promo_pick:{promo_id}")])
    await cq.message.edit_text("Выберите товар для акции:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await cq.answer()


@router.callback_query(F.data.startswith("a:promo_add_item:"))
async def promo_add_item(cq: CallbackQuery, db: Database):
    if not await _guard_admin(db, cq.from_user.id):
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
            InlineKeyboardButton(text="🏠 Главная", callback_data="a:home"),
            InlineKeyboardButton(text="🔙 Назад к акции", callback_data=f"a:promo:{promo_id}"),
        ],
    ]))
