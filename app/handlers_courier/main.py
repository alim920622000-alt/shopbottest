from __future__ import annotations

import random
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from app.db.database import Database
from app.repositories.couriers_repo import CouriersRepo
from app.repositories.orders_repo import OrdersRepo
from app.repositories.zones_repo import ZonesRepo
from app.repositories.settings_repo import SettingsRepo

router = Router()
ZONE_PAGE_SIZE = 8


def _push(stack: list[str], view: str) -> list[str]:
    if not stack or stack[-1] != view:
        stack.append(view)
    return stack[-10:]


def _kb_menu(online: bool) -> InlineKeyboardMarkup:
    if online:
        rows = [
            [InlineKeyboardButton(text="🚚 Доступные", callback_data="cr:available")],
            [InlineKeyboardButton(text="🧾 Мои активные", callback_data="cr:active")],
            [InlineKeyboardButton(text="📚 История", callback_data="cr:history")],
            [InlineKeyboardButton(text="🗺 Моя зона", callback_data="cr:zone")],
            [InlineKeyboardButton(text="👤 Кабинет", callback_data="cr:cabinet")],
            [InlineKeyboardButton(text="[Статус: На линии]", callback_data="cr:toggle_online")],
        ]
    else:
        rows = [
            [InlineKeyboardButton(text="[Статус: Не на линии]", callback_data="cr:toggle_online")],
            [InlineKeyboardButton(text="Мои активные", callback_data="cr:active")],
            [InlineKeyboardButton(text="История", callback_data="cr:history")],
            [InlineKeyboardButton(text="Моя зона", callback_data="cr:zone")],
            [InlineKeyboardButton(text="Кабинет", callback_data="cr:cabinet")],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_menu(message: Message | CallbackQuery, db: Database, user_id: int):
    c = await CouriersRepo(db).get(user_id)
    online = int((c or {}).get("is_online") or 0) == 1
    text = "Курьер-бот"
    kb = _kb_menu(online)
    if isinstance(message, Message):
        await message.answer(text, reply_markup=kb)
    else:
        await message.message.edit_text(text, reply_markup=kb)


@router.message(CommandStart())
async def start_cmd(message: Message, db: Database, state: FSMContext):
    await CouriersRepo(db).ensure(message.from_user.id)
    await state.update_data(back_stack=["menu"])
    await _render_menu(message, db, message.from_user.id)


@router.callback_query(F.data == "cr:toggle_online")
async def toggle_online(cq: CallbackQuery, db: Database, state: FSMContext):
    repo = CouriersRepo(db)
    data = await repo.get(cq.from_user.id)
    online = int((data or {}).get("is_online") or 0) == 1
    await repo.set_online(cq.from_user.id, not online)
    await state.update_data(back_stack=["menu"])
    await _render_menu(cq, db, cq.from_user.id)
    await cq.answer()


@router.callback_query(F.data == "cr:back")
async def back(cq: CallbackQuery, db: Database, state: FSMContext):
    data = await state.get_data()
    stack = list(data.get("back_stack") or ["menu"])
    if len(stack) > 1:
        stack.pop()
    target = stack[-1]
    await state.update_data(back_stack=stack)
    if target == "menu":
        await _render_menu(cq, db, cq.from_user.id)
    elif target == "zone":
        await zone(cq, db, state, 0)
    elif target == "available":
        await available(cq, db, state)
    elif target == "active":
        await active(cq, db, state)
    elif target == "history":
        await history(cq, db, state)
    await cq.answer()


@router.callback_query(F.data == "cr:available")
async def available(cq: CallbackQuery, db: Database, state: FSMContext):
    stack = list((await state.get_data()).get("back_stack") or ["menu"])
    await state.update_data(back_stack=_push(stack, "available"))
    rows = await OrdersRepo(db).list_available_for_courier(cq.from_user.id)
    kb_rows = [[InlineKeyboardButton(text=f"Заказ #{r['id']}", callback_data=f"cr:order:{r['id']}")] for r in rows]
    kb_rows.append([InlineKeyboardButton(text="Назад", callback_data="cr:back")])
    await cq.message.edit_text("Доступные заказы", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await cq.answer()


@router.callback_query(F.data == "cr:active")
async def active(cq: CallbackQuery, db: Database, state: FSMContext):
    stack = list((await state.get_data()).get("back_stack") or ["menu"])
    await state.update_data(back_stack=_push(stack, "active"))
    rows = await OrdersRepo(db).list_active_for_courier(cq.from_user.id)
    kb_rows = [[InlineKeyboardButton(text=f"Заказ #{r['id']}", callback_data=f"cr:order:{r['id']}")] for r in rows]
    kb_rows.append([InlineKeyboardButton(text="Назад", callback_data="cr:back")])
    await cq.message.edit_text("Мои активные", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await cq.answer()


@router.callback_query(F.data == "cr:history")
async def history(cq: CallbackQuery, db: Database, state: FSMContext):
    stack = list((await state.get_data()).get("back_stack") or ["menu"])
    await state.update_data(back_stack=_push(stack, "history"))
    rows = await OrdersRepo(db).list_history_for_courier(cq.from_user.id)
    kb_rows = [[InlineKeyboardButton(text=f"Заказ #{r['id']}", callback_data=f"cr:order:{r['id']}")] for r in rows]
    kb_rows.append([InlineKeyboardButton(text="Назад", callback_data="cr:back")])
    await cq.message.edit_text("История", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await cq.answer()


@router.callback_query(F.data.startswith("cr:order:"))
async def order_card(cq: CallbackQuery, db: Database, state: FSMContext):
    order_id = int(cq.data.split(":")[-1])
    repo = OrdersRepo(db)
    o = await repo.get_order(order_id)
    if not o:
        await cq.answer("Заказ не найден", show_alert=True)
        return
    text = f"Заказ #{o['id']}\nmerchant_status={o.get('merchant_status')}\ncourier_status={o.get('courier_status')}"
    rows = []
    if o.get("courier_status") == "searching":
        rows.append([InlineKeyboardButton(text="✅ Принять доставку", callback_data=f"cr:accept:{order_id}")])
    if o.get("courier_status") == "assigned" and o.get("merchant_status") == "ready":
        rows.append([InlineKeyboardButton(text="📦 Забрал заказ", callback_data=f"cr:pickup:{order_id}")])
    if o.get("courier_status") == "picked_up":
        rows.append([InlineKeyboardButton(text="📍 Прибыл", callback_data=f"cr:arrived:{order_id}")])
    rows.append([InlineKeyboardButton(text="Назад", callback_data="cr:back")])
    await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await cq.answer()


async def _can_accept(db: Database, courier_user_id: int) -> bool:
    settings = SettingsRepo(db)
    mode = int(await settings.get("courier_capacity_mode", "1"))
    max_active = int(await settings.get("max_active_orders", "2"))
    active = await OrdersRepo(db).list_active_for_courier(courier_user_id)
    if mode == 1:
        return len(active) < 1
    if mode == 2:
        return len(active) < max_active
    if mode == 3:
        if len(active) == 0:
            return True
        if len(active) > 1:
            return False
        return str(active[0].get("courier_status") or "") == "arrived"
    return False


@router.callback_query(F.data.startswith("cr:accept:"))
async def accept(cq: CallbackQuery, db: Database):
    order_id = int(cq.data.split(":")[-1])
    if not await _can_accept(db, cq.from_user.id):
        await cq.answer("Превышен лимит активных заказов", show_alert=True)
        return
    ok = await OrdersRepo(db).assign_courier_atomic(order_id, cq.from_user.id)
    await cq.answer("Принято" if ok else "Уже занят", show_alert=not ok)


@router.callback_query(F.data.startswith("cr:pickup:"))
async def pickup(cq: CallbackQuery, db: Database):
    order_id = int(cq.data.split(":")[-1])
    await OrdersRepo(db).set_courier_status(order_id, "picked_up")
    await cq.answer("Статус: забрал")


@router.callback_query(F.data.startswith("cr:arrived:"))
async def arrived(cq: CallbackQuery, db: Database):
    order_id = int(cq.data.split(":")[-1])
    repo = OrdersRepo(db)
    code = f"{random.randint(1000, 9999)}"
    await repo.set_handoff_code_if_empty(order_id, code)
    await repo.set_courier_status(order_id, "arrived")
    await cq.answer("Курьер прибыл")


@router.callback_query(F.data == "cr:cabinet")
async def cabinet(cq: CallbackQuery, db: Database, state: FSMContext):
    stack = list((await state.get_data()).get("back_stack") or ["menu"])
    await state.update_data(back_stack=_push(stack, "cabinet"))
    await cq.message.edit_text("Кабинет курьера", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="cr:back")]]))
    await cq.answer()


