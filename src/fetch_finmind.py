from __future__ import annotations

"""FinMind 補洞層：只補「同交易日、目前為 null」的欄位。

用途（yfinance 抓不到或抓錯時的第二來源）
- USD/TWD ............ TaiwanExchangeRate（yfinance 的 TWD=X 常常缺當日）
- 台指期夜盤 / OI .... TaiwanFuturesDaily / TaiwanFuturesInstitutionalInvestors
- 美股個股 ........... USStockPrice（NVDA / AMD / TSM / AAPL / MSFT）
- 台積電 2330 ........ TaiwanStockPrice（用來對照 ADR 溢價，旁白可加一句）

規則（沿用 canonical 的 source_policy）
- 只有 date == 指定交易日 才採用；日期不符 -> 記錄 DATE_MISMATCH 並跳過。
- 只填 None／空陣列，永不覆寫既有非空值。
- 沒有 token 也能跑（免費層有流量限制），有 FINMIND_TOKEN 就帶上。

環境變數：FINMIND_TOKEN（GitHub Secret，選用）
"""

import os
from typing import Any

import requests

API = "https://api.finmindtrade.com/api/v4/data"
TIMEOUT = 25
TOKEN = os.getenv("FINMIND_TOKEN", "")


def _query(dataset: str, start: str, end: str | None = None, data_id: str | None = None) -> list[dict]:
    params: dict[str, Any] = {"dataset": dataset, "start_date": start}
    if end:
        params["end_date"] = end
    if data_id:
        params["data_id"] = data_id
    if TOKEN:
        params["token"] = TOKEN
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    r = requests.get(API, params=params, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    payload = r.json()
    if payload.get("status") not in (200, "200", None):
        raise RuntimeError(f"FinMind {dataset} failed: {payload.get('msg')}")
    return payload.get("data") or []


def _f(v) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _same_date(rows: list[dict], date_text: str) -> list[dict]:
    return [r for r in rows if str(r.get("date", ""))[:10] == date_text]


# ——— 台指期 ———

def futures_night_session(session_trade_date: str) -> dict:
    rows = _same_date(_query("TaiwanFuturesDaily", session_trade_date, session_trade_date, "TX"),
                      session_trade_date)
    night = [r for r in rows
             if any(k in str(r.get("trading_session", "")).lower()
                    for k in ("after", "盤後", "position_2"))]
    pool = night or rows
    if not pool:
        return {}
    # 取成交量最大的近月合約
    row = max(pool, key=lambda r: _f(r.get("volume")) or 0)
    close = _f(row.get("close"))
    spread = _f(row.get("spread"))
    return {
        "night_close": close,
        "change_points": spread,
        "change_pct": _f(row.get("spread_per")),
        "night_high": _f(row.get("max")),
        "night_low": _f(row.get("min")),
        "volume": _f(row.get("volume")),
        "total_oi": _f(row.get("open_interest")),
    }


def futures_foreign_oi(session_trade_date: str) -> dict:
    rows = _same_date(
        _query("TaiwanFuturesInstitutionalInvestors", session_trade_date, session_trade_date, "TX"),
        session_trade_date)
    foreign = [r for r in rows if "Foreign" in str(r.get("institutional_investors", ""))]
    if not foreign:
        return {}
    row = foreign[0]
    long_oi = _f(row.get("long_open_interest_balance_volume"))
    short_oi = _f(row.get("short_open_interest_balance_volume"))
    net = None
    if long_oi is not None and short_oi is not None:
        net = long_oi - short_oi
    return {"foreign_long_oi": long_oi, "foreign_short_oi": short_oi, "foreign_net_oi": net}


# ——— 匯率 / 個股 ———

def usd_twd(date_text: str) -> dict:
    rows = _same_date(_query("TaiwanExchangeRate", date_text, date_text, "USD"), date_text)
    if not rows:
        return {}
    row = rows[0]
    close = _f(row.get("spot_sell")) or _f(row.get("cash_sell"))
    return {"close": close, "trade_date": date_text} if close else {}


def us_stock(symbol: str, date_text: str) -> dict:
    rows = _same_date(_query("USStockPrice", date_text, date_text, symbol), date_text)
    if not rows:
        return {}
    row = rows[0]
    close, adj = _f(row.get("Close")), _f(row.get("Adj_Close"))
    return {"close": close if close is not None else adj, "trade_date": date_text}


def tsmc_2330(date_text: str) -> dict:
    rows = _same_date(_query("TaiwanStockPrice", date_text, date_text, "2330"), date_text)
    if not rows:
        return {}
    row = rows[0]
    return {"close": _f(row.get("close")), "change": _f(row.get("spread")), "trade_date": date_text}


# ——— 統一入口 ———

FINMIND_US = {"NVIDIA": "NVDA", "AMD": "AMD", "TSM ADR": "TSM", "Apple": "AAPL", "Microsoft": "MSFT"}


def fill_missing(report: dict, market_trade_date: str, audit: list[dict]) -> dict:
    """在 yfinance 補值之後執行；只補仍然是 None 的欄位。"""
    idx = report.setdefault("indices", {})
    stocks = report.setdefault("stocks", {})

    def note(section: str, name: str, status: str, **extra):
        audit.append({"source": "finmind", "section": section, "name": name, "status": status, **extra})

    twd = idx.setdefault("USD/TWD", {"symbol": "TWD=X"})
    if twd.get("close") is None:
        try:
            got = usd_twd(market_trade_date)
            if got:
                twd.update({k: v for k, v in got.items() if twd.get(k) is None})
                note("indices", "USD/TWD", "FILLED")
            else:
                note("indices", "USD/TWD", "NO_SAME_DATE_ROW")
        except Exception as exc:
            note("indices", "USD/TWD", "ERROR", error=str(exc))

    for name, sym in FINMIND_US.items():
        q = stocks.get(name)
        if not q or q.get("close") is not None:
            continue
        try:
            got = us_stock(sym, market_trade_date)
            if got.get("close") is not None:
                q["close"] = got["close"]
                q.setdefault("trade_date", market_trade_date)
                note("stocks", name, "FILLED_CLOSE")
            else:
                note("stocks", name, "NO_SAME_DATE_ROW")
        except Exception as exc:
            note("stocks", name, "ERROR", error=str(exc))

    tx = report.get("taiwan_futures") or {}
    if tx.get("night_close") is None and tx.get("session_trade_date"):
        try:
            got = futures_night_session(tx["session_trade_date"])
            got.update({k: v for k, v in (futures_foreign_oi(tx["session_trade_date"]) or {}).items()})
            filled = [k for k, v in got.items() if tx.get(k) is None and v is not None]
            for k in filled:
                tx[k] = got[k]
            if filled:
                tx["source"] = (tx.get("source") or "") + " + FinMind"
            note("taiwan_futures", "TX", "FILLED" if filled else "NO_SAME_DATE_ROW", fields=filled)
            report["taiwan_futures"] = tx
        except Exception as exc:
            note("taiwan_futures", "TX", "ERROR", error=str(exc))

    return report
