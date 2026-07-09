"""Structured tile patterns (v0.3) — the Quake 2 "base texture set" analog.

id's Q2 art pipeline hinged on small, hand-drawn, power-of-two tile sets
("base" sets plus area sets) that level designers skinned brushes with. The
honest Patina analog is not hand-drawn art — it is *structured* generated
tiles: grout-lined floor tile, checkerboard, running-bond block courses,
panel seams, planking. Structure is what makes a surface read as a material
instead of tinted noise, and per-cell colour jitter is what fakes the
hand-set variety of a real texture set.

Rules, same as everything else in Patina:

* Deterministic: every pattern draws from :func:`patina.determinism.rng_for`
  streams keyed by ``(seed, "pattern", material_key, ...)`` — disjoint from
  the v0.2 ``"palette"`` streams, so untouched paths stay byte-identical.
* Tileable by construction: features are placed on integer cell grids over
  normalised 0..1 UV space, so the tile wraps exactly under Patina's
  box-projection UVs.
* Honest: these are stand-ins. The paint templates (:mod:`patina.templates`)
  are the seam where a human replaces them with real art via ``byo`` mode.

A pattern spec is plain JSON inside a theme::

    "pattern": {
        "floor": {"type": "tile", "cells": 4, "groove": "#3a352c"},
        "exterior_wall": {"type": "block", "rows": 6, "cols": 3}
    }

Spec keys (all optional except ``type``): ``cells`` / ``rows`` / ``cols``
(grid density, 1-64), ``groove`` (line colour ``#rrggbb``; default = darkened
base), ``line_px`` (line width in pixels at the generated size, 0-16),
``jitter`` (per-cell brightness jitter, 0-0.5).
"""

from __future__ import annotations

import numpy as np

from .determinism import rng_for

#: Pattern types a theme may request. ``noise`` is the v0.1.x/v0.2 look and
#: is handled by :mod:`patina.palette` itself (specifying it is equivalent to
#: omitting the pattern entry, but draws from the pattern RNG stream).
PATTERN_TYPES = ("noise", "tile", "checker", "block", "panel", "plank")

_MAX_GRID = 64
_MAX_LINE_PX = 16


