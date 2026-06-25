"""Collision is sacred: the collision mesh set is identical pre/post Patina,
asserted by name + vertex hash (TDD 8.1)."""

from __future__ import annotations

import shutil

from patina import gltf_io
from patina.cli import build_parser, run


def test_collision_signature_unchanged(shell, tmp_path):
    before = gltf_io.load_glb(shell).collision_signature()

    wd = tmp_path / "work"; wd.mkdir(exist_ok=True); dst = wd / "shell.glb"
    shutil.copy(shell, dst)
    shutil.copy(str(shell)[:-4] + ".gameplay.json", str(dst)[:-4] + ".gameplay.json")
    args = build_parser().parse_args([str(dst), "--mode", "procedural"])
    res = run(args)

    after = gltf_io.load_glb(res["output_glb"]).collision_signature()
    assert before == after, "collision geometry changed"
    assert set(before.keys()) == {"floor-colonly"}


def test_collision_tri_count_unchanged(shell, tmp_path):
    raw = gltf_io.load_glb(shell).stats()
    wd = tmp_path / "work"; wd.mkdir(exist_ok=True); dst = wd / "shell.glb"
    shutil.copy(shell, dst)
    shutil.copy(str(shell)[:-4] + ".gameplay.json", str(dst)[:-4] + ".gameplay.json")
    args = build_parser().parse_args([str(dst)])
    res = run(args)
    out = gltf_io.load_glb(res["output_glb"]).stats()
    assert out["collision_tris"] == raw["collision_tris"]
    assert out["collision_meshes"] == raw["collision_meshes"]
