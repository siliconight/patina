"""The second keep-out: dressing never sits where a body will be.

`patina.gameplay` derives keep-out volumes from the shell's own gameplay.json --
objectives, cover markers, landmarks, spawns -- and hands them to
`openings.apply` in the same shape as the opening boxes, so one filter enforces
both over the assembled order list.

These tests pin the two things most likely to break it quietly:

  * the Z BAND. Without one, a ground-floor cover marker excludes a roofline
    strip nine metres above it. That protects nothing and deletes dressing,
    and it would look like the filter working.
  * the ROOM-BOUNDS TRAP. `openings.keep_out_boxes` already measured it -- room
    bounds flagged 1034 of 2098 orders because a room's bounds include the wall
    plane every facade cover sits on. Nothing here may use a room extent.
"""

import json
import os

import pytest

from patina import gameplay, openings

_HERE = os.path.dirname(__file__)


def _marker(kind, x, y, z=0.0, room="r"):
    return {"type": kind, "x": x, "y": y, "z": z, "room": room, "id": f"{kind}_1"}


def _order(cover, pos, size=1.0):
    return {"cover": cover, "pos": list(pos), "size": size}


# --------------------------------------------------------------------------- #

def test_no_gameplay_yields_no_boxes():
    """Absence must be empty, never a crash and never a silent pass -- the
    caller prints 'NOT enforced' on this."""
    assert gameplay.keep_out_boxes(None) == []
    assert gameplay.keep_out_boxes({}) == []
    assert gameplay.keep_out_boxes({"markers": [], "objectives": []}) == []


def test_every_protected_kind_produces_a_box():
    gp = {"markers": [_marker(k, 0.0, 0.0) for k in
                      ("cover_low", "cover_high", "landmark",
                       "crew_spawn", "responder_spawn")],
          "objectives": [{"x": 5.0, "y": 5.0, "z": 0.0, "id": "obj"}]}
    boxes = gameplay.keep_out_boxes(gp)
    assert gameplay.counts(boxes) == {
        "cover_high": 1, "cover_low": 1, "crew_spawn": 1,
        "landmark": 1, "objective": 1, "responder_spawn": 1}


def test_ignored_kinds_are_not_protected():
    """Listed rather than omitted, so the absence stays a decision."""
    gp = {"markers": [_marker(k, 0.0, 0.0) for k in gameplay.IGNORED]}
    assert gameplay.keep_out_boxes(gp) == []


def test_boxes_are_bounded_and_non_degenerate():
    gp = {"markers": [_marker(k, 0.0, 0.0) for k in gameplay.KINDS]}
    for b in gameplay.keep_out_boxes(gp):
        assert b["x1"] > b["x0"] and b["y1"] > b["y0"] and b["z1"] > b["z0"]
        vol = ((b["x1"] - b["x0"]) * (b["y1"] - b["y0"]) *
               (b["z1"] - b["z0"]))
        assert 1.0 < vol < 400.0, (b["kind"], vol)


def test_the_filter_actually_drops_an_order_on_a_cover_marker():
    """Prove the detector. A gate that never fires is indistinguishable from
    one that was removed."""
    gp = {"markers": [_marker("cover_low", 0.0, 0.0)]}
    boxes = gameplay.keep_out_boxes(gp)
    kept, report = openings.apply([_order("gutter_run", (0.0, 0.0, 1.0))], boxes)
    assert kept == []
    assert report["dropped"] == {"gutter_run": 1}


def test_an_order_clear_of_every_marker_survives():
    gp = {"markers": [_marker("cover_low", 0.0, 0.0)]}
    boxes = gameplay.keep_out_boxes(gp)
    kept, report = openings.apply([_order("gutter_run", (40.0, 40.0, 1.0))],
                                  boxes)
    assert len(kept) == 1 and report["dropped"] == {}


def test_the_z_band_spares_a_roofline_strip_above_a_cover_marker():
    """THE regression this file exists for. A cover marker on the ground floor
    must not delete dressing on the roof directly above it."""
    gp = {"markers": [_marker("cover_low", 0.0, 0.0, z=0.0)]}
    boxes = gameplay.keep_out_boxes(gp)
    high = _order("edge_strip", (0.0, 0.0, 9.0), size=0.6)
    low = _order("edge_strip", (0.0, 0.0, 1.0), size=0.6)
    kept, _ = openings.apply([high, low], boxes)
    assert kept == [high], "the ground-level strip should drop, the roof one stay"


def test_frame_stays_exempt_under_the_new_boxes():
    """`frame` is the sole exemption in `openings.EXEMPT`, and adding a second
    box source must not quietly change that."""
    gp = {"markers": [_marker("cover_low", 0.0, 0.0)]}
    boxes = gameplay.keep_out_boxes(gp)
    kept, _ = openings.apply([_order("frame", (0.0, 0.0, 1.0))], boxes)
    assert len(kept) == 1


def test_landmark_gets_more_breathing_space_than_cover():
    """sect.5 'do not crowd the landmark' -- and it must be visible in the
    numbers, not just the docstring."""
    gp = {"markers": [_marker("landmark", 0.0, 0.0),
                      _marker("cover_low", 100.0, 0.0)]}
    b = {x["kind"]: x for x in gameplay.keep_out_boxes(gp)}
    assert (b["landmark"]["x1"] - b["landmark"]["x0"]) > \
           (b["cover_low"]["x1"] - b["cover_low"]["x0"])


def test_no_box_is_derived_from_a_room_extent():
    """The trap `openings.keep_out_boxes` documents, declined a second time.

    A room on the demo building is 30 x 13 m. Every box here is a point radius
    of at most STANCE + 2.0, so no side may approach a room's scale.
    """
    gp = {"markers": [_marker(k, 0.0, 0.0) for k in gameplay.KINDS],
          "objectives": [{"x": 0.0, "y": 0.0, "z": 0.0, "id": "o"}]}
    widest = 2.0 * (gameplay.STANCE + max(v[0] for v in gameplay.KINDS.values()))
    for b in gameplay.keep_out_boxes(gp):
        assert (b["x1"] - b["x0"]) <= widest + 1e-9
        assert (b["y1"] - b["y0"]) <= widest + 1e-9
    assert widest < 6.0, widest


def test_shipped_demo_building_if_present():
    """Against the real file when it is reachable, so the shape of live data
    is exercised rather than only the fixtures above."""
    path = os.path.join(_HERE, "data", "lot_demo_001.gameplay.json")
    if not os.path.isfile(path):
        pytest.skip("no shipped gameplay fixture")
    with open(path, encoding="utf-8") as f:
        gp = json.load(f)
    boxes = gameplay.keep_out_boxes(gp)
    assert boxes, "the demo building carries markers; zero boxes is a bug"
    assert set(gameplay.counts(boxes)) <= set(gameplay.KINDS) | {"objective"}
