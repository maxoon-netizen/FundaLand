from __future__ import annotations

import logging
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from browser import create_driver
from config import CATEGORIES, MAX_PAGES

logger = logging.getLogger(__name__)


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
        "source": category.get("source", "fundainbusiness"),
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
    driver = create_driver()

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
