from __future__ import annotations

import re
from datetime import datetime, timedelta

import aiosqlite

from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL DEFAULT 'fundainbusiness',
                category TEXT NOT NULL,
                title TEXT,
                url TEXT NOT NULL,
                price TEXT,
                price_numeric REAL,
                area TEXT,
                area_numeric REAL,
                location TEXT,
                image_url TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS filters (
                chat_id TEXT PRIMARY KEY,
                min_price REAL,
                max_price REAL,
                min_area REAL,
                max_area REAL,
                max_days INTEGER
            )
        """)
        # Idempotent migrations for older DBs
        for ddl in (
            "ALTER TABLE listings ADD COLUMN price_numeric REAL",
            "ALTER TABLE listings ADD COLUMN area_numeric REAL",
            "ALTER TABLE listings ADD COLUMN source TEXT NOT NULL DEFAULT 'fundainbusiness'",
        ):
            try:
                await db.execute(ddl)
            except Exception:
                pass
        await db.commit()


def parse_price(price_text: str) -> float | None:
    """Extract numeric price from text like 'EUR 150.000 k.k.' or 'EUR 2.500.000'."""
    if not price_text:
        return None
    text = price_text.lower()
    if "aanvraag" in text or "overleg" in text:
        return None
    # Remove currency symbols and text, keep digits and separators
    cleaned = re.sub(r"[^\d.,]", "", text)
    if not cleaned:
        return None
    # Dutch format: 150.000 or 2.500.000 (dots as thousands)
    # Remove dots (thousands separator), replace comma with dot (decimal)
    cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_area(area_text: str) -> float | None:
    """Extract numeric area in m² from text like '5.000 m²' or '2 ha 30 a'."""
    if not area_text:
        return None
    text = area_text.lower()

    # Try hectares pattern: "2 ha 30 a" or "5 ha"
    ha_match = re.search(r"(\d+[\d.,]*)\s*ha", text)
    a_match = re.search(r"(\d+[\d.,]*)\s*a(?:\s|$|[^a-z])", text)
    ca_match = re.search(r"(\d+[\d.,]*)\s*ca", text)

    if ha_match:
        ha = float(ha_match.group(1).replace(".", "").replace(",", "."))
        total_m2 = ha * 10000
        if a_match:
            total_m2 += float(a_match.group(1).replace(".", "").replace(",", ".")) * 100
        if ca_match:
            total_m2 += float(ca_match.group(1).replace(".", "").replace(",", "."))
        return total_m2

    # Try m² pattern: "5.000 m²" or "5000 m2"
    m2_match = re.search(r"(\d+[\d.,]*)\s*m[²2]", text)
    if m2_match:
        val = m2_match.group(1).replace(".", "").replace(",", ".")
        try:
            return float(val)
        except ValueError:
            pass

    return None


async def listing_exists(listing_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM listings WHERE id = ?", (listing_id,)
        )
        return await cursor.fetchone() is not None


async def save_listing(listing: dict):
    row = {
        "id": listing["id"],
        "source": listing.get("source", "fundainbusiness"),
        "category": listing["category"],
        "title": listing.get("title"),
        "url": listing["url"],
        "price": listing.get("price"),
        "price_numeric": listing.get("price_numeric"),
        "area": listing.get("area"),
        "area_numeric": listing.get("area_numeric"),
        "location": listing.get("location"),
        "image_url": listing.get("image_url"),
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO listings
               (id, source, category, title, url, price, price_numeric, area, area_numeric, location, image_url)
               VALUES (:id, :source, :category, :title, :url, :price, :price_numeric, :area, :area_numeric, :location, :image_url)""",
            row,
        )
        await db.commit()


async def get_new_listings(listings: list[dict]) -> list[dict]:
    """Filter out listings that are already in the database."""
    new = []
    for listing in listings:
        if not await listing_exists(listing["id"]):
            new.append(listing)
    return new


# --- Filter management ---

async def get_filters(chat_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM filters WHERE chat_id = ?", (chat_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
    return None


async def save_filters(chat_id: str, **kwargs):
    """Save or update filters for a chat. Pass min_price, max_price, min_area, max_area, max_days."""
    existing = await get_filters(chat_id)
    if existing:
        sets = []
        vals = []
        for key in ("min_price", "max_price", "min_area", "max_area", "max_days"):
            if key in kwargs:
                sets.append(f"{key} = ?")
                vals.append(kwargs[key])
        if sets:
            vals.append(chat_id)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    f"UPDATE filters SET {', '.join(sets)} WHERE chat_id = ?",
                    vals,
                )
                await db.commit()
    else:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """INSERT INTO filters (chat_id, min_price, max_price, min_area, max_area, max_days)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    chat_id,
                    kwargs.get("min_price"),
                    kwargs.get("max_price"),
                    kwargs.get("min_area"),
                    kwargs.get("max_area"),
                    kwargs.get("max_days"),
                ),
            )
            await db.commit()


async def clear_filters(chat_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM filters WHERE chat_id = ?", (chat_id,))
        await db.commit()


async def search_listings(
    min_price: float | None = None,
    max_price: float | None = None,
    min_area: float | None = None,
    max_area: float | None = None,
    max_days: int | None = None,
    source: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search listings by criteria."""
    conditions = []
    params = []

    if min_price is not None:
        conditions.append("price_numeric >= ?")
        params.append(min_price)
    if max_price is not None:
        conditions.append("price_numeric <= ?")
        params.append(max_price)
    if min_area is not None:
        conditions.append("area_numeric >= ?")
        params.append(min_area)
    if max_area is not None:
        conditions.append("area_numeric <= ?")
        params.append(max_area)
    if max_days is not None:
        cutoff = (datetime.utcnow() - timedelta(days=max_days)).isoformat()
        conditions.append("first_seen >= ?")
        params.append(cutoff)
    if source is not None:
        conditions.append("source = ?")
        params.append(source)

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"SELECT * FROM listings WHERE {where} ORDER BY first_seen DESC LIMIT ?",
            params,
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


def listing_matches_filters(listing: dict, filters: dict) -> bool:
    """Check if a listing matches the given filters."""
    if not filters:
        return True

    price = listing.get("price_numeric")
    area = listing.get("area_numeric")

    if filters.get("min_price") and (price is None or price < filters["min_price"]):
        return False
    if filters.get("max_price") and (price is None or price > filters["max_price"]):
        return False
    if filters.get("min_area") and (area is None or area < filters["min_area"]):
        return False
    if filters.get("max_area") and (area is None or area > filters["max_area"]):
        return False

    return True
