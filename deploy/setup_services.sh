#!/bin/bash
# Set up systemd services for FundaLand
# Run as: sudo bash setup_services.sh

set -e

PROJECT_DIR="/home/deploy/fundaland"
USER="deploy"

echo "=== Setting up FundaLand services ==="

# Create the bot service (runs continuously for Telegram commands)
cat > /etc/systemd/system/fundaland-bot.service << EOF
[Unit]
Description=FundaLand Telegram Bot
After=network.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create the scraper service (runs periodically)
cat > /etc/systemd/system/fundaland-scraper.service << EOF
[Unit]
Description=FundaLand Scraper
After=network.target

[Service]
Type=oneshot
User=${USER}
WorkingDirectory=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
Environment=DISPLAY=:99
ExecStartPre=/usr/bin/bash -c 'Xvfb :99 -screen 0 1280x900x24 &'
ExecStart=${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/main.py
ExecStopPost=/usr/bin/bash -c 'pkill -f "Xvfb :99" || true'
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOF

# Create the scraper timer (every 30 min)
cat > /etc/systemd/system/fundaland-scraper.timer << EOF
[Unit]
Description=Run FundaLand scraper every 30 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=30min
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Reload and enable
systemctl daemon-reload
systemctl enable fundaland-bot.service
systemctl enable fundaland-scraper.timer

echo ""
echo "=== Services created ==="
echo "Start bot:     sudo systemctl start fundaland-bot"
echo "Start timer:   sudo systemctl start fundaland-scraper.timer"
echo "Check bot:     sudo systemctl status fundaland-bot"
echo "Check timer:   sudo systemctl list-timers fundaland-scraper.timer"
echo "Bot logs:      sudo journalctl -u fundaland-bot -f"
echo "Scraper logs:  sudo journalctl -u fundaland-scraper -f"
