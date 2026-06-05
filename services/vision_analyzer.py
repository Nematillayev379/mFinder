import json
import logging
import base64
from openai import AsyncOpenAI, BadRequestError
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

VISION_MODELS = [
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
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
            temperature=0.3,
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

    prompt = """CRITICAL: You must analyze visual features BEFORE naming anything. DO NOT default to popular anime.

STEP 1 - DESCRIBE WHAT YOU SEE (must be specific):
a) Characters visible: hair color/length, eye color, clothing, weapons, accessories
b) Setting: indoor/outdoor, modern/medieval/fantasy/sci-fi, day/night
c) Art style: line thickness, color saturation, animation era
d) Distinctive objects: weapons, vehicles, creatures, technology
e) Any text/logos on screen

STEP 2 - GENRE IDENTIFICATION:
Is this: isekai fantasy? school life? mecha? samurai? horror? comedy? shonen action?
DO NOT just say "shonen action" - be specific.

STEP 3 - CHECK AGAINST COMMON ANIME:
- "Attack on Titan": soldiers with 3D gear, swords, walls, titans, scouts regiment cloaks
- "Tensura/Slime": blue slime, demon lords, isekai, fantasy medieval, magic
- "Naruto": ninjas, headbands, jutsu hand signs
- "One Piece": straw hat, pirates, ships
- "Demon Slayer": Taisho era, swords, demons
- "Sword Art Online": VR, video game world, glowing swords
- "My Hero Academia": superpowers, hero costumes, school

ONLY name the anime if features CLEARLY match. If you see fantasy isekai with slimes/magic, it is NOT Attack on Titan.

STEP 4 - JSON RESPONSE:
{
    "type": "anime" or "movie" or "series",
    "title": "Title (ONLY if confident)",
    "title_english": "English title",
    "title_japanese": "Japanese/Romaji title",
    "year": "Release year",
    "genre": ["genre"],
    "studio": "Studio",
    "confidence": 0.0-1.0,
    "visual_features": "Specific description of what you see in frames",
    "reasoning": "Why this identification matches features",
    "anilist_id": "AniList ID if known",
    "tmdb_id": "TMDB ID if known"
}

CRITICAL: If features don't match any anime, set confidence to 0.3 and describe visual features only. Better to say "I see isekai fantasy with blue slime" than to wrongly name Attack on Titan."""

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
