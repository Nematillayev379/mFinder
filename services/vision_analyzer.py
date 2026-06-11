import json
import logging
import base64
from openai import AsyncOpenAI, BadRequestError
from config import GROQ_API_KEY, GROQ_MODEL, MAX_FRAMES

logger = logging.getLogger(__name__)

GEMINI_API_KEY = __import__("os").getenv("GEMINI_API_KEY", "")

VISION_MODELS = [
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

clients = {}

if GEMINI_API_KEY:
    clients["gemini"] = AsyncOpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        timeout=60,
    )
    logger.info("Gemini API configured")

clients["groq"] = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=60,
)


def _get_all_models():
    models = []
    if "gemini" in clients:
        models.append(("gemini", "gemini-2.0-flash"))
    if "groq" in clients:
        for m in VISION_MODELS:
            models.append(("groq", m))
    return models


def _load_images(frame_paths: list[str], limit: int = MAX_FRAMES) -> list[dict]:
    images = []
    for path in frame_paths[:limit]:
        try:
            with open(path, "rb") as f:
                images.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode()}"
                    }
                })
        except Exception as e:
            logger.error(f"Failed to read frame {path}: {e}")
            continue
    return images


async def _try_model(provider: str, model_name: str, messages: list, max_tokens: int, temperature: float = 0.2) -> str | None:
    client = clients.get(provider)
    if not client:
        return None
    try:
        logger.info(f"Trying {provider}/{model_name}")
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content
        return None
    except BadRequestError as e:
        logger.error(f"{provider}/{model_name} BadRequest: {str(e)[:300]}")
        return None
    except Exception as e:
        logger.error(f"{provider}/{model_name} error: {type(e).__name__}: {str(e)[:200]}")
        return None


async def _step1_describe(images: list[dict]) -> dict | None:
    prompt = """Analyze these video frames. Describe ONLY what you see visually. DO NOT name any anime/movie/series.

Describe in detail:
1. CHARACTERS: hair color, length, style, eye color, clothing, accessories, weapons
2. SETTING: indoor/outdoor, medieval/modern/sci-fi/fantasy, buildings, landscape
3. ART STYLE: animation quality, color palette, 2D/3D/CGI
4. DISTINCTIVE FEATURES: creatures, magic effects, vehicles, technology
5. TEXT: any visible text, signs, logos (include language)
6. OBJECTS: weapons, items, nature elements
7. MOOD: dark/bright/action/comedy/drama

Respond in EXACT JSON:
{
    "characters": "detailed character description",
    "setting": "detailed setting description",
    "art_style": "animation style",
    "distinctive_features": "unique elements",
    "visible_text": "any text or 'none'",
    "objects": "notable objects",
    "mood": "overall mood",
    "era_indicator": "time period suggested"
}

Be EXTREMELY specific about colors, shapes, and details."""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, *images]}]

    for provider, model in _get_all_models():
        text = await _try_model(provider, model, messages, 800, 0.1)
        if text:
            try:
                j_start = text.find("{")
                j_end = text.rfind("}") + 1
                if j_start != -1 and j_end > j_start:
                    parsed = json.loads(text[j_start:j_end])
                    logger.info(f"Step 1 ({provider}/{model}): {json.dumps(parsed, ensure_ascii=False)[:300]}")
                    return parsed
            except json.JSONDecodeError:
                pass
    return None


async def _step2_identify(images: list[dict], features: dict) -> dict | None:
    feature_text = "\n".join(f"- {k}: {v}" for k, v in features.items() if v and v != "none")

    prompt = f"""Based on these VISUAL FEATURES from video frames, identify the anime/movie/series.

VISUAL FEATURES:
{feature_text}

RULES:
1. Match ALL features to a specific anime/movie. Do NOT guess randomly.
2. ALL features should match, not just 1-2.
3. NEVER say "Attack on Titan" unless you see: 3D maneuvering gear, vertical cables, Wall Maria/Rose/Sina, Titan shifters, Survey Corps green cloaks.
4. If unsure, describe what genre/type it is and set confidence below 0.4.

IDENTIFICATION STEPS:
A) What genre is this? (isekai, school, mecha, shonen, etc.)
B) What era/time period? (medieval, modern, Taisho, sci-fi, etc.)
C) What are the most distinctive visual elements?
D) Which specific anime/movie matches ALL these features?

Respond in EXACT JSON:
{{
    "type": "anime" or "movie" or "series",
    "genre_guess": "specific genre",
    "era_guess": "time period",
    "distinctive_elements": "most unique features you see",
    "title": "Title ONLY if features CLEARLY match",
    "title_english": "English title",
    "title_japanese": "Japanese title",
    "year": "Release year",
    "genre": ["genre"],
    "studio": "Studio",
    "confidence": 0.0-1.0,
    "matching_features": "Which features match",
    "anilist_id": "AniList ID if known",
    "tmdb_id": "TMDB ID if known",
    "search_terms": "keywords for database search if confidence < 0.5"
}}

If confidence < 0.4, set title to your best guess but provide search_terms for fallback."""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, *images]}]

    for provider, model in _get_all_models():
        text = await _try_model(provider, model, messages, 1200, 0.1)
        if text:
            try:
                j_start = text.find("{")
                j_end = text.rfind("}") + 1
                if j_start != -1 and j_end > j_start:
                    parsed = json.loads(text[j_start:j_end])
                    logger.info(f"Step 2 ({provider}/{model}): {parsed.get('title')} (confidence={parsed.get('confidence', 0):.2f})")
                    return parsed
            except json.JSONDecodeError:
                pass
    return None


async def analyze_frames(frame_paths: list[str]) -> dict:
    images = _load_images(frame_paths)

    if not images:
        return {"type": "unknown", "title": "No frames to analyze", "confidence": 0.0}

    logger.info(f"Analyzing {len(images)} frames with 2-step process")

    features = await _step1_describe(images)

    if not features:
        logger.warning("Step 1 failed, trying single-step")
        return await _single_step(images)

    result = await _step2_identify(images, features)

    if not result:
        logger.warning("Step 2 failed, trying single-step")
        return await _single_step(images)

    result["visual_features"] = features.get("characters", "") + " | " + features.get("setting", "")
    return result


async def _single_step(images: list[dict]) -> dict:
    prompt = """Identify the anime/movie in these frames.
- DO NOT guess popular anime unless features match exactly
- If unsure, describe features and set confidence below 0.4

JSON:
{
    "type": "anime" or "movie" or "series",
    "title": "Title or 'Unknown'",
    "title_english": "English title",
    "title_japanese": "Japanese title",
    "year": "Year",
    "genre": ["genre"],
    "studio": "Studio",
    "confidence": 0.0-1.0,
    "visual_features": "What you see",
    "reasoning": "Why this match",
    "anilist_id": "ID if known",
    "tmdb_id": "ID if known",
    "search_terms": "keywords if low confidence"
}"""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, *images]}]

    for provider, model in _get_all_models():
        text = await _try_model(provider, model, messages, 1000, 0.1)
        if text:
            try:
                j_start = text.find("{")
                j_end = text.rfind("}") + 1
                if j_start != -1 and j_end > j_start:
                    parsed = json.loads(text[j_start:j_end])
                    logger.info(f"Single step ({provider}/{model}): {parsed.get('title')} ({parsed.get('confidence', 0):.2f})")
                    return parsed
            except json.JSONDecodeError:
                pass

    return {"type": "unknown", "title": "Could not analyze", "confidence": 0.0}
