"""SMS plugin — read and send the phone's SMS messages from the desktop."""
from __future__ import annotations

import logging
import threading

from ..packets import packet

log = logging.getLogger(__name__)


class Sms:
    """Receives incoming SMS from the phone (kdeconnect.sms.notification) and
    tracks conversations read from kdeconnect.sms.request replies."""
    INCOMING_CAP = "kdeconnect.sms.notification"
    REQUEST_CAP = "kdeconnect.sms.request"

    def __init__(self):
        self._messages: dict[str, list[dict]] = {}  # device -> messages
        self._lock = threading.Lock()

    def handle(self, device, pkt: dict) -> None:
        t = pkt.get("type", "")
        body = pkt.get("body", {})
        if t == self.INCOMING_CAP:
            msg = {"event": body.get("event"), "number": body.get("phoneNumber"),
                   "text": body.get("messageBody", ""), "date": body.get("mills"),
                   "threadId": body.get("threadId")}
            with self._lock:
                self._messages.setdefault(device.id, []).append(msg)
            log.info("SMS from %s: %s", body.get("phoneNumber"),
                     (body.get("messageBody") or "")[:60])
        elif t == self.REQUEST_CAP:
            messages = body.get("messages")
            if isinstance(messages, dict):
                for k, v in messages.items():
                    payload = v.get("body", v)
                    with self._lock:
                        self._messages.setdefault(device.id, []).append({
                            "number": payload.get("address"),
                            "text": payload.get("body"),
                            "date": payload.get("date"),
                            "threadId": payload.get("thread_id"),
                        })
            elif isinstance(messages, list):
                with self._lock:
                    self._messages.setdefault(device.id, []).extend(messages)

    def inbox(self, device_id: str) -> list[dict]:
        with self._lock:
            return list(self._messages.get(device_id, []))


class SmsSource:
    """Send an SMS through the phone (requires the phone app's SMS permission)."""
    REQUEST_CAP = Sms.REQUEST_CAP

    @staticmethod
    def send(device, number: str, text: str) -> None:
        device.send(packet(Sms.REQUEST_CAP, body={
            "version": 2, "action": "send", "addresses": [{"address": number}],
            "messageBody": text,
        }))

    @staticmethod
    def request_conversations(device) -> None:
        device.send(packet(Sms.REQUEST_CAP, body={"action": "request_conversations"}))

    @staticmethod
    def request_thread(device, thread_id) -> None:
        device.send(packet(Sms.REQUEST_CAP, body={"action": "request_thread",
                                                  "threadID": thread_id}))
