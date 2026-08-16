from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from .fetch_market import collect_market
from .fetch_finviz import capture_finviz


def main() -> None:
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei"))
    now = datetime.now(tz)
    out = Path(os.getenv("OUTPUT_DIR", "output")) / now.strftime("%Y-%m-%d")
    out.mkdir(parents=True, exist_ok=True)

    market = collect_market()
    (out / "market.json").write_text(json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8")

    capture_finviz(out / "finviz_nasdaq100.png")

    print(f"Prepared daily market package: {out}")
    print("Next stage: narration/script generation, Azure TTS, subtitle timing, and V9 render.")


if __name__ == "__main__":
    main()
