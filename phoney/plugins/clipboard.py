"""Clipboard sync — mirrors your phone's clipboard on Linux and vice versa."""
from __future__ import annotations

import logging
import subprocess

from ..packets import packet

log = logging.getLogger(__name__)


class Clipboard:
    CAPABILITY = "kdeconnect.clipboard"

    def __init__(self, get_clipboard, set_clipboard):
        self.get_clipboard = get_clipboard
        self.set_clipboard = set_clipboard

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        if "content" in body:
            content = body["content"]
            log.debug("Clipboard from phone: %r", content[:80])
            try:
                self.set_clipboard(content)
            except Exception as e:
                log.error("Could not set clipboard: %s", e)

    def push(self, device) -> None:
        """Send our clipboard to the phone."""
        try:
            content = self.get_clipboard()
        except Exception as e:
            log.debug("No clipboard available: %s", e)
            return
        if content:
            try:
                device.send(packet("kdeconnect.clipboard",
                                    body={"content": content}))
            except ConnectionError as e:
                log.error("Clipboard push failed: %s", e)


def make_x11_clipboard() -> Clipboard:
    """Clipboard backend via xclip / wl-copy-paste (X11 or Wayland)."""
    def get() -> str | None:
        for argv in (["wl-paste", "-n"], ["xclip", "-selection", "clipboard", "-o"]):
            try:
                r = subprocess.run(argv, capture_output=True, timeout=5)
                if r.returncode == 0:
                    return r.stdout.decode("utf-8", "replace")
            except FileNotFoundError:
                continue
        return None

    def set(content: str) -> None:
        done = False
        for argv in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
            try:
                subprocess.run(argv, input=content.encode(), timeout=5,
                               check=True)
                done = True
                break
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        if not done:
            raise RuntimeError("no clipboard tool (install xclip or wl-clipboard)")

    return Clipboard(get, set)
