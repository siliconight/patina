"""The keep-out rule: dressing never intersects a traversable opening.

A door, window, garage or breach is a hole a player walks or shoots through.
Measured on `category5_baie_dore_001` before the rule existed -- 19 openings,
2184 orders -- 25 non-frame orders had their ORIGIN inside one: 14 pilasters
across windows, 5 base courses and 5 curbs through door thresholds. Sweeping
each order's declared span finds more, because an order centred beside a door
can still reach across it.
"""
import math

import pytest

from patina import openings, trim
from patina.slots import Slot, SlotManifest


def _slot(slot_id="ext_0_N_open1", role="doorway", rot_y=0.0,
          translation=(0.0, 10.0, 1.85), ops=None):
    return Slot(slot_id=slot_id, role=role, current_ref=f"{role}_greybox_01",
                facing="N", translation=translation, rot_y=rot_y,
                dims=(2.0, 0.35, 3.7),
                openings=([{"kind": "door", "width": 1.2, "height": 2.1,
                            "sill": 0.0}] if ops is None else ops))


def _manifest(slots):
    return SlotManifest(version="1.2.0", building_id="t", theme="greybox",
                        module_library="art/zoo", module_size=2.0,
                        space="spec/Blender Z-up raw coords", slots=slots)


def _boxes(slots=None):
    return openings.keep_out_boxes(_manifest(slots or [_slot()]))


def _order(cover, pos, **kw):
    o = {"cover": cover, "pos": list(pos), "normal": [0.0, 1.0, 0.0],
         "size": 2.0}
    o.update(kw)
    return o


# -- the box ---------------------------------------------------------------- #

def test_an_opening_becomes_a_box_on_its_wall_plane():
    b = _boxes()[0]
    # slot base = 1.85 - 3.7/2 = 0.0; sill 0 -> 0.0 .. 2.1, plus margin
    assert b["z0"] == pytest.approx(-openings.MARGIN)
    assert b["z1"] == pytest.approx(2.1 + openings.MARGIN)
    assert b["x0"] < -0.6 and b["x1"] > 0.6      # 1.2 m wide plus margin
    assert b["kind"] == "door"


def test_every_traversable_kind_is_kept_out():
    """A breach is a hole something already came through."""
    for kind in openings.TRAVERSABLE:
        s = _slot(ops=[{"kind": kind, "width": 1.2, "height": 2.1, "sill": 0.0}])
        assert len(openings.keep_out_boxes(_manifest([s]))) == 1, kind


def test_a_slot_with_no_openings_contributes_nothing():
    s = _slot(role="wall", ops=[])
    assert openings.keep_out_boxes(_manifest([s])) == []


# -- the rule --------------------------------------------------------------- #

def test_a_curb_through_a_doorway_is_dropped():
    """The literal 'expect to walk through' case."""
    boxes = _boxes()
    kept, rep = openings.apply([_order("curb", (0.0, 10.0, 0.0))], boxes)
    assert kept == []
    assert rep["dropped"]["curb"] == 1


def test_a_curb_clear_of_the_door_survives():
    boxes = _boxes()
    kept, rep = openings.apply([_order("curb", (8.0, 10.0, 0.0))], boxes)
    assert len(kept) == 1 and not rep["dropped"]


def test_a_strip_that_only_REACHES_the_opening_is_caught():
    """Point-in-box is not enough: a 2 m strip beside a door crosses it."""
    boxes = _boxes()
    beside = _order("base_course", (1.3, 10.0, 0.0),
                    tangent=[1.0, 0.0, 0.0], size=2.0)
    assert openings.hits(beside, boxes), "swept span must be tested, not the origin"


def test_frame_is_the_sole_exemption():
    """Surrounding an opening is the entire point of a frame."""
    boxes = _boxes()
    f = _order("frame", (0.0, 10.0, 1.05), size2=[1.2, 2.1])
    assert openings.hits(f, boxes) == []
    kept, rep = openings.apply([f], boxes)
    assert kept == [f] and not rep["dropped"]
    assert openings.EXEMPT == ("frame",), "adding a second must be deliberate"


