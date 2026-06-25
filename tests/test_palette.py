"""Procedural texture palette: posterize, determinism, tileability, modes."""

from __future__ import annotations

import numpy as np

from patina.mesh import SurfaceRole
from patina.palette import PaletteOptions, build_palette, generate_tile, posterize


def test_posterize_reduces_levels():
    arr = np.linspace(0, 1, 256).reshape(16, 16, 1).repeat(3, axis=2)
    out = posterize(arr, 4)
    assert len(np.unique(out)) <= 4


def test_generate_tile_deterministic():
    opts = PaletteOptions(mode="procedural", size=64, seed=1999)
    a = np.asarray(generate_tile(SurfaceRole.WALL, opts))
    b = np.asarray(generate_tile(SurfaceRole.WALL, opts))
    assert np.array_equal(a, b)


def test_tiles_differ_by_role():
    opts = PaletteOptions(mode="procedural", size=64, seed=1999)
    wall = np.asarray(generate_tile(SurfaceRole.WALL, opts))
    floor = np.asarray(generate_tile(SurfaceRole.FLOOR, opts))
    assert not np.array_equal(wall, floor)


def test_tile_is_tileable():
    """Left/right and top/bottom edges should match (seamless wrap)."""
    opts = PaletteOptions(mode="procedural", size=64, seed=1999)
    img = np.asarray(generate_tile(SurfaceRole.WALL, opts)).astype(int)
    # integer-frequency sinusoids wrap exactly; allow 1 LSB for posterize rounding
    assert np.abs(img[0, :] - img[-1, :]).max() <= 18
    assert np.abs(img[:, 0] - img[:, -1]).max() <= 18


def test_vertex_color_mode_makes_no_textures():
    assert build_palette({SurfaceRole.WALL}, PaletteOptions(mode="vertex-color")) == {}


def test_procedural_mode_makes_a_tile_per_role():
    roles = {SurfaceRole.WALL, SurfaceRole.FLOOR}
    out = build_palette(roles, PaletteOptions(mode="procedural", size=32))
    assert set(out) == {"wall", "floor"}
    assert all(v[:8].startswith(b"\x89PNG") for v in out.values())
