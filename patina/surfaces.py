"""Surface-role classification.

Each visual face is tagged floor / wall / ceiling / trim. The role drives the
vertex-colour base tint (5.1) and the per-surface material / texture variant
(5.3). Roles are deliberately coarse — the PS1 look does not need more than
this to read.

Primary signal is the *world-space* face normal (so it must run after
:meth:`Scene.bake_visual_transforms`). A mesh may be promoted wholesale to
``trim`` by a ``gameplay.json`` surface hint (``{"mesh": <name>, "role": ...}``)
or by an obvious name token — that is the one place authored intent overrides
geometry.
"""

from __future__ import annotations

import numpy as np

from .mesh import Mesh, Scene, SurfaceRole

# cos of the angle that separates "horizontal" from "vertical" faces.
_UP_THRESHOLD = 0.7

# Name tokens that read as trim/detail rather than structure.
_TRIM_TOKENS = ("trim", "rail", "counter", "ledge", "sill", "molding", "moulding")


def _hinted_roles(scene: Scene) -> dict[str, SurfaceRole]:
    roles: dict[str, SurfaceRole] = {}
    gp = scene.gameplay or {}
    for entry in gp.get("surfaces", []) or []:
        name = entry.get("mesh")
        role = entry.get("role")
        if name and role:
            try:
                roles[name] = SurfaceRole(role)
            except ValueError:
                pass
    return roles


def _face_normals(mesh: Mesh):
    for prim in mesh.primitives:
        prim.ensure_normals()
        tris = prim.positions[prim.indices]                  # (T,3,3)
        fn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        ln = np.linalg.norm(fn, axis=1, keepdims=True)
        fn = np.divide(fn, ln, out=np.zeros_like(fn), where=ln > 1e-12)
        yield prim, fn


def classify(scene: Scene) -> None:
    """Fill ``prim.face_roles`` for every visual primitive in place."""
    hints = _hinted_roles(scene)
    for mesh in scene.visual_meshes():
        forced = hints.get(mesh.name)
        if forced is None and any(tok in mesh.name.lower() for tok in _TRIM_TOKENS):
            forced = SurfaceRole.TRIM
        for prim, fn in _face_normals(mesh):
            roles = np.empty(fn.shape[0], dtype=object)
            up = fn[:, 2] >= _UP_THRESHOLD
            down = fn[:, 2] <= -_UP_THRESHOLD
            roles[:] = SurfaceRole.WALL
            roles[up] = SurfaceRole.FLOOR
            roles[down] = SurfaceRole.CEILING
            if forced is not None:
                roles[:] = forced
            prim.face_roles = roles


def role_counts(scene: Scene) -> dict[str, int]:
    counts: dict[str, int] = {}
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.face_roles is None:
                continue
            for r in prim.face_roles:
                counts[r.value] = counts.get(r.value, 0) + 1
    return counts
