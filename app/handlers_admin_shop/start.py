from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_shop.utils import is_shop_admin
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.order_seen_repo import OrderSeenRepo
from app.services.screen import clear_state_keep_screen
from app.services.chat_screen_controller import ChatScreenController
from app.services.notification_center import remember_admin_prev_target

router = Router()


def kb_admin_main(chat_unread_threads: int = 0, new_orders_count: int = 0):
    chat_text = "💬 Чат"
    if chat_unread_threads > 0:
        chat_text = f"{chat_text} ({chat_unread_threads})"
    orders_text = "📦 Заказы"
    if new_orders_count > 0:
        orders_text = f"{orders_text} ({new_orders_count})"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=orders_text, callback_data="a:orders")],
        [InlineKeyboardButton(text="🧺 Продукты", callback_data="a:products")],
        [InlineKeyboardButton(text="🕓 История",  callback_data="a:history")],
        [InlineKeyboardButton(text="🎁 Акции",    callback_data="a:promos")],
        [InlineKeyboardButton(text=chat_text,    callback_data="a:chat")],
        [InlineKeyboardButton(text="👤 Кабинет",  callback_data="a:cabinet")],
    ])


async def build_admin_shop_main_kb(db: Database, user_id: int) -> InlineKeyboardMarkup:
    unread = await ChatReadsRepo(db).count_unread_orders("admin_shop", user_id)
    new_orders = await OrderSeenRepo(db).count_new_orders("admin_shop", user_id)
    return kb_admin_main(chat_unread_threads=unread, new_orders_count=new_orders)


@router.message(CommandStart())
async def start_cmd(message: Message, db: Database, state: FSMContext):
    if not await is_shop_admin(db, message.from_user.id):
        await message.answer("Нет доступа. Ваш user_id не назначен админом магазина.")
        return

    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
    await remember_admin_prev_target(db, "admin_shop", message.from_user.id, "a:home")
    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=lambda: _render_admin_main(db, message.from_user.id),
        db=db,
        bot_kind="admin_shop",
    )
    await controller.delete_user_message(message)
    await controller.delete_screen()
    await controller.refresh()


@router.callback_query(F.data == "a:home")
async def home(cq, db: Database, state: FSMContext):
    # Быстрый возврат в главное меню
    await clear_state_keep_screen(state, db, "admin_shop", cq.message.chat.id)
    await remember_admin_prev_target(db, "admin_shop", cq.from_user.id, "a:home")
    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.message.chat.id,
        state=state,
        render=lambda: _render_admin_main(db, cq.from_user.id),
        db=db,
        bot_kind="admin_shop",
    )
    await controller.delete_screen()
    await controller.refresh()
    await cq.answer()


async def _render_admin_main(db: Database, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    return "Админ-меню магазина:", await build_admin_shop_main_kb(db, user_id)
