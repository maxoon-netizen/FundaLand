#!/bin/bash
# Deploy FundaLand to VPS
set -e

VPS_HOST="65.108.157.57"
VPS_USER="deploy"
VPS_KEY="$HOME/.ssh/vps_65_108_157_57_key"
REMOTE_DIR="/home/deploy/fundaland"

SSH_CMD="ssh -i $VPS_KEY $VPS_USER@$VPS_HOST"
SCP_CMD="scp -i $VPS_KEY"

echo "=== Deploying FundaLand to VPS ==="

# Create remote directory
$SSH_CMD "mkdir -p $REMOTE_DIR/deploy"

# Copy project files
echo "Uploading files..."
$SCP_CMD config.py database.py scraper.py notifier.py bot.py main.py requirements.txt .env \
    $VPS_USER@$VPS_HOST:$REMOTE_DIR/

$SCP_CMD deploy/install.sh deploy/setup_services.sh \
    $VPS_USER@$VPS_HOST:$REMOTE_DIR/deploy/

# Set up venv and install deps on VPS
echo "Setting up Python environment..."
$SSH_CMD << 'REMOTE_SCRIPT'
cd /home/deploy/fundaland

# Create venv if needed
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Python dependencies installed ==="
REMOTE_SCRIPT

echo ""
echo "=== Files deployed! ==="
echo ""
echo "Now SSH into VPS and run:"
echo "  ssh -i $VPS_KEY $VPS_USER@$VPS_HOST"
echo ""
echo "  # 1. Install Chrome + xvfb (one time):"
echo "  sudo bash /home/deploy/fundaland/deploy/install.sh"
echo ""
echo "  # 2. Init scraper (first run, saves existing listings):"
echo "  cd /home/deploy/fundaland && source venv/bin/activate && source .env && export TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID"
echo "  Xvfb :99 -screen 0 1280x900x24 & export DISPLAY=:99"
echo "  python main.py --init"
echo ""
echo "  # 3. Set up services:"
echo "  sudo bash /home/deploy/fundaland/deploy/setup_services.sh"
echo "  sudo systemctl start fundaland-bot"
echo "  sudo systemctl start fundaland-scraper.timer"
