"""Decal pass — surface story without geometry (bashing brief step 3).

The brief's "highest return area": materials create the base look, decals
create the lived-in feel. This module does the two offline halves:

* **Textures** — small posterized RGBA stamps (stains, scuffs, streaks),
  generated deterministically per ``(seed, type)``. Algorithmic stand-ins in
  the same spirit as :mod:`patina.palette` — honest grime, not forged art.
* **Placement** — seeded, area-weighted sampling over classified faces. Each
  theme :class:`~patina.themes.DecalSpec` targets a set of surface roles at a
  density (count per 100 m²); placements are emitted into the manifest as
  ``pos / normal / size / rot`` records for the Godot addon to instantiate as
  ``Decal`` nodes.

Non-destructive by construction: nothing here touches geometry, collision or
gameplay data. Deleting the ``PatinaDecals`` node in Godot removes the entire
pass.

Coordinate contract: positions/normals are in the styled ``.glb``'s baked
world space (Z-up, matching every other Patina stage and the kitbash bounds).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import numpy as np
from PIL import Image

from .determinism import rng_for
from .mesh import Scene, SurfaceRole
from .palette import posterize
from .themes import Theme

_TEX_SIZE = 96          # px; decals are small stamps, not tiling materials
_GRIME = (0.165, 0.141, 0.122)   # matches the brief's #2a241f grime anchor


@dataclass(frozen=True)
class Placement:
    type: str
    pos: tuple[float, float, float]
    normal: tuple[float, float, float]
    size: tuple[float, float]      # width, height in world metres
    rot: float                     # degrees around the surface normal


# ---------------------------------------------------------------------------
# Procedural stamp textures
# ---------------------------------------------------------------------------

def _grid(size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (xx, yy, r) in -1..1 with r = distance from centre."""
    lin = np.linspace(-1, 1, size)
    yy, xx = np.meshgrid(lin, lin, indexing="ij")
    return xx, yy, np.sqrt(xx * xx + yy * yy)


def _blob_alpha(size: int, rng: np.random.Generator,
                wobble: float = 0.35, hard: float = 4.0) -> np.ndarray:
    """Irregular soft-edged blob mask via angularly-warped radius."""
    xx, yy, r = _grid(size)
    ang = np.arctan2(yy, xx)
    warp = np.zeros_like(r)
    for k in range(2, 6):
        warp += rng.uniform(0, wobble / k) * np.sin(k * ang + rng.uniform(0, 6.28))
    edge = 0.85 + warp
    return np.clip((edge - r) * hard, 0, 1)


def _stamp(rgb: np.ndarray, alpha: np.ndarray, levels: int) -> Image.Image:
    rgb = posterize(np.clip(rgb, 0, 1), levels)
    a = posterize(np.clip(alpha, 0, 1)[..., None], levels)[..., 0]
    out = np.dstack([rgb, a])
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def _tex_water_stain(size, rng, levels):
    xx, yy, r = _grid(size)
    a = _blob_alpha(size, rng, wobble=0.5, hard=3.0)
    ring = np.clip(1.0 - np.abs(a - 0.35) * 3.0, 0, 1)     # darker tide-line edge
    base = np.array([0.42, 0.37, 0.30])
    rgb = base[None, None, :] * (0.85 - 0.35 * ring)[..., None]
    return _stamp(rgb, a * (0.35 + 0.45 * ring), levels)


def _tex_oil_stain(size, rng, levels):
    xx, yy, r = _grid(size)
    sq = np.sqrt((xx / rng.uniform(0.8, 1.0)) ** 2 + (yy / rng.uniform(0.55, 0.8)) ** 2)
    a = np.clip((0.9 - sq) * 3.0, 0, 1) * _blob_alpha(size, rng, wobble=0.25)
    rgb = np.tile(np.array([0.06, 0.06, 0.08]), (size, size, 1))
    return _stamp(rgb, a * 0.85, levels)


def _tex_scuff_marks(size, rng, levels):
    xx, yy, _ = _grid(size)
    a = np.zeros((size, size))
    for _i in range(int(rng.integers(3, 6))):
        y0, w = rng.uniform(-0.7, 0.7), rng.uniform(0.02, 0.06)
        tilt = rng.uniform(-0.25, 0.25)
        band = np.exp(-(((yy - y0 - tilt * xx) / w) ** 2))
        fade = np.clip(1 - np.abs(xx) / rng.uniform(0.6, 1.0), 0, 1)
        a = np.maximum(a, band * fade * rng.uniform(0.4, 0.8))
    rgb = np.tile(np.array(_GRIME), (size, size, 1))
    return _stamp(rgb, a, levels)


def _tex_rust_streak(size, rng, levels):
    xx, yy, _ = _grid(size)
    a = np.zeros((size, size))
    for _i in range(int(rng.integers(2, 5))):
        x0, w = rng.uniform(-0.6, 0.6), rng.uniform(0.03, 0.09)
        col = np.exp(-(((xx - x0) / w) ** 2))
        fade = np.clip((yy + 1) / rng.uniform(1.2, 2.0), 0, 1)  # fades downward
        a = np.maximum(a, col * (1 - fade) * rng.uniform(0.5, 0.9))
    rust = np.array([0.45, 0.22, 0.10])
    rgb = np.tile(rust, (size, size, 1)) * (0.7 + 0.3 * a[..., None])
    return _stamp(rgb, a, levels)


