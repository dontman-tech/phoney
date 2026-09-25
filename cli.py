#!/usr/bin/env python3
"""phoney — CLI for the Phoney daemon.

    phoney daemon                run the background daemon
    phoney list                  list discovered devices
    phoney pair <device>         send/accept a pairing request
    phoney unpair <device>       remove pairing
    phoney send <device> <file>  send a file to the phone
    phoney clip [device]         push clipboard to phone(s)
"""
from __future__ import annotations

import argparse
import sys

from phoney.daemon import Daemon


def main() -> int:
    ap = argparse.ArgumentParser(prog="phoney", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("daemon")
    sub.add_parser("list")
    p = sub.add_parser("pair"); p.add_argument("device")
    p = sub.add_parser("unpair"); p.add_argument("device")
    p = sub.add_parser("send"); p.add_argument("device"); p.add_argument("file")
    p = sub.add_parser("clip"); p.add_argument("device", nargs="?")
    p = sub.add_parser("send-notification"); p.add_argument("device")
    p.add_argument("title"); p.add_argument("body", nargs="?", default="")

    args = ap.parse_args()

    if args.cmd == "daemon":
        d = Daemon()
        d.start()
        print("Phoney daemon running. Press Ctrl-C to stop.")
        try:
            import signal
            signal.pause()
        except KeyboardInterrupt:
            pass
        return 0

    # One-shot commands run against a short-lived daemon instance so we still
    # receive the UDP announce from the phone (discovery is passive on our side
    # only for a few seconds).
    d = Daemon()
    d.transport._broadcast_identity()
    import time
    time.sleep(1.5)

    if args.cmd == "list":
        devs = d.devices()
        if not devs:
            print("No devices found. Make sure KDE Connect is open on your "
                  "phone and both are on the same Wi-Fi.")
            return 1
        for dev in devs:
            state = "paired" if dev.paired else "not paired"
            print(f"{dev.name:30s} {dev.id}  ({state})")
        return 0

    try:
        if args.cmd == "pair":
            dev = d.pair(args.device)
            if dev.paired:
                print(f"Paired with {dev.name}.")
                return 0
            print("Pairing request sent — confirm on your phone if asked.")
            return 0 if dev.paired else 2
        if args.cmd == "unpair":
            d.unpair(args.device)
            print(f"Unpaired {args.device}.")
            return 0
        if args.cmd == "send":
            d.send_file(args.device, args.file)
            print("Transfer started.")
            return 0
        if args.cmd == "clip":
            d.push_clipboard(args.device)
            print("Clipboard pushed.")
            return 0
        if args.cmd == "send-notification":
            from phoney.packets import packet
            dev = d._find(args.device)
            dev.send(packet("kdeconnect.notification",
                            body={"id": f"phoney-cli-{time.time()}",
                                  "title": args.title, "text": args.body,
                                  "appName": "Phoney"}))
            return 0
    except (LookupError, ConnectionError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
