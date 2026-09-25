"""LAN transport: UDP discovery, TCP/TLS connections, pairing state machine.

Implements the parts of the KDE Connect protocol we need:

* UDP broadcast identity packets on port 1716 (discovery).
* TCP connections on port 1716 wrapped in TLS with self-signed certificates.
* Pairing via ``kdeconnect.pair`` packets that carry the peer certificate (PEM).
* Plain-TCP data connections for file transfer (protocol v7 style transferInfo).
"""
from __future__ import annotations

import json
import logging
import socket
import ssl
import threading
import time
from pathlib import Path
from typing import Callable

from .packets import Identity, packet, read_packet

DISCOVERY_PORT = 1716
DISCOVERY_ADDR = "255.255.255.255"

log = logging.getLogger(__name__)


class Device:
    """One paired-or-pairable remote device."""

    def __init__(self, identity: Identity, addr: str):
        self.identity = identity
        self.addr = addr
        self.paired = False
        self.peer_cert: bytes | None = None   # PEM bytes learned via pairing
        self.sock: ssl.SSLSocket | socket.SocketIO | None = None
        self.last_seen = time.time()
        self.incoming_lock = threading.Lock()

    @property
    def id(self) -> str:
        return self.identity.device_id

    @property
    def name(self) -> str:
        return self.identity.name

    def send(self, raw: bytes) -> None:
        with self.incoming_lock:
            if self.sock is None:
                raise ConnectionError("not connected")
            self.sock.sendall(raw)


