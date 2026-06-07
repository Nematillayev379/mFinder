import logging
import aiohttp
from config import HTTP_TIMEOUT

logger = logging.getLogger(__name__)

TRACE_MOE_API = "https://api.trace.moe/search"
SIMILARITY_THRESHOLD = 0.82


async def search_anime_by_image(image_path: str) -> dict | None:
    """
    Anime frame rasmidan anime aniqlash (trace.moe orqali).
    Faqat ANIMElar uchun - film/serial uchun ishlamaydi.
    """
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
