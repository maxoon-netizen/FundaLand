"""Scraper for funda.nl residential listings (detached houses near Amsterdam)."""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import urljoin

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from browser import create_driver, dismiss_cookie_wall
from config import FUNDA_CATEGORY, FUNDA_MAX_PAGES

logger = logging.getLogger(__name__)

BASE = "https://www.funda.nl"
ID_RE = re.compile(r"/(\d+)/?$")


def _build_page_url(base_url: str, page_num: int) -> str:
    """funda paginates with &page=N (page=1 is the first page)."""
    if page_num <= 1:
        return base_url
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}page={page_num}"


def _wait_for_results(driver) -> bool:
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'a[href*="/detail/koop/"]')
            )
        )
        return True
    except Exception:
        return False


def _extract_listings_from_page(driver) -> list[dict]:
    """Pull listing dicts from the current funda search-results page."""
    # Each card root is the immediate parent <div> of an `<a href="/detail/koop/.../huis-...">`.
    # Multiple anchors per card share the same listing id, so we dedupe by id.
    anchors = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/detail/koop/"]')
    cards: dict[str, object] = {}
    for a in anchors:
        href = a.get_attribute("href") or ""
        if "/huis-" not in href:
            continue
        m = ID_RE.search(href.split("?")[0])
        if not m:
            continue
        listing_id = m.group(1)
        if listing_id in cards:
            continue
        # Walk up to the card root: the smallest ancestor <div> wrapping this listing only.
        try:
            card_root = a.find_element(By.XPATH, "./ancestor::div[1]")
        except Exception:
            continue
        cards[listing_id] = (card_root, href)

    listings = []
    for listing_id, (root, href) in cards.items():
        try:
            listing = _parse_card(root, href, listing_id)
            if listing:
                listings.append(listing)
        except Exception as e:
            logger.debug("failed to parse funda card %s: %s", listing_id, e)
    return listings


def _safe_text(el, css: str) -> str:
    try:
        return el.find_element(By.CSS_SELECTOR, css).text.strip()
    except Exception:
        return ""


def _parse_card(root, href: str, listing_id: str) -> dict | None:
    url = urljoin(BASE, href.split("?")[0])

    # Title — the H2 holds "Street Number\n1234 AB City"; we take the street line
    raw_title = _safe_text(root, "h2")
    title = raw_title.split("\n")[0].strip() if raw_title else ""

    # Subtitle — postcode + city (e.g. "1704 DM Heerhugowaard")
    location = _safe_text(root, "div.truncate.text-neutral-80") or _safe_text(root, "div.truncate")

    # Price — find the first element whose text starts with '€'.
    # We can't rely on a class because `font-semibold` is reused on the title row too.
    price = ""
    try:
        price_el = root.find_element(
            By.XPATH,
            ".//*[starts-with(normalize-space(text()), '€')][1]",
        )
        price = price_el.text.strip().split("\n")[0]
    except Exception:
        pass

    # Specs row — <div class="flex gap-3"><span>347 m²</span><span>1.220 m²</span> 13 C</div>
    # Two m^2 values: living area, then plot area. We surface the plot value as `area`
    # because that's what the user filters on.
    area = ""
    living = ""
    try:
        specs_el = root.find_element(By.CSS_SELECTOR, "div.flex.gap-3")
        m2_spans = [
            s.text.strip()
            for s in specs_el.find_elements(By.CSS_SELECTOR, "span")
            if "m" in s.text
        ]
        if len(m2_spans) >= 2:
            living, area = m2_spans[0], m2_spans[1]
        elif m2_spans:
            area = m2_spans[0]
    except Exception:
        pass

    # Image
    image_url = ""
    try:
        img_el = root.find_element(By.CSS_SELECTOR, "img[alt*='main image']")
        image_url = img_el.get_attribute("src") or ""
    except Exception:
        try:
            img_el = root.find_element(By.CSS_SELECTOR, "img[src]")
            image_url = img_el.get_attribute("src") or ""
        except Exception:
            pass

    if not (title or price):
        return None

    return {
        "id": listing_id,
        "source": FUNDA_CATEGORY["source"],
        "category": FUNDA_CATEGORY["name"],
        "title": title or "Unknown",
        "url": url,
        "price": price,
        "area": area,  # plot area
        "location": location,
        "image_url": image_url,
        "extra_living_area": living,  # not stored, but useful for debug
    }


def scrape_funda_sync() -> list[dict]:
    """Scrape all configured funda.nl pages and return listings."""
    base_url = FUNDA_CATEGORY["url"]
    all_listings: list[dict] = []
    driver = create_driver()

    try:
        for page_num in range(1, FUNDA_MAX_PAGES + 1):
            url = _build_page_url(base_url, page_num)
            logger.info("Scraping funda page %d: %s", page_num, url)
            try:
                driver.get(url)
                time.sleep(3)
                if page_num == 1:
                    dismiss_cookie_wall(driver)
                if not _wait_for_results(driver):
                    logger.warning("funda: no results detected on page %d", page_num)
                    break
                # Scroll to trigger lazy loaders
                for y in (600, 1400, 2400, 3600, 4800):
                    driver.execute_script(f"window.scrollTo(0, {y});")
                    time.sleep(0.4)

                listings = _extract_listings_from_page(driver)
                if not listings:
                    logger.info("funda: no listings on page %d, stopping", page_num)
                    break
                all_listings.extend(listings)
                logger.info("funda: %d listings on page %d", len(listings), page_num)
            except Exception as e:
                logger.error("funda: error on page %d: %s", page_num, e)
                break
    finally:
        driver.quit()

    # Dedupe by id (funda re-shows top-position listings on multiple pages)
    seen, unique = set(), []
    for listing in all_listings:
        if listing["id"] in seen:
            continue
        seen.add(listing["id"])
        unique.append(listing)

    logger.info("funda: %d unique listings scraped", len(unique))
    return unique
