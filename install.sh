#!/bin/bash
# Install script for Antec Flux Pro Display Service
# Run with: sudo bash install.sh

set -e

echo "=== Antec Flux Pro Display Service Installer ==="

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash install.sh)"
    exit 1
fi

# Install Python hidapi dependency
echo "[1/6] Installing python-hidapi..."
pacman -S --noconfirm --needed python-hidapi 2>/dev/null || {
    echo "python-hidapi not in repos, trying pip..."
    pip install hidapi --break-system-packages
}

# Copy the script
echo "[2/6] Installing service script..."
mkdir -p /opt/antec-flux-display
cp antec-flux-display.py /opt/antec-flux-display/
chmod 755 /opt/antec-flux-display/antec-flux-display.py

# Install udev rule
echo "[3/6] Installing udev rule..."
cp 99-antec-flux-display.rules /etc/udev/rules.d/
udevadm control --reload-rules
udevadm trigger

# Install systemd service
echo "[4/6] Installing systemd service..."
cp antec-flux-display.service /etc/systemd/system/
systemctl daemon-reload

# Enable and start
echo "[5/6] Enabling service..."
systemctl enable antec-flux-display.service

echo "[6/6] Starting service..."
systemctl start antec-flux-display.service

echo ""
echo "=== Installation complete ==="
echo ""
echo "Check status:  systemctl status antec-flux-display"
echo "View logs:     journalctl -u antec-flux-display -f"
echo "Stop service:  sudo systemctl stop antec-flux-display"
echo "Uninstall:     sudo bash uninstall.sh"
