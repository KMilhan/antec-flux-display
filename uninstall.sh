#!/bin/bash
# Uninstall script for Antec Flux Pro Display Service
# Run with: sudo bash uninstall.sh

set -e

echo "=== Antec Flux Pro Display Service Uninstaller ==="

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo bash uninstall.sh)"
    exit 1
fi

echo "[1/4] Stopping service..."
systemctl stop antec-flux-display.service 2>/dev/null || true
systemctl disable antec-flux-display.service 2>/dev/null || true

echo "[2/4] Removing systemd service..."
rm -f /etc/systemd/system/antec-flux-display.service
systemctl daemon-reload

echo "[3/4] Removing udev rule..."
rm -f /etc/udev/rules.d/99-antec-flux-display.rules
udevadm control --reload-rules

echo "[4/4] Removing service files..."
rm -rf /opt/antec-flux-display

echo ""
echo "=== Uninstallation complete ==="
