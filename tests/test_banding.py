"""Vertical banding: spec validation, world-height band selection, family
locking, the no-band byte-identity guarantee, and theme/skin/CLI wiring."""

from __future__ import annotations

import numpy as np
import pytest

from patina import banding, cli, families, skins, themes
from patina.mesh import SurfaceRole


def test_parse_forces_last_to_one_and_sorts():
    raw = {"wall": [{"to": 0.9, "tint": "#222222"}, {"to": 0.3, "tint": "#111111"}]}
    parsed = banding.parse(raw)
    tos = [to for to, _ in parsed[SurfaceRole.WALL]]
    assert tos == [0.3, 1.0]              # sorted, last clamped to 1.0


@pytest.mark.parametrize("raw", [
    {"floor": [{"to": 0.5, "tint": "#111111"}]},      # non-vertical role
    {"wall": []},                                     # empty
    {"wall": [{"to": 1.5, "tint": "#111111"}]},       # out of range
    {"wall": [{"to": 0.5}]},                          # missing tint
    {"wall": [{"to": 0.9, "tint": "#111111"},
              {"to": 0.3, "tint": "#222222"}]},       # descending (pre-sort check)
    {"wall": [{"to": 0.5, "tint": "nope"}]},          # bad hex
])
def test_validate_spec_raises(raw):
    with pytest.raises(ValueError):
        banding.validate_spec(raw, "here")


def test_band_rgb_selects_by_fraction():
    pairs = banding.parse({"wall": [
        {"to": 0.3, "tint": "#ff0000"}, {"to": 0.9, "tint": "#00ff00"},
        {"to": 1.0, "tint": "#0000ff"}]})[SurfaceRole.WALL]
    assert np.allclose(banding.band_rgb(pairs, 0.1), [1, 0, 0])   # base
    assert np.allclose(banding.band_rgb(pairs, 0.5), [0, 1, 0])   # body
    assert np.allclose(banding.band_rgb(pairs, 0.99), [0, 0, 1])  # cap


def test_vertex_band_tints_only_touches_banded_roles():
    bands = banding.parse({"wall": [{"to": 0.5, "tint": "#ff0000"},
                                    {"to": 1.0, "tint": "#00ff00"}]})
    pos = np.array([[0, 0, 0.0], [0, 0, 1.0], [0, 0, 0.0]], np.float32)
    roles = np.array([SurfaceRole.WALL, SurfaceRole.WALL, SurfaceRole.FLOOR],
                     dtype=object)
    base = np.tile(np.array([0.5, 0.5, 0.5], np.float32), (3, 1))
    out = banding.vertex_band_tints(pos, roles, bands, (0.0, 1.0), base)
    assert np.allclose(out[0], [1, 0, 0])       # wall, low -> base band
    assert np.allclose(out[1], [0, 1, 0])       # wall, high -> cap band
    assert np.allclose(out[2], [0.5, 0.5, 0.5])  # floor untouched


def test_lock_bands_to_family():
    bands = banding.parse({"wall": [{"to": 0.5, "tint": "#ff0011"},
                                    {"to": 1.0, "tint": "#0011ff"}]})
    fam = families.load("delco_faded")
    locked = banding.lock(bands, fam)
    lib = fam.palette_rgb()
    for _, rgb in locked[SurfaceRole.WALL]:
        assert float(((lib - rgb) ** 2).sum(1).min()) < 1e-10


def test_delco_theme_declares_bands():
    t = themes.load("delco_1997_gas_station")
    assert "wall" in t.bands and "exterior_wall" in t.bands
    parsed = banding.parse(t.bands)
    assert len(parsed[SurfaceRole.WALL]) == 3


def test_default_theme_has_no_bands():
    assert themes.load("default").bands == {}


def test_skin_bands_from_60_30_10():
    sk = skins.generate("nicotine", ["#a98a52"])
    b = sk.bands()
    assert set(b) == {"wall", "exterior_wall"}
    # wall base band == dominant shadow; cap == accent base
    assert b["wall"][0]["tint"] == sk.slots["dominant"]["shadow"]
    assert b["wall"][-1]["tint"] == sk.slots["accent"]["base"]


def test_theme_bad_bands_raise(tmp_path):
    import json
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"name": "t", "bands": {"ceiling": [
        {"to": 0.5, "tint": "#111111"}]}}))
    with pytest.raises(ValueError):
        themes.load(str(p))


def _run(shell, tmp_path, extra):
    out = str(tmp_path / "o.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--out", out] + extra)
    return cli.run(args), out


def _wall_colors_by_height(glb):
    from patina import gltf_io
    s = gltf_io.load_glb(glb)
    zmin = min(p.positions[:, 2].min() for m in s.visual_meshes()
               for p in m.primitives if p.vertex_count())
    zmax = max(p.positions[:, 2].max() for m in s.visual_meshes()
               for p in m.primitives if p.vertex_count())
    low, high = [], []
    for m in s.visual_meshes():
        if "wall" not in m.name.lower():
            continue
        for p in m.primitives:
            if p.color is None:
                continue
            frac = (p.positions[:, 2] - zmin) / (zmax - zmin)
            low.extend(p.color[frac < 0.2, :3].tolist())
            high.extend(p.color[frac > 0.95, :3].tolist())
    return np.array(low), np.array(high)


def test_cli_bands_change_wall_by_height(shell, tmp_path):
    res, out = _run(shell, tmp_path, ["--theme", "delco_1997_gas_station"])
    assert res["bands"] == ["exterior_wall", "wall"]
    low, high = _wall_colors_by_height(out)
    # base band is redder (brick), cap band is warmer/brighter (flashing):
    assert low.size and high.size
    assert low[:, 0].mean() - low[:, 2].mean() > high[:, 0].mean() - high[:, 2].mean() \
        or high.mean() > low.mean()          # distinct bands by height


def test_no_bands_flag_and_default_identical(shell, tmp_path):
    r1, o1 = _run(shell, tmp_path / "a", [])              # default theme, no bands declared
    r2, o2 = _run(shell, tmp_path / "b", ["--no-bands"])
    assert "bands" not in r1 and "bands" not in r2
    from patina import gltf_io
    import hashlib
    def h(glb):
        s = gltf_io.load_glb(glb)
        m = hashlib.sha256()
        for mesh in sorted(s.visual_meshes(), key=lambda x: x.name):
            for p in mesh.primitives:
                if p.color is not None:
                    m.update(np.ascontiguousarray(p.color).tobytes())
        return m.hexdigest()
    assert h(o1) == h(o2)
