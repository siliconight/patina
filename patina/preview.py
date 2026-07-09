"""Look preview (v0.13): eyeball the composite before the engine walk.

Every art-pass bake — Zoo's wear+ambient, Patina's nuance+depth, per-slot
variation — lands in vertex colour, and Lux multiplies its lit result by that
colour (``base *= v_vertex_color``). Three multiplicative bakes then a runtime
multiply is easy to over-darken: albedo can end up so low that Lux's banding
has nothing to work with. That failure only shows in-engine today.

This is a *small software rasteriser* that approximates the composite so the
risk is visible offline. It is not a renderer competing with Lux — it stands in
for Lux just enough to be honest about the multiply:

    preview = band_light(N·L)  ×  vertex_colour  ×  albedo_stand_in

with a Lux-like key direction, lifted/banded diffuse, and a cool ambient floor.
The point is calibration, not beauty: if the preview crushes to black, so will
the real thing, and the fix is lower bake strengths (never a clamp).

It reports luma stats (how much headroom is left for Lux's bands) alongside the
image, so "too dark" is a number, not just a vibe. Pure numpy; no bpy, no Godot.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .mesh import Scene


@dataclass
class PreviewOptions:
    width: int = 640
    height: int = 400
    # Lux-like key light (world space, FROM surface TO light) — matches the
    # delco afternoon sun's rough elevation/azimuth so the preview reads like
    # the target preset rather than a neutral studio light.
    key_dir: tuple = (0.4, 0.8, 0.45)
    key_color: tuple = (1.0, 0.96, 0.88)
    ambient: tuple = (0.34, 0.36, 0.42)     # cool ambient floor (Lux ambient)
    band_count: int = 3                     # Lux banded diffuse
    shade_min: float = 0.18                 # Lux lifted shadow floor
    albedo: float = 0.8                     # flat albedo stand-in (no tile)
    yaw_deg: float = 35.0                   # camera orbit
    pitch_deg: float = 20.0
    bg: tuple = (0.10, 0.11, 0.13)


def _band(ndl: np.ndarray, opts: PreviewOptions) -> np.ndarray:
    """Lux-style lifted, banded diffuse over N·L."""
    lifted = opts.shade_min + (1.0 - opts.shade_min) * np.clip(ndl, 0.0, 1.0)
    steps = max(1, opts.band_count)
    return np.floor(lifted * steps + 0.5) / steps


def _camera(scene: Scene, opts: PreviewOptions):
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for m in scene.visual_meshes():
        for p in m.primitives:
            if p.vertex_count():
                lo = np.minimum(lo, p.positions.min(0))
                hi = np.maximum(hi, p.positions.max(0))
    if not np.isfinite(lo).all():
        lo, hi = np.zeros(3), np.ones(3)
    center = (lo + hi) / 2.0
    radius = float(np.linalg.norm(hi - lo)) * 0.5 + 1e-6
    yaw, pitch = np.radians(opts.yaw_deg), np.radians(opts.pitch_deg)
    eye = center + radius * 2.4 * np.array([
        np.cos(pitch) * np.sin(yaw), np.sin(pitch), np.cos(pitch) * np.cos(yaw)])
    fwd = center - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right) + 1e-9
    up = np.cross(right, fwd)
    return eye, right, up, fwd, radius


def render(scene: Scene, opts: PreviewOptions | None = None) -> np.ndarray:
    """Return an (H, W, 3) float image of the composite look."""
    opts = opts or PreviewOptions()
    W, H = opts.width, opts.height
    img = np.tile(np.array(opts.bg, np.float32), (H, W, 1))
    zbuf = np.full((H, W), np.inf)

    eye, right, up, fwd, radius = _camera(scene, opts)
    key = np.array(opts.key_dir, np.float32)
    key /= np.linalg.norm(key)
    key_col = np.array(opts.key_color, np.float32)
    amb = np.array(opts.ambient, np.float32)
    focal = 1.4 * max(W, H) / 2.0

    def project(P):
        rel = P - eye
        x = rel @ right
        y = rel @ up
        z = rel @ fwd
        z = np.where(np.abs(z) < 1e-6, 1e-6, z)
        sx = W * 0.5 + focal * x / z
        sy = H * 0.5 - focal * y / z
        return sx, sy, z

    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if not prim.triangle_count():
                continue
            pos = prim.positions
            col = (prim.color[:, :3] if prim.color is not None
                   else np.full((prim.vertex_count(), 3), 0.7, np.float32))
            sx, sy, z = project(pos)
            tris = prim.indices
            # per-face flat normal + N·L key term
            tp = pos[tris]
            fn = np.cross(tp[:, 1] - tp[:, 0], tp[:, 2] - tp[:, 0])
            ln = np.linalg.norm(fn, axis=1, keepdims=True)
            fn = np.divide(fn, ln, out=np.zeros_like(fn), where=ln > 1e-9)
            ndl = fn @ key
            shade = _band(ndl, opts)[:, None]                       # (T,1)
            _raster(img, zbuf, sx, sy, z, tris, col, shade, key_col, amb, opts)
    return np.clip(img, 0.0, 1.0)


def _raster(img, zbuf, sx, sy, z, tris, col, shade, key_col, amb, opts):
    H, W = zbuf.shape
    for t in range(tris.shape[0]):
        i0, i1, i2 = tris[t]
        xs = np.array([sx[i0], sx[i1], sx[i2]])
        ys = np.array([sy[i0], sy[i1], sy[i2]])
        zs = np.array([z[i0], z[i1], z[i2]])
        if np.any(zs <= 0):
            continue
        minx, maxx = int(max(0, np.floor(xs.min()))), int(min(W - 1, np.ceil(xs.max())))
        miny, maxy = int(max(0, np.floor(ys.min()))), int(min(H - 1, np.ceil(ys.max())))
        if minx > maxx or miny > maxy:
            continue
        area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
        if abs(area) < 1e-9:
            continue
        yy, xx = np.mgrid[miny:maxy + 1, minx:maxx + 1]
        px, py = xx + 0.5, yy + 0.5
        w0 = ((xs[1] - px) * (ys[2] - py) - (xs[2] - px) * (ys[1] - py)) / area
        w1 = ((xs[2] - px) * (ys[0] - py) - (xs[0] - px) * (ys[2] - py)) / area
        w2 = 1.0 - w0 - w1
        inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
        if not inside.any():
            continue
        zpix = w0 * zs[0] + w1 * zs[1] + w2 * zs[2]
        vcol = (w0[..., None] * col[i0] + w1[..., None] * col[i1]
                + w2[..., None] * col[i2])
        # the composite multiply: (banded key + ambient) x vertex_colour x albedo
        lit = (key_col * shade[t] + amb) * vcol * opts.albedo
        sub = zbuf[miny:maxy + 1, minx:maxx + 1]
        closer = inside & (zpix < sub)
        sub[closer] = zpix[closer]
        img[miny:maxy + 1, minx:maxx + 1][closer] = np.clip(lit, 0, 1)[closer]


def luma_stats(img: np.ndarray, bg: tuple) -> dict:
    """Headroom report: how dark the lit surfaces got (excludes background)."""
    flat = img.reshape(-1, 3)
    bg = np.array(bg, np.float32)
    surf = flat[np.abs(flat - bg).sum(1) > 0.02]
    if surf.size == 0:
        return {"surface_px": 0}
    luma = surf @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    crushed = float((luma < 0.06).mean())
    # Lux's banded diffuse needs range to read: below ~0.25 mean the bands
    # compress into a dark smear even before Lux darkens further, and a large
    # near-black share means bakes have already crushed detail. Both are the
    # "reduce bake strengths" signal.
    return {
        "surface_px": int(surf.shape[0]),
        "luma_mean": round(float(luma.mean()), 3),
        "luma_p10": round(float(np.percentile(luma, 10)), 3),
        "luma_p50": round(float(np.percentile(luma, 50)), 3),
        "crushed_frac": round(crushed, 3),      # share near-black (<0.06)
        "headroom_ok": bool(luma.mean() > 0.25 and crushed < 0.12),
    }
