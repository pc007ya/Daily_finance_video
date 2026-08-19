from __future__ import annotations

"""Finviz 擷取：只截地圖本身，並檢查熱力圖是否真的畫出來了。

與舊版的差異
- 先關掉 cookie / 廣告橫幅，再對 treemap 元素本身截圖（element screenshot），
  導覽列與頁尾根本不會進到 PNG，不需要事後按比例裁。
- 找不到元素時退回全頁截圖，交給 render_video._auto_crop 依彩色像素邊界裁。
- 新增彩度檢查：彩色像素比例過低視為沒渲染成功（比只看檔案 > 50KB 可靠）。
"""

import os
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

FINVIZ_URL = os.getenv("FINVIZ_URL", "https://finviz.com/map?t=sec_ndx")
MAP_SELECTORS = ["#body canvas", "canvas", "#chart", ".chart", "svg.map"]
DISMISS = ["button:has-text('Accept')", "button:has-text('I agree')",
           "#onetrust-accept-btn-handler", "[aria-label='Close']"]


def _colored_ratio(path: Path) -> float:
    im = Image.open(path).convert("RGB")
    im = im.resize((im.width // 6, im.height // 6))
    px = im.load()
    hits = 0
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            if max(r, g, b) - min(r, g, b) > 28 and max(r, g, b) > 60:
                hits += 1
    return hits / (im.width * im.height)


def capture_finviz(output_path: str | Path, min_colored: float = 0.12) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        page = browser.new_page(
            viewport={"width": 1920, "height": 1200},
            device_scale_factor=2,
            user_agent=("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"),
        )
        page.set_default_timeout(30_000)
        try:
            page.goto(FINVIZ_URL, wait_until="domcontentloaded", timeout=45_000)
        except PlaywrightTimeoutError:
            pass

        for sel in DISMISS:
            try:
                loc = page.locator(sel).first
                if loc.count() and loc.is_visible():
                    loc.click(timeout=1500)
            except Exception:
                pass

        page.wait_for_timeout(8_000)

        shot = None
        for sel in MAP_SELECTORS:
            loc = page.locator(sel).first
            try:
                if loc.count() and loc.is_visible():
                    box = loc.bounding_box()
                    if box and box["width"] > 700 and box["height"] > 400:
                        loc.screenshot(path=str(output))
                        shot = sel
                        break
            except Exception:
                continue
        if shot is None:
            page.screenshot(path=str(output), full_page=False)
        browser.close()

    if not output.exists() or output.stat().st_size < 50_000:
        raise RuntimeError("Finviz screenshot is missing or unexpectedly small")
    ratio = _colored_ratio(output)
    if ratio < min_colored:
        raise RuntimeError(f"Finviz heatmap did not render (colored pixel ratio {ratio:.3f})")
    print(f"Finviz captured via {shot or 'full page'}; colored ratio {ratio:.3f}")
    return output
