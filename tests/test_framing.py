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
    assert o["size2"] == [0.24, 4.2]


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
