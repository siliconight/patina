"""Trim sheets + dressing manifest (v0.11): the texture half of Zoo dressing.

Two art-pass items need a texture atlas plus a placement contract, not new
Patina geometry:

* **Trim sheets** (Steed/Q2 sense) — an *atlas*: edge caps, pipe runs, panel
  seams, corner guards, foundation courses, conduit, packed into one
  power-of-two image with a known UV region per piece. A modeller (or a Zoo
  recipe) UV-maps thin geometry to a region and gets that trim for free. This
  is texture work — squarely Patina's — and reuses the pattern generators and
  the family lock, so trim shares the building's palette.
* **Dressing manifest** — the placement contract that turns Patina's anchors
  into Zoo build orders: per anchor, *which trim piece* and *which UV region*
  a non-collision cover mesh should use. Patina supplies the atlas + the
  orders; Zoo builds the (``collision: none``) geometry. This closes the loop
  the anchors opened — Patina places and skins, Zoo builds.

Patina still ships **zero geometry**. The trim sheet is a PNG; the dressing
manifest is JSON naming trim pieces, UV regions, anchor positions (in the same
DC Blender Z-up space anchors use when a slots.json is present), and a
suggested cover kind. What Zoo does with it — extrude a strip, cap an edge,
box a vent — is Zoo's call, marked non-collision so the greybox collision is
never touched.

Deterministic: strip patterns draw from ``(seed, "trim", piece)`` streams;
dressing placement reuses the anchor seed. Family-locked when a family is
bound, so trim never breaks cohesion.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass

import numpy as np
from PIL import Image

from . import patterns
from .determinism import rng_for

# Each trim piece is a horizontal strip: a pattern spec + a relative height
# (fraction of the sheet). Widths span the full sheet (U tiles along the run).
# The pattern types are the existing generators, chosen to read as trim.
TRIM_PIECES: dict[str, dict] = {
    "roof_edge":   {"pattern": {"type": "plank", "rows": 2, "line_px": 2}, "h": 0.14},
    "panel_seam":  {"pattern": {"type": "panel", "cols": 6, "line_px": 1}, "h": 0.18},
    "pipe_run":    {"pattern": {"type": "panel", "cols": 3, "line_px": 3}, "h": 0.12},
    "corner_guard":{"pattern": {"type": "block", "rows": 2, "cols": 1}, "h": 0.10},
    "foundation":  {"pattern": {"type": "block", "rows": 3, "cols": 6}, "h": 0.24},
    "conduit":     {"pattern": {"type": "panel", "cols": 8, "line_px": 2}, "h": 0.10},
    "flashing":    {"pattern": {"type": "plank", "rows": 1, "line_px": 1}, "h": 0.12},
}

# Which trim piece each anchor kind suggests as its cover (the dressing map).
_ANCHOR_TRIM = {
    "roofline": "roof_edge",
    "wall_base": "foundation",
    "ground_edge": "foundation",
    "exterior_light": "conduit",
}

# Suggested Zoo cover kind per anchor (hint only; Zoo decides geometry).
_ANCHOR_COVER = {
    "roofline": "edge_strip",       # thin capping strip along the top edge
    "wall_base": "base_course",     # foundation band at the foot
    "ground_edge": "curb",          # ground-meet strip
    "exterior_light": "conduit_run",  # thin conduit up the wall to the light
}


@dataclass
class TrimRegion:
    """One piece's UV rectangle in the atlas (v0 top, v1 bottom; 0..1)."""

    piece: str
    u0: float
    v0: float
    u1: float
    v1: float


def _order() -> list[str]:
    return list(TRIM_PIECES)


