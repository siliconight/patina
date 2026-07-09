"""Placement anchors: derived from exterior-wall geometry, correct heights and
normals, deterministic, budget-clamped, opt-in, and never touching geometry."""

from __future__ import annotations

import json
import os

import numpy as np
import pytest

from patina import anchors, cli, gltf_io, surfaces


def _classified(shell):
    scene = gltf_io.load_glb(shell)
    scene.bake_visual_transforms()
    surfaces.classify(scene)
    return scene


def test_anchors_on_exterior_boundary_with_right_heights(shell):
    scene = _classified(shell)
    lo, hi = anchors._visual_aabb(scene)
    a = anchors.generate(scene, anchors.AnchorOptions(), seed=1999)
    assert a, "expected anchors on a boxy shell"
    for anc in a:
        x, y, z = anc.pos
        on_x = abs(abs(x) - max(abs(lo[0]), abs(hi[0]))) < 0.4
        on_y = abs(abs(y) - max(abs(lo[1]), abs(hi[1]))) < 0.4
        assert on_x or on_y, f"{anc.kind} off the exterior boundary: {anc.pos}"
        if anc.kind == "roofline":
            assert abs(z - hi[2]) < 0.3 and anc.normal == (0.0, 0.0, 1.0)
        if anc.kind in ("wall_base", "ground_edge"):
            assert abs(z - lo[2]) < 0.3
        if anc.kind == "wall_base":
            assert abs(anc.normal[2]) < 1e-6      # outward horizontal


def test_anchors_deterministic(shell):
    scene1 = _classified(shell)
    scene2 = _classified(shell)
    a = anchors.generate(scene1, anchors.AnchorOptions(), seed=7)
    b = anchors.generate(scene2, anchors.AnchorOptions(), seed=7)
    assert [(x.kind, x.pos, x.normal) for x in a] == \
           [(x.kind, x.pos, x.normal) for x in b]


def test_budget_clamp(shell):
    scene = _classified(shell)
    a = anchors.generate(scene, anchors.AnchorOptions(
        roofline_spacing=0.2, max_per_kind=5), seed=1)
    counts = anchors.kind_counts(a)
    assert counts.get("roofline", 0) <= 5


def test_kind_filter(shell):
    scene = _classified(shell)
    a = anchors.generate(scene, anchors.AnchorOptions(kinds=("roofline",)), seed=1)
    assert set(anchors.kind_counts(a)) == {"roofline"}


def test_sidecar_shape(shell):
    scene = _classified(shell)
    a = anchors.generate(scene, anchors.AnchorOptions(), seed=1)
    side = anchors.to_sidecar(a, seed=1, source="x.glb")
    assert side["schema"] == "patina-anchors/1"
    assert side["space"] == "baked_world_metres"
    assert sum(side["counts"].values()) == len(a)
    # every anchor record carries pos/normal/size
    for items in side["anchors"].values():
        for it in items:
            assert set(it) >= {"pos", "normal", "size"}


def _run(shell, tmp_path, extra):
    out = str(tmp_path / "o.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--out", out] + extra)
    return cli.run(args), out


def test_cli_anchors_opt_in(shell, tmp_path):
    # off by default
    r_off, _ = _run(shell, tmp_path / "off", [])
    assert "anchors" not in r_off
    # on with flag
    r_on, out = _run(shell, tmp_path / "on", ["--anchors"])
    assert os.path.exists(r_on["anchors"])
    man = json.load(open(out[:-4] + ".json"))
    assert man["anchors"]["counts"] == r_on["anchor_counts"]


def test_cli_anchors_do_not_touch_geometry(shell, tmp_path):
    """The styled .glb is identical whether or not anchors are emitted —
    anchors are metadata only."""
    import hashlib
    def geo(glb):
        s = gltf_io.load_glb(glb)
        m = hashlib.sha256()
        for mesh in sorted(s.meshes, key=lambda x: x.name):
            for p in mesh.primitives:
                m.update(np.ascontiguousarray(p.positions).tobytes())
                if p.color is not None:
                    m.update(np.ascontiguousarray(p.color).tobytes())
        return m.hexdigest()
    _, o1 = _run(shell, tmp_path / "a", ["--theme", "delco_1997_gas_station"])
    _, o2 = _run(shell, tmp_path / "b",
                 ["--theme", "delco_1997_gas_station", "--anchors"])
    assert geo(o1) == geo(o2)


def test_anchor_kinds_cli_filter(shell, tmp_path):
    res, _ = _run(shell, tmp_path, ["--anchors", "--anchor-kinds",
                                    "roofline", "wall_base"])
    assert set(res["anchor_counts"]) <= {"roofline", "wall_base"}
