# Daily Finance Video V2 — Implementation Direction

## Baseline

Implement from the current `main` branch. Preserve the working daily pipeline; this is an incremental refactor, not a rewrite.

## Non-negotiable duration policy

- Do **not** target or hard-code 120 seconds.
- Video duration is dynamic and derived from measured TTS narration duration plus required transitions/padding.
- `MAX_VIDEO_SECONDS=300` is the only hard duration cap.
- Do not speed up narration or truncate audio/video at 300 seconds.
- If narration would exceed 300 seconds, remove lower-priority narration before final render, preserving complete sentences and the closing segment.

## Truth layers

- `output/YYYY-MM-DD/morning_report.json` = **DATA TRUTH**
- `output/YYYY-MM-DD/scene_plan.json` = **PRESENTATION TRUTH**
- `output/YYYY-MM-DD/post_render_qa.json` = **QUALITY TRUTH**
- `output/YYYY-MM-DD/delivery_status.json` = **DELIVERY TRUTH**

Renderer must never independently fetch market data.

## Canonical rules

1. Start from `data/latest/morning_report.json`.
2. Validate `report_date` and `market_trade_date`.
3. GitHub fallback sources may fill only null/missing fields.
4. Fallback observations must match `market_trade_date`.
5. Never overwrite a valid canonical value with a different source/date.
6. Persist the final validated package to `output/YYYY-MM-DD/morning_report.json`.
7. Keep validation/audit information.

## P0 implementation

### 1. scene_plan.json

Add a scene-plan builder. `scene_plan.json` is the sole presentation timeline and must contain dynamic measured timing, narration/audio references, template/type, data bindings, assets, fallback policy and QA requirements.

Do not duplicate market values into scene_plan. Bind components to JSON paths in final `morning_report.json`.

Recommended scene types:

1. `market_overview`
2. `finviz_heatmap`
3. `ai_semiconductor`
4. `breaking_news`
5. `economic_calendar`
6. `earnings_calendar`
7. `taiwan_futures`

Scenes may be skipped when required data is unavailable. Narration and visuals must be skipped together.

### 2. Renderer reads scene plan

Refactor renderer toward a registry keyed by `scene.type`, not scene index. Keep current Python/Pillow/FFmpeg renderer for V2.0; do not migrate to Remotion yet.

### 3. Finviz scope

Do not hard-code NASDAQ-100. Read market scope/title/path/expected trade date from canonical Finviz metadata. Preserve existing screenshot/crop/visual QA fallback logic.

### 4. FinMind fallback

For US equities, fill at least `close`, `previous_close`, `change`, and `change_pct` when reliable same-date data exists. Do not invent 52-week values when unavailable. Preserve canonical-first/null-only behavior.

For USD/TWD, preserve quote semantics (`market_close`, `spot_sell`, etc.) rather than silently treating different quote types as identical.

### 5. TAIFEX contract selection

Do not define front month as simply the highest-volume row. Parse valid contract months, select the nearest valid month for the session date, and use volume only as a secondary selector. Record selected contract and reason in validation/audit output.

### 6. Chinese text wrapping

Replace fixed character slicing such as `headline[:58]` with font/pixel-width wrapping, max-line handling, and ellipsis.

### 7. Post-render QA

Create `post_render_qa.json`. At minimum verify:

- MP4 exists and has a reasonable size
- 1920×1080
- ~30 fps
- video duration > 0 and <= 300 seconds
- audio track exists
- subtitle expectations are met
- `abs(video_duration - audio_duration) <= 0.4s`
- scene planned/rendered duration differences
- report_date / market_trade_date / source_mode are present

### 8. Delivery status

Create `delivery_status.json` containing at least:

- report_date
- market_trade_date
- canonical status
- same-date validation status
- scene-plan status
- TTS status
- render status
- video QA status
- Google Drive status
- GitHub artifact status where determinable
- final MP4 filename
- Google Drive URL/identifier when available
- generated timestamp

The 07:00 morning-report consumer should use this as the primary handoff status instead of guessing from workflow timing.

### 9. GitHub Actions resilience

Artifact upload must run with `if: always()` so diagnostics and any successfully produced MP4 survive even when Google Drive upload fails.

Persist when available:

- final `morning_report.json`
- `validation_report.json`
- `scene_plan.json`
- `narration_timeline.json`
- `post_render_qa.json`
- `delivery_status.json`
- MP4

## Missing-data policy

A missing optional field must not fail the full video.

Recommended behavior:

- missing field → display `--`
- missing optional component asset → skip component
- missing scene-level required data → skip scene and its narration
- never narrate a scene whose visual/data section was skipped

## Acceptance tests

1. Normal complete-data day renders successfully.
2. Missing Taiwan futures skips the futures scene/narration and still passes.
3. Finviz failure uses fallback/skip behavior without killing the entire video.
4. Long narration remains A/V synced and <=300 seconds.
5. Short narration is not padded to an artificial target duration.
6. Wrong-date fallback is rejected and audited as a date mismatch.
7. Google Drive upload failure still leaves GitHub artifact/diagnostics.
8. Every displayed market number is traceable to final `output/YYYY-MM-DD/morning_report.json`.

## P1 after P0 passes a real GitHub Actions run

- primary candlestick/K-line component
- Finviz zoom/focus animation
- improved word-level subtitle timing
- scene preview thumbnails
- HERO earnings layout
- production-status dashboard

## Do not do in V2.0

- Do not import the full OpenMontage framework.
- Do not rewrite the pipeline as a large agent system.
- Do not migrate the renderer wholesale to Remotion.
- Do not change the 06:30 schedule merely to solve GitHub queue delay.
- Do not reintroduce a 120-second target.
- Do not let renderer fetch independent market prices.

## Required implementation workflow

Before modifying production code, create an implementation plan describing current behavior, affected files, migration steps, compatibility risks and tests. Preserve the currently working pipeline during migration.

After implementation, run syntax/tests and document changed/new files, behavior changes, known limitations and test results.
