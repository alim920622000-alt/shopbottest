from __future__ import annotations

from aiogram.fsm.context import FSMContext


async def remember_client_screen(state: FSMContext, screen: str, payload: dict | None = None) -> None:
    await state.update_data(ui_screen=screen, ui_payload=payload or {})
