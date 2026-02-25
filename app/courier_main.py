import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from app.db.database import Database, DBConfig
from app.handlers_courier.main import router as courier_router

logger = logging.getLogger(__name__)


async def main():
    settings = get_settings()
    token = settings.courier_bot_token
    if not token:
        logger.error("COURIER_BOT_TOKEN не задан. Запуск courier-бота остановлен.")
        raise RuntimeError("COURIER_BOT_TOKEN is empty in .env")

    db = Database(DBConfig(path=settings.db_path))
    await db.init_schema()

    bot = Bot(token=token)
    dp = Dispatcher(storage=MemoryStorage())
    dp["db"] = db
    dp.include_router(courier_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
