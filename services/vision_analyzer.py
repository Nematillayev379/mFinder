import json
import logging
import base64
from openai import AsyncOpenAI
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
    timeout=60,
)


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

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        *images,
                    ],
                }
            ],
            max_tokens=1000,
        )

        text = response.choices[0].message.content

        try:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                return json.loads(text[json_start:json_end])
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")

        return {
            "type": "unknown",
            "title": text[:200],
            "confidence": 0.0,
        }

    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return {"type": "unknown", "title": "API error", "confidence": 0.0}
