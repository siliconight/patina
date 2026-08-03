"""The keep-out rule: dressing never intersects a traversable opening.

THE RULE. A door, window, garage or breach is a hole a player walks or shoots
through. Nothing decorative may sit in one. The ``frame`` cover is the SOLE
exemption, because surrounding an opening is the entire point of a frame.

WHY THIS EXISTS AS ONE FILTER RATHER THAN A CHECK PER FAMILY. The families that
already respected openings did so by accident of their input: panel fields and
gutters are built from DC SLOTS, and a doorway is its own slot rather than a
wall with a hole, so they never had to think about it. The families built from
GEOMETRY -- roofline, wall_base, ground_edge, exterior_light -- come from
``_wall_segments``, which spans ``a_min..a_max`` and has never heard of an
opening. Measured on ``category5_baie_dore_001`` (19 openings: 9 door, 6 window,
3 breach, 1 garage), 25 non-frame orders had their ORIGIN inside a hole: 14
pilasters across windows, and 5 base courses plus 5 curbs running through door
thresholds -- the literal "expect to walk through" case.

So the filter runs ONCE over the assembled order list. A family added later is
covered without anyone remembering to add a check, which is the failure mode
this repo keeps rediscovering.

WHAT IS TESTED, AND WHAT IS DELIBERATELY NOT. An order declares a ``pos`` and a
span (``size``, or ``size2`` when it has two). That declared span is what gets
tested, swept along the direction the order runs. The CROSS-AXIS thickness --
how far a strip stands proud, how tall a curb is -- lives in Zoo's ``_COVER``
table, not in the manifest, and Patina does not guess at another repo's
constants. So the swept box is a LOWER BOUND on the real geometry and the
margin is what covers the difference. Stated here because a reader is entitled
to know the test is conservative by construction rather than by oversight.

CONDUIT IS SHORTENED, NOT DROPPED. Every other cover is discarded when it
collides: a curb that stops at a threshold and resumes past it is what a real
curb does. A conduit is different -- it runs from the ground UP to a fixture
that sits above a door, so it crosses that door's head by definition. Dropping
it would delete the run entirely; the right answer is to start it above the
opening. It is the one case where splitting beats dropping.
"""

from __future__ import annotations

import math

#: Opening kinds that are traversable. All of DC's kinds are: you walk through
#: a door or garage, you shoot through a window, and a breach is a hole
#: something already came through.
TRAVERSABLE = ("door", "garage", "window", "breach")

#: Covers exempt from the rule. Exactly one, and it is listed rather than
#: inferred so that adding a second is a visible decision.
EXEMPT = ("frame",)

#: Cross-axis of each cover, MIRRORED from `zoo_keeper/core/dressing.py`
#: `_COVER`. An order declares its SPAN; how tall a curb is or how deep a base
#: course sits lives in Zoo's table and never reaches this manifest, so a box
#: built from the span alone is a lower bound. Measured on the shipped build:
#: 3 base courses reached up to 0.32 m into openings the declared-span test
#: called clean, because a base course is 0.35 across and the test assumed 0.
#:
#: A blanket margin was tried first and is the wrong lever: sized to cover the
#: widest cover it dropped 11 gutters and all 4 conduits, none of which were
#: ever near a hole. Per-cover is precise -- a gutter is judged at 0.14 and a
#: base course at 0.35.
#:
#: These numbers are another repo's constants, which is a thing that rots. The
#: real fix is Zoo publishing its cover dimensions as a contract, the way DC
#: publishes slots; until then the value and its source are named together so
#: drift is findable.
_ZOO_CROSS = {                        # zoo_keeper/core/dressing.py _COVER
    "edge_strip": 0.10, "base_course": 0.35, "curb": 0.12,
    "conduit_run": 0.05, "panel_field": 1.20, "gutter_run": 0.14,
    "pilaster": 0.24, "frame": 0.12,
}

#: Zoo does not use `size` as the span. It SCALES it:
#: ``span = max(0.2, _COVER[cover]["span"] * max(size, 0.1) / 0.6)``.
#: A curb declaring ``size: 0.4`` is built 1.33 m long; a base course
#: declaring 0.8 is built 2.67 m. Testing the declared 0.4 understated the
#: real footprint by 3.3x, which is why base courses kept reaching into
#: doorways after the cross-axis was accounted for.
#:
#: `gutter_run` is the exception -- it spans its wall module exactly -- and
#: `panel_field`, `pilaster` and `frame` carry `size2` and are not scaled.
#: Same mirror, same rot risk, same real fix as _ZOO_CROSS: this belongs in a
#: contract Zoo publishes, not in a constant Patina copies.
#: `conduit_run` is DELIBERATELY absent: its span scaling was removed when
#: `size` became the true ground-to-fixture run length. Mirroring the old 1.6
#: put it straight back and left 3 conduits intersecting -- a mirror of a
#: constant that has since changed is worse than no mirror, and this one went
#: stale within the same day it was written. Exactly the argument for a
#: published contract.
_ZOO_SPAN = {                         # zoo_keeper/core/dressing.py _COVER
    "edge_strip": 2.0, "base_course": 2.0, "curb": 2.0,
}

