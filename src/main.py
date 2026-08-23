from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from .fetch_market import collect_market
from .fetch_finviz import capture_finviz
from .fetch_taifex import fetch_night_session
from .fetch_finmind import fill_missing
from .build_report import build_report
from .build_narration import build_segments
from .tts_edge import synthesize_segments
from .render_video_sector import render_daily_video
from .sector_rotation import build_sector_rotation


def _fill_nulls_same_date(target: dict, fallback: dict, market_trade_date: str, audit: list[dict], section: str) -> None:
    for name, fb in fallback.items():
        if name not in target:
            if fb.get("trade_date") == market_trade_date:
                target[name] = fb
                audit.append({"section": section, "name": name, "status": "FALLBACK_ADDED", "trade_date": fb.get("trade_date")})
            continue
        dst = target[name]; fb_date = fb.get("trade_date"); dst_date = dst.get("trade_date") or market_trade_date
        if fb_date != market_trade_date or dst_date != market_trade_date:
            audit.append({"section": section, "name": name, "status": "DATE_MISMATCH_NO_OVERRIDE", "canonical_trade_date": dst_date, "fallback_trade_date": fb_date})
            continue
        filled = []
        for key, value in fb.items():
            if key in {"symbol", "trade_date"}:
                if not dst.get(key): dst[key] = value
                continue
            if dst.get(key) is None or dst.get(key) == []:
                if value is not None and value != []: dst[key] = value; filled.append(key)
        audit.append({"section": section, "name": name, "status": "MATCH_SAME_DATE", "trade_date": fb_date, "filled_fields": filled})


def _load_canonical(date_text: str) -> dict | None:
    path = Path(os.getenv("CANONICAL_REPORT_PATH", "data/latest/morning_report.json"))
    if not path.exists(): return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("report_date") != date_text:
        print(f"Canonical report date mismatch: {data.get('report_date')} != {date_text}; using fallback build.")
        return None
    return data


def main() -> None:
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Taipei")); now = datetime.now(tz); date_text = now.strftime("%Y-%m-%d")
    out = Path(os.getenv("OUTPUT_DIR", "output")) / date_text; out.mkdir(parents=True, exist_ok=True)
    market = collect_market(); (out / "market.json").write_text(json.dumps(market, ensure_ascii=False, indent=2), encoding="utf-8")
    finviz = capture_finviz(out / "finviz_nasdaq100.png")
    sector_rotation = build_sector_rotation(out)
    canonical = _load_canonical(date_text); validation: list[dict] = []
    if canonical is not None:
        report = canonical; market_trade_date = report.get("market_trade_date")
        if not market_trade_date: raise RuntimeError("Canonical morning_report.json is missing market_trade_date")
        report.setdefault("indices", {}); report.setdefault("stocks", {})
        _fill_nulls_same_date(report["indices"], market.get("indices", {}), market_trade_date, validation, "indices")
        _fill_nulls_same_date(report["stocks"], market.get("stocks", {}), market_trade_date, validation, "stocks")
        report.setdefault("finviz", {}); report["finviz"]["path"] = str(finviz); report["finviz"]["captured_by_github"] = True
        report["source_mode"] = "CHATGPT_CANONICAL_PLUS_SAME_DATE_GITHUB_VALIDATION"
    else:
        report = build_report(market, date_text, str(finviz)); report["market_trade_date"] = report.get("market_trade_date") or date_text
        report["source_mode"] = "GITHUB_FALLBACK_NO_VALID_CANONICAL"; validation.append({"status": "NO_VALID_CANONICAL", "report_date": date_text})
    report["sector_rotation"] = sector_rotation
    if sector_rotation.get("trade_date") != report.get("market_trade_date"):
        validation.append({"section":"sector_rotation","status":"DATE_MISMATCH","sector_trade_date":sector_rotation.get("trade_date"),"market_trade_date":report.get("market_trade_date")})
    tx_existing = report.get("taiwan_futures") or {}; session_date = tx_existing.get("session_trade_date") or date_text
    fetched_tx = fetch_night_session(session_date, validation); report["taiwan_futures"] = {**tx_existing, **{k: v for k, v in fetched_tx.items() if v is not None}}
    fill_missing(report, report.get("market_trade_date") or date_text, validation)
    report_path = out / "morning_report.json"; report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "validation_report.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    segments = build_segments(report); (out / "narration_zh-TW.txt").write_text("".join(s["text"] for s in segments), encoding="utf-8")
    tts = synthesize_segments(segments, out)
    final = render_daily_video(report, finviz, tts["voice"], tts["subtitles"], tts["timeline"], out, date_text)
    print(f"Canonical morning report: {report_path}"); print(f"Sector rotation: {sector_rotation.get('path')}"); print(f"Final MP4: {final}")


if __name__ == "__main__": main()
