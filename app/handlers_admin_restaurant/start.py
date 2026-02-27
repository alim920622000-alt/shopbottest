from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.handlers_admin_restaurant.utils import is_restaurant_admin
from app.repositories.chat_reads_repo import ChatReadsRepo
from app.repositories.order_seen_repo import OrderSeenRepo
from app.services.screen import clear_state_keep_screen, show_main_menu
from app.services.chat_screen_controller import ChatScreenController
from app.services.chat_reminders import is_chat_reminder_text
from app.services.notification_center import remember_admin_prev_target
from app.utils.tg_safe import safe_delete_cq_message

router = Router()


def kb_admin_main(chat_unread_threads: int = 0, new_orders_count: int = 0) -> InlineKeyboardMarkup:
    chat_text = "💬 Чат"
    if chat_unread_threads > 0:
        chat_text = f"{chat_text} ({chat_unread_threads})"
    orders_text = "🍽 Заказы"
    if new_orders_count > 0:
        orders_text = f"{orders_text} ({new_orders_count})"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=orders_text, callback_data="r:orders")],
        [InlineKeyboardButton(text="🧾 Меню", callback_data="r:cats")],
        [InlineKeyboardButton(text="🕓 История", callback_data="r:history")],
        [InlineKeyboardButton(text="🎁 Акции", callback_data="r:promos")],
        [InlineKeyboardButton(text="👤 Кабинет", callback_data="r:cabinet")],
        [InlineKeyboardButton(text=chat_text, callback_data="r:chat")],
    ])


async def build_admin_restaurant_main_kb(db: Database, user_id: int) -> InlineKeyboardMarkup:
    unread = await ChatReadsRepo(db).count_unread_orders("admin_restaurant", user_id)
    new_orders = await OrderSeenRepo(db).count_new_orders("admin_restaurant", user_id)
    return kb_admin_main(chat_unread_threads=unread, new_orders_count=new_orders)


async def _render_admin_main(db: Database, user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    return "Админ-меню ресторана:", await build_admin_restaurant_main_kb(db, user_id)


@router.message(CommandStart())
async def start_cmd(message: Message, db: Database, state: FSMContext):
    if not await is_restaurant_admin(db, message.from_user.id):
        await message.answer("Нет доступа. Ваш user_id не назначен админом ресторана.")
        return
    await clear_state_keep_screen(state, db, "admin_restaurant", message.chat.id)
    await remember_admin_prev_target(db, "admin_restaurant", message.from_user.id, "r:home")
    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=lambda: _render_admin_main(db, message.from_user.id),
        db=db,
        bot_kind="admin_restaurant",
    )
    await controller.delete_user_message(message)
    await controller.delete_screen()
    await controller.refresh()


@router.callback_query(F.data == "r:home")
async def home(cq: CallbackQuery, db: Database, state: FSMContext):
    await clear_state_keep_screen(state, db, "admin_restaurant", cq.message.chat.id)
    await remember_admin_prev_target(db, "admin_restaurant", cq.from_user.id, "r:home")
    if is_chat_reminder_text(cq.message.text if cq.message else None):
        # Для напоминания удаляем сообщение и показываем главный экран через screen.py.
        await safe_delete_cq_message(cq)
        await show_main_menu(
            bot=cq.bot,
            chat_id=cq.message.chat.id,
            state=state,
            db=db,
            bot_kind="admin_restaurant",
            text="Админ-меню ресторана:",
            reply_markup=await build_admin_restaurant_main_kb(db, cq.from_user.id),
        )
    else:
        controller = ChatScreenController(
            bot=cq.bot,
            chat_id=cq.message.chat.id,
            state=state,
            render=lambda: _render_admin_main(db, cq.from_user.id),
            db=db,
            bot_kind="admin_restaurant",
        )
        await controller.delete_screen()
        await controller.refresh()
    await cq.answer()