def _tex_paint_chip(size, rng, levels):
    a = _blob_alpha(size, rng, wobble=0.6, hard=8.0)          # jaggy hard edge
    under = np.array([0.55, 0.53, 0.50])                       # exposed underlayer
    rgb = np.tile(under, (size, size, 1)) * rng.uniform(0.85, 1.05)
    return _stamp(rgb, a * 0.9, levels)


def _tex_gum_spot(size, rng, levels):
    a = _blob_alpha(size, rng, wobble=0.15, hard=10.0)
    rgb = np.tile(np.array([0.16, 0.15, 0.14]), (size, size, 1))
    return _stamp(rgb, a, levels)


def _tex_grime(size, rng, levels):
    a = _blob_alpha(size, rng, wobble=0.45, hard=2.5)
    rgb = np.tile(np.array(_GRIME), (size, size, 1))
    return _stamp(rgb, a * 0.6, levels)


_GENERATORS = {
    "water_stain": _tex_water_stain,
    "oil_stain": _tex_oil_stain,
    "scuff_marks": _tex_scuff_marks,
    "rust_streak": _tex_rust_streak,
    "paint_chip": _tex_paint_chip,
    "gum_spot": _tex_gum_spot,
    "grime": _tex_grime,
}


def generate_texture(decal_type: str, seed: int, levels: int = 16,
                     size: int = _TEX_SIZE) -> bytes:
    """Deterministic RGBA PNG bytes for a decal type (unknown -> grime)."""
    gen = _GENERATORS.get(decal_type, _tex_grime)
    rng = rng_for(seed, "decal-tex", decal_type)
    img = gen(size, rng, max(2, int(levels)))
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)   # deterministic across builds
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def _faces_for_roles(scene: Scene, roles: set[SurfaceRole]):
    """Yield (tri_pts (T,3,3), normals (T,3)) for matching faces, in stable order."""
    for mesh in sorted(scene.visual_meshes(), key=lambda m: m.name):
        for prim in mesh.primitives:
            if prim.face_roles is None:
                continue
            mask = np.array([r in roles for r in prim.face_roles], bool)
            if not mask.any():
                continue
            tris = prim.positions[prim.indices[mask]]              # (T,3,3)
            fn = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
            ln = np.linalg.norm(fn, axis=1, keepdims=True)
            fn = np.divide(fn, ln, out=np.zeros_like(fn), where=ln > 1e-12)
            yield tris, fn


def place(scene: Scene, theme: Theme, seed: int,
          density_scale: float = 1.0) -> list[Placement]:
    """Seeded, area-weighted decal placements for every theme decal spec.

    Independent RNG stream per spec type (``rng_for(seed, "decal", type)``),
    so adding a spec to a theme never reshuffles the others.
    """
    out: list[Placement] = []
    for spec in theme.decals:
        roles = {SurfaceRole(r) for r in spec.roles}
        tris_all, fn_all = [], []
        for tris, fn in _faces_for_roles(scene, roles):
            tris_all.append(tris)
            fn_all.append(fn)
        if not tris_all:
            continue
        tris = np.concatenate(tris_all)                            # (T,3,3)
        fn = np.concatenate(fn_all)                                # (T,3)
        areas = 0.5 * np.linalg.norm(
            np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]), axis=1)
        total = float(areas.sum())
        if total <= 1e-9:
            continue
        count = int(round(total / 100.0 * spec.per_100m2 * max(density_scale, 0.0)))
        count = min(max(count, 0), spec.max_count)
        if count == 0:
            continue

        rng = rng_for(seed, "decal", spec.type)
        cum = np.cumsum(areas)
        for _i in range(count):
            t = int(np.searchsorted(cum, rng.uniform(0, total)))
            t = min(t, len(areas) - 1)
            # Uniform barycentric sample (sqrt trick).
            r1, r2 = rng.uniform(), rng.uniform()
            s1 = np.sqrt(r1)
            p = (tris[t, 0] * (1 - s1) + tris[t, 1] * (s1 * (1 - r2))
                 + tris[t, 2] * (s1 * r2))
            w = float(rng.uniform(spec.size[0], spec.size[1]))
            h = w * float(rng.uniform(spec.aspect[0], spec.aspect[1]))
            rot = float(rng.uniform(0, 360)) if spec.rot == "random" else 0.0
            out.append(Placement(
                type=spec.type,
                pos=tuple(round(float(v), 4) for v in p),
                normal=tuple(round(float(v), 4) for v in fn[t]),
                size=(round(w, 4), round(h, 4)),
                rot=round(rot, 2),
            ))
    return out


def used_types(placements: list[Placement]) -> list[str]:
    return sorted({p.type for p in placements})
