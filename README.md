# FundaLand

Telegram bot that monitors [fundainbusiness.nl](https://www.fundainbusiness.nl) for new agricultural land and agricultural business listings in the Netherlands. Sends instant notifications when new listings appear and supports interactive search with filters.

## Features

- **Real-time monitoring** — scrapes fundainbusiness.nl every 30 minutes and sends new listings to Telegram instantly
- **Two categories tracked:**
  - 🌾 Agrarische Grond (Agricultural Land)
  - 🚜 Agrarisch Bedrijf (Agricultural Businesses)
- **Interactive Telegram bot** with search and filter commands
- **Filter by criteria:** price range, plot area, listing age
- **CAPTCHA bypass** using [undetected-chromedriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver) — fundainbusiness.nl uses Google reCAPTCHA which blocks headless browsers
- **SQLite database** to track seen listings and avoid duplicate notifications
- **Numeric parsing** for Dutch price formats (`€ 150.000 k.k.`) and area formats (`2 ha 30 a`, `5.000 m²`)
- **VPS-ready** with systemd services, xvfb virtual display, and deploy scripts

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/help` | Show all commands |
| `/search` | Search listings using current filters |
| `/filter` | Show active filters |
| `/price <min> [max]` | Set price filter in EUR (e.g. `/price 100000 500000`) |
| `/area <min> [max]` | Set area filter in m² (e.g. `/area 10000 50000`) |
| `/days <n>` | Only show listings from the last N days (e.g. `/days 7`) |
| `/clear` | Remove all filters |
| `/latest` | Show 5 most recent listings |
| `/stats` | Database statistics |

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
│  fundainbusiness │────▶│   scraper.py │────▶│  listings.db │
│       .nl       │     │  (selenium)  │     │   (SQLite)   │
└─────────────────┘     └──────┬───────┘     └──────┬───────┘
                               │                     │
                               ▼                     ▼
                        ┌──────────────┐     ┌──────────────┐
                        │  notifier.py │     │    bot.py    │
                        │ (new alerts) │     │  (commands)  │
                        └──────┬───────┘     └──────┬───────┘
                               │                     │
                               ▼                     ▼
                        ┌──────────────────────────────────┐
                        │        Telegram Bot API          │
                        └──────────────────────────────────┘
```

### File Overview

| File | Purpose |
|------|---------|
| `main.py` | Scraper entry point — scrapes, detects new listings, sends notifications |
| `bot.py` | Telegram bot — listens for commands, handles search/filter |
| `scraper.py` | Web scraper using undetected-chromedriver + Selenium |
| `database.py` | SQLite operations, filter management, numeric parsing |
| `notifier.py` | Telegram message formatting and sending |
| `config.py` | Configuration (categories, URLs, settings) |
| `deploy.sh` | One-command deploy to VPS |
| `deploy/install.sh` | VPS system dependencies (Chrome, xvfb) |
| `deploy/setup_services.sh` | systemd service creation |

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
# Clone the repo
git clone https://github.com/maxoon-netizen/FundaLand.git
cd FundaLand

# Create virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

# First run: saves existing listings without sending notifications
source .env && export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
python main.py --init

# Start the Telegram bot (interactive commands)
python bot.py

# Run the scraper manually
python main.py
```

### VPS Deployment (Ubuntu)

The project includes a complete deploy pipeline for running on a VPS with systemd.

```bash
# 1. Deploy files to VPS
./deploy.sh

# 2. SSH into VPS
ssh user@your-vps-ip

# 3. Install Chrome and xvfb (one time)
sudo bash /home/deploy/fundaland/deploy/install.sh

# 4. Initialize database (saves existing listings, no notifications)
Xvfb :99 -screen 0 1280x900x24 &
export DISPLAY=:99
cd /home/deploy/fundaland
source venv/bin/activate && source .env && export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
python main.py --init

# 5. Set up and start systemd services
sudo bash /home/deploy/fundaland/deploy/setup_services.sh
sudo systemctl start fundaland-bot
sudo systemctl start fundaland-scraper.timer
```

### systemd Services

| Service | Type | Purpose |
|---------|------|---------|
| `xvfb.service` | always-on | Virtual display for Chrome |
| `fundaland-bot.service` | always-on | Telegram bot (listens for commands) |
| `fundaland-scraper.service` | oneshot | Scraper (triggered by timer) |
| `fundaland-scraper.timer` | timer | Runs scraper every 30 minutes |

**Useful commands:**
```bash
# Check bot status
sudo systemctl status fundaland-bot

# View bot logs
sudo journalctl -u fundaland-bot -f

# View scraper logs
sudo journalctl -u fundaland-scraper -f

# Check next scraper run
sudo systemctl list-timers fundaland-scraper.timer

# Restart bot after code changes
sudo systemctl restart fundaland-bot
```

## How It Works

### CAPTCHA Bypass

fundainbusiness.nl uses Google reCAPTCHA v2 to block automated access. Headless browsers (Playwright, Selenium headless mode) are always blocked. The solution:

- **undetected-chromedriver** — a patched ChromeDriver that evades bot detection
- **Non-headless mode** — Chrome runs in visible mode, but on a virtual framebuffer (`xvfb`) on the server so no physical display is needed
- **Auto version detection** — the scraper detects the installed Chrome version and downloads the matching ChromeDriver

### Scraping Flow

1. Opens Chrome via undetected-chromedriver
2. Navigates to each category page (agricultural land + businesses)
3. Paginates through up to 10 pages per category (15 listings/page)
4. Extracts: title, location, price, area, image URL, listing URL
5. Compares against SQLite database to find new listings
6. Parses Dutch price/area formats into numeric values for filtering
7. Sends new listings via Telegram (respecting user's filters)

### Notification Format

Each new listing notification includes:
- Category emoji and name
- Street name and address
- City/postal code
- Price (or "Prijs op aanvraag")
- Area/features
- Direct link to the listing on funda

## Configuration

Edit `config.py` to customize:

```python
# Categories to monitor
CATEGORIES = [
    {"name": "Agrarische Grond", "url": "https://www.fundainbusiness.nl/agrarische-grond/heel-nederland/", "emoji": "🌾"},
    {"name": "Agrarisch Bedrijf", "url": "https://www.fundainbusiness.nl/agrarisch-bedrijf/heel-nederland/", "emoji": "🚜"},
]

# Pages per category (15 listings/page)
MAX_PAGES = 10

# Browser mode (must be False for CAPTCHA bypass)
HEADLESS = False
```

To change the scraping interval, edit the systemd timer:
```bash
sudo systemctl edit fundaland-scraper.timer
# Change OnUnitActiveSec=30min to your preferred interval
```

## License

MIT
