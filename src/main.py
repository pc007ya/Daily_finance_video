from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from .fetch_market import collect_market
from .fetch_finviz import capture_finviz
from .build_report import build_report
from .build_narration import build_narration
from .tts_edge import synthesize
from .render_video import render_daily_video


def main() -> None:
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei"))
    now = datetime.now(tz)
    date_text = now.strftime("%Y-%m-%d")
    out = Path(os.getenv("OUTPUT_DIR", "output")) / date_text
    out.mkdir(parents=True, exist_ok=True)

    # 1) Collect raw inputs.
    market = collect_market()
    (out / "market.json").write_text(
        json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    finviz = capture_finviz(out / "finviz_nasdaq100.png")

    # 2) Build ONE canonical morning package. Everything downstream reads this.
    report = build_report(market, date_text, str(finviz))
    report_path = out / "morning_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 3) Narration and slides share the exact same report object.
    narration = build_narration(report)
    (out / "narration_zh-TW.txt").write_text(narration, encoding="utf-8")

    voice = out / "voice.mp3"
    subtitles = out / "subtitles.srt"
    synthesize(narration, voice, subtitles)

    final = render_daily_video(report, finviz, voice, subtitles, out, date_text)

    print(f"Canonical morning report: {report_path}")
    print(f"Prepared daily finance video package: {out}")
    print(f"Final MP4: {final}")


if __name__ == "__main__":
    main()
