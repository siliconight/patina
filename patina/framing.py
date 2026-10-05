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
from .slots import (SlotManifest, footprint_center, modal_thickness,
                    wall_frame)

_FRAME_ROLES = ("doorway", "window")


def _uv(regions: list, piece: str):
    r = next((x for x in regions if x.piece == piece), None)
    if r is None:
        return None
    return [round(r.u0, 4), round(r.v0, 4), round(r.u1, 4), round(r.v1, 4)]


def _face(slot, lx: float, lz_abs: float, frame=None):
    """World position + outward normal for a point on a slot's outer face.

    ``lx`` is metres along the wall from its centre, ``lz_abs`` is absolute
    world Z supplied by the caller. ``frame`` is the slot's
    ``(run, thickness, along, outward)`` from :func:`slots.wall_frame`; the
    whole placement is then one line of arithmetic.

    IT USED TO DO THE TRIGONOMETRY HERE AND GET BOTH HALVES WRONG. It read
    ``dims[1]`` as the thickness -- on an east or west wall that is the two
    metre RUN, so a gutter sat 1.0 m off the facade instead of 0.175 -- and it
    took local +Y as outward, which ``rot_y`` swings to -X at 90 degrees, so
    the same covers pointed into the building. Both are settled once, in
    ``wall_frame``, rather than in each family that draws something.

    ``frame`` defaults to None, which reproduces the old single-convention
    answer, so a caller with no manifest to derive a centroid from still gets
    a result rather than an error. Every caller here passes one.
    """
    if frame is None:
        rad = math.radians(float(slot.rot_y))
        frame = (slot.size()[0], slot.size()[1],
                 (math.cos(rad), math.sin(rad)),
                 (-math.sin(rad), math.cos(rad)))
    _run, thick, along, out = frame
    ly = thick / 2.0
    px = float(slot.translation[0]) + lx * along[0] + ly * out[0]
    py = float(slot.translation[1]) + lx * along[1] + ly * out[1]
    n = [round(out[0], 3) + 0.0, round(out[1], 3) + 0.0, 0.0]
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
    thick_m = modal_thickness(manifest)
    for s in manifest.slots:
        if s.role not in _FRAME_ROLES or not s.dims:
            continue
        frame = wall_frame(s, center, thick_m)
        base_z = _base_z(s)
        for k, op in enumerate(s.openings):
            ow = float(op.get("width", 0.0))
            oh = float(op.get("height", 0.0))
            if ow <= 0.0 or oh <= 0.0:
                continue
            sill = float(op.get("sill", 0.0))
            pos, n = _face(s, 0.0, base_z + sill + oh / 2.0, frame)
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


def window_fixture_orders(manifest: SlotManifest, regions: list, *,
                          seed: int) -> list[dict]:
    """AN EMPTY'S WINDOW FIXTURES (0.26.0), as Zoo (>= 1.69.0) builds them.

    * ``window_bars`` -- one per opening of a barred window, at the opening's
      centre on the wall face, sized to it (``size2``);
    * ``ac_unit`` -- one per opening of a window with an air conditioner, at
      its SILL on the wall face: Zoo stands the unit there and reaches it back
      to the pane, and ``size2`` tells it how wide the opening is to close.

    ONLY ON A FACADE WINDOW. Deli Counter (>= 0.181.0) writes `bars` and `ac`
    only on an Empty's sealed windows; a real window is a firing line, and
    bars a bullet passes through would lie about it, so a slot without
    `glazing: "facade"` orders nothing whatever it carries. THE SLOT IS THE
    OPT-IN, so there is no flag. Exempt from the opening keep-out, as a frame
    is (`openings.EXEMPT`).
    """
    uv = _uv(regions, "frame")
    orders = []
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    for s in manifest.slots:
        if (s.role != "window" or s.glazing != "facade" or not s.dims
                or not (s.ac or s.bars)):
            continue
        frame = wall_frame(s, center, thick_m)
        base_z = _base_z(s)
        for k, op in enumerate(s.openings):
            ow = float(op.get("width", 0.0))
            oh = float(op.get("height", 0.0))
            if ow <= 0.0 or oh <= 0.0:
                continue
            sill = float(op.get("sill", 0.0))
            fixtures = []
            if s.bars:
                fixtures.append(("window_bars", base_z + sill + oh / 2.0))
            if s.ac:
                fixtures.append(("ac_unit", base_z + sill))
            for cover, z in fixtures:
                pos, n = _face(s, 0.0, z, frame)
                rng = rng_for(seed, cover, s.slot_id, str(k))
                orders.append({
                    "anchor_kind": "window_fixture",
                    "cover": cover,
                    "collision": "none",
                    "trim_piece": "frame",
                    "uv_region": uv,
                    "slot_id": s.slot_id,
                    "pos": pos, "normal": n,
                    "size": round(ow, 3),
                    "size2": [round(ow, 3), round(oh, 3)],
                    "seed_offset": int(rng.integers(0, 1_000_000)),
                })
    return orders


