"""Art-bash overrides: CLI/file parsing, field-wise precedence, image import
(PS1-ification + raw passthrough), theme substitution and alias-break, the
no-override byte-identity guarantee, and CLI integration."""

from __future__ import annotations

import io
import json
import os

import numpy as np
import pytest
from PIL import Image

from patina import cli, overrides, palette, themes
from patina.mesh import SurfaceRole
from patina.palette import PaletteOptions


@pytest.fixture()
def ref_image(tmp_path):
    p = tmp_path / "ref.jpg"
    arr = (np.random.default_rng(0).integers(0, 255, (60, 100, 3))).astype(np.uint8)
    Image.fromarray(arr).save(str(p))
    return str(p)


def test_parse_cli_colour_vs_image(ref_image):
    o = overrides.parse_cli([f"exterior_wall={ref_image}", "floor=#3b3a36,#45433d"])
    assert o["exterior_wall"].image == ref_image
    assert o["floor"].albedo == ["#3b3a36", "#45433d"]
    assert o["exterior_wall"].albedo == []


@pytest.mark.parametrize("bad", [
    "floor",                       # no '='
    "floor=notahex",               # not hex, not image ext
    "nope=#123456",                # unknown key
    "floor=/does/not/exist.png",   # missing image
    "floor=#12345",                # bad hex
])
def test_parse_cli_rejects(bad):
    with pytest.raises(ValueError):
        overrides.parse_cli([bad])


def test_load_file_and_relative_image(tmp_path, ref_image):
    # image referenced relatively resolves next to the json
    rel = os.path.basename(ref_image)
    os.rename(ref_image, tmp_path / rel)
    p = tmp_path / "bash.json"
    p.write_text(json.dumps({
        "exterior_wall": {"image": rel},
        "floor": {"albedo": ["#2f2e2b"], "pattern": {"type": "checker", "cells": 4}},
        "wall": {"tint": "#6a6455"},
    }))
    o = overrides.load_file(str(p))
    assert os.path.isabs(o["exterior_wall"].image)
    assert os.path.exists(o["exterior_wall"].image)
    assert o["floor"].pattern["type"] == "checker"
    assert o["wall"].tint == "#6a6455"


def test_load_file_rejects_unknown_field(tmp_path):
    p = tmp_path / "bash.json"
    p.write_text(json.dumps({"wall": {"colour": "#fff"}}))
    with pytest.raises(ValueError):
        overrides.load_file(str(p))


def test_merge_is_field_wise_and_later_wins():
    a = {"wall": overrides.Override(image="a.png", tint="#111111")}
    b = {"wall": overrides.Override(albedo=["#222222"], tint="#333333")}
    # need real files? merge doesn't validate; safe to use fake paths here.
    m = overrides.merge(a, b)
    assert m["wall"].image == "a.png"       # kept from a
    assert m["wall"].albedo == ["#222222"]  # added by b
    assert m["wall"].tint == "#333333"      # b wins


def test_apply_to_theme_breaks_alias_for_overridden_key():
    theme = themes.load("default")   # aliases exterior_wall -> wall
    assert theme.material_key("exterior_wall") == "wall"
    eff = overrides.apply_to_theme(theme, {"exterior_wall": overrides.Override(
        albedo=["#556677"])})
    assert eff.material_key("exterior_wall") == "exterior_wall"
    assert eff.albedo["exterior_wall"] == ["#556677"]


def test_import_tile_processed_is_square_posterized(ref_image):
    opts = PaletteOptions(mode="procedural", size=64, posterize=8)
    data = palette.import_tile(ref_image, opts, process=True)
    im = Image.open(io.BytesIO(data))
    assert im.size == (64, 64) and im.mode == "RGB"
    # posterize to 8 levels => <= 8**3 distinct colours, far fewer than source
    assert len(np.unique(np.asarray(im).reshape(-1, 3), axis=0)) <= 8 ** 3


def test_import_tile_raw_passthrough(ref_image):
    opts = PaletteOptions(mode="procedural", size=64, posterize=8)
    data = palette.import_tile(ref_image, opts, process=False)
    im = Image.open(io.BytesIO(data))
    assert im.size == (100, 60)   # untouched original dimensions


def test_apply_images_replaces_only_present_keys(ref_image):
    opts = PaletteOptions(mode="procedural", size=32, posterize=8)
    tiles = {"wall": b"original", "floor": b"original"}
    o = {"wall": overrides.Override(image=ref_image),
         "roof": overrides.Override(image=ref_image)}  # roof absent from tiles
    replaced = overrides.apply_images(tiles, o, opts)
    assert replaced == ["wall"]
    assert tiles["wall"] != b"original" and tiles["floor"] == b"original"


def _run(shell, tmp_path, extra):
    out = str(tmp_path / "o.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--out", out] + extra)
    return cli.run(args), out


def test_no_override_is_byte_identical(shell, tmp_path):
    """The v0.3 guarantee holds: no overrides -> same tiles on disk."""
    r1, _ = _run(shell, tmp_path / "a", ["--theme", "delco_1997_gas_station"])
    r2, _ = _run(shell, tmp_path / "b",
                 ["--theme", "delco_1997_gas_station", "--override", "floor=#000000"])
    d1, d2 = r1["textures_dir"], r2["textures_dir"]
    # every key except the overridden 'floor' is identical between runs
    for f in os.listdir(d1):
        if not f.endswith(".png"):
            continue
        a = open(os.path.join(d1, f), "rb").read()
        b = open(os.path.join(d2, f), "rb").read()
        if f == "floor.png":
            assert a != b
        else:
            assert a == b, f


def test_cli_image_override_end_to_end(shell, tmp_path, ref_image):
    res, _ = _run(shell, tmp_path, ["--override", f"exterior_wall={ref_image}"])
    assert res["overrides_imaged"] == ["exterior_wall"]
    assert "exterior_wall" in res["overrides"]
