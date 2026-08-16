from __future__ import annotations

import os
from pathlib import Path
from playwright.sync_api import sync_playwright

FINVIZ_URL = os.getenv("FINVIZ_URL", "https://finviz.com/map?t=sec_ndx")


def capture_finviz(output_path: str | Path) -> Path:
    """Capture the latest NASDAQ-100 Finviz heatmap as a PNG.

    The page is loaded fresh on each run so Taiwan morning output reflects the
    latest completed US trading session. If the US market was closed, Finviz
    naturally remains on the latest available session.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.goto(FINVIZ_URL, wait_until="networkidle", timeout=90_000)
        page.wait_for_timeout(3000)
        page.screenshot(path=str(output), full_page=False)
        browser.close()

    return output
