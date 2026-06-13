import html
import re
from utils.languages import get_message
from services.streaming_finder import get_free_options, get_paid_options


def clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'<[^>]+>', '', text)


def escape(text) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def format_result(ai_result: dict, anime_data: dict | None, movie_data: dict | None, lang: str) -> str:
    media_type = ai_result.get("type", "unknown")

    if media_type == "anime" and anime_data:
        return format_anime(ai_result, anime_data, lang)
    elif media_type in ("movie", "series") and movie_data:
        return format_movie(ai_result, movie_data, lang)
    else:
        return format_generic(ai_result, lang)


def format_anime(ai_result: dict, data: dict, lang: str) -> str:
    title = data.get("title", {})
    name = title.get("english") or title.get("romaji") or ai_result.get("title", "Unknown")
    name_jp = title.get("native", "")

    year = data.get("startDate", {}).get("year", ai_result.get("year", "?"))
    genres = ", ".join(data.get("genres", []))
    score = data.get("averageScore") or data.get("meanScore")
    score_str = f"{score}/100" if score else "N/A"

    episodes = data.get("episodes", "?")
    status = data.get("status", "")

    studios = data.get("studios", {}).get("nodes", [])
    studio = studios[0].get("name", "") if studios else ""

    description = clean_html(data.get("description") or ai_result.get("description", ""))[:300]

    links = data.get("externalLinks", [])
    mal_link = ""
    for link in links:
        if "myanimelist" in link.get("site", "").lower():
            mal_link = link.get("url", "")
            break
    if not mal_link:
        source = data.get("source", "")
        mal_id = data.get("id")
        if source == "jikan" and mal_id:
            mal_link = f"https://myanimelist.net/anime/{mal_id}"

    msg = "🎬 <b>ANIME TOPILDI!</b>\n\n"
    msg += f"📌 <b>Nomi:</b> {escape(name)}\n"
    if name_jp:
        msg += f"🇯🇵 <b>Yaponcha:</b> {escape(name_jp)}\n"
    msg += f"📅 <b>Yili:</b> {escape(year)}\n"
    msg += f"🎭 <b>Janr:</b> {escape(genres)}\n"
    if studio:
        msg += f"🏢 <b>Studio:</b> {escape(studio)}\n"
    msg += f"⭐ <b>Reyting:</b> {escape(score_str)}\n"
    msg += f"📺 <b>Qismlar:</b> {escape(episodes)}\n"
    msg += f"📊 <b>Holat:</b> {escape(status)}\n"

    if description:
        msg += f"\n📝 <b>Tavsif:</b>\n{escape(description)}...\n"

    if mal_link:
        msg += f'\n🔗 <b>MyAnimeList:</b> <a href="{mal_link}">Ko\'rish</a>\n'

    free_opts = get_free_options(lang, "anime")
    if free_opts:
        msg += "\n📺 <b>Bepul ko'rish:</b>\n"
        for opt in free_opts[:3]:
            msg += f'  • <a href="{opt["url"]}">{escape(opt["name"])}</a>\n'

    paid_opts = get_paid_options("anime")
    if paid_opts:
        msg += "\n💰 <b>Pullik platformalar:</b>\n"
        for opt in paid_opts[:3]:
            msg += f'  • <a href="{opt["url"]}">{escape(opt["name"])}</a>\n'

    return msg


def format_movie(ai_result: dict, data: dict, lang: str) -> str:
    name = data.get("title") or ai_result.get("title", "Unknown")
    original_name = data.get("original_title", "")

    release_date = data.get("release_date")
    if release_date:
        year = release_date[:4]
    else:
        year = ai_result.get("year", "?")

    genres = ", ".join([g.get("name", "") for g in data.get("genres", [])])
    rating = data.get("vote_average", ai_result.get("rating", "?"))
    rating_str = f"{rating}/10" if rating else "N/A"

    overview = clean_html(data.get("overview") or ai_result.get("description", ""))[:300]

    tmdb_id = data.get("id") or ai_result.get("tmdb_id")
    media_type = ai_result.get("type", "movie")
    tmdb_path = "tv" if media_type == "series" else "movie"
    tmdb_link = f"https://www.themoviedb.org/{tmdb_path}/{tmdb_id}" if tmdb_id else ""

    header = "📺 <b>SERIAL TOPILDI!</b>\n\n" if media_type == "series" else "🎬 <b>KINO TOPILDI!</b>\n\n"
    msg = header
    msg += f"📌 <b>Nomi:</b> {escape(name)}\n"
    if original_name and original_name != name:
        msg += f"🌐 <b>Asl nomi:</b> {escape(original_name)}\n"
    msg += f"📅 <b>Yili:</b> {escape(year)}\n"
    msg += f"🎭 <b>Janr:</b> {escape(genres)}\n"
    msg += f"⭐ <b>Reyting:</b> {escape(rating_str)}\n"

    if overview:
        msg += f"\n📝 <b>Tavsif:</b>\n{escape(overview)}...\n"

    if tmdb_link:
        msg += f'\n🔗 <b>TMDB:</b> <a href="{tmdb_link}">Ko\'rish</a>\n'

    free_opts = get_free_options(lang, media_type)
    if free_opts:
        msg += "\n📺 <b>Bepul ko'rish:</b>\n"
        for opt in free_opts[:3]:
            msg += f'  • <a href="{opt["url"]}">{escape(opt["name"])}</a>\n'

    paid_opts = get_paid_options(media_type)
    if paid_opts:
        msg += "\n💰 <b>Pullik platformalar:</b>\n"
        for opt in paid_opts[:3]:
            msg += f'  • <a href="{opt["url"]}">{escape(opt["name"])}</a>\n'

    return msg


def format_generic(ai_result: dict, lang: str) -> str:
    title = ai_result.get("title", "Unknown")
    confidence = ai_result.get("confidence", 0)
    visual_features = ai_result.get("visual_features", "")
    reasoning = ai_result.get("reasoning", "")

    if title in ("All models failed - check logs", "No frames to analyze", "Empty API response", "Empty content"):
        msg = "🔍 <b>TAHLIL NATIJASI</b>\n\n"
        msg += "⚠️ Video aniqlanmadi.\n\n"
        msg += "💡 <b>Maslahatlar:</b>\n"
        msg += "• Video 2-3 soniya uzunlikda bo'lsin\n"
        msg += "• Personajlar yoki sahna aniq ko'rinishi kerak\n"
        msg += "• Boshqa video sinab ko'ring\n"
        return msg

    msg = "🔍 <b>TAHLIL NATIJASI</b>\n\n"
    msg += f"📌 <b>Taxminiy nom:</b> {escape(title)}\n"
    msg += f"📊 <b>Ishonch:</b> {int(confidence * 100)}%\n"

    if visual_features:
        msg += f"\n👁 <b>Ko'rgan narsa:</b> {escape(visual_features)}\n"

    if reasoning:
        msg += f"\n🧠 <b>Sabab:</b> {escape(reasoning)}\n"

    msg += "\n⚠️ Aniqlashda qiyinchilik bo'ldi. Video aniqroq bo'lsa yaxshiroq natija beradi."

    return msg
