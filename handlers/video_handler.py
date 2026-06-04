import os
import uuid
import asyncio
import logging
import tempfile
from aiogram import Router, F
from aiogram.types import Message
from handlers.start_handler import get_user_lang
from utils.languages import get_message
from utils.formatter import format_result
from services.frame_extractor import extract_frames, cleanup_frames
from services.vision_analyzer import analyze_frames
from services.anime_searcher import search_anime_advanced, get_anime_by_id
from services.movie_searcher import search_movie, search_tv, get_movie_details, get_tv_details
from services.cache_service import compute_hash, get_cached, set_cached, check_rate_limit
from config import MAX_VIDEO_SIZE, RATE_LIMIT, MAX_CONCURRENT, MAX_MESSAGE_LENGTH

logger = logging.getLogger(__name__)

router = Router()

_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


@router.message(F.video | F.video_note | F.animation)
async def handle_video(message: Message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)

    if not check_rate_limit(user_id, RATE_LIMIT):
        await message.answer(get_message(lang, "rate_limit"))
        return

    video = message.video or message.video_note or message.animation
    if not video:
        return

    if video.file_size and video.file_size > MAX_VIDEO_SIZE:
        await message.answer(get_message(lang, "video_too_large"))
        return

    status_msg = await message.answer(get_message(lang, "processing"))

    tmp_path = None
    frames = []

    try:
        async with _semaphore:
            file = await message.bot.get_file(video.file_id)
            unique_name = f"{user_id}_{uuid.uuid4().hex}.mp4"
            tmp_path = os.path.join(tempfile.gettempdir(), unique_name)
            await message.bot.download_file(file.file_path, tmp_path)

            video_hash = compute_hash(tmp_path)
            cached = get_cached(video_hash)
            if cached:
                if len(cached) <= MAX_MESSAGE_LENGTH:
                    await status_msg.edit_text(cached, parse_mode="HTML")
                else:
                    await status_msg.edit_text(cached[:MAX_MESSAGE_LENGTH])
                return

            frames = await extract_frames(tmp_path)

            if not frames:
                await status_msg.edit_text(get_message(lang, "not_found"))
                return

            ai_result = await analyze_frames(frames)

            anime_data = None
            movie_data = None

            media_type = ai_result.get("type", "unknown")
            title = ai_result.get("title", "")

            if media_type == "anime":
                anilist_id = ai_result.get("anilist_id")
                if anilist_id:
                    try:
                        anime_data = await get_anime_by_id(int(anilist_id))
                    except (ValueError, TypeError):
                        pass
                if not anime_data:
                    anime_data = await search_anime_advanced(
                        title,
                        studio=ai_result.get("studio"),
                        year=ai_result.get("year"),
                    )
            elif media_type in ("movie", "series"):
                if media_type == "series":
                    search_result = await search_tv(title)
                    if search_result:
                        movie_data = await get_tv_details(search_result["id"])
                else:
                    search_result = await search_movie(title)
                    if search_result:
                        movie_data = await get_movie_details(search_result["id"])

            result_text = format_result(ai_result, anime_data, movie_data, lang)

            set_cached(video_hash, result_text)

            if len(result_text) <= MAX_MESSAGE_LENGTH:
                await status_msg.edit_text(result_text, parse_mode="HTML")
            else:
                chunks = [result_text[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(result_text), MAX_MESSAGE_LENGTH)]
                await status_msg.edit_text(chunks[0], parse_mode="HTML")
                for chunk in chunks[1:]:
                    await message.answer(chunk, parse_mode="HTML")

    except Exception as e:
        logger.exception(f"Video processing error for user {user_id}: {e}")
        try:
            await status_msg.edit_text(get_message(lang, "error"))
        except Exception:
            pass

    finally:
        if frames:
            cleanup_frames(frames)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
