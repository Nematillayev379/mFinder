import os
import re
import logging
import asyncio
import uuid
import tempfile
from pathlib import Path
import yt_dlp

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 90
MAX_FILE_SIZE = 80 * 1024 * 1024

URL_PATTERNS = [
    r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+",
    r"https?://(?:www\.)?youtu\.be/[\w-]+",
    r"https?://(?:www\.)?youtube\.com/shorts/[\w-]+",
    r"https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/[\w-]+",
    r"https?://(?:www\.)?instagram\.com/stories/[\w_/]+",
    r"https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+",
    r"https?://(?:vm|vt)\.tiktok\.com/[\w]+",
    r"https?://(?:www\.)?twitter\.com/[\w_]+/status/\d+",
    r"https?://(?:www\.)?x\.com/[\w_]+/status/\d+",
    r"https?://(?:www\.)?reddit\.com/r/[\w_]+/comments/\w+",
    r"https?://(?:www\.)?facebook\.com/[\w./]+/videos/\d+",
    r"https?://(?:www\.)?vimeo\.com/\d+",
    r"https?://(?:www\.)?dailymotion\.com/video/\w+",
    r"https?://(?:www\.)?twitch\.tv/[\w_/]+",
    r"https?://t\.me/[\w_]+/\d+",
]


def is_video_url(text: str) -> bool:
    """Matn ichida video URL bormi?"""
    for pattern in URL_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def extract_first_url(text: str) -> str | None:
    """Matndan birinchi video URL ni qaytaradi"""
    for pattern in URL_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


async def download_video(url: str) -> str | None:
    """
    URL dan video yuklab oladi, lokal fayl yo'lini qaytaradi.
    None - xato bo'lsa.
    """
    output_dir = Path(tempfile.gettempdir())
    unique_id = uuid.uuid4().hex
    output_template = str(output_dir / f"mfinder_{unique_id}.%(ext)s")

    ydl_opts = {
        "format": "best[filesize<80M]/best[filesize_approx<80M]/best",
        "outtmpl": output_template,
        "max_filesize": MAX_FILE_SIZE,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 30,
        "retries": 3,
        "merge_output_format": "mp4",
        "prefer_free_formats": False,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    }

    try:
        loop = asyncio.get_event_loop()

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=True)
                except yt_dlp.utils.DownloadError as e:
                    logger.error(f"yt-dlp download error: {str(e)[:200]}")
                    return None

                if not info:
                    return None

                if "requested_downloads" in info and info["requested_downloads"]:
                    filepath = info["requested_downloads"][0].get("filepath")
                    if filepath and os.path.exists(filepath):
                        return filepath

                final_path = ydl.prepare_filename(info)
                if os.path.exists(final_path):
                    return final_path

                base, _ = os.path.splitext(final_path)
                for ext in [".mp4", ".mkv", ".webm", ".mov", ".avi", ".flv"]:
                    candidate = base + ext
                    if os.path.exists(candidate):
                        return candidate
                return None

        filepath = await asyncio.wait_for(
            loop.run_in_executor(None, _download),
            timeout=DOWNLOAD_TIMEOUT,
        )

        if filepath and os.path.exists(filepath):
            size = os.path.getsize(filepath)
            if size > MAX_FILE_SIZE:
                logger.warning(f"Downloaded file too large: {size} bytes")
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                return None
            logger.info(f"Downloaded: {filepath} ({size} bytes)")
            return filepath
        return None

    except asyncio.TimeoutError:
        logger.error(f"Download timeout: {url[:100]}")
        return None
    except Exception as e:
        logger.error(f"Download error: {type(e).__name__}: {str(e)[:200]}")
        return None
