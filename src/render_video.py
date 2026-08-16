from __future__ import annotations

import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (14, 17, 23)
CARD = (27, 31, 40)
MUTED = (185, 190, 200)


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


def _base(title: str, date_text: str):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((80, 52), "國際財經晨報", font=_font(30, True), fill=MUTED)
    d.text((80, 105), title, font=_font(58, True), fill="white")
    d.text((80, 180), date_text, font=_font(26), fill=MUTED)
    d.line((80, 230, 1840, 230), fill=(65, 70, 80), width=2)
    return im, d


def _quote_card(d, x, y, w, h, name, q):
    d.rounded_rectangle((x, y, x+w, y+h), 22, fill=CARD, outline=(70, 75, 86), width=2)
    d.text((x+26, y+20), name, font=_font(28, True), fill=MUTED)
    d.text((x+26, y+70), _fmt(q.get("close")), font=_font(46, True), fill="white")
    d.text((x+26, y+140), f"{_fmt(q.get('change'))}   {_pct(q.get('change_pct'))}", font=_font(28, True), fill="white")


def _stock_52w_card(d, x, y, w, h, name, q):
    _quote_card(d, x, y, w, h, name, q)
    lo, hi = q.get("week52_low"), q.get("week52_high")
    pos, dist = q.get("week52_position_pct"), q.get("distance_from_52w_high_pct")
    gy = y + 230
    x1, x2 = x+35, x+w-35
    d.line((x1, gy, x2, gy), fill=(105,110,120), width=8)
    if pos is not None:
        px = x1 + (x2-x1)*max(0, min(1, pos/100))
        d.ellipse((px-12, gy-12, px+12, gy+12), fill="white")
    d.text((x1, y+255), f"52W Low {_fmt(lo)}", font=_font(20), fill=MUTED)
    d.text((x2, y+255), f"High {_fmt(hi)}", anchor="ra", font=_font(20), fill=MUTED)
    pos_txt = "N/A" if pos is None else f"{pos:.1f}%"
    dist_txt = "N/A" if dist is None else f"{dist:.1f}%"
    d.text((x+26, y+305), f"位階 {pos_txt}  ｜  距 52W High {dist_txt}", font=_font(24, True), fill="white")


def _audio_duration(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path)
    ]).decode().strip())


def _ffmpeg_escape_filter_path(path: Path) -> str:
    # FFmpeg filter syntax needs ':' and backslashes escaped even when the
    # process working directory changes. Use an absolute POSIX path.
    s = path.resolve().as_posix()
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def render_daily_video(market: dict, finviz_png: Path, voice_mp3: Path, subtitles_srt: Path, out_dir: Path, date_text: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    scenes = []

    im, d = _base("今早市場總覽", date_text)
    d.text((105, 350), "美股收盤 × 跨市場 × AI 半導體", font=_font(62, True), fill="white")
    d.text((105, 475), "價格、點數、漲跌幅與 52W 位階一次看", font=_font(44, True), fill="white")
    d.text((105, 760), "Finviz：NASDAQ-100 1-Day Performance", font=_font(34), fill=MUTED)
    scenes.append(im)

    im, d = _base("美股四大指數｜收盤價・點數・漲跌幅", date_text)
    indices = market.get("indices", {})
    keys = ["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000"]
    for i, name in enumerate(keys):
        x = 85 + (i % 2) * 890
        y = 300 + (i // 2) * 300
        _quote_card(d, x, y, 840, 245, name, indices.get(name, {}))
    scenes.append(im)

    im, d = _base("FINVIZ NASDAQ-100｜1 DAY PERFORMANCE", date_text)
    src = Image.open(finviz_png).convert("RGB")
    box = (70, 270, 1850, 945)
    bw, bh = box[2]-box[0], box[3]-box[1]
    ratio = min(bw/src.width, bh/src.height)
    rs = src.resize((int(src.width*ratio), int(src.height*ratio)))
    px = box[0] + (bw-rs.width)//2
    py = box[1] + (bh-rs.height)//2
    im.paste(rs, (px, py))
    d.text((80, 980), "來源：Finviz NASDAQ-100 Heatmap｜方塊面積代表市值", font=_font(25), fill=MUTED)
    scenes.append(im)

    im, d = _base("跨市場雷達", date_text)
    macro = ["VIX", "DXY", "US10Y", "GOLD", "WTI", "BRENT", "USD/TWD", "SOX"]
    for i, name in enumerate(macro):
        x = 70 + (i % 4) * 455
        y = 295 + (i // 4) * 310
        _quote_card(d, x, y, 420, 245, name, indices.get(name, {}))
    scenes.append(im)

    im, d = _base("AI／半導體｜收盤＋52週相對位階", date_text)
    stocks = market.get("stocks", {})
    names = ["TSM ADR", "NVIDIA", "AMD", "Apple"]
    for i, name in enumerate(names):
        x = 70 + (i % 2) * 900
        y = 280 + (i // 2) * 360
        _stock_52w_card(d, x, y, 850, 330, name, stocks.get(name, {}))
    d.text((960, 1010), "日漲跌看今天強弱；52W 位階看現在站在哪裡。", anchor="mm", font=_font(28), fill=MUTED)
    scenes.append(im)

    im, d = _base("今日觀察重點", date_text)
    sox = indices.get("SOX", {})
    vix = indices.get("VIX", {})
    brent = indices.get("BRENT", {})
    d.text((110, 340), f"SOX：{_fmt(sox.get('close'))}  {_pct(sox.get('change_pct'))}", font=_font(48, True), fill="white")
    d.text((110, 470), f"VIX：{_fmt(vix.get('close'))}  {_pct(vix.get('change_pct'))}", font=_font(48, True), fill="white")
    d.text((110, 600), f"Brent：{_fmt(brent.get('close'), prefix='$')}  {_pct(brent.get('change_pct'))}", font=_font(48, True), fill="white")
    d.text((110, 775), "盤前優先看：台積電 ADR、AI／半導體、美元與油價", font=_font(38, True), fill="white")
    scenes.append(im)

    duration = _audio_duration(voice_mp3)
    weights = [0.10, 0.18, 0.20, 0.16, 0.24, 0.12]
    clips = []
    for i, (im, weight) in enumerate(zip(scenes, weights), 1):
        png = out_dir / f"scene{i:02}.png"
        mp4 = out_dir / f"scene{i:02}.mp4"
        im.save(png)
        sec = max(2.0, duration * weight)
        zoom = "min(zoom+0.00045,1.055)" if i == 3 else "min(zoom+0.00020,1.025)"
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

    final = out_dir / f"daily_finance_{date_text}.mp4"
    sub_abs = _ffmpeg_escape_filter_path(subtitles_srt)
    vf = (
        f"subtitles='{sub_abs}':force_style='FontName=Noto Sans CJK TC,FontSize=22,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=26'"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(visual.resolve()), "-i", str(voice_mp3.resolve()),
        "-vf", vf, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(final.resolve())
    ], check=True)
    return final
