import logging
import aiohttp
from config import HTTP_TIMEOUT

logger = logging.getLogger(__name__)

JIKAN_API = "https://api.jikan.moe/v4"


async def _jikan_get(endpoint: str, params: dict = None) -> dict | None:
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            url = f"{JIKAN_API}/{endpoint}"
            async with session.get(url, params=params) as resp:
                if resp.status == 429:
                    logger.warning("Jikan: Rate limit hit, waiting 1s")
                    await __import__("asyncio").sleep(1)
                    async with session.get(url, params=params) as retry_resp:
                        if retry_resp.status != 200:
                            return None
                        data = await retry_resp.json()
                        return data.get("data")
                if resp.status != 200:
                    logger.warning(f"Jikan returned status {resp.status}")
                    return None
                data = await resp.json()
                return data.get("data")
    except Exception as e:
        logger.error(f"Jikan API error: {e}")
        return None


async def search_anime(title: str) -> dict | None:
    result = await _jikan_get("anime", {"q": title, "limit": 5})
    if not result:
        return None

    best = result[0]
    logger.info(f"Jikan search: '{title}' -> '{best.get('title', '')}' (mal_id={best.get('mal_id')})")
    return best


async def get_anime_by_id(mal_id: int) -> dict | None:
    return await _jikan_get(f"anime/{int(mal_id)}")


async def search_anime_advanced(title: str, studio: str = None, year: int = None) -> dict | None:
    params = {"q": title, "limit": 10}
    if year:
        params["start_date"] = f"{year}-01-01"
        params["end_date"] = f"{year}-12-31"

    result = await _jikan_get("anime", params)
    if result:
        return result[0]

    if studio:
        result = await _jikan_get("anime", {"q": studio, "limit": 5})
        if result:
            return result[0]

    return None


def normalize_to_anilist_format(jikan_data: dict) -> dict:
    title = jikan_data.get("title", "")
    title_japanese = jikan_data.get("title_japanese", "")
    title_english = jikan_data.get("title_english", "")

    return {
        "id": jikan_data.get("mal_id"),
        "title": {
            "romaji": title,
            "english": title_english or title,
            "native": title_japanese,
        },
        "description": jikan_data.get("synopsis", ""),
        "coverImage": {"large": jikan_data.get("images", {}).get("jpg", {}).get("large_image_url", "")},
        "startDate": {"year": jikan_data.get("year") or jikan_data.get("aired", {}).get("prop", {}).get("from", {}).get("year")},
        "endDate": {"year": jikan_data.get("aired", {}).get("prop", {}).get("to", {}).get("year")},
        "genres": [g.get("name", "") for g in jikan_data.get("genres", [])],
        "averageScore": jikan_data.get("score"),
        "meanScore": jikan_data.get("score"),
        "episodes": jikan_data.get("episodes"),
        "status": jikan_data.get("status", ""),
        "studios": {"nodes": [{"name": s.get("name", "")} for s in jikan_data.get("studios", [])]},
        "externalLinks": [
            {"site": "MyAnimeList", "url": f"https://myanimelist.net/anime/{jikan_data.get('mal_id', '')}"}
        ],
        "source": "jikan",
    }
