"""File transfer plugin.

Receiving: KDE Connect Android sends a ``kdeconnect.transfer`` packet with
``body.transferInfo`` = {"port": N, "portDescription": "..."} and opens a
plain-TCP listener on that port on the phone. We connect and stream bytes to a
file.

Sending: we open a plain-TCP listener on a free port, send a transfer packet
pointing at it, and stream the file to whoever connects (the phone).
"""
from __future__ import annotations

import logging
import os
import socket
import threading

from ..packets import packet

log = logging.getLogger(__name__)


class FileTransfer:
    CAPABILITY = "kdeconnect.transfer"

    def __init__(self, download_dir, upload_dir=None):
        from pathlib import Path
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- receive
    def handle(self, device, pkt: dict) -> None:
        info = pkt.get("body", {}).get("transferInfo", {})
        port = info.get("port")
        desc = info.get("portDescription", "file")
        if not port:
            return
        threading.Thread(target=self._download, args=(device, port, desc),
                         daemon=True).start()

    def _download(self, device, port: int, desc: str) -> None:
        host = device.addr
        try:
            sock = socket.create_connection((host, port), timeout=10)
            f = open(self._dest(desc), "wb")
            with sock, f:
                while True:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    f.write(chunk)
            log.info("Received %s from %s", f.name, device.name)
            self.notify_done(f"Received {desc.split('/')[-1]}")
        except OSError as e:
            log.error("Transfer from %s failed: %s", device.name, e)

    def _dest(self, desc: str) -> str:
        import os
        name = os.path.basename(desc) or "received-file"
        path = self.download_dir / name
        i = 1
        while path.exists():
            stem, ext = os.path.splitext(name)
            path = self.download_dir / f"{stem} ({i}){ext}"
            i += 1
        return str(path)

    # ------------------------------------------------------------------ send
    def send_file(self, device, path: str) -> bool:
        import os
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            log.error("Not a file: %s", path)
            return False
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(("", 0))
        port = srv.getsockname()[1]
        srv.listen(1)
        srv.settimeout(60)

        device.send(packet(
            "kdeconnect.transfer",
            body={"transferInfo": {
                "port": port,
                "portDescription": path,
            }}))
        threading.Thread(target=self._serve_upload,
                         args=(srv, path), daemon=True).start()
        return True

    def _serve_upload(self, srv: socket.socket, path: str) -> None:
        try:
            conn, _ = srv.accept()
            with conn, open(path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    conn.sendall(chunk)
            log.info("Sent %s", path)
            self.notify_done(f"Sent {os.path.basename(path)}")
        except (OSError, TimeoutError) as e:
            log.error("Sending %s failed: %s", path, e)
        finally:
            srv.close()

    def notify_done(self, msg: str) -> None:
        try:
            import subprocess
            subprocess.run(["notify-send", "-a", "Phoney", "Phoney", msg],
                           timeout=5, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
        except Exception:
            pass
