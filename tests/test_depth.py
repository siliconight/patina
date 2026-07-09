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
    # a chromatic base (warm palette) — multiplicative gain amplifies existing
    # chroma; a fully neutral grey would (correctly) stay neutral.
    rgb = np.tile(np.array([0.55, 0.45, 0.38], np.float32), (5, 1))
    shadow = np.linspace(0, 1, 5).astype(np.float32)
    out = depth.apply_shadow_gradient(rgb, shadow, o)

    def sat(c):
        mx, mn = c.max(1), c.min(1)
        return np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    s = sat(out)
    # saturation increases monotonically with shadow weight
    assert s[-1] > s[0]
    assert np.all(np.diff(s) >= -1e-6)


def test_neutral_stays_neutral_under_saturation():
    # the Lux-composition guarantee: a neutral grey gains no invented hue.
    o = depth.DepthOptions(shadow_sat=0.5, shadow_warm=0.0)
    grey = np.tile(np.array([0.5, 0.5, 0.5], np.float32), (5, 1))
    out = depth.apply_shadow_gradient(grey, np.ones(5, np.float32), o)
    assert np.allclose(out, grey, atol=1e-4)


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


def test_lux_preset_defers_tint_and_distance():
    """The Lux-composition preset: keeps saturation (form), zero temperature
    bias (Lux owns shadow colour), height-only recession (Lux fog owns
    distance)."""
    lux = depth.DepthOptions.preset("lux")
    assert lux.shadow_sat > 0            # form kept
    assert lux.shadow_warm == 0.0        # temperature deferred to Lux
    assert lux.atmos_radial == 0.0       # distance haze deferred to Lux fog
    assert lux.atmos_height > 0          # gentle height recession only
    # on a neutral grey it injects no hue at all
    grey = np.tile(np.array([0.5, 0.5, 0.5], np.float32), (4, 1))
    out = depth.apply_shadow_gradient(grey, np.ones(4, np.float32), lux)
    assert np.allclose(out, grey, atol=1e-4)


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


def test_depth_on_changes_and_concentrates_saturation(shell, tmp_path):
    _, o_off = _run(shell, tmp_path / "a", ["--theme", "delco_1997_gas_station"])
    r_on, o_on = _run(shell, tmp_path / "b",
                      ["--theme", "delco_1997_gas_station", "--depth", "delco"])
    assert r_on["depth"] == "delco"
    assert _vhash(o_off) != _vhash(o_on)
    from patina import gltf_io

    def sat_hi(glb):
        # the deepest-shadow tail (p99) is where the saturated-gradient cue
        # lives. Atmosphere desaturates the broad middle (mean/p90 fall), but
        # the deepest cavities should get MORE saturated — that's the form cue.
        s = gltf_io.load_glb(glb)
        c = np.vstack([p.color[:, :3] for m in s.visual_meshes()
                       for p in m.primitives if p.color is not None])
        mx, mn = c.max(1), c.min(1)
        sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
        return float(np.percentile(sat, 99))
    assert sat_hi(o_on) > sat_hi(o_off)


# --- arcade near/far separation (v0.14) ------------------------------------ #

def test_separation_near_punch_far_wash():
    o = depth.DepthOptions(near_sat=0.4, far_wash=0.6)
    rgb = np.tile(np.array([0.6, 0.42, 0.36], np.float32), (3, 1))
    recede = np.array([0.0, 0.5, 1.0], np.float32)   # near, mid, far
    out = depth.apply_separation(rgb, recede, o)

    def sat(c):
        mx, mn = c.max(), c.min()
        return (mx - mn) / max(mx, 1e-6)
    # near stays punchy, far washes to near-grey
    assert sat(out[0]) > sat(out[2])
    # far lifts toward the light haze (lighter than near)
    assert out[2].mean() > out[0].mean()


def test_separation_neutral_stays_neutral():
    # near-punch must not invent hue on a neutral grey (same guarantee as shadow)
    o = depth.DepthOptions(near_sat=0.5)
    grey = np.tile(np.array([0.5, 0.5, 0.5], np.float32), (3, 1))
    out = depth.apply_separation(grey, np.zeros(3, np.float32), o)
    assert np.allclose(out, grey, atol=1e-4)


def test_separation_inactive_noop():
    o = depth.DepthOptions()
    rgb = np.random.default_rng(3).random((8, 3)).astype(np.float32)
    assert np.array_equal(depth.apply_separation(rgb, np.ones(8), o), rgb)


def test_punch_preset():
    p = depth.DepthOptions.preset("punch")
    assert p.near_sat > 0 and p.far_wash > 0
    assert p.shadow_warm == 0.0          # still defers shadow colour to Lux
    assert "punch" in depth.preset_names()
