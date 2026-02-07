from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_restaurant.utils import is_restaurant_admin
from app.services.screen import clear_state_keep_screen
from app.services.chat_screen_controller import ChatScreenController

router = Router()


def kb_admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍽 Заказы", callback_data="r:orders")],
        [InlineKeyboardButton(text="🧾 Меню", callback_data="r:cats")],
        [InlineKeyboardButton(text="🕓 История", callback_data="r:history")],
        [InlineKeyboardButton(text="🎁 Акции", callback_data="r:promos")],
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="r:cabinet")],
        [InlineKeyboardButton(text="💬 Чат", callback_data="r:chat")],
    ])


@router.message(CommandStart())
async def start_cmd(message: Message, db: Database, state: FSMContext):
    if not await is_restaurant_admin(db, message.from_user.id):
        await message.answer("Нет доступа. Ваш user_id не назначен админом ресторана.")
        return
    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=lambda: ("Админ-меню ресторана:", kb_admin_main()),
        db=db,
        bot_kind="admin_restaurant",
    )
    await controller.delete_user_message(message)
    await controller.delete_screen()
    await controller.refresh()


@router.callback_query(F.data == "r:home")
async def home(cq: CallbackQuery, db: Database, state: FSMContext):
    await clear_state_keep_screen(state, db, "admin_restaurant", cq.message.chat.id)
    controller = ChatScreenController(
        bot=cq.bot,
        chat_id=cq.message.chat.id,
        state=state,
        render=lambda: ("Админ-меню ресторана:", kb_admin_main()),
        db=db,
        bot_kind="admin_restaurant",
    )
    await controller.delete_screen()
    await controller.refresh()
    await cq.answer()
