"""Mousepad plugin — remote mouse/keyboard control of the desktop from the phone."""
from __future__ import annotations

import logging

from ..packets import packet

log = logging.getLogger(__name__)


class Mousepad:
    """Receives kdeconnect.mousepad.request packets and injects input via xdotool."""
    CAPABILITY = "kdeconnect.mousepad.request"

    def __init__(self):
        self._tool: str | None = None

    # ------------------------------------------------------------- xdotool
    def _which(self) -> str:
        if self._tool is not None:
            return self._tool
        from shutil import which
        self._tool = which("xdotool") or ""
        return self._tool

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        tool = self._which()
        if not tool:
            log.info("Mousepad request ignored: xdotool not installed")
            return
        import subprocess
        try:
            if "dx" in body or "dy" in body:      # mouse move (relative)
                subprocess.run([tool, "mousemove_relative", "--",
                                str(body.get("dx", 0)), str(body.get("dy", 0))],
                               timeout=3)
            elif "scroll" in body:                 # scroll amount
                amount = body.get("scroll", 0)
                args = (["click", "4"] if amount > 0 else ["click", "5"]) * abs(int(amount))
                subprocess.run([tool, *args], timeout=3)
            elif "key" in body:                    # keyboard keysym / text
                subprocess.run([tool, "key", body["key"]], timeout=3)
            elif "specialKey" in body:             # special key table
                subprocess.run([tool, "key", _SPECIAL.get(str(body["specialKey"]), "")],
                               timeout=3)
            elif "singleclick" in body:
                subprocess.run([tool, "click", "1"], timeout=3)
            elif "middleclick" in body:
                subprocess.run([tool, "click", "2"], timeout=3)
            elif "rightclick" in body:
                subprocess.run([tool, "click", "3"], timeout=3)
            elif "doubleclick" in body:
                subprocess.run([tool, "click", "--repeat", "2", "--delay", "120", "1"],
                               timeout=3)
        except (FileNotFoundError, subprocess.SubprocessError) as e:
            log.debug("xdotool failed: %s", e)

    def ping(self, device) -> None:
        try:
            device.send(packet(self.CAPABILITY, body={"ackKeyboardPing": True}))
        except Exception:
            pass


# KDE Connect protocol special-keys enum (subset).
_SPECIAL = {
    "1": "BackSpace", "2": "Tab", "3": "Return", "5": "Home", "6": "End",
    "9": "Left", "10": "Up", "11": "Right", "12": "Down", "13": "Page_Up",
    "14": "Page_Down", "17": "Delete", "18": "F1", "19": "F2", "20": "F3",
    "21": "F4", "22": "F5", "23": "F6", "24": "F7", "25": "F8", "26": "F9",
    "27": "F10", "28": "F11", "29": "F12",
}


class MousepadSource:
    """Send mousepad packets to a phone app that supports remote input."""
    CAPABILITY = Mousepad.CAPABILITY

    @staticmethod
    def move(device, dx: int, dy: int) -> None:
        device.send(packet(Mousepad.CAPABILITY, body={"dx": dx, "dy": dy}))

    @staticmethod
    def key(device, key: str) -> None:
        device.send(packet(Mousepad.CAPABILITY, body={"key": key}))
