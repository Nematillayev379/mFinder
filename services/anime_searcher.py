import logging
import aiohttp
from config import HTTP_TIMEOUT

logger = logging.getLogger(__name__)

ANILIST_API = "https://graphql.anilist.co"

SEARCH_QUERY = """
query ($search: String) {
    Media(search: $search, type: ANIME) {
        id
        title {
            romaji
            english
            native
        }
        description
        coverImage {
            large
        }
        bannerImage
        startDate {
            year
            month
            day
        }
        endDate {
            year
            month
            day
        }
        genres
        averageScore
        meanScore
        popularity
        status
        episodes
        duration
        source
        studios(isMain: true) {
            nodes {
                name
            }
        }
        externalLinks {
            site
            url
        }
    }
}
"""

SEARCH_BY_ID_QUERY = """
query ($id: Int) {
    Media(id: $id, type: ANIME) {
        id
        title {
            romaji
            english
            native
        }
        description
        coverImage {
            large
        }
        genres
        averageScore
        meanScore
        episodes
        status
        startDate {
            year
        }
        studios(isMain: true) {
            nodes {
                name
            }
        }
        externalLinks {
            site
            url
        }
    }
}
"""


async def search_anime(title: str) -> dict | None:
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                "query": SEARCH_QUERY,
                "variables": {"search": title},
            }
            async with session.post(ANILIST_API, json=payload) as resp:
                if resp.status != 200:
                    logger.warning(f"AniList returned status {resp.status}")
                    return None
                data = await resp.json()
                return data.get("data", {}).get("Media")
    except Exception as e:
        logger.error(f"AniList API error: {e}")
        return None


async def get_anime_by_id(anilist_id: int) -> dict | None:
    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {
                "query": SEARCH_BY_ID_QUERY,
                "variables": {"id": int(anilist_id)},
            }
            async with session.post(ANILIST_API, json=payload) as resp:
                if resp.status != 200:
                    logger.warning(f"AniList returned status {resp.status}")
                    return None
                data = await resp.json()
                return data.get("data", {}).get("Media")
    except Exception as e:
        logger.error(f"AniList API error: {e}")
        return None


async def search_anime_advanced(title: str, studio: str = None, year: int = None) -> dict | None:
    result = await search_anime(title)
    if result:
        return result

    if studio:
        result = await search_anime(studio)
        if result:
            return result

    if year:
        result = await search_anime(f"{title} {year}")
        if result:
            return result

    return None
