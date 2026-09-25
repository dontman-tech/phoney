# Phoney

**Phone Link for Linux.** Pair your Linux desktop with your Android phone for
notifications, file transfer and clipboard sync — over the proven,
end-to-end-paired **KDE Connect protocol**.

## How pairing works

The Android side ships as the stock **KDE Connect** app (Play Store or
F-Droid) — you already trust its pairing flow, so Phoney doesn't ask you to
install an unknown APK. Phoney speaks the same protocol:

1. Discovery: UDP broadcast on port **1716**
2. TLS: both sides present self-signed certificates
3. Pairing: `kdeconnect.pair` packets exchange certificates; the PEM of each
   device you accept is stored in `~/.local/share/phoney/certs/`

## Install

```bash
git clone https://github.com/dontman-tech/phoney.git
cd phoney
./install.sh          # installs python deps + xclip + libnotify
phoney daemon         # or enable packaging/phoney.service as a user unit
```

## Pair your phone

1. Install **KDE Connect** on Android: https://kdeconnect.kde.org/download.html
2. Keep both devices on the same Wi‑Fi/network.
3. On Linux: `phoney list` — your phone appears.
4. `phoney pair <device-name>` and accept on the phone (or accept from the
   phone first — Phoney auto-accepts and records its certificate).
5. `phoney list` should now show *(paired)*.

## Use it

| Command | What it does |
|---|---|
| `phoney list` | show discovered devices |
| `phoney pair <device>` | send/accept pairing |
| `phoney unpair <device>` | remove pairing |
| `phoney send <device> file.pdf` | send a file to the phone |
| `phoney clip [device]` | push your clipboard to the phone(s) |

Receiving works automatically: file transfers land in
`~/.local/share/phoney/Downloads/`, phone notifications pop up via
`notify-send`, and clipboard changes from the phone are applied to your
desktop clipboard (X11 via `xclip`, Wayland via `wl-clipboard`).

## Security notes

Pairing is certificate-based: Phoney stores the exact certificate each device
presented when you paired, and traffic flows over TLS. Unpaired devices can
connect at the TLS layer but their packets are dropped. To revoke a device:
`phoney unpair <device>` deletes its stored certificate.

## What's in v1

- ✅ Phone notifications on the desktop
- ✅ File transfer (both directions)
- ✅ Clipboard sync (both directions)
- 🔜 SMS from the desktop (v1.1)
- 🔜 Mouse/keyboard remote, screen mirroring (v2)

## Architecture

```
phoney/
  packets.py        JSON packet framing + Identity
  transport.py      UDP discovery, TLS TCP, pairing state machine
  daemon.py         device registry + plugin routing
  plugins/
    notifications.py   kdeconnect.notification
    filetransfer.py    kdeconnect.transfer (plain-TCP payload connections)
    clipboard.py       kdeconnect.clipboard
cli.py             command-line interface
```

License: MIT.
