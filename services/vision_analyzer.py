import json
import logging
import base64
from openai import AsyncOpenAI, BadRequestError
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

if GROQ_MODEL not in VISION_MODELS:
    logger.warning(
        f"⚠️ {GROQ_MODEL} vision qo'llab-quvvatlamasligi mumkin! "
        f"Tavsiya: {VISION_MODELS}"
    )
else:
    logger.info(f"✅ Using vision model: {GROQ_MODEL}")

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=60,
)


async def _try_model(model_name: str, messages: list, max_tokens: int) -> str | None:
    """Bir model bilan urinib ko'radi. None qaytarsa, model ishlamayapti"""
    try:
        logger.info(f"Trying model: {model_name}")
        response = await client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=max_tokens,
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


async def analyze_frames(frame_paths: list[str]) -> dict:
    images = []
    for path in frame_paths[:5]:
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

    if not images:
        return {"type": "unknown", "title": "No frames to analyze", "confidence": 0.0}

    prompt = """You are an expert anime/movie/series identifier. Analyze ALL frames carefully step by step.

STEP 1 - VISUAL FEATURE ANALYSIS (be very detailed):
- Character hair: color, length, style, accessories
- Character eyes: color, shape
- Character clothing: colors, style, armor/weapons, school uniform, traditional
- Art style: modern digital, 2010s, 2020s, classic, CGI mix
- Animation quality: cinematic, TV series, low-budget, high-budget
- Background: medieval fantasy, modern city, school, sci-fi, post-apocalyptic
- Distinctive elements: magic circles, mecha, demons, monsters, vehicles
- Color palette: bright/colorful, dark/grim, pastel
- Time period indicators: cars, technology, architecture
- Any on-screen text: titles, watermarks, signs, kanji

STEP 2 - CROSS-REFERENCE:
Compare these features with your knowledge. If features match a famous anime, that's a good sign. If features DO NOT match popular series, say so. DO NOT guess popular names if features don't match.

STEP 3 - IDENTIFICATION:
Provide your best guess. Be honest about uncertainty.

CRITICAL RULES:
- "Attack on Titan" has: 3D gear, soldiers with swords, walls, titans, scouts regiment, brown/blonde/black hair, green cloaks
- "Tensura/Slime" has: slime characters, demon lords, fantasy medieval, magic, isekai, blue slime protagonist
- "Naruto" has: ninjas, headbands, orange outfit, jutsu, leaf village
- "One Piece" has: pirates, straw hat, devil fruits, Grand Line
- Do NOT confuse isekai fantasy with shonen action

Respond in EXACT JSON:
{
    "type": "anime" or "movie" or "series",
    "title": "Original title (be honest if unsure)",
    "title_english": "English title",
    "title_japanese": "Japanese/Romaji title",
    "year": "Release year",
    "genre": ["genre1"],
    "studio": "Studio name",
    "confidence": 0.0-1.0,
    "visual_features": "Detailed description of what you see",
    "reasoning": "Why this identification",
    "anilist_id": "AniList ID if known (numeric)",
    "tmdb_id": "TMDB ID if known (numeric)"
}

If confidence < 0.6, say so. If you don't recognize it, give visual features only."""

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                *images,
            ],
        }
    ]

    models_to_try = [GROQ_MODEL] + [m for m in VISION_MODELS if m != GROQ_MODEL]

    text = None
    used_model = None
    for model in models_to_try:
        text = await _try_model(model, messages, 1000)
        if text:
            used_model = model
            logger.info(f"✅ Success with model: {model}")
            break
        else:
            logger.warning(f"❌ Model {model} failed, trying next...")

    if not text:
        logger.error("All vision models failed")
        return {
            "type": "unknown",
            "title": "All models failed - check logs",
            "confidence": 0.0,
        }

    logger.info(f"Groq response from {used_model}: {len(text)} chars")

    try:
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start != -1 and json_end > json_start:
            parsed = json.loads(text[json_start:json_end])
            logger.info(f"Parsed: type={parsed.get('type')}, title={parsed.get('title')}")
            return parsed
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error: {e}")

    return {
        "type": "unknown",
        "title": text[:200],
        "confidence": 0.0,
    }
