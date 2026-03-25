from __future__ import annotations

import logging
import re
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import CATEGORIES, HEADLESS, MAX_PAGES

logger = logging.getLogger(__name__)


def _get_chrome_major_version() -> int | None:
    """Detect installed Chrome major version."""
    import subprocess
    for cmd in ["google-chrome --version", "chromium-browser --version",
                "chromium --version", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome --version"]:
        try:
            out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
            match = re.search(r"(\d+)\.", out)
            if match:
                return int(match.group(1))
        except Exception:
            continue
    return None


def _create_driver() -> uc.Chrome:
    """Create an undetected Chrome driver."""
    options = uc.ChromeOptions()
    if HEADLESS:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=nl-NL")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    version = _get_chrome_major_version()
    logger.info("Detected Chrome version: %s", version)
    driver = uc.Chrome(options=options, version_main=version)
    return driver


def _extract_listings_from_page(driver, category: dict) -> list[dict]:
    """Extract listing data from the current page."""
    listings = []

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "li.search-result[data-search-result-listing]")
            )
        )
    except Exception:
        logger.warning("No search results found on page %s", driver.current_url)
        return listings

    items = driver.find_elements(
        By.CSS_SELECTOR, "li.search-result[data-search-result-listing]"
    )

    for item in items:
        try:
            listing = _parse_listing_item(item, driver.current_url, category)
            if listing:
                listings.append(listing)
        except Exception as e:
            logger.debug("Failed to parse listing item: %s", e)

    return listings


def _parse_listing_item(item, page_url: str, category: dict) -> dict | None:
    """Parse a single listing element into a dict."""
    # Find the main link with object URL
    try:
        link_el = item.find_element(By.CSS_SELECTOR, "a[data-search-result-item-anchor]")
    except Exception:
        try:
            link_el = item.find_element(By.CSS_SELECTOR, 'a[href*="/object-"]')
        except Exception:
            return None

    href = link_el.get_attribute("href")
    if not href or "/object-" not in href:
        return None

    url = href.split("?")[0]

    id_match = re.search(r"object-(\d+)", url)
    if not id_match:
        return None
    listing_id = id_match.group(1)

    # Title
    title = ""
    try:
        title_el = item.find_element(
            By.CSS_SELECTOR, "h2[data-test-search-result-header-title]"
        )
        title = title_el.text.strip()
    except Exception:
        pass

    # Location (subtitle)
    location = ""
    try:
        loc_el = item.find_element(
            By.CSS_SELECTOR, "h4[data-test-search-result-header-subtitle]"
        )
        location = loc_el.text.strip()
    except Exception:
        pass

    # Price
    price = ""
    try:
        price_el = item.find_element(By.CSS_SELECTOR, ".search-result-price")
        price = price_el.text.strip()
    except Exception:
        pass

    # Area / features
    area = ""
    try:
        kenmerken_el = item.find_element(By.CSS_SELECTOR, ".search-result-kenmerken")
        area = re.sub(r"\s+", " ", kenmerken_el.text.strip())
    except Exception:
        pass

    # Image
    image_url = ""
    try:
        img_el = item.find_element(By.CSS_SELECTOR, ".search-result-image img")
        image_url = img_el.get_attribute("src") or ""
    except Exception:
        try:
            img_el = item.find_element(By.CSS_SELECTOR, "img[src]")
            image_url = img_el.get_attribute("src") or ""
        except Exception:
            pass

    return {
        "id": listing_id,
        "category": category["name"],
        "title": title or "Unknown",
        "url": url,
        "price": price,
        "area": area,
        "location": location,
        "image_url": image_url,
    }


def scrape_category(driver, category: dict) -> list[dict]:
    """Scrape all pages of a category."""
    all_listings = []
    base_url = category["url"]

    for page_num in range(1, MAX_PAGES + 1):
        url = base_url if page_num == 1 else f"{base_url}p{page_num}/"
        logger.info("Scraping %s page %d: %s", category["name"], page_num, url)

        try:
            driver.get(url)
            time.sleep(2)

            listings = _extract_listings_from_page(driver, category)
            if not listings:
                logger.info("No more listings at page %d, stopping.", page_num)
                break

            all_listings.extend(listings)
            logger.info("Found %d listings on page %d", len(listings), page_num)

        except Exception as e:
            logger.error("Error scraping %s page %d: %s", category["name"], page_num, e)
            break

    return all_listings


def scrape_all_sync() -> list[dict]:
    """Scrape all configured categories and return listings."""
    all_listings = []
    driver = _create_driver()

    try:
        for category in CATEGORIES:
            try:
                listings = scrape_category(driver, category)
                all_listings.extend(listings)
            except Exception as e:
                logger.error("Failed to scrape category %s: %s", category["name"], e)
    finally:
        driver.quit()

    # Deduplicate by ID
    seen = set()
    unique = []
    for listing in all_listings:
        if listing["id"] not in seen:
            seen.add(listing["id"])
            unique.append(listing)

    logger.info("Total unique listings scraped: %d", len(unique))
    return unique
