import logging
import aiohttp
from config import HTTP_TIMEOUT

logger = logging.getLogger(__name__)

SAUCENAO_API = "https://saucenao.com/search.php"
SIMILARITY_THRESHOLD = 50.0


async def search_by_image(image_path: str) -> dict | None:
    """SauceNAO orqali rasm orqali anime/manga qidirish"""
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()

        form = aiohttp.FormData()
        form.add_field("file", image_data, filename="frame.jpg", content_type="image/jpeg")

        params = {
            "output_type": "2",
            "numres": "5",
        }

        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(SAUCENAO_API, data=form, params=params) as resp:
                if resp.status == 429:
                    logger.warning("SauceNAO: Rate limit")
                    return None
                if resp.status != 200:
                    logger.warning(f"SauceNAO returned status {resp.status}")
                    return None

                data = await resp.json()
                header = data.get("header", {})
                results = data.get("results") or []

                if not results:
                    logger.info("SauceNAO: No results found")
                    return None

                best = results[0]
                header_result = best.get("header", {})
                similarity = float(header_result.get("similarity", "0"))
                index_name = header_result.get("index_name", "")

                anime_indices = [5, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
                index_id = int(header_result.get("index_id", "0") or "0")
                is_anime = index_id in anime_indices or "anime" in index_name.lower() or "manga" in index_name.lower()

                if similarity < SIMILARITY_THRESHOLD:
                    logger.info(f"SauceNAO: similarity {similarity:.1f}% below threshold")
                    return None

                data_fields = best.get("data", {})
                source_title = data_fields.get("source") or data_fields.get("title") or ""
                ext_urls = data_fields.get("ext_urls") or []
                source_url = ext_urls[0] if ext_urls else ""

                part = data_fields.get("part", "")

                logger.info(
                    f"SauceNAO: match found - {source_title} "
                    f"(similarity={similarity:.1f}%, index={index_name})"
                )

                return {
                    "title": source_title,
                    "similarity": similarity / 100.0,
                    "source_url": source_url,
                    "part": part,
                    "index_name": index_name,
                    "index_id": index_id,
                    "is_anime": is_anime,
                    "source": "saucenao",
                }

    except aiohttp.ClientError as e:
        logger.error(f"SauceNAO network error: {e}")
        return None
    except Exception as e:
        logger.error(f"SauceNAO error: {type(e).__name__}: {e}")
        return None
