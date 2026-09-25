"""Notifications plugin — shows your phone's Android notifications on Linux."""
from __future__ import annotations

import logging
import subprocess
import threading

from ..packets import packet

log = logging.getLogger(__name__)


class Notifications:
    CAPABILITY = "kdeconnect.notification"

    def __init__(self):
        self._handles: dict[str, str] = {}  # internalId -> originalId
        self._lock = threading.Lock()

    def handle(self, device, pkt: dict) -> None:
        body = pkt.get("body", {})
        title = body.get("title", "Notification")
        text = body.get("text", "")
        app = body.get("appName", "")
        ident = body.get("id", "")

        with self._lock:
            if ident and self._handles.get(ident):
                return  # duplicate
        prefix = f"{app}: " if app else ""
        self._notify(f"{prefix}{title}", text)
        with self._lock:
            if ident:
                self._handles[ident] = ident

    def _notify(self, title: str, body: str) -> None:
        for argv in (
            ["notify-send", "-a", "Phoney", title, body],
            ["notify-send", title, body],
        ):
            try:
                subprocess.run(argv, timeout=5,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue
        log.info("Notification (no notifier installed): %s — %s", title, body)

    # We don't request the reply capability in v1; still answer dismissals.
    def dismiss(self, device, ident: str) -> None:
        try:
            device.send(packet("kdeconnect.notification.request",
                                body={"cancel": ident}))
        except Exception:
            pass
