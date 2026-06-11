import json
import logging
import base64
from openai import AsyncOpenAI, BadRequestError
from config import GROQ_API_KEY, GROQ_MODEL, MAX_FRAMES

logger = logging.getLogger(__name__)

VISION_MODELS = [
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]

if GROQ_MODEL not in VISION_MODELS:
    logger.warning(
        f"{GROQ_MODEL} vision qo'llab-quvvatlamasligi mumkin! "
        f"Tavsiya: {VISION_MODELS}"
    )
else:
    logger.info(f"Using vision model: {GROQ_MODEL}")

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=60,
)


async def _try_model(model_name: str, messages: list, max_tokens: int, temperature: float = 0.3) -> str | None:
    try:
        logger.info(f"Trying model: {model_name}")
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
        logger.error(f"Model {model_name} BadRequest: {str(e)[:300]}")
        return None
    except Exception as e:
        logger.error(f"Model {model_name} error: {type(e).__name__}: {str(e)[:200]}")
        return None


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


async def _step1_describe(images: list[dict]) -> dict | None:
    """BOSQICH 1: Faqat visual features ni tasvirlash - hech qanday anime nomi YO'Q"""
    prompt = """You are a visual feature analyst. Describe ONLY what you see. DO NOT name any anime, movie, or series.

Analyze these video frames and describe:
1. CHARACTERS: hair color, hair length, hair style, eye color, skin tone, age, gender, clothing colors, clothing style, armor/weapons/accessories
2. SETTING: indoor/outdoor, medieval/modern/sci-fi/fantasy, landscape, buildings, sky, lighting
3. ART STYLE: animation quality, color palette (bright/dark/pastel), line thickness, 2D/3D/CGI
4. DISTINCTIVE FEATURES: creatures, monsters, magic effects, vehicles, technology, architecture
5. TEXT: any visible text, signs, logos, watermarks (include language if visible)
6. OBJECTS: weapons (swords, guns, bows), items (books, crystals, food), nature (trees, water, fire)

Respond in EXACT JSON:
{
    "characters": "detailed character description",
    "setting": "detailed setting description", 
    "art_style": "animation style description",
    "distinctive_features": "unique visual elements",
    "visible_text": "any text seen or 'none'",
    "objects": "notable objects or items",
    "mood": "dark/bright/cheerful/dramatic/action/comedy",
    "era_indicator": "what time period this suggests"
}

IMPORTANT: Describe WHAT you see, not what you think it is. Be extremely specific about colors, shapes, and details."""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, *images]}]

    for model in VISION_MODELS:
        text = await _try_model(model, messages, 800, temperature=0.2)
        if text:
            try:
                json_start = text.find("{")
                json_end = text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    parsed = json.loads(text[json_start:json_end])
                    logger.info(f"Step 1 description: {json.dumps(parsed, ensure_ascii=False)[:300]}")
                    return parsed
            except json.JSONDecodeError:
                pass
    return None


async def _step2_identify(images: list[dict], features: dict) -> dict | None:
    """BOSQICH 2: Tasvirlangan features asosida anime/kinoni aniqlash"""
    feature_text = "\n".join(f"- {k}: {v}" for k, v in features.items() if v and v != "none")

    prompt = f"""You are an anime/movie/series identification expert. Based on these VISUAL FEATURES extracted from video frames, identify what anime or movie this is.

VISUAL FEATURES:
{feature_text}

RULES:
1. You MUST match features to a specific anime/movie. Do NOT guess randomly.
2. Compare each feature against known series. ALL features should match, not just 1-2.
3. If NO anime/movie matches all features, set confidence below 0.3.
4. NEVER say "Attack on Titan" unless you see: 3D maneuvering gear, vertical maneuvering cables, Wall Maria/Rose/Sina, Titan shifters, Survey Corps green cloaks, ODM gear.

COMMON ANIME FEATURES (for reference):
- Attack on Titan: military uniforms, green cloaks, 3D gear, swords, walls, titans
- Tensura: blue/white slime, demon lords, fantasy medieval, magic circles, isekai
- Naruto: orange/black outfits, headbands, hand signs, chakra, leaf village
- One Piece: straw hat, pirates, Devil Fruits, Grand Line, ships
- Demon Slayer: Taisho era (1912-1926), katanas, breathing effects, demons
- Jujutsu Kaisen: modern Tokyo, school uniforms, cursed energy, domain expansion
- My Hero Academia: hero costumes, quirks, UA school, superpowers

Respond in EXACT JSON:
{{
    "type": "anime" or "movie" or "series",
    "title": "Original title (ONLY if features clearly match)",
    "title_english": "English title",
    "title_japanese": "Japanese/Romaji title",
    "year": "Release year",
    "genre": ["genre"],
    "studio": "Studio name",
    "confidence": 0.0-1.0,
    "matching_features": "Which features matched this anime",
    "non_matching_features": "Which features DON'T match",
    "anilist_id": "AniList ID if known",
    "tmdb_id": "TMDB ID if known",
    "search_terms": "keywords for database search if confidence < 0.6"
}}

If confidence < 0.4, put your best guess in "title" but set low confidence AND provide search_terms for database fallback."""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}, *images]}]

    for model in VISION_MODELS:
        text = await _try_model(model, messages, 1200, temperature=0.2)
        if text:
            try:
                json_start = text.find("{")
                json_end = text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    parsed = json.loads(text[json_start:json_end])
                    logger.info(f"Step 2 result: {parsed.get('title')} (confidence={parsed.get('confidence', 0):.2f})")
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
        logger.warning("Step 1 failed, trying single-step analysis")
        return await _single_step(images)

    result = await _step2_identify(images, features)

    if not result:
        logger.warning("Step 2 failed, trying single-step analysis")
        return await _single_step(images)

    result["visual_features"] = features.get("characters", "") + " | " + features.get("setting", "")
    return result


async def _single_step(images: list[dict]) -> dict:
    """Fallback: bitta qadamda aniqlash"""
    prompt = """Identify the anime/movie in these frames. Be extremely careful:
- DO NOT guess popular anime unless features match exactly
- Describe what you see FIRST, then identify
- If unsure, describe visual features and set confidence below 0.4

JSON format:
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

    for model in VISION_MODELS:
        text = await _try_model(model, messages, 1000, temperature=0.2)
        if text:
            try:
                json_start = text.find("{")
                json_end = text.rfind("}") + 1
                if json_start != -1 and json_end > json_start:
                    parsed = json.loads(text[json_start:json_end])
                    logger.info(f"Single step: {parsed.get('title')} ({parsed.get('confidence', 0):.2f})")
                    return parsed
            except json.JSONDecodeError:
                pass

    return {"type": "unknown", "title": "Could not analyze", "confidence": 0.0}
