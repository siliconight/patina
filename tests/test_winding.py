"""Densify must preserve triangle winding.

Godot back-face-culls by default, so a face wound backwards after densification
simply disappears from one side (walls, shelves, counters). The grid rebuild
infers a corner loop whose orientation is arbitrary relative to the source face;
without a correction, ~half of all faces flip.

These tests assert the invariant: every generated triangle's geometric normal
agrees with its averaged exported vertex normal (dot >= 0). The first case uses
an *adversarial* quad whose inferred loop orientation opposes its true normal,
so it reverses pre-fix — that's what gives this test teeth (the shared shell
fixture happens to wind cleanly and would pass even unfixed).
"""

from __future__ import annotations

import numpy as np

from patina import gltf_io, nuance
from patina.mesh import Mesh, MeshKind, Primitive, Scene

_TOL = 1e-4


def _reversed_count(scene: Scene):
    """(reversed, total) visual triangles, geometric normal vs exported normal."""
    bad = total = 0
    for mesh in scene.visual_meshes():
        for p in mesh.primitives:
            if p.normals is None:
                continue
            tris = p.positions[p.indices]
            gn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
            ln = np.linalg.norm(gn, axis=1, keepdims=True)
            gn = np.divide(gn, ln, out=np.zeros_like(gn), where=ln > 1e-12)
            vn = p.normals[p.indices].mean(axis=1)        # avg exported vert normal
            dots = (gn * vn).sum(axis=1)
            bad += int((dots < -_TOL).sum())
            total += len(dots)
    return bad, total


def _adversarial_scene() -> Scene:
    """A unit quad whose source winding is +Z but whose unique-order corner
    loop infers -Z, so the grid rebuild reverses it without the fix."""
    pos = np.array([[0, 0, 0], [0, 1, 0], [1, 0, 0], [1, 1, 0]], np.float32)
    nrm = np.tile([0.0, 0.0, 1.0], (4, 1)).astype(np.float32)
    idx = np.array([[0, 2, 3], [0, 3, 1]], np.uint32)     # correct +Z winding
    prim = Primitive(positions=pos, indices=idx, normals=nrm)
    return Scene(meshes=[Mesh(name="quad", kind=MeshKind.VISUAL, primitives=[prim])])


def test_adversarial_quad_winding_preserved():
    scene = _adversarial_scene()
    nuance.densify(scene, nuance.NuanceOptions(target_edge=0.4))
    prim = scene.visual_meshes()[0].primitives[0]
    assert prim.triangle_count() > 2                       # actually densified
    bad, total = _reversed_count(scene)
    assert bad == 0, f"{bad}/{total} triangles reversed after densify"


def test_shell_winding_preserved(shell):
    scene = gltf_io.load_glb(shell)
    before_bad, _ = _reversed_count(scene)
    assert before_bad == 0                                 # input is clean
    scene.bake_visual_transforms()
    nuance.densify(scene, nuance.NuanceOptions())
    bad, total = _reversed_count(scene)
    assert bad == 0, f"{bad}/{total} triangles reversed after densify"
