"""Vertex nuance (TDD 5.1, phase P1): densify + bevel + procedural vertex colour.

This is the single biggest look win and the PS1 shader's required input (PS1
shaders are vertex-lit, so they want geometry that carries vertex colours and
enough density to hold them).

**Shared formula with Deli Counter.** The colour math here is the *same* design
as Deli Counter's shipped ``--vertex-nuance`` pass — the numbers are the
contract, not the bmesh calls:

* per-face base tint: floor ``(0.62, 0.60, 0.58)``, wall ``(0.74, 0.74, 0.76)``,
  ceiling/trim variants;
* times fake-AO that darkens geometric edges/crevices (``AO_STRENGTH 0.45``);
* times a height grime gradient, darker toward each mesh's local floor
  (``GRIME 0.25`` over ``0.6 m``).

Keeping the constants identical means a greybox styled by Patina and one styled
by Deli Counter's own pass read the same.

**Scope of the pure-Python copy (v0.1).** Densify and vertex colour are
implemented natively here and are fully offline-verifiable. *Geometric* bevel —
insetting hard edges by ~1.5 cm so light catches them — is the one sub-step
that wants a real mesh kernel (clamp_overlap, neighbour propagation). In the
pure-Python path it is OFF by default; the edge-cavity term in the vertex-colour
AO stands in for its read (it breaks the "perfect CG box" look without new
geometry). When Deli Counter's bpy pass is importable, :func:`bevel` bridges to
it (the "calls Deli Counter's if present, else vendors a copy" path from 5.1).

**Governing principle (carried over, do not relitigate):** minimal /
readability-first, never "beauty". Just enough to communicate the space.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .mesh import Mesh, Primitive, Scene, SurfaceRole

# Base tints — identical to Deli Counter's --vertex-nuance.
_BASE_TINT = {
    SurfaceRole.FLOOR:   np.array([0.62, 0.60, 0.58], np.float32),
    SurfaceRole.WALL:    np.array([0.74, 0.74, 0.76], np.float32),
    SurfaceRole.CEILING: np.array([0.66, 0.66, 0.64], np.float32),
    SurfaceRole.TRIM:    np.array([0.68, 0.66, 0.64], np.float32),
    SurfaceRole.UNKNOWN: np.array([0.72, 0.72, 0.72], np.float32),
    # New v0.2 roles default to their v0.1.x umbrella tints so the default
    # theme's vertex colours are unchanged. Themed looks override these.
    SurfaceRole.EXTERIOR_WALL: np.array([0.74, 0.74, 0.76], np.float32),
    SurfaceRole.ROOF:          np.array([0.66, 0.66, 0.64], np.float32),
}
_AO_STRENGTH = 0.45
_GRIME_STRENGTH = 0.25
_GRIME_HEIGHT = 0.6


@dataclass
class NuanceOptions:
    densify: bool = True
    bevel: bool = True               # honoured only when the bpy bridge is present
    vertex_color: bool = True
    target_edge: float = 0.75        # metres; ~0.5-1 m per the TDD
    max_subdiv: int = 4
    bevel_offset: float = 0.015      # metres (bridge param)
    ao_strength: float = _AO_STRENGTH
    grime_strength: float = _GRIME_STRENGTH
    grime_height: float = _GRIME_HEIGHT


# --------------------------------------------------------------------------- #
# Densify
# --------------------------------------------------------------------------- #
# Deli Counter faces are axis-aligned rectangles (each face = two coplanar
# triangles, flat-shaded so faces don't share vertices). So instead of
# uniformly quadrupling every triangle -- which explodes a 150-2500 tri shell --
# we grid-subdivide each face to the exact target density and leave thin faces
# alone. That keeps the budget sane (the named risk in TDD 9) and is crack-free
# because faces are independent vertex islands. Non-rectangular islands fall
# back to uniform midpoint subdivision.

_MAX_SEG = 24      # hard cap on subdivisions per face axis (pathological guard)


def _components(prim: Primitive) -> list[np.ndarray]:
    """Indices of triangles grouped into vertex-connected islands (= faces)."""
    parent = list(range(prim.vertex_count()))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for tri in prim.indices:
        union(tri[0], tri[1])
        union(tri[1], tri[2])
    groups: dict[int, list[int]] = {}
    for ti, tri in enumerate(prim.indices):
        groups.setdefault(find(tri[0]), []).append(ti)
    return [np.array(v, np.int32) for v in groups.values()]


def _quad_loop(verts: np.ndarray):
    """Order 4 coplanar corner positions into a CCW loop; None if not a quad."""
    if verts.shape[0] != 4:
        return None
    c = verts.mean(0)
    n = np.cross(verts[1] - verts[0], verts[2] - verts[0])
    ln = np.linalg.norm(n)
    if ln < 1e-9:
        return None
    n /= ln
    u = verts[0] - c
    u /= max(np.linalg.norm(u), 1e-9)
    w = np.cross(n, u)
    ang = np.array([np.arctan2(np.dot(verts[i] - c, w), np.dot(verts[i] - c, u))
                    for i in range(4)])
    return np.argsort(ang)


def _grid_quad(corners, nrm4, uv4, nu, nv):
    """Bilinear grid of a quad; returns pos, nrm, uv, local-index triangles."""
    p0, p1, p2, p3 = corners
    def lin4(arr): return arr if arr is not None else None
    n0, n1, n2, n3 = (nrm4 if nrm4 is not None else (None,) * 4)
    t0, t1, t2, t3 = (uv4 if uv4 is not None else (None,) * 4)
    pos, nrm, uv = [], ([] if nrm4 is not None else None), ([] if uv4 is not None else None)
    for j in range(nv + 1):
        v = j / nv
        for i in range(nu + 1):
            u = i / nu
            top = p0 * (1 - u) + p1 * u
            bot = p3 * (1 - u) + p2 * u
            pos.append(top * (1 - v) + bot * v)
            if nrm is not None:
                nt = n0 * (1 - u) + n1 * u
                nb = n3 * (1 - u) + n2 * u
                m = nt * (1 - v) + nb * v
                ln = np.linalg.norm(m)
                nrm.append(m / ln if ln > 1e-12 else n0)
            if uv is not None:
                tt = t0 * (1 - u) + t1 * u
                tb = t3 * (1 - u) + t2 * u
                uv.append(tt * (1 - v) + tb * v)
    tris = []
    w = nu + 1
    for j in range(nv):
        for i in range(nu):
            a = j * w + i; b = a + 1; cc = a + w; d = cc + 1
            tris.extend([(a, b, cc), (b, d, cc)])
    return (np.array(pos, np.float32),
            np.array(nrm, np.float32) if nrm is not None else None,
            np.array(uv, np.float32) if uv is not None else None,
            np.array(tris, np.uint32))


def _match_winding(grid_pos, grid_idx, src_pos, src_tris):
    """Flip generated triangle winding to match the source face's orientation.

    ``_quad_loop`` sorts corners geometrically but its loop orientation is
    arbitrary relative to the source face, so ``_grid_quad`` may emit every
    triangle wound backwards. Godot back-face-culls by default, so a reversed
    face simply vanishes from one side. We compare the first generated
    triangle's geometric normal against the aggregate normal of the source
    triangles (their winding) and, if they oppose, swap the 2nd/3rd index of
    every generated triangle. This preserves source orientation without making
    materials double-sided or disabling culling.
    """
    if grid_idx.shape[0] == 0:
        return grid_idx
    st = src_pos[src_tris]
    src_n = np.cross(st[:, 1] - st[:, 0], st[:, 2] - st[:, 0]).sum(axis=0)
    a, b, c = grid_pos[grid_idx[0, 0]], grid_pos[grid_idx[0, 1]], grid_pos[grid_idx[0, 2]]
    gen_n = np.cross(b - a, c - a)
    if float(np.dot(gen_n, src_n)) < 0.0:
        grid_idx = grid_idx[:, [0, 2, 1]]
    return grid_idx


def _densify_prim(prim: Primitive, target: float, max_subdiv: int) -> None:
    seg_cap = min(_MAX_SEG, 2 ** max_subdiv if max_subdiv else 1)
    out_pos, out_nrm, out_uv, out_idx = [], [], [], []
    has_n = prim.normals is not None
    has_uv = prim.uv0 is not None
    base = 0
    for comp in _components(prim):
        tri_local = prim.indices[comp]
        vids = np.unique(tri_local)
        corners = prim.positions[vids]
        loop = _quad_loop(corners) if vids.size == 4 else None
        if loop is not None:
            ordered = vids[loop]
            cp = prim.positions[ordered]
            eu = np.linalg.norm(cp[1] - cp[0]); ev = np.linalg.norm(cp[3] - cp[0])
            nu = int(np.clip(np.ceil(eu / target), 1, seg_cap))
            nv = int(np.clip(np.ceil(ev / target), 1, seg_cap))
            n4 = prim.normals[ordered] if has_n else None
            t4 = prim.uv0[ordered] if has_uv else None
            gp, gn, gt, gi = _grid_quad(cp, n4, t4, nu, nv)
            gi = _match_winding(gp, gi, prim.positions, tri_local)
            out_pos.append(gp)
            if has_n: out_nrm.append(gn)
            if has_uv: out_uv.append(gt)
            out_idx.append(gi + base)
            base += gp.shape[0]
        else:
            # Fallback: keep the island's triangles as-is.
            remap = {int(v): base + k for k, v in enumerate(vids)}
            out_pos.append(prim.positions[vids])
            if has_n: out_nrm.append(prim.normals[vids])
            if has_uv: out_uv.append(prim.uv0[vids])
            out_idx.append(np.array([[remap[int(v)] for v in tri] for tri in tri_local],
                                    np.uint32))
            base += vids.size
    prim.positions = np.vstack(out_pos).astype(np.float32)
    prim.normals = np.vstack(out_nrm).astype(np.float32) if has_n else None
    prim.uv0 = np.vstack(out_uv).astype(np.float32) if has_uv else None
    prim.indices = np.vstack(out_idx).astype(np.uint32)


def densify(scene: Scene, opts: NuanceOptions) -> None:
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            _densify_prim(prim, opts.target_edge, opts.max_subdiv)
            prim.face_roles = None     # topology changed; reclassify downstream


# --------------------------------------------------------------------------- #
# Bevel (bridge to Deli Counter's bpy pass when available; else no-op)
# --------------------------------------------------------------------------- #

def _deli_counter_bevel_available() -> bool:
    try:
        import bpy  # noqa: F401  (Blender as a module)
        return True
    except Exception:
        return False


def bevel(scene: Scene, opts: NuanceOptions) -> bool:
    """Geometric bevel of hard edges. Returns True if it actually ran.

    Implemented via the Deli Counter / Blender (bpy) bridge. With no bpy
    present this is a no-op (the edge-cavity AO term stands in for the look),
    and the caller logs that bevel was skipped.
    """
    if not opts.bevel or not _deli_counter_bevel_available():
        return False
    import bmesh
    import bpy
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            bm = bmesh.new()
            verts = [bm.verts.new(p) for p in prim.positions.tolist()]
            bm.verts.ensure_lookup_table()
            for tri in prim.indices.tolist():
                try:
                    bm.faces.new([verts[i] for i in tri])
                except ValueError:
                    pass
            hard = [e for e in bm.edges if len(e.link_faces) == 2
                    and e.calc_face_angle(None) is not None
                    and e.calc_face_angle(0.0) > 0.6]
            if hard:
                bmesh.ops.bevel(bm, geom=hard, offset=opts.bevel_offset,
                                segments=1, clamp_overlap=True, affect="EDGES")
            bm.verts.ensure_lookup_table()
            prim.positions = np.array([v.co[:] for v in bm.verts], np.float32)
            tri_idx = []
            for f in bm.faces:
                vs = [v.index for v in f.verts]
                for k in range(1, len(vs) - 1):
                    tri_idx.append((vs[0], vs[k], vs[k + 1]))
            prim.indices = np.array(tri_idx, np.uint32)
            prim.normals = None
            prim.face_roles = None
            bm.free()
    return True


# --------------------------------------------------------------------------- #
# Procedural vertex colour (the load-bearing look win)
# --------------------------------------------------------------------------- #

def _vertex_roles(prim: Primitive) -> np.ndarray:
    """Majority role per vertex from incident faces (box faces don't share)."""
    votes = [dict() for _ in range(prim.vertex_count())]
    for tri, role in zip(prim.indices, prim.face_roles):
        for vi in tri:
            votes[vi][role] = votes[vi].get(role, 0) + 1
    out = np.empty(prim.vertex_count(), dtype=object)
    for i, v in enumerate(votes):
        out[i] = max(v, key=v.get) if v else SurfaceRole.UNKNOWN
    return out


def _edge_cavity_ao(prim: Primitive, strength: float) -> np.ndarray:
    """Darken vertices near geometric edges/crevices.

    Geometry-pure proxy for ambient occlusion that survives glTF export and
    stands in for the bevel's light-catch when geometric bevel is off.

    Deli Counter / Blender exports box faces as *separate vertex islands*
    (flat shading duplicates verts per face), so a naive per-vertex normal is
    constant inside a face and would never see an edge. We therefore **weld by
    position**: vertices that share a world position (the 2-3 faces meeting at a
    cube edge/corner) are pooled, and the divergence of their incident face
    normals drives the darkening. Flat interiors stay bright; edges and corners
    darken, strongest at corners where three faces meet.
    """
    tris = prim.positions[prim.indices]
    fn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(fn, axis=1, keepdims=True)
    fn = np.divide(fn, ln, out=np.zeros_like(fn), where=ln > 1e-12)

    # Per-vertex accumulated incident face normals + counts.
    acc = np.zeros((prim.vertex_count(), 3))
    cnt = np.zeros(prim.vertex_count())
    for k in range(3):
        np.add.at(acc, prim.indices[:, k], fn)
        np.add.at(cnt, prim.indices[:, k], 1.0)

    # Pool by welded position.
    keys = np.round(prim.positions, 3)
    order = np.lexsort((keys[:, 2], keys[:, 1], keys[:, 0]))
    spread = np.zeros(prim.vertex_count())
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and np.array_equal(keys[order[j]], keys[order[i]]):
            j += 1
        grp = order[i:j]
        g_acc = acc[grp].sum(axis=0)
        g_cnt = max(cnt[grp].sum(), 1.0)
        coherence = np.linalg.norm(g_acc) / g_cnt        # 1 = flat, <1 = edge
        spread[grp] = np.clip(1.0 - coherence, 0.0, 1.0)
        i = j
    return 1.0 - strength * spread


def _height_grime(prim: Primitive, strength: float, height: float) -> np.ndarray:
    z = prim.positions[:, 2]
    zmin = float(z.min())
    t = np.clip((zmin + height - z) / max(height, 1e-6), 0.0, 1.0)
    return 1.0 - strength * t


def vertex_color(scene: Scene, opts: NuanceOptions,
                 tints: dict[SurfaceRole, np.ndarray] | None = None) -> None:
    """Bake role tint * edge-cavity AO * height grime into vertex colour.

    ``tints`` optionally overrides the built-in per-role base tints (theme
    palettes); roles absent from the override fall back to the defaults.
    """
    table = dict(_BASE_TINT)
    if tints:
        table.update({r: np.asarray(t, np.float32) for r, t in tints.items()})
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.face_roles is None:
                raise RuntimeError("vertex_color requires surfaces.classify() first")
            roles = _vertex_roles(prim)
            tint = np.array([table[r] for r in roles], np.float32)   # (V,3)
            ao = _edge_cavity_ao(prim, opts.ao_strength)[:, None]
            grime = _height_grime(prim, opts.grime_strength, opts.grime_height)[:, None]
            rgb = np.clip(tint * ao * grime, 0.0, 1.0).astype(np.float32)
            alpha = np.ones((prim.vertex_count(), 1), np.float32)
            prim.color = np.hstack([rgb, alpha])
