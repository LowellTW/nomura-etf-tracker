"""Fetch and normalize public Nomura ETF data."""

from .client import NomuraClient
from .normalize import build_snapshot

__all__ = ["NomuraClient", "build_snapshot"]

