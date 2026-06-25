"""Determinism: same input + seed -> byte-identical output (TDD 8.1)."""

from __future__ import annotations

import shutil

from patina.cli import build_parser, run


def _run(shell_src, workdir, mode):
    workdir.mkdir(parents=True, exist_ok=True)
    dst = workdir / "shell.glb"
    shutil.copy(shell_src, dst)
    gp = str(shell_src)[:-4] + ".gameplay.json"
    shutil.copy(gp, str(dst)[:-4] + ".gameplay.json")
    args = build_parser().parse_args([str(dst), "--mode", mode])
    return run(args)


def test_vertex_color_mode_deterministic(shell, tmp_path):
    r1 = _run(shell, tmp_path / "a", "vertex-color")
    r2 = _run(shell, tmp_path / "b", "vertex-color")
    assert open(r1["output_glb"], "rb").read() == open(r2["output_glb"], "rb").read()
    assert open(r1["manifest"]).read() == open(r2["manifest"]).read()


def test_procedural_mode_deterministic(shell, tmp_path):
    r1 = _run(shell, tmp_path / "a", "procedural")
    r2 = _run(shell, tmp_path / "b", "procedural")
    assert open(r1["output_glb"], "rb").read() == open(r2["output_glb"], "rb").read()
    assert open(r1["manifest"]).read() == open(r2["manifest"]).read()
    # generated textures byte-identical too
    import os
    for fn in os.listdir(r1["textures_dir"]):
        a = os.path.join(r1["textures_dir"], fn)
        b = os.path.join(r2["textures_dir"], fn)
        assert open(a, "rb").read() == open(b, "rb").read(), fn
