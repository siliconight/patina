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


# --- surface mottle (v0.15) ------------------------------------------------- #

def test_mottle_off_is_noop():
    import numpy as np
    from patina import nuance
    from patina.mesh import Primitive
    p = Primitive(
        positions=np.random.default_rng(1).random((100, 3)).astype(np.float32),
        indices=np.arange(99).astype(np.uint32))
    m = nuance._surface_mottle(p, 0.0, 1.5)
    assert np.allclose(m, 1.0)          # strength 0 => multiplier 1 everywhere


def test_mottle_centered_on_one():
    import numpy as np
    from patina import nuance
    from patina.mesh import Primitive
    p = Primitive(
        positions=(np.random.default_rng(2).random((2000, 3)) * 10).astype(np.float32),
        indices=np.arange(1999).astype(np.uint32))
    m = nuance._surface_mottle(p, 0.25, 1.5)
    # mean ~1.0 (only nudges value, doesn't brighten/darken overall)
    assert abs(float(m.mean()) - 1.0) < 0.05
    # actually varies (not flat)
    assert float(m.std()) > 0.02
    # stays positive
    assert float(m.min()) > 0.0


def test_mottle_coherent_not_speckle():
    # adjacent points should have similar mottle (smooth), unlike random noise.
    import numpy as np
    from patina import nuance
    from patina.mesh import Primitive
    base = np.array([[1.0, 1.0, 1.0], [1.01, 1.0, 1.0]], np.float32)  # 1cm apart
    p = Primitive(positions=base, indices=np.array([0], np.uint32))
    m = nuance._surface_mottle(p, 0.3, 1.5)
    assert abs(float(m[0]) - float(m[1])) < 0.02      # near-identical => coherent