class Transport:
    """Owns the UDP announcer/listener and the TLS TCP server."""

    def __init__(self, identity: Identity, data_dir: Path,
                 on_device: Callable[[Device], None],
                 on_packet: Callable[[Device, dict], None],
                 on_data_conn: Callable[[socket.socket, str], None]):
        self.identity = identity
        self.data_dir = data_dir
        self.on_device = on_device        # a device was discovered / connected
        self.on_packet = on_packet        # a packet arrived over TLS
        self.on_data_conn = on_data_conn  # plain-TCP transfer connection opened
        self.devices: dict[str, Device] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._own_cert = self._load_or_create_cert()
        self._tls_ctx_in, self._tls_ctx_out = self._tls_contexts()
        self.threads: list[threading.Thread] = []

    # ------------------------------------------------------------------ certs
    @property
    def cert_dir(self) -> Path:
        d = self.data_dir / "certs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _load_or_create_cert(self) -> Path:
        crt = self.cert_dir / "phoney.crt"
        key = self.cert_dir / "phoney.key"
        if crt.exists() and key.exists():
            return crt
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import datetime

        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subj = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, self.identity.device_id)])
        cert = (x509.CertificateBuilder()
                .subject_name(subj).issuer_name(subj)
                .public_key(k.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
                .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
                .sign(k, hashes.SHA256()))
        key.write_bytes(k.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()))
        crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        return crt

    def _tls_contexts(self) -> tuple[ssl.SSLContext, ssl.SSLContext]:
        crt = str(self._own_cert)
        key = str(self.cert_dir / "phoney.key")
        # Incoming: we must accept the peer's self-signed cert; verification of
        # paired devices happens afterwards against the stored PEM.
        ctx_in = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx_in.load_cert_chain(crt, key)
        ctx_in.set_ciphers("HIGH@SECLEVEL=1")
        ctx_out = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx_out.load_cert_chain(crt, key)
        ctx_out.check_hostname = False
        ctx_out.verify_mode = ssl.CERT_NONE
        ctx_out.set_ciphers("HIGH@SECLEVEL=1")
        return ctx_in, ctx_out

    # --------------------------------------------------------------- lifecycle
    def start(self) -> None:
        for target, name in ((self._udp_loop, "discovery"), (self._tcp_loop, "tcp")):
            t = threading.Thread(target=target, name=name, daemon=True)
            t.start()
            self.threads.append(t)
        self.announce()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            for d in self.devices.values():
                try:
                    if d.sock:
                        d.sock.close()
                except OSError:
                    pass

    # ------------------------------------------------------------- discovery
    def announce(self) -> None:
        """Broadcast our identity once (call periodically to re-discover)."""
        self._broadcast_identity()

    def _broadcast_identity(self) -> None:
        raw = self.identity.to_packet()
        raw = (json.dumps(raw, separators=(",", ":")) + "\n").encode()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            s.sendto(raw, (DISCOVERY_ADDR, DISCOVERY_PORT))
        finally:
            s.close()

    def _udp_loop(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind(("", DISCOVERY_PORT))
        s.settimeout(1.0)
        while not self._stop.is_set():
            try:
                data, addr = s.recvfrom(65535)
            except socket.timeout:
                continue
            try:
                pkt = json.loads(data.decode().strip())
                if pkt.get("type") != "kdeconnect.identity":
                    continue
                ident = Identity.from_packet(pkt)
                if ident.device_id == self.identity.device_id:
                    continue
            except (ValueError, KeyError):
                continue
            with self._lock:
                dev = self.devices.get(ident.device_id)
                if dev is None:
                    dev = Device(ident, addr[0])
                    self.devices[ident.device_id] = dev
                    log.info("Discovered device %s (%s)", ident.name, ident.device_type)
                    self.on_device(dev)
                dev.last_seen = time.time()
                if dev.identity.name != ident.name:
                    dev.identity = ident
            self._connect_to(dev)

    def _connect_to(self, dev: Device) -> None:
        """Open a TLS connection to a discovered device if we don't have one."""
        with dev.incoming_lock:
            if dev.sock is not None:
                return
        try:
            raw = socket.create_connection((dev.addr, DISCOVERY_PORT), timeout=5)
            sock = self._tls_ctx_out.wrap_socket(raw, server_hostname=dev.addr)
            self._handshake_identity(dev, sock, dev.addr, send_first=True)
        except OSError as e:
            log.debug("Connect to %s failed: %s", dev.addr, e)
            try:
                raw.close()
            except OSError:
                pass

    # ------------------------------------------------------------- TCP server
    def _tcp_loop(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except (AttributeError, OSError):
            pass
        srv.bind(("", DISCOVERY_PORT))
        srv.listen(8)
        srv.settimeout(1.0)
        while not self._stop.is_set():
            try:
                raw, addr = srv.accept()
            except socket.timeout:
                continue
            threading.Thread(target=self._accept_incoming, args=(raw, addr),
                             daemon=True).start()

    def _accept_incoming(self, raw: socket.socket, addr) -> None:
        first = raw.recv(3, socket.MSG_PEEK)
        if first[:1] in (b"\x16", b"\x80"):  # TLS ClientHello
            try:
                sock = self._tls_ctx_in.wrap_socket(raw, server_side=True)
            except ssl.SSLError as e:
                log.debug("TLS accept from %s failed: %s", addr, e)
                raw.close()
                return
            self._handshake_identity(None, sock, addr[0])
        else:
            # Plain-TCP transfer data connection (protocol v7 transferInfo).
            self.on_data_conn(raw, addr[0])

    def _handshake_identity(self, dev: Device | None, sock, addr: str = "",
                            send_first: bool = False) -> None:
        try:
            if send_first:
                # The connecting side sends identity first (KDE Connect convention).
                sock.sendall((json.dumps(self.identity.to_packet(),
                                         separators=(",", ":")) + "\n").encode())
            pkt = read_packet(sock)
            if pkt.get("type") != "kdeconnect.identity":
                log.debug("Expected identity, got %s", pkt.get("type"))
                sock.close()
                return
            ident = Identity.from_packet(pkt)
            if ident.device_id == self.identity.device_id:
                sock.close()
                return
            with self._lock:
                dev = self.devices.setdefault(ident.device_id,
                                              Device(ident, addr))
                dev.identity = ident
                dev.addr = addr
                dev.sock = sock
            if not send_first:
                sock.sendall((json.dumps(self.identity.to_packet(),
                                         separators=(",", ":")) + "\n").encode())
            log.info("Connected to %s at %s", ident.name, addr)
            self.on_device(dev)
            threading.Thread(target=self._read_loop, args=(dev,),
                             daemon=True).start()
        except (OSError, ValueError) as e:
            log.debug("Handshake with %s failed: %s", addr, e)
            try:
                sock.close()
            except OSError:
                pass

    def _read_loop(self, dev: Device) -> None:
        try:
            while True:
                pkt = read_packet(dev.sock)
                if pkt.get("type") == "kdeconnect.pair":
                    self._handle_pair(dev, pkt)
                    continue
                if not dev.paired and pkt.get("type") != "kdeconnect.pair":
                    continue  # ignore traffic from unpaired devices
                self.on_packet(dev, pkt)
        except (ConnectionError, OSError, ValueError):
            pass
        finally:
            with dev.incoming_lock:
                if dev.sock is not None:
                    try:
                        dev.sock.close()
                    except OSError:
                        pass
                dev.sock = None

    # ---------------------------------------------------------------- pairing
    def pair_with(self, dev: Device) -> None:
        """Send a pairing request (or accept an incoming one)."""
        cert_pem = self._own_cert.read_bytes()
        dev.send(packet("kdeconnect.pair",
                        body={"pair": True, "certificate": cert_pem.decode()}))

    def unpair(self, dev: Device) -> None:
        try:
            dev.send(packet("kdeconnect.pair", body={"pair": False}))
        except ConnectionError:
            pass
        dev.paired = False
        self._forget(dev.id)

    def _handle_pair(self, dev: Device, pkt: dict) -> None:
        body = pkt.get("body", {})
        wants_pair = body.get("pair", False)
        cert = body.get("certificate")
        if cert:
            dev.peer_cert = cert.encode()
        if wants_pair and not dev.paired:
            self.pair_with(dev)  # accept: reply with our cert
            self._trust(dev)
        elif not wants_pair:
            self._forget(dev.id)
            dev.paired = False

    def _trust(self, dev: Device) -> None:
        if dev.peer_cert is None:
            return
        dev.paired = True
        f = self.cert_dir / f"{dev.id}.pem"
        f.write_bytes(dev.peer_cert)
        log.info("Paired with %s", dev.name)

    def _forget(self, device_id: str) -> None:
        f = self.cert_dir / f"{device_id}.pem"
        if f.exists():
            f.unlink()
