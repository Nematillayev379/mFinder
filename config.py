import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def require_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        logger.critical(f"Missing required environment variable: {key}")
        sys.exit(1)
    return value


TELEGRAM_BOT_TOKEN = require_env("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = require_env("GROQ_API_KEY")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct")

MAX_VIDEO_SIZE = 50 * 1024 * 1024
MAX_FRAMES = 8
FRAME_INTERVAL = 2
FRAME_TIMEOUT = 30
HTTP_TIMEOUT = 30
GROQ_TIMEOUT = 60
TEMP_DIR = "data/temp"
CACHE_DB = "data/cache.db"
CACHE_TTL = 86400
RATE_LIMIT = 50
MAX_CONCURRENT = 5
MAX_MESSAGE_LENGTH = 4096
