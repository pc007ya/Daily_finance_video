from __future__ import annotations

"""畫面長度由 narration_timeline 決定；Finviz 自動裁到熱力圖邊界。

與舊版的差異
- 移除 weights=[10,20,20,30,25,15] 與 120 秒假設：每個分鏡的秒數 = 該段旁白的實測長度。
- 分鏡由 timeline 決定：旁白沒有第 7 段，就不會產生台指期畫面（不再空轉）。
- 新增分鏡 6（重大新聞）與分鏡 7（台指期夜盤 / OI）。
- Finviz 改用 _auto_crop：偵測彩色（treemap）像素的邊界，把導覽列、頁尾、留白整片裁掉，
  不再用 0.015/0.06/0.91 這種寫死的比例。
- 字幕改燒進畫面（subtitles 濾鏡，底部固定），同時保留 mov_text 軟字幕軌。
"""

import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080

# 白底橘色盤，與審視面板同一組值。名字照語意取——白底之下 BG/WHITE 那套舊名會反過來害人。
PAPER = (250, 248, 244)      # 暖白紙面
CARD = (255, 255, 255)       # 卡片
RULE = (229, 224, 216)       # 框線／分隔線
INK = (31, 29, 26)           # 主要文字
SOFT = (61, 57, 52)          # 次要內文
MUTED = (122, 115, 108)      # 標籤、註記
ACCENT = (217, 119, 87)      # Claude 橘：badge 與重點
HEADER = (244, 240, 232)     # 標題列底
UP = (47, 125, 79)           # 上漲（白底上讀得清楚的深綠，不用螢光綠）
DOWN = (180, 68, 47)         # 下跌
INFO = (91, 116, 140)        # 52W 位階、日期等次要資訊

SUB_STYLE = (
    "FontName=Noto Sans CJK TC,FontSize=21,Bold=1,Alignment=2,MarginV=40,"
    "PrimaryColour=&H001A1D1F&,OutlineColour=&H00F4F8FA&,BorderStyle=3,Outline=7,Shadow=0"
)


def _font(size: int, bold: bool = False):
    for p in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _fmt(v, digits=2, prefix=""):
    return "N/A" if v is None else f"{prefix}{v:,.{digits}f}"


def _pct(v):
    return "N/A" if v is None else f"{v:+.2f}%"


def _sign(v):
    return MUTED if v is None else (UP if v >= 0 else DOWN)


