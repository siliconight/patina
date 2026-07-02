"""Themes: builtin loading, validation, and the default-theme compatibility
guarantee (default must reproduce v0.1.x tints / tiles / file set)."""

from __future__ import annotations

import json

import pytest

from patina import themes
from patina.mesh import SurfaceRole


def test_builtins_load():
    for name in themes.builtin_names():
        t = themes.load(name)
        assert t.name == name


def test_default_theme_is_v01_compatible():
    t = themes.load("default")
    # No tint / albedo overrides -> stages fall back to v0.1.x constants.
    assert t.tint == {} and t.albedo == {}
    # New roles alias onto their v0.1.x umbrella roles -> no new tile files.
    assert t.material_key("exterior_wall") == "wall"
    assert t.material_key("roof") == "ceiling"
    assert t.material_key("floor") == "floor"
    assert not t.decals


def test_gas_station_theme_shape():
    t = themes.load("delco_1997_gas_station")
    assert t.palette["primary"] == "#d8c78f"
    assert t.tint_rgb("exterior_wall") is not None
    assert t.albedo_variants("floor")
    assert any(s.rot == "vertical" for s in t.decals)
    # Every decal spec targets valid roles.
    valid = {r.value for r in SurfaceRole}
    for spec in t.decals:
        assert set(spec.roles) <= valid


def test_user_theme_from_json(tmp_path):
    p = tmp_path / "my_theme.json"
    p.write_text(json.dumps({
        "name": "my_theme",
        "albedo": {"wall": ["#112233"]},
        "decals": [{"type": "grime", "roles": ["floor"],
                    "per_100m2": 2.0, "size": [0.2, 0.5]}],
    }))
    t = themes.load(str(p))
    assert t.name == "my_theme"
    assert t.albedo_variants("wall") == [themes._hex_rgb("#112233")]
    assert t.decals[0].type == "grime"


@pytest.mark.parametrize("bad", [
    {"albedo": {"wall": ["#112233"]}},                                 # no name
    {"name": "x", "tint": {"nope": "#112233"}},                        # bad role
    {"name": "x", "tint": {"wall": "red"}},                            # bad hex
    {"name": "x", "albedo": {"wall": []}},                             # empty list
    {"name": "x", "alias": {"wall": "nope"}},                          # bad alias
    {"name": "x", "decals": [{"type": "t", "roles": ["floor"],
                              "per_100m2": 1, "size": [0.5, 0.2]}]},   # min>max
    {"name": "x", "decals": [{"type": "t", "roles": ["floor"],
                              "per_100m2": 1, "size": [0.2, 0.5],
                              "rot": "sideways"}]},                    # bad rot
])
def test_bad_themes_raise(tmp_path, bad):
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        themes.load(str(p))


def test_unknown_theme_name_raises():
    with pytest.raises(ValueError):
        themes.load("no_such_theme")
