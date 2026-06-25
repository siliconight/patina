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

from .determinism import rng_for
from .mesh import SurfaceRole

# Albedo base colour per role (a touch warmer / stronger than the vertex tints,
# since the shader multiplies texture * vertex colour).
_ALBEDO = {
    SurfaceRole.FLOOR:   (0.42, 0.40, 0.38),
    SurfaceRole.WALL:    (0.66, 0.65, 0.67),
    SurfaceRole.CEILING: (0.55, 0.55, 0.53),
    SurfaceRole.TRIM:    (0.50, 0.43, 0.34),
    SurfaceRole.UNKNOWN: (0.60, 0.60, 0.60),
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


def generate_tile(role: SurfaceRole, opts: PaletteOptions) -> Image.Image:
    """Deterministic posterized albedo tile for a role."""
    rng = rng_for(opts.seed, "palette", role.value)
    n = _tileable_noise(opts.size, rng)
    base = np.array(_ALBEDO.get(role, _ALBEDO[SurfaceRole.UNKNOWN]), np.float32)
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


def build_palette(roles: set[SurfaceRole], opts: PaletteOptions) -> dict[str, bytes]:
    """Return {role -> PNG bytes} for the chosen mode (empty for vertex-color)."""
    if opts.mode == "vertex-color":
        return {}
    if opts.mode == "procedural":
        return {r.value: _png_bytes(generate_tile(r, opts)) for r in sorted(roles, key=lambda x: x.value)}
    if opts.mode == "byo":
        if not opts.byo_dir or not os.path.isdir(opts.byo_dir):
            raise FileNotFoundError(f"byo mode needs --textures DIR (got {opts.byo_dir!r})")
        out: dict[str, bytes] = {}
        for r in sorted(roles, key=lambda x: x.value):
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                cand = os.path.join(opts.byo_dir, r.value + ext)
                if os.path.exists(cand):
                    with open(cand, "rb") as fh:
                        out[r.value] = fh.read()
                    break
        return out
    raise ValueError(f"unknown palette mode {opts.mode!r}")