#: Clearance only, now that the cross-axis is accounted for properly: the gap a
#: player should see around a hole, not a stand-in for an unknown dimension.
MARGIN = 0.08

#: Nav agent radius, from Lot's walk-scene NavigationMesh (`agent_radius = 0.4`
#: in `site_walk.tscn`). The body that has to fit through the hole.
_AGENT_RADIUS = 0.40
#: Deepest any cover stands proud of its wall -- `gutter_run` in Zoo's _COVER.
_PROUDEST_COVER = 0.10


def lane_reach(wall_depth: float) -> float:
    """How far the keep-out extends along an opening's normal, each side.

    DERIVED, from the three things that have to fit rather than a number that
    looked about right: half the wall's own thickness (so nothing sits in the
    reveal), the deepest a cover stands proud of that wall, and one nav agent
    radius so a body can pass without clipping. On a 0.35 m wall that is
    0.175 + 0.10 + 0.40 = 0.675 m.

    THIS is the "walk or shoot through" rule. An opening is not a plane, it is
    a LANE: the volume swept by walking through a door or firing through a
    window. Testing the plane alone let a curb sit in a doorway threshold and a
    panel field sit in a window's firing line while the rule reported clean.
    """
    return round(float(wall_depth) / 2.0 + _PROUDEST_COVER + _AGENT_RADIUS, 3)


def keep_out_boxes(manifest, margin: float = MARGIN) -> list[dict]:
    """Axis-aligned world boxes for every traversable opening in a shell.

    Reads ``fit.openings`` (width / height / sill) off each slot and extrudes
    it along that slot's normal by :func:`lane_reach`, so the volume is the
    LANE a body walks or a shot travels through, not the plane of the hole.
    Spec Blender Z-up throughout -- the same space the orders are in, so
    nothing converts.

    NOT room interiors. Measured on `category5_baie_dore_001`, testing orders
    against `gameplay.json` room bounds flagged 1034 of 2098 -- including 603
    of 1315 panel fields -- because a room's bounds include the wall plane and
    every facade cover sits on it. A rule that flags half the dressing is
    measuring the wall, not an intrusion.
    """
    boxes: list[dict] = []
    for s in manifest.slots:
        if not s.dims or not s.openings:
            continue
        base = s.base_z()
        rad = math.radians(float(s.rot_y))
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        tx, ty = float(s.translation[0]), float(s.translation[1])
        depth = s.size()[1]
        for op in s.openings:
            if op.get("kind", "door") not in TRAVERSABLE:
                continue
            w = float(op.get("width", 0.0))
            h = float(op.get("height", 0.0))
            if w <= 0.0 or h <= 0.0:
                continue
            sill = float(op.get("sill", 0.0))
            hx = w / 2.0
            reach = lane_reach(depth)
            pts = [(tx + dx * cos_r - dy * sin_r, ty + dx * sin_r + dy * cos_r)
                   for dx in (-hx, hx) for dy in (-reach, reach)]
            boxes.append({
                "slot_id": s.slot_id,
                "kind": op.get("kind", "door"),
                "x0": min(p[0] for p in pts) - margin,
                "x1": max(p[0] for p in pts) + margin,
                "y0": min(p[1] for p in pts) - margin,
                "y1": max(p[1] for p in pts) + margin,
                "z0": base + sill - margin,
                "z1": base + sill + h + margin,
            })
    return boxes


def _run_axis(order) -> tuple:
    """Unit vector the order's span runs along.

    ``tangent`` when the order carries one (anchor-derived, since v0.19).
    Otherwise the horizontal perpendicular of the wall normal, which is exact
    for the slot-derived facade kit: a gutter or pilaster runs across the face
    it stands proud of. ``conduit_run`` is the exception -- its span is
    vertical, because it climbs a wall rather than crossing it.
    """
    if order.get("cover") == "conduit_run":
        return (0.0, 0.0, 1.0)
    t = order.get("tangent")
    if t and len(t) >= 3 and (abs(t[0]) + abs(t[1]) + abs(t[2])) > 1e-9:
        n = math.sqrt(sum(float(v) ** 2 for v in t[:3])) or 1.0
        return (float(t[0]) / n, float(t[1]) / n, float(t[2]) / n)
    n = order.get("normal") or (0.0, 1.0, 0.0)
    px, py = -float(n[1]), float(n[0])
    ln = math.hypot(px, py)
    return (px / ln, py / ln, 0.0) if ln > 1e-9 else (1.0, 0.0, 0.0)


