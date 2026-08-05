"""Keep-out volumes derived from the shell's own ``gameplay.json``.

THE RULE. Dressing never sits where the player will stand, shelter, or look.
An objective is a place a body plants itself for several seconds; a cover
marker is a place a body crouches and a silhouette gets read against whatever
is behind it; a landmark is the thing the room is supposed to be remembered
for; a spawn is where a body appears. None of those want decorative geometry
in them.

WHY THIS EXISTS NOW. Patina has always had this data and has never read it.
``cli.py`` loads the shell's ``gameplay.json`` and re-emits it beside the
styled output -- *"Patina is visual-only; markers/collision are the original's,
untouched"* -- so ``scene.gameplay`` is in memory during the same run that
decides where every cover order goes, and is passed straight through. Measured
on ``lot_demo_001`` seed 5017, one demo building carries 9 cover markers, 2
objectives, 2 spawns, 2 landmarks, 4 rooms with bounds and combat range, and
303 surface roles. The dressing pass read none of it.

This is the ``§23`` exclusion list from ``patina/docs/DRESSING_CHECKLIST.md``,
minus the parts that need metadata the schema does not carry yet:

    do not place clutter ... in objective interaction zones ... behind common
    enemy silhouettes ... within a landmark's visual breathing space

WHAT IS DELIBERATELY NOT USED: ROOM BOUNDS. ``openings.keep_out_boxes`` already
recorded the measurement -- on ``category5_baie_dore_001``, testing orders
against ``gameplay.json`` room bounds flagged 1034 of 2098, including 603 of
1315 panel fields, because a room's bounds include the wall plane and every
facade cover sits on it. A rule that flags half the dressing is measuring the
wall, not an intrusion. So every volume here is a POINT RADIUS around a marker,
never a room extent. The same trap, declined twice.

MEASURED ON A REAL BUILDING, AND IT DROPS NOTHING TODAY. Run over
``category5_baie_dore_001`` -- art-passed, post-fix families, 253 orders -- this
filter removed **0**, and all 22 boxes went unhit. That zero is STRUCTURAL, not
a bug, and the difference was checked rather than assumed:

  * the five surviving cover families (``base_course``, ``curb``,
    ``edge_strip``, ``gutter_run``, ``conduit_run``) are all EXTERIOR facade
    and roof elements. Every marker is INTERIOR. Once ``panel_field`` and
    ``pilaster`` were dropped from the adapter, no dressing family reaches
    inside a room at all.
  * zero orders overlap a box in PLAN even with z ignored entirely, so this is
    not a height-band artefact.
  * nearest approach from any order to any keep-out is 1.68 m, against a
    ``cover_*`` reach of 1.50 m.

So this is a TRIPWIRE, and it starts doing work the day interior dressing
arrives. Stated here because a filter reporting zero is indistinguishable from
a filter that was never wired, and this repo has shipped that mistake before.

THE RADII ARE THEREFORE UNVALIDATED. Nothing in the shipped data exercises
them. A sensitivity sweep puts the first drop at 1.5x the per-kind allowance
(8 orders) and 18 at 2.0x -- so 1.68 m of clearance sits just under where the
rule would begin to bite, and this measurement cannot tell "correct" from
"slightly too small". Revisit when interior families exist.

WHAT THIS RULE DOES NOT DO, AND CANNOT. A radius protects the volume AT a
marker. Checklist sect.11 and sect.20 are about what sits BEHIND a body from the
shooter's side -- "busy edge patterns behind enemies create visual camouflage".
That is a SIGHTLINE, not a sphere: it needs the line from a likely attacker
position through the cover to the surface beyond, and the surface beyond is
exactly where ``base_course`` and ``gutter_run`` live. So this module delivers
sect.23's exclusion clauses (objective interaction zones, landmark breathing
space, spawn volumes) and does NOT deliver the silhouette-background clause.
That one needs `spawn -> objective` route geometry the schema does not carry
yet, and calling it done because a radius shipped would be the "designed
correctly, never wired" pattern with extra steps.

SPACE. ``gameplay.json`` markers, objectives and room bounds are in the same
spec Blender Z-up plan space as the slots -- verified on the shipped demo by
testing every marker against its own room's XY bounds: 14 of 15 inside, the one
outside being a ``crew_spawn`` that sits in the street. So nothing converts,
exactly as in :mod:`patina.openings`.
"""

from __future__ import annotations

#: Nav agent radius, from Lot's walk-scene NavigationMesh (``agent_radius =
#: 0.4`` in ``site_walk.tscn``) -- the body that has to fit. Mirrored from
#: :mod:`patina.openings`, which derives its lane reach from the same number.
_AGENT_RADIUS = 0.40

