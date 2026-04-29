# FundaLand

Telegram bot that monitors two Dutch real-estate sites for new listings and sends instant notifications:

- **[fundainbusiness.nl](https://www.fundainbusiness.nl)** — agricultural land and businesses across the Netherlands
- **[funda.nl](https://www.funda.nl)** — detached houses (configurable; defaults to within 50 km of Amsterdam, ≥3 bedrooms, ≥700 m² plot, ≤€1,000,000)

Both feeds flow into the same database and the same Telegram chat. Source-aware browse commands let you slice them apart on demand.

## Features

- **Real-time monitoring** — both sites are scraped every 30 minutes and new listings are pushed to Telegram instantly
- **Three feeds tracked:**
  - 🌾 Agrarische Grond (agricultural land)
  - 🚜 Agrarisch Bedrijf (agricultural businesses)
  - 🏡 Vrijstaande woning (funda detached houses, filtered by URL)
- **Source-aware browse commands** — `/recent`, `/funda`, `/agri`
- **Persistent filters** — price range, plot area, freshness — survive restarts
- **CAPTCHA bypass** using [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) — both sites detect and block headless browsers
- **Toppositie filtering** — funda's sponsored cards (which don't honor the URL filters) are skipped automatically
- **Fortnightly health check** — a separate systemd timer posts a summary to Telegram every 14 days and flags selector drift
- **SQLite database** with a `source` column distinguishing each feed and avoiding duplicate notifications
- **Numeric parsing** for Dutch price formats (`€ 150.000 k.k.`) and area formats (`2 ha 30 a`, `5.000 m²`)
- **VPS-ready** with systemd services, xvfb virtual display, and deploy scripts

## Telegram Commands

### Browse

| Command | Description |
|---------|-------------|
| `/recent [days]` | All listings from last N days, both feeds (default 14) |
| `/funda [days]` | Funda detached houses only, last N days (default 14) |
| `/agri [days]` | Agricultural listings only, last N days (default 14) |
| `/latest` | Show 5 most recent listings |

### Filtered search

| Command | Description |
|---------|-------------|
| `/search` | Search listings using current saved filters (capped at 20 results) |
| `/filter` | Show active filters |
| `/price <min> [max]` | Set price filter in EUR (e.g. `/price 100000 500000`) |
| `/area <min> [max]` | Set area filter in m² (e.g. `/area 700 5000`) |
| `/days <n>` | Persistent freshness filter (e.g. `/days 7`) |
| `/clear` | Remove all filters |

### Other

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show all commands |
| `/stats` | Database statistics |

## Architecture

```
┌──────────────────┐  ┌────────┐
│ fundainbusiness  │  │ funda  │
│       .nl        │  │  .nl   │
└────────┬─────────┘  └────┬───┘
         │                 │
         ▼                 ▼
   ┌──────────┐    ┌──────────────────┐
   │scraper.py│    │ funda_scraper.py │
   └────┬─────┘    └─────────┬────────┘
        │                    │
        └─────────┬──────────┘
                  │  shared:
                  ▼  browser.py (driver factory)
            ┌──────────────┐
            │   main.py    │  parse_price / parse_area
            │  (pipeline)  │
            └───────┬──────┘
                    │
            ┌───────▼──────┐    ┌──────────┐
            │ listings.db  │◀──▶│  bot.py  │
            │   (SQLite,   │    │(commands)│
            │   `source`)  │    └─────┬────┘
            └───────┬──────┘          │
                    │                 │
            ┌───────▼──────┐          │
            │  notifier.py │          │
            └───────┬──────┘          │
                    └─────────┬───────┘
                              ▼
                  ┌──────────────────────┐
                  │  Telegram Bot API    │
                  └──────────────────────┘
```

A separate `health_check.py` runs every 14 days via its own systemd timer and posts a status summary to the same chat — see [Health check](#health-check).

### File Overview

| File | Purpose |
|------|---------|
| `main.py` | Pipeline entry — runs both scrapers, dedupes, notifies |
| `bot.py` | Telegram bot — listens for commands, handles browse/search |
| `scraper.py` | fundainbusiness.nl scraper |
| `funda_scraper.py` | funda.nl scraper (skips sponsored Toppositie cards) |
| `browser.py` | Shared `undetected-chromedriver` factory + cookie-wall dismisser |
| `database.py` | SQLite ops, filter management, numeric parsing, schema migrations |
| `notifier.py` | Telegram message formatting and sending |
| `config.py` | Categories, funda filter URL, settings |
| `health_check.py` | Fortnightly health summary (sent to Telegram) |
| `dump_funda.py` | One-off DOM inspector for re-discovering funda selectors |
| `deploy.sh` | scp deploy to VPS |
| `deploy/install.sh` | VPS system dependencies (Chrome, xvfb) |
| `deploy/setup_services.sh` | systemd unit creation |
| `deploy/fundaland-healthcheck.{service,timer}` | Health-check unit + timer |

## Setup

### Prerequisites

- Python 3.9+
- Google Chrome installed
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- Your Telegram Chat ID

### Getting Your Telegram Chat ID

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → follow the steps → copy the bot token
2. Send any message to your new bot
3. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
4. Find `"chat":{"id": YOUR_CHAT_ID}` in the response

### Local Installation

```bash
git clone https://github.com/maxoon-netizen/FundaLand.git
cd FundaLand

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

source .env && export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID

# First run: scrape both feeds and save without sending notifications
python main.py --init

# Start the Telegram bot
python bot.py

# Run the scraper manually
python main.py
```

### VPS Deployment (Ubuntu)

```bash
# 1. Deploy files
./deploy.sh

# 2. SSH into VPS
ssh user@your-vps-ip

# 3. Install Chrome and xvfb (one time)
sudo bash /home/deploy/fundaland/deploy/install.sh

# 4. Initialize the database (saves existing listings without notifying)
Xvfb :99 -screen 0 1280x900x24 &
export DISPLAY=:99
cd /home/deploy/fundaland
source venv/bin/activate && source .env && export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
python main.py --init

# 5. Set up and start systemd services
sudo bash /home/deploy/fundaland/deploy/setup_services.sh
sudo systemctl start fundaland-bot
sudo systemctl start fundaland-scraper.timer

# 6. Install the health-check timer
sudo cp deploy/fundaland-healthcheck.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fundaland-healthcheck.timer
```

### systemd Services

| Service | Type | Purpose |
|---------|------|---------|
| `xvfb.service` | always-on | Virtual display for Chrome |
| `fundaland-bot.service` | always-on | Telegram bot (listens for commands) |
| `fundaland-scraper.service` | oneshot | Scraper run (triggered by timer) |
| `fundaland-scraper.timer` | timer | Runs scraper every 30 minutes |
| `fundaland-healthcheck.service` | oneshot | Posts health summary to Telegram |
| `fundaland-healthcheck.timer` | timer | Runs health check every 14 days |

**Useful commands:**

```bash
sudo systemctl status fundaland-bot
sudo journalctl -u fundaland-bot -f
sudo journalctl -u fundaland-scraper -f
sudo systemctl list-timers
sudo systemctl restart fundaland-bot       # after code changes
```

## How It Works

### CAPTCHA / bot detection bypass

Both fundainbusiness.nl and funda.nl block headless browsers. The solution:

- **undetected-chromedriver** — a patched ChromeDriver that evades bot detection
- **Non-headless mode** — Chrome runs in visible mode but on a virtual framebuffer (`xvfb`) on the server, so no physical display is needed
- **Auto version detection** (`browser.chrome_major_version`) — finds the installed Chrome major version and pins the matching ChromeDriver

### Scraping flow

`main.py` orchestrates the pipeline:

1. Run `scraper.scrape_all_sync()` for fundainbusiness (10 pages × 2 categories)
2. Run `funda_scraper.scrape_funda_sync()` for funda.nl (5 pages of the filtered search)
3. Parse Dutch price/area strings into numeric columns
4. Insert via `INSERT OR IGNORE` (dedupe by listing id)
5. For each genuinely new listing, push to Telegram with the source-specific emoji

### Funda filter URL

Funda's filters are encoded directly in the URL — no UI clicks needed:

```
https://www.funda.nl/zoeken/koop
  ?selected_area=["amsterdam,50km"]
  &object_type=["house"]
  &house_type=["detached_house"]
  &price="0-1000000"
  &plot_area="700-"
  &bedrooms="3-"
  &sort="date_down"
```

Edit `FUNDA_CATEGORY["url"]` in `config.py` to change criteria.

### Toppositie filtering

Funda injects sponsored "Toppositie" cards at the top of search results. They don't honor the URL filters (apartments and out-of-radius listings can leak through) and they use a different DOM that lacks separate location/area divs. The scraper skips them by checking whether the card's `<h2>` contains a `€` symbol — regular cards have `Street Number\n1234 AB City` in the h2, never the price.

### Notification format

Each new listing notification includes the source emoji, street, city/postcode, price, plot/area, and a direct link.

### Health check

`health_check.py` runs every 14 days (`fundaland-healthcheck.timer`) and posts a Telegram summary covering:

- systemd unit health (`fundaland-bot`, `fundaland-scraper.timer`, `xvfb`)
- last scraper exit code and timestamp
- new listings per source over the last 14 days

If zero new funda listings appeared in the window, the script flags suspected selector drift on funda.nl — that's the early warning that the scraper needs attention. Run `dump_funda.py` to re-inspect the DOM if it fires.

## Configuration

Edit `config.py`:

```python
# fundainbusiness.nl categories
CATEGORIES = [
    {"name": "Agrarische Grond", "url": "...heel-nederland/", "emoji": "🌾", "source": "fundainbusiness"},
    {"name": "Agrarisch Bedrijf", "url": "...heel-nederland/", "emoji": "🚜", "source": "fundainbusiness"},
]
MAX_PAGES = 10

# funda.nl filtered search (URL-encoded filters)
FUNDA_CATEGORY = {
    "name": "Vrijstaande woning (Amsterdam +50km)",
    "url": "https://www.funda.nl/zoeken/koop?...",
    "emoji": "🏡",
    "source": "funda",
}
FUNDA_MAX_PAGES = 5

HEADLESS = False   # must be False for both sites' CAPTCHA bypass
```

Change the scraping interval:

```bash
sudo systemctl edit fundaland-scraper.timer
# Edit OnUnitActiveSec=30min
```

## License

MIT
