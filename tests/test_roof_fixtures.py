"""An Empty's roof fixtures (0.29.0): a TV antenna, and the odd satellite dish.

Deli Counter (>= 0.185.0) writes `antenna` / `dish` on an Empty's roof slot,
with `front`, the facing of the wall that holds its front door; this orders
them for Zoo (>= 1.74.0) to build, set back from the front parapet.
"""
import math

import pytest

from patina import framing, openings, slots, trim
from patina.slots import Slot, SlotManifest


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def _manifest(building="gs_empty_rowhome_t", **roof):
    # a rowhome Empty's roof, 6.0 x 12.0 with its top at 9.30, and parapets
    # 0.9 m tall and 0.3 m thick on the front (S) and the back (N)
    r = Slot(slot_id="roof_footprint", role="roof", current_ref="roof_greybox_01", facing="up",
             story=3, translation=(0.0, 0.0, 9.15), rot_y=0.0, dims=(6.0, 12.0, 0.3), **roof)
    par = [Slot(slot_id=f"parapet_{f}_t0_{k}", role="wall", current_ref="wall_greybox_01",
                story=3, translation=(x, y, 9.75), rot_y=0.0 if f == "N" else 180.0,
                dims=(3.0, 0.3, 0.9))
           for f, y in (("N", 5.85), ("S", -5.85)) for k, x in enumerate((-1.5, 1.5))]
    return SlotManifest(version="1.3.0", building_id=building, theme="greybox",
                        module_library="art/zoo", module_size=2.0,
                        space="spec/Blender Z-up raw coords", slots=[r] + par)


def _orders(building="gs_empty_rowhome_t", **roof):
    return framing.roof_fixture_orders(_manifest(building, **roof), _regions(), seed=1999)


def test_parse_reads_the_roof_fixtures():
    """FAILS ON 0.28.0: the slot model dropped them."""
    raw = {"slots": [{"slot_id": "roof_footprint", "role": "roof", "antenna": True, "dish": True,
                      "front": "S", "fit": {"dims": [6.0, 12.0, 0.3]}}]}
    s = slots.parse(raw).slots[0]
    assert (s.antenna, s.dish, s.front) == (True, True, "S")


def test_the_antenna_stands_on_the_roof_set_back_from_the_front_parapet():
    (o,) = _orders(antenna=True, front="S")
    assert o["cover"] == "tv_antenna" and o["normal"] == [0.0, 0.0, 1.0]
    x, y, z = o["pos"]
    assert z == pytest.approx(9.30)
    back = y - (-5.7)                    # behind the front parapet's inner face
    assert framing.ANTENNA_SETBACK[0] - 1e-3 <= back <= framing.ANTENNA_SETBACK[1] + 1e-3
    assert abs(x) <= framing.ANTENNA_ACROSS * 6.0 + 1e-3
    boom, mast = o["size2"]
    assert framing.ANTENNA_BOOM[0] <= boom <= framing.ANTENNA_BOOM[1]
    assert framing.ANTENNA_MAST[0] <= mast <= framing.ANTENNA_MAST[1]


def test_the_dish_stands_behind_the_parapet_with_its_bowl_over_it():
    (o,) = _orders(dish=True, front="S")
    assert o["cover"] == "sat_dish"
    assert o["pos"][1] == pytest.approx(-5.7 + framing.DISH_SETBACK)
    assert o["size2"] == [framing.DISH_WIDTH, round(0.9 + framing.DISH_ABOVE_PARAPET, 3)]


def test_they_look_along_their_bearings():
    a, d = _orders(antenna=True, dish=True, front="S")
    for o, deg in ((a, framing.ANTENNA_BEARING), (d, framing.DISH_BEARING)):
        tx, ty, _ = o["tangent"]
        assert math.degrees(math.atan2(tx, ty)) % 360.0 == pytest.approx(deg, abs=0.01)


def test_the_dish_stands_on_the_other_half_from_the_antenna():
    for b in "abcdef":
        a, d = _orders(building="gs_empty_rowhome_" + b, antenna=True, dish=True, front="S")
        assert a["pos"][0] * d["pos"][0] <= 0.0, b


def test_each_house_draws_its_own_antenna():
    """Every Empty's roof slot is `roof_footprint`: keyed by the slot alone,
    the whole street would draw the one antenna."""
    sizes = {tuple(_orders(building="gs_empty_rowhome_" + b, antenna=True, front="S")[0]["size2"])
             for b in "abcdefghijkl"}
    assert len(sizes) == 12


def test_nothing_without_a_front_and_nothing_unasked():
    assert _orders(antenna=True, dish=True) == []      # no front to set them back from
    assert _orders(front="S") == []


def test_they_are_exempt_from_the_keep_out():
    assert {"tv_antenna", "sat_dish"} <= set(openings.EXEMPT)
