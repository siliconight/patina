"""Tests for panel-field orders (v0.17)."""

import math

import pytest

from patina import paneling, trim
from patina.slots import Slot, SlotManifest


def _slot(slot_id="ext_0_N_seg0", facing="N", rot_y=0.0, dims=(2.0, 0.3, 4.2),
          translation=(-15.0, 11.0, 2.1), pivot="center", role="wall"):
    return Slot(slot_id=slot_id, role=role, current_ref="wall_greybox_01",
                facing=facing, translation=translation, rot_y=rot_y,
                dims=dims, pivot=pivot)


def _manifest(slots):
    return SlotManifest(version="1.2.0", building_id="t", theme="greybox",
                        module_library="art/zoo", module_size=2.0,
                        space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    _, regions = trim.build_sheet(size=64, seed=1999)
    return regions


def test_grid_covers_wall_and_skips_openings():
    m = _manifest([_slot(),
                   _slot(slot_id="ext_0_N_open1", role="doorway")])
    orders = paneling.panel_orders(m, _regions(), seed=1999)
    # 2.0m wide / 1.2 target -> 2 cols; 4.2m tall -> round(3.5) = 4 rows
    assert len(orders) == 8
    assert all(o["cover"] == "panel_field" for o in orders)
    assert all(o["slot_id"] == "ext_0_N_seg0" for o in orders)  # no doorway
    assert all(o["collision"] == "none" for o in orders)


def test_panel_face_offset_and_normal():
    m = _manifest([_slot()])
    o = paneling.panel_orders(m, _regions(), seed=1999)[0]
    # facing N, rot_y 0: normal +Y, face plane at ty + d/2
    assert o["normal"] == [0.0, 1.0, 0.0]
    assert o["pos"][1] == pytest.approx(11.0 + 0.15, abs=1e-3)
    w, h = o["size2"]
    # gap was 0.03: a 3 cm channel of bare wall between every pair of panels,
    # which with Zoo's proud depth was a groove around all 1032 cells. The
    # joint is the seam a player reads as "tiles".
    assert w == pytest.approx(1.0 - 0.01, abs=1e-3)
    assert h == pytest.approx(1.05 - 0.01, abs=1e-3)
    assert o["size"] == pytest.approx(w)


def test_rotation_rotates_normal_and_positions():
    m = _manifest([_slot(rot_y=90.0)])
    o = paneling.panel_orders(m, _regions(), seed=1999)[0]
    assert o["normal"] == [-1.0, 0.0, 0.0]


def test_interior_walls_skipped_when_exterior_marked():
    m = _manifest([_slot(),
                   _slot(slot_id="int_0_seg0", facing=None)])
    orders = paneling.panel_orders(m, _regions(), seed=1999)
    assert {o["slot_id"] for o in orders} == {"ext_0_N_seg0"}


def test_an_interior_wall_that_carries_facing_is_still_interior():
    """The case the filter actually meets, and used to let through.

    DC sets ``facing`` on interior partitions too -- it says which way a
    surface points, not whether it is on the shell. On a shipped building all
    299 wall slots carried ``facing``, 74 of them ``int_``, so a test of
    "facing or ext_ prefix" admitted the whole building. The old version of
    the test above passes either way, because its interior slot has no
    ``facing`` -- it was checking a case that does not occur.
    """
    m = _manifest([_slot(), _slot(slot_id="int_-1_4_seg1", facing="N")])
    orders = paneling.panel_orders(m, _regions(), seed=1999)
    assert {o["slot_id"] for o in orders} == {"ext_0_N_seg0"}


def test_a_prefixed_manifest_with_no_exterior_walls_gets_nothing():
    """Not the legacy fallback. A basement-only shell is modern and empty."""
    m = _manifest([_slot(slot_id="int_-1_a", facing="N"),
                   _slot(slot_id="int_-1_b", facing="S")])
    assert paneling.panel_orders(m, _regions(), seed=1999) == []


def test_a_manifest_with_no_prefixes_at_all_still_panels_everything():
    """The legacy fallback, kept: an old manifest keeps its old output."""
    m = _manifest([_slot(slot_id="wall_a", facing=None),
                   _slot(slot_id="wall_b", facing=None)])
    orders = paneling.panel_orders(m, _regions(), seed=1999)
    assert {o["slot_id"] for o in orders} == {"wall_a", "wall_b"}


def test_deterministic():
    m = _manifest([_slot()])
    a = paneling.panel_orders(m, _regions(), seed=1999)
    b = paneling.panel_orders(m, _regions(), seed=1999)
    assert a == b


def test_manifest_appends_extra_orders():
    regions = _regions()
    m = _manifest([_slot()])
    panels = paneling.panel_orders(m, regions, seed=1999)
    dm = trim.dressing_manifest([], regions, seed=1999, source="t.glb",
                                sheet_file="t.trim.png",
                                space="spec/Blender Z-up raw coords",
                                building_id="t", extra_orders=panels)
    assert len(dm["orders"]) == 8
    assert dm["counts"]["panel_field"] == 8


def test_remainder_wall_grids_its_own_size_not_the_squared_one():
    """``scale`` on a ``size_mod == "end"`` slot is a copy of ``dims``.

    Composing them gave a 1.69 x 13.69 m wall out of a 1.3 x 3.7 m one: the
    panel grid ran 1 col x 11 rows up past the roof instead of 1 x 3.
    """
    m = _manifest([_slot(dims=(1.3, 0.35, 3.7), translation=(-15.0, 11.0, 5.85))])
    m.slots[0].size_mod = "end"
    m.slots[0].scale = (1.3, 0.35, 3.7)
    orders = paneling.panel_orders(m, _regions(), seed=1999)
    # 1.3m / 1.2 -> 1 col; 3.7m / 1.2 -> round(3.08) = 3 rows
    assert len(orders) == 3
    tops = [o["pos"][2] for o in orders]
    assert max(tops) < 7.7, tops        # inside the module, not above the roof


def test_budget_clamp():
    m = _manifest([_slot(slot_id=f"ext_{i}") for i in range(50)])
    orders = paneling.panel_orders(m, _regions(), seed=1999, max_orders=20)
    assert len(orders) == 20


# --------------------------------------------------------------------------- #
# Which side of the wall a panel lands on
# --------------------------------------------------------------------------- #
# A single-slot manifest cannot catch this: its own translation IS the
# footprint centre, so there is no "away" and the sign stays +1. Every test
# above is that shape, which is why the whole facade could be inside-out with
# a green suite. These build a box.

def _box():
    """Four perimeter walls of a 40 x 24 m building centred on the origin.

    ``facing`` is what DC would emit for each -- and note the values are just
    carried, never read: the outward rule works off position alone.
    """
    return _manifest([
        _slot(slot_id="ext_0_N_seg0", facing="N", rot_y=0.0,
              translation=(0.0, 12.0, 2.1)),
        _slot(slot_id="ext_0_S_seg0", facing="S", rot_y=180.0,
              translation=(0.0, -12.0, 2.1)),
        _slot(slot_id="ext_0_E_seg0", facing="E", rot_y=90.0,
              translation=(20.0, 0.0, 2.1)),
        _slot(slot_id="ext_0_W_seg0", facing="W", rot_y=270.0,
              translation=(-20.0, 0.0, 2.1)),
    ])


def _first(orders, slot_id):
    return next(o for o in orders if o["slot_id"] == slot_id)


def test_every_wall_of_a_box_panels_on_the_outside():
    """The defect, at full size: 546 of 1032 panel fields faced indoors.

    Local +Y is not "out" -- ``rot_y`` swings it to -X at 90 degrees and +X at
    270, so the east and west walls of every building were panelled on their
    room side. Non-collision geometry standing in walkable floor space, which
    is the rule this pipeline is not allowed to break.
    """
    orders = paneling.panel_orders(_box(), _regions(), seed=1999)
    n = _first(orders, "ext_0_N_seg0")
    s = _first(orders, "ext_0_S_seg0")
    e = _first(orders, "ext_0_E_seg0")
    w = _first(orders, "ext_0_W_seg0")

    assert n["normal"] == [0.0, 1.0, 0.0]
    assert s["normal"] == [0.0, -1.0, 0.0]
    assert e["normal"] == [1.0, 0.0, 0.0]      # was [-1, 0, 0]: into the room
    assert w["normal"] == [-1.0, 0.0, 0.0]     # was [1, 0, 0]

    # and the face plane moved with the normal, half a wall depth proud
    assert n["pos"][1] == pytest.approx(12.15, abs=1e-3)
    assert s["pos"][1] == pytest.approx(-12.15, abs=1e-3)
    assert e["pos"][0] == pytest.approx(20.15, abs=1e-3)   # was 19.85
    assert w["pos"][0] == pytest.approx(-20.15, abs=1e-3)  # was -19.85


def test_a_perimeter_wall_facing_into_the_building_still_panels_outward():
    """``facing`` is not a compass bearing on the shell.

    DC emits slots per ROOM, so ``facing`` says which way a surface points into
    the space it bounds. A wall along the building's south edge that bounds the
    room to its north is authored facing N -- pointing INTO the building. This
    is the residual half of the count the rotation alone does not explain:
    28 N and 24 S pilasters inward on the shipped building.
    """
    m = _manifest(_box().slots + [
        _slot(slot_id="ext_0_S_seg1", facing="N", rot_y=0.0,
              translation=(6.0, -12.0, 2.1))])
    o = _first(paneling.panel_orders(m, _regions(), seed=1999), "ext_0_S_seg1")
    assert o["normal"] == [0.0, -1.0, 0.0]     # out, not where facing points
    assert o["pos"][1] == pytest.approx(-12.15, abs=1e-3)


def test_the_footprint_center_is_a_bbox_midpoint_not_a_mean():
    """One densely partitioned wing must not drag the centre into itself.

    With a mean, twenty slots clustered at the west end move the centre west
    far enough that the east wall reads as the near face and panels inward --
    the original bug back, in a shape no rotation explains.
    """
    from patina import slots as S
    crowd = [_slot(slot_id=f"int_0_{i}", facing="N", translation=(-19.0, 0.0, 2.1))
             for i in range(20)]
    m = _manifest(_box().slots + crowd)
    assert S.footprint_center(m) == (0.0, 0.0)
    o = _first(paneling.panel_orders(m, _regions(), seed=1999), "ext_0_E_seg0")
    assert o["normal"] == [1.0, 0.0, 0.0]


def test_a_lone_slot_keeps_the_old_direction():
    """No building to be outside of, so nothing changes and nothing breaks.

    Every manifest in this file's older tests is this shape. Pinned so the
    degenerate case stays a deliberate answer rather than an accident of
    which way a zero dot product rounds.
    """
    o = paneling.panel_orders(_manifest([_slot()]), _regions(), seed=1999)[0]
    assert o["normal"] == [0.0, 1.0, 0.0]
