from __future__ import annotations

import json
from pathlib import Path
import matplotlib.pyplot as plt
import yfinance as yf

SECTORS = {
    "Technology": "XLK", "Communication": "XLC", "Discretionary": "XLY", "Staples": "XLP",
    "Energy": "XLE", "Financials": "XLF", "Health Care": "XLV", "Industrials": "XLI",
    "Materials": "XLB", "Real Estate": "XLRE", "Utilities": "XLU",
}

TAIWAN_MAP = {
    "Technology": ["台積電/半導體", "AI Server/ASIC", "PCB/散熱/電源"],
    "Communication": ["網通", "伺服器連接", "電信"],
    "Discretionary": ["汽車/零組件", "運動休閒", "消費電子"],
    "Staples": ["食品", "通路", "民生消費"],
    "Energy": ["塑化/能源", "油氣", "航運"],
    "Financials": ["金控", "銀行", "保險"],
    "Health Care": ["生技", "醫材", "製藥"],
    "Industrials": ["重電", "自動化", "工具機"],
    "Materials": ["鋼鐵", "化工", "原物料"],
    "Real Estate": ["營建", "資產", "建材"],
    "Utilities": ["電力設備", "儲能", "綠能"],
}


def _quadrant(x: float, y: float) -> str:
    if x >= 0 and y >= 0: return "LEADING"
    if x < 0 and y >= 0: return "EMERGING"
    if x < 0 and y < 0: return "LAGGING"
    return "FADING"


def _taiwan_signal(row: dict) -> dict:
    q = row["quadrant"]
    if q == "LEADING": stance, score = "偏多關注", 2
    elif q == "EMERGING": stance, score = "轉強觀察", 1
    elif q == "FADING": stance, score = "追價風險升高", -1
    else: stance, score = "相對弱勢", -2
    return {"sector": row["name"], "quadrant": q, "stance": stance, "score": score,
            "groups": TAIWAN_MAP.get(row["name"], [])}


def build_sector_rotation(out_dir: Path, tail_sessions: int = 5) -> dict:
    tickers = ["SPY", *SECTORS.values()]
    raw = yf.download(tickers, period="3mo", interval="1d", auto_adjust=True, progress=False)
    close = raw["Close"].dropna(how="all").ffill()
    if len(close) < 27: return {"status": "INSUFFICIENT_DATA", "sectors": []}
    rows, trails = [], {}
    for name, ticker in SECTORS.items():
        trail = []
        for back in range(tail_sessions - 1, -1, -1):
            end = len(close) - 1 - back
            if end < 21: continue
            sec_1m = close[ticker].iloc[end] / close[ticker].iloc[end - 21] - 1
            spy_1m = close["SPY"].iloc[end] / close["SPY"].iloc[end - 21] - 1
            sec_1w = close[ticker].iloc[end] / close[ticker].iloc[end - 5] - 1
            spy_1w = close["SPY"].iloc[end] / close["SPY"].iloc[end - 5] - 1
            trail.append({"date": str(close.index[end].date()),
                          "relative_1m_pct": round((sec_1m-spy_1m)*100, 3),
                          "relative_1w_pct": round((sec_1w-spy_1w)*100, 3)})
        if not trail: continue
        latest = trail[-1]; latest["name"], latest["ticker"] = name, ticker
        latest["quadrant"] = _quadrant(latest["relative_1m_pct"], latest["relative_1w_pct"])
        if len(trail) > 1:
            latest["previous_quadrant"] = _quadrant(trail[-2]["relative_1m_pct"], trail[-2]["relative_1w_pct"])
            latest["quadrant_change"] = latest["previous_quadrant"] != latest["quadrant"]
        rows.append(latest); trails[name] = trail
    signals = {q.lower(): [r["name"] for r in rows if r["quadrant"] == q] for q in ["LEADING","EMERGING","LAGGING","FADING"]}
    signals["transitions"] = [f"{r['name']}: {r.get('previous_quadrant')} → {r['quadrant']}" for r in rows if r.get("quadrant_change")]
    tw = [_taiwan_signal(r) for r in rows]
    tw_focus = sorted(tw, key=lambda x: (-x["score"], x["sector"]))
    result = {"status":"OK","benchmark":"SPY","one_month_sessions":21,"one_week_sessions":5,
              "tail_sessions":tail_sessions,"trade_date":str(close.index[-1].date()),"sectors":rows,
              "signals":signals,"taiwan_implications":tw,"taiwan_focus":tw_focus}
    fig, ax = plt.subplots(figsize=(16,9)); ax.axhline(0,linewidth=1); ax.axvline(0,linewidth=1)
    for name, trail in trails.items():
        xs=[p["relative_1m_pct"] for p in trail]; ys=[p["relative_1w_pct"] for p in trail]
        ax.plot(xs,ys,marker="o",alpha=.45); ax.scatter(xs[-1],ys[-1],marker="D",s=90)
        ax.annotate(name,(xs[-1],ys[-1]),xytext=(6,2),textcoords="offset points",fontsize=10)
    ax.set_title(f"S&P 500 Sector Rotation vs SPY | {result['trade_date']} | tail: last {tail_sessions} sessions")
    ax.set_xlabel("vs SPY, 1 month %"); ax.set_ylabel("vs SPY, 1 week %")
    ax.text(.01,.98,"EMERGING",transform=ax.transAxes,va="top",fontweight="bold"); ax.text(.99,.98,"LEADING",transform=ax.transAxes,ha="right",va="top",fontweight="bold")
    ax.text(.01,.02,"LAGGING",transform=ax.transAxes,va="bottom",fontweight="bold"); ax.text(.99,.02,"FADING",transform=ax.transAxes,ha="right",va="bottom",fontweight="bold")
    ax.grid(alpha=.15); fig.tight_layout(); png=out_dir/"sector_rotation.png"; fig.savefig(png,dpi=150); plt.close(fig)
    result["path"]=str(png); (out_dir/"sector_rotation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
