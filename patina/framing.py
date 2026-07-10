"""Facade kit (v0.18): frame, gutter, and pilaster orders.

The last of the architectural-depth bucket — the "fake depth with thin
geometry" items that only stick out a few inches. Like panel fields, all
three ride the slots.json modular alignment, emit spec-space build orders,
and leave the geometry to Zoo's ``dress_cover``:

* **Frames** — every doorway/window slot carries its exact opening rect
  (``fit.openings``: width, height, sill), so each opening gets one
  ``frame`` order: a picture-frame of four thin strips Zoo builds around
  the hole. ``size2`` is the opening, not the module.
* **Gutters** — one ``gutter_run`` per exterior wall slot, spanning the
  module width just under the roofline. Seams between adjacent modules
  land at module boundaries, which is where real gutter sections join.
* **Pilasters** — one vertical ``pilaster`` at each wall slot's left edge
  (module seams every module width), reading as columns at sixth-gen
  fidelity. Adjacent modules share seams, so one edge per slot avoids
  doubles; the run's far end is closed by the neighbouring wall's own
  pilaster or a corner.

Deterministic, arithmetic placement; ``seed_offset`` per order from
``(seed, kind, slot_id, ...)`` streams. Patina still ships zero geometry.
"""

from __future__ import annotations

import math

from .determinism import rng_for
from .paneling import wall_slots
from .slots import SlotManifest

_FRAME_ROLES = ("doorway", "window")


def _uv(regions: list, piece: str):
    r = next((x for x in regions if x.piece == piece), None)
    if r is None:
        return None
    return [round(r.u0, 4), round(r.v0, 4), round(r.u1, 4), round(r.v1, 4)]


def _face(slot, lx: float, lz_abs: float):
    """World position + outward normal for a point on a slot's outer face.

    ``lx`` is along the module (metres from center), ``lz_abs`` is absolute
    world Z supplied by the caller. Same rotation math as paneling.
    """
    d = float(slot.dims[1]) * float(slot.scale[1])
    rad = math.radians(float(slot.rot_y))
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    ly = d / 2.0
    px = float(slot.translation[0]) + lx * cos_r - ly * sin_r
    py = float(slot.translation[1]) + lx * sin_r + ly * cos_r
    n = [round(-sin_r, 3) + 0.0, round(cos_r, 3) + 0.0, 0.0]
    return [round(px, 3), round(py, 3), round(lz_abs, 3)], n


def _base_z(slot) -> float:
    h = float(slot.dims[2]) * float(slot.scale[2])
    tz = float(slot.translation[2])
    return tz if slot.pivot == "base" else tz - h / 2.0


def frame_orders(manifest: SlotManifest, regions: list, *, seed: int,
                 frame_width: float = 0.12) -> list[dict]:
    """One ``frame`` order per opening on every doorway/window slot."""
    uv = _uv(regions, "frame")
    orders = []
    for s in manifest.slots:
        if s.role not in _FRAME_ROLES or not s.dims:
            continue
        base_z = _base_z(s)
        for k, op in enumerate(s.openings):
            ow = float(op.get("width", 0.0))
            oh = float(op.get("height", 0.0))
            if ow <= 0.0 or oh <= 0.0:
                continue
            sill = float(op.get("sill", 0.0))
            pos, n = _face(s, 0.0, base_z + sill + oh / 2.0)
            rng = rng_for(seed, "frame", s.slot_id, str(k))
            orders.append({
                "anchor_kind": "opening_frame",
                "cover": "frame",
                "collision": "none",
                "trim_piece": "frame",
                "uv_region": uv,
                "slot_id": s.slot_id,
                "opening_kind": op.get("kind", "door"),
                "pos": pos, "normal": n,
                "size": round(ow, 3),
                "size2": [round(ow, 3), round(oh, 3)],
                "frame_width": frame_width,
                "seed_offset": int(rng.integers(0, 1_000_000)),
            })
    return orders


def gutter_orders(manifest: SlotManifest, regions: list, *, seed: int,
                  drop: float = 0.08) -> list[dict]:
    """One ``gutter_run`` per exterior wall slot, just under the roofline."""
    uv = _uv(regions, "flashing")
    orders = []
    for s in wall_slots(manifest):
        w = float(s.dims[0]) * float(s.scale[0])
        h = float(s.dims[2]) * float(s.scale[2])
        pos, n = _face(s, 0.0, _base_z(s) + h - drop)
        rng = rng_for(seed, "gutter", s.slot_id)
        orders.append({
            "anchor_kind": "roof_gutter",
            "cover": "gutter_run",
            "collision": "none",
            "trim_piece": "flashing",
            "uv_region": uv,
            "slot_id": s.slot_id,
            "pos": pos, "normal": n,
            "size": round(w, 3),
            "seed_offset": int(rng.integers(0, 1_000_000)),
        })
    return orders


def pilaster_orders(manifest: SlotManifest, regions: list, *, seed: int,
                    width: float = 0.24) -> list[dict]:
    """One vertical ``pilaster`` at each exterior wall slot's left edge."""
    uv = _uv(regions, "pilaster")
    orders = []
    for s in wall_slots(manifest):
        w = float(s.dims[0]) * float(s.scale[0])
        h = float(s.dims[2]) * float(s.scale[2])
        pos, n = _face(s, -w / 2.0, _base_z(s) + h / 2.0)
        rng = rng_for(seed, "pilaster", s.slot_id)
        orders.append({
            "anchor_kind": "wall_pilaster",
            "cover": "pilaster",
            "collision": "none",
            "trim_piece": "pilaster",
            "uv_region": uv,
            "slot_id": s.slot_id,
            "pos": pos, "normal": n,
            "size": round(width, 3),
            "size2": [round(width, 3), round(h, 3)],
            "seed_offset": int(rng.integers(0, 1_000_000)),
        })
    return orders
