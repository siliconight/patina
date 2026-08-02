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


# --------------------------------------------------------------------------- #
# v0.19: the ground plane, and conduit that runs to a real fixture
# --------------------------------------------------------------------------- #
# A wall segment is bucketed by wall PLANE, so every storey of one facade
# collapses into one row spanning foundation to parapet. Measured on
# lf_category5_baie_dore_001_5421: z_lo -4.30, z_hi 9.00, span 13.30 against a
# walkable range of 12.00. wall_base and ground_edge emitted at z_lo, so every
# curb and base course was buried 4.30 m under the street; exterior_light sat
# at 0.75 of that span -- 5.67 m, a third-storey height -- referring to no
# light at all.

def _seg(axis=0, fixed=22.0, a_min=-16.0, a_max=16.0, z_lo=-4.30, z_hi=9.00):
    """One facade's worth of wall, spanning basement to parapet."""
    normal = np.zeros(2)
    normal[axis] = 1.0
    return {"axis": axis, "along": 1 - axis, "normal": normal,
            "fixed": fixed, "a_min": a_min, "a_max": a_max,
            "z_lo": z_lo, "z_hi": z_hi}


def test_blender_z_is_canonical_z():
    """The claim `ground_z` rests on: heights need no conversion.

    `blender_to_canonical` is composed from `blender_to_patina` and `_up_to_z`
    rather than written out, so it cannot drift from the passes it must agree
    with. For a DC export it works out to (x, -y, z) -- the horizontal axes
    move, the vertical one does not.
    """
    assert anchors.blender_to_canonical((7.0, -3.0, 2.45), 1) == (7.0, 3.0, 2.45)
    assert anchors.blender_to_canonical((7.0, -3.0, 2.45), 2) == (7.0, -3.0, 2.45)
    for z in (-4.3, 0.0, 2.85, 9.0):
        assert anchors.blender_to_canonical((1.0, 2.0, z), 1)[2] == z


def test_ground_families_use_the_ground_plane_not_the_foundation():
    """The regression: curbs at 0.00, not -4.30."""
    segs = [_seg()]
    opts = anchors.AnchorOptions(ground_z=0.0,
                                 kinds=("wall_base", "ground_edge"))
    got = {"wall_base": [], "ground_edge": []}
    for a in _emit_with_segments(segs, opts, seed=1999):
        got[a.kind].append(a.pos[2])
    assert got["wall_base"] and got["ground_edge"]
    assert set(got["wall_base"]) == {0.0}
    assert set(got["ground_edge"]) == {0.0}
    assert -4.30 not in got["wall_base"], "still measuring from the foundation"


def test_ground_families_fall_back_to_the_segment_when_no_manifest():
    """A single-storey shell with no slots.json: z_lo IS the ground.

    The fallback is not a shrug -- it is correct for the hand-authored shells
    that carry no manifest, and wrong only for a building with a basement,
    which by construction has a manifest.
    """
    segs = [_seg(z_lo=0.0, z_hi=3.6)]
    opts = anchors.AnchorOptions(ground_z=None, kinds=("ground_edge",))
    zs = {a.pos[2] for a in _emit_with_segments(segs, opts, seed=1999)}
    assert zs == {0.0}


def test_roofline_is_left_alone():
    """A parapet cap a metre above the roof slab is architecture, not a bug."""
    segs = [_seg()]
    opts = anchors.AnchorOptions(ground_z=0.0, kinds=("roofline",))
    zs = {a.pos[2] for a in _emit_with_segments(segs, opts, seed=1999)}
    assert zs == {9.0}


def _emit_with_segments(segs, opts, seed):
    """Drive the placement rules over hand-built segments.

    Segment extraction needs a classified mesh; the placement rules are what is
    under test. Monkeypatching the extractor keeps the test about the arithmetic
    instead of about building a four-storey glTF fixture.
    """
    from patina.mesh import Scene
    real = anchors._wall_segments
    anchors._wall_segments = lambda scene: iter(segs)
    try:
        return anchors._generate_zup(Scene(), opts, seed)
    finally:
        anchors._wall_segments = real


# -- conduit ---------------------------------------------------------------- #

_LIGHTS = {
    "light_manifest_version": "1.1.0",
    "anchors": [
        {"id": "ext_0_N_pack_1", "type": "wall_pack", "pos": [-8.8, 16.15, 2.45]},
        {"id": "ext_0_S_sign", "type": "sign", "pos": [-4.4, -16.2, 2.55]},
        {"id": "r0_ceiling", "type": "fluorescent", "pos": [0.0, 0.0, 3.6]},
        {"id": "ext_0_N_window_1", "type": "window", "pos": [-2.0, 16.0, 1.8]},
    ],
}


def test_conduit_targets_are_exterior_fixtures_only():
    """Nothing runs up an outside wall to a ceiling strip light."""
    got = anchors.conduit_targets(_LIGHTS, 1)
    assert [t[1] for t in got] == ["ext_0_N_pack_1", "ext_0_S_sign"]
    # positions arrive in the canonical frame: y flips, z is untouched
    assert got[0][0] == (-8.8, -16.15, 2.45)


def test_conduit_runs_from_the_ground_to_the_real_fixture():
    """`size` is the RUN LENGTH, `tag` names the light it feeds."""
    segs = [_seg(axis=1, fixed=-16.15, a_min=-22.0, a_max=22.0)]
    opts = anchors.AnchorOptions(
        ground_z=0.0, kinds=("exterior_light",),
        conduit_targets=anchors.conduit_targets(_LIGHTS, 1)[:1])
    out = _emit_with_segments(segs, opts, seed=1999)
    assert len(out) == 1
    a = out[0]
    assert a.pos == (-8.8, -16.15, 2.45)      # AT the fixture
    assert a.size == pytest.approx(2.45)      # ground 0.0 -> fixture 2.45
    assert a.tag == "ext_0_N_pack_1"
    assert a.pos[2] != pytest.approx(5.67)    # the old 0.75-of-the-building rule


def test_no_light_manifest_emits_no_conduit():
    """A conduit runs TO something. With nothing to run to, emit nothing.

    The old rule invented one every `light_spacing` metres regardless.
    """
    assert anchors.conduit_targets(None, 1) == ()
    opts = anchors.AnchorOptions(ground_z=0.0, kinds=("exterior_light",))
    assert _emit_with_segments([_seg()], opts, seed=1999) == []


def test_a_fixture_on_no_classified_wall_is_dropped_not_guessed():
    """Better to lose a conduit than to give it an invented normal."""
    far = (((900.0, 900.0, 2.45), "ext_9_pack"),)
    opts = anchors.AnchorOptions(ground_z=0.0, kinds=("exterior_light",),
                                 conduit_targets=far)
    assert _emit_with_segments([_seg()], opts, seed=1999) == []
