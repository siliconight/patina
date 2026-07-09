"""Look preview: the composite renders, the multiply darkens as expected, and
the headroom report catches over-dark bakes (the point of the harness)."""

from __future__ import annotations

import numpy as np

from patina import gltf_io, preview, surfaces
from patina.mesh import Mesh, MeshKind, Primitive, Scene


def _box(color):
    c = np.array([[x, y, z] for x in (-1.0, 1) for y in (-1.0, 1)
                  for z in (-1.0, 1)], np.float32)
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1),
             (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    prim = Primitive(positions=c, indices=np.array(faces, np.uint32))
    prim.color = np.hstack([np.full((8, 3), color, np.float32),
                            np.ones((8, 1), np.float32)])
    return Scene(meshes=[Mesh(name="box", kind=MeshKind.VISUAL, primitives=[prim])])


def test_renders_surface_pixels():
    img = preview.render(_box(0.7), preview.PreviewOptions(width=160, height=120))
    assert img.shape == (120, 160, 3)
    bg = preview.PreviewOptions().bg
    surf = np.abs(img.reshape(-1, 3) - np.array(bg)).sum(1) > 0.02
    assert surf.sum() > 100          # the box actually drew


def test_band_quantizes():
    o = preview.PreviewOptions(band_count=3, shade_min=0.18)
    ndl = np.linspace(-1, 1, 50)
    b = preview._band(ndl, o)
    assert len(np.unique(np.round(b, 3))) <= 4      # ~band_count distinct levels
    assert b.min() >= o.shade_min - 1e-6


def test_darker_vertex_colour_darker_preview():
    def mean_luma(color):
        img = preview.render(_box(color), preview.PreviewOptions(width=160, height=120))
        st = preview.luma_stats(img, preview.PreviewOptions().bg)
        return st["luma_mean"]
    assert mean_luma(0.3) < mean_luma(0.8)          # the multiply darkens


def test_headroom_flags_overdark():
    bright = preview.luma_stats(
        preview.render(_box(0.7), preview.PreviewOptions(width=160, height=120)),
        preview.PreviewOptions().bg)
    dark = preview.luma_stats(
        preview.render(_box(0.18), preview.PreviewOptions(width=160, height=120)),
        preview.PreviewOptions().bg)
    assert bright["headroom_ok"] is True
    assert dark["headroom_ok"] is False             # the harness catches it


def test_deterministic():
    a = preview.render(_box(0.6), preview.PreviewOptions(width=120, height=90))
    b = preview.render(_box(0.6), preview.PreviewOptions(width=120, height=90))
    assert np.array_equal(a, b)


def test_empty_scene_no_crash():
    img = preview.render(Scene(meshes=[]), preview.PreviewOptions(width=64, height=64))
    assert img.shape == (64, 64, 3)


def test_cli_preview(shell, tmp_path):
    import os
    from patina import cli
    out = str(tmp_path / "o.glb")
    args = cli.build_parser().parse_args(
        [shell, "--mode", "procedural", "--theme", "delco_1997_gas_station",
         "--preview", "--out", out])
    res = cli.run(args)
    assert os.path.exists(res["preview"])
    assert "headroom_ok" in res["preview_stats"]
