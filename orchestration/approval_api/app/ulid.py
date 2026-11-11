"""Tiny dependency-free ULID generator.

SCHEMA.md requires server-generated, time-sortable, lexicographically-ordered
ids for both ``approvals`` (doc id == ``approval_id``) and ``audit_log`` rows.
A ULID (Crockford base32, 48-bit millisecond timestamp + 80 bits of
randomness) satisfies that and avoids hotspotting on a monotonic key.

We implement it inline (no third-party ``ulid`` package) so the service has one
fewer dependency to pin/audit and is guaranteed importable in CI/the emulator.

Reference: the ULID spec -- https://github.com/ulid/spec
"""

from __future__ import annotations

import os
import time

# Crockford's base32 alphabet (excludes I, L, O, U to avoid ambiguity).
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ENCODE_LEN = 26  # ULID string length


def _encode(value: int, length: int) -> str:
    """Encode ``value`` as a fixed-``length`` Crockford base32 string."""
    chars = []
    for _ in range(length):
        value, rem = divmod(value, 32)
        chars.append(_CROCKFORD[rem])
    return "".join(reversed(chars))


def new_ulid(prefix: str = "") -> str:
    """Return a new ULID string, optionally with a human-readable ``prefix``.

    ``prefix`` (e.g. ``"apr_"`` for approvals, ``"evt_"`` for audit rows) is not
    part of the ULID spec but aids readability, matching the ``apr_...`` example
    ids in SCHEMA.md. The 26-char ULID body remains sortable regardless.
    """
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)  # 48-bit ms
    randomness = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    body = _encode((timestamp_ms << 80) | randomness, _ENCODE_LEN)
    return f"{prefix}{body}"
