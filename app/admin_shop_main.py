import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.db.database import Database, DBConfig
from app.handlers_admin_shop.start import router as start_router
from app.handlers_admin_shop.orders import router as orders_router
from app.handlers_admin_shop.extra import router as extra_router
from app.handlers_admin_shop.products import router as products_router
from app.handlers_admin_shop.chat import router as chat_router
from app.handlers_admin_shop.fallback import router as fallback_router
from app.services.chat_reminders import run_chat_reminder_worker


async def main():
    load_dotenv()
    token = os.getenv("ADMIN_SHOP_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("ADMIN_SHOP_BOT_TOKEN is empty in .env")

    db = Database(DBConfig(path=os.getenv("DB_PATH", "shop.db")))
    await db.init_schema()

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    dp["db"] = db

    dp.include_router(start_router)
    dp.include_router(products_router)
    dp.include_router(extra_router)
    dp.include_router(orders_router)
    dp.include_router(chat_router)
    dp.include_router(fallback_router)

    asyncio.create_task(run_chat_reminder_worker(bot, db, "admin_shop"))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
