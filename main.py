import asyncio
import logging
import signal
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_BOT_TOKEN
from handlers.start_handler import router as start_router
from handlers.video_handler import router as video_router
from services.cache_service import cleanup_cache
from services.frame_extractor import cleanup_old_temp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Bot starting...")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(start_router)
    dp.include_router(video_router)

    try:
        cleanup_old_temp()
        cleanup_cache()
    except Exception as e:
        logger.warning(f"Startup cleanup failed: {e}")

    logger.info("Bot is running!")

    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Bot shutting down...")
        try:
            await bot.session.close()
        except Exception as e:
            logger.error(f"Error closing session: {e}")


def handle_signal(signum, frame):
    logger.info(f"Received signal {signum}")
    sys.exit(0)


if __name__ == "__main__":
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
