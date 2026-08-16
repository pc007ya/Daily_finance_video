from __future__ import annotations

import asyncio
from pathlib import Path
import edge_tts

VOICE = "zh-TW-HsiaoChenNeural"
RATE = "-2%"


async def _synthesize(text: str, media_path: Path, subtitle_path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE)
    submaker = edge_tts.SubMaker()

    media_path.parent.mkdir(parents=True, exist_ok=True)
    with media_path.open("wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)

    subtitle_path.write_text(submaker.get_srt(), encoding="utf-8")


def synthesize(text: str, media_path: str | Path, subtitle_path: str | Path) -> tuple[Path, Path]:
    media = Path(media_path)
    subtitles = Path(subtitle_path)
    asyncio.run(_synthesize(text, media, subtitles))
    return media, subtitles
