"""Placement anchors (v0.8): where dressing goes, not the dressing itself.

The richest art-pass items — roofline units, wall-base props, exterior
lighting, silhouette breakers, storytelling clusters — all add *geometry*,
which a texture tool has no business generating. But the hard, automatable
part of those items isn't the mesh; it's *placement*. Patina already knows the
surface roles, the visual AABB, which faces are roofline, and where the wall
bases meet the ground. So Patina emits **anchors**: seeded world-space points
with a type, a surface normal, and a size hint, written to a
``<out>.anchors.json`` sidecar. A downstream geometry tool (Lux for lights —
same ``.lights.json`` → Lot → Lux bridge convention; Zoo or a dressing kit for
props) reads the anchors and instantiates real meshes. Patina decides *where*;
the geometry tools supply *what*.

This keeps the non-promise intact — Patina still ships zero building geometry —
while turning the deferred geometry wishlist into a clean division of labour.

Anchor kinds (all derived from geometry, none inventing structure):

* ``roofline`` — along the top edge of each exterior wall (HVAC, vents, tanks,
  the silhouette breakers of art-pass step 6). Normal points up.
* ``wall_base`` — along the foot of each exterior wall (dumpsters, pallets,
  electrical boxes, AC units — the props of step 5). Normal points outward.
* ``exterior_light`` — above exterior doors/centres of exterior walls (the
  lighting anchors of step 13). Normal points outward.
* ``ground_edge`` — where exterior walls meet the ground plane (curbs, weeds,
  utility covers — the ground transition of step 15). Normal points up.

Contract: positions/normals are in the styled ``.glb``'s baked world-metre
space (identical to the decal contract). Placement is deterministic — seeded
by ``(seed, "anchors", kind, index)`` — and every anchor is *visual-only
metadata*; nothing here touches collision, and a tool is free to ignore any
anchor. Density is per-linear-metre or per-face, budget-clamped like decals.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .determinism import rng_for
from .mesh import Scene, SurfaceRole

ANCHOR_KINDS = ("roofline", "wall_base", "exterior_light", "ground_edge")


@dataclass
class Anchor:
    kind: str
    pos: tuple[float, float, float]      # world metres (baked)
    normal: tuple[float, float, float]   # unit, world space
    size: float                          # suggested footprint hint, metres
    tag: str = ""                        # optional storytelling hint (role/cluster)


@dataclass
class AnchorOptions:
    roofline_spacing: float = 2.5        # metres between roofline anchors
    wall_base_spacing: float = 3.5       # metres between wall-base props
    light_spacing: float = 5.0           # metres between exterior lights
    ground_spacing: float = 2.0          # metres between ground-edge details
    max_per_kind: int = 64               # budget clamp per kind
    kinds: tuple[str, ...] = ANCHOR_KINDS


def _visual_aabb(scene: Scene):
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.vertex_count():
                lo = np.minimum(lo, prim.positions.min(0))
                hi = np.maximum(hi, prim.positions.max(0))
    return lo, hi


def _exterior_wall_faces(scene: Scene):
    """Yield (centroid, outward_normal, world-z-extent) for exterior-wall faces."""
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.face_roles is None:
                continue
            tris = prim.positions[prim.indices]                  # (T,3,3)
            fn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
            ln = np.linalg.norm(fn, axis=1, keepdims=True)
            fn = np.divide(fn, ln, out=np.zeros_like(fn), where=ln > 1e-9)
            centroids = tris.mean(axis=1)                         # (T,3)
            for t, role in enumerate(prim.face_roles):
                if role == SurfaceRole.EXTERIOR_WALL:
                    yield centroids[t], fn[t], (tris[t, :, 2].min(), tris[t, :, 2].max())


def _wall_segments(scene: Scene):
    """Deduplicated exterior-wall verticals as (centroid_xy, outward_horiz_normal,
    width_estimate, z_lo, z_hi). Collapses the many triangles of one wall panel
    into a few representative segments keyed by (normal-axis, boundary bucket)."""
    buckets: dict[tuple, list] = {}
    lo, hi = _visual_aabb(scene)
    for c, n, (zlo, zhi) in _exterior_wall_faces(scene):
        horiz = np.array([n[0], n[1]])
        h = np.linalg.norm(horiz)
        if h < 1e-6:
            continue
        horiz = horiz / h
        axis = int(np.argmax(np.abs(horiz)))                 # 0=x 1=y wall runs along the other
        along = 1 - axis
        # bucket by which outer boundary and coarse position along the wall
        side = "hi" if horiz[axis] > 0 else "lo"
        key = (axis, side, round(float(c[axis]), 1))
        buckets.setdefault(key, []).append((c, horiz, along, zlo, zhi))
    for key, items in buckets.items():
        cs = np.array([it[0] for it in items])
        horiz = items[0][1]
        along = items[0][2]
        zlo = min(it[3] for it in items)
        zhi = max(it[4] for it in items)
        a_min, a_max = cs[:, along].min(), cs[:, along].max()
        yield {
            "axis": key[0], "along": along, "normal": horiz,
            "fixed": float(cs[:, key[0]].mean()),
            "a_min": float(a_min), "a_max": float(a_max),
            "z_lo": float(zlo), "z_hi": float(zhi),
        }


def _points_along(a_min: float, a_max: float, spacing: float):
    """Evenly spaced parameter values covering a run, endpoints inset half a step."""
    length = a_max - a_min
    if length <= 1e-6:
        return [(a_min + a_max) / 2.0]
    n = max(1, int(round(length / max(spacing, 1e-3))))
    step = length / n
    return [a_min + step * (i + 0.5) for i in range(n)]


def _seg_point(seg, along_val: float, z: float):
    """World position on a wall segment at a given along-value and height."""
    p = np.zeros(3)
    p[seg["axis"]] = seg["fixed"]
    p[seg["along"]] = along_val
    p[2] = z
    return p


def _up_to_z(positions: np.ndarray, up_axis: int) -> np.ndarray:
    """Permute positions so ``up_axis`` becomes Z, keeping a right-handed frame.

    The anchor geometry math is written Z-up (horizontal = axes 0,1; up = 2).
    Rather than thread an axis through every helper, we rotate the scene into a
    canonical Z-up frame on the way in and rotate anchors back on the way out.
    """
    if up_axis == 2:
        return positions
    if up_axis == 1:                    # Y-up (DC glTF): (x,y,z) -> (x,z,y)... 
        return positions[:, [0, 2, 1]]
    return positions[:, [2, 1, 0]]      # X-up (unusual): swap X and Z


def _z_to_up(vec, up_axis: int):
    """Inverse of the axis permutation for a single (x,y,z) tuple/array."""
    x, y, z = vec
    if up_axis == 2:
        return (x, y, z)
    if up_axis == 1:
        return (x, z, y)
    return (z, y, x)


def generate(scene: Scene, opts: AnchorOptions, seed: int,
             up_axis: int = 2) -> list[Anchor]:
    """Compute placement anchors from the classified, baked scene.

    ``up_axis`` (0=X, 1=Y, 2=Z) tells the pass which axis is vertical — 2 for
    legacy Z-up shells, 1 for DC's Y-up glTF exports. Internally the math runs
    Z-up; anchors are permuted back to the scene's frame before returning.
    """
    # Run the whole computation in a temporary Z-up view of the primitives.
    if up_axis != 2:
        saved = []
        for mesh in scene.visual_meshes():
            for prim in mesh.primitives:
                saved.append((prim, prim.positions))
                prim.positions = _up_to_z(prim.positions, up_axis)
    try:
        result = _generate_zup(scene, opts, seed)
    finally:
        if up_axis != 2:
            for prim, pos in saved:
                prim.positions = pos
    if up_axis == 2:
        return result
    # Permute each anchor's pos/normal back to the scene frame.
    out = []
    for a in result:
        p = _z_to_up(a.pos, up_axis)
        n = _z_to_up(a.normal, up_axis)
        out.append(Anchor(kind=a.kind,
                          pos=(round(p[0], 3), round(p[1], 3), round(p[2], 3)),
                          normal=(round(n[0], 3), round(n[1], 3), round(n[2], 3)),
                          size=a.size, tag=a.tag))
    return out


def _generate_zup(scene: Scene, opts: AnchorOptions, seed: int) -> list[Anchor]:
    """Compute placement anchors assuming a Z-up scene (canonical frame)."""
    lo, hi = _visual_aabb(scene)
    segs = list(_wall_segments(scene))
    out: list[Anchor] = []

    def emit(kind, seg, along_vals, z, normal, size, jitter_scale):
        rng = rng_for(seed, "anchors", kind, str(seg["axis"]), str(seg["fixed"]))
        for i, av in enumerate(along_vals):
            j = (rng.random() - 0.5) * jitter_scale
            p = _seg_point(seg, av + j, z)
            out.append(Anchor(kind=kind,
                              pos=(round(float(p[0]), 3), round(float(p[1]), 3),
                                   round(float(p[2]), 3)),
                              normal=(round(float(normal[0]), 3),
                                      round(float(normal[1]), 3),
                                      round(float(normal[2]), 3)),
                              size=size, tag="exterior_wall"))

    for seg in segs:
        n3 = np.array([0.0, 0.0, 0.0])
        n3[seg["axis"]] = seg["normal"][seg["axis"]]
        if "roofline" in opts.kinds:
            emit("roofline", seg,
                 _points_along(seg["a_min"], seg["a_max"], opts.roofline_spacing),
                 seg["z_hi"], (0.0, 0.0, 1.0), 0.6, opts.roofline_spacing * 0.3)
        if "wall_base" in opts.kinds:
            emit("wall_base", seg,
                 _points_along(seg["a_min"], seg["a_max"], opts.wall_base_spacing),
                 seg["z_lo"], tuple(n3), 0.8, opts.wall_base_spacing * 0.3)
        if "exterior_light" in opts.kinds:
            zmid = seg["z_lo"] + 0.75 * (seg["z_hi"] - seg["z_lo"])
            emit("exterior_light", seg,
                 _points_along(seg["a_min"], seg["a_max"], opts.light_spacing),
                 zmid, tuple(n3), 0.3, 0.0)
        if "ground_edge" in opts.kinds:
            emit("ground_edge", seg,
                 _points_along(seg["a_min"], seg["a_max"], opts.ground_spacing),
                 seg["z_lo"], (0.0, 0.0, 1.0), 0.4, opts.ground_spacing * 0.2)

    # Budget clamp per kind (deterministic: keep the first N in emission order).
    clamped: list[Anchor] = []
    counts: dict[str, int] = {}
    for a in out:
        if counts.get(a.kind, 0) < opts.max_per_kind:
            clamped.append(a)
            counts[a.kind] = counts.get(a.kind, 0) + 1
    return clamped


def to_sidecar(anchors: list[Anchor], *, seed: int, source: str,
               space: str = "baked_world_metres",
               building_id: str | None = None) -> dict:
    """The ``<out>.anchors.json`` payload for downstream geometry tools.

    ``space`` names the coordinate frame the positions are in. When aligned to
    DC (v0.9), the caller converts positions to Blender Z-up first and passes
    ``space="spec/Blender Z-up raw coords"`` so anchors round-trip with
    ``gameplay.json`` / ``slots.json`` markers instead of a Patina-only frame.
    ``building_id`` ties the sidecar to the DC building when known.
    """
    by_kind: dict[str, list] = {}
    for a in anchors:
        by_kind.setdefault(a.kind, []).append({
            "pos": list(a.pos), "normal": list(a.normal),
            "size": a.size, "tag": a.tag,
        })
    out = {
        "schema": "patina-anchors/1",
        "source": source,
        "seed": seed,
        "space": space,
        "units": "meters",
        "note": "visual-only placement hints; collision/gameplay untouched",
        "anchors": {k: by_kind.get(k, []) for k in sorted(by_kind)},
        "counts": {k: len(v) for k, v in sorted(by_kind.items())},
    }
    if building_id:
        out["building_id"] = building_id
    return out


def in_blender_space(anchors: list[Anchor]) -> list[Anchor]:
    """Copy of the anchors with positions/normals converted to DC Blender Z-up.

    Patina computes anchors in its baked glTF (Y-up) space; DC's markers and
    slots live in Blender Z-up raw coords. Aligning the emitted sidecar to that
    shared space is what lets Lux/Zoo consume Patina anchors with the same
    transform code they use for DC's own manifests.
    """
    from .slots import patina_to_blender
    out = []
    for a in anchors:
        p = patina_to_blender(a.pos)
        n = patina_to_blender(a.normal)
        out.append(Anchor(kind=a.kind,
                          pos=(round(p[0], 3), round(p[1], 3), round(p[2], 3)),
                          normal=(round(n[0], 3), round(n[1], 3), round(n[2], 3)),
                          size=a.size, tag=a.tag))
    return out


def kind_counts(anchors: list[Anchor]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in anchors:
        counts[a.kind] = counts.get(a.kind, 0) + 1
    return counts
