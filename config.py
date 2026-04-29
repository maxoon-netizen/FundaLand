import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent

# Database
DB_PATH = BASE_DIR / "listings.db"

# Telegram
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- fundainbusiness.nl (agricultural) ---
CATEGORIES = [
    {
        "name": "Agrarische Grond",
        "url": "https://www.fundainbusiness.nl/agrarische-grond/heel-nederland/",
        "emoji": "\U0001F33E",
        "source": "fundainbusiness",
    },
    {
        "name": "Agrarisch Bedrijf",
        "url": "https://www.fundainbusiness.nl/agrarisch-bedrijf/heel-nederland/",
        "emoji": "\U0001F69C",
        "source": "fundainbusiness",
    },
]

# Pages per fundainbusiness category (~15 listings/page)
MAX_PAGES = 10

# --- funda.nl (residential) ---
# Detached house, within 50km of Amsterdam, 3+ bedrooms, plot >= 700 m^2, price <= EUR 1,000,000.
FUNDA_CATEGORY = {
    "name": "Vrijstaande woning (Amsterdam +50km)",
    "url": (
        "https://www.funda.nl/zoeken/koop"
        '?selected_area=%5B%22amsterdam%2C50km%22%5D'
        '&object_type=%5B%22house%22%5D'
        '&house_type=%5B%22detached_house%22%5D'
        '&price=%220-1000000%22'
        '&plot_area=%22700-%22'
        '&bedrooms=%223-%22'
        '&sort=%22date_down%22'
    ),
    "emoji": "\U0001F3E1",
    "source": "funda",
}

# Pages per funda search (~15 listings/page)
FUNDA_MAX_PAGES = 5

# Scraping interval in minutes (for reference, actual scheduling done via systemd)
CHECK_INTERVAL_MINUTES = 30

# Browser settings — on VPS with xvfb we run non-headless on a virtual display
HEADLESS = False
