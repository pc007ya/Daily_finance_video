from __future__ import annotations

from datetime import datetime, timezone


def _tone(change_pct):
    if change_pct is None:
        return "neutral"
    if change_pct >= 0.75:
        return "positive"
    if change_pct <= -0.75:
        return "negative"
    return "neutral"


def _market_takeaways(market: dict) -> list[str]:
    idx = market.get("indices", {})
    stocks = market.get("stocks", {})
    notes: list[str] = []

    sp = idx.get("S&P 500", {})
    nas = idx.get("NASDAQ", {})
    sox = idx.get("SOX", {})
    vix = idx.get("VIX", {})
    tsm = stocks.get("TSM ADR", {})

    if sp.get("change_pct") is not None and nas.get("change_pct") is not None:
        leader = "科技成長股" if nas["change_pct"] > sp["change_pct"] else "大型股大盤"
        notes.append(f"美股相對強弱：{leader}表現較強。")
    if sox.get("change_pct") is not None:
        notes.append(f"SOX 單日變動 {sox['change_pct']:+.2f}%，作為台股半導體開盤的重要風向。")
    if tsm.get("change_pct") is not None:
        notes.append(f"台積電 ADR 單日變動 {tsm['change_pct']:+.2f}%，留意台積電與先進製程供應鏈連動。")
    if vix.get("close") is not None:
        notes.append(f"VIX 收在 {vix['close']:.2f}，風險情緒判讀需搭配指數方向。")
    return notes


def build_report(market: dict, date_text: str, finviz_path: str | None = None) -> dict:
    idx = market.get("indices", {})
    stocks = market.get("stocks", {})
    return {
        "schema_version": "1.0",
        "report_date": date_text,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_policy": {
            "market": "yfinance",
            "heatmap": "Finviz NASDAQ-100 sector map",
            "note": "06:30 canonical package; 07:00 ChatGPT may append breaking news but must preserve these market figures for the same report date.",
        },
        "indices": idx,
        "stocks": stocks,
        "finviz": {
            "path": finviz_path,
            "url": "https://finviz.com/map?t=sec_ndx",
        },
        "weekly_calendar": market.get("weekly_calendar", []),
        "earnings_calendar": market.get("earnings_calendar", []),
        "ai_semiconductor_news": market.get("ai_semiconductor_news", []),
        "taiwan_futures": market.get("taiwan_futures", {}),
        "market_takeaways": _market_takeaways(market),
        "risk_tone": _tone((idx.get("S&P 500") or {}).get("change_pct")),
    }
