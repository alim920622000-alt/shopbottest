# -*- coding: utf-8 -*-
from aiogram import F
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from app.i18n.client.translator import t
from app.services.message_cleanup import send_temp_message
from app.handlers_client.kb import client_quick_menu

from app.db.database import Database
from app.services.chat_screen_controller import ChatScreenController
from app.services.client_ui_renderer import render_client_screen
from app.services.client_ui_state import remember_client_screen
from app.services.screen import clear_state_keep_screen, show_main_menu

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext, db: Database, locale: str = "ru"):
    await clear_state_keep_screen(state, db, "client", message.chat.id)
    await remember_client_screen(state, "main", {})
    await state.update_data(user_id=message.from_user.id, locale=locale)

    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=lambda: render_client_screen(db, state),
        db=db,
        bot_kind="client",
    )
    await controller.delete_user_message(message)
    await controller.delete_screen()
    await controller.refresh()
    
    await message.answer(
        t(locale, "client.quick_menu_title"),
        reply_markup=client_quick_menu(locale),
    )


@router.message(F.text == t("ru", "client.quick_cart"))
@router.message(F.text == t("uz", "client.quick_cart"))
@router.message(F.text == t("tj", "client.quick_cart"))
async def open_cart_quick(message: Message):
    await send_temp_message(message, "Корзина", seconds=3, delete_user=True)


@router.message(F.text == t("ru", "client.quick_search"))
@router.message(F.text == t("uz", "client.quick_search"))
@router.message(F.text == t("tj", "client.quick_search"))
async def open_search_quick(message: Message):
    await send_temp_message(message, "Введите название товара", seconds=3, delete_user=True)


@router.message(F.text == t("ru", "client.quick_orders"))
@router.message(F.text == t("uz", "client.quick_orders"))
@router.message(F.text == t("tj", "client.quick_orders"))
async def open_orders_quick(message: Message):
    await send_temp_message(message, "Заказы", seconds=3, delete_user=True)


@router.message(F.text == t("ru", "client.quick_home"))
@router.message(F.text == t("uz", "client.quick_home"))
@router.message(F.text == t("tj", "client.quick_home"))
async def open_home_quick(message: Message, state: FSMContext, db: Database):
    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    locale = data.get("locale", "ru")

    await clear_state_keep_screen(state, db, "client", message.chat.id)
    await remember_client_screen(state, "main", {})
    await state.update_data(user_id=message.from_user.id, locale=locale)

    controller = ChatScreenController(
        bot=message.bot,
        chat_id=message.chat.id,
        state=state,
        render=lambda: render_client_screen(db, state),
        db=db,
        bot_kind="client",
    )
    await controller.delete_screen()
    await controller.refresh()
