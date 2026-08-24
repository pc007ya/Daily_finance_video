from __future__ import annotations
SCENE_TITLES={1:"今日三大重點",2:"美股四大指數",3:"市場雷達",4:"Finviz NASDAQ-100 熱力圖",5:"S&P 500 Sector Rotation",6:"台股族群輪動",7:"AI / 半導體",8:"今日重大新聞",9:"台指期夜盤 / OI",10:"今日與本週焦點"}
def _fmt(v,digits=2): return None if v is None else f"{v:,.{digits}f}"
def _quote(name,q,unit="點"):
    close,chg,pct=q.get("close"),q.get("change"),q.get("change_pct")
    if close is None or chg is None or pct is None:return None
    return f"{name}收在{_fmt(close)}{unit}，{'上漲' if chg>=0 else '下跌'}{_fmt(abs(chg))}{unit}，幅度{_fmt(abs(pct))}%。"
def _yield_sentence(q):
    close=q.get("close"); bps=q.get("change_bps")
    if close is None:return None
    if bps is None and q.get("change") is not None:bps=q["change"]*100
    return f"美國十年期公債殖利率約在{_fmt(close)}%"+("。" if bps is None else f"，單日{'上升' if bps>=0 else '下降'}{abs(bps):.0f}個基點。")
def _sector_sentence(rot):
    if rot.get("status")!="OK":return []
    s=rot.get("signals",{}); out=["接著看標普五百RRG風格板塊輪動，以SPY為基準觀察相對強度與動能。"]
    if s.get("leading"):out.append("領先象限以"+"、".join(s["leading"][:3])+"為主。")
    if s.get("improving"):out.append("改善象限包括"+"、".join(s["improving"][:3])+"。")
    if s.get("weakening"):out.append("轉弱象限包括"+"、".join(s["weakening"][:3])+"，短線追價要謹慎。")
    return out[:3]
def _taiwan_sentence(rot):
    rows=rot.get("taiwan_focus") or []; pos=[r for r in rows if r.get("score",0)>0]; neg=[r for r in rows if r.get("score",0)<0]; out=["把美股輪動映射到台股，觀察今天盤前的族群優先順序。"]
    if pos:
        r=pos[0]; out.append(f"目前偏多主線對應{r.get('sector')}，台股留意"+"、".join((r.get("groups") or [])[:3])+"。")
    if len(pos)>1:
        r=pos[1]; out.append(f"第二個轉強方向是{r.get('sector')}，對應"+"、".join((r.get("groups") or [])[:2])+"。")
    if neg:
        r=neg[-1]; out.append(f"相對風險較高的是{r.get('sector')}，相關族群短線避免只看美股反彈追價。")
    return out[:4]
def build_segments(report):
    idx=report.get("indices",{}); stocks=report.get("stocks",{}); seg=[]
    def add(scene,text):
        if text:seg.append({"scene":scene,"text":text})
    add(1,"兩分鐘掌握最新國際財經與台股盤前重點。"); board={s.get("scene"):s for s in report.get("video_storyboard",[])}
    for p in (board.get(1,{}).get("points") or [])[:3]:add(1,str(p).rstrip("。")+"。")
    for n in ["S&P 500","NASDAQ","DOW","RUSSELL 2000"]:add(2,_quote(n,idx.get(n,{})))
    add(3,_quote("VIX恐慌指數",idx.get("VIX",{}),""));add(3,_quote("美元指數",idx.get("DXY",{}),""));add(3,_yield_sentence(idx.get("US10Y",{})));add(3,_quote("黃金",idx.get("GOLD",{}),"美元"));add(3,_quote("西德州原油",idx.get("WTI",{}),"美元"));add(3,_quote("美元兌新台幣",idx.get("USD/TWD",{}),""))
    add(4,"接著看Finviz納斯達克一百熱力圖，先看科技權值再看產業擴散。")
    rot=report.get("sector_rotation") or {}
    for x in _sector_sentence(rot):add(5,x)
    for x in _taiwan_sentence(rot):add(6,x)
    add(7,_quote("費城半導體指數",idx.get("SOX",{})));add(7,_quote("台積電ADR",stocks.get("TSM ADR",{}),"美元"))
    for n,spoken in [("NVIDIA","NVIDIA"),("AMD","AMD"),("Apple","蘋果"),("Microsoft","微軟")]:add(7,_quote(spoken,stocks.get(n,{}),"美元"))
    points=report.get("narration_points") or []; news=[p for p in points if any(k in p for k in ("風險","新聞","通膨","利率","油"))][:3]
    if not news:news=[str(n.get("headline","")) for n in report.get("breaking_news",[])[:3]]
    for x in news:add(8,str(x).rstrip("。")+"。")
    tx=report.get("taiwan_futures") or {}
    if tx.get("night_close") is not None:
        pts=tx.get("change_points"); s=f"台指期夜盤收在{_fmt(tx['night_close'],0)}點"; s+=(f"，{'上漲' if (pts or 0)>=0 else '下跌'}{abs(pts):,.0f}點" if pts is not None else ""); add(9,s+"。")
    earn=report.get("earnings_calendar",[])[:3]; names="、".join(str(e.get("company","")) for e in earn if e.get("company"))
    if names:add(10,f"本週財報：{names}。")
    add(10,"以上是今天的國際財經晨報，投資有風險，資訊僅供市場觀察參考。");return seg
def build_narration(report):return "".join(s["text"] for s in build_segments(report))
