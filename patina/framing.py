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


def door_fixture_orders(manifest: SlotManifest, regions: list, *,
                        seed: int) -> list[dict]:
    """AN EMPTY'S IRON SECURITY DOOR (0.28.0), as Zoo (>= 1.72.0) builds it:
    one ``security_door`` per opening of a facade doorway whose slot carries
    `security_door` (Deli Counter >= 0.182.0 writes it on the front door of a
    house that has one), at the opening's centre on the wall face, sized to
    it. Zoo hangs it in the reveal, in front of the leaf.

    ONLY ON A FACADE DOORWAY, as the window fixtures are: a real door is a way
    in. The slot is the opt-in, and the cover is exempt from the opening
    keep-out (`openings.EXEMPT`)."""
    uv = _uv(regions, "frame")
    orders = []
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    for s in manifest.slots:
        if (s.role != "doorway" or s.glazing != "facade" or not s.dims
                or not s.security_door):
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
            rng = rng_for(seed, "security_door", s.slot_id, str(k))
            orders.append({
                "anchor_kind": "door_fixture",
                "cover": "security_door",
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


#: AN EMPTY'S ROOF FIXTURES (0.29.0): where they stand, measured back into the
#: roof from the inner face of the front parapet. From across the road -- an
#: eye at 1.6 m some 14 m from the facade -- anything less than about 0.6 m
#: over the parapet per metre behind it is hidden, so both stand near the
#: front. The antenna 1.0 to 1.6 m back, within 15 % of the roof's width of
#: its centreline, its mast and boom drawn per house; the dish 0.25 m back
#: and 18 to 32 % out on the other half, so the two never share a footing,
#: its bowl's centre `DISH_ABOVE_PARAPET` over the parapet's top.
ANTENNA_SETBACK = (1.0, 1.6)
ANTENNA_ACROSS = 0.15
ANTENNA_MAST = (2.6, 3.4)
ANTENNA_BOOM = (1.6, 2.6)
DISH_SETBACK = 0.25
DISH_ACROSS = (0.18, 0.32)
DISH_ABOVE_PARAPET = 0.6
DISH_WIDTH = 0.5
#: Bearings in the building's own frame -- Deli Counter's facings, N = +y and
#: E = +x -- as compass degrees. Philadelphia's TV transmitters stand in
#: Roxborough, north-west of South Philly, so a rowhouse antenna points about
#: 325; the DSS satellites sit at 101 W, so a Philadelphia dish looks about
#: 211, SSW (and up 41 degrees, Zoo's `DISH_TILT`). A building turned at
#: placement turns its fixtures with it; Level Factory's terrace turns every
#: house of a row the same way, so a row's antennas point one way, which is
#: what a street shows.
ANTENNA_BEARING = 325.0
DISH_BEARING = 211.0
_FACING = {"N": (0.0, 1.0), "E": (1.0, 0.0), "S": (0.0, -1.0), "W": (-1.0, 0.0)}


def _bearing(deg: float) -> list:
    r = math.radians(deg)
    return [round(math.sin(r), 4), round(math.cos(r), 4), 0.0]


def _parapet(manifest: SlotManifest, front: str) -> tuple:
    """``(thickness, height)`` of the front's parapet -- Deli Counter (>= 0.177.0)
    names its tiles `parapet_<facing>_...` -- or ``(0.0, 0.0)`` with none."""
    for s in manifest.slots:
        if str(s.slot_id).startswith(f"parapet_{front}_") and s.dims:
            w, d, h = s.size()
            return min(w, d), h
    return 0.0, 0.0


def roof_fixture_orders(manifest: SlotManifest, regions: list, *,
                        seed: int) -> list[dict]:
    """AN EMPTY'S TV ANTENNA AND SATELLITE DISH (0.29.0), as Zoo (>= 1.74.0)
    builds them: a ``tv_antenna`` and a ``sat_dish`` on the roof's top
    surface, up-facing, each with the bearing it looks along as its
    ``tangent``.

    Deli Counter (>= 0.185.0) writes `antenna` / `dish` on an Empty's roof
    slot with `front`, the facing of the wall that holds its front door. THE
    SLOT IS THE OPT-IN, as a window's fixtures are; one with no `front` orders
    nothing, since there is no parapet to set them back from. Exempt from the
    opening keep-out (`openings.EXEMPT`): nothing walks or shoots across an
    Empty's roof.

    Each house draws its own antenna, its place and the dish's side from
    ``(seed, kind, building, slot)``: every Empty's roof slot is
    `roof_footprint`, so keyed by the slot alone the street would draw one.
    """
    uv = _uv(regions, "frame")
    orders = []
    for s in manifest.slots:
        if s.role != "roof" or not s.dims or not (s.antenna or s.dish):
            continue
        f = _FACING.get(str(s.front or ""))
        if f is None:
            continue
        w, d, _h = s.size()
        rad = math.radians(float(s.rot_y))
        a = (math.cos(rad), math.sin(rad))            # the slot's local x
        b = (-math.sin(rad), math.cos(rad))           # and its local y
        p = (-f[1], f[0])                             # across the house
        half = (abs(f[0] * a[0] + f[1] * a[1]) * w + abs(f[0] * b[0] + f[1] * b[1]) * d) / 2.0
        across = abs(p[0] * a[0] + p[1] * a[1]) * w + abs(p[0] * b[0] + p[1] * b[1]) * d
        thick, par_h = _parapet(manifest, str(s.front))
        inner = half - thick
        top = s.base_z() + s.size()[2]
        cx, cy = float(s.translation[0]), float(s.translation[1])

        def at(back, off):
            return [round(cx + f[0] * (inner - back) + p[0] * off, 3),
                    round(cy + f[1] * (inner - back) + p[1] * off, 3), round(top, 3)]

        side = 1.0
        if s.antenna:
            rng = rng_for(seed, "tv_antenna", manifest.building_id, s.slot_id)
            back = float(rng.uniform(*ANTENNA_SETBACK))
            off = float(rng.uniform(-ANTENNA_ACROSS, ANTENNA_ACROSS)) * across
            mast = round(float(rng.uniform(*ANTENNA_MAST)), 3)
            boom = round(float(rng.uniform(*ANTENNA_BOOM)), 3)
            side = -1.0 if off >= 0.0 else 1.0
            orders.append({
                "anchor_kind": "roof_fixture", "cover": "tv_antenna", "collision": "none",
                "trim_piece": "frame", "uv_region": uv, "slot_id": s.slot_id,
                "pos": at(back, off), "normal": [0.0, 0.0, 1.0],
                "tangent": _bearing(ANTENNA_BEARING),
                "size": boom, "size2": [boom, mast],
                "seed_offset": int(rng.integers(0, 1_000_000)),
            })
        if s.dish:
            rng = rng_for(seed, "sat_dish", manifest.building_id, s.slot_id)
            if not s.antenna:
                side = 1.0 if rng.uniform() < 0.5 else -1.0
            off = side * float(rng.uniform(*DISH_ACROSS)) * across
            orders.append({
                "anchor_kind": "roof_fixture", "cover": "sat_dish", "collision": "none",
                "trim_piece": "frame", "uv_region": uv, "slot_id": s.slot_id,
                "pos": at(DISH_SETBACK, off), "normal": [0.0, 0.0, 1.0],
                "tangent": _bearing(DISH_BEARING),
                "size": DISH_WIDTH,
                "size2": [DISH_WIDTH, round(par_h + DISH_ABOVE_PARAPET, 3)],
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
    """One ``gutter_run`` per top-storey exterior wall slot, under the roofline.

    NOT ON AN EMPTY'S PARTY WALL (0.29.1). On an Empty -- a shell any of whose
    slots carries `glazing: "facade"` -- a face with no window, door or breach
    on any storey is a party wall, and a rowhouse roof drains front and back:
    the downspouts already keep to faces with openings. Between two houses of
    one height the party-wall gutter was hidden; beside a lower neighbour it
    stood exposed and, lit against an unlit wall, read as lines floating in
    the sky (roadmap 184, cold runs 9160 and 9161). A free-standing building
    keeps a gutter on every face, as before.
    """
    uv = _uv(regions, "flashing")
    orders = []
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    empty = any(s.glazing == "facade" for s in manifest.slots)
    faced = {_side(wall_frame(s, center, thick_m)) for s in manifest.slots
             if s.role in _FACE_ROLES and str(s.slot_id).startswith("ext_")}
    scuppered = scupper_sides(manifest)
    for s in roofline_slots(manifest):
        if empty and _side(wall_frame(s, center, thick_m)) not in faced:
            continue
        if _side(wall_frame(s, center, thick_m)) in scuppered:
            continue
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


def scupper_sides(manifest: SlotManifest) -> dict:
    """``{side: roof_z}``: the faces whose roof drains through its parapet (0.34.0, the factory's roadmap 324).

    A flat roof behind a parapet has no eave to hang a gutter from: its water leaves through a scupper in the
    parapet, into a conductor head, down a downspout. Patina hung a gutter at the top storey's wall top anyway, under
    the parapet -- on seed 9082's bank a white aluminium line across the facade 1.4 m below its top, the line that
    read from the street once the parapet stood flush (the factory's docs/findings/parapet_flush/). On a side a
    parapet stands over the gutter is left out and the downspouts run to the roof's surface, ordered `head`, and Zoo
    (>= 1.147.0) builds the head and the scupper.

    NOT ON AN EMPTY. The walker asked for rain gutters on the rowhomes (2026-10-04), and the Empties' parapets are
    their cornices; whether a rowhome drains through its parapet is the walker's call, and until it is made an Empty
    keeps the gutter it has. `roof_z` is the top of the roof slot under the parapet, or the parapet's foot when the
    manifest has none."""
    if any(s.glazing == "facade" for s in manifest.slots):
        return {}
    roofs = [s for s in manifest.slots if s.role == "roof" and s.dims]
    out = {}
    for s in manifest.slots:
        if not _is_parapet(s) or not s.dims:
            continue
        side = str(s.slot_id)[len("parapet_"):][:1]
        out_n = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}.get(side)
        if out_n is None:
            continue
        foot = _base_z(s)
        below = [r.base_z() + r.size()[2] for r in roofs if r.base_z() <= foot + s.size()[2]]
        roof_z = max([z for z in below if z >= foot - 1e-6] or [foot])
        out[out_n] = round(max(out.get(out_n, roof_z), roof_z), 3)
    return out


#: A STRING COURSE AT EVERY FLOOR LINE (the factory's roadmap 324). The walker, 2026-10-29: "Things still look
#: simple, and computer made", and of the target, "the detail and placement of hard surfaces". Deli Counter centres
#: a storey's walls on the footprint line and stops them under the slab above, and the slab stops at that line: so
#: between two storeys a facade carries a 0.3 m band of slab edge recessed half a wall -- a dark groove at every floor
#: of every building that is not an Empty (seed 9082's bank: walls 0 -> 3.3, 3.6 -> 6.9; the factory's
#: docs/findings/slice_look/). A commercial facade marks that line with a string course: a band proud of the wall
#: over the floor's edge. One a wall slot of the storey above, so a band that would cross an opening's keep-out is
#: refused alone; `size2` = [run, height], Zoo builds it `STRING_PROUD` out of the face.
#: NOT ON AN EMPTY: its walls run the full storey with no band between (Deli Counter 0.175.2), and its stone
#: lintels and sills are its language, the walker's to change.
STRING_OVER = 0.05       # the band laps the walls above and below the slab by this, each side
STRING_MIN_GAP = 0.05    # a gap smaller than this is not a slab band (an Empty's, a wall run full height)


def string_course_orders(manifest: SlotManifest, regions: list, *, seed: int) -> list[dict]:
    """One ``string_course`` per exterior wall or opening slot standing on a slab band above grade."""
    if any(s.glazing == "facade" for s in manifest.slots):
        return []
    uv = _uv(regions, "base_course")
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    faces = [s for s in manifest.slots if s.dims and str(s.slot_id).startswith("ext_")
             and s.story is not None and (s.role == "wall" or s.role in _FACE_ROLES)]
    if not faces:
        return []
    ground = min(_base_z(s) for s in faces if int(s.story) == 0) if any(int(s.story) == 0 for s in faces) else None
    tops, bases = {}, {}
    for s in faces:
        key = (_side(wall_frame(s, center, thick_m)), int(s.story))
        tops[key] = max(tops.get(key, -1e9), _base_z(s) + s.size()[2])
        if s.role == "wall":
            bases[key] = min(bases.get(key, 1e9), _base_z(s))
    orders = []
    for s in sorted(faces, key=lambda s: s.slot_id):
        frame = wall_frame(s, center, thick_m)
        side, k = _side(frame), int(s.story)
        below = tops.get((side, k - 1))
        z1 = _base_z(s)
        if below is None or z1 - below < STRING_MIN_GAP or (ground is not None and z1 <= ground + 0.05):
            continue
        # a slot that starts above its storey's floor (an opening set on its sill) stands on no floor line
        if abs(z1 - bases.get((side, k), z1)) > 1e-3:
            continue
        height = z1 - below + 2.0 * STRING_OVER
        run = frame[0]
        pos, n = _face(s, 0.0, (z1 + below) / 2.0, frame)
        rng = rng_for(seed, "string_course", s.slot_id)
        orders.append({
            "anchor_kind": "floor_line",
            "cover": "string_course",
            "collision": "none",
            "trim_piece": "base_course",
            "uv_region": uv,
            "slot_id": s.slot_id,
            "pos": pos, "normal": n,
            "size": round(run, 3),
            "size2": [round(run, 3), round(height, 3)],
            "seed_offset": int(rng.integers(0, 1_000_000)),
        })
    orders += _roof_line_bands(manifest, uv, seed)
    return _corner_bands(_join_bands(orders, manifest))


#: A ROOF-LINE BAND UNDER A PARAPET (0.36.0, the factory's roadmap 324). Deli Counter 0.292.0 stands a parapet on
#: the wall below it, so a facade runs from the ground to the coping with nothing marking where the roof is. A
#: commercial front marks it: a band at the parapet's foot over the roof slab's depth, the cornice line. Patina knows
#: that depth from the roof slot under the parapet (as `scupper_sides` does). Against a parapet standing on its roof
#: (Deli Counter < 0.292.0) there is no depth and no band.
_PARAPET_NORMAL = {"N": (0.0, 1.0), "S": (0.0, -1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}


def _roof_line_bands(manifest: SlotManifest, uv, seed: int) -> list[dict]:
    roofs = [r for r in manifest.slots if r.role == "roof" and r.dims]
    out = []
    for s in sorted((s for s in manifest.slots if _is_parapet(s) and s.dims), key=lambda s: s.slot_id):
        n = _PARAPET_NORMAL.get(str(s.slot_id)[len("parapet_"):][:1])
        if n is None:
            continue
        run, thick, h = s.size()
        foot = _base_z(s)
        tops = [r.base_z() + r.size()[2] for r in roofs]
        tops = [z for z in tops if foot - 1e-6 <= z <= foot + h]
        if not tops or max(tops) - foot < STRING_MIN_GAP:
            continue
        roof_z = max(tops)
        height = roof_z - foot + 2.0 * STRING_OVER
        tx, ty = float(s.translation[0]), float(s.translation[1])
        pos = [round(tx + n[0] * thick / 2.0, 3), round(ty + n[1] * thick / 2.0, 3), round((foot + roof_z) / 2.0, 3)]
        rng = rng_for(seed, "roof_line", s.slot_id)
        out.append({
            "anchor_kind": "roof_line", "cover": "string_course", "collision": "none",
            "trim_piece": "base_course", "uv_region": uv, "slot_id": s.slot_id,
            "pos": pos, "normal": [n[0], n[1], 0.0],
            "size": round(run, 3), "size2": [round(run, 3), round(height, 3)],
            "seed_offset": int(rng.integers(0, 1_000_000)),
        })
    return out


#: Zoo's string course stands this far out of its face (`core.dressing.STRING_PROUD`) and this far into it
#: (`STRING_INTO`): mirrored, so a corner can be closed round the band's own depth.
_BAND_PROUD, _BAND_INTO = 0.06, 0.01
#: A run whose end stands this near the perpendicular face's plane ends at a corner.
_CORNER_REACH = 0.6


def _corner_bands(runs: list[dict]) -> list[dict]:
    """Close every outside corner round a band, the way the coping closes its own (0.36.0).

    Deli Counter's N and S wall runs stop at the side walls' INNER faces and a corner post seats the corner, so a
    band built from wall slots stopped short of every corner by a wall. Per band level: an N or S run reaching
    toward an E or W face plane runs on to that plane plus the band's projection, and an E or W run reaching toward
    an N or S face plane stops at that band's back (the plane less `_BAND_INTO`) -- so the two meet and do not
    overlap, and no face is shared."""
    levels: dict = {}
    for o in runs:
        levels.setdefault((round(o["pos"][2], 3), o["size2"][1]), []).append(o)
    out = []
    for _key, group in sorted(levels.items()):
        planes = {}
        for o in group:
            nx, ny = round(o["normal"][0]), round(o["normal"][1])
            planes[(nx, ny)] = o["pos"][0] if nx else o["pos"][1]
        for o in group:
            nx, ny = round(o["normal"][0]), round(o["normal"][1])
            ax = 0 if nx == 0 else 1
            half = o["size2"][0] / 2.0
            a0, a1 = o["pos"][ax] - half, o["pos"][ax] + half
            lo_key, hi_key = ((-1, 0), (1, 0)) if ax == 0 else ((0, -1), (0, 1))
            for key, is_hi in ((lo_key, False), (hi_key, True)):
                if key not in planes:
                    continue
                plane = planes[key]
                end = a1 if is_hi else a0
                if abs(end - plane) > _CORNER_REACH:
                    continue
                if ax == 0:      # N or S: on past the side face by the band's projection
                    target = plane + _BAND_PROUD if is_hi else plane - _BAND_PROUD
                else:            # E or W: stop at the N or S band's back
                    target = plane - _BAND_INTO if is_hi else plane + _BAND_INTO
                if is_hi:
                    a1 = target
                else:
                    a0 = target
            o = dict(o)
            length = round(a1 - a0, 4)
            pos = list(o["pos"])
            pos[ax] = round((a0 + a1) / 2.0, 4)
            o.update(pos=pos, size=length, size2=[length, o["size2"][1]])
            out.append(o)
    return out


def _join_bands(orders: list[dict], manifest: SlotManifest) -> list[dict]:
    """Bands that meet end to end, on one plane at one height, as one run -- after each slot's band has met the
    opening keep-out alone, so an opening splits a run and never drops it.

    One band a slot left a dark tick at every 2 m joint on the first slice that carried them: each band's ends are
    bevelled by the cover's own bevel, and the recessed slab edge behind showed through the notch (the factory's
    docs/findings/slice_look/, slice 3). A run has no joint to show."""
    from . import openings as _openings
    boxes = _openings.keep_out_boxes(manifest)
    keep = [o for o in orders if not (boxes and _openings.hits(o, boxes))]
    groups: dict = {}
    for o in keep:
        nx, ny = o["normal"][0], o["normal"][1]
        ax = 0 if abs(nx) < 0.5 else 1                       # the axis the band runs along
        key = (round(nx), round(ny), round(o["pos"][1 - ax], 3), round(o["pos"][2], 3), o["size2"][1])
        groups.setdefault(key, []).append((ax, o))
    out = []
    for key in sorted(groups):
        items = sorted(groups[key], key=lambda it: it[1]["pos"][it[0]] - it[1]["size2"][0] / 2.0)
        run = None
        for ax, o in items:
            a0 = o["pos"][ax] - o["size2"][0] / 2.0
            a1 = o["pos"][ax] + o["size2"][0] / 2.0
            if run is not None and a0 - run["a1"] <= 0.01:
                run["a1"] = max(run["a1"], a1)
                run["ids"].append(o["slot_id"])
                continue
            if run is not None:
                out.append(_band_run(run))
            run = {"ax": ax, "a0": a0, "a1": a1, "o": o, "ids": [o["slot_id"]]}
        if run is not None:
            out.append(_band_run(run))
    return out


def _band_run(run: dict) -> dict:
    o = dict(run["o"])
    length = round(run["a1"] - run["a0"], 3)
    pos = list(o["pos"])
    pos[run["ax"]] = round((run["a0"] + run["a1"]) / 2.0, 4)
    o.update(pos=pos, size=length, size2=[length, o["size2"][1]], slot_ids=list(run["ids"]))
    return o


#: QUOINS AT A CIVIC BUILDING'S CORNERS (0.38.0, the factory's roadmap 324). The walker's comps, 2026-10-29: a bank
#: reads as a bank from 50 m -- "an architectural language per building type" (the factory's
#: docs/findings/slice_look/). The slice's bank read as a two-storey commercial box with two cream bands. Quoins --
#: dressed stone blocks at the outside corners, alternately long and short on the two faces -- are what makes a civic
#: front read solid and deliberate. Each block on each face is a short `string_course` in the stone trim (Zoo builds it
#: as it builds the bands), closed round the corner by the bands' rule (`_corner_bands`): the N or S block runs on past
#: the side face by the band's projection, the E or W block stops at its back. A block within `QUOIN_BAND_CLEAR` of a
#: band is left out -- both stand `_BAND_PROUD` from the face, and where they crossed their fronts would be one plane.
CIVIC_WORDS = ("bank", "credit", "courthouse", "landmark", "municipal", "library", "post_office")
QUOIN_H = 0.32
QUOIN_JOINT = 0.03
QUOIN_LONG = 0.62
QUOIN_SHORT = 0.36
QUOIN_BAND_CLEAR = 0.05


def quoin_orders(manifest: SlotManifest, regions: list, *, seed: int, bands=()) -> list[dict]:
    """Quoins up every outside corner of a civic building that is not an Empty, as `string_course` orders."""
    bid = str(manifest.building_id or "").lower()
    if not any(w in bid for w in CIVIC_WORDS) or any(s.glazing == "facade" for s in manifest.slots):
        return []
    from . import openings as _openings
    uv = _uv(regions, "base_course")
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    faces = [s for s in manifest.slots if s.dims and str(s.slot_id).startswith("ext_")
             and s.story is not None and (s.role == "wall" or s.role in _FACE_ROLES)]
    if not faces:
        return []
    planes: dict = {}
    for s in faces:
        frame = wall_frame(s, center, thick_m)
        pos, _n = _face(s, 0.0, 0.0, frame)
        key = _side(frame)
        planes.setdefault(key, []).append(pos[0] if key[0] else pos[1])
    planes = {k: sorted(v)[len(v) // 2] for k, v in planes.items()}
    if not all(k in planes for k in ((0, 1), (0, -1), (1, 0), (-1, 0))):
        return []
    ground_floor = [s for s in faces if int(s.story) == 0] or faces
    ground = min(_base_z(s) for s in ground_floor)
    top = max(_base_z(s) + s.size()[2] for s in faces)
    clear = [(b["pos"][2] - b["size2"][1] / 2.0 - QUOIN_BAND_CLEAR, b["pos"][2] + b["size2"][1] / 2.0 + QUOIN_BAND_CLEAR)
             for b in bands]
    boxes = _openings.keep_out_boxes(manifest)
    n_y, s_y, e_x, w_x = planes[(0, 1)], planes[(0, -1)], planes[(1, 0)], planes[(-1, 0)]
    orders = []
    z, k = ground, 0
    while z + QUOIN_H <= top + 1e-6:
        zc = z + QUOIN_H / 2.0
        if not any(lo < zc + QUOIN_H / 2.0 and zc - QUOIN_H / 2.0 < hi for lo, hi in clear):
            for ex, ey in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                long_ns = (k + (ex > 0) + (ey > 0)) % 2 == 0
                a = QUOIN_LONG if long_ns else QUOIN_SHORT
                b = QUOIN_SHORT if long_ns else QUOIN_LONG
                yp = n_y if ey > 0 else s_y
                xp = e_x if ex > 0 else w_x
                # N or S face: from the corner inward by a, on past the side face by the band's projection
                x0, x1 = sorted((xp - ex * a, xp + ex * _BAND_PROUD))
                # E or W face: from the N or S face inward by b, to that block's back
                y0, y1 = sorted((yp - ey * b, yp - ey * _BAND_INTO))
                pair = []
                for nrm, pos, length in (((0.0, float(ey), 0.0), [(x0 + x1) / 2.0, yp, zc], x1 - x0),
                                         ((float(ex), 0.0, 0.0), [xp, (y0 + y1) / 2.0, zc], y1 - y0)):
                    rng = rng_for(seed, "quoin", f"{ex}{ey}{k}{nrm[0]}")
                    pair.append({
                        "anchor_kind": "quoin", "cover": "string_course", "collision": "none",
                        "trim_piece": "base_course", "uv_region": uv, "slot_id": f"quoin_{ex}{ey}_{k}",
                        "pos": [round(v, 4) for v in pos], "normal": list(nrm),
                        "size": round(length, 4), "size2": [round(length, 4), QUOIN_H],
                        "seed_offset": int(rng.integers(0, 1_000_000)),
                    })
                if boxes and any(_openings.hits(o, boxes) for o in pair):
                    continue
                orders.extend(pair)
        z += QUOIN_H + QUOIN_JOINT
        k += 1
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
    scuppered = scupper_sides(manifest)
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
        headed = key in scuppered
        if headed:
            top_z = scuppered[key]
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
                    o = {"anchor_kind": "downspout", "cover": "downspout",
                         "collision": "none", "trim_piece": "flashing",
                         "uv_region": uv, "slot_id": s.slot_id,
                         "pos": pos, "normal": n,
                         "size": round(top_z - base, 3),
                         "seed_offset": int(rng.integers(0, 1_000_000))}
                    if headed:
                        o["head"] = True
                    return o
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


#: A PARAPET'S COPING (0.33.0, the factory's roadmap 324). The walker,
#: 2026-10-28: "less about realistic textures and more about the 3d shape
#: themselves". A parapet's top was capped by the roofline anchors' 2 m
#: `edge_strip`s, set 2.5 m apart with jitter and centred on the wall's OUTER
#: face -- 64 of them on `bank_branch_a02`, a broken 6 x 10 cm stick half off
#: the wall, a hairline at 30 m. A coping is one piece the length of its run,
#: over the whole wall, overhanging both faces so it throws a shadow line on
#: the facade and on the roof: built from the parapet's own slots, as a
#: gutter is from the eave's.
#:
#: The overhang each face, metres -- the window sill's (Zoo 1.145.0
#: `WINDOW_SILL_PROUD`), so the building's two ledges agree. Its height is
#: Zoo's (`core.dressing.COPING_H`): Patina plans the footprint, Zoo the solid.
COPING_OVER = 0.05
#: An `edge_strip` this near a coping's top plane, under its footprint, is the
#: roofline cap the coping replaces (:func:`drop_capped_edge_strips`). Its
#: anchor stands at the top of the wall it caps: measured 0 m off on
#: `bank_branch_a02`. The tolerance is the strip's own half-height and more.
COPING_CAP_TOL = 0.15
#: Each parapet side's outward normal and the `rot_y` Deli Counter gives it
#: (`deli_counter.py` `_record_parapet_slot`): `fit.dims` is (run, thickness,
#: height) in the slot's own frame on every side.
_PARAPET_OUT = {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}
_PARAPET_ROT = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}


def _parapet_side(slot) -> str:
    """The side a parapet tile stands on, from its id, checked against its
    `rot_y`. A tile whose two disagree is a shape this was not written
    against, and raises rather than capping the wrong face."""
    side = str(slot.slot_id)[len("parapet_"):][:1]
    if side not in _PARAPET_OUT:
        raise ValueError("parapet slot %r names no side" % slot.slot_id)
    turn = (float(slot.rot_y) - _PARAPET_ROT[side] + 180.0) % 360.0 - 180.0
    if abs(turn) > 0.5:
        raise ValueError("parapet slot %r: rot_y %s is not side %s's %s"
                         % (slot.slot_id, slot.rot_y, side, _PARAPET_ROT[side]))
    return side


def _parapet_runs(tiles: list) -> list[dict]:
    """One side's tiles joined into runs: tiles that meet end to end, on one
    line, one thickness and one top, are one run. A gap or a step starts the
    next."""
    items = []
    for s in tiles:
        side = _parapet_side(s)
        run, thick, h = s.size()
        ax = 0 if side in ("N", "S") else 1
        c = float(s.translation[ax])
        items.append({"side": side, "ax": ax,
                      "a0": c - run / 2.0, "a1": c + run / 2.0,
                      "fixed": float(s.translation[1 - ax]),
                      "thick": thick, "top": s.base_z() + h,
                      "ids": [s.slot_id]})
    items.sort(key=lambda it: (round(it["fixed"], 3), it["a0"]))
    runs = []
    for it in items:
        cur = runs[-1] if runs else None
        if (cur is not None and abs(it["a0"] - cur["a1"]) <= 0.002
                and abs(it["fixed"] - cur["fixed"]) <= 0.001
                and abs(it["thick"] - cur["thick"]) <= 0.001
                and abs(it["top"] - cur["top"]) <= 0.001):
            cur["a1"] = it["a1"]
            cur["ids"].append(it["ids"][0])
        else:
            runs.append(dict(it, ids=list(it["ids"])))
    return runs


def coping_orders(manifest: SlotManifest, regions: list, *, seed: int,
                  over: float = COPING_OVER) -> list[dict]:
    """One ``coping`` per parapet run (Deli Counter >= 0.177.0's parapet slots).

    THE CORNERS. Deli Counter gives a parapet's corners to its N and S runs
    (`_parapets`, "THE CORNERS BELONG TO N/S"): E and W stand between their
    inner faces. The copings follow: an N or S coping runs ``over`` past the
    corner, so the outer corner is capped round both faces, and an E or W
    coping stops ``over`` short of the N and S inner faces, where their
    roof-side overhang already is. The two abut; nothing is capped twice.

    NOT PAST AN EMPTY'S PARTY WALL. On an Empty -- a shell any of whose slots
    carries `glazing: "facade"` -- a face with no window, door or breach is a
    party wall (:func:`gutter_orders`), and the house beside it stands on the
    other side of that face. The party coping does not overhang it, and the
    front and back copings do not run past it: two houses of one height meet
    coping to coping at the lot line. A free-standing building overhangs
    every face.
    """
    parapets = [s for s in manifest.slots if _is_parapet(s) and s.dims]
    if not parapets:
        return []
    uv = _uv(regions, "roof_edge")
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    empty = any(s.glazing == "facade" for s in manifest.slots)
    faced = {_side(wall_frame(s, center, thick_m)) for s in manifest.slots
             if s.role in _FACE_ROLES and str(s.slot_id).startswith("ext_")}

    def exposed(side):
        return not empty or _PARAPET_OUT[side] in faced

    by_story: dict = {}
    for s in parapets:
        by_story.setdefault(s.story, {}).setdefault(_parapet_side(s), []).append(s)
    orders = []
    for story in sorted(by_story, key=lambda k: (k is None, k or 0)):
        runs = {side: _parapet_runs(tiles) for side, tiles in by_story[story].items()}
        ns = runs.get("N", []) + runs.get("S", [])
        lo_x = min((r["a0"] for r in ns), default=None)
        hi_x = max((r["a1"] for r in ns), default=None)
        n_inner = [r["fixed"] - r["thick"] / 2.0 for r in runs.get("N", [])]
        s_inner = [r["fixed"] + r["thick"] / 2.0 for r in runs.get("S", [])]
        for side in ("N", "E", "S", "W"):
            for r in runs.get(side, []):
                e0, e1 = r["a0"], r["a1"]
                if side in ("N", "S"):
                    if exposed("W") and lo_x is not None and abs(e0 - lo_x) <= 0.001:
                        e0 -= over
                    if exposed("E") and hi_x is not None and abs(e1 - hi_x) <= 0.001:
                        e1 += over
                else:
                    if any(abs(e0 - y) <= 0.001 for y in s_inner):
                        e0 += over
                    if any(abs(e1 - y) <= 0.001 for y in n_inner):
                        e1 -= over
                if e1 - e0 <= 0.01:
                    continue
                out_over = over if exposed(side) else 0.0
                width = r["thick"] + over + out_over
                outward = _PARAPET_OUT[side][1 - r["ax"]]
                pos = [0.0, 0.0, round(r["top"], 3)]
                pos[r["ax"]] = round((e0 + e1) / 2.0, 4)
                pos[1 - r["ax"]] = round(r["fixed"] + (out_over - over) / 2.0 * outward, 4)
                tangent = [1.0, 0.0, 0.0] if r["ax"] == 0 else [0.0, 1.0, 0.0]
                length = round(e1 - e0, 4)
                rng = rng_for(seed, "coping", r["ids"][0])
                orders.append({
                    "anchor_kind": "parapet_coping",
                    "cover": "coping",
                    "collision": "none",
                    "trim_piece": "roof_edge",
                    "uv_region": uv,
                    "slot_id": r["ids"][0],
                    "slot_ids": list(r["ids"]),
                    "pos": pos, "normal": [0.0, 0.0, 1.0], "tangent": tangent,
                    "size": length,
                    "size2": [length, round(width, 4)],
                    "seed_offset": int(rng.integers(0, 1_000_000)),
                })
    return orders


def drop_capped_edge_strips(orders: list[dict]) -> tuple[list[dict], int]:
    """``(kept, dropped)``: the roofline ``edge_strip``s a ``coping`` replaces.

    The roofline anchors come from the shell's geometry (`anchors`), know
    nothing of slots, and stand at the top of every wall plane -- which on a
    parapet is the coping's line. A strip under a coping's footprint and
    within :data:`COPING_CAP_TOL` of its top plane is dropped; one anywhere
    else (a building with no parapet, a lower wing) is kept.
    """
    boxes = []
    for o in orders:
        if o.get("cover") != "coping":
            continue
        length, width = (float(v) for v in o["size2"][:2])
        along_x = abs(float((o.get("tangent") or (1.0, 0.0, 0.0))[0])) > 0.5
        hx, hy = (length, width) if along_x else (width, length)
        px, py, pz = (float(v) for v in o["pos"])
        boxes.append((px - hx / 2.0 - 0.01, px + hx / 2.0 + 0.01,
                      py - hy / 2.0 - 0.01, py + hy / 2.0 + 0.01, pz))
    if not boxes:
        return list(orders), 0
    kept, dropped = [], 0
    for o in orders:
        if o.get("cover") == "edge_strip":
            x, y, z = (float(v) for v in o["pos"])
            if any(x0 <= x <= x1 and y0 <= y <= y1 and abs(z - top) <= COPING_CAP_TOL
                   for x0, x1, y0, y1, top in boxes):
                dropped += 1
                continue
        kept.append(o)
    return kept, dropped
