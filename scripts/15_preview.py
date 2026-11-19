"""The link-preview picture: output/preview.jpg, a 1200 x 630 screenshot of the live site.

iMessage, Slack and the like show it as the big card when someone is sent the site's link (the Open Graph tags in
13_overview.py's page point at it, and publish_site.sh copies it next to that page). It is the real map, taken from
the published site in a headless Brave with the legend folded so the creeks fill the card. No AREA needed. Run it by
hand when the picture should change; it is not part of publish_site.sh, since it photographs what is already live.
    15_preview.py                                    the San Gabriels from the LA map
    PREVIEW='la/stream_map.html#34.27,-117.95,12' 15_preview.py      any page and view under /streams/
Needs Brave and the playwright package (no browser download): any Python that has it, e.g.
    python3 -m venv /tmp/pw && /tmp/pw/bin/pip install playwright && /tmp/pw/bin/python scripts/15_preview.py
"""
import os, subprocess, time
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SITE = "https://alexanderswann.github.io/streams/"
BROWSER = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
page_view = os.environ.get("PREVIEW", "la/stream_map.html#34.27,-117.95,12")
out, raw = f"{ROOT}/output/preview.jpg", f"{ROOT}/output/preview_2x.png"

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=BROWSER, headless=True)
    pg = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
    pg.goto(SITE + page_view, wait_until="load", timeout=300_000)
    fold = pg.locator("button.lx")                  # the area maps' legend: fold it to its title
    if fold.count():
        fold.first.click()
    pg.wait_for_load_state("networkidle", timeout=120_000)
    time.sleep(6)                                   # the last tiles fade in
    pg.screenshot(path=raw)
    b.close()
subprocess.run(["sips", "-z", "630", "1200", "-s", "format", "jpeg", "-s", "formatOptions", "85", raw, "--out", out],
               check=True, capture_output=True)
os.remove(raw)
print(f"{out}: {SITE}{page_view}, {os.path.getsize(out) // 1024} KB")
