#!/bin/bash
# FundaLand VPS installation script
# Run as: sudo bash install.sh

set -e

echo "=== FundaLand VPS Setup ==="

# Install Chrome + xvfb (virtual display for non-headless Chrome)
echo "Installing Chrome and dependencies..."
apt-get update
apt-get install -y wget gnupg2 xvfb

# Add Google Chrome repo
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
apt-get update
apt-get install -y google-chrome-stable

echo "Chrome version:"
google-chrome --version

# Install Python venv if needed
apt-get install -y python3-venv python3-pip

echo "=== System dependencies installed ==="