def _hex(s: str) -> np.ndarray:
    t = s.strip().lstrip("#")
    return np.array([int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


def validate_spec(spec: dict, where: str) -> None:
    """Raise ValueError on a malformed pattern spec (theme-load time)."""
    if not isinstance(spec, dict):
        raise ValueError(f"{where}: pattern spec must be an object")
    ptype = spec.get("type")
    if ptype not in PATTERN_TYPES:
        raise ValueError(
            f"{where}: unknown pattern type {ptype!r} (want one of {PATTERN_TYPES})")
    for k in ("cells", "rows", "cols"):
        if k in spec:
            v = spec[k]
            if not isinstance(v, int) or not (1 <= v <= _MAX_GRID):
                raise ValueError(f"{where}: {k} must be an int 1..{_MAX_GRID}")
    if "line_px" in spec:
        v = spec["line_px"]
        if not isinstance(v, int) or not (0 <= v <= _MAX_LINE_PX):
            raise ValueError(f"{where}: line_px must be an int 0..{_MAX_LINE_PX}")
    if "jitter" in spec:
        v = spec["jitter"]
        if not isinstance(v, (int, float)) or not (0.0 <= v <= 0.5):
            raise ValueError(f"{where}: jitter must be 0..0.5")
    if "groove" in spec:
        g = spec["groove"]
        if not isinstance(g, str) or len(g.strip().lstrip("#")) != 6:
            raise ValueError(f"{where}: groove must be '#rrggbb'")
        try:
            _hex(g)
        except ValueError as e:
            raise ValueError(f"{where}: bad groove colour {g!r}") from e


# --------------------------------------------------------------------------- #
# Shared building blocks
# --------------------------------------------------------------------------- #

def tileable_noise(size: int, rng: np.random.Generator, octaves: int = 3) -> np.ndarray:
    """Sum of integer-frequency sinusoids -> seamlessly tiling value noise.

    Same construction as the palette's noise (integer frequencies wrap
    exactly); kept separate so the two never share an RNG stream.
    """
    yy, xx = np.meshgrid(np.linspace(0, 2 * np.pi, size, endpoint=False),
                         np.linspace(0, 2 * np.pi, size, endpoint=False), indexing="ij")
    field = np.zeros((size, size))
    amp = 1.0
    for o in range(octaves):
        fx, fy = int(rng.integers(1, 4 + o * 2)), int(rng.integers(1, 4 + o * 2))
        px, py = rng.uniform(0, 2 * np.pi, 2)
        field += amp * np.sin(fx * xx + px) * np.cos(fy * yy + py)
        amp *= 0.5
    field -= field.min()
    field /= max(field.max(), 1e-6)
    return field


def _cell_colors(rng: np.random.Generator, ny: int, nx: int,
                 base: np.ndarray, variants: list, jitter: float) -> np.ndarray:
    """(ny, nx, 3) per-cell colour: variant pick + brightness jitter.

    One array draw each, in fixed order, so the result is independent of any
    caller iteration order (the determinism module's requirement).
    """
    if variants:
        idx = rng.integers(0, len(variants), size=(ny, nx))
        cols = np.asarray(variants, np.float32)[idx]
    else:
        cols = np.tile(base.astype(np.float32), (ny, nx, 1))
    j = rng.uniform(-jitter, jitter, size=(ny, nx, 1)).astype(np.float32)
    return np.clip(cols * (1.0 + j), 0.0, 1.0)


def _grid(size: int):
    """Normalised pixel-centre coordinates, (size, size) each of v (rows), u."""
    c = (np.arange(size) + 0.5) / size
    vv, uu = np.meshgrid(c, c, indexing="ij")
    return vv, uu


def _groove_rgb(spec: dict, base: np.ndarray) -> np.ndarray:
    g = spec.get("groove")
    return _hex(g) if g else np.clip(base * 0.5, 0, 1).astype(np.float32)


# --------------------------------------------------------------------------- #
# Pattern implementations. Each returns a float (size, size, 3) image in 0..1
# (pre-posterize; the palette posterizes, same as the noise path).
# --------------------------------------------------------------------------- #

def _pat_tile(spec, size, rng, base, variants):
    """Square grid with grout lines — lino / ceramic floor, drop ceiling."""
    cells = int(spec.get("cells", 4))
    line_px = int(spec.get("line_px", 2))
    jitter = float(spec.get("jitter", 0.08))
    vv, uu = _grid(size)
    ix = np.minimum((uu * cells).astype(int), cells - 1)
    iy = np.minimum((vv * cells).astype(int), cells - 1)
    fx, fy = uu * cells - ix, vv * cells - iy
    img = _cell_colors(rng, cells, cells, base, variants, jitter)[iy, ix]
    g = line_px * cells / size
    img[(fx < g) | (fy < g)] = _groove_rgb(spec, base)
    return img


def _pat_checker(spec, size, rng, base, variants):
    """Two-tone checkerboard — the classic 90s deli / gas-station floor."""
    cells = int(spec.get("cells", 4))
    cells += cells % 2                       # even count wraps seamlessly
    jitter = float(spec.get("jitter", 0.06))
    vv, uu = _grid(size)
    ix = np.minimum((uu * cells).astype(int), cells - 1)
    iy = np.minimum((vv * cells).astype(int), cells - 1)
    if len(variants) >= 2:
        col_a, col_b = (np.asarray(variants[0], np.float32),
                        np.asarray(variants[1], np.float32))
    else:
        col_a, col_b = base, np.clip(base * 0.72, 0, 1)
    parity = ((ix + iy) % 2)[..., None]
    cols = np.where(parity == 0, col_a, col_b).astype(np.float32)
    j = rng.uniform(-jitter, jitter, size=(cells, cells)).astype(np.float32)
    return np.clip(cols * (1.0 + j[iy, ix][..., None]), 0.0, 1.0)


def _pat_block(spec, size, rng, base, variants):
    """Running-bond courses with mortar lines — cinderblock / brick."""
    rows = int(spec.get("rows", 6))
    cols = int(spec.get("cols", 3))
    line_px = int(spec.get("line_px", 2))
    jitter = float(spec.get("jitter", 0.08))
    vv, uu = _grid(size)
    iy = np.minimum((vv * rows).astype(int), rows - 1)
    fy = vv * rows - iy
    # Alternate rows shift by half a block; integer cols keeps the wrap exact.
    xs = uu * cols + (iy % 2) * 0.5
    ix = xs.astype(int) % cols
    fx = xs - np.floor(xs)
    img = _cell_colors(rng, rows, cols, base, variants, jitter)[iy, ix]
    gx, gy = line_px * cols / size, line_px * rows / size
    img[(fx < gx) | (fy < gy)] = _groove_rgb(spec, base)
    return img


def _pat_panel(spec, size, rng, base, variants):
    """Vertical panel seams — siding, wainscot sheets, garage panelling."""
    cols = int(spec.get("cols", 4))
    line_px = int(spec.get("line_px", 1))
    jitter = float(spec.get("jitter", 0.05))
    vv, uu = _grid(size)
    ix = np.minimum((uu * cols).astype(int), cols - 1)
    fx = uu * cols - ix
    img = _cell_colors(rng, 1, cols, base, variants, jitter)[np.zeros_like(ix), ix]
    g = line_px * cols / size
    img[fx < g] = _groove_rgb(spec, base)
    return img


def _pat_plank(spec, size, rng, base, variants):
    """Horizontal boards with gap lines and along-board grain — wood trim."""
    rows = int(spec.get("rows", 5))
    line_px = int(spec.get("line_px", 1))
    jitter = float(spec.get("jitter", 0.10))
    vv, uu = _grid(size)
    iy = np.minimum((vv * rows).astype(int), rows - 1)
    fy = vv * rows - iy
    img = _cell_colors(rng, rows, 1, base, variants, jitter)[iy, np.zeros_like(iy)]
    # Grain: integer-frequency sinusoids along u, phase per board (wraps in u
    # exactly; boards are discrete so v wraps too).
    freqs = rng.integers(6, 14, size=2)
    phases = rng.uniform(0, 2 * np.pi, size=(rows, 2)).astype(np.float32)
    grain = (np.sin(2 * np.pi * int(freqs[0]) * uu + phases[iy, 0])
             + 0.5 * np.sin(2 * np.pi * int(freqs[1]) * uu + phases[iy, 1])) / 1.5
    img = np.clip(img * (1.0 + 0.06 * grain[..., None]), 0.0, 1.0)
    g = line_px * rows / size
    img[fy < g] = _groove_rgb(spec, base)
    return img


def _pat_noise(spec, size, rng, base, variants):
    """Explicit noise pattern (pattern-stream flavour of the v0.1.x look)."""
    n = tileable_noise(size, rng)
    if variants:
        base = np.asarray(variants[int(rng.integers(0, len(variants)))], np.float32)
    value = 0.82 + 0.36 * n
    return np.clip(value[..., None] * base[None, None, :], 0, 1)


_GENERATORS = {
    "noise": _pat_noise,
    "tile": _pat_tile,
    "checker": _pat_checker,
    "block": _pat_block,
    "panel": _pat_panel,
    "plank": _pat_plank,
}


def generate(key: str, spec: dict, *, size: int, seed: int,
             base: np.ndarray, variants: list) -> np.ndarray:
    """Float (size, size, 3) pattern image in 0..1 for one material key.

    ``variants`` are the theme's albedo colours for the key (may be empty ->
    per-cell jitter of ``base`` only). Structure comes from the pattern; a
    faint noise overlay (its own RNG stream) breaks up the flat cells.
    """
    rng = rng_for(seed, "pattern", key)
    img = _GENERATORS[spec["type"]](spec, size, rng,
                                    np.asarray(base, np.float32), variants)
    overlay = tileable_noise(size, rng_for(seed, "pattern", key, "noise"))
    return np.clip(img * (0.92 + 0.16 * overlay)[..., None], 0.0, 1.0)
