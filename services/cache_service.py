import sqlite3
import time
import hashlib
import logging
from pathlib import Path
from config import CACHE_DB, CACHE_TTL

logger = logging.getLogger(__name__)

DB_PATH = Path(CACHE_DB)


def _ensure_dirs():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    _ensure_dirs()
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cache (
            video_hash TEXT PRIMARY KEY,
            result TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            user_id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0,
            reset_at REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def compute_hash(file_path: str) -> str:
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_cached(video_hash: str) -> str | None:
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT result, created_at FROM cache WHERE video_hash = ?",
            (video_hash,),
        )
        row = cursor.fetchone()
        if row and (time.time() - row[1]) < CACHE_TTL:
            return row[0]
        return None
    except Exception as e:
        logger.error(f"Cache read error: {e}")
        return None
    finally:
        conn.close()


def set_cached(video_hash: str, result: str):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO cache (video_hash, result, created_at) VALUES (?, ?, ?)",
            (video_hash, result, time.time()),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Cache write error: {e}")
    finally:
        conn.close()


def check_rate_limit(user_id: int, limit: int = 50) -> bool:
    conn = get_connection()
    try:
        now = time.time()
        conn.execute(
            """INSERT INTO rate_limits (user_id, count, reset_at) VALUES (?, 1, ?)
               ON CONFLICT(user_id) DO UPDATE SET
               count = CASE WHEN rate_limits.reset_at < ? THEN 1 ELSE rate_limits.count + 1 END,
               reset_at = CASE WHEN rate_limits.reset_at < ? THEN ? ELSE rate_limits.reset_at END""",
            (user_id, now + 86400, now, now, now + 86400),
        )
        conn.commit()

        cursor = conn.execute("SELECT count FROM rate_limits WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row and row[0] > limit:
            return False
        return True
    except Exception as e:
        logger.error(f"Rate limit error: {e}")
        return True
    finally:
        conn.close()


def cleanup_cache():
    conn = get_connection()
    try:
        cutoff = time.time() - CACHE_TTL
        conn.execute("DELETE FROM cache WHERE created_at < ?", (cutoff,))
        conn.execute("DELETE FROM rate_limits WHERE reset_at < ?", (time.time() - 172800,))
        conn.commit()
        logger.info("Cache cleanup completed")
    except Exception as e:
        logger.error(f"Cache cleanup error: {e}")
    finally:
        conn.close()
