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
    #: Storey 0's floor plane in the CANONICAL Z-up frame -- see
    #: :func:`blender_to_canonical`. None means "unknown", which falls the
    #: ground families back to the segment minimum (correct for the
    #: single-storey shells that carry no manifest, wrong for anything with a
    #: basement, and recorded as such in the sidecar).
    ground_z: float | None = None
    #: ``(pos, anchor_id)`` per real exterior fixture, positions already in the
    #: canonical frame. Empty means no light manifest was found.
    conduit_targets: tuple = ()


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


def blender_to_canonical(p, up_axis: int) -> tuple:
    """A DC Blender Z-up point in the frame the anchor math runs in.

    COMPOSED from the two conversions that already exist rather than derived by
    hand: :func:`slots.blender_to_patina` puts a DC point in Patina's baked
    glTF space, and :func:`_up_to_z` permutes that into the canonical Z-up
    view. Composing beats deriving because the composition cannot drift away
    from the passes it has to agree with -- and because writing this
    permutation out by hand is exactly the mistake that produced equal and
    opposite errors on two axes three times in one afternoon.

    For a DC export (``up_axis == 1``) the composition works out to
    ``(x, -y, z)``: the VERTICAL COORDINATE IS UNCHANGED, so a Blender-space
    height and a canonical height are the same number. That is what lets
    ``ground_z`` come straight off the slot manifest. It is asserted by
    :func:`test_blender_z_is_canonical_z` rather than trusted.

    ``up_axis == 2`` is a legacy hand-authored Z-up shell, which is already in
    DC's frame and needs no conversion. Such shells carry no DC manifest, so
    this branch exists for completeness, not for the pipeline.
    """
    if up_axis == 2:
        return (float(p[0]), float(p[1]), float(p[2]))
    from .slots import blender_to_patina
    q = np.array([blender_to_patina(p)], dtype=np.float64)
    return tuple(float(v) for v in _up_to_z(q, up_axis)[0])


def conduit_targets(light_manifest, up_axis: int,
                    kinds=("wall_pack", "sign")) -> tuple:
    """``((pos, anchor_id), ...)`` for the exterior fixtures conduit runs to.

    DC derives a wall pack over every exterior door and one storefront sign
    from the real openings, and puts them in ``<name>.lights.json`` already
    stood proud of the wall face (``_WALL_PACK_OUT``, ``_SIGN_OUT``). Taking
    those positions as given is deliberate: it means the conduit needs no face
    math of its own, and no second chance to get a normal backwards.

    Interior kinds (``fluorescent``, ``window``) are not conduit targets --
    nothing runs up an outside wall to a ceiling strip light.
    """
    if not light_manifest:
        return ()
    out = []
    for a in light_manifest.get("anchors", []) or []:
        if a.get("type") not in kinds:
            continue
        pos = a.get("pos")
        if not pos or len(pos) < 3:
            continue
        out.append((blender_to_canonical(pos, up_axis), str(a.get("id", ""))))
    return tuple(out)


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


def _nearest_segment(segs, p):
    """The wall segment a point sits on, or None if it sits on none of them.

    Nearest by distance to the wall PLANE, among segments whose run actually
    covers the point (with a module of slack, since DC stands a fixture proud
    of the face and a door can sit at a segment's end). Returning None rather
    than a best guess matters: a fixture on a wall Patina never classified as
    exterior should drop out, not acquire an invented normal.
    """
    best, best_d = None, None
    for s in segs:
        along = p[s["along"]]
        if not (s["a_min"] - 2.0 <= along <= s["a_max"] + 2.0):
            continue
        d = abs(p[s["axis"]] - s["fixed"])
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best if best_d is not None and best_d <= 2.0 else None


def _conduit_anchors(segs, opts: AnchorOptions, seed: int) -> list[Anchor]:
    """One conduit per REAL exterior fixture, sized to the run it makes.

    RETRACTED RULE, kept because its output looked plausible: conduit used to
    be placed at ``z_lo + 0.75 * (z_hi - z_lo)`` along each wall, on
    ``light_spacing`` centres. On a shell whose segments span basement to
    parapet that evaluates to 5.67 m -- a third-storey height -- and it
    referred to no light whatsoever. It was decorative fiction that happened to
    land on a wall.

    DC already derives every exterior wall pack and the storefront sign from
    the actual door openings and ships them in ``<name>.lights.json``. A
    conduit is the run that FEEDS one, so there is exactly one per fixture and
    it ends where the fixture is.

    Two fields carry more than they used to, both deliberately:

    * ``size`` is the RUN LENGTH from the ground plane up to the fixture, not a
      footprint hint. A conduit's useful dimension is how far it runs, and the
      old value was a constant 0.3 that nothing downstream could have depended
      on.
    * ``tag`` is the DC anchor id, so a conduit in the world is traceable back
      to the light it was drawn for instead of the generic ``exterior_wall``.

    With no light manifest this emits nothing and says so through the count --
    a wall with no fixtures needs no conduit, and inventing one is what the old
    rule did.
    """
    out: list[Anchor] = []
    ground = opts.ground_z
    for pos, aid in opts.conduit_targets:
        seg = _nearest_segment(segs, pos)
        if seg is None:
            continue
        n3 = [0.0, 0.0, 0.0]
        n3[seg["axis"]] = float(seg["normal"][seg["axis"]])
        base = seg["z_lo"] if ground is None else ground
        run = max(0.0, float(pos[2]) - base)
        out.append(Anchor(
            kind="exterior_light",
            pos=(round(float(pos[0]), 3), round(float(pos[1]), 3),
                 round(float(pos[2]), 3)),
            normal=(round(n3[0], 3), round(n3[1], 3), round(n3[2], 3)),
            size=round(run, 3),
            tag=aid or "exterior_wall"))
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
        # A wall segment is bucketed by wall PLANE, so every storey of one
        # facade collapses into a single row: z_lo is the bottom of the
        # FOUNDATION and z_hi the top of the parapet. That is fine for a
        # roofline -- a parapet cap belongs at the top of the building -- and
        # wrong for everything that belongs where a player stands.
        ground = seg["z_lo"] if opts.ground_z is None else opts.ground_z
        if "roofline" in opts.kinds:
            emit("roofline", seg,
                 _points_along(seg["a_min"], seg["a_max"], opts.roofline_spacing),
                 seg["z_hi"], (0.0, 0.0, 1.0), 0.6, opts.roofline_spacing * 0.3)
        if "wall_base" in opts.kinds:
            emit("wall_base", seg,
                 _points_along(seg["a_min"], seg["a_max"], opts.wall_base_spacing),
                 ground, tuple(n3), 0.8, opts.wall_base_spacing * 0.3)
        if "ground_edge" in opts.kinds:
            emit("ground_edge", seg,
                 _points_along(seg["a_min"], seg["a_max"], opts.ground_spacing),
                 ground, (0.0, 0.0, 1.0), 0.4, opts.ground_spacing * 0.2)

    if "exterior_light" in opts.kinds:
        out.extend(_conduit_anchors(segs, opts, seed))

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
