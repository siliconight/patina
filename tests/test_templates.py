"""Painter's seams: paint templates (map skinning) and start skins (model
skinning). Determinism, honest skipping of UV0-less meshes, CLI wiring."""

from __future__ import annotations

import os

import numpy as np

from patina import cli, templates
from patina.mesh import Mesh, MeshKind, Primitive, Scene


def test_paint_templates_written_and_deterministic(tmp_path):
    d1, d2 = str(tmp_path / "a"), str(tmp_path / "b")
    w1 = templates.write_paint_templates(["floor", "wall"], d1, size=128, texel=2.0)
    w2 = templates.write_paint_templates(["floor", "wall"], d2, size=128, texel=2.0)
    assert len(w1) == 2
    for p1, p2 in zip(w1, w2):
        b1, b2 = open(p1, "rb").read(), open(p2, "rb").read()
        assert b1[:8].startswith(b"\x89PNG")
        assert b1 == b2


def _uv_mapped_quad() -> Primitive:
    pos = np.array([[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], np.float32)
    idx = np.array([[0, 1, 2], [0, 2, 3]], np.uint32)
    uv0 = np.array([[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]], np.float32)
    return Primitive(positions=pos, indices=idx, uv0=uv0)


def test_start_skins_written_for_uv0_and_skipped_without(tmp_path):
    scene = Scene(meshes=[
        Mesh(name="prop_a", kind=MeshKind.VISUAL, primitives=[_uv_mapped_quad()]),
        Mesh(name="bare", kind=MeshKind.VISUAL, primitives=[
            Primitive(positions=np.zeros((3, 3), np.float32),
                      indices=np.array([[0, 1, 2]], np.uint32))]),
    ])
    out = str(tmp_path / "skins")
    written, skipped = templates.write_start_skins(scene, out, size=64)
    assert len(written) == 1 and skipped == ["bare"]
    assert os.path.basename(written[0]) == "prop_a.startskin.png"
    # Deterministic bytes.
    out2 = str(tmp_path / "skins2")
    written2, _ = templates.write_start_skins(scene, out2, size=64)
    assert open(written[0], "rb").read() == open(written2[0], "rb").read()


def test_start_skin_triangles_get_unique_colours():
    mesh = Mesh(name="p", kind=MeshKind.VISUAL, primitives=[_uv_mapped_quad()])
    img = np.asarray(templates.start_skin(mesh, size=64))
    colours = np.unique(img.reshape(-1, 3), axis=0)
    # Background + wire + two triangle fills (+ label pixels) at minimum.
    assert len(colours) >= 4


def test_safe_name():
    assert templates.safe_name("wall/north:01") == "wall_north_01"
    assert templates.safe_name("") == "unnamed"


def test_cli_templates_flag(shell, tmp_path):
    out = str(tmp_path / "styled.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--theme", "delco_1997_gas_station",
         "--templates", "--out", out])
    res = cli.run(args)
    tdir = res["templates_dir"]
    assert res["templates"] >= 1
    files = sorted(os.listdir(tdir))
    assert all(f.endswith(".template.png") for f in files)
    # One template per material key that received a tile.
    assert {f.split(".template.png")[0] for f in files} == set(
        os.path.splitext(f)[0] for f in os.listdir(res["textures_dir"])
        if f.endswith(".png"))


def test_cli_start_skins_flag_skips_greybox(shell, tmp_path, capsys):
    out = str(tmp_path / "styled.glb")
    args = cli.build_parser().parse_args([shell, "--start-skins", "--out", out])
    res = cli.run(args)
    # Deli Counter greyboxes carry no authored UV0: all skipped, none written.
    assert res["start_skins"] == 0