def order_box(order) -> dict:
    """The order's declared footprint as an axis-aligned box.

    Span swept along :func:`_run_axis`, plus the vertical half-height when the
    order declares one in ``size2``. Exact for axis-aligned walls (every shell
    DC emits), conservative otherwise.
    """
    pos = [float(v) for v in order.get("pos", (0.0, 0.0, 0.0))]
    cover = order.get("cover", "")
    size2 = order.get("size2")
    declared = float(order.get("size", 0.0) or 0.0)
    if size2 and len(size2) >= 2:
        span = float(size2[0])
    elif cover in _ZOO_SPAN:
        span = max(0.2, _ZOO_SPAN[cover] * max(declared, 0.1) / 0.6)
    else:
        span = declared
    ux, uy, uz = _run_axis(order)
    hx, hy, hz = ux * span / 2.0, uy * span / 2.0, uz * span / 2.0
    # The axis the span does NOT run along. A strip that runs horizontally is
    # `cross` TALL; a conduit runs vertically, so its span already covers the
    # height and `cross` is only its width.
    if size2 and len(size2) >= 2:
        half_v = float(size2[1]) / 2.0
    elif abs(uz) > 0.5:
        half_v = 0.0
    else:
        half_v = _ZOO_CROSS.get(cover, 0.0) / 2.0
    return {
        "x0": pos[0] - abs(hx), "x1": pos[0] + abs(hx),
        "y0": pos[1] - abs(hy), "y1": pos[1] + abs(hy),
        "z0": pos[2] - abs(hz) - half_v, "z1": pos[2] + abs(hz) + half_v,
    }


def _overlaps(a: dict, b: dict) -> bool:
    """True only on a POSITIVE overlap; touching the boundary is clearance.

    Inclusive comparison made the rule unsatisfiable for the one cover that is
    shortened rather than dropped: a conduit told to start at an opening's top
    edge starts exactly there, and `z0 <= z1` then reports it as still inside.
    The gate could never reach zero. Touching the box is fine because the box
    is already grown by MARGIN -- the clearance is in the box, not in the
    comparison.
    """
    return (a["x0"] < b["x1"] and a["x1"] > b["x0"]
            and a["y0"] < b["y1"] and a["y1"] > b["y0"]
            and a["z0"] < b["z1"] and a["z1"] > b["z0"])


def hits(order, boxes) -> list[dict]:
    """Opening boxes this order intersects. Empty for an exempt cover."""
    if order.get("cover") in EXEMPT:
        return []
    ob = order_box(order)
    return [b for b in boxes if _overlaps(ob, b)]


def _shorten_conduit(order, blocking) -> dict | None:
    """Start the run above the highest opening it crosses, or drop it.

    A conduit that would begin inside a doorway starts at that doorway's head
    instead. If nothing is left of the run -- the fixture is itself inside the
    opening -- there is no conduit to build and None is correct.
    """
    top = max(b["z1"] for b in blocking)
    fixture_z = float(order["pos"][2]) + float(order.get("size", 0.0)) / 2.0
    run = fixture_z - top
    if run <= 0.05:
        return None
    out = dict(order)
    size = round(run, 3)
    centre = round(top + size / 2.0, 3)
    # Rounding to millimetres can pull the base back INSIDE the hole: the first
    # run of this produced pos 3.087 from 3.0875, putting the conduit's foot
    # 0.0005 m under a door head and leaving the gate at one violation nobody
    # would ever see. Clamp after rounding rather than trusting it.
    if centre - size / 2.0 < top:
        centre = round(centre + 0.001, 3)
    out["size"] = size
    out["pos"] = [order["pos"][0], order["pos"][1], centre]
    out["clipped_by"] = sorted({b["slot_id"] for b in blocking})
    return out


def apply(orders, boxes):
    """``(kept_orders, report)`` with the rule enforced.

    The report names what happened per cover so a build can print it and a gate
    can assert on it. Silence about dropped dressing is how 25 orders sat
    inside holes without anyone noticing.
    """
    kept, dropped, shortened = [], {}, {}
    for o in orders:
        blocking = hits(o, boxes)
        if not blocking:
            kept.append(o)
            continue
        cover = o.get("cover", "?")
        if cover == "conduit_run":
            fixed = _shorten_conduit(o, blocking)
            if fixed is not None:
                shortened[cover] = shortened.get(cover, 0) + 1
                kept.append(fixed)
                continue
        dropped[cover] = dropped.get(cover, 0) + 1
    return kept, {"openings": len(boxes),
                  "dropped": dict(sorted(dropped.items())),
                  "shortened": dict(sorted(shortened.items()))}


def violations(orders, boxes) -> list[dict]:
    """Orders still intersecting an opening. THE GATE: this must be empty.

    Every defect found in this layer today -- fixtures inside floor slabs,
    curbs under the basement, strips pointing at world +X -- shipped because
    nothing asserted the result. A filter without a gate is a filter somebody
    removes later.
    """
    out = []
    for o in orders:
        blocking = hits(o, boxes)
        if blocking:
            out.append({"cover": o.get("cover"), "pos": list(o.get("pos", ())),
                        "slot_ids": sorted({b["slot_id"] for b in blocking})})
    return out
