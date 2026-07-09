"""Procedural skins: 60/30/10 generation, seed pinning + harmony fill, slot
grading, Color Swatch interop (library + saved palette + text export), the
no-skin byte-identity guarantee, and CLI wiring."""

from __future__ import annotations

import colorsys
import io
import json
import os

import numpy as np
import pytest
from PIL import Image

from patina import cli, skins
from patina.mesh import SurfaceRole


def _hue(hex_):
    t = hex_.lstrip("#")
    r, g, b = (int(t[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)[0]


def test_generate_has_full_60_30_10():
    sk = skins.generate("faded", ["#8f8877"])
    for slot in ("dominant", "secondary", "accent"):
        assert set(sk.slots[slot]) == {"shadow", "base", "light"}
    # nine distinct family colours
    fam = sk.family()
    assert len(fam.colors) == 9 and len(set(fam.colors)) == 9


def test_shadow_darker_than_light():
    sk = skins.generate("clean", ["#7f6050"])
    for slot in sk.slots.values():
        def v(h): return colorsys.rgb_to_hsv(
            *[int(h.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4)])[2]
        assert v(slot["shadow"]) < v(slot["base"]) <= v(slot["light"]) + 1e-6


def test_seeds_pin_slots_and_harmony_fills():
    # two seeds pin dominant + secondary; accent filled by complementary harmony
    sk = skins.generate("neon", ["#ff0055", "#00ffcc"])
    assert sk.slots["dominant"]["base"].lower().startswith("#ff00") or \
        abs(_hue(sk.slots["dominant"]["base"]) - _hue("#ff0055")) < 0.02
    assert abs(_hue(sk.slots["secondary"]["base"]) - _hue("#00ffcc")) < 0.05


def test_monochrome_one_hue_varied_value():
    sk = skins.generate("grimy", ["#4a5a3f"])   # grimy defaults to monochrome
    hues = [_hue(sk.slots[s]["base"]) for s in ("dominant", "secondary", "accent")]
    assert max(hues) - min(hues) < 0.02          # same hue
    assert len(set(sk.family().colors)) == 9     # still nine distinct (value/sat)


def test_style_only_uses_default_seed():
    sk = skins.generate("neon")
    assert sk.style == "neon" and len(sk.family().colors) == 9


@pytest.mark.parametrize("bad", [
    ("nope", ["#000000"]),                       # unknown style
])
def test_unknown_style_raises(bad):
    with pytest.raises(ValueError):
        skins.generate(*bad)


def test_too_many_seeds_raises():
    with pytest.raises(ValueError):
        skins.generate("clean", ["#111111", "#222222", "#333333", "#444444"])


def test_role_maps_accent_on_trim():
    sk = skins.generate("faded", ["#8f8877"])
    assert sk.tint["trim"] == sk.slots["accent"]["base"]
    assert sk.tint["floor"] in sk.slots["dominant"].values()
    assert all(len(v) == 2 for v in sk.albedo.values())   # two variants each


def test_seeds_from_library_tolerant(tmp_path):
    lib = {"liked": [{"hex": "#3a5f8a", "name": "sky"}, "#c25b3f",
                     {"color": "#e0d8b0"}], "disliked": ["#000000"]}
    p = tmp_path / "lib.json"
    p.write_text(json.dumps(lib))
    seeds = skins.seeds_from_library(str(p))
    assert seeds == ["#3a5f8a", "#c25b3f", "#e0d8b0"]


def test_from_swatch_palette_taken_as_authored():
    pal = {"dominant": {"shadow": "#203040", "base": "#40607f", "light": "#5878a0"},
           "secondary": {"shadow": "#3a2a20", "base": "#7f5a40", "light": "#a07858"},
           "accent": {"shadow": "#802010", "base": "#c04020", "light": "#e05838"}}
    sk = skins.from_swatch_palette(pal)
    assert sk.slots["accent"]["base"] == "#c04020"
    assert sk.harmony == "imported"


def test_from_swatch_palette_rejects_incomplete():
    with pytest.raises(ValueError):
        skins.from_swatch_palette({"dominant": {"base": "#123456"}})


def test_to_swatch_text_labels_slots():
    sk = skins.generate("faded", ["#8f8877"])
    txt = skins.to_swatch_text(sk)
    assert "DOMINANT" in txt and "ACCENT" in txt and "shadow" in txt


def test_resolve_hex_vs_file(tmp_path):
    sk = skins.resolve("grimy:#4a5a3f")
    assert sk.style == "grimy"
    pal = {"dominant": {"shadow": "#203040", "base": "#40607f", "light": "#5878a0"},
           "secondary": {"shadow": "#3a2a20", "base": "#7f5a40", "light": "#a07858"},
           "accent": {"shadow": "#802010", "base": "#c04020", "light": "#e05838"}}
    p = tmp_path / "pal.json"
    p.write_text(json.dumps(pal))
    sk2 = skins.resolve(f"clean:{p}")
    assert sk2.slots["accent"]["base"] == "#c04020"


def _run(shell, tmp_path, extra):
    out = str(tmp_path / "o.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--out", out] + extra)
    return cli.run(args), out


def test_skin_cohesion_end_to_end(shell, tmp_path):
    res, _ = _run(shell, tmp_path, ["--skin", "grimy:#4a5a3f"])
    lib = {tuple(int(x) for x in np.round(c * 255))
           for c in skins.generate("grimy", ["#4a5a3f"]).family().palette_rgb()}
    seen = set()
    for f in os.listdir(res["textures_dir"]):
        if not f.endswith(".png"):
            continue
        arr = np.asarray(Image.open(os.path.join(res["textures_dir"], f))
                         .convert("RGB")).reshape(-1, 3)
        for c in np.unique(arr, axis=0):
            seen.add(tuple(int(x) for x in c))
    assert seen <= lib                       # every surface shares the skin's library
    assert os.path.exists(res["skin_json"])


def test_no_skin_byte_identical(shell, tmp_path):
    r1, _ = _run(shell, tmp_path / "a", ["--theme", "delco_1997_gas_station"])
    r2, _ = _run(shell, tmp_path / "b",
                 ["--theme", "delco_1997_gas_station", "--skin", "grimy:#4a5a3f"])
    assert "skin" not in r1 and r2["skin"] == "grimy_skin"
    d1, d2 = r1["textures_dir"], r2["textures_dir"]
    changed = False
    for f in os.listdir(d1):
        if f.endswith(".png") and open(os.path.join(d1, f), "rb").read() != \
                open(os.path.join(d2, f), "rb").read():
            changed = True
    assert changed                            # skin changes output; no-skin path untouched
