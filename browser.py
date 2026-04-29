"""Shared Chrome driver factory for the funda.nl and fundainbusiness.nl scrapers."""
from __future__ import annotations

import logging
import re
import subprocess

import undetected_chromedriver as uc

from config import HEADLESS

logger = logging.getLogger(__name__)


def chrome_major_version() -> int | None:
    """Detect installed Chrome major version (Linux + macOS)."""
    candidates = [
        ["google-chrome", "--version"],
        ["chromium-browser", "--version"],
        ["chromium", "--version"],
        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
    ]
    for argv in candidates:
        try:
            out = subprocess.check_output(argv, stderr=subprocess.DEVNULL).decode()
            match = re.search(r"(\d+)\.", out)
            if match:
                return int(match.group(1))
        except Exception:
            continue
    return None


def create_driver() -> uc.Chrome:
    """Create an undetected Chrome driver tuned for funda's bot detection."""
    options = uc.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=nl-NL")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    version = chrome_major_version()
    logger.info("Detected Chrome version: %s", version)
    return uc.Chrome(options=options, version_main=version)


def dismiss_cookie_wall(driver) -> None:
    """Best-effort accept of cookie/consent dialogs (funda + fundainbusiness)."""
    selectors = [
        "button#onetrust-accept-btn-handler",
        "button[data-testid='accept-cookies']",
        "button[aria-label*='akkoord' i]",
        "button[aria-label*='accept' i]",
    ]
    from selenium.webdriver.common.by import By
    for sel in selectors:
        try:
            driver.find_element(By.CSS_SELECTOR, sel).click()
            logger.info("Dismissed cookie wall via %s", sel)
            return
        except Exception:
            continue
