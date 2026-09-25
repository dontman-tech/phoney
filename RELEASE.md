# Phoney v0.1.0 — release notes

First tagged release of Phoney, the Linux Phone Link / Link-to-Windows
equivalent built on the KDE Connect protocol.

## Highlights
- Pairing with the stock KDE Connect Android app (no custom APK needed)
- Notifications, file transfer, clipboard sync
- Battery status, remote mouse/keyboard, media control, find-my-phone
- SMS read/send, incoming-call alerts with mute
- Screen mirroring via scrcpy integration
- Local web dashboard (http://127.0.0.1:3000/phoney) + full CLI

## Install
```bash
git clone https://github.com/dontman-tech/phoney.git
cd phoney && ./install.sh
phoney daemon    # dashboard opens at http://127.0.0.1:3000/phoney
```

## Known limitations
- Real-device verification pending (loopback-tested so far)
- Desktop plugins assume an X11 session (xclip/xdotool); Wayland support not yet validated