@router.callback_query(F.data == "cr:zone")
async def zone(cq: CallbackQuery, db: Database, state: FSMContext, page: int = 0):
    stack = list((await state.get_data()).get("back_stack") or ["menu"])
    await state.update_data(back_stack=_push(stack, "zone"))
    zrepo = ZonesRepo(db)
    crepo = CouriersRepo(db)
    c = await crepo.get(cq.from_user.id)
    selected = await zrepo.list_for_courier(cq.from_user.id)
    rows = await zrepo.list_active(limit=ZONE_PAGE_SIZE, offset=page * ZONE_PAGE_SIZE)
    kb_rows = []
    for z in rows:
        mark = "✅" if int(z["id"]) in selected else "⬜"
        kb_rows.append([InlineKeyboardButton(text=f"{mark} {z['name']}", callback_data=f"cr:zone_toggle:{z['id']}:{page}")])
    aa = int((c or {}).get("accept_all_zones") or 0) == 1
    kb_rows.append([InlineKeyboardButton(text=f"Все зоны: {'✅' if aa else '⬜'}", callback_data="cr:zone_all")])
    kb_rows.append([InlineKeyboardButton(text="Сохранить", callback_data="cr:zone_save")])
    kb_rows.append([InlineKeyboardButton(text="Назад", callback_data="cr:back")])
    await cq.message.edit_text("Моя зона", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows))
    await cq.answer()


