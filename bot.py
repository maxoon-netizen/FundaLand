#!/usr/bin/env python3
"""
FundaLand Telegram Bot — interactive commands for searching and filtering listings.

Commands:
    /start              - Welcome message
    /help               - Show help
    /search             - Search with current filters
    /filter             - Show current filters
    /price 100000 500000 - Set price range (EUR)
    /area 10000 50000   - Set area range (m²)
    /days 7             - Only listings from last N days
    /clear              - Clear all filters
    /stats              - Show database statistics
    /latest             - Show 5 most recent listings
"""
from __future__ import annotations

import asyncio
import logging

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes

import config
from database import (
    init_db,
    get_filters,
    save_filters,
    clear_filters,
    search_listings,
    listing_matches_filters,
)
from notifier import format_search_result
import aiosqlite

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "\U0001F33E <b>FundaLand Bot</b>\n\n"
        "I monitor fundainbusiness.nl for agricultural land and businesses.\n"
        "New listings are sent automatically.\n\n"
        "Use /help to see available commands.",
        parse_mode="HTML",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "<b>Commands:</b>\n\n"
        "/search — Search with current filters\n"
        "/filter — Show current filters\n"
        "/price 100000 500000 — Set price range (\u20ac)\n"
        "/area 10000 50000 — Set area range (m\u00b2)\n"
        "/days 7 — Persistent freshness filter\n"
        "/clear — Clear all filters\n\n"
        "<b>Browse</b>\n"
        "/recent [days] — All listings from last N days (default 14)\n"
        "/funda [days] — Funda detached houses, last N days\n"
        "/agri [days] — Agricultural listings, last N days\n"
        "/latest — 5 most recent listings\n\n"
        "<b>Other</b>\n"
        "/stats — Database statistics\n",
        parse_mode="HTML",
    )


async def cmd_filter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    filters = await get_filters(chat_id)

    if not filters or all(v is None for k, v in filters.items() if k != "chat_id"):
        await update.message.reply_text(
            "No filters set. Use /price, /area, or /days to add filters."
        )
        return

    lines = ["\U0001F50D <b>Current filters:</b>\n"]
    if filters.get("min_price") is not None or filters.get("max_price") is not None:
        lo = f"\u20ac{filters['min_price']:,.0f}" if filters.get("min_price") else "any"
        hi = f"\u20ac{filters['max_price']:,.0f}" if filters.get("max_price") else "any"
        lines.append(f"\U0001F4B0 Price: {lo} — {hi}")
    if filters.get("min_area") is not None or filters.get("max_area") is not None:
        lo = f"{filters['min_area']:,.0f} m\u00b2" if filters.get("min_area") else "any"
        hi = f"{filters['max_area']:,.0f} m\u00b2" if filters.get("max_area") else "any"
        lines.append(f"\U0001F4D0 Area: {lo} — {hi}")
    if filters.get("max_days") is not None:
        lines.append(f"\U0001F4C5 Last {filters['max_days']} days")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    args = context.args

    if not args or len(args) < 1:
        await update.message.reply_text(
            "Usage: /price <min> [max]\nExample: /price 100000 500000"
        )
        return

    try:
        min_price = float(args[0])
        max_price = float(args[1]) if len(args) > 1 else None
    except ValueError:
        await update.message.reply_text("Invalid numbers. Example: /price 100000 500000")
        return

    await save_filters(chat_id, min_price=min_price, max_price=max_price)
    msg = f"\u2705 Price filter set: \u20ac{min_price:,.0f}"
    if max_price:
        msg += f" — \u20ac{max_price:,.0f}"
    await update.message.reply_text(msg)


