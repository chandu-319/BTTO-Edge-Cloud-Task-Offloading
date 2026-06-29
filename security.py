"""Data integrity helpers based on SHA-256."""

from __future__ import annotations

import hashlib


def sha256_digest(payload: bytes) -> str:
    """Return the SHA-256 hex digest for task data."""
    return hashlib.sha256(payload).hexdigest()


def verify_payload(original_hash: str, payload: bytes) -> bool:
    """Return whether payload matches a previously recorded SHA-256 hash."""
    return sha256_digest(payload) == original_hash
