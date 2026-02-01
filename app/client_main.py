import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from app.db.database import Database, DBConfig
from app.handlers_client.start import router as start_router
from app.handlers_client.catalog import router as catalog_router
from app.handlers_client.orders import router as orders_router
from app.handlers_client.cabinet import router as cabinet_router
from app.handlers_client.inline_search import router as inline_search_router


async def main():
    load_dotenv()
    token = os.getenv("CLIENT_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("CLIENT_BOT_TOKEN is empty in .env")

    db = Database(DBConfig(path=os.getenv("DB_PATH", "shop.db")))
    await db.init_schema()

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())

    # пробросим db в data (глобально)
    dp["db"] = db

    dp.include_router(start_router)
    dp.include_router(catalog_router)
    dp.include_router(orders_router)
    dp.include_router(cabinet_router)
    dp.include_router(inline_search_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
