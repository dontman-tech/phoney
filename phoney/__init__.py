"""Phoney — a Linux companion for the KDE Connect protocol.

Pairs your Linux desktop with your Android phone (using the stock KDE Connect
app) for notifications, file transfer and clipboard sync.
"""
from __future__ import annotations

import logging

from .daemon import Daemon

__version__ = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

__all__ = ["Daemon", "__version__"]
