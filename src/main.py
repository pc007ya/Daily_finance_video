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


def _fill_nulls_same_date(target: dict, fallback: dict, market_trade_date: str, audit: list[dict], section: str) -> None:
    for name, fb in fallback.items():
        if name not in target:
            if fb.get("trade_date") == market_trade_date:
                target[name] = fb
                audit.append({"section": section, "name": name, "status": "FALLBACK_ADDED", "trade_date": fb.get("trade_date")})
            continue

        dst = target[name]
        fb_date = fb.get("trade_date")
        dst_date = dst.get("trade_date") or market_trade_date
        if fb_date != market_trade_date or dst_date != market_trade_date:
            audit.append({
                "section": section,
                "name": name,
                "status": "DATE_MISMATCH_NO_OVERRIDE",
                "canonical_trade_date": dst_date,
                "fallback_trade_date": fb_date,
            })
            continue

        filled = []
        for key, value in fb.items():
            if key in {"symbol", "trade_date"}:
                if not dst.get(key):
                    dst[key] = value
                continue
            if dst.get(key) is None or dst.get(key) == []:
                if value is not None and value != []:
                    dst[key] = value
                    filled.append(key)
        audit.append({
            "section": section,
            "name": name,
            "status": "MATCH_SAME_DATE",
            "trade_date": fb_date,
            "filled_fields": filled,
        })


def _load_canonical(date_text: str) -> dict | None:
    path = Path(os.getenv("CANONICAL_REPORT_PATH", "data/latest/morning_report.json"))
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("report_date") != date_text:
        print(f"Canonical report date mismatch: {data.get('report_date')} != {date_text}; using fallback build.")
        return None
    return data


def main() -> None:
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei"))
    now = datetime.now(tz)
    date_text = now.strftime("%Y-%m-%d")
    out = Path(os.getenv("OUTPUT_DIR", "output")) / date_text
    out.mkdir(parents=True, exist_ok=True)

    market = collect_market()
    (out / "market.json").write_text(
        json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    finviz = capture_finviz(out / "finviz_nasdaq100.png")

    canonical = _load_canonical(date_text)
    validation: list[dict] = []

    if canonical is not None:
        report = canonical
        market_trade_date = report.get("market_trade_date")
        if not market_trade_date:
            raise RuntimeError("Canonical morning_report.json is missing market_trade_date")

        report.setdefault("indices", {})
        report.setdefault("stocks", {})
        _fill_nulls_same_date(report["indices"], market.get("indices", {}), market_trade_date, validation, "indices")
        _fill_nulls_same_date(report["stocks"], market.get("stocks", {}), market_trade_date, validation, "stocks")

        report.setdefault("finviz", {})
        report["finviz"]["path"] = str(finviz)
        report["finviz"]["captured_by_github"] = True
        report["source_mode"] = "CHATGPT_CANONICAL_PLUS_SAME_DATE_GITHUB_VALIDATION"
    else:
        report = build_report(market, date_text, str(finviz))
        report["source_mode"] = "GITHUB_FALLBACK_NO_VALID_CANONICAL"
        validation.append({"status": "NO_VALID_CANONICAL", "report_date": date_text})

    report_path = out / "morning_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "validation_report.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    narration = build_narration(report)
    (out / "narration_zh-TW.txt").write_text(narration, encoding="utf-8")

    voice = out / "voice.mp3"
    subtitles = out / "subtitles.srt"
    synthesize(narration, voice, subtitles)

    final = render_daily_video(report, finviz, voice, subtitles, out, date_text)

    print(f"Canonical morning report: {report_path}")
    print(f"Validation report: {out / 'validation_report.json'}")
    print(f"Prepared daily finance video package: {out}")
    print(f"Final MP4: {final}")


if __name__ == "__main__":
    main()
