#!/usr/bin/env bash
#
# Run this ON the Oracle VM after files have been copied to /home/ubuntu/clash-tracker.
# Usage:  bash /home/ubuntu/clash-tracker/deploy/setup-vm.sh
#
set -euo pipefail

PROJECT_DIR="/home/ubuntu/clash-tracker"
VENV_DIR="$PROJECT_DIR/venv"

echo "=== Clash Tracker VM Setup ==="

# ---------- System packages ----------
echo "[1/5] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv python3-pip

# ---------- Python venv ----------
echo "[2/5] Creating Python virtual environment..."
if [ ! -x "$VENV_DIR/bin/pip" ]; then
    python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip -q

echo "[3/5] Installing Python dependencies..."
"$VENV_DIR/bin/pip" install -q \
    -r "$PROJECT_DIR/apps/api/requirements.txt" \
    -r "$PROJECT_DIR/apps/ingestion/requirements.txt"

# ---------- systemd units ----------
echo "[4/5] Installing systemd services..."
sudo cp "$PROJECT_DIR/deploy/clash-tracker-api.service"         /etc/systemd/system/
sudo cp "$PROJECT_DIR/deploy/clash-tracker-ingestion.service"   /etc/systemd/system/
sudo cp "$PROJECT_DIR/deploy/clash-tracker-ingestion.timer"     /etc/systemd/system/

sudo systemctl daemon-reload

sudo systemctl enable --now clash-tracker-api.service
sudo systemctl enable --now clash-tracker-ingestion.timer

# ---------- Firewall (iptables — Oracle Cloud uses iptables by default) ----------
echo "[5/5] Opening port 8000..."
sudo iptables -D INPUT -m state --state NEW -p tcp --dport 8000 -j ACCEPT 2>/dev/null || true
REJECT_LINE=$(sudo iptables -L INPUT --line-numbers -n | grep -i reject | head -1 | awk '{print $1}')
if [ -n "$REJECT_LINE" ]; then
    sudo iptables -I INPUT "$REJECT_LINE" -m state --state NEW -p tcp --dport 8000 -j ACCEPT
else
    sudo iptables -A INPUT -m state --state NEW -p tcp --dport 8000 -j ACCEPT
fi
sudo netfilter-persistent save 2>/dev/null || true

echo ""
echo "=== Setup complete ==="
echo "  API:        http://$(hostname -I | awk '{print $1}'):8000/health"
echo "  Ingestion:  systemctl status clash-tracker-ingestion.timer"
echo ""
echo "Run an immediate ingestion test:"
echo "  sudo systemctl start clash-tracker-ingestion.service"
echo "  journalctl -u clash-tracker-ingestion.service -f"
