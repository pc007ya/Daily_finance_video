from __future__ import annotations

"""Sector-rotation aware renderer.

Keeps the established renderer/layout intact, inserts Sector Rotation as scene 5,
and shifts the previous scenes 5-8 to 6-9.
"""

from pathlib import Path
from PIL import Image

from . import render_video as legacy


def _scene5_rotation(rep, date_text, assets):
    im, d = legacy._base("S&P 500 Sector Rotation｜RRG-style vs SPY", date_text, "輪動")
    rot = rep.get("sector_rotation") or {}
    path = rot.get("path")

    if path and Path(path).exists():
        src = Image.open(path).convert("RGB")
        box = (45, 135, 1435, 920)
        bw, bh = box[2] - box[0], box[3] - box[1]
        ratio = min(bw / src.width, bh / src.height)
        rs = src.resize((int(src.width * ratio), int(src.height * ratio)))
        ox, oy = box[0] + (bw - rs.width) // 2, box[1] + (bh - rs.height) // 2
        im.paste(rs, (ox, oy))
        d.rectangle((ox - 1, oy - 1, ox + rs.width, oy + rs.height), outline=legacy.RULE, width=2)
    else:
        legacy._panel(d, (45, 135, 1435, 920))
        d.text((740, 525), "Sector Rotation 圖表資料待確認", anchor="mm",
               font=legacy._font(30, True), fill=legacy.MUTED)

    legacy._panel(d, (1470, 150, 1875, 900))
    d.text((1672, 182), "RRG 輪動訊號", anchor="mm", font=legacy._font(28, True), fill=legacy.INK)

    sig = rot.get("signals") or {}
    groups = [
        ("LEADING", sig.get("leading") or [], legacy.UP),
        ("IMPROVING", sig.get("improving") or [], legacy.INFO),
        ("WEAKENING", sig.get("weakening") or [], legacy.ACCENT),
        ("LAGGING", sig.get("lagging") or [], legacy.MUTED),
    ]
    y = 228
    for label, names, col in groups:
        d.text((1505, y), label, font=legacy._font(19, True), fill=col)
        text = "、".join(names[:4]) if names else "—"
        d.text((1505, y + 30), text, font=legacy._font(19, True), fill=legacy.INK)
        y += 78

    rows = rot.get("sectors") or []
    leaders = sorted(rows, key=lambda r: r.get("relative_20d_pct", -999), reverse=True)[:3]
    d.text((1505, 555), "相對 SPY 強弱", font=legacy._font(20, True), fill=legacy.INK)
    d.text((1505, 585), "ETF     1D      5D      20D", font=legacy._font(16, True), fill=legacy.MUTED)
    yy = 618
    for r in leaders:
        line = f"{r.get('ticker','—'):<5} {r.get('relative_1d_pct',0):>+5.1f}% {r.get('relative_5d_pct',0):>+5.1f}% {r.get('relative_20d_pct',0):>+6.1f}%"
        d.text((1505, yy), line, font=legacy._font(16, True), fill=legacy.SOFT)
        yy += 34

    transitions = sig.get("transitions") or []
    d.text((1505, 735), "象限切換", font=legacy._font(18, True), fill=legacy.MUTED)
    if transitions:
        for i, line in enumerate(transitions[:2]):
            d.text((1505, 765 + i * 30), str(line)[:31], font=legacy._font(15, True), fill=legacy.SOFT)
    else:
        d.text((1505, 765), "今日無象限切換", font=legacy._font(15, True), fill=legacy.SOFT)

    d.text((1505, 836), f"交易日 {rot.get('trade_date', 'N/A')}", font=legacy._font(15), fill=legacy.MUTED)
    d.text((1505, 861), "中心值 100｜尾跡 5 日", font=legacy._font(15), fill=legacy.MUTED)
    d.text((1505, 884), "開放近似算法，非 JdK 專有公式", font=legacy._font(13), fill=legacy.MUTED)
    return im


legacy.BUILDERS.clear()
legacy.BUILDERS.update({
    1: legacy._scene1,
    2: legacy._scene2,
    3: legacy._scene3,
    4: legacy._scene4,
    5: _scene5_rotation,
    6: legacy._scene5,
    7: legacy._scene6,
    8: legacy._scene7,
    9: legacy._scene8,
})


def render_daily_video(report: dict, finviz_png: Path, voice_mp3: Path, subtitles_srt: Path,
                       timeline: list[dict], out_dir: Path, date_text: str) -> Path:
    return legacy.render_daily_video(report, finviz_png, voice_mp3, subtitles_srt, timeline, out_dir, date_text)
