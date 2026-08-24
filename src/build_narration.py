from __future__ import annotations

"""分段旁白：Finviz 後新增 Sector Rotation，後續 scene 順延。"""

SCENE_TITLES = {
    1: "今日三大重點",
    2: "美股四大指數",
    3: "市場雷達",
    4: "Finviz NASDAQ-100 熱力圖",
    5: "S&P 500 Sector Rotation",
    6: "AI / 半導體",
    7: "今日重大新聞",
    8: "台指期夜盤 / OI",
    9: "今日與本週焦點",
}


def _fmt(v, digits=2):
    return None if v is None else f"{v:,.{digits}f}"


def _quote(name: str, q: dict, unit: str = "點") -> str | None:
    close, chg, pct = q.get("close"), q.get("change"), q.get("change_pct")
    if close is None or chg is None or pct is None:
        return None
    direction = "上漲" if chg >= 0 else "下跌"
    return f"{name}收在{_fmt(close)}{unit}，{direction}{_fmt(abs(chg))}{unit}，幅度{_fmt(abs(pct))}%。"


def _yield_sentence(q: dict) -> str | None:
    close = q.get("close")
    if close is None: return None
    bps = q.get("change_bps")
    if bps is None and q.get("change") is not None: bps = q["change"] * 100
    tail = "" if bps is None else f"，單日{'上升' if bps >= 0 else '下降'}{abs(bps):.0f}個基點"
    return f"美國十年期公債殖利率約在{_fmt(close)}%{tail}。"


def _sector_sentence(rot: dict) -> list[str]:
    if rot.get("status") != "OK": return []
    sig = rot.get("signals", {})
    leading = sig.get("leading") or []
    improving = sig.get("improving") or []
    weakening = sig.get("weakening") or []
    transitions = sig.get("transitions") or []
    out = ["接著看標普五百RRG風格板塊輪動，以SPY為基準，觀察相對強度、動能與最近五個交易日的移動方向。"]
    if leading: out.append("目前領先象限以" + "、".join(leading[:3]) + "為主。")
    if improving: out.append("正在改善象限的板塊包括" + "、".join(improving[:3]) + "，留意是否進一步轉入領先。")
    if weakening: out.append("進入轉弱象限的板塊包括" + "、".join(weakening[:3]) + "，短線追價要更謹慎。")
    if transitions:
        spoken = "；".join(transitions[:2])
        spoken = (spoken.replace("LEADING", "領先").replace("IMPROVING", "改善")
                  .replace("LAGGING", "落後").replace("WEAKENING", "轉弱"))
        out.append("最新象限切換是" + spoken + "。")
    return out[:4]


def build_segments(report: dict) -> list[dict]:
    idx = report.get("indices", {}); stocks = report.get("stocks", {}); seg: list[dict] = []
    def add(scene: int, text: str | None):
        if text: seg.append({"scene": scene, "text": text})

    add(1, "兩分鐘掌握最新國際財經與台股盤前重點。")
    board = {s.get("scene"): s for s in report.get("video_storyboard", [])}
    for point in (board.get(1, {}).get("points") or [])[:3]: add(1, str(point).rstrip("。") + "。")

    for name in ["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000"]: add(2, _quote(name, idx.get(name, {})))

    add(3, _quote("VIX恐慌指數", idx.get("VIX", {}), unit="")); add(3, _quote("美元指數", idx.get("DXY", {}), unit=""))
    add(3, _yield_sentence(idx.get("US10Y", {}))); add(3, _quote("黃金", idx.get("GOLD", {}), unit="美元"))
    add(3, _quote("西德州原油", idx.get("WTI", {}), unit="美元")); add(3, _quote("美元兌新台幣", idx.get("USD/TWD", {}), unit=""))

    add(4, "接著看Finviz納斯達克一百熱力圖。")
    add(4, "方塊面積代表市值，綠色上漲、紅色下跌，先看科技權值再看產業擴散。")

    for line in _sector_sentence(report.get("sector_rotation") or {}): add(5, line)

    add(6, _quote("費城半導體指數", idx.get("SOX", {})))
    add(6, _quote("台積電ADR", stocks.get("TSM ADR", {}), unit="美元"))
    for name, spoken in [("NVIDIA", "NVIDIA"), ("AMD", "AMD"), ("Apple", "蘋果"), ("Microsoft", "微軟")]: add(6, _quote(spoken, stocks.get(name, {}), unit="美元"))

    points = report.get("narration_points") or []
    news_lines = [p for p in points if any(k in p for k in ("風險", "新聞", "通膨", "利率", "油"))][:3]
    if not news_lines: news_lines = [str(n.get("headline", "")) for n in report.get("breaking_news", [])[:3]]
    for line in news_lines: add(7, str(line).rstrip("。") + "。")

    tx = report.get("taiwan_futures") or {}
    if tx.get("night_close") is not None:
        pts = tx.get("change_points"); direction = "上漲" if (pts or 0) >= 0 else "下跌"
        s = f"台指期夜盤收在{_fmt(tx['night_close'], 0)}點"
        if pts is not None: s += f"，{direction}{abs(pts):,.0f}點"
        if tx.get("change_pct") is not None: s += f"，幅度{_fmt(abs(tx['change_pct']))}%"
        add(8, s + "。")
        if tx.get("foreign_net_oi") is not None: add(8, f"外資期貨淨未平倉{tx['foreign_net_oi']:,.0f}口，是判斷開盤方向的關鍵。")

    earn = report.get("earnings_calendar", [])[:3]
    names = "、".join(str(e.get("company", "")) for e in earn if e.get("company"))
    if names: add(9, f"本週財報：{names}。")
    add(9, "以上是今天的國際財經晨報，投資有風險，資訊僅供市場觀察參考。")
    return seg


def build_narration(report: dict) -> str:
    return "".join(s["text"] for s in build_segments(report))
