import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from app.handlers_admin_restaurant.products import router as products_router
from app.handlers_admin_restaurant.extra import router as extra_router

from app.db.database import Database, DBConfig
from app.handlers_admin_restaurant.start import router as start_router
from app.handlers_admin_restaurant.orders import router as orders_router
from app.handlers_admin_restaurant.notifications import router as notifications_router
from app.handlers_admin_restaurant.fallback import router as fallback_router
from app.services.chat_reminders import run_chat_reminder_worker


async def main():
    load_dotenv()
    token = os.getenv("ADMIN_RESTAURANT_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("ADMIN_RESTAURANT_BOT_TOKEN is empty in .env")

    db = Database(DBConfig(path=os.getenv("DB_PATH", "shop.db")))
    await db.init_schema()

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db

    dp.include_router(start_router)
    dp.include_router(orders_router)
    dp.include_router(products_router)
    dp.include_router(extra_router)
    dp.include_router(notifications_router)
    dp.include_router(fallback_router)

    asyncio.create_task(run_chat_reminder_worker(bot, db, "admin_restaurant", dp.storage))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
