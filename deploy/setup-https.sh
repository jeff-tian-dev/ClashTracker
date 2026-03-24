#!/usr/bin/env bash
#
# Enable HTTPS on the Oracle VM using Caddy + Let's Encrypt.
# Run this AFTER you have a domain pointing to your VM's public IP.
#
# Usage:  bash deploy/setup-https.sh YOUR_API_DOMAIN
# Example: bash deploy/setup-https.sh clashtracker-api.duckdns.org
#
# Use a hostname that points at THIS VM (API only). The public React app should be on
# GitHub Pages with a different hostname (e.g. clashtracker.duckdns.org → GitHub).
#
# Prerequisites:
#   1. Create a DuckDNS subdomain for the API, e.g. clashtracker-api.duckdns.org → your VM IP
#   2. Point that hostname to your VM's public IP (DuckDNS "current ip")
#   3. Open ports 80 and 443 in Oracle Cloud Security List (VCN -> Security Lists -> Ingress)
#
set -euo pipefail

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ]; then
    echo "Usage: bash deploy/setup-https.sh YOUR_DOMAIN"
    echo "Example: bash deploy/setup-https.sh clashtracker-api.duckdns.org"
    exit 1
fi

PROJECT_DIR="/home/ubuntu/clash-tracker"

echo "=== Enabling HTTPS for $DOMAIN ==="

# ---------- Install Caddy ----------
echo "[1/4] Installing Caddy..."
sudo apt-get update -qq
sudo apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --batch --no-tty --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update -qq
sudo apt-get install -y -qq caddy

# ---------- Configure Caddyfile ----------
echo "[2/4] Configuring Caddy..."
sudo tee /etc/caddy/Caddyfile > /dev/null <<CADDY
$DOMAIN {
    reverse_proxy localhost:8000
}
CADDY

# ---------- Open ports 80 and 443 ----------
echo "[3/4] Opening ports 80 and 443..."
for PORT in 80 443; do
    sudo iptables -D INPUT -m state --state NEW -p tcp --dport $PORT -j ACCEPT 2>/dev/null || true
    REJECT_LINE=$(sudo iptables -L INPUT --line-numbers -n | grep -i reject | head -1 | awk '{print $1}')
    if [ -n "$REJECT_LINE" ]; then
        sudo iptables -I INPUT "$REJECT_LINE" -m state --state NEW -p tcp --dport $PORT -j ACCEPT
    else
        sudo iptables -A INPUT -m state --state NEW -p tcp --dport $PORT -j ACCEPT
    fi
done
sudo netfilter-persistent save 2>/dev/null || true

# ---------- Start Caddy ----------
echo "[4/4] Starting Caddy..."
sudo systemctl enable --now caddy
sudo systemctl restart caddy

echo ""
echo "=== HTTPS setup complete ==="
echo "  API (HTTPS): https://$DOMAIN"
echo "  Health:      https://$DOMAIN/health"
echo ""
echo "Set GitHub Actions / Vite VITE_API_URL to: https://$DOMAIN"
echo "Rebuild GitHub Pages after DNS for the Pages domain points to GitHub (not this VM)."
echo ""
