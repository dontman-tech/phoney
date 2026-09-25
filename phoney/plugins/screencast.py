"""Screen mirror via scrcpy — launches scrcpy against a paired phone over ADB.

This is the piece KDE Connect doesn't have. It rides the USB/TCP ADB link
(scrcpy requires adb, and works over Wi-Fi ADB), so it complements the
network pairing rather than duplicating it.
"""
from __future__ import annotations

import logging
import subprocess

from ..packets import packet

log = logging.getLogger(__name__)


class ScreenMirror:
    CAPABILITY = "phoney.screenmirror"

    def __init__(self):
        self._proc: subprocess.Popen | None = None

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        if body.get("request") == "status":
            self._status(device)
        elif body.get("request") == "start":
            self.start(body.get("host"))
        elif body.get("request") == "stop":
            self.stop()

    def _status(self, device) -> None:
        try:
            device.send(packet(self.CAPABILITY, body={
                "running": self._proc is not None and self._proc.poll() is None,
                "available": _has_scrcpy(),
            }))
        except Exception:
            pass

    def start(self, host: str | None = None) -> str:
        """Launch scrcpy against `host` (Wi-Fi ADB) or the default USB device."""
        if not _has_scrcpy():
            return "scrcpy is not installed (apt install scrcpy)"
        if self._proc is not None and self._proc.poll() is None:
            return "already running"
        argv = ["scrcpy", "--max-size", "1024", "--video-codec", "h264"]
        if host:
            argv = ["adb", "connect", host] and [*argv, "--tcpip", host.split(":")[0]]
        self._proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
        log.info("scrcpy started (pid %s)", self._proc.pid)
        return "started"

    def stop(self) -> str:
        if self._proc is None or self._proc.poll() is not None:
            return "not running"
        self._proc.terminate()
        return "stopped"


def _has_scrcpy() -> bool:
    from shutil import which
    return which("scrcpy") is not None
