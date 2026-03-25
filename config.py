import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Database
DB_PATH = BASE_DIR / "listings.db"

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Scraping targets
CATEGORIES = [
    {
        "name": "Agrarische Grond",
        "url": "https://www.fundainbusiness.nl/agrarische-grond/heel-nederland/",
        "emoji": "\U0001F33E",
    },
    {
        "name": "Agrarisch Bedrijf",
        "url": "https://www.fundainbusiness.nl/agrarisch-bedrijf/heel-nederland/",
        "emoji": "\U0001F69C",
    },
]

# How many pages to scrape per category (each page ~15 listings)
MAX_PAGES = 10

# Scraping interval in minutes (for reference, actual scheduling done via systemd)
CHECK_INTERVAL_MINUTES = 30

# Browser settings
# On VPS with xvfb, we run non-headless but on a virtual display
HEADLESS = False
