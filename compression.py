"""Compression helpers for the task-offloading extension."""

from __future__ import annotations

import zlib


def compress_payload(payload: bytes) -> bytes:
    """Compress task data using zlib."""
    return zlib.compress(payload, level=6)


def decompress_payload(payload: bytes) -> bytes:
    """Decompress zlib-compressed task data."""
    return zlib.decompress(payload)


def compression_ratio(original: bytes, compressed: bytes) -> float:
    """Return compressed/original size ratio, guarding empty payloads."""
    if not original:
        return 1.0
    return len(compressed) / len(original)
