"""Depth cues (v0.12): saturated shadow gradients, atmospheric recession,
texture temperature — and the byte-identity guarantee when depth is off."""

from __future__ import annotations

import numpy as np

from patina import cli, depth, patterns
from patina.mesh import SurfaceRole


def test_hsv_roundtrip():
    rng = np.random.default_rng(0)
    rgb = rng.random((200, 3)).astype(np.float32)
    back = depth._hsv_to_rgb(depth._rgb_to_hsv(rgb))
    assert np.allclose(rgb, back, atol=1e-4)


def test_shadow_gradient_raises_saturation():
    o = depth.DepthOptions(shadow_sat=0.4, shadow_warm=0.0)
    rgb = np.tile(np.array([0.5, 0.48, 0.46], np.float32), (5, 1))
    shadow = np.linspace(0, 1, 5).astype(np.float32)
    out = depth.apply_shadow_gradient(rgb, shadow, o)

    def sat(c):
        mx, mn = c.max(1), c.min(1)
        return np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    s = sat(out)
    # saturation increases monotonically with shadow weight
    assert s[-1] > s[0]
    assert np.all(np.diff(s) >= -1e-6)


def test_shadow_warm_bias_shifts_temperature():
    warm = depth.DepthOptions(shadow_sat=0.0, shadow_warm=0.3)
    cool = depth.DepthOptions(shadow_sat=0.0, shadow_warm=-0.3)
    rgb = np.tile(np.array([0.5, 0.5, 0.5], np.float32), (3, 1))
    shadow = np.ones(3, np.float32)
    w = depth.apply_shadow_gradient(rgb, shadow, warm)
    c = depth.apply_shadow_gradient(rgb, shadow, cool)
    assert (w[:, 0] - w[:, 2]).mean() > 0        # warm: R up relative to B
    assert (c[:, 0] - c[:, 2]).mean() < 0        # cool: B up relative to R


def test_atmospheric_pulls_toward_target():
    o = depth.DepthOptions(atmos=0.5)
    rgb = np.tile(np.array([0.3, 0.25, 0.2], np.float32), (3, 1))
    recede = np.array([0.0, 0.5, 1.0], np.float32)
    out = depth.apply_atmospheric(rgb, recede, o)
    # no recession -> unchanged; full recession -> halfway to target
    assert np.allclose(out[0], rgb[0])
    assert np.allclose(out[2], rgb[2] * 0.5 + depth._ATMOS_TARGET * 0.5, atol=1e-5)
    # receding surfaces get cooler (blue closes on/exceeds red)
    assert (out[2, 2] - out[2, 0]) > (rgb[2, 2] - rgb[2, 0])


def test_recession_weight_height_and_radial():
    pos = np.array([[0, 0, 0.0], [0, 0, 1.0], [5, 0, 0.0]], np.float32)
    centroid = np.array([0, 0, 0.0], np.float32)
    # height only
    wh = depth.recession_weight(pos, 2, (0.0, 1.0), centroid,
                                depth.DepthOptions(atmos=1, atmos_height=1))
    assert wh[1] > wh[0]                          # higher recedes more
    # radial only
    wr = depth.recession_weight(pos, 2, (0.0, 1.0), centroid,
                                depth.DepthOptions(atmos=1, atmos_radial=1))
    assert wr[2] > wr[0]                          # farther recedes more


def test_presets_and_off():
    assert not depth.DepthOptions.preset("off").active()
    assert depth.DepthOptions.preset("delco").active()
    assert "delco" in depth.preset_names()


def test_inactive_is_noop():
    o = depth.DepthOptions()
    rgb = np.random.default_rng(1).random((10, 3)).astype(np.float32)
    assert np.array_equal(depth.apply_shadow_gradient(rgb, np.ones(10), o), rgb)
    assert np.array_equal(depth.apply_atmospheric(rgb, np.ones(10), o), rgb)


# --- pattern texture temperature ------------------------------------------- #

def test_pattern_temp_zero_identical():
    base = np.array([0.5, 0.5, 0.5], np.float32)
    a = patterns.generate("k", {"type": "tile", "cells": 6, "jitter": 0.1},
                          size=48, seed=2, base=base, variants=[])
    b = patterns.generate("k", {"type": "tile", "cells": 6, "jitter": 0.1,
                                "temp": 0.0}, size=48, seed=2, base=base, variants=[])
    assert np.array_equal(a, b)


def test_pattern_temp_widens_warm_cool_spread():
    base = np.array([0.5, 0.5, 0.5], np.float32)
    a = patterns.generate("k", {"type": "tile", "cells": 6, "jitter": 0.1},
                          size=48, seed=2, base=base, variants=[])
    c = patterns.generate("k", {"type": "tile", "cells": 6, "jitter": 0.1,
                                "temp": 0.15}, size=48, seed=2, base=base, variants=[])
    assert (c[..., 0] - c[..., 2]).std() > (a[..., 0] - a[..., 2]).std()


def test_temp_validation():
    import pytest
    with pytest.raises(ValueError):
        patterns.validate_spec({"type": "tile", "temp": 0.9}, "here")


# --- CLI byte-identity ------------------------------------------------------ #

def _run(shell, tmp_path, extra):
    out = str(tmp_path / "o.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--out", out] + extra)
    return cli.run(args), out


def _vhash(glb):
    from patina import gltf_io
    import hashlib
    s = gltf_io.load_glb(glb)
    h = hashlib.sha256()
    for m in sorted(s.visual_meshes(), key=lambda x: x.name):
        for p in m.primitives:
            if p.color is not None:
                h.update(np.ascontiguousarray(p.color).tobytes())
    return h.hexdigest()


def test_depth_off_byte_identical(shell, tmp_path):
    r1, o1 = _run(shell, tmp_path / "a", ["--theme", "delco_1997_gas_station"])
    r2, o2 = _run(shell, tmp_path / "b",
                  ["--theme", "delco_1997_gas_station", "--depth", "off"])
    assert "depth" not in r1 and "depth" not in r2
    assert _vhash(o1) == _vhash(o2)


def test_depth_on_changes_and_raises_saturation(shell, tmp_path):
    _, o_off = _run(shell, tmp_path / "a", ["--theme", "delco_1997_gas_station"])
    r_on, o_on = _run(shell, tmp_path / "b",
                      ["--theme", "delco_1997_gas_station", "--depth", "delco"])
    assert r_on["depth"] == "delco"
    assert _vhash(o_off) != _vhash(o_on)
    from patina import gltf_io

    def mean_sat(glb):
        s = gltf_io.load_glb(glb)
        c = np.vstack([p.color[:, :3] for m in s.visual_meshes()
                       for p in m.primitives if p.color is not None])
        mx, mn = c.max(1), c.min(1)
        return float(np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0).mean())
    assert mean_sat(o_on) > mean_sat(o_off)