#: Deepest any cover stands proud of its wall -- ``gutter_run`` in Zoo's
#: ``_COVER``. Also mirrored from :mod:`patina.openings`.
_PROUDEST_COVER = 0.10

#: DERIVED: a body standing at a marker, plus the deepest thing Patina can
#: hang on the surface next to it. Everything below adds its own allowance on
#: top of this floor.
STANCE = _AGENT_RADIUS + _PROUDEST_COVER          # 0.50 m

#: Head height for a standing body. The z extent matters as much as the radius:
#: without it a cover marker on the ground floor would exclude a roofline strip
#: nine metres above it, which protects nothing and deletes dressing.
_HEAD = 2.20

#: Per-kind allowance ON TOP of STANCE, and the z band each volume occupies
#: relative to the marker. The radii are a DESIGN choice, not a derivation --
#: Patina cannot see the footprint of Lot's cover pieces or the reach of an
#: interaction animation, and this layer does not guess at another repo's
#: constants. They are listed here so that changing one is a visible decision,
#: and the audit below reports what each cost.
#:
#:   kind          extra  z_lo   z_hi   why
#:   objective      1.50  -0.50  _HEAD  a body plants here for seconds
#:   cover_*        1.00  -0.50  _HEAD  a body crouches, a silhouette is read
#:   landmark       2.00  -1.00   3.50  sect.5 "do not crowd the landmark"
#:   *_spawn        1.00  -0.50  _HEAD  a body appears here
KINDS: dict[str, tuple[float, float, float]] = {
    "objective":       (1.50, -0.50, _HEAD),
    "cover_low":       (1.00, -0.50, _HEAD),
    "cover_high":      (1.00, -0.50, _HEAD),
    "landmark":        (2.00, -1.00, 3.50),
    "crew_spawn":      (1.00, -0.50, _HEAD),
    "responder_spawn": (1.00, -0.50, _HEAD),
}

#: Marker types present in shipped gameplay.json that are deliberately NOT
#: protected, listed rather than omitted so the absence is a decision:
#:   camera_socket  a camera mount IS dressing; it wants company
#:   ladder, hatch  traversal, already covered by openings.keep_out_boxes
#:   extraction     a zone, not a point -- see the room-bounds note above
#:   loot           small, and often sits ON a dressed surface by design
IGNORED = ("camera_socket", "ladder", "hatch", "extraction", "loot")


def _box(kind: str, x: float, y: float, z: float, label: str) -> dict:
    extra, z_lo, z_hi = KINDS[kind]
    reach = STANCE + extra
    return {
        # `slot_id` so the report and `openings.violations` format unchanged --
        # this is the identity of the thing being protected, whatever it is.
        "slot_id": label,
        "kind": kind,
        "x0": x - reach, "x1": x + reach,
        "y0": y - reach, "y1": y + reach,
        "z0": z + z_lo, "z1": z + z_hi,
    }


def keep_out_boxes(gameplay) -> list[dict]:
    """Axis-aligned world boxes around every place a body will be.

    ``gameplay`` is the parsed ``gameplay.json``. Returns the same box shape
    :func:`patina.openings.keep_out_boxes` returns, so the two lists
    concatenate and :func:`patina.openings.apply` enforces both at once, over
    the assembled order list, exactly once -- the property that module was
    built to have.

    Returns ``[]`` for a shell with no gameplay data. The caller must say so
    out loud rather than letting "no gate ran" read as "gate passed".
    """
    if not gameplay:
        return []
    boxes: list[dict] = []

    for m in gameplay.get("markers") or ():
        kind = str(m.get("type") or "")
        if kind not in KINDS:
            continue
        label = f"{kind}@{m.get('room') or 'site'}:{m.get('id') or m.get('name') or len(boxes)}"
        boxes.append(_box(kind, float(m["x"]), float(m["y"]), float(m["z"]),
                          label))

    # Objectives are their own list, not markers -- and on the demo building
    # one of them (`OBJECTIVE_GRAB_DRAWERS`) sits at the same position as a
    # cover_low marker. Both boxes are emitted; overlap is free and the report
    # is more honest for naming each reason separately.
    for o in gameplay.get("objectives") or ():
        label = f"objective:{o.get('id') or o.get('name') or len(boxes)}"
        boxes.append(_box("objective", float(o["x"]), float(o["y"]),
                          float(o["z"]), label))

    return boxes


def counts(boxes) -> dict:
    """``{kind: n}`` for the build log."""
    out: dict[str, int] = {}
    for b in boxes:
        out[b["kind"]] = out.get(b["kind"], 0) + 1
    return dict(sorted(out.items()))
