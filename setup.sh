#!/bin/bash
# FundaLand setup script

set -e

echo "=== FundaLand Setup ==="

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Installing Playwright browsers..."
playwright install chromium

# Check for .env file
if [ ! -f ".env" ]; then
    echo ""
    echo "=== IMPORTANT: Configure your Telegram bot ==="
    echo ""
    echo "1. Open Telegram and message @BotFather"
    echo "2. Send /newbot and follow the steps to create a bot"
    echo "3. Copy the bot token"
    echo ""
    echo "4. To get your Chat ID:"
    echo "   - Message your new bot (send anything)"
    echo "   - Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
    echo "   - Find your chat ID in the response"
    echo ""
    read -p "Enter your Telegram Bot Token: " bot_token
    read -p "Enter your Telegram Chat ID: " chat_id
    echo "TELEGRAM_BOT_TOKEN=${bot_token}" > .env
    echo "TELEGRAM_CHAT_ID=${chat_id}" >> .env
    echo "Saved to .env"
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Usage:"
echo "  source venv/bin/activate"
echo "  source .env && export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID"
echo ""
echo "  # First run (visible browser to solve CAPTCHA, saves listings without notifying):"
echo "  python main.py --init --headful"
echo ""
echo "  # Normal run:"
echo "  python main.py"
echo ""
echo "  # Set up cron job (every 30 min):"
echo "  crontab -e"
echo "  */30 * * * * cd $(pwd) && source venv/bin/activate && source .env && export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID && python main.py >> fundaland.log 2>&1"