async def cmd_area(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    args = context.args

    if not args or len(args) < 1:
        await update.message.reply_text(
            "Usage: /area <min_m2> [max_m2]\nExample: /area 10000 50000\n"
            "Tip: 1 ha = 10000 m\u00b2"
        )
        return

    try:
        min_area = float(args[0])
        max_area = float(args[1]) if len(args) > 1 else None
    except ValueError:
        await update.message.reply_text("Invalid numbers. Example: /area 10000 50000")
        return

    await save_filters(chat_id, min_area=min_area, max_area=max_area)
    msg = f"\u2705 Area filter set: {min_area:,.0f} m\u00b2"
    if max_area:
        msg += f" — {max_area:,.0f} m\u00b2"
    await update.message.reply_text(msg)


async def cmd_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    args = context.args

    if not args:
        await update.message.reply_text("Usage: /days <number>\nExample: /days 7")
        return

    try:
        max_days = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid number. Example: /days 7")
        return

    await save_filters(chat_id, max_days=max_days)
    await update.message.reply_text(f"\u2705 Showing only listings from last {max_days} days")


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    await clear_filters(chat_id)
    await update.message.reply_text("\u2705 All filters cleared.")


async def _send_paginated(update: Update, results: list, header: str, empty_msg: str):
    """Send a list of listings as one or more Telegram messages, chunked at 4000 chars."""
    if not results:
        await update.message.reply_text(empty_msg)
        return

    current = header
    for r in results:
        entry = "\n" + format_search_result(r) + "\n\u2500\u2500\u2500"
        if len(current + entry) > 4000:
            await update.message.reply_text(current, parse_mode="HTML", disable_web_page_preview=True)
            current = ""
        current += entry
    if current:
        await update.message.reply_text(current, parse_mode="HTML", disable_web_page_preview=True)


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    filters = await get_filters(chat_id)

    kwargs = {}
    if filters:
        for key in ("min_price", "max_price", "min_area", "max_area", "max_days"):
            if filters.get(key) is not None:
                kwargs[key] = filters[key]

    results = await search_listings(**kwargs, limit=20)
    header = f"\U0001F50D Found {len(results)} listing(s):\n"
    await _send_paginated(update, results, header, "No listings match your filters.")


def _parse_days(args, default: int) -> int:
    if not args:
        return default
    try:
        return max(1, int(args[0]))
    except ValueError:
        return default


async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all listings from the last N days, ignoring saved filters. Default 14."""
    days = _parse_days(context.args, 14)
    results = await search_listings(max_days=days, limit=500)
    header = f"\U0001F4C5 <b>Last {days} days</b> \u2014 {len(results)} listing(s):\n"
    await _send_paginated(update, results, header, f"No listings in the last {days} days.")


async def cmd_funda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Funda detached houses from the last N days (default 14)."""
    days = _parse_days(context.args, 14)
    results = await search_listings(max_days=days, source="funda", limit=500)
    header = f"\U0001F3E1 <b>Funda \u00b7 last {days} days</b> \u2014 {len(results)} house(s):\n"
    await _send_paginated(update, results, header, f"No funda listings in the last {days} days.")


async def cmd_agri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fundainbusiness agricultural listings from the last N days (default 14)."""
    days = _parse_days(context.args, 14)
    results = await search_listings(max_days=days, source="fundainbusiness", limit=500)
    header = f"\U0001F33E <b>Agrarisch \u00b7 last {days} days</b> \u2014 {len(results)} listing(s):\n"
    await _send_paginated(update, results, header, f"No agricultural listings in the last {days} days.")


async def cmd_latest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    results = await search_listings(limit=5)

    if not results:
        await update.message.reply_text("No listings in database yet.")
        return

    text = "\U0001F195 <b>Latest 5 listings:</b>\n"
    for r in results:
        text += "\n" + format_search_result(r) + "\n\u2500\u2500\u2500"

    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(config.DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM listings")
        total = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT category, COUNT(*) FROM listings GROUP BY category"
        )
        cats = await cursor.fetchall()

        cursor = await db.execute(
            "SELECT COUNT(*) FROM listings WHERE price_numeric IS NOT NULL"
        )
        with_price = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COUNT(*) FROM listings WHERE area_numeric IS NOT NULL"
        )
        with_area = (await cursor.fetchone())[0]

    lines = [f"\U0001F4CA <b>Database stats:</b>\n", f"Total listings: {total}"]
    for cat, count in cats:
        lines.append(f"  {cat}: {count}")
    lines.append(f"\nWith parsed price: {with_price}")
    lines.append(f"With parsed area: {with_area}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def post_init(app: Application):
    """Set bot commands menu."""
    await app.bot.set_my_commands([
        BotCommand("search", "Search with filters"),
        BotCommand("filter", "Show current filters"),
        BotCommand("price", "Set price range"),
        BotCommand("area", "Set area range (m\u00b2)"),
        BotCommand("days", "Listings from last N days"),
        BotCommand("clear", "Clear all filters"),
        BotCommand("latest", "5 most recent listings"),
        BotCommand("recent", "All listings, last N days (default 14)"),
        BotCommand("funda", "Funda houses, last N days"),
        BotCommand("agri", "Agricultural listings, last N days"),
        BotCommand("stats", "Database statistics"),
        BotCommand("help", "Show help"),
    ])


def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        return

    # Init database synchronously before starting bot
    asyncio.new_event_loop().run_until_complete(init_db())

    app = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("filter", cmd_filter))
    app.add_handler(CommandHandler("price", cmd_price))
    app.add_handler(CommandHandler("area", cmd_area))
    app.add_handler(CommandHandler("days", cmd_days))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("latest", cmd_latest))
    app.add_handler(CommandHandler("recent", cmd_recent))
    app.add_handler(CommandHandler("funda", cmd_funda))
    app.add_handler(CommandHandler("agri", cmd_agri))
    app.add_handler(CommandHandler("stats", cmd_stats))

    logger.info("Bot started, polling for updates...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
