#!/usr/bin/env bash
#
# Run this ON the Oracle VM after files have been copied to /home/ubuntu/clash-tracker.
# Usage:  bash /home/ubuntu/clash-tracker/deploy/setup-vm.sh
#
# Idempotent / fast re-runs: skips apt when OS packages are present, skips pip when
# requirements*.txt hashes match the last install (see venv/.requirements.sha256).
#
set -euo pipefail

PROJECT_DIR="/home/ubuntu/clash-tracker"
VENV_DIR="$PROJECT_DIR/venv"
HASH_FILE="$VENV_DIR/.requirements.sha256"

echo "=== Clash Tracker VM Setup ==="

# ---------- System packages (only when missing) ----------
echo "[1/5] System packages..."
_needs_apt=false
if ! dpkg -s python3 >/dev/null 2>&1; then _needs_apt=true; fi
if ! dpkg -s python3-venv >/dev/null 2>&1; then _needs_apt=true; fi
if ! dpkg -s python3-pip >/dev/null 2>&1; then _needs_apt=true; fi
if [ "$_needs_apt" = true ]; then
    echo "    Installing python3, venv, pip (first run or package missing)..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-venv python3-pip
else
    echo "    Skipped (already installed)."
fi

# ---------- Python venv ----------
echo "[2/5] Python virtual environment..."
if [ ! -x "$VENV_DIR/bin/pip" ]; then
    echo "    Creating venv at $VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
    rm -f "$HASH_FILE"
else
    echo "    Skipped (venv exists)."
fi

# ---------- Python dependencies (only when requirements changed) ----------
API_REQ="$PROJECT_DIR/apps/api/requirements.txt"
ING_REQ="$PROJECT_DIR/apps/ingestion/requirements.txt"
if [ ! -f "$API_REQ" ] || [ ! -f "$ING_REQ" ]; then
    echo "ERROR: Missing $API_REQ or $ING_REQ" >&2
    exit 1
fi

REQ_HASH=$(cat "$API_REQ" "$ING_REQ" | sha256sum | awk '{print $1}')

echo "[3/5] Python dependencies..."
if [ -f "$HASH_FILE" ] && [ "$(cat "$HASH_FILE")" = "$REQ_HASH" ]; then
    echo "    Skipped (requirements unchanged)."
else
    echo "    Installing / upgrading packages..."
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -q \
        -r "$API_REQ" \
        -r "$ING_REQ"
    echo "$REQ_HASH" >"$HASH_FILE"
fi

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
