import asyncio
import logging
import aiohttp
from config import HTTP_TIMEOUT

logger = logging.getLogger(__name__)

TRACE_MOE_API = "https://api.trace.moe/search"
SIMILARITY_THRESHOLD = 0.30


async def search_anime_by_image(image_path: str) -> dict | None:
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        form = aiohttp.FormData()
        form.add_field(
            "image",
            image_data,
            filename="frame.jpg",
            content_type="image/jpeg",
        )

        timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{TRACE_MOE_API}?anilistInfo",
                data=form,
            ) as resp:
                if resp.status == 402:
                    logger.warning("trace.moe: Search quota exhausted")
                    return None
                if resp.status == 429:
                    logger.warning("trace.moe: Rate limit")
                    return None
                if resp.status != 200:
                    logger.warning(f"trace.moe returned status {resp.status}")
                    return None

                data = await resp.json()
                error = data.get("error")
                if error:
                    logger.warning(f"trace.moe error: {error}")
                    return None

                results = data.get("result") or []
                if not results:
                    logger.info("trace.moe: No results found")
                    return None

                best = results[0]
                similarity = best.get("similarity", 0)

                if similarity < SIMILARITY_THRESHOLD:
                    logger.info(
                        f"trace.moe: Best similarity {similarity:.2%} "
                        f"below threshold {SIMILARITY_THRESHOLD:.0%}"
                    )
                    return None

                anilist = best.get("anilist", {})
                if isinstance(anilist, int):
                    anilist_id = anilist
                    anilist_info = None
                else:
                    anilist_id = anilist.get("id")
                    anilist_info = anilist

                logger.info(
                    f"trace.moe: Match found - anilist_id={anilist_id}, "
                    f"similarity={similarity:.2%}, episode={best.get('episode')}"
                )

                return {
                    "anilist_id": anilist_id,
                    "similarity": similarity,
                    "episode": best.get("episode"),
                    "filename": best.get("filename"),
                    "from_time": best.get("from"),
                    "to_time": best.get("to"),
                    "video": best.get("video"),
                    "image": best.get("image"),
                    "anilist_info": anilist_info,
                    "source": "trace.moe",
                }

    except aiohttp.ClientError as e:
        logger.error(f"trace.moe network error: {e}")
        return None
    except Exception as e:
        logger.error(f"trace.moe error: {type(e).__name__}: {e}")
        return None


async def search_anime_by_video(video_path: str) -> dict | None:
    try:
        import os
        size = os.path.getsize(video_path)
        if size > 20 * 1024 * 1024:
            logger.info("trace.moe: Video too large for direct upload, skipping")
            return None

        with open(video_path, "rb") as f:
            video_data = f.read()

        form = aiohttp.FormData()
        form.add_field(
            "image",
            video_data,
            filename="video.mp4",
            content_type="video/mp4",
        )

        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{TRACE_MOE_API}?anilistInfo",
                data=form,
            ) as resp:
                if resp.status in (402, 429):
                    return None
                if resp.status != 200:
                    return None

                data = await resp.json()
                if data.get("error"):
                    return None

                results = data.get("result") or []
                if not results:
                    return None

                best = results[0]
                similarity = best.get("similarity", 0)

                if similarity < SIMILARITY_THRESHOLD:
                    return None

                anilist = best.get("anilist", {})
                if isinstance(anilist, int):
                    anilist_id = anilist
                else:
                    anilist_id = anilist.get("id")

                logger.info(
                    f"trace.moe (video): Match - anilist_id={anilist_id}, "
                    f"similarity={similarity:.2%}"
                )

                return {
                    "anilist_id": anilist_id,
                    "similarity": similarity,
                    "episode": best.get("episode"),
                    "filename": best.get("filename"),
                    "from_time": best.get("from"),
                    "to_time": best.get("to"),
                    "video": best.get("video"),
                    "image": best.get("image"),
                    "anilist_info": anilist if isinstance(anilist, dict) else None,
                    "source": "trace.moe",
                }

    except Exception as e:
        logger.debug(f"trace.moe video search: {type(e).__name__}: {e}")
        return None


async def search_anime_by_images_parallel(image_paths: list[str]) -> dict | None:
    if not image_paths:
        return None

    tasks = [search_anime_by_image(path) for path in image_paths[:6]]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    best = None
    for r in results:
        if isinstance(r, Exception):
            logger.warning(f"trace.moe parallel search error: {r}")
            continue
        if r is None:
            continue
        if best is None or r.get("similarity", 0) > best.get("similarity", 0):
            best = r

    if best:
        logger.info(
            f"trace.moe (parallel): Best match from {len(image_paths)} frames - "
            f"anilist_id={best.get('anilist_id')}, similarity={best.get('similarity', 0):.2%}"
        )

    return best
