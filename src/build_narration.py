from __future__ import annotations

"""旁白改為「分段」輸出：每一句都帶 scene id。

與舊版的差異
- 旁白完全不唸「距離五十二週高點約 X%」（實測 15 句 / 57.5 秒 / 全片 25%，且圖卡上已經有）。
  52W 距離只出現在圖卡的「距52W High」欄位。
- 讀 canonical 的 video_storyboard / narration_points / breaking_news / major_earnings /
  weekly_calendar / earnings_calendar / taiwan_futures，不再自己編重點。
- 沒有資料的段落不產生句子 -> 該分鏡整段不存在，畫面不會空轉。
- US10Y 用 bps 句型，不套「收盤價 + 距 52W 高」。
"""

SCENE_TITLES = {
    1: "今日三大重點",
    2: "美股四大指數",
    3: "市場雷達",
    4: "Finviz NASDAQ-100 熱力圖",
    5: "AI / 半導體",
    6: "今日重大新聞",
    7: "台指期夜盤 / OI",
    8: "今日與本週焦點",
}


def _fmt(v, digits=2):
    return None if v is None else f"{v:,.{digits}f}"


def _quote(name: str, q: dict, unit: str = "點") -> str | None:
    """52W 距離只留在圖卡上，旁白不唸（唸出來冗餘且吃秒數）。"""
    close, chg, pct = q.get("close"), q.get("change"), q.get("change_pct")
    if close is None or chg is None or pct is None:
        return None
    direction = "上漲" if chg >= 0 else "下跌"
    return f"{name}收在{_fmt(close)}{unit}，{direction}{_fmt(abs(chg))}{unit}，幅度{_fmt(abs(pct))}%。"


def _yield_sentence(q: dict) -> str | None:
    close = q.get("close")
    if close is None:
        return None
    bps = q.get("change_bps")
    if bps is None and q.get("change") is not None:
        bps = q["change"] * 100
    tail = ""
    if bps is not None:
        tail = f"，單日{'上升' if bps >= 0 else '下降'}{abs(bps):.0f}個基點"
    return f"美國十年期公債殖利率約在{_fmt(close)}%{tail}。"


def build_segments(report: dict) -> list[dict]:
    idx = report.get("indices", {})
    stocks = report.get("stocks", {})
    seg: list[dict] = []

    def add(scene: int, text: str | None):
        if text:
            seg.append({"scene": scene, "text": text})

    # 1 — 開場 + canonical 當日三大重點
    add(1, "兩分鐘掌握最新國際財經與台股盤前重點。")
    board = {s.get("scene"): s for s in report.get("video_storyboard", [])}
    for point in (board.get(1, {}).get("points") or [])[:3]:
        add(1, str(point).rstrip("。") + "。")

    # 2 — 四大指數
    for name in ["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000"]:
        add(2, _quote(name, idx.get(name, {})))

    # 3 — 雷達
    add(3, _quote("VIX恐慌指數", idx.get("VIX", {}), unit=""))
    add(3, _quote("美元指數", idx.get("DXY", {}), unit=""))
    add(3, _yield_sentence(idx.get("US10Y", {})))
    add(3, _quote("黃金", idx.get("GOLD", {}), unit="美元"))
    add(3, _quote("西德州原油", idx.get("WTI", {}), unit="美元"))
    add(3, _quote("美元兌新台幣", idx.get("USD/TWD", {}), unit=""))

    # 4 — Finviz（只在這一段講熱力圖）
    add(4, "接著看Finviz納斯達克一百熱力圖。")
    add(4, "方塊面積代表市值，綠色上漲、紅色下跌，先看科技權值再看產業擴散。")

    # 5 — 半導體與焦點個股（52W 只留關鍵標的）
    add(5, _quote("費城半導體指數", idx.get("SOX", {})))
    add(5, _quote("台積電ADR", stocks.get("TSM ADR", {}), unit="美元"))
    for name, spoken in [("NVIDIA", "NVIDIA"), ("AMD", "AMD"), ("Apple", "蘋果"), ("Microsoft", "微軟")]:
        add(5, _quote(spoken, stocks.get(name, {}), unit="美元"))

    # 6 — 重大新聞：優先用 canonical 的 narration_points，其次 breaking_news 標題
    points = report.get("narration_points") or []
    news_lines = [p for p in points if any(k in p for k in ("風險", "新聞", "通膨", "利率", "油"))][:3]
    if not news_lines:
        news_lines = [str(n.get("headline", "")) for n in report.get("breaking_news", [])[:3]]
    for line in news_lines:
        add(6, str(line).rstrip("。") + "。")

    # 7 — 台指期夜盤：沒抓到就整段不產生
    tx = report.get("taiwan_futures") or {}
    if tx.get("night_close") is not None:
        pts = tx.get("change_points")
        direction = "上漲" if (pts or 0) >= 0 else "下跌"
        s = f"台指期夜盤收在{_fmt(tx['night_close'], 0)}點"
        if pts is not None:
            s += f"，{direction}{abs(pts):,.0f}點"
        if tx.get("change_pct") is not None:
            s += f"，幅度{_fmt(abs(tx['change_pct']))}%"
        add(7, s + "。")
        if tx.get("foreign_net_oi") is not None:
            add(7, f"外資期貨淨未平倉{tx['foreign_net_oi']:,.0f}口，是判斷開盤方向的關鍵。")

    # 8 — 本週行事曆與財報（唸出真正的日期與公司）
    cal = [c for c in report.get("weekly_calendar", []) if c.get("importance") in ("HIGH", "CRITICAL")][:2]
    for c in cal:
        when = c.get("time_tw") or c.get("date") or ""
        add(8, f"{when}，{c.get('event', '')}。")
    earn = report.get("earnings_calendar", [])[:3]
    if earn:
        names = "、".join(f"{e.get('company', '')}" for e in earn if e.get("company"))
        add(8, f"財報方面留意{names}。")
    add(8, "以上是今天的國際財經晨報，投資有風險，資訊僅供市場觀察參考。")

    return seg


def build_narration(report: dict) -> str:
    """保留舊介面：整段文字（除錯／存檔用）。"""
    return "".join(s["text"] for s in build_segments(report))
