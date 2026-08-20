# Daily Finance Video

每日自動產生台灣早晨國際財經影片，並與 07:00 文字晨報共用同一份 canonical market package。

## 目前正式流程

```text
06:00 canonical morning_report.json
        ↓
06:30 GitHub Actions scheduled run
        ↓
same-date validation / null fill
(yfinance → TAIFEX → FinMind)
        ↓
output/YYYY-MM-DD/morning_report.json
        ↓
build_narration.py
        ↓
tts_edge.py（逐句 Edge TTS + 實測 duration）
        ↓
narration_timeline.json
        ↓
render_video.py
        ↓
MP4
        ↓
Google Drive + GitHub Actions artifact
        ↓
07:00 國際財經晨報
```

## Canonical 規則

- `data/latest/morning_report.json`：06:00 上游 canonical。
- `output/YYYY-MM-DD/morning_report.json`：GitHub 同交易日補值後的 final canonical，影片與 07:00 文字晨報應優先使用這份。
- fallback 只能補 `None` / 空欄位。
- fallback observation 必須與 `market_trade_date` 相同。
- 不得用不同交易日資料覆蓋 canonical。
- renderer 不應自行重新抓取另一份市場行情。

## 影片時長政策

影片**不設定固定目標秒數**，也不得使用固定 120 秒或固定 scene weights。

正式規則：

```text
video duration = actual TTS narration duration
```

- 每句旁白由 `tts_edge.synthesize_segments()` 分段合成。
- 每句用 `ffprobe` 實測 duration。
- Scene `start / end / duration` 由實際語音 timeline 產生。
- `render_video.py` 依 timeline 決定畫面長度。
- 預設硬上限：`MAX_VIDEO_SECONDS=300`。
- 影片總長只要 `> 0` 且 `<= 300s` 即視為符合長度規格。
- 不因影片超過 120 秒而判定失敗。
- 不允許為了符合固定秒數而任意加速語音或截斷畫面。

目前 `tts_edge.py` 在超過 300 秒預算時，以完整句子為單位停止加入後續內容，保留結尾句，不切半句。

## 目前資料來源

### 市場資料

- canonical morning package
- yfinance：同交易日 null fill
- FinMind：同交易日補缺，不覆蓋 canonical

### 台指期 / OI

優先：

1. TAIFEX OpenAPI
2. FinMind fallback

夜盤歸屬遵守 TAIFEX 規則：15:00–05:00 歸屬次一交易日；不同 session date 的資料不得混用。

### Finviz

- 優先直接擷取 treemap / chart 元素。
- 截不到才退回整頁 screenshot。
- render 前使用彩度自動裁切熱力圖有效區域。
- 使用彩色像素比例檢查圖片是否真的成功渲染。

## 字幕

- Edge TTS：`zh-TW-HsiaoChenNeural`
- 逐 Scene / 逐句合成。
- 字幕依標點與最大字數拆分。
- 最終 MP4 使用 burned subtitle，並可保留 soft subtitle track。
- GitHub runner 需安裝 `fonts-noto-cjk`。

## 目前主要程式

```text
src/
  main.py
  build_report.py
  build_narration.py
  fetch_market.py
  fetch_finviz.py
  fetch_taifex.py
  fetch_finmind.py
  tts_edge.py
  render_video.py
  upload_gdrive.py

.github/workflows/daily.yml
requirements.txt
data/latest/morning_report.json
```

## V2 下一階段

下一階段採 OpenMontage-Lite 概念，但不整套搬入 OpenMontage。

核心新增：

```text
morning_report.json     = DATA TRUTH
scene_plan.json         = PRESENTATION TRUTH
post_render_qa.json     = QUALITY TRUTH
delivery_status.json    = DELIVERY TRUTH
```

### scene_plan.json

預計控制：

- Scene 順序
- 動態 start / end / duration
- narration / audio / subtitle
- visual template
- canonical data bindings
- assets
- animations
- missing-data fallback
- scene QA

Scene 時長仍由實際 TTS 決定，不為每個 Scene 寫死秒數。

### 建議 Scene 類型

1. Market Overview
2. Finviz Heatmap
3. AI / Semiconductor
4. Breaking News
5. Weekly Economic Calendar
6. Earnings
7. Taiwan Futures / OI

Scene 可以依當日資料缺失狀態跳過，不應為了維持固定影片長度而空轉。

## QA 目標

V2 至少檢查：

- final canonical 存在
- `report_date` / `market_trade_date` 正確
- MP4 存在
- 1920×1080
- audio track 存在
- video duration > 0
- video duration <= 300 秒
- audio / video duration 差異在容許範圍內
- subtitle 存在
- 每個 renderer 數字皆可追溯至 final canonical

## GitHub / Google Drive Delivery

06:30 GitHub Scheduled Action 可能因 GitHub queue 延遲，不應假設 06:30 準時完成。

07:00 晨報應確認當日影片，不得拿前一日 MP4 替代。

V2 預計新增 `delivery_status.json`，記錄：

```json
{
  "report_date": "YYYY-MM-DD",
  "canonical": "PASS",
  "same_date_validation": "PASS",
  "scene_plan": "PASS",
  "tts": "PASS",
  "render": "PASS",
  "video_qa": "PASS",
  "gdrive": "PASS",
  "artifact": "PASS",
  "final_mp4": "daily_finance_YYYY-MM-DD.mp4"
}
```

GitHub artifact upload 應最終改為 `if: always()`，確保即使 Google Drive upload 失敗，仍保留 output 與診斷檔案。

## 執行

```bash
python -m src.main
```

若需要自訂影片最大長度：

```bash
MAX_VIDEO_SECONDS=300 python -m src.main
```

預設即為 300 秒。
