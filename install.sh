#!/usr/bin/env bash
# Phoney — one-shot install for the Linux desktop app.
set -euo pipefail

echo "==> Installing system dependencies"
# Core: cryptography (protocol TLS), xclip (clipboard), libnotify (toasts).
# Optional but recommended: xdotool (remote mouse/keyboard), playerctl
# (media control), scrcpy (screen mirroring).
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-pip python3-cryptography xclip libnotify-bin \
    xdotool playerctl scrcpy adb || \
  sudo apt-get install -y python3 python3-pip python3-cryptography xclip libnotify-bin
elif command -v dnf >/dev/null 2>&1; then
  sudo dnf install -y python3-pip python3-cryptography xclip libnotify xdotool playerctl scrcpy android-tools || \
  sudo dnf install -y python3-pip python3-cryptography xclip libnotify
elif command -v pacman >/dev/null 2>&1; then
  sudo pacman -S --noconfirm --needed python python-pip python-cryptography xclip libnotify xdotool playerctl scrcpy android-tools || \
  sudo pacman -S --noconfirm --needed python python-pip python-cryptography xclip libnotify
else
  echo "Unknown package manager — install python3, pip, cryptography, xclip, libnotify manually." >&2
  echo "Optional: xdotool playerctl scrcpy adb" >&2
fi

echo "==> Installing Phoney"
python3 -m pip install --user --break-system-packages . 2>/dev/null \
  || python3 -m pip install --user .

echo "==> Done. Run 'phoney daemon' (dashboard: http://127.0.0.1:3000/phoney)."
echo "    Or install the systemd unit: cp packaging/phoney.service ~/.config/systemd/user/"
