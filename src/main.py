from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from .fetch_market import collect_market
from .fetch_finviz import capture_finviz
from .build_narration import build_narration
from .tts_edge import synthesize


def main() -> None:
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei"))
    now = datetime.now(tz)
    out = Path(os.getenv("OUTPUT_DIR", "output")) / now.strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)

    market = collect_market()
    (out / "market.json").write_text(json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8")

    capture_finviz(out / "finviz_nasdaq100.png")

    narration = build_narration(market)
    (out / "narration_zh-TW.txt").write_text(narration, encoding="utf-8")

    synthesize(narration, out / "voice.mp3", out / "subtitles.srt")

    print(f"Prepared daily market package: {out}")
    print("Generated: market.json, finviz_nasdaq100.png, narration_zh-TW.txt, voice.mp3, subtitles.srt")
    print("Next stage: V9 visual renderer + FFmpeg final MP4.")


if __name__ == "__main__":
    main()