def _base(title: str, date_text: str, badge: str):
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 92), fill=HEADER)
    d.rectangle((0, 89, W, 92), fill=ACCENT)
    d.text((26, 18), badge, font=_font(28, True), fill=ACCENT)
    d.text((W // 2, 42), title, anchor="mm", font=_font(48, True), fill=INK)
    d.text((W - 28, 24), date_text, anchor="ra", font=_font(22), fill=MUTED)
    return im, d


def _panel(d, xy):
    d.rectangle(xy, fill=CARD, outline=RULE, width=2)


def _quote_card(d, x, y, w, h, name, q):
    _panel(d, (x, y, x + w, y + h))
    d.text((x + 20, y + 16), name, font=_font(24, True), fill=MUTED)
    d.text((x + 20, y + 58), _fmt(q.get("close")), font=_font(40, True), fill=INK)
    d.text((x + 20, y + 116), f"{_fmt(q.get('change'))}   {_pct(q.get('change_pct'))}",
           font=_font(25, True), fill=_sign(q.get("change_pct")))
    dist = q.get("distance_from_52w_high_pct")
    d.text((x + 20, y + 156), "距52W High N/A" if dist is None else f"距52W High {dist:.2f}%",
           font=_font(21, True), fill=_sign(dist))


def _draw_candles(d, box, candles):
    x1, y1, x2, y2 = box
    if not candles:
        d.text(((x1 + x2) // 2, (y1 + y2) // 2), "K線資料待確認", anchor="mm", font=_font(19), fill=MUTED)
        return
    candles = candles[-24:]
    lo = min(c["low"] for c in candles)
    hi = max(c["high"] for c in candles)
    span = max(hi - lo, 1e-6)
    step = (x2 - x1) / max(len(candles), 1)
    body = max(3, int(step * 0.55))
    yy = lambda v: y2 - int((v - lo) / span * (y2 - y1))
    for i, c in enumerate(candles):
        cx = int(x1 + (i + 0.5) * step)
        col = UP if c["close"] >= c["open"] else DOWN
        d.line((cx, yy(c["high"]), cx, yy(c["low"])), fill=col, width=2)
        top, bot = yy(max(c["open"], c["close"])), yy(min(c["open"], c["close"]))
        if bot <= top:
            bot = top + 2
        d.rectangle((cx - body // 2, top, cx + body // 2, bot), fill=col)


def _stock_card(d, x, y, w, h, name, q):
    _panel(d, (x, y, x + w, y + h))
    d.text((x + 18, y + 14), name, font=_font(25, True), fill=INK)
    d.text((x + w - 18, y + 16), _pct(q.get("change_pct")), anchor="ra", font=_font(24, True),
           fill=_sign(q.get("change_pct")))
    d.text((x + 18, y + 52), f"收盤 {_fmt(q.get('close'))}", font=_font(19), fill=MUTED)
    dist = q.get("distance_from_52w_high_pct")
    d.text((x + 18, y + 82), "距52W High N/A" if dist is None else f"距52W High {dist:.2f}%",
           font=_font(18, True), fill=_sign(dist))
    _draw_candles(d, (x + 18, y + 122, x + w - 18, y + h - 22), q.get("candles") or [])


def _auto_crop(src: Image.Image, pad: int = 6) -> Image.Image:
    """裁到 treemap 的實際邊界：只保留有彩度（綠／紅方塊）的區域。

    比寫死比例穩：Finviz 改版、視窗高度不同、出現 cookie bar 都不會裁歪。
    """
    small = src.convert("RGB").resize((src.width // 4, src.height // 4))
    px = small.load()
    cols, rows = [], []
    for y in range(small.height):
        hits = 0
        for x in range(small.width):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > 28 and max(r, g, b) > 60:
                hits += 1
        if hits > small.width * 0.05:
            rows.append(y)
    for x in range(small.width):
        hits = 0
        for y in range(small.height):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > 28 and max(r, g, b) > 60:
                hits += 1
        if hits > small.height * 0.05:
            cols.append(x)
    if not rows or not cols:
        return src
    box = (max(0, cols[0] * 4 - pad), max(0, rows[0] * 4 - pad),
           min(src.width, (cols[-1] + 1) * 4 + pad), min(src.height, (rows[-1] + 1) * 4 + pad))
    if box[2] - box[0] < src.width * 0.3 or box[3] - box[1] < src.height * 0.3:
        return src
    return src.crop(box)


# ——— 各分鏡畫面 ———

def _scene1(rep, date_text, assets):
    im, d = _base("國際財經與市場晨報", date_text, "重點")
    idx = rep.get("indices", {})
    for i, name in enumerate(["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000", "VIX", "DXY", "GOLD", "WTI"]):
        _quote_card(d, 28 + i * 235, 180, 215, 220, name, idx.get(name, {}))
    board = {s.get("scene"): s for s in rep.get("video_storyboard", [])}
    d.text((40, 472), "今日三大重點", font=_font(34, True), fill=INK)
    for i, t in enumerate((board.get(1, {}).get("points") or [])[:3]):
        d.text((58, 548 + i * 70), "• " + str(t), font=_font(29), fill=SOFT)
    return im


def _index_table(rep, date_text, names, title):
    im, d = _base(title, date_text, "指數")
    _panel(d, (50, 150, 1870, 885))
    for x, h in zip([80, 500, 850, 1120, 1400, 1660],
                    ["指標", "收盤", "漲跌", "漲跌幅", "52週高點距離", "52W 位階"]):
        d.text((x, 182), h, font=_font(25, True), fill=MUTED)
    idx = rep.get("indices", {})
    for r, name in enumerate(names):
        q = idx.get(name, {})
        y = 245 + r * 72
        d.line((70, y + 52, 1840, y + 52), fill=RULE, width=1)
        d.text((80, y), name, font=_font(24, True), fill=INK)
        d.text((500, y), _fmt(q.get("close")), font=_font(24), fill=INK)
        d.text((850, y), _fmt(q.get("change")), font=_font(24, True), fill=_sign(q.get("change")))
        d.text((1120, y), _pct(q.get("change_pct")), font=_font(24, True), fill=_sign(q.get("change_pct")))
        dist, pos = q.get("distance_from_52w_high_pct"), q.get("week52_position_pct")
        d.text((1400, y), "N/A" if dist is None else f"{dist:.2f}%", font=_font(24, True), fill=_sign(dist))
        d.text((1660, y), "N/A" if pos is None else f"{pos:.1f}%", font=_font(24), fill=INFO)
    return im


def _scene2(rep, date_text, assets):
    return _index_table(rep, date_text, ["S&P 500", "NASDAQ", "DOW", "RUSSELL 2000"], "美股四大指數")


def _scene3(rep, date_text, assets):
    im, d = _base("跨市場雷達｜利率・美元・商品・匯率", date_text, "雷達")
    idx = rep.get("indices", {})
    for i, name in enumerate(["VIX", "DXY", "US10Y", "USD/TWD", "GOLD", "WTI", "BRENT", "SOX"]):
        _quote_card(d, 60 + (i % 4) * 455, 180 + (i // 4) * 340, 420, 260, name, idx.get(name, {}))
    return im


def _scene4(rep, date_text, assets):
    im, d = _base("NASDAQ-100 熱力圖｜Finviz", date_text, "熱力圖")
    src = _auto_crop(Image.open(assets["finviz"]).convert("RGB"))
    box = (45, 135, 1475, 920)
    bw, bh = box[2] - box[0], box[3] - box[1]
    ratio = min(bw / src.width, bh / src.height)
    rs = src.resize((int(src.width * ratio), int(src.height * ratio)))
    ox, oy = box[0] + (bw - rs.width) // 2, box[1] + (bh - rs.height) // 2
    im.paste(rs, (ox, oy))
    d.rectangle((ox - 1, oy - 1, ox + rs.width, oy + rs.height), outline=RULE, width=2)
    _panel(d, (1510, 150, 1870, 890))
    d.text((1690, 185), "熱力圖閱讀", anchor="mm", font=_font(28, True), fill=INK)
    for i, t in enumerate(["綠：上漲", "紅：下跌", "面積：市值", "先看科技權值", "再看產業擴散"]):
        d.text((1540, 270 + i * 90), t, font=_font(25, True),
               fill=UP if i == 0 else DOWN if i == 1 else MUTED)
    return im


def _scene5(rep, date_text, assets):
    im, d = _base("AI / 半導體｜昨夜表現＋K線", date_text, "個股")
    stocks = rep.get("stocks", {})
    for i, name in enumerate(["TSM ADR", "NVIDIA", "AMD", "Apple", "Microsoft"]):
        _stock_card(d, 35 + i * 375, 170, 355, 710, name, stocks.get(name, {}))
    return im


def _scene6(rep, date_text, assets):
    im, d = _base("今日重大新聞", date_text, "新聞")
    news = rep.get("breaking_news", [])[:3]
    for i, n in enumerate(news):
        y = 165 + i * 250
        _panel(d, (50, y, 1870, y + 220))
        d.text((75, y + 20), str(n.get("importance", "")), font=_font(21, True), fill=ACCENT)
        d.text((200, y + 18), str(n.get("headline", ""))[:58], font=_font(28, True), fill=INK)
        d.text((75, y + 76), str(n.get("summary", ""))[:74], font=_font(22), fill=SOFT)
        d.text((75, y + 130), "市場影響：" + str(n.get("market_impact", ""))[:66], font=_font(21), fill=MUTED)
        d.text((75, y + 174), "台股影響：" + str(n.get("taiwan_impact", ""))[:66], font=_font(21, True), fill=INFO)
    return im


def _scene7(rep, date_text, assets):
    im, d = _base("台指期夜盤 / 未平倉", date_text, "台指期")
    tx = rep.get("taiwan_futures", {}) or {}
    cells = [
        ("夜盤收盤", _fmt(tx.get("night_close"), 0)),
        ("漲跌點數", _fmt(tx.get("change_points"), 0)),
        ("漲跌幅", _pct(tx.get("change_pct"))),
        ("夜盤高低", f"{_fmt(tx.get('night_high'), 0)} / {_fmt(tx.get('night_low'), 0)}"),
        ("成交量", _fmt(tx.get("volume"), 0)),
        ("總未平倉", _fmt(tx.get("total_oi"), 0)),
        ("外資淨 OI", _fmt(tx.get("foreign_net_oi"), 0)),
        ("外資淨 OI 增減", _fmt(tx.get("foreign_net_change"), 0)),
    ]
    for i, (label, value) in enumerate(cells):
        x, y = 60 + (i % 4) * 455, 190 + (i // 4) * 330
        _panel(d, (x, y, x + 420, y + 250))
        d.text((x + 22, y + 24), label, font=_font(24, True), fill=MUTED)
        d.text((x + 22, y + 92), value, font=_font(46, True), fill=INK)
    d.text((60, 900), f"歸屬交易日 {tx.get('session_trade_date', 'N/A')}｜{tx.get('night_session_window', '')}",
           font=_font(22, True), fill=ACCENT)
    return im


def _scene8(rep, date_text, assets):
    im, d = _base("本週重要行事曆與大型企業財報", date_text, "行事曆")
    _panel(d, (45, 150, 1120, 900))
    _panel(d, (1150, 150, 1875, 900))
    d.text((75, 180), "本週重要總經事件", font=_font(30, True), fill=INK)
    for i, item in enumerate(rep.get("weekly_calendar", [])[:7]):
        y = 245 + i * 88
        d.text((80, y), str(item.get("time_tw") or item.get("date", "")), font=_font(20, True), fill=INFO)
        d.text((80, y + 34), str(item.get("event", ""))[:34], font=_font(23, True), fill=INK)
        d.text((980, y), str(item.get("importance", "")), anchor="ra", font=_font(19, True), fill=MUTED)
    d.text((1180, 180), "市值前100大企業財報", font=_font(30, True), fill=INK)
    for i, item in enumerate(rep.get("earnings_calendar", [])[:8]):
        y = 245 + i * 76
        d.text((1185, y), str(item.get("date", "")), font=_font(19), fill=INFO)
        d.text((1185, y + 30), str(item.get("company", "")), font=_font(23, True), fill=INK)
        d.text((1700, y + 30), str(item.get("ticker", "")), anchor="ra", font=_font(21, True), fill=MUTED)
        d.text((1845, y + 30), str(item.get("timing", ""))[:6], anchor="ra", font=_font(18), fill=MUTED)
    return im


BUILDERS = {1: _scene1, 2: _scene2, 3: _scene3, 4: _scene4,
            5: _scene5, 6: _scene6, 7: _scene7, 8: _scene8}


def render_daily_video(report: dict, finviz_png: Path, voice_mp3: Path, subtitles_srt: Path,
                       timeline: list[dict], out_dir: Path, date_text: str) -> Path:
    """timeline 來自 tts_edge.synthesize_segments()：畫面秒數 = 旁白秒數。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not timeline:
        raise RuntimeError("Empty narration timeline")
    if not subtitles_srt.exists() or subtitles_srt.stat().st_size < 16:
        raise RuntimeError(f"Subtitle file missing or empty: {subtitles_srt}")

    assets = {"finviz": finviz_png}
    clips = []
    for i, row in enumerate(timeline, 1):
        scene = row["scene"]
        builder = BUILDERS.get(scene)
        if builder is None:
            continue
        im = builder(report, date_text, assets)
        png = out_dir / f"scene{scene:02}.png"
        mp4 = out_dir / f"clip{i:02}.mp4"
        im.save(png)
        sec = max(1.5, float(row["duration"]))
        zoom = "min(zoom+0.00030,1.035)" if scene == 4 else "min(zoom+0.00012,1.018)"
        vf = (f"scale=2048:1152,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d=1:s=1920x1080:fps=30,format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(png), "-vf", vf,
                        "-t", f"{sec:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "21", str(mp4)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clips.append(mp4)

    concat = out_dir / "scenes.txt"
    concat.write_text("\n".join(f"file '{p.name}'" for p in clips), encoding="utf-8")
    visual = out_dir / "visual.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat.name,
                    "-c", "copy", visual.name],
                   cwd=out_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 字幕燒進畫面（底部固定）+ 保留軟字幕軌
    final = out_dir / f"daily_finance_{date_text}.mp4"
    subprocess.run([
        "ffmpeg", "-y",
        "-i", visual.name,
        "-i", str(voice_mp3.resolve()),
        "-i", str(subtitles_srt.resolve()),
        "-filter_complex", f"[0:v]subtitles={subtitles_srt.name}:force_style='{SUB_STYLE}'[v]",
        "-map", "[v]", "-map", "1:a:0", "-map", "2:s:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-c:s", "mov_text",
        "-metadata:s:s:0", "language=zho", "-disposition:s:0", "default",
        "-shortest", "-movflags", "+faststart", final.name
    ], cwd=out_dir, check=True)
    return final
