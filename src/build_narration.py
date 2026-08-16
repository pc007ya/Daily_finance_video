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
    return f"{name}收在{_fmt(close)}{unit}，{direction}{_fmt(abs(change))}{unit}，幅度{_fmt(abs(pct))}%。"


def build_narration(market: dict) -> str:
    idx = market.get("indices", {})
    stocks = market.get("stocks", {})

    parts = ["兩分鐘掌握最新國際財經與台股盤前重點。"]
    for name in ["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000"]:
        if name in idx:
            parts.append(_quote_sentence(name, idx[name]))

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
            s += f"目前距離五十二週高點約{_fmt(abs(dist))}%。"
        parts.append(s)

    parts.append("畫面同步顯示Finviz納斯達克一百最新一日收盤熱力圖。")
    parts.append("後續版本將加入重大財報、台指期夜盤未平倉量與完整台股盤前結論。")
    return "".join(parts)
