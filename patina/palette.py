"""Procedural / posterized textures (TDD 5.3, phase P4).

Not hand-painted art — an algorithmic *stand-in* that reads as "PS1 texture":
small (128-256 px), tileable, posterized to a low colour depth (the documented
PS1-feel trick), with a per-surface-role variant. Generated deterministically
from ``seed + role`` so the same project always produces the same tiles.

Three modes, mirroring the TDD:

* ``vertex-color`` — no textures at all (lightest, most authentic to a
  blockout-plus). Returns no tiles; the look comes purely from vertex nuance.
* ``procedural`` — generated tiles, one per used surface role.
* ``byo`` — point at a folder of the user's own low-res textures keyed by role
  (``floor.png`` / ``wall.png`` / ``ceiling.png`` / ``trim.png``); Patina does
  the unwrap, the human did the painting. This is the honest seam of step 4.

Tileability: tiles are built from integer-frequency sinusoids, which wrap
exactly, so they repeat seamlessly under the box-projection UVs.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass

import numpy as np
from PIL import Image

from . import patterns
from .determinism import rng_for
from .mesh import SurfaceRole
from .themes import Theme

# Albedo base colour per role (a touch warmer / stronger than the vertex tints,
# since the shader multiplies texture * vertex colour). Themes override these;
# the new v0.2 roles default to their umbrella values (and the default theme
# additionally aliases them, so no new tiles are generated in default).
_ALBEDO = {
    SurfaceRole.FLOOR:   (0.42, 0.40, 0.38),
    SurfaceRole.WALL:    (0.66, 0.65, 0.67),
    SurfaceRole.CEILING: (0.55, 0.55, 0.53),
    SurfaceRole.TRIM:    (0.50, 0.43, 0.34),
    SurfaceRole.UNKNOWN: (0.60, 0.60, 0.60),
    SurfaceRole.EXTERIOR_WALL: (0.66, 0.65, 0.67),
    SurfaceRole.ROOF:          (0.55, 0.55, 0.53),
}

# byo-mode lookup fallbacks: a texture folder keyed for v0.1.x roles keeps
# working — new roles borrow their umbrella role's file when no specific one
# is provided.
_BYO_FALLBACK = {
    SurfaceRole.EXTERIOR_WALL.value: SurfaceRole.WALL.value,
    SurfaceRole.ROOF.value: SurfaceRole.CEILING.value,
}


@dataclass
class PaletteOptions:
    mode: str = "vertex-color"        # vertex-color | procedural | byo
    size: int = 128                   # 128-256 px
    posterize: int = 16               # levels per channel (~16 = PS1 banding)
    byo_dir: str | None = None
    seed: int = 1999


def posterize(arr: np.ndarray, levels: int) -> np.ndarray:
    """Quantise a float image (0..1) to ``levels`` steps per channel."""
    levels = max(2, int(levels))
    return np.round(np.clip(arr, 0, 1) * (levels - 1)) / (levels - 1)


def _tileable_noise(size: int, rng: np.random.Generator, octaves=3) -> np.ndarray:
    """Sum of integer-frequency sinusoids -> seamlessly tiling value noise."""
    yy, xx = np.meshgrid(np.linspace(0, 2 * np.pi, size, endpoint=False),
                         np.linspace(0, 2 * np.pi, size, endpoint=False), indexing="ij")
    field = np.zeros((size, size))
    amp = 1.0
    for o in range(octaves):
        fx, fy = int(rng.integers(1, 4 + o * 2)), int(rng.integers(1, 4 + o * 2))
        px, py = rng.uniform(0, 2 * np.pi, 2)
        field += amp * np.sin(fx * xx + px) * np.cos(fy * yy + py)
        amp *= 0.5
    field -= field.min()
    field /= max(field.max(), 1e-6)
    return field


def generate_tile(role: SurfaceRole, opts: PaletteOptions,
                  theme: Theme | None = None) -> Image.Image:
    """Deterministic posterized albedo tile for a role (material key).

    The noise stream is keyed only by ``(seed, "palette", role)`` and theme
    albedo variants draw from a *separate* stream, so a theme with no albedo
    entry for a role produces bytes identical to the pre-theme output.

    v0.3: a theme may request a *structured* pattern for a material key
    (tile / checker / block / panel / plank — see :mod:`patina.patterns`).
    Pattern RNG streams are keyed ``(seed, "pattern", key, ...)``, disjoint
    from the ``"palette"`` streams, so keys without a pattern entry (and the
    whole default theme) stay byte-identical to v0.2.
    """
    if theme is not None:
        spec = theme.pattern_spec(role.value)
        if spec is not None:
            base = np.array(_ALBEDO.get(role, _ALBEDO[SurfaceRole.UNKNOWN]),
                            np.float32)
            variants = theme.albedo_variants(role.value)
            rgb = patterns.generate(role.value, spec, size=opts.size,
                                    seed=opts.seed, base=base,
                                    variants=variants)
            rgb = posterize(rgb, opts.posterize)
            return Image.fromarray((rgb * 255).astype(np.uint8), "RGB")

    rng = rng_for(opts.seed, "palette", role.value)
    n = _tileable_noise(opts.size, rng)
    base = np.array(_ALBEDO.get(role, _ALBEDO[SurfaceRole.UNKNOWN]), np.float32)
    if theme is not None:
        variants = theme.albedo_variants(role.value)
        if variants:
            vrng = rng_for(opts.seed, "palette", role.value, "variant")
            base = np.array(variants[int(vrng.integers(0, len(variants)))],
                            np.float32)
    # Modulate brightness by noise (+/- ~18%) then tint.
    value = 0.82 + 0.36 * n
    rgb = np.clip(value[..., None] * base[None, None, :], 0, 1)
    rgb = posterize(rgb, opts.posterize)
    return Image.fromarray((rgb * 255).astype(np.uint8), "RGB")


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    # optimize=False keeps output deterministic across Pillow builds.
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def import_tile(path: str, opts: PaletteOptions, *, process: bool = True) -> bytes:
    """Bring an external image/photo in as a tile (PNG bytes).

    With ``process`` (default): centre-crop to square, resize to the tile
    size with box filtering, drop to RGB, and posterize to the PS1 colour
    depth — a phone photo of a real surface becomes a period-correct tile.
    With ``process=False`` the file is passed through as PNG bytes untouched
    (already-authored pixel art). Deterministic in the file bytes either way.
    """
    with Image.open(path) as im:
        im.load()
        if not process:
            return _png_bytes(im.convert("RGBA") if im.mode == "P" else im)
        im = im.convert("RGB")
        w, h = im.size
        s = min(w, h)
        im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
        im = im.resize((opts.size, opts.size), Image.BOX)
    arr = np.asarray(im, np.float32) / 255.0
    arr = posterize(arr, opts.posterize)
    return _png_bytes(Image.fromarray((arr * 255).astype(np.uint8), "RGB"))


def build_palette(roles: set[SurfaceRole], opts: PaletteOptions,
                  theme: Theme | None = None) -> dict[str, bytes]:
    """Return {material key -> PNG bytes} for the chosen mode.

    Keys are theme material keys: aliased roles share one tile (the default
    theme aliases ``exterior_wall`` -> ``wall`` and ``roof`` -> ``ceiling``,
    so its output file set matches v0.1.x exactly). Empty for vertex-color.
    """
    if opts.mode == "vertex-color":
        return {}
    keys = sorted({(theme.material_key(r.value) if theme else r.value)
                   for r in roles})
    if opts.mode == "procedural":
        return {k: _png_bytes(generate_tile(SurfaceRole(k), opts, theme))
                for k in keys}
    if opts.mode == "byo":
        if not opts.byo_dir or not os.path.isdir(opts.byo_dir):
            raise FileNotFoundError(f"byo mode needs --textures DIR (got {opts.byo_dir!r})")
        out: dict[str, bytes] = {}
        for key in keys:
            for name in (key, _BYO_FALLBACK.get(key)):
                if name is None:
                    continue
                found = False
                for ext in (".png", ".jpg", ".jpeg", ".webp"):
                    cand = os.path.join(opts.byo_dir, name + ext)
                    if os.path.exists(cand):
                        with open(cand, "rb") as fh:
                            out[key] = fh.read()
                        found = True
                        break
                if found:
                    break
        return out
    raise ValueError(f"unknown palette mode {opts.mode!r}")
