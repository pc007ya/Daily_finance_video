from __future__ import annotations

import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (3, 18, 38)
PANEL = (6, 31, 60)
PANEL2 = (8, 42, 76)
GRID = (25, 74, 112)
WHITE = (245, 248, 252)
MUTED = (160, 184, 210)
YELLOW = (255, 205, 40)
GREEN = (55, 220, 120)
RED = (255, 92, 92)
CYAN = (50, 177, 255)


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _fmt(v, digits=2, prefix=""):
    return "N/A" if v is None else f"{prefix}{v:,.{digits}f}"


def _pct(v):
    return "N/A" if v is None else f"{v:+.2f}%"


def _sign_color(v):
    if v is None:
        return MUTED
    return GREEN if v >= 0 else RED


def _base(title: str, date_text: str, timecode: str):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 92), fill=(2, 13, 29))
    d.text((26, 18), timecode, font=_font(28, True), fill=YELLOW)
    d.text((W//2, 42), title, anchor="mm", font=_font(48, True), fill=WHITE)
    d.text((W-28, 24), date_text, anchor="ra", font=_font(22), fill=MUTED)
    return im, d


def _panel(d, xy, radius=16):
    d.rounded_rectangle(xy, radius=radius, fill=PANEL, outline=GRID, width=2)


def _quote_card(d, x, y, w, h, name, q, show_52=True):
    _panel(d, (x, y, x+w, y+h))
    d.text((x+20, y+16), name, font=_font(24, True), fill=MUTED)
    d.text((x+20, y+58), _fmt(q.get("close")), font=_font(40, True), fill=WHITE)
    chg, pct = q.get("change"), q.get("change_pct")
    d.text((x+20, y+116), f"{_fmt(chg)}   {_pct(pct)}", font=_font(25, True), fill=_sign_color(pct))
    if show_52:
        dist = q.get("distance_from_52w_high_pct")
        txt = "距52W High N/A" if dist is None else f"距52W High {dist:.2f}%"
        d.text((x+20, y+156), txt, font=_font(21, True), fill=_sign_color(dist if dist is not None else 0))


def _draw_candles(d, box, candles):
    x1, y1, x2, y2 = box
    if not candles:
        d.text(((x1+x2)//2, (y1+y2)//2), "K線資料待確認", anchor="mm", font=_font(19), fill=MUTED)
        return
    candles = candles[-24:]
    lows = [c["low"] for c in candles]
    highs = [c["high"] for c in candles]
    lo, hi = min(lows), max(highs)
    span = max(hi-lo, 1e-6)
    step = (x2-x1) / max(len(candles), 1)
    body_w = max(3, int(step*0.55))
    def yy(v): return y2 - int((v-lo)/span*(y2-y1))
    for i, c in enumerate(candles):
        cx = int(x1 + (i+0.5)*step)
        col = GREEN if c["close"] >= c["open"] else RED
        d.line((cx, yy(c["high"]), cx, yy(c["low"])), fill=col, width=2)
        top, bot = yy(max(c["open"], c["close"])), yy(min(c["open"], c["close"]))
        if bot <= top:
            bot = top + 2
        d.rectangle((cx-body_w//2, top, cx+body_w//2, bot), fill=col)


def _stock_k_card(d, x, y, w, h, name, q):
    _panel(d, (x, y, x+w, y+h))
    pct = q.get("change_pct")
    d.text((x+18, y+14), name, font=_font(25, True), fill=WHITE)
    d.text((x+w-18, y+16), _pct(pct), anchor="ra", font=_font(24, True), fill=_sign_color(pct))
    d.text((x+18, y+52), f"收盤 {_fmt(q.get('close'))}", font=_font(19), fill=MUTED)
    dist = q.get("distance_from_52w_high_pct")
    dist_txt = "N/A" if dist is None else f"{dist:.2f}%"
    d.text((x+18, y+82), f"距52W High {dist_txt}", font=_font(18, True), fill=_sign_color(dist if dist is not None else 0))
    _draw_candles(d, (x+18, y+122, x+w-18, y+h-22), q.get("candles") or [])


def _crop_finviz(src: Image.Image) -> Image.Image:
    # Browser screenshots include some chrome/padding around the map. Keep the
    # visual center where the treemap lives and remove the least useful bands.
    w, h = src.size
    left = int(w * 0.015)
    right = int(w * 0.985)
    top = int(h * 0.06)
    bottom = int(h * 0.91)
    return src.crop((left, top, right, bottom))


def _audio_duration(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path)
    ]).decode().strip())


def render_daily_video(market: dict, finviz_png: Path, voice_mp3: Path, subtitles_srt: Path, out_dir: Path, date_text: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    idx = market.get("indices", {})
    stocks = market.get("stocks", {})
    scenes = []

    # 00:00-00:10 — sample-style headline dashboard.
    im, d = _base("國際財經與市場晨報", date_text, "00:00 - 00:10")
    names = ["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000", "VIX", "DXY", "GOLD", "WTI"]
    for i, name in enumerate(names):
        x = 28 + i*235
        q = idx.get(name, {})
        _quote_card(d, x, 180, 215, 220, name, q, show_52=True)
    d.text((40, 472), "昨夜市場重點", font=_font(34, True), fill=WHITE)
    points = [
        "美股四大指數與波動率快速定位",
        "AI／半導體與台積電 ADR 為台股盤前核心",
        "同步觀察美元、美債殖利率、黃金與油價",
    ]
    for i, t in enumerate(points):
        d.text((58, 548+i*70), "• "+t, font=_font(29), fill=(210, 232, 250))
    d.text((40, 980), "旁白重點：先判斷市場方向，再看資金集中與事件風險。", font=_font(24, True), fill=YELLOW)
    scenes.append(im)

    # 00:10-00:30 — index table, matching sample layout and colors.
    im, d = _base("昨夜市場總覽", date_text, "00:10 - 00:30")
    _panel(d, (50, 150, 1870, 885))
    cols = [80, 500, 850, 1120, 1400, 1660]
    headers = ["指標", "收盤", "漲跌", "漲跌幅", "52週高點距離", "52W 位階"]
    for x, htxt in zip(cols, headers):
        d.text((x, 182), htxt, font=_font(25, True), fill=MUTED)
    rows = ["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000", "VIX", "DXY", "GOLD", "WTI"]
    for r, name in enumerate(rows):
        y = 245 + r*72
        q = idx.get(name, {})
        d.line((70, y+52, 1840, y+52), fill=(16, 60, 96), width=1)
        d.text((80, y), name, font=_font(24, True), fill=WHITE)
        d.text((500, y), _fmt(q.get("close")), font=_font(24), fill=WHITE)
        d.text((850, y), _fmt(q.get("change")), font=_font(24, True), fill=_sign_color(q.get("change")))
        d.text((1120, y), _pct(q.get("change_pct")), font=_font(24, True), fill=_sign_color(q.get("change_pct")))
        dist = q.get("distance_from_52w_high_pct")
        pos = q.get("week52_position_pct")
        d.text((1400, y), "N/A" if dist is None else f"{dist:.2f}%", font=_font(24, True), fill=_sign_color(dist if dist is not None else 0))
        d.text((1660, y), "N/A" if pos is None else f"{pos:.1f}%", font=_font(24), fill=CYAN)
    d.text((40, 980), "旁白重點：收盤表現＋52週位階一起看，避免只看單日漲跌。", font=_font(24, True), fill=YELLOW)
    scenes.append(im)

    # 00:30-00:50 — cross-market radar.
    im, d = _base("跨市場雷達｜利率・美元・商品・半導體", date_text, "00:30 - 00:50")
    radar = ["US10Y", "USD/TWD", "SOX", "VIX", "DXY", "GOLD", "WTI", "BRENT"]
    for i, name in enumerate(radar):
        x = 60 + (i%4)*455
        y = 180 + (i//4)*340
        _quote_card(d, x, y, 420, 260, name, idx.get(name, {}), show_52=True)
    d.text((40, 980), "旁白重點：科技股強弱要搭配 SOX、殖利率與美元共同判讀。", font=_font(24, True), fill=YELLOW)
    scenes.append(im)

    # 00:50-01:20 — actual Finviz screenshot, cropped to usable treemap content.
    im, d = _base("NASDAQ-100 熱力圖｜Finviz", date_text, "00:50 - 01:20")
    src = _crop_finviz(Image.open(finviz_png).convert("RGB"))
    box = (45, 135, 1475, 920)
    bw, bh = box[2]-box[0], box[3]-box[1]
    ratio = min(bw/src.width, bh/src.height)
    rs = src.resize((int(src.width*ratio), int(src.height*ratio)))
    im.paste(rs, (box[0]+(bw-rs.width)//2, box[1]+(bh-rs.height)//2))
    _panel(d, (1510, 150, 1870, 890))
    d.text((1690, 185), "熱力圖閱讀", anchor="mm", font=_font(28, True), fill=WHITE)
    tips = ["綠：上漲", "紅：下跌", "面積：市值", "先看科技權值", "再看產業擴散"]
    for i, t in enumerate(tips):
        d.text((1540, 270+i*90), t, font=_font(25, True), fill=GREEN if i==0 else RED if i==1 else MUTED)
    d.text((40, 980), "旁白重點：此段只解讀 Finviz，避免 60–80 秒旁白與投影片錯位。", font=_font(24, True), fill=YELLOW)
    scenes.append(im)

    # 01:20-01:45 — focused names with actual OHLC mini K-lines.
    im, d = _base("焦點個股走勢｜昨夜表現＋K線", date_text, "01:20 - 01:45")
    focus = ["Apple", "NVIDIA", "TSM ADR", "AMD", "Microsoft"]
    card_w = 355
    for i, name in enumerate(focus):
        _stock_k_card(d, 35+i*375, 170, card_w, 710, name, stocks.get(name, {}))
    d.text((40, 980), "旁白重點：個股同時看收盤漲跌、距 52W High 與近一月 K 線趨勢。", font=_font(24, True), fill=YELLOW)
    scenes.append(im)

    # 01:45-02:00 — new page: weekly macro calendar + top-100 earnings slot.
    im, d = _base("本週美股重要行事曆｜總經數據＋大型企業財報", date_text, "01:45 - 02:00")
    _panel(d, (45, 150, 1120, 900))
    _panel(d, (1150, 150, 1875, 900))
    d.text((75, 180), "本週重要總經事件", font=_font(30, True), fill=WHITE)
    calendar = market.get("weekly_calendar") or []
    if calendar:
        for i, item in enumerate(calendar[:8]):
            y = 245+i*75
            d.text((80, y), str(item.get("date", "")), font=_font(21, True), fill=CYAN)
            d.text((280, y), str(item.get("event", "")), font=_font(22, True), fill=WHITE)
            d.text((850, y), str(item.get("forecast", "")), font=_font(21), fill=MUTED)
    else:
        fallback = ["CPI 消費者物價指數", "PPI 生產者物價指數", "Fed 利率決策 / 點陣圖", "非農就業 NFP", "失業率", "零售銷售", "PCE / 核心 PCE"]
        for i, t in enumerate(fallback):
            d.text((80, 250+i*82), "• "+t, font=_font(24, True), fill=WHITE)
        d.text((80, 835), "Live calendar fetcher 尚待串接", font=_font(20), fill=YELLOW)
    d.text((1180, 180), "市值前100大企業財報", font=_font(30, True), fill=WHITE)
    earnings = market.get("earnings_calendar") or []
    if earnings:
        for i, item in enumerate(earnings[:10]):
            y = 245+i*60
            d.text((1185, y), str(item.get("date", "")), font=_font(19), fill=CYAN)
            d.text((1370, y), str(item.get("company", "")), font=_font(21, True), fill=WHITE)
            d.text((1780, y), str(item.get("ticker", "")), anchor="ra", font=_font(20, True), fill=MUTED)
    else:
        d.text((1185, 255), "自動篩選：市值前100大", font=_font(23, True), fill=WHITE)
        d.text((1185, 310), "顯示：日期／公司／代號／盤前盤後", font=_font(21), fill=MUTED)
        d.text((1185, 365), "Live earnings fetcher 尚待串接", font=_font(20), fill=YELLOW)
    d.text((40, 980), "旁白重點：CPI、PPI、Fed、非農、失業率，以及大型權值股財報。", font=_font(24, True), fill=YELLOW)
    scenes.append(im)

    duration = _audio_duration(voice_mp3)
    weights = [10, 20, 20, 30, 25, 15]
    total_w = sum(weights)
    clips = []
    for i, (im, weight) in enumerate(zip(scenes, weights), 1):
        png = out_dir / f"scene{i:02}.png"
        mp4 = out_dir / f"scene{i:02}.mp4"
        im.save(png)
        sec = max(2.0, duration * weight / total_w)
        zoom = "min(zoom+0.00030,1.035)" if i == 4 else "min(zoom+0.00012,1.018)"
        vf = f"scale=2048:1152,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,format=yuv420p"
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(png), "-vf", vf,
            "-t", f"{sec:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", str(mp4)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clips.append(mp4)

    concat = out_dir / "scenes.txt"
    concat.write_text("\n".join(f"file '{p.name}'" for p in clips), encoding="utf-8")
    visual = out_dir / "visual.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat.name, "-c", "copy", visual.name
    ], cwd=out_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if not subtitles_srt.exists() or subtitles_srt.stat().st_size < 16:
        raise RuntimeError(f"Subtitle file missing or empty: {subtitles_srt}")

    final = out_dir / f"daily_finance_{date_text}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", str(visual.resolve()),
        "-i", str(voice_mp3.resolve()),
        "-i", str(subtitles_srt.resolve()),
        "-map", "0:v:0", "-map", "1:a:0", "-map", "2:s:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text",
        "-metadata:s:s:0", "language=zho", "-disposition:s:0", "default",
        "-shortest", "-movflags", "+faststart", str(final.resolve())
    ], check=True)
    return final
