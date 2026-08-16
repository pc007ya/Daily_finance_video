from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path
import edge_tts

VOICE = "zh-TW-HsiaoChenNeural"
RATE = "-2%"


def _audio_duration(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path)
    ]).decode().strip())


def _ts(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _fallback_srt(text: str, duration: float) -> str:
    parts = [p.strip() for p in re.split(r"(?<=[。！？；])", text) if p.strip()]
    if not parts:
        parts = [text.strip() or "國際財經晨報"]
    total = max(1, sum(len(p) for p in parts))
    cur = 0.0
    blocks = []
    for i, part in enumerate(parts, 1):
        share = duration * len(part) / total
        end = duration if i == len(parts) else min(duration, cur + max(1.2, share))
        blocks.append(f"{i}\n{_ts(cur)} --> {_ts(end)}\n{part}\n")
        cur = end
    return "\n".join(blocks)


async def _synthesize(text: str, media_path: Path, subtitle_path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE)
    submaker = edge_tts.SubMaker()

    media_path.parent.mkdir(parents=True, exist_ok=True)
    subtitle_path.parent.mkdir(parents=True, exist_ok=True)
    with media_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    srt = ""
    try:
        srt = submaker.get_srt().strip()
    except Exception:
        srt = ""

    if not srt:
        srt = _fallback_srt(text, _audio_duration(media_path)).strip()

    subtitle_path.write_text(srt + "\n", encoding="utf-8")
    if not subtitle_path.exists() or subtitle_path.stat().st_size < 16:
        raise RuntimeError("Subtitle generation failed")


def synthesize(text: str, media_path: str | Path, subtitle_path: str | Path) -> tuple[Path, Path]:
    media = Path(media_path)
    subtitles = Path(subtitle_path)
    asyncio.run(_synthesize(text, media, subtitles))
    return media, subtitles
