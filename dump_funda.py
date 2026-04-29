"""One-off: dump funda.nl filtered search page so we can write reliable selectors.

Filters:
  - detached house
  - within 50km of Amsterdam
  - 3+ bedrooms
  - plot >= 700 m²
  - price <= EUR 1,000,000
"""
from __future__ import annotations

import re
import subprocess
import time

import undetected_chromedriver as uc

URL = (
    "https://www.funda.nl/zoeken/koop"
    '?selected_area=%5B%22amsterdam%2C50km%22%5D'
    '&object_type=%5B%22house%22%5D'
    '&house_type=%5B%22detached_house%22%5D'
    '&price=%220-1000000%22'
    '&plot_area=%22700-%22'
    '&bedrooms=%223-%22'
    "&sort=%22date_down%22"
)


def _chrome_major() -> int | None:
    try:
        out = subprocess.check_output(
            ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
            stderr=subprocess.DEVNULL,
        ).decode()
        m = re.search(r"(\d+)\.", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None


def main() -> None:
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,1400")
    options.add_argument("--lang=nl-NL")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = uc.Chrome(options=options, version_main=_chrome_major())
    try:
        print(f"Loading {URL}")
        driver.get(URL)
        time.sleep(10)

        # Try to dismiss the cookie wall if present
        for sel in [
            "button#onetrust-accept-btn-handler",
            "button[data-testid='accept-cookies']",
            "button[aria-label*='akkoord' i]",
            "button[aria-label*='accept' i]",
        ]:
            try:
                driver.find_element("css selector", sel).click()
                print(f"clicked cookie button: {sel}")
                time.sleep(2)
                break
            except Exception:
                continue

        # Scroll to force lazy-loaded cards
        for y in (600, 1400, 2400, 3600):
            driver.execute_script(f"window.scrollTo(0, {y});")
            time.sleep(1)

        html = driver.page_source
        with open("funda_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        driver.save_screenshot("funda_screenshot.png")

        print(f"final url: {driver.current_url}")
        print(f"dump size: {len(html):,} chars")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
