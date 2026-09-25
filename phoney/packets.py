"""KDE Connect network packet handling.

Every packet on the wire is a single UTF-8 JSON object terminated by a newline
(the legacy framing) — we read length-prefixed free-form payloads per protocol
v8. In practice both framing styles exist; KDE Connect uses newline-terminated
JSON over TCP.
"""
from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass, field


@dataclass
class Identity:
    """A kdeconnect.identity packet, our own or a remote device's."""

    name: str
    device_id: str
    device_type: str = "desktop"
    protocol_version: str = "8.0"
    incoming: list[str] = field(default_factory=list)   # capabilities we can accept
    outgoing: list[str] = field(default_factory=list)   # capabilities we can offer

    @classmethod
    def from_packet(cls, pkt: dict) -> "Identity":
        body = pkt.get("body", {})
        return cls(
            name=body.get("deviceName", "unknown"),
            device_id=body.get("deviceId", ""),
            device_type=body.get("deviceType", "smartphone"),
            protocol_version=body.get("protocolVersion", "7.0"),
            incoming=body.get("incomingCapabilities", []) or [],
            outgoing=body.get("outgoingCapabilities", []) or [],
        )

    def to_packet(self) -> dict:
        return {
            "id": int(time.time() * 1000),
            "type": "kdeconnect.identity",
            "body": {
                "deviceName": self.name,
                "deviceId": self.device_id,
                "deviceType": self.device_type,
                "protocolVersion": self.protocol_version,
                "incomingCapabilities": self.incoming,
                "outgoingCapabilities": self.outgoing,
            },
        }


def packet(type_: str, body: dict | None = None, **payloads) -> bytes:
    """Serialize a packet with newline framing."""
    pkt: dict = {"id": int(time.time() * 1000), "type": type_}
    if body is not None:
        pkt["body"] = body
    for k, v in payloads.items():
        if v is not None:
            pkt[k] = v
    return (json.dumps(pkt, separators=(",", ":")) + "\n").encode()


def read_packet(sock: socket.socket) -> dict:
    """Read one newline-terminated JSON packet from a socket."""
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("peer closed connection")
        buf += chunk
        if len(buf) > 1 << 20:  # 1 MiB cap on packet size
            raise ValueError("packet too large")
    return json.loads(buf.decode().strip())
