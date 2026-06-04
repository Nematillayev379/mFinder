FREE_STREAMING_SITES = {
    "uz": [
        {"name": "AnimeUz", "url": "https://animeuz.uz"},
        {"name": "Kinolar.uz", "url": "https://kinolar.uz"},
        {"name": "Uztelecom TV", "url": "https://tv.uztelecom.uz"},
    ],
    "en": [
        {"name": "Crunchyroll (Free)", "url": "https://www.crunchyroll.com"},
        {"name": "YouTube (Official)", "url": "https://www.youtube.com"},
        {"name": "Tubi", "url": "https://tubitv.com"},
        {"name": "Pluto TV", "url": "https://pluto.tv"},
        {"name": "Peacock Free", "url": "https://www.peacocktv.com"},
    ],
    "ru": [
        {"name": "AniLibria", "url": "https://anilibria.to"},
        {"name": "Jut.su", "url": "https://jut.su"},
        {"name": "Okko (Free)", "url": "https://okko.tv"},
        {"name": "Ivi (Free)", "url": "https://www.ivi.ru"},
    ],
    "ja": [
        {"name": "ABEMA", "url": "https://abema.tv"},
        {"name": "TVer", "url": "https://tver.jp"},
        {"name": "YouTube (Official)", "url": "https://www.youtube.com"},
    ],
}

PAID_PLATFORMS = {
    "anime": [
        {"name": "Crunchyroll", "url": "https://www.crunchyroll.com"},
        {"name": "Netflix", "url": "https://www.netflix.com"},
        {"name": "Hulu", "url": "https://www.hulu.com"},
    ],
    "movie": [
        {"name": "Netflix", "url": "https://www.netflix.com"},
        {"name": "Amazon Prime", "url": "https://www.amazon.com/prime"},
        {"name": "Disney+", "url": "https://www.disneyplus.com"},
        {"name": "HBO Max", "url": "https://www.max.com"},
    ],
    "series": [
        {"name": "Netflix", "url": "https://www.netflix.com"},
        {"name": "Amazon Prime", "url": "https://www.amazon.com/prime"},
        {"name": "Disney+", "url": "https://www.disneyplus.com"},
        {"name": "HBO Max", "url": "https://www.max.com"},
    ],
}


def get_free_options(lang: str, media_type: str = "anime") -> list[dict]:
    return FREE_STREAMING_SITES.get(lang, FREE_STREAMING_SITES["en"]).copy()


def get_paid_options(media_type: str) -> list[dict]:
    return PAID_PLATFORMS.get(media_type, PAID_PLATFORMS.get("movie", []))
