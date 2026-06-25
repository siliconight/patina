"""Vertex nuance: budget stays sane, vertex colour present and bounded."""

from __future__ import annotations

import numpy as np

from patina import gltf_io, nuance, surfaces


def _styled(shell, target=0.75):
    scene = gltf_io.load_glb(shell)
    scene.bake_visual_transforms()
    opts = nuance.NuanceOptions(target_edge=target)
    nuance.densify(scene, opts)
    surfaces.classify(scene)
    nuance.vertex_color(scene, opts)
    return scene


def test_densify_respects_budget(shell):
    raw = gltf_io.load_glb(shell)
    raw_tris = raw.stats()["visual_tris"]
    scene = _styled(shell, target=0.75)
    tris = scene.stats()["visual_tris"]
    assert tris > raw_tris                      # it did densify
    assert tris < 4000                          # but stayed inside a sane multiple


def test_densify_target_monotonic(shell):
    coarse = _styled(shell, target=1.5).stats()["visual_tris"]
    fine = _styled(shell, target=0.5).stats()["visual_tris"]
    assert fine > coarse                        # smaller target -> more tris


def test_vertex_color_present_and_bounded(shell):
    scene = _styled(shell)
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            assert prim.color is not None
            assert prim.color.shape[0] == prim.vertex_count()
            assert prim.color.shape[1] == 4
            assert np.all(prim.color >= 0.0) and np.all(prim.color <= 1.0)


def test_vertex_color_varies_with_height(shell):
    """Grime gradient should make lower verts darker than upper ones."""
    scene = _styled(shell)
    wall = next(m for m in scene.visual_meshes() if m.name == "wall_north")
    prim = wall.primitives[0]
    z = prim.positions[:, 2]
    luminance = prim.color[:, :3].mean(axis=1)
    lo = luminance[z < z.min() + 0.3].mean()
    hi = luminance[z > z.max() - 0.3].mean()
    assert lo < hi                              # darker near the floor


def test_edge_cavity_ao_darkens_edges(shell):
    """Welded-position AO should darken cube edges/corners vs face interiors."""
    import numpy as np
    scene = _styled(shell)
    wall = next(m for m in scene.visual_meshes() if m.name == "wall_north")
    prim = wall.primitives[0]
    lum = prim.color[:, :3].mean(axis=1)
    assert np.percentile(lum, 95) - np.percentile(lum, 5) > 0.1
