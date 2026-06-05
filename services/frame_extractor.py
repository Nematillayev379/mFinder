import asyncio
import logging
import os
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

TEMP_DIR = Path("data/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


async def extract_frames(video_path: str, max_frames: int = 5, interval: int = 2) -> list[str]:
    output_dir = TEMP_DIR / str(uuid.uuid4())
    output_dir.mkdir(parents=True, exist_ok=True)

    output_pattern = str(output_dir / "frame_%03d.jpg")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vf", f"fps=1/{interval}",
        "-vframes", str(max_frames),
        "-q:v", "2",
        "-y",
        output_pattern,
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30,
        )
        if process.returncode != 0:
            logger.warning(f"ffmpeg exited with code {process.returncode}")
    except asyncio.TimeoutError:
        logger.error("ffmpeg timed out")
        try:
            process.kill()
        except Exception:
            pass
        return []
    except Exception as e:
        logger.error(f"ffmpeg error: {e}")
        return []

    frames = sorted(output_dir.glob("frame_*.jpg"))
    return [str(f) for f in frames]


def cleanup_frames(frames: list[str]):
    for frame in frames:
        try:
            os.remove(frame)
        except OSError:
            pass
    try:
        frame_dir = Path(frames[0]).parent if frames else None
        if frame_dir and frame_dir.exists():
            remaining = list(frame_dir.iterdir())
            if not remaining:
                frame_dir.rmdir()
    except OSError:
        pass


def cleanup_old_temp():
    now = time.time()
    for item in TEMP_DIR.iterdir():
        try:
            if item.is_dir():
                age = now - item.stat().st_mtime
                if age > 3600:
                    import shutil
                    shutil.rmtree(item, ignore_errors=True)
        except Exception:
            pass
