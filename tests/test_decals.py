"""Decal pass: seeded determinism, role targeting, density scaling, and the
non-destructive guarantee (geometry untouched by placement)."""

from __future__ import annotations

import shutil

import numpy as np

from patina import decals, gltf_io, surfaces, themes
from patina.cli import build_parser, run

_GAS = "delco_1997_gas_station"


def _styled_scene(shell):
    scene = gltf_io.load_glb(shell)
    scene.bake_visual_transforms()
    surfaces.classify(scene)
    return scene


def test_placements_deterministic(shell):
    t = themes.load(_GAS)
    a = decals.place(_styled_scene(shell), t, seed=1999)
    b = decals.place(_styled_scene(shell), t, seed=1999)
    assert a == b
    assert a, "gas station theme should place at least one decal on the shell"
    c = decals.place(_styled_scene(shell), t, seed=2000)
    assert a != c, "different seed should reshuffle placements"


def test_textures_deterministic():
    for dtype in ("water_stain", "oil_stain", "rust_streak", "totally_unknown"):
        assert (decals.generate_texture(dtype, 1999)
                == decals.generate_texture(dtype, 1999))
    assert (decals.generate_texture("water_stain", 1999)
            != decals.generate_texture("water_stain", 2000))


def test_placements_respect_roles(shell):
    scene = _styled_scene(shell)
    t = themes.load(_GAS)
    placed = decals.place(scene, t, seed=1999)

    # Each placement's face normal must be consistent with at least one of
    # the roles its spec targets (up-facing for floor/roof, down-facing for
    # ceiling, near-horizontal for wall roles).
    roles_by_type = {s.type: set(s.roles) for s in t.decals}
    up_roles = {"floor", "roof"}
    down_roles = {"ceiling"}
    side_roles = {"wall", "exterior_wall", "trim", "unknown"}
    for p in placed:
        nz = float(np.array(p.normal)[2])
        allowed = roles_by_type[p.type]
        ok = ((allowed & up_roles and nz >= 0.7)
              or (allowed & down_roles and nz <= -0.7)
              or (allowed & side_roles and abs(nz) < 0.7))
        assert ok, f"{p.type} landed on a face outside its target roles: {p}"


def test_density_scale_and_budget(shell):
    scene = _styled_scene(shell)
    t = themes.load(_GAS)
    base = decals.place(scene, t, seed=1999, density_scale=1.0)
    none = decals.place(scene, t, seed=1999, density_scale=0.0)
    heavy = decals.place(scene, t, seed=1999, density_scale=50.0)
    assert none == []
    assert len(heavy) >= len(base)
    # Hard budget: never more than max_count per spec.
    per_type: dict[str, int] = {}
    for p in heavy:
        per_type[p.type] = per_type.get(p.type, 0) + 1
    caps = {s.type: s.max_count for s in t.decals}
    for dtype, n in per_type.items():
        assert n <= caps[dtype]


def test_cli_themed_run_end_to_end(shell, tmp_path):
    wd = tmp_path / "work"; wd.mkdir(); dst = wd / "shell.glb"
    shutil.copy(shell, dst)
    shutil.copy(str(shell)[:-4] + ".gameplay.json", str(dst)[:-4] + ".gameplay.json")

    before = gltf_io.load_glb(str(dst)).collision_signature()
    args = build_parser().parse_args(
        [str(dst), "--mode", "procedural", "--theme", _GAS])
    res = run(args)

    # Collision sacred, themed or not.
    after = gltf_io.load_glb(res["output_glb"]).collision_signature()
    assert before == after

    import json, os
    man = json.load(open(res["manifest"]))
    assert man["theme"]["name"] == _GAS
    assert man["decals"]["instances"], "themed run should emit decal instances"
    for dtype, rel in man["decals"]["textures"].items():
        assert os.path.exists(os.path.join(os.path.dirname(res["manifest"]), rel)), dtype
    # Every instance type resolves to a texture (validate() enforces too).
    types = set(man["decals"]["textures"])
    assert {i["type"] for i in man["decals"]["instances"]} <= types


def test_no_decals_flag(shell, tmp_path):
    wd = tmp_path / "work"; wd.mkdir(); dst = wd / "shell.glb"
    shutil.copy(shell, dst)
    shutil.copy(str(shell)[:-4] + ".gameplay.json", str(dst)[:-4] + ".gameplay.json")
    args = build_parser().parse_args([str(dst), "--theme", _GAS, "--no-decals"])
    res = run(args)
    import json
    man = json.load(open(res["manifest"]))
    assert man["decals"]["instances"] == []