# -- conduit is shortened, not dropped -------------------------------------- #

def test_a_conduit_starts_above_the_door_it_would_cross():
    """It runs from the ground UP to a fixture above a door, so it crosses by
    definition. Dropping it would delete the run; it should start higher."""
    boxes = _boxes()
    # run 0.0 -> 2.45, centred at 1.225
    c = _order("conduit_run", (0.0, 10.0, 1.225), size=2.45)
    kept, rep = openings.apply([c], boxes)
    assert rep["shortened"]["conduit_run"] == 1
    got = kept[0]
    top = 2.1 + openings.MARGIN
    assert got["pos"][2] > c["pos"][2], "must start higher, not lower"
    assert got["size"] == pytest.approx(2.45 - top, abs=2e-3)
    assert got["clipped_by"] == ["ext_0_N_open1"]


def test_a_conduit_with_nothing_left_is_dropped():
    """Fixture inside the opening: there is no run to build."""
    boxes = _boxes()
    c = _order("conduit_run", (0.0, 10.0, 0.5), size=1.0)
    kept, rep = openings.apply([c], boxes)
    assert kept == [] and rep["dropped"]["conduit_run"] == 1


# -- the gate --------------------------------------------------------------- #

def test_violations_is_empty_after_the_filter_and_not_before():
    """A filter with no gate is a filter somebody removes later."""
    boxes = _boxes()
    orders = [_order("curb", (0.0, 10.0, 0.0)),
              _order("pilaster", (0.0, 10.0, 1.0), size2=[0.24, 3.7]),
              _order("curb", (8.0, 10.0, 0.0))]
    assert len(openings.violations(orders, boxes)) == 2
    kept, _rep = openings.apply(orders, boxes)
    assert openings.violations(kept, boxes) == []


def test_manifest_enforces_the_rule_and_reports_it():
    _png, regions = trim.build_sheet(size=64, seed=1999)
    dm = trim.dressing_manifest(
        [], regions, seed=1999, source="t.glb", sheet_file="t.trim.png",
        space="spec/Blender Z-up raw coords", building_id="t",
        extra_orders=[_order("curb", (0.0, 10.0, 0.0)),
                      _order("curb", (8.0, 10.0, 0.0))],
        keep_out=_boxes())
    assert len(dm["orders"]) == 1
    assert dm["keep_out"]["dropped"] == {"curb": 1}
    assert dm["keep_out"]["openings"] == 1


def test_no_keep_out_means_no_filtering_and_no_report():
    """Absent boxes must not silently read as 'nothing to protect'."""
    _png, regions = trim.build_sheet(size=64, seed=1999)
    dm = trim.dressing_manifest(
        [], regions, seed=1999, source="t.glb", sheet_file="t.trim.png",
        space="spec/Blender Z-up raw coords",
        extra_orders=[_order("curb", (0.0, 10.0, 0.0))])
    assert len(dm["orders"]) == 1
    assert "keep_out" not in dm


def test_shortening_survives_millimetre_rounding():
    """A rounded centre must not pull the foot back under the door head.

    Found by the gate, not by eye: the first implementation produced a centre
    of 3.087 from 3.0875 and left the conduit 0.0005 m inside the opening.
    """
    boxes = _boxes()
    top = 2.1 + openings.MARGIN
    for run in (2.45, 2.55, 2.85, 3.0, 3.3):
        c = _order("conduit_run", (0.0, 10.0, run / 2.0), size=run)
        kept, _rep = openings.apply([c], boxes)
        if not kept:
            continue
        got = kept[0]
        foot = got["pos"][2] - got["size"] / 2.0
        assert foot >= top - 1e-9, (run, foot, top)
        assert openings.violations(kept, boxes) == [], run
