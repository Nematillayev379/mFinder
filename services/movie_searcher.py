import logging
import aiohttp
from config import TMDB_API_KEY, HTTP_TIMEOUT

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"


async def _tmdb_get(endpoint: str, params: dict = None) -> dict | None:
    if not TMDB_API_KEY:
        logger.warning("TMDB API key not configured")
        return None

    timeout = aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            all_params = {"api_key": TMDB_API_KEY, "language": "en-US"}
            if params:
                all_params.update(params)
            async with session.get(f"{TMDB_BASE}{endpoint}", params=all_params) as resp:
                if resp.status != 200:
                    logger.warning(f"TMDB returned status {resp.status} for {endpoint}")
                    return None
                return await resp.json()
    except Exception as e:
        logger.error(f"TMDB API error: {e}")
        return None


async def search_movie(title: str) -> dict | None:
    data = await _tmdb_get("/search/movie", {"query": title})
    if data:
        results = data.get("results", [])
        if results:
            return results[0]
    return None


async def search_tv(title: str) -> dict | None:
    data = await _tmdb_get("/search/tv", {"query": title})
    if data:
        results = data.get("results", [])
        if results:
            return results[0]
    return None


async def get_movie_details(movie_id: int) -> dict | None:
    return await _tmdb_get(f"/movie/{movie_id}")


async def get_tv_details(tv_id: int) -> dict | None:
    return await _tmdb_get(f"/tv/{tv_id}")
