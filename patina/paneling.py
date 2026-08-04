"""Panel fields (v0.17): the highest-ROI facade cover.

One flat greybox wall becomes a grid of thin proud panels — concrete panel,
brick section, siding — purely through non-collision cover geometry. Same
collision, dramatically better lighting: the gaps between panels are where a
sixth-gen facade gets its shadow lines.

This is the wall-scale extension of the v0.11 dressing contract, and it rides
the modular alignment (v0.9) instead of geometry analysis: DC's slots.json
already partitions every facade into wall / doorway / window / breach slots,
so panel grids are laid **per wall slot** and openings never need hole math —
a doorway simply isn't a wall slot. Slot transforms are spec/Blender Z-up
with ``rot_y`` in degrees about up (slots.json states this), which is exactly
the space DC-aligned dressing manifests already use, so panel orders join the
anchor orders with no conversion.

Patina still ships zero geometry. Each panel is one build order (cover
``panel_field``): position, outward normal, ``size2`` = [width, height] of
the panel face. Zoo's ``dress_cover`` builds the thin box. ``size`` stays the
scalar width so a pre-panel Zoo degrades to a strip instead of crashing.

Deterministic: the grid is arithmetic (no randomness); ``seed_offset`` per
panel comes from ``(seed, "panel", slot_id, col, row)`` streams.
"""

from __future__ import annotations

from .determinism import rng_for
from .slots import (SlotManifest, footprint_center, modal_thickness,
                    wall_frame)

# Panels smaller than this on either axis read as noise, not paneling.
_MIN_PANEL = 0.25


def wall_slots(manifest: SlotManifest) -> list:
    """Exterior wall slots eligible for paneling.

    A slot qualifies with role ``wall``, known dims, and an exterior signal.

    ``facing`` IS NOT AN EXTERIOR SIGNAL, and treating it as one is why the
    inside of every building was being panelled. DC sets ``facing`` on interior
    partitions too -- it says which way the surface points, not whether it is
    on the shell. Measured on ``category5_baie_dore_001``: 299 wall slots, all
    299 with ``facing`` set, 74 of them ``int_``-prefixed. So the test
    ``s.facing or s.slot_id.startswith("ext_")`` admitted every slot in the
    building and excluded nothing, and a quarter of the dressed walls were
    partitions -- which is where the pilasters standing in walkable floor space
    came from. Non-collision geometry you walk straight through, on a wall
    nobody outside can see.

    The prefix is the signal. ``int_`` is out; the ``facing``-or-``ext_`` test
    stays for what remains, so a manifest that names slots some third way keeps
    working.

    THE LEGACY FALLBACK IS NARROWER THAN IT LOOKS. "Nothing qualified, so
    panel everything" exists for old manifests that carry no prefixes at all.
    Left broad it also fires on a MODERN manifest whose walls are all
    ``int_`` -- a basement-only shell -- and panels every partition in it,
    which is the defect wearing the fallback as a disguise. So the fallback is
    conditioned on the manifest using no prefixes, not on the filter coming up
    empty: a prefixed manifest that qualifies nothing gets nothing, and that
    is the correct answer rather than a degenerate one.
    """
    walls = [s for s in manifest.slots if s.role == "wall" and s.dims]
    ext = [s for s in walls
           if not s.slot_id.startswith("int_")
           and (s.facing or s.slot_id.startswith("ext_"))]
    if ext:
        return ext
    prefixed = any(s.slot_id.startswith(("int_", "ext_")) for s in walls)
    return [] if prefixed else walls


def panel_orders(manifest: SlotManifest, regions: list, *, seed: int,
                 panel: float = 1.2, gap: float = 0.01,
                 max_orders: int = 4000) -> list[dict]:
    """Panel-field build orders for every exterior wall slot.

    ``regions`` is the trim-atlas region list (the ``panel_seam`` piece skins
    panel faces so they share the building's family). ``panel`` is the target
    panel edge in metres; each slot fits a uniform grid to its own dims, so
    cells are exact and seams align across identical modules.

    CELL SIZE IS NOT THE SUBTLETY LEVER, and halving it was tried and undone.
    A 1.2 m cell on a 3.7 m storey looks coarse, so 0.6 seems like the fix --
    but halving a grid cell does not halve the count, it roughly TRIPLES it:
    1374 orders become 3732 on the shipped building. Three times as many
    elements is louder, not quieter. What a panel field shouts with is its
    PROUD DEPTH (the shadow line in the gap) and its COVERAGE (every exterior
    wall slot, fully gridded, on every building). Those are the levers.

    THE JOINT IS THE OTHER HALF OF THE SEAM. ``gap`` was 0.03, leaving a 3 cm
    channel of bare wall between every pair of panels; paired with Zoo's 0.03 m
    proud depth that is a 3x3 cm groove around all 1032 cells. Tightened to
    0.01 here and the proud depth to 0.012 in Zoo, so the joint reads as a line
    rather than a channel. This does NOT remove the grid -- a panel field is
    articulation and articulation has seams -- it makes the seam quiet.

    ``max_orders`` was raised to 4000 anyway and the clamp made loud, because a
    budget that silently truncates leaves a facade half-panelled and reports
    success.
    """
    region = next((r for r in regions if r.piece == "panel_seam"), None)
    uv = [round(region.u0, 4), round(region.v0, 4),
          round(region.u1, 4), round(region.v1, 4)] if region else None

    orders: list[dict] = []
    center = footprint_center(manifest)
    thick_m = modal_thickness(manifest)
    for s in wall_slots(manifest):
        _w, _d, h = s.size()
        # RUN and THICKNESS, not dims[0] and dims[1]. Half the wall slots in a
        # building carry dims already rotated into world axes, so reading them
        # positionally gridded every east and west facade across its 35 cm
        # thickness instead of its 2 m run. slots.wall_frame is the one place
        # that knows -- it also returns which face is the street side, so the
        # axis and the side are settled together.
        run, thick, along, out = wall_frame(s, center, thick_m)
        cols = max(1, round(run / panel))
        rows = max(1, round(h / panel))
        cell_w, cell_h = run / cols, h / rows
        face_w = round(cell_w - gap, 3)
        face_h = round(cell_h - gap, 3)
        if face_w < _MIN_PANEL or face_h < _MIN_PANEL:
            continue
        tx, ty, tz = (float(v) for v in s.translation)
        z0 = 0.0 if s.pivot == "base" else -h / 2.0
        ly = thick / 2.0
        nx = round(out[0], 3) + 0.0
        ny = round(out[1], 3) + 0.0
        for i in range(cols):
            lx = -run / 2.0 + cell_w * (i + 0.5)
            px = tx + lx * along[0] + ly * out[0]
            py = ty + lx * along[1] + ly * out[1]
            for j in range(rows):
                pz = tz + z0 + cell_h * (j + 0.5)
                if len(orders) >= max_orders:
                    return orders
                rng = rng_for(seed, "panel", s.slot_id, str(i), str(j))
                orders.append({
                    "anchor_kind": "wall_panel",
                    "cover": "panel_field",
                    "collision": "none",
                    "trim_piece": "panel_seam",
                    "uv_region": uv,
                    "slot_id": s.slot_id,
                    "pos": [round(px, 3), round(py, 3), round(pz, 3)],
                    "normal": [nx, ny, 0.0],
                    "size": face_w,
                    "size2": [face_w, face_h],
                    "seed_offset": int(rng.integers(0, 1_000_000)),
                })
    return orders
