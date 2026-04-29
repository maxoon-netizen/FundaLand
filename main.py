#!/usr/bin/env python3
"""
FundaLand Scraper — scrapes fundainbusiness.nl and sends new listings via Telegram.

Usage:
    python main.py              # Run once (scrape + notify)
    python main.py --init       # First run: save all existing listings without notifying
"""
from __future__ import annotations

import argparse
import asyncio
import logging

import config
from database import (
    init_db,
    get_new_listings,
    save_listing,
    get_filters,
    listing_matches_filters,
    parse_price,
    parse_area,
)
from scraper import scrape_all_sync
from funda_scraper import scrape_funda_sync
from notifier import send_listing, send_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run(init_mode: bool = False):
    """Main run: scrape, find new listings, notify."""
    await init_db()

    logger.info("Starting scrape...")
    fib_listings = scrape_all_sync()
    logger.info("fundainbusiness: %d listings", len(fib_listings))

    funda_listings = scrape_funda_sync()
    logger.info("funda: %d listings", len(funda_listings))

    all_listings = fib_listings + funda_listings
    if not all_listings:
        logger.warning("No listings scraped. Both sites may be blocking us.")
        return

    # Parse numeric values
    for listing in all_listings:
        listing["price_numeric"] = parse_price(listing.get("price", ""))
        listing["area_numeric"] = parse_area(listing.get("area", ""))

    new_listings = await get_new_listings(all_listings)
    logger.info("Found %d new listings", len(new_listings))

    # Save all new listings to the database
    for listing in new_listings:
        await save_listing(listing)

    if init_mode:
        logger.info(
            "Init mode: saved %d listings to database without sending notifications.",
            len(new_listings),
        )
        return

    if not new_listings:
        return

    # Load filters for the configured chat
    chat_id = config.TELEGRAM_CHAT_ID
    filters = await get_filters(chat_id) if chat_id else None

    emoji_map = {cat["name"]: cat["emoji"] for cat in config.CATEGORIES}
    emoji_map[config.FUNDA_CATEGORY["name"]] = config.FUNDA_CATEGORY["emoji"]

    sent = 0
    for listing in new_listings:
        # If filters exist, only send matching listings
        if filters and not listing_matches_filters(listing, filters):
            continue
        emoji = emoji_map.get(listing["category"], "\U0001F3E0")
        await send_listing(listing, emoji, chat_id)
        sent += 1
        await asyncio.sleep(0.5)

    if sent > 0:
        await send_summary(sent, len(all_listings), chat_id)
    logger.info("Sent %d notifications (out of %d new)", sent, len(new_listings))


def main():
    parser = argparse.ArgumentParser(description="FundaLand Scraper")
    parser.add_argument("--init", action="store_true", help="Save existing listings without notifying")
    args = parser.parse_args()

    asyncio.run(run(init_mode=args.init))


if __name__ == "__main__":
    main()
