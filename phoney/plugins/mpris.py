"""MprisControl plugin — remote media control in both directions."""
from __future__ import annotations

import json
import logging
import subprocess
import threading

from ..packets import packet

log = logging.getLogger(__name__)


class MprisControl:
    """Receives kdeconnect.mpris packets: phone's play/pause/next drives the
    desktop's active player via playerctl, and reports player state back."""
    CAPABILITY = "kdeconnect.mpris"

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        cmd = body.get("command")
        if cmd:
            argv = {"Play": ["play"], "Pause": ["pause"],
                    "PlayPause": ["play-pause"], "Stop": ["stop"],
                    "Next": ["next"], "Previous": ["previous"]}.get(cmd)
            if argv:
                try:
                    subprocess.run(["playerctl", *argv], timeout=3,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except FileNotFoundError:
                    log.info("playerctl not installed; media control unavailable")
            self._report(device)

    def _report(self, device) -> None:
        try:
            out = subprocess.run(["playerctl", "status"], timeout=3, text=True,
                                 capture_output=True).stdout.strip()
            meta = subprocess.run(["playerctl", "metadata", "--format",
                                   "{{title}}|{{artist}}|{{album}}"],
                                  timeout=3, text=True, capture_output=True).stdout.strip()
            title, artist, album = (meta.split("|") + ["", "", ""])[:3]
        except (FileNotFoundError, subprocess.SubprocessError):
            out, title, artist = "", "", ""
        try:
            device.send(packet(self.CAPABILITY, body={
                "type": "status", "player": "playerctl",
                "isPlaying": out == "Playing",
                "title": title, "artist": artist, "nowPlaying": title,
            }))
        except Exception:
            pass

    def refresh(self, device) -> None:
        self._report(device)


class MprisSource:
    """Drive a phone's media player from the desktop (pause your phone)."""
    CAPABILITY = "kdeconnect.mpris"

    @staticmethod
    def command(device, cmd: str) -> None:
        device.send(packet("kdeconnect.mpris", body={"command": cmd}))
