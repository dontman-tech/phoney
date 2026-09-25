"""FindMyPhone plugin — ring the phone from the desktop."""
from __future__ import annotations

import logging
import threading

from ..packets import packet

log = logging.getLogger(__name__)


class FindMyPhone:
    CAPABILITY = "kdeconnect.findmyphone.request"

    def ring(self, device) -> None:
        try:
            device.send(packet(self.CAPABILITY, body={"request": True}))
            log.info("Ring request sent to %s", device.name)
        except Exception:
            pass


class FindMyPhoneSource:
    """Desktop side: a phone asking us to ring rings the local bell/sound."""
    CAPABILITY = FindMyPhone.CAPABILITY

    def __init__(self):
        self._timer: threading.Timer | None = None
        self._count = 0

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        if body.get("request"):
            self._ring_desktop()

    def _ring_desktop(self) -> None:
        import subprocess
        from shutil import which
        for cmd in (
            ["paplay", "--volume=32768", self._alarm()],
            ["canberra-gtk-play", "-i", "phone-incoming-call"],
            ["aplay", self._alarm()],
        ):
            if which(cmd[0]):
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return
                except OSError:
                    continue
        # Fallback: ring the terminal bell for 10 seconds.
        def bell():
            for _ in range(10):
                print("\a", flush=True)
                threading.Event().wait(1)
        threading.Thread(target=bell, daemon=True).start()

    @staticmethod
    def _alarm() -> str:
        from pathlib import Path
        candidates = [
            Path("/usr/share/sounds/freedesktop/stereo/phone-incoming-call.oga"),
            Path("/usr/share/sounds/alsa/Front_Center.wav"),
        ]
        for p in candidates:
            if p.exists():
                return str(p)
        return ""