def build_sheet(*, size: int, seed: int, family=None, posterize: int = 16
                ) -> tuple[bytes, list[TrimRegion]]:
    """Generate the trim atlas PNG and its per-piece UV regions.

    Pieces stack as horizontal strips top-to-bottom, heights normalised to fill
    the sheet. Each strip is a family-locked posterized pattern (so trim shares
    the building palette). Returns (png_bytes, regions).
    """
    order = _order()
    total_h = sum(TRIM_PIECES[p]["h"] for p in order)
    variants = [tuple(c) for c in family.palette_rgb()] if family is not None else []
    base = np.array((0.55, 0.53, 0.48), np.float32)

    sheet = np.zeros((size, size, 3), np.float32)
    regions: list[TrimRegion] = []
    y = 0
    for i, piece in enumerate(order):
        frac = TRIM_PIECES[piece]["h"] / total_h
        h = size - y if i == len(order) - 1 else max(1, int(round(frac * size)))
        strip = patterns.generate(f"trim_{piece}", TRIM_PIECES[piece]["pattern"],
                                  size=size, seed=seed,
                                  base=base, variants=variants)  # (size,size,3)
        sheet[y:y + h] = strip[:h]
        regions.append(TrimRegion(piece, 0.0, y / size, 1.0, (y + h) / size))
        y += h
        if y >= size:
            break

    if family is not None:
        from . import families
        sheet = families.quantize(sheet, family)
    else:
        sheet = patterns_posterize(sheet, posterize)

    img = Image.fromarray((np.clip(sheet, 0, 1) * 255).astype(np.uint8), "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue(), regions


def patterns_posterize(arr: np.ndarray, levels: int) -> np.ndarray:
    levels = max(2, int(levels))
    return np.round(arr * (levels - 1)) / (levels - 1)


def regions_dict(regions: list[TrimRegion]) -> dict[str, list[float]]:
    return {r.piece: [round(r.u0, 4), round(r.v0, 4), round(r.u1, 4), round(r.v1, 4)]
            for r in regions}


# --------------------------------------------------------------------------- #
# Dressing manifest — anchors -> Zoo build orders
# --------------------------------------------------------------------------- #

def dressing_orders(anchors: list, regions: list[TrimRegion], *,
                    seed: int) -> list[dict]:
    """Per-anchor build orders: trim piece + UV region + cover hint.

    ``anchors`` are :class:`patina.anchors.Anchor` in whatever space the caller
    emits (DC Blender Z-up when a slots.json is present). Anchor kinds without a
    trim mapping are skipped (Patina has no cover suggestion for them).
    """
    region_by_piece = {r.piece: r for r in regions}
    orders = []
    for i, a in enumerate(anchors):
        piece = _ANCHOR_TRIM.get(a.kind)
        if piece is None or piece not in region_by_piece:
            continue
        r = region_by_piece[piece]
        rng = rng_for(seed, "dressing", a.kind, str(i))
        orders.append({
            "anchor_kind": a.kind,
            "cover": _ANCHOR_COVER.get(a.kind, "strip"),
            "collision": "none",
            "trim_piece": piece,
            "uv_region": [round(r.u0, 4), round(r.v0, 4), round(r.u1, 4), round(r.v1, 4)],
            "pos": list(a.pos),
            "normal": list(a.normal),
            "size": a.size,
            "seed_offset": int(rng.integers(0, 1_000_000)),
        })
    return orders


def dressing_manifest(anchors: list, regions: list[TrimRegion], *, seed: int,
                      source: str, sheet_file: str, space: str,
                      building_id: str | None = None) -> dict:
    """The ``<out>.dressing.json`` payload: atlas + per-anchor build orders."""
    orders = dressing_orders(anchors, regions, seed=seed)
    kinds: dict[str, int] = {}
    for o in orders:
        kinds[o["cover"]] = kinds.get(o["cover"], 0) + 1
    out = {
        "schema": "patina-dressing/1",
        "source": source,
        "seed": seed,
        "space": space,
        "trim_sheet": sheet_file,
        "trim_regions": regions_dict(regions),
        "note": "non-collision cover build orders for Zoo; Patina supplies the "
                "trim atlas + placement, Zoo builds the geometry (collision: none)",
        "counts": dict(sorted(kinds.items())),
        "orders": orders,
    }
    if building_id:
        out["building_id"] = building_id
    return out
