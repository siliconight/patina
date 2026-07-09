"""Structured tile patterns: determinism, tileability (roll invariance of the
grid structure), per-cell variety, spec validation, and the default-theme
byte-identity guarantee carried forward from v0.2."""

from __future__ import annotations

import io
import json

import numpy as np
import pytest

from patina import patterns, themes
from patina.determinism import rng_for
from patina.mesh import SurfaceRole
from patina.palette import PaletteOptions, generate_tile

BASE = np.array([0.6, 0.6, 0.6], np.float32)
SIZE = 96  # divisible by the cell counts used below


def _raw(ptype, spec_extra=None, variants=None):
    """Run one raw generator with a fixed stream (no overlay noise)."""
    spec = {"type": ptype, "jitter": 0.0}
    spec.update(spec_extra or {})
    fn = patterns._GENERATORS[ptype]
    return fn(spec, SIZE, rng_for(7, "t", ptype), BASE, variants or [])


def test_generate_deterministic_per_type():
    for ptype in patterns.PATTERN_TYPES:
        spec = {"type": ptype}
        a = patterns.generate("wall", spec, size=64, seed=1999, base=BASE, variants=[])
        b = patterns.generate("wall", spec, size=64, seed=1999, base=BASE, variants=[])
        assert np.array_equal(a, b), ptype


def test_types_differ():
    imgs = [patterns.generate("wall", {"type": t}, size=64, seed=1999,
                              base=BASE, variants=[]) for t in patterns.PATTERN_TYPES]
    for i in range(len(imgs)):
        for j in range(i + 1, len(imgs)):
            assert not np.array_equal(imgs[i], imgs[j])


def test_tile_structure_wraps():
    img = _raw("tile", {"cells": 4})
    assert np.allclose(img, np.roll(img, SIZE // 4, axis=0))
    assert np.allclose(img, np.roll(img, SIZE // 4, axis=1))


def test_checker_structure_wraps():
    img = _raw("checker", {"cells": 4})
    assert np.allclose(img, np.roll(img, 2 * (SIZE // 4), axis=0))
    assert np.allclose(img, np.roll(img, 2 * (SIZE // 4), axis=1))
    # And a one-cell roll flips parity, so it must NOT match.
    assert not np.allclose(img, np.roll(img, SIZE // 4, axis=1))


def test_block_structure_wraps():
    img = _raw("block", {"rows": 6, "cols": 3})
    assert np.allclose(img, np.roll(img, SIZE // 3, axis=1))       # one block
    assert np.allclose(img, np.roll(img, 2 * (SIZE // 6), axis=0))  # two courses


def test_panel_structure_wraps():
    img = _raw("panel", {"cols": 4})
    assert np.allclose(img, np.roll(img, SIZE // 4, axis=1))


def test_plank_gap_rows_hit_groove_colour():
    spec = {"rows": 4, "line_px": 2, "groove": "#102030"}
    img = _raw("plank", spec)
    groove = patterns._hex("#102030")
    board_px = SIZE // 4
    for k in range(4):
        assert np.allclose(img[k * board_px], groove)


def test_variants_drive_cell_variety():
    variants = [(0.9, 0.1, 0.1), (0.1, 0.9, 0.1), (0.1, 0.1, 0.9)]
    img = _raw("tile", {"cells": 4, "line_px": 0}, variants=variants)
    # With three loud variants over 16 cells, more than one must appear.
    assert len(np.unique(img.reshape(-1, 3), axis=0)) >= 2


@pytest.mark.parametrize("bad", [
    {"type": "plaid"},
    {"type": "tile", "cells": 0},
    {"type": "tile", "cells": 999},
    {"type": "block", "line_px": 99},
    {"type": "panel", "jitter": 0.9},
    {"type": "tile", "groove": "red"},
    "not-a-dict",
])
def test_validate_spec_raises(bad):
    with pytest.raises(ValueError):
        patterns.validate_spec(bad, "here")


def test_theme_with_bad_pattern_raises(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"name": "t", "pattern": {"wall": {"type": "plaid"}}}))
    with pytest.raises(ValueError):
        themes.load(str(p))
    p.write_text(json.dumps({"name": "t", "pattern": {"nope": {"type": "tile"}}}))
    with pytest.raises(ValueError):
        themes.load(str(p))


def _png(role, theme, opts):
    buf = io.BytesIO()
    generate_tile(role, opts, theme).save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def test_default_theme_tiles_still_byte_identical():
    """The v0.2 guarantee survives v0.3: no pattern entry -> old code path."""
    opts = PaletteOptions(mode="procedural", size=64, seed=1999)
    default = themes.load("default")
    for role in (SurfaceRole.FLOOR, SurfaceRole.WALL, SurfaceRole.CEILING):
        assert _png(role, default, opts) == _png(role, None, opts)


def test_delco_theme_uses_patterns():
    t = themes.load("delco_1997_gas_station")
    assert t.pattern_spec("floor")["type"] == "tile"
    assert t.pattern_spec("exterior_wall")["type"] == "block"
    assert t.pattern_spec("roof") is None          # tar stays noise
    opts = PaletteOptions(mode="procedural", size=64, seed=1999)
    assert _png(SurfaceRole.FLOOR, t, opts) != _png(SurfaceRole.FLOOR, None, opts)
