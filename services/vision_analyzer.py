import json
import logging
import base64
from openai import AsyncOpenAI, BadRequestError
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

VISION_MODELS = [
    "llama-3.2-90b-vision-preview",
    "llama-3.2-11b-vision-preview",
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

    prompt = """Analyze these video frames and identify the anime, movie, or TV series.

Look for:
1. Character designs (hair color, style, clothing, distinguishing features)
2. Art style and animation quality
3. Background settings and environments
4. Text overlays (Japanese, English, etc.)
5. Color palette and visual tone
6. Any logos, titles, or watermarks

Respond in this EXACT JSON format:
{
    "type": "anime" or "movie" or "series",
    "title": "Original title",
    "title_english": "English title if different",
    "title_japanese": "Japanese title if anime",
    "year": "Release year or range",
    "genre": ["genre1", "genre2"],
    "studio": "Studio name if anime",
    "episode": "Episode number if identifiable",
    "confidence": 0.0 to 1.0,
    "description": "Brief description",
    "anilist_id": "AniList ID if anime (numeric)",
    "tmdb_id": "TMDB ID if movie/series (numeric)"
}

If unsure, make your best guess and explain why. Be specific about distinguishing features."""

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
