from __future__ import annotations

"""逐段合成，讓「畫面長度」等於「該段旁白的真實長度」。

影片總長不寫死：多長完全由旁白決定，只有 MAX_VIDEO_SECONDS（預設 300 秒）這個上限，
超過就整句捨棄後面的內容並保留結尾語，不會把句子切一半。

回傳 timeline：每個分鏡的精確 start / end（秒），render_video 直接照它切畫面，
不再需要 weights=[10,20,20,30,25,15] 這種寫死的比例，也不再假設影片是 120 秒。
字幕依標點切成 <=14 字的短塊，避免單句掛 11.8 秒。
"""

import asyncio
import json
import os
import re
import subprocess
from pathlib import Path

import edge_tts

VOICE = "zh-TW-HsiaoChenNeural"
RATE = "-2%"
MAX_SUB_CHARS = 14

# 影片長度不寫死（多長由旁白決定），但設一個上限避免失控。
# 逐句合成時一旦累積超過上限就停止收句，並保證結尾那句一定唸完。
MAX_TOTAL_SEC = float(os.getenv("MAX_VIDEO_SECONDS", "300"))


def _duration(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", str(path)
    ]).decode().strip())


def _ts(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _chunks(text: str) -> list[str]:
    parts = [p for p in re.split(r"(?<=[，、。；！？])", text) if p.strip()]
    out: list[str] = []
    for p in parts:
        if out and len(out[-1]) + len(p) <= MAX_SUB_CHARS:
            out[-1] += p
        elif len(p) <= MAX_SUB_CHARS:
            out.append(p)
        else:
            for i in range(0, len(p), MAX_SUB_CHARS):
                out.append(p[i:i + MAX_SUB_CHARS])
    return out or [text]


async def _speak(text: str, path: Path) -> None:
    communicate = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE)
    with path.open("wb") as fh:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])


def synthesize_segments(segments: list[dict], out_dir: Path) -> dict:
    """segments: [{"scene": int, "text": str}] —— 順序即播放順序。"""
    parts_dir = out_dir / "voice_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    timed: list[dict] = []
    cursor = 0.0
    files: list[Path] = []
    dropped: list[dict] = []

    # 結尾語先合成量長度，把它的秒數從預算裡扣掉，這樣 MAX_TOTAL_SEC 才是真正的硬上限
    body, tail = segments[:-1], segments[-1]
    tail_part = parts_dir / "seg_tail.mp3"
    asyncio.run(_speak(tail["text"], tail_part))
    tail_dur = _duration(tail_part)
    budget = MAX_TOTAL_SEC - tail_dur

    for i, seg in enumerate(body, 1):
        part = parts_dir / f"seg{i:03}.mp3"
        asyncio.run(_speak(seg["text"], part))
        dur = _duration(part)
        if cursor + dur > budget:
            # 整句捨棄，不切半句；後面的句子一併不要，維持敘事順序
            dropped.extend(body[i - 1:])
            part.unlink(missing_ok=True)
            break
        timed.append({**seg, "start": cursor, "end": cursor + dur, "duration": dur})
        cursor += dur
        files.append(part)

    timed.append({**tail, "start": cursor, "end": cursor + tail_dur, "duration": tail_dur})
    cursor += tail_dur
    files.append(tail_part)

    if dropped:
        print(f"MAX_VIDEO_SECONDS={MAX_TOTAL_SEC:.0f}s 上限生效，捨棄 {len(dropped)} 句："
              f"{'／'.join(s['text'][:12] for s in dropped)}")

    concat = parts_dir / "parts.txt"
    concat.write_text("\n".join(f"file '{p.name}'" for p in files), encoding="utf-8")
    voice = out_dir / "voice.mp3"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat.name,
        "-c", "copy", str(voice.resolve())
    ], cwd=parts_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 字幕：段落邊界是實測值，段內按字數比例分配
    blocks, n = [], 0
    for seg in timed:
        pieces = _chunks(seg["text"])
        total = sum(len(p) for p in pieces) or 1
        t = seg["start"]
        for j, piece in enumerate(pieces):
            share = seg["duration"] * len(piece) / total
            end = seg["end"] if j == len(pieces) - 1 else min(seg["end"], t + share)
            n += 1
            blocks.append(f"{n}\n{_ts(t)} --> {_ts(end)}\n{piece}\n")
            t = end
    srt = out_dir / "subtitles.srt"
    srt.write_text("\n".join(blocks) + "\n", encoding="utf-8")

    # timeline：每個 scene 的精確區間
    timeline = []
    for seg in timed:
        if timeline and timeline[-1]["scene"] == seg["scene"]:
            timeline[-1]["end"] = seg["end"]
        else:
            timeline.append({"scene": seg["scene"], "start": seg["start"], "end": seg["end"]})
    for row in timeline:
        row["duration"] = round(row["end"] - row["start"], 3)

    (out_dir / "narration_timeline.json").write_text(
        json.dumps({"total": cursor, "max_total_sec": MAX_TOTAL_SEC,
                    "dropped_for_length": dropped, "timeline": timeline, "segments": timed},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    return {"voice": voice, "subtitles": srt, "timeline": timeline, "total": cursor}
