from __future__ import annotations

from dataclasses import dataclass, asdict, field
import yfinance as yf


@dataclass
class Quote:
    symbol: str
    close: float | None
    change: float | None
    change_pct: float | None
    week52_low: float | None = None
    week52_high: float | None = None
    week52_position_pct: float | None = None
    distance_from_52w_high_pct: float | None = None
    candles: list[dict] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def _safe(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def get_quote(symbol: str) -> Quote:
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="3mo", auto_adjust=False)
    info = ticker.fast_info

    close = _safe(hist["Close"].iloc[-1]) if not hist.empty else None
    prev = _safe(hist["Close"].iloc[-2]) if len(hist) >= 2 else None
    change = close - prev if close is not None and prev is not None else None
    pct = change / prev * 100 if change is not None and prev else None

    low = _safe(getattr(info, "year_low", None))
    high = _safe(getattr(info, "year_high", None))
    pos = None
    dist = None
    if close is not None and low is not None and high is not None and high > low:
        pos = (close - low) / (high - low) * 100
        dist = (close / high - 1) * 100

    candles = []
    if not hist.empty:
        for _, row in hist.tail(32).iterrows():
            o, h, l, c = (_safe(row.get(k)) for k in ["Open", "High", "Low", "Close"])
            if None not in (o, h, l, c):
                candles.append({"open": o, "high": h, "low": l, "close": c})

    return Quote(symbol, close, change, pct, low, high, pos, dist, candles)


def collect_market() -> dict:
    indices = {
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "DOW": "^DJI",
        "RUSSELL 2000": "^RUT",
        "VIX": "^VIX",
        "SOX": "^SOX",
        "DXY": "DX-Y.NYB",
        "US10Y": "^TNX",
        "GOLD": "GC=F",
        "WTI": "CL=F",
        "BRENT": "BZ=F",
        "USD/TWD": "TWD=X",
    }
    stocks = {
        "TSM ADR": "TSM",
        "NVIDIA": "NVDA",
        "AMD": "AMD",
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "Amazon": "AMZN",
        "Meta": "META",
        "Tesla": "TSLA",
    }

    return {
        "indices": {name: get_quote(sym).to_dict() for name, sym in indices.items()},
        "stocks": {name: get_quote(sym).to_dict() for name, sym in stocks.items()},
        "weekly_calendar": [],
        "earnings_calendar": [],
    }
