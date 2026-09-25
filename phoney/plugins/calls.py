"""Calls plugin — incoming-call alerts on the desktop, mute/answer hooks."""
from __future__ import annotations

import logging

from ..packets import packet

log = logging.getLogger(__name__)


class Calls:
    CAPABILITY = "kdeconnect.telephony"
    # v2 capability: "kdeconnect.call" — accept both.

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        t = pkt.get("type", "")
        if t == self.CAPABILITY:
            state = body.get("state") or body.get("event")
            number = body.get("phoneNumber") or body.get("contactName") or "unknown"
            if state in ("ringing", "0"):
                self._alert(device, number)
            elif state in ("missed_call",):
                log.info("Missed call from %s (%s)", number, device.name)
        elif "isCancel" in body:
            log.info("Call cancelled on %s", device.name)

    def _alert(self, device, number: str) -> None:
        import subprocess
        title = f"Incoming call — {number}"
        log.info(title)
        for argv in (["notify-send", "-a", "Phoney", "-u", "critical", title,
                      device.name],
                     ["notify-send", title, device.name]):
            try:
                subprocess.run(argv, timeout=5,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue


class CallsSource:
    """Desktop-initiated: silence an incoming call."""
    CAPABILITY = Calls.CAPABILITY

    @staticmethod
    def mute(device) -> None:
        device.send(packet("kdeconnect.telephony", body={"action": "mute"}))
