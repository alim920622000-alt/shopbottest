from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_shop.utils import is_shop_admin
from app.services.screen import clear_state_keep_screen
from app.services.chat_screen_controller import ChatScreenController

router = Router()


def kb_admin_main():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Заказы", callback_data="a:orders")],
        [InlineKeyboardButton(text="🧺 Продукты", callback_data="a:products")],
        [InlineKeyboardButton(text="🕓 История",  callback_data="a:history")],
        [InlineKeyboardButton(text="🎁 Акции",    callback_data="a:promos")],
        [InlineKeyboardButton(text="💬 Чат",    callback_data="a:chat")],
        [InlineKeyboardButton(text="👤 Кабинет",  callback_data="a:cabinet")],
    ])


@router.message(CommandStart())
async def start_cmd(message: Message, db: Database, state: FSMContext):
    if not await is_shop_admin(db, message.from_user.id):
        await message.answer("Нет доступа. Ваш user_id не назначен админом магазина.")
        return

    await clear_state_keep_screen(state, db, "admin_shop", message.chat.id)
    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=lambda: ("Админ-меню магазина:", kb_admin_main()),
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
    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.message.chat.id,
        state=state,
        render=lambda: ("Админ-меню магазина:", kb_admin_main()),
        db=db,
        bot_kind="admin_shop",
    )
    await controller.delete_screen()
    await controller.refresh()
    await cq.answer()
