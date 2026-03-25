#!/bin/bash
# Run FundaLand scraper (for use with cron)
cd /Users/maksim/Documents/FundaLand
source venv/bin/activate
source .env
export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
python main.py >> fundaland.log 2>&1
