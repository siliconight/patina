"""Box-projection UVs (TDD 5.2, phase P3).

Every Deli Counter face is axis-aligned, so UVs are nearly free: project each
face along its dominant world-space normal at a fixed texel density. A
checker/trim texture then reads at a consistent scale across walls of different
dimensions.

**The I-5 trap, handled:** Deli Counter scales unit cubes non-uniformly via
node transform. If UVs were computed in *local* space, texel density would
smear on stretched faces. Patina bakes the node transform into the vertices
before any stage (see :meth:`Scene.bake_visual_transforms`), so positions here
are already world-space metres and density is uniform by construction.

UVs land in the **second** UV channel (``uv1``) so vertex colour (channel 0
semantics) and texture can coexist; the PS1 shader mixes them.
"""

from __future__ import annotations

import numpy as np

from .mesh import Primitive, Scene


def _dominant_axis(face_normal: np.ndarray) -> int:
    return int(np.argmax(np.abs(face_normal)))


# For projection along axis A, the two in-plane axes (u, v).
_PLANE = {0: (1, 2), 1: (0, 2), 2: (0, 1)}


def project(scene: Scene, texel: float = 1.0) -> None:
    """Assign world-space box-projection UVs into ``uv1`` for visual meshes.

    ``texel`` is world metres per texture tile (one full 0..1 UV span).
    """
    inv = 1.0 / max(texel, 1e-6)
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            uv = np.zeros((prim.vertex_count(), 2), np.float32)
            tris = prim.positions[prim.indices]
            fn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
            for t, (tri, n) in enumerate(zip(prim.indices, fn)):
                au, av = _PLANE[_dominant_axis(n)]
                for vi in tri:
                    p = prim.positions[vi]
                    uv[vi] = (p[au] * inv, p[av] * inv)
            prim.uv1 = uv


def density_report(scene: Scene, texel: float) -> dict:
    """Per-face texels-per-metre ratio; used by the offline uniformity test.

    For a correct box projection every face should report ~1/texel along both
    axes regardless of how the face was scaled. Returns summary stats.
    """
    expected = 1.0 / max(texel, 1e-6)
    ratios = []
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.uv1 is None:
                continue
            tris_p = prim.positions[prim.indices]
            tris_uv = prim.uv1[prim.indices]
            for wp, wu in zip(tris_p, tris_uv):
                world_e = np.linalg.norm(wp[1] - wp[0]) + np.linalg.norm(wp[2] - wp[0])
                uv_e = np.linalg.norm(wu[1] - wu[0]) + np.linalg.norm(wu[2] - wu[0])
                if world_e > 1e-6:
                    ratios.append(uv_e / world_e)
    ratios = np.array(ratios) if ratios else np.array([0.0])
    return {
        "expected_ratio": expected,
        "mean_ratio": float(ratios.mean()),
        "min_ratio": float(ratios.min()),
        "max_ratio": float(ratios.max()),
        "max_rel_error": float(np.max(np.abs(ratios - expected)) / expected),
    }
