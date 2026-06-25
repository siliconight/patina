"""Determinism helpers.

The TDD's load-bearing property: *same input + same seed -> byte-identical
output, every run, every machine.* Most stages are pure functions of geometry
and need no randomness at all (the vertex-colour formula is fully geometric).
Where a stage does want variation — procedural texture generation, per-surface
variant selection — it must draw from a stream that is reproducible and
**independent of iteration order**, so a dict reordering can never change the
bytes.

:func:`rng_for` gives each logical unit (e.g. a surface role) its own generator
seeded by hashing the global seed together with string tags. Two runs that ask
for ``rng_for(1999, "wall")`` get the same generator regardless of what else
happened in between.
"""

from __future__ import annotations

import hashlib

import numpy as np


def _mix(seed: int, *tags: str) -> int:
    h = hashlib.sha256(str(seed).encode())
    for t in tags:
        h.update(b"\x00")
        h.update(str(t).encode())
    # 64-bit seed for numpy's PCG64.
    return int.from_bytes(h.digest()[:8], "little")


def rng_for(seed: int, *tags: str) -> np.random.Generator:
    """A numpy Generator unique to (seed, *tags), order-independent."""
    return np.random.default_rng(_mix(seed, *tags))
