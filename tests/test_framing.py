"""Tests for the facade kit orders (v0.18)."""

import pytest

from patina import framing, trim
from patina.slots import Slot, SlotManifest


def _slot(slot_id="ext_0_N_seg0", role="wall", facing="N", rot_y=0.0,
          dims=(2.0, 0.3, 4.2), translation=(-15.0, 11.0, 2.1),
          openings=None):
    return Slot(slot_id=slot_id, role=role, current_ref=f"{role}_greybox_01",
                facing=facing, translation=translation, rot_y=rot_y,
                dims=dims, openings=openings or [])


def _manifest(slots):
    return SlotManifest(version="1.2.0", building_id="t", theme="greybox",
                        module_library="art/zoo", module_size=2.0,
                        space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    _, regions = trim.build_sheet(size=64, seed=1999)
    return regions


def test_atlas_gained_frame_and_pilaster_pieces():
    pieces = {r.piece for r in _regions()}
    assert {"frame", "pilaster"} <= pieces


def test_frame_targets_the_opening_not_the_module():
    door = _slot(slot_id="ext_0_N_open1", role="doorway",
                 dims=(3.0, 0.3, 4.2), translation=(9.0, 11.0, 2.1),
                 openings=[{"kind": "garage", "width": 3.0, "height": 3.0,
                            "sill": 0.0}])
    orders = framing.frame_orders(_manifest([door]), _regions(), seed=1999)
    assert len(orders) == 1
    o = orders[0]
    assert o["size2"] == [3.0, 3.0]
    assert o["opening_kind"] == "garage"
    # module base z = 2.1 - 4.2/2 = 0.0; center = sill 0 + 3.0/2
    assert o["pos"][2] == pytest.approx(1.5)
    assert o["pos"][1] == pytest.approx(11.15)  # on the outer face
    assert o["normal"] == [0.0, 1.0, 0.0]


def test_window_sill_lifts_the_frame():
    win = _slot(role="window",
                openings=[{"kind": "window", "width": 3.0, "height": 2.4,
                           "sill": 1.0}])
    o = framing.frame_orders(_manifest([win]), _regions(), seed=1999)[0]
    assert o["pos"][2] == pytest.approx(0.0 + 1.0 + 1.2)


def test_gutter_rides_just_under_the_roofline():
    o = framing.gutter_orders(_manifest([_slot()]), _regions(), seed=1999)[0]
    assert o["cover"] == "gutter_run"
    assert o["pos"][2] == pytest.approx(4.2 - 0.08)
    assert o["size"] == pytest.approx(2.0)


def test_pilaster_sits_at_the_left_module_seam():
    o = framing.pilaster_orders(_manifest([_slot()]), _regions(), seed=1999)[0]
    assert o["cover"] == "pilaster"
    assert o["pos"][0] == pytest.approx(-16.0)   # -15 - w/2
    # was 0.24: a 24 cm column is 1/15 of a 3.7 m storey, coarse enough to
    # read as structure rather than trim. Halved with base_course.
    assert o["size2"] == [0.12, 4.2]


def test_interior_and_wall_only_filters():
    m = _manifest([_slot(),
                   _slot(slot_id="int_0", facing=None),
                   _slot(slot_id="ext_0_N_open1", role="doorway",
                         openings=[{"width": 1.0, "height": 2.1,
                                    "sill": 0.0}])])
    gutters = framing.gutter_orders(m, _regions(), seed=1999)
    pilasters = framing.pilaster_orders(m, _regions(), seed=1999)
    assert {o["slot_id"] for o in gutters} == {"ext_0_N_seg0"}
    assert {o["slot_id"] for o in pilasters} == {"ext_0_N_seg0"}


def test_deterministic():
    m = _manifest([_slot()])
    assert framing.gutter_orders(m, _regions(), seed=1999) == \
        framing.gutter_orders(m, _regions(), seed=1999)


# --------------------------------------------------------------------------- #
# Remainder walls: dims and scale are ONE measurement, not two factors
# --------------------------------------------------------------------------- #

def _remainder():
    """A real ``size_mod == "end"`` slot, copied off a shipped manifest.

    DC authors a wall remainder as a UNIT box and rides the real size on the
    per-slot scale, so ``scale`` is a COPY of ``dims`` -- 29 of 319 slots in
    ``category5_baie_dore_001`` look exactly like this. Storey height 3.7 m.
    """
    return Slot(slot_id="ext_1_N_end", role="wall", current_ref="wall_greybox_01",
                facing="N", size_mod="end", translation=(-15.0, 11.0, 5.85),
                dims=(1.3, 0.35, 3.7), scale=(1.3, 0.35, 3.7))


def test_a_remainder_wall_is_its_dims_not_dims_times_scale():
    """The regression: cover geometry three storeys above the building.

    ``dims[2] * scale[2]`` is ``3.7 * 3.7 == 13.69``, which put the measured
    ``Cover_gutter_run`` at 12.61 on a building whose roof is at 7.4. The slot
    is 3.7 m tall; the gutter belongs just under ITS top.
    """
    assert _remainder().size() == (1.3, 0.35, 3.7)
    o = framing.gutter_orders(_manifest([_remainder()]), _regions(), seed=1999)[0]
    # base = 5.85 - 3.7/2 = 4.0; top = 7.7; gutter = 7.7 - 0.08
    assert o["pos"][2] == pytest.approx(7.62)
    assert o["pos"][2] != pytest.approx(12.62)   # the squared answer
    assert o["size"] == pytest.approx(1.3)


def test_a_remainder_pilaster_is_module_tall_not_storey_squared():
    o = framing.pilaster_orders(_manifest([_remainder()]), _regions(),
                                seed=1999)[0]
    assert o["size2"] == [0.12, 3.7]      # width halved; the HEIGHT is the point
    assert o["pos"][2] == pytest.approx(4.0 + 3.7 / 2.0)


# --------------------------------------------------------------------------- #
# Which side of the wall a cover lands on
# --------------------------------------------------------------------------- #
# Same defect as paneling and the same blind spot in the tests above: a
# one-slot manifest is its own centre, so there is no outward direction left to
# get wrong. Measured on `category5_baie_dore_001`, 148 of 225 pilasters and 32
# of 74 gutters stood on the inside of their walls.

def _box(extra=()):
    """Four perimeter walls of a 40 x 24 m building centred on the origin."""
    return _manifest([
        _slot(slot_id="ext_0_N_seg0", facing="N", rot_y=0.0,
              translation=(0.0, 12.0, 2.1)),
        _slot(slot_id="ext_0_S_seg0", facing="S", rot_y=180.0,
              translation=(0.0, -12.0, 2.1)),
        _slot(slot_id="ext_0_E_seg0", facing="E", rot_y=90.0,
              translation=(20.0, 0.0, 2.1)),
        _slot(slot_id="ext_0_W_seg0", facing="W", rot_y=270.0,
              translation=(-20.0, 0.0, 2.1)),
    ] + list(extra))


def _by_slot(orders):
    return {o["slot_id"]: o for o in orders}


def test_pilasters_stand_on_the_outside_of_every_wall():
    o = _by_slot(framing.pilaster_orders(_box(), _regions(), seed=1999))
    assert o["ext_0_N_seg0"]["normal"] == [0.0, 1.0, 0.0]
    assert o["ext_0_S_seg0"]["normal"] == [0.0, -1.0, 0.0]
    assert o["ext_0_E_seg0"]["normal"] == [1.0, 0.0, 0.0]
    assert o["ext_0_W_seg0"]["normal"] == [-1.0, 0.0, 0.0]
    # a column proud of the east facade, not standing in the room behind it
    assert o["ext_0_E_seg0"]["pos"][0] == pytest.approx(20.15, abs=1e-3)
    assert o["ext_0_W_seg0"]["pos"][0] == pytest.approx(-20.15, abs=1e-3)


def test_a_pilaster_still_picks_one_end_of_its_module():
    """Flipping the FACE must not flip the module's own left edge.

    One pilaster per slot at ``lx = -w/2`` is what stops adjacent modules
    doubling up at a shared seam. Every slot in a wall run shares a ``rot_y``
    and therefore a sign, so they all still choose the same end.
    """
    run = [_slot(slot_id=f"ext_0_E_seg{i}", facing="E", rot_y=90.0,
                 translation=(20.0, -4.0 + 2.0 * i, 2.1)) for i in range(3)]
    o = framing.pilaster_orders(_manifest(run), _regions(), seed=1999)
    # lx = -w/2 = -1.0 along the module, which on a rot_y 90 wall runs along -Y
    assert [x["pos"][1] for x in o] == pytest.approx([-5.0, -3.0, -1.0])
    assert len({round(x["pos"][1], 3) for x in o}) == 3       # no doubles


def test_gutters_hang_off_the_outside():
    o = _by_slot(framing.gutter_orders(_box(), _regions(), seed=1999))
    assert o["ext_0_E_seg0"]["pos"][0] == pytest.approx(20.15, abs=1e-3)
    assert o["ext_0_W_seg0"]["normal"] == [-1.0, 0.0, 0.0]


def test_an_opening_frame_goes_on_the_outward_face():
    door = _slot(slot_id="ext_0_E_open1", role="doorway", facing="E",
                 rot_y=90.0, translation=(20.0, 4.0, 2.1),
                 openings=[{"kind": "door", "width": 1.0, "height": 2.1,
                            "sill": 0.0}])
    o = framing.frame_orders(_box([door]), _regions(), seed=1999)[0]
    assert o["normal"] == [1.0, 0.0, 0.0]
    assert o["pos"][0] == pytest.approx(20.15, abs=1e-3)


def test_a_perimeter_wall_facing_into_the_building_is_dressed_outward():
    """``facing`` points into the room a wall bounds, not out of the shell.

    DC emits slots per ROOM, so a wall along the building's south edge that
    bounds the room to its north is authored facing N -- pointing INTO the
    building. This is the half of the inward count that rotation alone does
    not explain: 28 N and 24 S pilasters on the shipped building.
    """
    inward = _slot(slot_id="ext_0_S_seg1", facing="N", rot_y=0.0,
                   translation=(6.0, -12.0, 2.1))
    o = _by_slot(framing.pilaster_orders(_box([inward]), _regions(), seed=1999))
    assert o["ext_0_S_seg1"]["normal"] == [0.0, -1.0, 0.0]
    assert o["ext_0_S_seg1"]["pos"][1] == pytest.approx(-12.15, abs=1e-3)


def test_a_slot_with_no_dims_raises_rather_than_placing_at_the_origin():
    """A missing manifest field must not read as a placement bug."""
    with pytest.raises(ValueError, match="fit.dims"):
        Slot(slot_id="ext_0", role="wall", current_ref="wall_greybox_01",
             dims=None).size()
