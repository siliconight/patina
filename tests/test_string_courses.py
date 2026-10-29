"""A string course at every floor line (the factory's roadmap 324).

Between two storeys Deli Counter leaves the slab's edge recessed half a wall: a groove at every floor of every
building that is not an Empty. A string course covers it: one band a wall slot of the storey above, at the floor line,
lapping the walls above and below.
"""
import pytest

from patina import framing, trim
from patina.slots import Slot, SlotManifest

WALL_H, SLAB = 3.3, 0.3


def _slot(sid, side, x, y, story, rot, role="wall", base=None, h=WALL_H, glazing=None, openings_=None):
    b = story * (WALL_H + SLAB) if base is None else base
    return Slot(slot_id=sid, role=role, current_ref=f"{role}_greybox_01", facing=side, story=story,
                translation=(x, y, b + h / 2.0), rot_y=rot, dims=(2.0, 0.3, h), glazing=glazing,
                openings=openings_ or [])


def _block(storeys=2, glazing=None):
    """A 6 m square, `storeys` high: three 2 m wall slots a side a storey, slabs 0.3 m between."""
    slots = []
    for st in range(storeys):
        for side, (y, rot) in {"N": (3.0, 0.0), "S": (-3.0, 180.0)}.items():
            for i, x in enumerate((-2.0, 0.0, 2.0)):
                slots.append(_slot(f"ext_{st}_{side}_seg{i}", side, x, y, st, rot, glazing=glazing))
        for side, (x, rot) in {"E": (3.0, 90.0), "W": (-3.0, 270.0)}.items():
            for i, y in enumerate((-2.0, 0.0, 2.0)):
                slots.append(_slot(f"ext_{st}_{side}_seg{i}", side, x, y, st, rot, glazing=glazing))
    return SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                        module_size=2.0, space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def test_a_band_at_every_floor_line_over_the_slab():
    """FAILS ON 0.34.0: no string course."""
    o = framing.string_course_orders(_block(storeys=3), _regions(), seed=1999)
    assert len(o) == 2 * 4                                    # two floor lines, one run a side each
    zs = sorted({round(x["pos"][2], 3) for x in o})
    assert zs == [pytest.approx(WALL_H + SLAB / 2.0), pytest.approx(2 * (WALL_H + SLAB) - SLAB / 2.0)]
    for x in o:
        assert x["cover"] == "string_course" and x["collision"] == "none"
        assert x["size2"][1] == pytest.approx(SLAB + 2 * framing.STRING_OVER)
        # three 2 m slots, one band; N and S on round both corners, E and W to the N and S bands' backs (0.36.0)
        ns = abs(x["normal"][1]) > 0.5
        face = 3.15
        want = 2 * (face + framing._BAND_PROUD) if ns else 2 * (face - framing._BAND_INTO)
        assert x["size2"][0] == pytest.approx(want) and len(x["slot_ids"]) == 3


def test_an_opening_splits_a_run_and_does_not_drop_it():
    """Slice 3's first build: one band a slot left a tick at every joint. A run joins them; a slot whose band
    meets an opening's keep-out is refused alone and the run either side of it stands."""
    m = _block(storeys=2)
    m.slots.append(_slot("ext_1_N_open0", "N", 0.0, 3.0, 1, 0.0, role="doorway", base=WALL_H + SLAB, h=WALL_H,
                         openings_=[{"kind": "door", "width": 1.0, "height": 3.0, "sill": 0.0}]))
    m.slots = [s for s in m.slots if s.slot_id != "ext_1_N_seg1"]
    north = [x for x in framing.string_course_orders(m, _regions(), seed=1999) if x["normal"][1] > 0.5]
    assert north and all("ext_1_N_open0" not in x["slot_ids"] for x in north)
    # the two 2 m pieces either side of the door, each run on round its corner (0.36.0)
    assert sum(x["size2"][0] for x in north) == pytest.approx(4.0 + 2 * (0.15 + framing._BAND_PROUD))


def test_none_at_grade_on_one_storey_or_on_an_empty():
    assert framing.string_course_orders(_block(storeys=1), _regions(), seed=1999) == []
    assert framing.string_course_orders(_block(storeys=2, glazing="facade"), _regions(), seed=1999) == []


def test_an_opening_set_on_its_sill_stands_on_no_floor_line():
    m = _block(storeys=2)
    m.slots.append(_slot("ext_1_N_open0", "N", 0.0, 3.0, 1, 0.0, role="window", base=WALL_H + SLAB + 0.85, h=1.6))
    o = framing.string_course_orders(m, _regions(), seed=1999)
    assert "ext_1_N_open0" not in {x["slot_id"] for x in o}


def _parapeted(storeys=2):
    """`_block` with Deli Counter 0.292.0's parapet -- on the walls' outer faces from the top storey's wall top,
    1.4 m -- and the roof slab under it, 0.3 m thick."""
    m = _block(storeys=storeys)
    top = (storeys - 1) * (WALL_H + SLAB) + WALL_H
    for side, (x, y, rot, run) in {"N": (0.0, 3.05, 0.0, 6.3), "S": (0.0, -3.05, 180.0, 6.3),
                                   "E": (3.05, 0.0, 90.0, 5.9), "W": (-3.05, 0.0, 270.0, 5.9)}.items():
        m.slots.append(Slot(slot_id=f"parapet_{side}_t0_0", role="wall", current_ref="wall_greybox_01",
                            facing=side, story=storeys, translation=(x, y, top + 0.7), rot_y=rot,
                            dims=(run, 0.2, 1.4)))
    m.slots.append(Slot(slot_id="roof_footprint", role="roof", current_ref="roof_greybox_01", story=storeys,
                        translation=(0.0, 0.0, top + SLAB / 2.0), dims=(6.0, 6.0, SLAB)))
    return m


def test_a_band_marks_the_roof_line_under_a_parapet():
    """FAILS ON 0.35.0: no band where the roof is."""
    o = framing.string_course_orders(_parapeted(storeys=2), _regions(), seed=1999)
    roof = [x for x in o if x["anchor_kind"] == "roof_line"]
    assert len(roof) == 4
    top = WALL_H + SLAB + WALL_H
    for x in roof:
        assert x["pos"][2] == pytest.approx(top + SLAB / 2.0)
        assert x["size2"][1] == pytest.approx(SLAB + 2 * framing.STRING_OVER)


def test_the_bands_close_every_outside_corner_without_overlapping():
    """FAILS ON 0.35.0: a band built from wall slots stopped a wall short of every corner."""
    o = framing.string_course_orders(_parapeted(storeys=2), _regions(), seed=1999)
    for level in ("floor_line", "roof_line"):
        runs = [x for x in o if x["anchor_kind"] == level]
        n = next(x for x in runs if x["normal"][1] > 0.5)
        e = next(x for x in runs if x["normal"][0] > 0.5)
        n_face, e_face = n["pos"][1], e["pos"][0]
        assert n["pos"][0] + n["size2"][0] / 2 == pytest.approx(e_face + framing._BAND_PROUD)
        assert e["pos"][1] + e["size2"][0] / 2 == pytest.approx(n_face - framing._BAND_INTO)