def opening_trim_orders(manifest: SlotManifest, regions: list, *,
                        seed: int) -> list[dict]:
    """AN EMPTY'S STONE LINTELS AND SILLS (0.27.0), as Zoo (>= 1.71.0) builds
    them. The walker's South Philly photograph: "white stone lintels and
    sills over and under every window".

    * ``lintel`` -- one per opening of a facade window or doorway, at the
      opening's HEAD on the wall face; Zoo stands the block on that line.
    * ``window_sill`` -- one per opening of a facade window, at its SILL on
      the wall face; Zoo hangs the block below that line. A door has none:
      its threshold is the sidewalk's.

    ONLY ON A FACADE SLOT (`glazing: "facade"`), as the window fixtures are,
    and for the same reason they are exempt from the opening keep-out
    (`openings.EXEMPT`): they sit on the opening's own head and sill, inside
    its margin, and the opening is sealed. ``size2`` is the opening.
    """
    uv = _uv(regions, "frame")
    orders = []
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    for s in manifest.slots:
        if s.role not in ("window", "doorway") or s.glazing != "facade" or not s.dims:
            continue
        frame = wall_frame(s, center, thick_m)
        base_z = _base_z(s)
        for k, op in enumerate(s.openings):
            ow = float(op.get("width", 0.0))
            oh = float(op.get("height", 0.0))
            if ow <= 0.0 or oh <= 0.0:
                continue
            sill = float(op.get("sill", 0.0))
            trims = [("lintel", base_z + sill + oh)]
            if s.role == "window":
                trims.append(("window_sill", base_z + sill))
            for cover, z in trims:
                pos, n = _face(s, 0.0, z, frame)
                rng = rng_for(seed, cover, s.slot_id, str(k))
                orders.append({
                    "anchor_kind": "opening_trim",
                    "cover": cover,
                    "collision": "none",
                    "trim_piece": "frame",
                    "uv_region": uv,
                    "slot_id": s.slot_id,
                    "pos": pos, "normal": n,
                    "size": round(ow, 3),
                    "size2": [round(ow, 3), round(oh, 3)],
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

    A PARAPET IS NOT A ROOFLINE (0.25.0). Deli Counter 0.177.0 made each
    parapet tile a wall slot on the storey above the top floor, so "the top
    storey" became the parapet and the gutters went up onto it: cold run 9151
    put `gs_empty_rowhome_f`'s at z 9.92 on `parapet_*` slots, the top of the
    parapet, where 9148 had them at 8.92 under the roof. A gutter hangs at
    the eave, which is the top of the highest STOREY wall, so parapets are
    left out before the top storey is found.

    AND THE TOP STOREY'S OPENINGS ARE PART OF IT (0.25.1). A window is a slot
    of its own, so a roofline of WALL slots stopped at every top-floor window
    bay: cold run 9153's rowhomes showed a pale gutter broken over each one.
    An exterior window, door or breach on the top storey carries its stretch
    of the eave. Its module is the storey's height (Deli Counter >= 0.176.0
    names heights apart), so its gutter hangs at the same line, above the
    opening's head -- clear of the keep-out the dressing filter enforces.
    """
    walls = [s for s in wall_slots(manifest) if not _is_parapet(s)]
    storeys = [int(s.story) for s in walls if s.story is not None]
    if not storeys:
        return walls
    top = max(storeys)
    eave = [s for s in walls if s.story is not None and int(s.story) == top]
    eave += [s for s in manifest.slots
             if s.role in _FACE_ROLES and str(s.slot_id).startswith("ext_")
             and s.story is not None and int(s.story) == top]
    return eave


def gutter_orders(manifest: SlotManifest, regions: list, *, seed: int,
                  drop: float = 0.08) -> list[dict]:
    """One ``gutter_run`` per top-storey exterior wall slot, under the roofline."""
    uv = _uv(regions, "flashing")
    orders = []
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    for s in roofline_slots(manifest):
        _w, _d, h = s.size()
        # `run`, not dims[0]. A west wall's dims[0] is its 35 cm THICKNESS, so
        # the gutter shipped as a 35 cm stub every 2 m -- dashes along the
        # roofline -- and 1.0 m clear of the wall it belongs to.
        run, _thick, _along, _out = frame = wall_frame(s, center, thick_m)
        pos, n = _face(s, 0.0, _base_z(s) + h - drop, frame)
        rng = rng_for(seed, "gutter", s.slot_id)
        orders.append({
            "anchor_kind": "roof_gutter",
            "cover": "gutter_run",
            "collision": "none",
            "trim_piece": "flashing",
            "uv_region": uv,
            "slot_id": s.slot_id,
            "pos": pos, "normal": n,
            "size": round(run, 3),
            "seed_offset": int(rng.integers(0, 1_000_000)),
        })
    return orders


def _is_parapet(slot) -> bool:
    """A parapet tile's slot (Deli Counter >= 0.177.0): `parapet_<side>...`."""
    return str(slot.slot_id).startswith("parapet_")


#: A DOWNSPOUT A FACE, AND ONE MORE FOR EVERY TWELVE METRES OF GUTTER
#: (0.25.0). The rule of thumb is one downspout per 30 to 40 feet of gutter --
#: 9 to 12 m -- and twelve is its long end. Chosen from that, not derived: no
#: roof area and no rainfall are modelled.
DOWNSPOUT_EVERY = 12.0
#: The pipe's centre, in from the end of its face, metres -- at the corner or
#: the party line, where the walker's South Philly row has it.
DOWNSPOUT_INSET = 0.15
#: The gutter's height on the wall, mirrored from Zoo's
#: `zoo_keeper/core/dressing.py` `_COVER["gutter_run"]["cross"]`, which
#: `openings._ZOO_CROSS` mirrors too: the pipe tops out at the gutter's
#: underside.
GUTTER_CROSS = 0.14
#: Opening slots: a face carrying one of these is a face somebody looks at.
_FACE_ROLES = ("window", "doorway", "breach")


def _side(frame) -> tuple:
    """A face's key: its outward normal, rounded to whole units -- exact for
    the axis-aligned shells Deli Counter emits. `facing` is not used: it
    points into the room a wall bounds (see `test_framing`)."""
    out = frame[3]
    return (round(out[0]), round(out[1]))


def downspout_orders(manifest: SlotManifest, regions: list, *, seed: int,
                     keep_out: list | None = None, drop: float = 0.08) -> list[dict]:
    """Downspouts from the gutter to the ground (0.25.0).

    The walker, 2026-10-04: "also we need rain gutters". A gutter reads from
    the street by the pipe that carries its water down; nothing drew one.

    * ON THE FACES SOMEBODY SEES: every roofline face with a window, door or
      breach on any storey. A blank side wall -- an Empty's party wall -- gets
      none.
    * ONE A FACE, ONE MORE PER `DOWNSPOUT_EVERY` OF GUTTER: a short face takes
      a seeded end; a longer one both ends, and the rest spread between them.
    * CLEAR OF THE OPENINGS by the keep-out Patina already enforces
      (`openings.keep_out_boxes`): a blocked end gives way to the other, an
      interior pipe slides to the nearest clear module seam, and a pipe with
      nowhere clear is left out. The placement and the filter are one test.
    * FROM THE GUTTER'S UNDERSIDE TO THE GROUND: the top storey's roofline
      less `drop` and half `GUTTER_CROSS`, down to the floor of the face's
      storey 0. ``size`` is the length and ``pos`` its middle, as a conduit's.
    """
    from . import openings as _openings
    uv = _uv(regions, "flashing")
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    top = roofline_slots(manifest)
    if not top:
        return []
    faced = set()
    for s in manifest.slots:
        if s.role in _FACE_ROLES and str(s.slot_id).startswith("ext_"):
            faced.add(_side(wall_frame(s, center, thick_m)))
    ground = {}
    for s in wall_slots(manifest):
        if _is_parapet(s):
            continue
        key = _side(wall_frame(s, center, thick_m))
        z = _base_z(s)
        if s.story is not None and int(s.story) == 0:
            ground[key] = min(ground.get(key, z), z)
    runs = {}
    for s in top:
        frame = wall_frame(s, center, thick_m)
        runs.setdefault(_side(frame), []).append((s, frame))
    orders = []
    for key in sorted(runs):
        if key not in faced:
            continue
        items = runs[key]

        def span(item):
            s, (run, _t, along, _o) = item
            a = float(s.translation[0]) * along[0] + float(s.translation[1]) * along[1]
            return a - run / 2.0, a + run / 2.0, a

        lo, hi = min(span(it)[0] for it in items), max(span(it)[1] for it in items)
        s0, _f0 = items[0]
        top_z = _base_z(s0) + s0.size()[2] - drop - GUTTER_CROSS / 2.0
        base = ground.get(key, min(_base_z(s) for s, _f in items))
        if top_z - base <= 0.5:
            continue
        mid_z = (top_z + base) / 2.0
        rng = rng_for(seed, "downspout", f"{key[0]}_{key[1]}")

        def order_at(a):
            """The order whose pipe stands at along-coordinate ``a``."""
            for it in items:
                a0, a1, ac = span(it)
                if a0 - 1e-6 <= a <= a1 + 1e-6:
                    s, frame = it
                    pos, n = _face(s, a - ac, mid_z, frame)
                    return {"anchor_kind": "downspout", "cover": "downspout",
                            "collision": "none", "trim_piece": "flashing",
                            "uv_region": uv, "slot_id": s.slot_id,
                            "pos": pos, "normal": n,
                            "size": round(top_z - base, 3),
                            "seed_offset": int(rng.integers(0, 1_000_000))}
            return None

        def clear(o):
            return o is not None and (not keep_out or not _openings.hits(o, keep_out))

        ends = [lo + DOWNSPOUT_INSET, hi - DOWNSPOUT_INSET]
        if int(rng.integers(0, 2)):
            ends.reverse()
        n = max(1, math.ceil((hi - lo) / DOWNSPOUT_EVERY - 1e-9))
        picked, taken = [], []
        if n == 1:
            for a in ends:
                o = order_at(a)
                if clear(o):
                    picked.append(o)
                    break
        else:
            for a in sorted(ends):
                o = order_at(a)
                if clear(o):
                    picked.append(o)
                    taken.append(a)
            # the rest stand at module seams -- where gutter sections join --
            # nearest an even spacing, each sliding to the next seam out when
            # an opening is in its way
            seams = sorted({round(e, 6) for it in items for e in span(it)[:2]
                            if lo + 1e-6 < e < hi - 1e-6})
            for k in range(1, n - 1):
                target = lo + (hi - lo) * k / (n - 1)
                for a in sorted(seams, key=lambda e: abs(e - target)):
                    o = order_at(a)
                    if clear(o) and all(abs(a - t) > 1e-6 for t in taken):
                        picked.append(o)
                        taken.append(a)
                        break
        orders += picked
    return orders


def pilaster_orders(manifest: SlotManifest, regions: list, *, seed: int,
                    width: float = 0.12) -> list[dict]:
    """One vertical ``pilaster`` at each exterior wall slot's left edge."""
    uv = _uv(regions, "pilaster")
    orders = []
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    for s in wall_slots(manifest):
        _w, _d, h = s.size()
        run, _thick, _along, _out = frame = wall_frame(s, center, thick_m)
        # ``lx`` stays -run/2 whatever the outward side turns out to be.
        # Flipping the face does not flip the wall's own left end, and every
        # slot in one run shares a frame, so they all still pick the same end
        # and adjacent modules still avoid doubling up at the seam.
        pos, n = _face(s, -run / 2.0, _base_z(s) + h / 2.0, frame)
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
