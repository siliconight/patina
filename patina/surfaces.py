"""Surface-role classification.

Each visual face is tagged floor / wall / exterior_wall / ceiling / roof /
trim. The role drives the vertex-colour base tint (5.1), the per-surface
material / texture variant (5.3) and, since v0.2, theme decal targeting.
Roles are deliberately coarse — the PS1 look does not need more than this to
read.

Primary signal is the *world-space* face normal (so it must run after
:meth:`Scene.bake_visual_transforms`). Two refinements use the scene's visual
AABB, matching the bashing-brief buckets that matter most for theming:

* **exterior_wall** — a vertical face whose centroid sits on the outer AABB
  boundary along its normal's dominant horizontal axis, with the normal
  pointing outward. Rectangular shells classify exactly; concave footprints
  (L-shapes) conservatively leave inner-corner exterior faces as ``wall``,
  which only means they get interior treatment — never a gameplay change.
* **roof** — an up-facing face whose centroid sits at the top of the visual
  AABB (within tolerance).

A mesh may still be promoted wholesale by a ``gameplay.json`` surface hint
(``{"mesh": <name>, "role": ...}``) or by an obvious name token — authored
intent overrides geometry, and now accepts any :class:`SurfaceRole` value.
"""

from __future__ import annotations

import numpy as np

from .mesh import Mesh, Scene, SurfaceRole

# cos of the angle that separates "horizontal" from "vertical" faces.
_UP_THRESHOLD = 0.7

# How close (metres) a face centroid must sit to the visual AABB boundary to
# read as exterior wall / roof. Deli Counter walls are ~0.2 m thick; half of
# that plus slack.
_BOUNDARY_TOL = 0.25

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


def _visual_aabb(scene: Scene):
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    any_pts = False
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.vertex_count():
                lo = np.minimum(lo, prim.positions.min(0))
                hi = np.maximum(hi, prim.positions.max(0))
                any_pts = True
    return (lo, hi) if any_pts else (np.zeros(3), np.zeros(3))


def classify(scene: Scene) -> None:
    """Fill ``prim.face_roles`` for every visual primitive in place."""
    hints = _hinted_roles(scene)
    lo, hi = _visual_aabb(scene)
    for mesh in scene.visual_meshes():
        forced = hints.get(mesh.name)
        if forced is None and any(tok in mesh.name.lower() for tok in _TRIM_TOKENS):
            forced = SurfaceRole.TRIM
        for prim, fn in _face_normals(mesh):
            roles = np.empty(fn.shape[0], dtype=object)
            up = fn[:, 2] >= _UP_THRESHOLD
            down = fn[:, 2] <= -_UP_THRESHOLD
            vertical = ~(up | down)
            roles[:] = SurfaceRole.WALL
            roles[up] = SurfaceRole.FLOOR
            roles[down] = SurfaceRole.CEILING

            centroids = prim.positions[prim.indices].mean(axis=1)   # (T,3)

            # roof: up-facing at the top of the visual AABB.
            roof = up & (centroids[:, 2] >= hi[2] - _BOUNDARY_TOL)
            roles[roof] = SurfaceRole.ROOF

            # exterior wall: vertical face on the AABB boundary along the
            # normal's dominant horizontal axis, normal pointing outward.
            if vertical.any():
                horiz = np.abs(fn[:, :2])                            # (T,2)
                axis = np.argmax(horiz, axis=1)                      # 0=x 1=y
                idx = np.arange(fn.shape[0])
                sgn = np.sign(fn[idx, axis])
                on_hi = (sgn > 0) & (centroids[idx, axis] >= hi[axis] - _BOUNDARY_TOL)
                on_lo = (sgn < 0) & (centroids[idx, axis] <= lo[axis] + _BOUNDARY_TOL)
                roles[vertical & (on_hi | on_lo)] = SurfaceRole.EXTERIOR_WALL

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
