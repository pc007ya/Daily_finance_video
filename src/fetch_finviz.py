from __future__ import annotations

import os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

FINVIZ_URL = os.getenv("FINVIZ_URL", "https://finviz.com/map?t=sec_ndx")


def capture_finviz(output_path: str | Path) -> Path:
    """Capture the latest NASDAQ-100 Finviz heatmap as a PNG.

    Finviz keeps background requests open, so waiting for networkidle can time
    out on CI. Wait for DOM content instead, then give the map time to render.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        page = browser.new_page(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
            ),
        )
        page.set_default_timeout(30_000)
        try:
            page.goto(FINVIZ_URL, wait_until="domcontentloaded", timeout=45_000)
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(8_000)
        if page.locator("body").count() == 0:
            browser.close()
            raise RuntimeError("Finviz page did not render a document body")

        page.screenshot(path=str(output), full_page=False)
        browser.close()

    if not output.exists() or output.stat().st_size < 50_000:
        raise RuntimeError("Finviz screenshot is missing or unexpectedly small")
    return output
