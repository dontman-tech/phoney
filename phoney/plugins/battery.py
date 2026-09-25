"""Battery plugin — phone battery level reported on the desktop (v1 request/reply)."""
from __future__ import annotations

import logging
import threading

from ..packets import packet

log = logging.getLogger(__name__)


class Battery:
    CAPABILITY = "kdeconnect.battery"

    def __init__(self):
        self._levels: dict[str, dict] = {}  # device id -> {level, charging, ts}
        self._lock = threading.Lock()

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        level = body.get("currentCharge")
        if level is None:
            return
        with self._lock:
            self._levels[device.id] = {
                "level": level,
                "charging": bool(body.get("isCharging", False)),
                "threshold": body.get("thresholdEvent", 0),
                "ts": body.get("ts"),
            }
        log.info("Battery %s: %s%% (charging=%s)", device.name, level,
                 body.get("isCharging"))

    def refresh(self, device) -> None:
        """Ask the phone for its current battery state (KDE Connect answers)."""
        try:
            device.send(packet(self.CAPABILITY, body={"request": True}))
        except Exception:
            pass

    def get(self, device_id: str) -> dict | None:
        with self._lock:
            return self._levels.get(device_id)


class BatterySource:
    """Desktop-side battery provider so a phone pairing to us can ask too."""

    CAPABILITY = Battery.CAPABILITY

    @staticmethod
    def read() -> dict | None:
        import glob
        from pathlib import Path
        for base in ("/sys/class/power_supply/",):
            for d in sorted(glob.glob(base + "*")):
                try:
                    cap = int(Path(d, "capacity").read_text())
                    status = Path(d, "status").read_text().strip()
                    return {"currentCharge": cap,
                            "isCharging": status in ("Charging", "Full")}
                except (OSError, ValueError):
                    continue
        return None

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        if body.get("request"):
            state = self.read()
            if state:
                try:
                    device.send(packet(self.CAPABILITY, body=state))
                except Exception:
                    pass
