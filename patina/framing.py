"""Facade kit (v0.18): frame, gutter, and pilaster orders.

The last of the architectural-depth bucket — the "fake depth with thin
geometry" items that only stick out a few inches. Like panel fields, all
three ride the slots.json modular alignment, emit spec-space build orders,
and leave the geometry to Zoo's ``dress_cover``:

* **Frames** — every doorway/window slot carries its exact opening rect
  (``fit.openings``: width, height, sill), so each opening gets one
  ``frame`` order: a picture-frame of four thin strips Zoo builds around
  the hole. ``size2`` is the opening, not the module.

  NOT REQUESTED BY THE PIPELINE, and here is why. Every Zoo module with an
  opening already frames it -- ``doorway_*`` ships ``Doorway_Jamb_L``,
  ``Doorway_Jamb_R`` and ``Doorway_Header``; ``window_*`` ships those plus
  ``Window_Sill`` and ``Window_Glass``. Adding these strips put a second
  frame around the first on all 16 openings of a shipped building, which is
  exactly what it looks like. This pass also gives a DOORWAY a sill -- a bar
  across a threshold you walk over -- which Zoo's doorway deliberately does
  not have, and a ``breach`` is a hole blown through a wall that should carry
  no frame at all. Kept for a greybox build whose modules do no framing of
  their own; the Level Factory adapter stopped passing ``--frames``.
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
from .slots import SlotManifest, footprint_center, outward_sign

_FRAME_ROLES = ("doorway", "window")


def _uv(regions: list, piece: str):
    r = next((x for x in regions if x.piece == piece), None)
    if r is None:
        return None
    return [round(r.u0, 4), round(r.v0, 4), round(r.u1, 4), round(r.v1, 4)]


def _face(slot, lx: float, lz_abs: float, out: float = 1.0):
    """World position + outward normal for a point on a slot's outer face.

    ``lx`` is along the module (metres from center), ``lz_abs`` is absolute
    world Z supplied by the caller. Same rotation math as paneling.

    ``out`` is which of the module's two faces is the outer one, +1 or -1 from
    :func:`slots.outward_sign`. It defaults to +1 -- the value this function
    assumed for its whole life -- so a caller that has no manifest to derive it
    from still gets the old answer instead of an error, but every caller here
    passes it. WHICH FACE IS OUT IS NOT LOCAL +Y: `rot_y` swings local +Y to
    -X at 90 degrees and +X at 270, so all 96 east and west pilasters stood on
    the inside of their walls.
    """
    d = slot.size()[1]
    rad = math.radians(float(slot.rot_y))
    cos_r, sin_r = math.cos(rad), math.sin(rad)
    ly = out * d / 2.0
    px = float(slot.translation[0]) + lx * cos_r - ly * sin_r
    py = float(slot.translation[1]) + lx * sin_r + ly * cos_r
    n = [round(out * -sin_r, 3) + 0.0, round(out * cos_r, 3) + 0.0, 0.0]
    return [round(px, 3), round(py, 3), round(lz_abs, 3)], n


def _base_z(slot) -> float:
    """The module's own floor plane. One rule, in :meth:`Slot.base_z`."""
    return slot.base_z()


def frame_orders(manifest: SlotManifest, regions: list, *, seed: int,
                 frame_width: float = 0.12) -> list[dict]:
    """One ``frame`` order per opening on every doorway/window slot."""
    uv = _uv(regions, "frame")
    orders = []
    center = footprint_center(manifest)
    for s in manifest.slots:
        if s.role not in _FRAME_ROLES or not s.dims:
            continue
        out = outward_sign(s, center)
        base_z = _base_z(s)
        for k, op in enumerate(s.openings):
            ow = float(op.get("width", 0.0))
            oh = float(op.get("height", 0.0))
            if ow <= 0.0 or oh <= 0.0:
                continue
            sill = float(op.get("sill", 0.0))
            pos, n = _face(s, 0.0, base_z + sill + oh / 2.0, out)
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


def roofline_slots(manifest: SlotManifest) -> list:
    """Exterior wall slots on the TOP storey -- the ones that have a roofline.

    A gutter is a roofline object. Emitting one per exterior wall slot put a
    run at the top of EVERY storey: measured on the shipped building, 299
    gutters at z -0.38, 3.62 and 7.62, which is the basement ceiling, the
    first floor line and the actual roof. Those are the pale horizontal bands
    crossing the facade at every floor, and at 0.10 m proud a gutter is the
    deepest cover in the kit, so they were also the loudest thing on it.

    Slots with no ``story`` fall back to every wall slot -- an older manifest
    should keep its old output rather than silently lose its gutters.
    """
    walls = wall_slots(manifest)
    storeys = [int(s.story) for s in walls if s.story is not None]
    if not storeys:
        return walls
    top = max(storeys)
    return [s for s in walls if s.story is not None and int(s.story) == top]


def gutter_orders(manifest: SlotManifest, regions: list, *, seed: int,
                  drop: float = 0.08) -> list[dict]:
    """One ``gutter_run`` per top-storey exterior wall slot, under the roofline."""
    uv = _uv(regions, "flashing")
    orders = []
    center = footprint_center(manifest)
    for s in roofline_slots(manifest):
        w, _d, h = s.size()
        pos, n = _face(s, 0.0, _base_z(s) + h - drop, outward_sign(s, center))
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
                    width: float = 0.12) -> list[dict]:
    """One vertical ``pilaster`` at each exterior wall slot's left edge."""
    uv = _uv(regions, "pilaster")
    orders = []
    center = footprint_center(manifest)
    for s in wall_slots(manifest):
        w, _d, h = s.size()
        # ``lx`` stays -w/2 whatever the outward side turns out to be. Flipping
        # the face does not flip the module's own left edge, and every slot in
        # one wall run shares a rot_y and therefore a sign, so they all still
        # pick the same end and adjacent modules still avoid doubling up.
        pos, n = _face(s, -w / 2.0, _base_z(s) + h / 2.0,
                       outward_sign(s, center))
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
