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
from services.anime_searcher import search_anime_advanced, get_anime_by_id, search_anime
from services.movie_searcher import search_movie, search_tv, get_movie_details, get_tv_details
from services.video_downloader import is_video_url, extract_first_url, download_video
from services.trace_moe_service import search_anime_by_image, search_anime_by_video
from services.saucenao_service import search_by_image as saucenao_search
from services.cache_service import compute_hash, get_cached, set_cached, check_rate_limit
from config import MAX_VIDEO_SIZE, RATE_LIMIT, MAX_CONCURRENT, MAX_MESSAGE_LENGTH, MAX_FRAMES, FRAME_INTERVAL

logger = logging.getLogger(__name__)

router = Router()

_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


async def _process_video_file(message: Message, status_msg, tmp_path: str, user_id: int, lang: str) -> list[str]:
    frames = await extract_frames(tmp_path, max_frames=MAX_FRAMES, interval=FRAME_INTERVAL)

    if not frames:
        await status_msg.edit_text(get_message(lang, "not_found"))
        return []

    trace_result = await search_anime_by_video(tmp_path)

    if not trace_result:
        trace_result = await search_anime_by_image(frames[0])

    if not trace_result and len(frames) > 1:
        trace_result = await search_anime_by_image(frames[1])

    if not trace_result and len(frames) > 2:
        trace_result = await search_anime_by_image(frames[len(frames) // 2])

    saucenao_result = None
    if not trace_result:
        for i in range(min(3, len(frames))):
            saucenao_result = await saucenao_search(frames[i])
            if saucenao_result:
                break

    ai_result = None
    anime_data = None
    movie_data = None

    if trace_result:
        anilist_id = trace_result.get("anilist_id")
        if anilist_id:
            try:
                anime_data = await get_anime_by_id(int(anilist_id))
            except (ValueError, TypeError):
                pass

        if anime_data:
            titles = anime_data.get("title", {}) or {}
            ai_result = {
                "type": "anime",
                "title": titles.get("romaji") or titles.get("english") or titles.get("native") or "Unknown",
                "title_english": titles.get("english") or "",
                "title_japanese": titles.get("native") or "",
                "year": str((anime_data.get("startDate") or {}).get("year") or ""),
                "genre": anime_data.get("genres") or [],
                "studio": "",
                "confidence": trace_result.get("similarity", 0.0),
                "visual_features": f"trace.moe match (similarity: {trace_result.get('similarity', 0):.0%})",
                "reasoning": f"Episode {trace_result.get('episode', '?')} identified via frame matching",
                "anilist_id": str(anilist_id),
                "tmdb_id": "",
                "episode": str(trace_result.get("episode") or ""),
            }
            logger.info(f"trace.moe match: {ai_result['title']} ({ai_result['confidence']:.0%})")
        else:
            trace_result = None

    if not ai_result and saucenao_result:
        sn_title = saucenao_result.get("title", "")
        if sn_title:
            anime_data = await search_anime(sn_title)
        if anime_data:
            titles = anime_data.get("title", {}) or {}
            ai_result = {
                "type": "anime",
                "title": titles.get("romaji") or titles.get("english") or titles.get("native") or sn_title,
                "title_english": titles.get("english") or "",
                "title_japanese": titles.get("native") or "",
                "year": str((anime_data.get("startDate") or {}).get("year") or ""),
                "genre": anime_data.get("genres") or [],
                "studio": "",
                "confidence": saucenao_result.get("similarity", 0.0),
                "visual_features": f"SauceNAO match ({saucenao_result.get('index_name', '')})",
                "reasoning": f"Matched via SauceNAO image search",
                "anilist_id": str(anime_data.get("id", "")),
                "tmdb_id": "",
            }
            logger.info(f"SauceNAO match: {ai_result['title']} ({ai_result['confidence']:.0%})")
        elif sn_title:
            ai_result = {
                "type": "anime",
                "title": sn_title,
                "title_english": "",
                "title_japanese": "",
                "year": "",
                "genre": [],
                "studio": "",
                "confidence": saucenao_result.get("similarity", 0.0),
                "visual_features": f"SauceNAO: {saucenao_result.get('index_name', '')}",
                "reasoning": f"Matched via SauceNAO ({saucenao_result.get('source_url', '')})",
                "anilist_id": "",
                "tmdb_id": "",
            }

    if ai_result is None:
        ai_result = await analyze_frames(frames)

    media_type = ai_result.get("type", "unknown")
    title = ai_result.get("title", "")
    confidence = ai_result.get("confidence", 0)
    search_terms = ai_result.get("search_terms", "")

    if media_type == "anime" and not anime_data:
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
        if not anime_data and confidence < 0.5 and search_terms:
            logger.info(f"Low confidence ({confidence:.2f}), trying search_terms: {search_terms}")
            anime_data = await search_anime(search_terms)
        if not anime_data and confidence < 0.5 and title and title != "Unknown":
            logger.info(f"Trying alternative search with title: {title}")
            anime_data = await search_anime(title)

    elif media_type in ("movie", "series") and not movie_data:
        if media_type == "series":
            search_result = await search_tv(title)
            if search_result:
                movie_data = await get_tv_details(search_result["id"])
        else:
            search_result = await search_movie(title)
            if search_result:
                movie_data = await get_movie_details(search_result["id"])

    if not anime_data and not movie_data and ai_result.get("type") == "unknown":
        pass

    result_text = format_result(ai_result, anime_data, movie_data, lang)

    set_cached(video_hash := compute_hash(tmp_path), result_text)

    if len(result_text) <= MAX_MESSAGE_LENGTH:
        await status_msg.edit_text(result_text, parse_mode="HTML")
    else:
        chunks = [result_text[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(result_text), MAX_MESSAGE_LENGTH)]
        await status_msg.edit_text(chunks[0], parse_mode="HTML")
        for chunk in chunks[1:]:
            await message.answer(chunk, parse_mode="HTML")

    return frames


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

            frames = await _process_video_file(message, status_msg, tmp_path, user_id, lang)

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


@router.message(F.text & F.text.contains("http"))
async def handle_url(message: Message):
    user_id = message.from_user.id
    lang = get_user_lang(user_id)
    text = message.text or ""

    if not is_video_url(text):
        return

    url = extract_first_url(text)
    if not url:
        return

    if not check_rate_limit(user_id, RATE_LIMIT):
        await message.answer(get_message(lang, "rate_limit"))
        return

    status_msg = await message.answer(get_message(lang, "downloading"))

    tmp_path = None
    frames = []

    try:
        async with _semaphore:
            tmp_path = await download_video(url)

            if not tmp_path:
                await status_msg.edit_text(get_message(lang, "download_failed"))
                return

            await status_msg.edit_text(get_message(lang, "processing"))
            video_hash = compute_hash(tmp_path)
            cached = get_cached(video_hash)
            if cached:
                if len(cached) <= MAX_MESSAGE_LENGTH:
                    await status_msg.edit_text(cached, parse_mode="HTML")
                else:
                    await status_msg.edit_text(cached[:MAX_MESSAGE_LENGTH])
                return

            frames = await _process_video_file(message, status_msg, tmp_path, user_id, lang)

    except Exception as e:
        logger.exception(f"URL processing error for user {user_id}: {e}")
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
