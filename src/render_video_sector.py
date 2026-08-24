from __future__ import annotations
from pathlib import Path
from PIL import Image
from . import render_video as legacy


def _scene5_rotation(rep, date_text, assets):
    im,d=legacy._base("S&P 500 Sector Rotation｜RRG-style vs SPY",date_text,"輪動"); rot=rep.get("sector_rotation") or {}; path=rot.get("path")
    if path and Path(path).exists():
        src=Image.open(path).convert("RGB"); box=(45,135,1435,920); bw,bh=box[2]-box[0],box[3]-box[1]; ratio=min(bw/src.width,bh/src.height); rs=src.resize((int(src.width*ratio),int(src.height*ratio))); ox,oy=box[0]+(bw-rs.width)//2,box[1]+(bh-rs.height)//2; im.paste(rs,(ox,oy)); d.rectangle((ox-1,oy-1,ox+rs.width,oy+rs.height),outline=legacy.RULE,width=2)
    legacy._panel(d,(1470,150,1875,900)); d.text((1672,182),"RRG 輪動訊號",anchor="mm",font=legacy._font(28,True),fill=legacy.INK); sig=rot.get("signals") or {}; y=228
    for label,key,col in [("LEADING","leading",legacy.UP),("IMPROVING","improving",legacy.INFO),("WEAKENING","weakening",legacy.ACCENT),("LAGGING","lagging",legacy.MUTED)]:
        names=sig.get(key) or []; d.text((1505,y),label,font=legacy._font(19,True),fill=col); d.text((1505,y+30),"、".join(names[:4]) if names else "—",font=legacy._font(19,True),fill=legacy.INK); y+=78
    d.text((1505,836),f"交易日 {rot.get('trade_date','N/A')}",font=legacy._font(15),fill=legacy.MUTED); d.text((1505,861),"中心值 100｜尾跡 5 日",font=legacy._font(15),fill=legacy.MUTED); d.text((1505,884),"開放近似算法，非 JdK 專有公式",font=legacy._font(13),fill=legacy.MUTED); return im


def _scene6_taiwan(rep,date_text,assets):
    im,d=legacy._base("台股族群輪動｜美股映射＋盤前焦點",date_text,"台股輪動"); rot=rep.get("sector_rotation") or {}; rows=rot.get("taiwan_focus") or []
    # Left: ranked Taiwan implications derived from US RRG.
    legacy._panel(d,(45,145,1180,915)); d.text((80,180),"美股輪動 → 台股族群映射",font=legacy._font(30,True),fill=legacy.INK)
    d.text((80,230),"美股板塊",font=legacy._font(20,True),fill=legacy.MUTED); d.text((350,230),"狀態",font=legacy._font(20,True),fill=legacy.MUTED); d.text((590,230),"台股對應族群",font=legacy._font(20,True),fill=legacy.MUTED)
    for i,r in enumerate(rows[:7]):
        y=280+i*82; score=r.get("score",0); col=legacy.UP if score>0 else legacy.DOWN if score<0 else legacy.MUTED
        d.text((80,y),str(r.get("sector","")),font=legacy._font(22,True),fill=legacy.INK); d.text((350,y),str(r.get("stance","")),font=legacy._font(21,True),fill=col); d.text((590,y)," / ".join((r.get("groups") or [])[:3]),font=legacy._font(20,True),fill=legacy.SOFT); d.line((70,y+55,1150,y+55),fill=legacy.RULE,width=1)
    # Right: Top 3 actionable focus.
    legacy._panel(d,(1215,145,1875,915)); d.text((1545,180),"今日台股 Top 3",anchor="mm",font=legacy._font(30,True),fill=legacy.INK)
    positives=[r for r in rows if r.get("score",0)>0]; negatives=[r for r in rows if r.get("score",0)<0]
    picks=[]
    if positives: picks.append(("最強主線",positives[0],legacy.UP))
    if len(positives)>1: picks.append(("轉強觀察",positives[1],legacy.INFO))
    if negatives: picks.append(("風險族群",negatives[-1],legacy.DOWN))
    for i,(label,r,col) in enumerate(picks[:3]):
        y=270+i*190; d.text((1260,y),label,font=legacy._font(22,True),fill=col); d.text((1260,y+42),str(r.get("sector","")),font=legacy._font(31,True),fill=legacy.INK); d.text((1260,y+88),str(r.get("stance","")),font=legacy._font(20,True),fill=col); d.text((1260,y+126)," / ".join((r.get("groups") or [])[:2]),font=legacy._font(18),fill=legacy.SOFT)
    d.text((1260,850),"第一層：美股 RRG 映射",font=legacy._font(16),fill=legacy.MUTED); d.text((1260,878),"後續可疊加台股5D/20D、法人與融資驗證",font=legacy._font(15),fill=legacy.MUTED); return im

legacy.BUILDERS.clear(); legacy.BUILDERS.update({1:legacy._scene1,2:legacy._scene2,3:legacy._scene3,4:legacy._scene4,5:_scene5_rotation,6:_scene6_taiwan,7:legacy._scene5,8:legacy._scene6,9:legacy._scene7,10:legacy._scene8})

def render_daily_video(report:dict,finviz_png:Path,voice_mp3:Path,subtitles_srt:Path,timeline:list[dict],out_dir:Path,date_text:str)->Path:
    return legacy.render_daily_video(report,finviz_png,voice_mp3,subtitles_srt,timeline,out_dir,date_text)
