from __future__ import annotations


def _fmt(v, digits=2):
    if v is None:
        return "資料待確認"
    return f"{v:,.{digits}f}"


def _quote_sentence(name: str, q: dict, unit: str = "點") -> str:
    close = q.get("close")
    change = q.get("change")
    pct = q.get("change_pct")
    if close is None or change is None or pct is None:
        return f"{name}資料待確認。"
    direction = "上漲" if change >= 0 else "下跌"
    s = f"{name}收在{_fmt(close)}{unit}，{direction}{_fmt(abs(change))}{unit}，幅度{_fmt(abs(pct))}%。"
    dist = q.get("distance_from_52w_high_pct")
    if dist is not None:
        s += f"距離五十二週高點約{_fmt(abs(dist))}%。"
    return s


def build_narration(market: dict) -> str:
    idx = market.get("indices", {})
    stocks = market.get("stocks", {})

    parts = ["兩分鐘掌握最新國際財經與台股盤前重點。先看昨夜美股收盤。"]

    # Scene 2: US index overview. Keep this block together so the spoken order
    # follows the on-screen table.
    for name in ["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000"]:
        if name in idx:
            parts.append(_quote_sentence(name, idx[name]))

    # Scene 3: cross-market / futures-style radar.
    if "VIX" in idx:
        parts.append(_quote_sentence("VIX恐慌指數", idx["VIX"], unit=""))
    if "DXY" in idx:
        parts.append(_quote_sentence("美元指數", idx["DXY"], unit=""))
    if "US10Y" in idx:
        parts.append(_quote_sentence("美國十年期公債殖利率", idx["US10Y"], unit=""))
    if "GOLD" in idx:
        parts.append(_quote_sentence("黃金", idx["GOLD"], unit="美元"))
    if "WTI" in idx:
        parts.append(_quote_sentence("西德州原油", idx["WTI"], unit="美元"))

    # Scene 4: Finviz must be narrated while the heatmap is actually on screen.
    parts.append("接著看Finviz納斯達克一百一日收盤熱力圖。方塊面積代表市值，綠色代表上漲、紅色代表下跌，快速確認資金集中在哪些產業與大型權值股。")

    # Scene 5: focused stocks with 52W context and mini price charts.
    if "SOX" in idx:
        parts.append(_quote_sentence("費城半導體指數", idx["SOX"]))
    for name in ["TSM ADR", "NVIDIA", "AMD", "Apple", "Microsoft"]:
        q = stocks.get(name)
        if not q or q.get("close") is None:
            continue
        close = q["close"]
        chg = q.get("change") or 0
        pct = q.get("change_pct") or 0
        dist = q.get("distance_from_52w_high_pct")
        direction = "上漲" if chg >= 0 else "下跌"
        s = f"{name}收在{_fmt(close)}美元，{direction}{_fmt(abs(chg))}美元，幅度{_fmt(abs(pct))}%。"
        if dist is not None:
            s += f"距離五十二週高點約{_fmt(abs(dist))}%。"
        parts.append(s)

    # Scene 6: weekly calendar / earnings page. Dedicated fetchers will replace
    # the fallback copy once live calendar data is available.
    cal = market.get("weekly_calendar") or []
    earn = market.get("earnings_calendar") or []
    if cal or earn:
        parts.append("最後看本週美股重要行事曆與大型企業財報，重點包含通膨、聯準會、就業數據，以及市值前百大企業財報。")
    else:
        parts.append("最後保留本週美股重要行事曆與大型企業財報頁，後續自動帶入CPI、PPI、聯準會利率決策、非農就業、失業率，以及市值前百大企業財報。")

    parts.append("以上是今天的國際財經晨報，投資有風險，以上資訊僅供市場觀察參考。")
    return "".join(parts)
