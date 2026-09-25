"""Phoney daemon — owns the transport and routes packets to plugins."""
from __future__ import annotations

import logging
import socket
import threading
import time
from pathlib import Path

from .packets import Identity, packet
from .transport import Device, Transport
from .plugins.clipboard import Clipboard, make_x11_clipboard
from .plugins.filetransfer import FileTransfer
from .plugins.notifications import Notifications

log = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".local" / "share" / "phoney"


class Daemon:
    """Run one Phoney instance: discover, pair, and serve plugins."""

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.device_name = socket.gethostname()
        self.identity = Identity(
            name=self.device_name,
            device_id=f"phoney-{self.device_name}".replace(" ", "")[:64],
            device_type="desktop",
            incoming=[Notifications.CAPABILITY, FileTransfer.CAPABILITY,
                      Clipboard.CAPABILITY],
            outgoing=[FileTransfer.CAPABILITY, Clipboard.CAPABILITY],
        )
        self.notifications = Notifications()
        self.filetransfer = FileTransfer(self.data_dir / "Downloads")
        self.clipboard: Clipboard = make_x11_clipboard()
        self.transport = Transport(
            self.identity, self.data_dir,
            on_device=self._on_device,
            on_packet=self._on_packet,
            on_data_conn=self._on_data_conn,
        )

    # ------------------------------------------------------------------ events
    def _on_device(self, dev: Device) -> None:
        pass  # CLI/UI observes via transport.devices

    def _on_packet(self, dev: Device, pkt: dict) -> None:
        t = pkt.get("type", "")
        if t == self.notifications.CAPABILITY:
            self.notifications.handle(dev, pkt)
        elif t == self.filetransfer.CAPABILITY:
            self.filetransfer.handle(dev, pkt)
        elif t == self.clipboard.CAPABILITY:
            self.clipboard.handle(dev, pkt)
        else:
            log.debug("Unhandled packet %s from %s", t, dev.name)

    def _on_data_conn(self, sock: socket.socket, addr: str) -> None:
        # Plain-TCP data connection: likely an incoming file transfer payload.
        log.debug("Data connection from %s", addr)
        try:
            sock.close()
        except OSError:
            pass

    # ------------------------------------------------------------------ API
    def start(self) -> None:
        self.transport.start()
        threading.Thread(target=self._keepalive, daemon=True).start()

    def stop(self) -> None:
        self.transport.stop()

    def _keepalive(self) -> None:
        while True:
            time.sleep(25)
            try:
                self.transport._broadcast_identity()
            except OSError:
                pass

    def devices(self) -> list[Device]:
        return list(self.transport.devices.values())

    def paired_devices(self) -> list[Device]:
        return [d for d in self.devices() if d.paired]

    def pair(self, name_or_id: str) -> Device:
        dev = self._find(name_or_id)
        self.transport.pair_with(dev)
        # Pairing completes when the peer replies; poll for convenience.
        for _ in range(20):
            if dev.paired:
                return dev
            time.sleep(0.25)
        return dev

    def unpair(self, name_or_id: str) -> None:
        self.transport.unpair(self._find(name_or_id))

    def send_file(self, name_or_id: str, path: str) -> None:
        dev = self._find(name_or_id)
        if not dev.paired:
            raise ConnectionError(f"{dev.name} is not paired")
        self.filetransfer.send_file(dev, path)

    def push_clipboard(self, name_or_id: str | None = None) -> None:
        targets = ([self._find(name_or_id)] if name_or_id
                   else self.paired_devices())
        for dev in targets:
            self.clipboard.push(dev)

    def _find(self, name_or_id: str) -> Device:
        for d in self.devices():
            if name_or_id in (d.id, d.name):
                return d
        raise LookupError(f"No device matching {name_or_id!r}. "
                          f"Visible: {[(d.name, d.paired) for d in self.devices()]}")
