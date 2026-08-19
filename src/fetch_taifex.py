from __future__ import annotations

"""TAIFEX 台指期夜盤 + 未平倉 fetcher。

資料來源優先序
1. TAIFEX OpenAPI v1（官方、免金鑰，但**只提供最新一個交易日**）
   - DailyMarketReportFut ................ 期貨每日行情（含盤後交易時段）
   - MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate
                                          三大法人・區分各期貨契約（外資多空未平倉）
   - OpenInterestOfLargeTradersFutures ... 大額交易人未沖銷部位
2. FinMind TaiwanFuturesDaily / TaiwanFuturesInstitutionalInvestors（可回溯歷史）

夜盤歸屬規則：TAIFEX 把 15:00–05:00 的盤後交易歸到「次一交易日」。
本模組只接受 session_trade_date 相符的資料，日期不符一律回 None 並寫進 audit，
絕不用前一日盤中 OI 混充夜盤 OI（canonical 的 note 明確禁止）。

欄位名稱若 TAIFEX 改版：程式會記錄 UNKNOWN_SCHEMA 到 audit 並回 None，不會亂填。
"""

import os
from typing import Any

import requests

OPENAPI = "https://openapi.taifex.com.tw/v1"
TIMEOUT = 20
CONTRACT = "TX"

NIGHT_KEYS = ("盤後", "after", "AfterHours", "position_2", "after_market")


def _get(path: str) -> list[dict]:
    r = requests.get(f"{OPENAPI}/{path}", timeout=TIMEOUT,
                     headers={"User-Agent": "daily-finance-video/1.0"})
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("data", [])


def _num(v: Any) -> float | None:
    if v is None:
        return None
    s = str(v).replace(",", "").replace("%", "").strip()
    if s in ("", "-", "--", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pick(row: dict, *names: str):
    for n in names:
        for k, v in row.items():
            if n in k:
                return v
    return None


def _is_night(row: dict) -> bool:
    blob = " ".join(str(v) for v in row.values())
    return any(k in blob for k in NIGHT_KEYS)


def _norm_date(v: Any) -> str | None:
    s = str(v or "").strip().replace("/", "-")
    return s[:10] if len(s) >= 10 else None


def fetch_night_session(session_trade_date: str, audit: list[dict] | None = None) -> dict:
    """回傳 canonical taiwan_futures 的欄位；抓不到就全 None。"""
    audit = audit if audit is not None else []
    out: dict[str, Any] = {
        "contract": CONTRACT,
        "session_trade_date": session_trade_date,
        "night_close": None, "change_points": None, "change_pct": None,
        "night_high": None, "night_low": None, "volume": None,
        "total_oi": None, "oi_change": None,
        "foreign_long_oi": None, "foreign_short_oi": None,
        "foreign_net_oi": None, "foreign_net_change": None,
        "source": None,
    }

    # ——— 1. 官方行情（僅最新交易日）———
    try:
        rows = [r for r in _get("DailyMarketReportFut")
                if str(_pick(r, "契約", "contract_id", "Contract") or "").strip() == CONTRACT]
        night = [r for r in rows if _is_night(r)] or []
        same = [r for r in night if _norm_date(_pick(r, "日期", "Date", "trade_date")) == session_trade_date]
        if same:
            row = sorted(same, key=lambda r: str(_pick(r, "到期月份", "contract_date") or ""))[0]
            out.update({
                "night_close": _num(_pick(row, "收盤價", "最後成交價", "close")),
                "change_points": _num(_pick(row, "漲跌價", "漲跌")),
                "change_pct": _num(_pick(row, "漲跌%", "漲跌百分比")),
                "night_high": _num(_pick(row, "最高價", "high")),
                "night_low": _num(_pick(row, "最低價", "low")),
                "volume": _num(_pick(row, "成交量", "volume")),
                "total_oi": _num(_pick(row, "未沖銷", "未平倉", "open_interest")),
                "source": "TAIFEX OpenAPI DailyMarketReportFut (after-hours)",
            })
            audit.append({"section": "taiwan_futures", "status": "TAIFEX_OPENAPI_OK",
                          "session_trade_date": session_trade_date})
        else:
            audit.append({"section": "taiwan_futures", "status": "TAIFEX_OPENAPI_DATE_MISMATCH",
                          "wanted": session_trade_date,
                          "available": sorted({_norm_date(_pick(r, "日期", "Date")) for r in rows} - {None})})
    except Exception as exc:
        audit.append({"section": "taiwan_futures", "status": "TAIFEX_OPENAPI_ERROR", "error": str(exc)})

    # ——— 2. 外資未平倉（三大法人・區分各期貨契約）———
    try:
        rows = _get("MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate")
        tx = [r for r in rows
              if "臺股期貨" in str(_pick(r, "商品名稱", "契約", "contract") or "")
              and "外資" in str(_pick(r, "身份別", "identity") or "")]
        for row in tx:
            if _norm_date(_pick(row, "日期", "Date")) not in (session_trade_date, None):
                continue
            out["foreign_long_oi"] = _num(_pick(row, "多方未平倉口數", "未平倉多方口數"))
            out["foreign_short_oi"] = _num(_pick(row, "空方未平倉口數", "未平倉空方口數"))
            out["foreign_net_oi"] = _num(_pick(row, "多空未平倉口數淨額", "淨額"))
            audit.append({"section": "taiwan_futures", "status": "TAIFEX_FOREIGN_OI_OK"})
            break
    except Exception as exc:
        audit.append({"section": "taiwan_futures", "status": "TAIFEX_FOREIGN_OI_ERROR", "error": str(exc)})

    # ——— 3. FinMind 補洞（可回溯歷史；官方 OpenAPI 只有最新一日）———
    if out["night_close"] is None or out["foreign_net_oi"] is None:
        try:
            from .fetch_finmind import futures_night_session, futures_foreign_oi
            fm = futures_night_session(session_trade_date)
            for k, v in (fm or {}).items():
                if out.get(k) is None and v is not None:
                    out[k] = v
            if out["night_close"] is not None and not out["source"]:
                out["source"] = "FinMind TaiwanFuturesDaily (after_market)"
            if out["foreign_net_oi"] is None:
                foreign = futures_foreign_oi(session_trade_date)
                for k, v in (foreign or {}).items():
                    if out.get(k) is None and v is not None:
                        out[k] = v
            audit.append({"section": "taiwan_futures", "status": "FINMIND_FALLBACK_USED"})
        except Exception as exc:
            audit.append({"section": "taiwan_futures", "status": "FINMIND_FALLBACK_ERROR", "error": str(exc)})

    if out["night_close"] is not None and out["change_pct"] is None and out["change_points"] is not None:
        prev = out["night_close"] - out["change_points"]
        if prev:
            out["change_pct"] = out["change_points"] / prev * 100

    if out["night_close"] is None:
        out["note"] = "夜盤資料未取得；旁白與分鏡 7 會自動跳過，不留空畫面。"
    return out
