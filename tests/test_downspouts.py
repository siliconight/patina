"""Gutters at the eave and downspouts to the ground (0.25.0).

The walker, 2026-10-04: "also we need rain gutters". Patina has emitted a
`gutter_run` under every top-storey roofline since 0.18, and nothing drew
the pipe that carries the water down -- the thing that makes a gutter read
from the street (the walker's South Philly row: a pale downspout down the
party wall). And since Deli Counter 0.177.0 made parapets into wall slots,
the "top storey" was the parapet: cold run 9151 measured `gs_empty_rowhome_f`'s
gutters at z 9.92 on `parapet_*` slots, the top of the parapet, where 9148
had them at 8.92 under the roof.
"""
import pytest

from patina import framing, openings, trim
from patina.slots import Slot, SlotManifest

H = 3.1


def _wall(sid, side, x, y, story, rot, h=H, role="wall", openings_=None, dims=None):
    return Slot(slot_id=sid, role=role, current_ref=f"{role}_greybox_01", facing=side,
                story=story, translation=(x, y, story * H + h / 2.0), rot_y=rot,
                dims=dims or (2.0, 0.3, h), openings=openings_ or [])


def _rowhouse(window_on=("N",), parapet=True, storeys=3):
    """A 6 x 12 m house: walls on four sides, three 2 m modules a side on the
    short (N/S) faces and six on the long (E/W) ones, `storeys` high, a
    window on the faces named, and a parapet on top."""
    slots = []
    for st in range(storeys):
        for i in range(3):
            x = -2.0 + 2.0 * i
            slots.append(_wall(f"ext_{st}_N_seg{i}", "N", x, 6.0, st, 0.0))
            slots.append(_wall(f"ext_{st}_S_seg{i}", "S", x, -6.0, st, 180.0))
        for i in range(6):
            y = -5.0 + 2.0 * i
            slots.append(_wall(f"ext_{st}_E_seg{i}", "E", 3.0, y, st, 90.0))
            slots.append(_wall(f"ext_{st}_W_seg{i}", "W", -3.0, y, st, 270.0))
    for side, (x, y, rot) in {"N": (0.0, 6.0, 0.0), "S": (0.0, -6.0, 180.0),
                              "E": (3.0, 0.0, 90.0), "W": (-3.0, 0.0, 270.0)}.items():
        if side in window_on:
            slots.append(_wall(f"ext_1_{side}_open0", side, x, y, 1, rot, role="window",
                               dims=(0.95, 0.3, H),
                               openings_=[{"kind": "window", "width": 0.95, "height": 1.6,
                                           "sill": 0.85}]))
    if parapet:
        for side, (x, y, rot, run) in {"N": (0.0, 6.0, 0.0, 6.0), "S": (0.0, -6.0, 180.0, 6.0),
                                       "E": (3.0, 0.0, 90.0, 11.4), "W": (-3.0, 0.0, 270.0, 11.4)}.items():
            slots.append(Slot(slot_id=f"parapet_{side}", role="wall", current_ref="wall_greybox_01",
                              facing=side, story=storeys,
                              translation=(x, y, storeys * H + 0.4), rot_y=rot,
                              dims=(run, 0.3, 0.8), openings=[]))
    return SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                        module_size=2.0, space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def test_gutters_hang_at_the_eave_not_on_the_parapet():
    """FAILS ON 0.24.0: the parapet was the top storey, and the gutters
    stood on top of it."""
    g = framing.gutter_orders(_rowhouse(), _regions(), seed=1999)
    assert g and not [o for o in g if o["slot_id"].startswith("parapet_")]
    assert {round(o["pos"][2], 3) for o in g} == {round(3 * H - 0.08, 3)}


def test_a_downspout_comes_down_each_face_with_an_opening_and_no_other():
    """FAILS ON 0.24.0: no downspout at all."""
    d = framing.downspout_orders(_rowhouse(window_on=("N", "S")), _regions(), seed=1999)
    faces = sorted(tuple(o["normal"][:2]) for o in d)
    assert faces == [(0.0, -1.0), (0.0, 1.0)]
    assert {o["cover"] for o in d} == {"downspout"}


def test_it_runs_from_the_gutter_s_underside_to_the_ground():
    d = framing.downspout_orders(_rowhouse(), _regions(), seed=1999)[0]
    top = 3 * H - 0.08 - framing.GUTTER_CROSS / 2.0
    assert d["size"] == pytest.approx(top, abs=1e-3)
    assert d["pos"][2] == pytest.approx(top / 2.0, abs=1e-3)
    # on the outside of the north face, at one end of it
    assert d["pos"][1] == pytest.approx(6.15, abs=1e-3)
    assert abs(abs(d["pos"][0]) - (3.0 - framing.DOWNSPOUT_INSET)) < 1e-3


def test_it_takes_the_end_clear_of_the_openings():
    """A window at one end of the face sends the pipe to the other; the
    opening keep-out Patina already enforces is the judge, so the placement
    and the filter cannot disagree."""
    m = _rowhouse(window_on=())
    for i, x in ((0, -2.4), (1, 2.4)):
        blocked = _rowhouse(window_on=())
        blocked.slots.append(_wall("ext_1_N_open0", "N", x, 6.0, 1, 0.0, role="window",
                                   dims=(0.95, 0.3, H),
                                   openings_=[{"kind": "window", "width": 0.95, "height": 1.6,
                                               "sill": 0.85}]))
        boxes = openings.keep_out_boxes(blocked)
        d = framing.downspout_orders(blocked, _regions(), seed=1999 + i, keep_out=boxes)
        assert len(d) == 1 and openings.hits(d[0], boxes) == []
        assert (d[0]["pos"][0] > 0) == (x < 0)
    assert framing.downspout_orders(m, _regions(), seed=1999) == []


def test_a_long_face_gets_one_every_twelve_metres():
    long_run = [Slot(slot_id=f"ext_0_N_seg{i}", role="wall", current_ref="wall_greybox_01",
                     facing="N", story=0, translation=(-29.0 + 2.0 * i, 6.0, 1.55), rot_y=0.0,
                     dims=(2.0, 0.3, H)) for i in range(30)]
    door = Slot(slot_id="ext_0_N_open0", role="doorway", current_ref="doorway_greybox_01",
                facing="N", story=0, translation=(0.0, 6.0, 1.55), rot_y=0.0,
                dims=(1.0, 0.3, H), openings=[{"kind": "door", "width": 1.0, "height": 2.2, "sill": 0.0}])
    m = SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                     module_size=2.0, space="spec/Blender Z-up raw coords", slots=long_run + [door])
    d = framing.downspout_orders(m, _regions(), seed=1999, keep_out=openings.keep_out_boxes(m))
    assert len(d) == 5            # 60 m of gutter, one every 12 m


def test_the_same_seed_places_the_same_pipes():
    a = framing.downspout_orders(_rowhouse(), _regions(), seed=7)
    assert a == framing.downspout_orders(_rowhouse(), _regions(), seed=7)


def test_the_opening_filter_reads_a_downspout_as_a_vertical_run():
    """`openings` mirrors Zoo's cover sizes; a downspout runs up the wall
    like a conduit, so its footprint is a vertical line, not a strip
    across the face."""
    o = {"cover": "downspout", "pos": [0.0, 6.15, 4.6], "normal": [0.0, 1.0, 0.0], "size": 9.2}
    b = openings.order_box(o)
    assert b["z0"] == pytest.approx(0.0) and b["z1"] == pytest.approx(9.2)
    assert b["x0"] == pytest.approx(0.0) and b["x1"] == pytest.approx(0.0)
