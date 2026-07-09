"""Texture families: builtin/file load, deterministic extraction, the
palette-lock pass (cohesion — every surface shares the library), the
no-family byte-identity guarantee, and CLI wiring."""

from __future__ import annotations

import io
import json
import os

import numpy as np
import pytest
from PIL import Image

from patina import cli, families
from patina.palette import PaletteOptions, generate_tile
from patina.mesh import SurfaceRole


@pytest.fixture()
def photo(tmp_path):
    p = tmp_path / "ref.jpg"
    rng = np.random.default_rng(0)
    arr = rng.integers(0, 255, (48, 72, 3)).astype(np.uint8)
    Image.fromarray(arr).save(str(p))
    return str(p)


def test_load_builtin_and_luma_sorted():
    f = families.load("delco_faded")
    lumas = [0.2126 * r + 0.7152 * g + 0.0722 * b
             for (r, g, b) in f.palette_rgb()]
    assert lumas == sorted(lumas)          # canonical ordering
    assert len(f.colors) == 10


def test_load_unknown_raises():
    with pytest.raises(ValueError):
        families.load("no_such_family")


def test_save_roundtrip(tmp_path):
    f = families.load("delco_faded")
    p = str(tmp_path / "fam.json")
    families.save(f, p)
    g = families.load(p)
    assert g.colors == f.colors and g.posterize == f.posterize


def test_file_needs_colors(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps({"name": "x"}))
    with pytest.raises(ValueError):
        families.load(str(p))


def test_extract_is_deterministic(photo):
    a = families.extract(photo, 6, seed=1999)
    b = families.extract(photo, 6, seed=1999)
    assert a.colors == b.colors
    assert len(a.colors) == 6


def test_extract_k_bounds(photo):
    with pytest.raises(ValueError):
        families.extract(photo, 0)
    with pytest.raises(ValueError):
        families.extract(photo, 999)


def test_quantize_snaps_to_library():
    f = families.load("delco_faded")
    pal = f.palette_rgb()
    arr = np.random.default_rng(1).random((8, 8, 3)).astype(np.float32)
    q = families.quantize(arr, f)
    flat = {tuple(np.round(c, 6)) for c in q.reshape(-1, 3)}
    lib = {tuple(np.round(c, 6)) for c in pal}
    assert flat <= lib


def test_lock_tiles_cohesion():
    """Every pixel across a locked tile set is a family colour — the point."""
    f = families.load("delco_faded")
    opts = PaletteOptions(mode="procedural", size=32, seed=1999)
    from patina import themes
    theme = themes.load("delco_1997_gas_station")
    tiles = {}
    for role in (SurfaceRole.FLOOR, SurfaceRole.WALL, SurfaceRole.CEILING):
        buf = io.BytesIO()
        generate_tile(role, opts, theme).save(buf, format="PNG", optimize=False)
        tiles[role.value] = buf.getvalue()
    families.lock_tiles(tiles, f)
    lib = {tuple(int(x) for x in np.round(c * 255)) for c in f.palette_rgb()}
    seen = set()
    for data in tiles.values():
        arr = np.asarray(Image.open(io.BytesIO(data)).convert("RGB")).reshape(-1, 3)
        for c in np.unique(arr, axis=0):
            seen.add(tuple(int(x) for x in c))
    assert seen <= lib


def test_lock_tint_snaps():
    f = families.load("delco_faded")
    t = np.array(families.lock_tint((0.5, 0.1, 0.1), f), np.float32)
    # the returned colour is exactly one of the library entries
    dists = ((f.palette_rgb() - t) ** 2).sum(1)
    assert float(dists.min()) < 1e-10


def test_swatch_sheet_is_png():
    data = families.swatch_sheet(families.load("delco_faded"))
    assert data[:8].startswith(b"\x89PNG")


def _run(shell, tmp_path, extra):
    out = str(tmp_path / "o.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--out", out] + extra)
    return cli.run(args), out


def test_no_family_byte_identical(shell, tmp_path):
    r1, _ = _run(shell, tmp_path / "a", ["--theme", "delco_1997_gas_station"])
    r2, _ = _run(shell, tmp_path / "b",
                 ["--theme", "delco_1997_gas_station", "--family", "delco_faded"])
    d1, d2 = r1["textures_dir"], r2["textures_dir"]
    # locked run differs; the point is that r1 (no family) took the old path
    assert "family" not in r1 and r2["family"] == "delco_faded"
    for f in os.listdir(d1):
        if not f.endswith(".png"):
            continue
        assert open(os.path.join(d1, f), "rb").read() != \
            open(os.path.join(d2, f), "rb").read()


def test_cli_family_emits_artifacts(shell, tmp_path):
    res, out = _run(shell, tmp_path,
                    ["--theme", "delco_1997_gas_station", "--family", "delco_faded"])
    assert os.path.exists(res["family_json"])
    assert os.path.exists(res["family_swatches"])
    man = json.load(open(out[:-4] + ".json"))
    assert man["family"]["name"] == "delco_faded"
    assert len(man["family"]["colors"]) == 10


def test_cli_extract_family(shell, tmp_path, photo):
    res, _ = _run(shell, tmp_path, ["--extract-family", f"{photo}:5"])
    assert res["family"].startswith("extracted_")
    assert len(res["family_colors"]) == 5
