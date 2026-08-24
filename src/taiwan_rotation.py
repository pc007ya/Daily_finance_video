from __future__ import annotations

"""Taiwan sector confirmation layer.

Combines US RRG mapping with Taiwan-local evidence when available.
Missing institutional/margin inputs are neutral, never fabricated.
"""
from pathlib import Path
import json
import yfinance as yf

BASKETS={
 "AI/半導體":["2330.TW","2454.TW","3443.TW"],
 "AI Server/ODM":["2317.TW","2382.TW","3231.TW"],
 "PCB/CCL":["3037.TW","2383.TW","2368.TW"],
 "散熱":["3017.TW","3324.TW","3653.TW"],
 "網通":["2345.TW","6285.TW","3596.TW"],
 "記憶體":["2408.TW","2344.TW","8299.TWO"],
 "重電":["1513.TW","1519.TW","1503.TW"],
 "航運":["2603.TW","2609.TW","2615.TW"],
 "金融":["2881.TW","2882.TW","2891.TW"],
 "生技":["6446.TW","6472.TW","1795.TW"],
}

def _ret(s,n): return None if len(s)<=n else float((s.iloc[-1]/s.iloc[-1-n]-1)*100)
def _score(rel5,rel20):
    s=0
    if rel5 is not None:s += 2 if rel5>1 else 1 if rel5>0 else -2 if rel5<-1 else -1
    if rel20 is not None:s += 2 if rel20>2 else 1 if rel20>0 else -2 if rel20<-2 else -1
    return s

def build_taiwan_rotation(out_dir:Path, us_rotation:dict)->dict:
    tickers=["^TWII"]+[x for v in BASKETS.values() for x in v]
    raw=yf.download(tickers,period="3mo",interval="1d",auto_adjust=True,progress=False)
    close=raw["Close"].dropna(how="all").ffill(); rows=[]
    if len(close)<25:return {"status":"INSUFFICIENT_DATA","groups":[]}
    bench=close["^TWII"]
    for name,members in BASKETS.items():
        usable=[m for m in members if m in close and close[m].notna().sum()>20]
        if not usable:continue
        basket=close[usable].pct_change(fill_method=None).mean(axis=1).fillna(0).add(1).cumprod()
        r5,r20=_ret(basket,5),_ret(basket,20); b5,b20=_ret(bench,5),_ret(bench,20)
        rel5=None if r5 is None or b5 is None else r5-b5; rel20=None if r20 is None or b20 is None else r20-b20
        local=_score(rel5,rel20)
        rows.append({"group":name,"members":usable,"relative_5d_pct":None if rel5 is None else round(rel5,2),"relative_20d_pct":None if rel20 is None else round(rel20,2),"local_score":local,"institutional_score":None,"margin_score":None,"confirmed_score":local,"data_quality":"PRICE_CONFIRMED; FLOW_PENDING"})
    rows.sort(key=lambda r:r["confirmed_score"],reverse=True)
    result={"status":"OK","trade_date":str(close.index[-1].date()),"benchmark":"^TWII","method":"equal_weight basket vs TAIEX; 5D+20D price confirmation","groups":rows,"top3":[r["group"] for r in rows[:3]],"risk3":[r["group"] for r in rows[-3:]]}
    (out_dir/"taiwan_rotation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
