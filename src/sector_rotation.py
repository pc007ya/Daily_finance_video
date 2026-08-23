from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

SECTORS = {
    "Technology": "XLK",
    "Communication": "XLC",
    "Discretionary": "XLY",
    "Staples": "XLP",
    "Energy": "XLE",
    "Financials": "XLF",
    "Health Care": "XLV",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
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


def _quadrant(rs_ratio: float, rs_momentum: float) -> str:
    if rs_ratio >= 100 and rs_momentum >= 100:
        return "LEADING"
    if rs_ratio < 100 and rs_momentum >= 100:
        return "IMPROVING"
    if rs_ratio < 100 and rs_momentum < 100:
        return "LAGGING"
    return "WEAKENING"


def _zscore(s: pd.Series, window: int = 60) -> pd.Series:
    mean = s.rolling(window, min_periods=max(20, window // 2)).mean()
    std = s.rolling(window, min_periods=max(20, window // 2)).std().replace(0, pd.NA)
    return (s - mean) / std


def _rrg_proxy(relative_price: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Open RRG-style proxy centered at 100.

    StockCharts' JdK RS-Ratio/RS-Momentum formula is proprietary, so this project
    uses a reproducible approximation: rolling z-score of log relative price for
    RS-Ratio and rolling z-score of its 10-session change for RS-Momentum.
    """
    log_rel = relative_price.clip(lower=1e-12).map(__import__("math").log)
    ratio = 100 + 10 * _zscore(log_rel, 60)
    momentum = 100 + 10 * _zscore(ratio.diff(10), 60)
    return ratio, momentum


def _relative_return(close: pd.DataFrame, ticker: str, sessions: int) -> float:
    if len(close) <= sessions:
        return float("nan")
    sec = close[ticker].iloc[-1] / close[ticker].iloc[-1 - sessions] - 1
    spy = close["SPY"].iloc[-1] / close["SPY"].iloc[-1 - sessions] - 1
    return float((sec - spy) * 100)


def _taiwan_signal(row: dict) -> dict:
    q = row["quadrant"]
    if q == "LEADING":
        stance, score = "偏多關注", 2
    elif q == "IMPROVING":
        stance, score = "轉強觀察", 1
    elif q == "WEAKENING":
        stance, score = "追價風險升高", -1
    else:
        stance, score = "相對弱勢", -2
    return {
        "sector": row["name"],
        "ticker": row["ticker"],
        "quadrant": q,
        "stance": stance,
        "score": score,
        "groups": TAIWAN_MAP.get(row["name"], []),
    }


def build_sector_rotation(out_dir: Path, tail_sessions: int = 5) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    tickers = ["SPY", *SECTORS.values()]
    raw = yf.download(tickers, period="9mo", interval="1d", auto_adjust=True, progress=False)
    close = raw["Close"].dropna(how="all").ffill()

    if len(close) < 90:
        return {"status": "INSUFFICIENT_DATA", "sectors": []}

    rows, trails = [], {}
    for name, ticker in SECTORS.items():
        rel_price = close[ticker] / close["SPY"]
        rs_ratio, rs_momentum = _rrg_proxy(rel_price)
        frame = pd.DataFrame({"rs_ratio": rs_ratio, "rs_momentum": rs_momentum}).dropna()
        if len(frame) < tail_sessions:
            continue

        trail_df = frame.tail(tail_sessions)
        trail = [
            {
                "date": str(idx.date()),
                "rs_ratio": round(float(r.rs_ratio), 3),
                "rs_momentum": round(float(r.rs_momentum), 3),
            }
            for idx, r in trail_df.iterrows()
        ]

        latest = dict(trail[-1])
        latest.update({
            "name": name,
            "ticker": ticker,
            "relative_1d_pct": round(_relative_return(close, ticker, 1), 3),
            "relative_5d_pct": round(_relative_return(close, ticker, 5), 3),
            "relative_20d_pct": round(_relative_return(close, ticker, 20), 3),
        })
        latest["quadrant"] = _quadrant(latest["rs_ratio"], latest["rs_momentum"])

        if len(trail) > 1:
            prev = trail[-2]
            latest["previous_quadrant"] = _quadrant(prev["rs_ratio"], prev["rs_momentum"])
            latest["quadrant_change"] = latest["previous_quadrant"] != latest["quadrant"]
            dx = latest["rs_ratio"] - prev["rs_ratio"]
            dy = latest["rs_momentum"] - prev["rs_momentum"]
            latest["direction"] = {
                "dx": round(dx, 3),
                "dy": round(dy, 3),
                "trend": "UP_RIGHT" if dx >= 0 and dy >= 0 else
                         "UP_LEFT" if dx < 0 <= dy else
                         "DOWN_RIGHT" if dx >= 0 > dy else "DOWN_LEFT",
            }

        rows.append(latest)
        trails[name] = trail

    quadrants = ["LEADING", "IMPROVING", "LAGGING", "WEAKENING"]
    signals = {q.lower(): [r["ticker"] for r in rows if r["quadrant"] == q] for q in quadrants}
    signals["transitions"] = [
        f"{r['ticker']}: {r.get('previous_quadrant')} → {r['quadrant']}"
        for r in rows if r.get("quadrant_change")
    ]

    strongest = sorted(rows, key=lambda r: (r["relative_20d_pct"], r["relative_5d_pct"]), reverse=True)
    improving = sorted(
        [r for r in rows if r["quadrant"] == "IMPROVING"],
        key=lambda r: (r.get("direction", {}).get("dy", 0), r["relative_5d_pct"]),
        reverse=True,
    )

    tw = [_taiwan_signal(r) for r in rows]
    result = {
        "status": "OK",
        "method": "RRG_STYLE_PROXY",
        "method_note": "Open approximation; not proprietary JdK RS-Ratio/RS-Momentum.",
        "benchmark": "SPY",
        "tail_sessions": tail_sessions,
        "trade_date": str(close.index[-1].date()),
        "sectors": rows,
        "signals": signals,
        "leaders_20d": [r["ticker"] for r in strongest[:3]],
        "improving_focus": [r["ticker"] for r in improving[:3]],
        "taiwan_implications": tw,
        "taiwan_focus": sorted(tw, key=lambda x: (-x["score"], x["sector"])),
    }

    fig, ax = plt.subplots(figsize=(16, 9))
    ax.axhline(100, linewidth=1)
    ax.axvline(100, linewidth=1)

    for name, trail in trails.items():
        xs = [p["rs_ratio"] for p in trail]
        ys = [p["rs_momentum"] for p in trail]
        ticker = SECTORS[name]
        ax.plot(xs, ys, marker="o", alpha=.5)
        ax.scatter(xs[-1], ys[-1], marker="D", s=95)
        ax.annotate(ticker, (xs[-1], ys[-1]), xytext=(6, 2), textcoords="offset points", fontsize=10)

    ax.set_title(f"S&P 500 RRG-style Sector Rotation vs SPY | {result['trade_date']} | tail {tail_sessions} sessions")
    ax.set_xlabel("RS-Ratio proxy (100 = benchmark center)")
    ax.set_ylabel("RS-Momentum proxy (100 = benchmark center)")
    ax.text(.99, .98, "LEADING", transform=ax.transAxes, ha="right", va="top", fontweight="bold")
    ax.text(.01, .98, "IMPROVING", transform=ax.transAxes, va="top", fontweight="bold")
    ax.text(.01, .02, "LAGGING", transform=ax.transAxes, va="bottom", fontweight="bold")
    ax.text(.99, .02, "WEAKENING", transform=ax.transAxes, ha="right", va="bottom", fontweight="bold")
    ax.grid(alpha=.15)
    fig.tight_layout()

    png = out_dir / "sector_rotation.png"
    fig.savefig(png, dpi=150)
    plt.close(fig)

    result["path"] = str(png)
    (out_dir / "sector_rotation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return result
