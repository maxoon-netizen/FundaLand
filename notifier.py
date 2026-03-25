from __future__ import annotations

import logging

import telegram

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

logger = logging.getLogger(__name__)


def _format_message(listing: dict, emoji: str) -> str:
    """Format a listing into a Telegram message."""
    parts = [f"{emoji} <b>New: {listing['category']}</b>"]

    if listing.get("title"):
        parts.append(f"<b>{listing['title']}</b>")
    if listing.get("location"):
        parts.append(f"\U0001F4CD {listing['location']}")
    if listing.get("price"):
        parts.append(f"\U0001F4B0 {listing['price']}")
    if listing.get("area"):
        parts.append(f"\U0001F4D0 {listing['area']}")

    parts.append(f'\n\U0001F517 <a href="{listing["url"]}">View on Funda</a>')

    return "\n".join(parts)


def format_search_result(listing: dict) -> str:
    """Format a listing for search results."""
    parts = []
    if listing.get("title"):
        parts.append(f"<b>{listing['title']}</b>")
    if listing.get("location"):
        parts.append(f"\U0001F4CD {listing['location']}")
    if listing.get("price"):
        parts.append(f"\U0001F4B0 {listing['price']}")
    if listing.get("area"):
        parts.append(f"\U0001F4D0 {listing['area']}")
    parts.append(f'\U0001F517 <a href="{listing["url"]}">Link</a>')
    return "\n".join(parts)


async def send_listing(listing: dict, emoji: str = "\U0001F3E0", chat_id: str | None = None):
    """Send a single listing to Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram bot token not configured!")
        return

    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not target_chat:
        logger.error("Telegram chat ID not configured!")
        return

    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    message = _format_message(listing, emoji)

    try:
        if listing.get("image_url") and listing["image_url"].startswith("http"):
            try:
                await bot.send_photo(
                    chat_id=target_chat,
                    photo=listing["image_url"],
                    caption=message,
                    parse_mode="HTML",
                )
                return
            except Exception:
                pass

        await bot.send_message(
            chat_id=target_chat,
            text=message,
            parse_mode="HTML",
            disable_web_page_preview=False,
        )
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", e)


async def send_summary(total_new: int, total_scraped: int, chat_id: str | None = None):
    """Send a summary message."""
    if not TELEGRAM_BOT_TOKEN:
        return

    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not target_chat:
        return

    bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
    text = f"\u2705 Scan complete: {total_new} new listings found (out of {total_scraped} total)"

    try:
        await bot.send_message(chat_id=target_chat, text=text)
    except Exception as e:
        logger.error("Failed to send summary: %s", e)
