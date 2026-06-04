import asyncio
import logging
import signal
import sys
from aiohttp import web
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


async def health_handler(request):
    return web.Response(text="OK", status=200)


async def run_health_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()
    logger.info("Health server started on port 10000")
    return runner


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

    health_runner = await run_health_server()

    logger.info("Bot is running!")

    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Bot shutting down...")
        try:
            await bot.session.close()
        except Exception as e:
            logger.error(f"Error closing session: {e}")
        try:
            await health_runner.cleanup()
        except Exception as e:
            logger.error(f"Error stopping health server: {e}")


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
