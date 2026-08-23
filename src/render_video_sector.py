from __future__ import annotations

"""Sector-rotation aware renderer.

Keeps the established renderer/layout intact, inserts Sector Rotation as scene 5,
and shifts the previous scenes 5-8 to 6-9.
"""

from pathlib import Path
from PIL import Image

from . import render_video as legacy


def _scene5_rotation(rep, date_text, assets):
    im, d = legacy._base("S&P 500 Sector Rotation｜相對 SPY", date_text, "輪動")
    rot = rep.get("sector_rotation") or {}
    path = rot.get("path")

    if path and Path(path).exists():
        src = Image.open(path).convert("RGB")
        box = (45, 135, 1460, 920)
        bw, bh = box[2] - box[0], box[3] - box[1]
        ratio = min(bw / src.width, bh / src.height)
        rs = src.resize((int(src.width * ratio), int(src.height * ratio)))
        ox, oy = box[0] + (bw - rs.width) // 2, box[1] + (bh - rs.height) // 2
        im.paste(rs, (ox, oy))
        d.rectangle((ox - 1, oy - 1, ox + rs.width, oy + rs.height), outline=legacy.RULE, width=2)
    else:
        legacy._panel(d, (45, 135, 1460, 920))
        d.text((752, 525), "Sector Rotation 圖表資料待確認", anchor="mm",
               font=legacy._font(30, True), fill=legacy.MUTED)

    legacy._panel(d, (1495, 150, 1875, 900))
    d.text((1685, 185), "輪動訊號", anchor="mm", font=legacy._font(30, True), fill=legacy.INK)
    sig = rot.get("signals") or {}
    groups = [
        ("LEADING", sig.get("leading") or [], legacy.UP),
        ("EMERGING", sig.get("emerging") or [], legacy.INFO),
        ("FADING", sig.get("fading") or [], legacy.ACCENT),
    ]
    y = 245
    for label, names, col in groups:
        d.text((1530, y), label, font=legacy._font(22, True), fill=col)
        text = "、".join(names[:4]) if names else "—"
        d.text((1530, y + 38), text, font=legacy._font(22, True), fill=legacy.INK)
        y += 118

    transitions = sig.get("transitions") or []
    d.text((1530, y + 5), "象限切換", font=legacy._font(22, True), fill=legacy.MUTED)
    for i, line in enumerate(transitions[:3]):
        d.text((1530, y + 46 + i * 48), str(line)[:28], font=legacy._font(18, True), fill=legacy.SOFT)

    d.text((1530, 820), f"交易日 {rot.get('trade_date', 'N/A')}", font=legacy._font(18), fill=legacy.MUTED)
    d.text((1530, 853), "X：1M vs SPY", font=legacy._font(18), fill=legacy.MUTED)
    d.text((1530, 882), "Y：1W vs SPY｜尾跡 5 日", font=legacy._font(18), fill=legacy.MUTED)
    return im


# Scene 5 is the new Sector Rotation page. Existing pages shift by one.
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
