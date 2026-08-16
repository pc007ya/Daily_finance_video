# Daily Finance Video

每日自動產生台灣早晨國際財經影片。

## 目標流程

07:00 台灣時間觸發 → 抓取最新完成交易日市場資料 → 取得 Finviz NASDAQ-100 Heatmap → 產生旁白與字幕 → Azure Speech `zh-TW-HsiaoChenNeural` → FFmpeg 合成 MP4 → 上傳 GitHub Actions artifact。

## 固定影片規格

- 16:9 / 1920×1080
- 字幕固定最底部
- Finviz：`https://finviz.com/map?t=sec_ndx`
- 指數：收盤價 + 漲跌點數 + 漲跌幅
- 個股：收盤價 + 漲跌金額 + 漲跌幅 + 52W Low/High + 52W 位階% + 距 52W High%
- 台指期：收盤點數 + 漲跌點數 + 漲跌幅 + OI 判讀
- 重大財報：營收 / EPS / 財測 / 盤後反應 / 台股供應鏈影響

## 專案結構

```text
src/
  main.py
  fetch_market.py
  fetch_finviz.py
  tts_azure.py
  render_video.py
.github/workflows/daily.yml
requirements.txt
.env.example
```

## GitHub Secrets

需要設定：

- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION`

## 執行

```bash
python -m src.main
```

目前為第一版自動化骨架，接下來逐步補齊市場資料來源、台指期/OI、字幕與 V9 視覺模板。
