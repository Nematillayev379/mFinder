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
        models.append(("groq", GROQ_MODEL))
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


async def _try_model(provider: str, model_name: str, messages: list, max_tokens: int, temperature: float = 0.0) -> str | None:
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
    prompt = """Analyze these video frames and describe ONLY what you see visually. DO NOT name any anime, movie, or series.

Be EXTREMELY specific and detailed about:

1. CHARACTERS:
   - Hair: exact color (not just "dark" but "navy blue", "crimson red", "platinum blonde"), length (short/medium/long/very long), style (spiky/flowing/ponytail/braided/bob)
   - Eyes: exact color, shape (sharp/round/narrow), expression
   - Clothing: color, style (school uniform/suit/casual/fantasy armor), specific details (ribbon, tie, cape)
   - Accessories: weapons, jewelry, glasses, scars, distinctive marks
   - Age appearance: child/teen/adult

2. SETTING:
   - Location: school/classroom/castle/forest/city/space/underwater
   - Time: daytime/night/sunset/dawn
   - Architecture: Japanese/Western/medieval/modern/futuristic
   - Weather: clear/rainy/snowy/cloudy

3. ART STYLE:
   - Quality: high budget/low budget/CGI
   - Color palette: warm/cool/dark/bright/pastel/vibrant
   - Distinctive style: realistic/chibi/moe/realistic proportions

4. DISTINCTIVE FEATURES:
   - Any unique creatures, magic effects, technology
   - Special abilities, transformations, auras
   - Vehicles, mecha, weapons

5. TEXT (if any):
   - Any visible text, signs, logos, titles
   - Language (Japanese/English/other)

6. COMPOSITION:
   - Number of characters visible
   - Action scene vs dialogue scene
   - Camera angle (close-up/medium/wide)

Respond in EXACT JSON:
{
    "characters": "extremely detailed character descriptions",
    "setting": "detailed setting and environment",
    "art_style": "animation style and quality",
    "distinctive_features": "unique elements and effects",
    "visible_text": "any text or 'none'",
    "objects": "notable objects and items",
    "mood": "overall atmosphere",
    "era_indicator": "time period suggested"
}"""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, *images]}]

    for provider, model in _get_all_models():
        text = await _try_model(provider, model, messages, 800, 0.0)
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

CRITICAL RULES - FOLLOW EXACTLY:
1. Match ALL features to a specific anime/movie. Do NOT guess randomly.
2. ALL features should match, not just 1-2.
3. NEVER guess popular anime unless ALL features match perfectly.
4. NEVER say "Attack on Titan" unless you see: 3D maneuvering gear, vertical cables, Wall Maria/Rose/Sina, Titan shifters, Survey Corps green cloaks.
5. NEVER say "Naruto" unless you see: orange jumpsuit, headband with leaf symbol, whisker marks, blonde spiky hair.
6. NEVER say "One Piece" unless you see: straw hat, scars, pirate outfits, Devil Fruit powers.
7. NEVER say "Dragon Ball" unless you see: spiky black hair, orange gi, ki blasts, Saiyan tails.
8. If features don't clearly match any specific anime, describe the genre/type and set confidence below 0.3.

IDENTIFICATION STEPS:
A) What genre is this? (isekai, school, mecha, shonen, slice-of-life, fantasy, sci-fi, etc.)
B) What era/time period? (medieval, modern, Taisho, sci-fi future, etc.)
C) What are the most distinctive visual elements that make this unique?
D) Which specific anime/movie matches ALL these features? (If unsure, say "Unknown")

Respond in EXACT JSON:
{{
    "type": "anime" or "movie" or "series",
    "genre_guess": "specific genre",
    "era_guess": "time period",
    "distinctive_elements": "most unique features you see",
    "title": "Title ONLY if features CLEARLY match, otherwise 'Unknown'",
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

If confidence < 0.3, set title to 'Unknown' and provide search_terms for fallback."""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, *images]}]

    for provider, model in _get_all_models():
        text = await _try_model(provider, model, messages, 1200, 0.0)
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

    if result.get("confidence", 0) < 0.3:
        logger.warning(f"Low confidence ({result.get('confidence', 0):.2f}), adding search_terms")
        if not result.get("search_terms"):
            result["search_terms"] = " ".join([
                features.get("art_style", ""),
                features.get("era_indicator", ""),
                features.get("distinctive_features", ""),
            ]).strip()

    result["visual_features"] = features.get("characters", "") + " | " + features.get("setting", "")
    return result


async def _single_step(images: list[dict]) -> dict:
    prompt = """Identify the anime/movie in these frames.

CRITICAL RULES:
- DO NOT guess popular anime unless ALL features match exactly
- NEVER say "Attack on Titan", "Naruto", "One Piece", or "Dragon Ball" unless you see their EXACT distinctive features
- If unsure, describe features and set confidence below 0.3
- It's better to say "Unknown" than to guess incorrectly

Respond in EXACT JSON:
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
        text = await _try_model(provider, model, messages, 1000, 0.0)
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
