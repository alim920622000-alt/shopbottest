import asyncio
import os
from app.handlers.noop import router as noop_router
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.db.database import Database, DBConfig
from app.handlers_client.start import router as start_router
from app.handlers_client.catalog import router as catalog_router
from app.handlers_client.orders import router as orders_router
from app.handlers_client.cabinet import router as cabinet_router
from app.handlers_client.inline_search import router as inline_search_router
from app.handlers_client.notifications import router as notifications_router
from app.handlers_client.fallback import router as fallback_router
from app.handlers_client.middleware import ClientLocaleMiddleware
from app.services.chat_reminders import run_chat_reminder_worker


async def main():
    load_dotenv()
    token = os.getenv("CLIENT_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("CLIENT_BOT_TOKEN is empty in .env")

    db = Database(DBConfig(path=os.getenv("DB_PATH", "shop.db"), dsn=os.getenv("DB_DSN", "")))
    await db.init_schema()

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    # пробросим db в data (глобально)
    dp["db"] = db

    locale_middleware = ClientLocaleMiddleware()
    dp.message.middleware(locale_middleware)
    dp.callback_query.middleware(locale_middleware)

    dp.include_router(start_router)
    dp.include_router(catalog_router)
    dp.include_router(orders_router)
    dp.include_router(cabinet_router)
    dp.include_router(inline_search_router)
    dp.include_router(notifications_router)
    dp.include_router(noop_router)
    dp.include_router(fallback_router)
    
    
    asyncio.create_task(run_chat_reminder_worker(bot, db, "client", dp.storage))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
