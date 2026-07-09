"""Painter's seams (v0.3): paint templates and Texpaint-style start skins.

Two tools straight out of the Quake 2 art workflow, honestly scoped:

* **Paint templates** — id's level texture sets were painted by hand at fixed
  power-of-two sizes with known world scale. Patina's box-projection UVs give
  every generated tile a fixed world scale too (``--texel`` metres per tile),
  so we can emit, per material key, a calibration sheet: the current
  stand-in tile (or a neutral base) with a metre grid, axis marks and the key
  name baked in. A texture artist paints over it in any 2D app, drops the
  result into a ``byo`` folder under the same name, and re-runs Patina — the
  unwrap was the tool's job, the painting stays human.

* **Start skins** — John Carmack's Texpaint generated a "triangle-unique
  multicolored start skin" from a model's mapping coordinates so artists
  could see coverage and problem areas before painting. Patina does the same
  for any visual mesh that carries an *authored* UV0 channel: every triangle
  is rasterised into UV space in its own colour with wire lines on top.
  Deli Counter greyboxes ship no UV0 (their UVs are Patina's box projection),
  so this is the *model* half of the workflow — props, fixtures, characters.
  Meshes without UV0 are skipped and reported, never faked.

Both outputs are deterministic (colours come from index math, not RNG; PNGs
are written with ``optimize=False``) and both are inputs to human craft, not
substitutes for it.
"""

from __future__ import annotations

import colorsys
import io
import os
import re

import numpy as np
from PIL import Image, ImageDraw

from .mesh import Scene

_BASE_GRAY = (184, 184, 184)
_GRID_RGB = (110, 110, 110)
_BORDER_RGB = (70, 70, 70)
_LABEL_RGB = (35, 35, 35)
_SKIN_BG = (26, 26, 26)
_WIRE_RGB = (16, 16, 16)


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)   # deterministic across builds
    return buf.getvalue()


def safe_name(name: str) -> str:
    """Mesh name -> filesystem-safe stem."""
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name) or "unnamed"


# --------------------------------------------------------------------------- #
# Paint templates (map skinning: the byo seam, made drawable)
# --------------------------------------------------------------------------- #

def paint_template(key: str, *, size: int, texel: float,
                   background: Image.Image | None = None) -> Image.Image:
    """One calibration sheet for one material key.

    ``background`` is the generated stand-in tile when available (procedural
    mode) so the painter starts from the current look; otherwise neutral
    grey. The metre grid is drawn from ``texel`` (world metres per full
    tile), which is exactly how the box projection will map the painted
    result back onto the level.
    """
    if background is not None:
        img = background.convert("RGB").resize((size, size), Image.NEAREST)
    else:
        img = Image.new("RGB", (size, size), _BASE_GRAY)
    d = ImageDraw.Draw(img)

    # Metre grid (only when a metre is at least a few pixels wide).
    px_per_m = size / max(texel, 1e-6)
    if px_per_m >= 8:
        m = px_per_m
        x = m
        while x < size - 1:
            d.line([(round(x), 0), (round(x), size)], fill=_GRID_RGB, width=1)
            x += m
        y = m
        while y < size - 1:
            d.line([(0, round(y)), (size, round(y))], fill=_GRID_RGB, width=1)
            y += m

    d.rectangle([0, 0, size - 1, size - 1], outline=_BORDER_RGB, width=2)

    # Labels: key, world scale, axis arrows. Default PIL bitmap font.
    d.text((5, 4), key, fill=_LABEL_RGB)
    d.text((5, size - 14), f"{texel:g} m / tile", fill=_LABEL_RGB)
    d.line([(size - 34, size - 9), (size - 12, size - 9)], fill=_LABEL_RGB, width=1)
    d.line([(size - 16, size - 12), (size - 12, size - 9), (size - 16, size - 6)],
           fill=_LABEL_RGB, width=1)
    d.text((size - 44, size - 14), "U", fill=_LABEL_RGB)
    d.line([(size - 8, size - 36), (size - 8, size - 14)], fill=_LABEL_RGB, width=1)
    d.line([(size - 11, size - 32), (size - 8, size - 36), (size - 5, size - 32)],
           fill=_LABEL_RGB, width=1)
    d.text((size - 8 - 10, size - 48), "V", fill=_LABEL_RGB)
    return img


def write_paint_templates(keys: list[str], out_dir: str, *, size: int,
                          texel: float,
                          backgrounds: dict[str, bytes] | None = None) -> list[str]:
    """Write ``<key>.template.png`` per material key; returns written paths."""
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for key in sorted(keys):
        bg = None
        if backgrounds and key in backgrounds:
            bg = Image.open(io.BytesIO(backgrounds[key]))
        img = paint_template(key, size=size, texel=texel, background=bg)
        path = os.path.join(out_dir, f"{safe_name(key)}.template.png")
        with open(path, "wb") as fh:
            fh.write(_png_bytes(img))
        written.append(path)
    return written


# --------------------------------------------------------------------------- #
# Start skins (model skinning: Texpaint's first move)
# --------------------------------------------------------------------------- #

def _tri_color(i: int) -> tuple[int, int, int]:
    """Triangle-unique colour: golden-angle hue walk (deterministic, no RNG)."""
    h = (i * 0.6180339887498949) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.55, 0.95)
    return int(r * 255), int(g * 255), int(b * 255)


def start_skin(mesh, *, size: int) -> Image.Image | None:
    """Triangle-unique start skin from the mesh's authored UV0, or None.

    glTF UV convention (v grows downward) matches image rows directly, so
    triangles are drawn at ``(u * size, v * size)`` with no flip. UVs are
    used as authored; anything outside 0..1 simply falls off the sheet, which
    is itself useful information about the unwrap.
    """
    prims = [p for p in mesh.primitives if p.uv0 is not None and p.vertex_count()]
    if not prims:
        return None
    img = Image.new("RGB", (size, size), _SKIN_BG)
    d = ImageDraw.Draw(img)
    tri_index = 0
    for prim in prims:
        uv = np.asarray(prim.uv0, np.float32) * (size - 1)
        for tri in prim.indices:
            pts = [tuple(uv[int(v)]) for v in tri]
            d.polygon(pts, fill=_tri_color(tri_index))
            tri_index += 1
    # Wire pass on top so shared edges stay visible over the fills.
    for prim in prims:
        uv = np.asarray(prim.uv0, np.float32) * (size - 1)
        for tri in prim.indices:
            pts = [tuple(uv[int(v)]) for v in tri]
            d.line([pts[0], pts[1], pts[2], pts[0]], fill=_WIRE_RGB, width=1)
    d.text((5, 4), safe_name(mesh.name), fill=(230, 230, 230))
    return img


def write_start_skins(scene: Scene, out_dir: str, *,
                      size: int) -> tuple[list[str], list[str]]:
    """Write ``<mesh>.startskin.png`` per visual mesh with UV0.

    Returns ``(written_paths, skipped_mesh_names)``. Skipped means "no
    authored UV0" — box-projection UVs (uv1) are world-tiling, not a
    paintable unwrap, so faking a sheet from them would be dishonest.
    """
    written: list[str] = []
    skipped: list[str] = []
    made_dir = False
    for mesh in scene.visual_meshes():
        img = start_skin(mesh, size=size)
        if img is None:
            skipped.append(mesh.name)
            continue
        if not made_dir:
            os.makedirs(out_dir, exist_ok=True)
            made_dir = True
        path = os.path.join(out_dir, f"{safe_name(mesh.name)}.startskin.png")
        with open(path, "wb") as fh:
            fh.write(_png_bytes(img))
        written.append(path)
    return written, skipped