@router.callback_query(F.data.startswith("cr:zone_toggle:"))
async def zone_toggle(cq: CallbackQuery, db: Database, state: FSMContext):
    _, _, zid, page = cq.data.split(":")
    await ZonesRepo(db).toggle_for_courier(cq.from_user.id, int(zid))
    await zone(cq, db, state, int(page))


@router.callback_query(F.data == "cr:zone_all")
async def zone_all(cq: CallbackQuery, db: Database, state: FSMContext):
    c = await CouriersRepo(db).get(cq.from_user.id)
    await CouriersRepo(db).set_accept_all_zones(cq.from_user.id, int((c or {}).get("accept_all_zones") or 0) != 1)
    await zone(cq, db, state, 0)


@router.callback_query(F.data == "cr:zone_save")
async def zone_save(cq: CallbackQuery):
    await cq.answer("Сохранено")


@router.callback_query(F.data == "cr:capacity")
async def capacity_menu(cq: CallbackQuery, db: Database):
    await cq.message.edit_text(
        "Режим вместимости",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="mode1", callback_data="cr:cap_set:1")],
            [InlineKeyboardButton(text="mode2", callback_data="cr:cap_set:2")],
            [InlineKeyboardButton(text="mode3", callback_data="cr:cap_set:3")],
            [InlineKeyboardButton(text="Назад", callback_data="cr:back")],
        ]),
    )
    await cq.answer()


@router.callback_query(F.data.startswith("cr:cap_set:"))
async def cap_set(cq: CallbackQuery, db: Database):
    mode = cq.data.split(":")[-1]
    await SettingsRepo(db).set("courier_capacity_mode", mode)
    await cq.answer("Режим сохранён")
