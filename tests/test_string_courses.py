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
        assert x["size2"][0] == pytest.approx(6.0) and len(x["slot_ids"]) == 3   # three 2 m slots, one band


def test_an_opening_splits_a_run_and_does_not_drop_it():
    """Slice 3's first build: one band a slot left a tick at every joint. A run joins them; a slot whose band
    meets an opening's keep-out is refused alone and the run either side of it stands."""
    m = _block(storeys=2)
    m.slots.append(_slot("ext_1_N_open0", "N", 0.0, 3.0, 1, 0.0, role="doorway", base=WALL_H + SLAB, h=WALL_H,
                         openings_=[{"kind": "door", "width": 1.0, "height": 3.0, "sill": 0.0}]))
    m.slots = [s for s in m.slots if s.slot_id != "ext_1_N_seg1"]
    north = [x for x in framing.string_course_orders(m, _regions(), seed=1999) if x["normal"][1] > 0.5]
    assert north and all("ext_1_N_open0" not in x["slot_ids"] for x in north)
    assert sum(x["size2"][0] for x in north) == pytest.approx(4.0)


def test_none_at_grade_on_one_storey_or_on_an_empty():
    assert framing.string_course_orders(_block(storeys=1), _regions(), seed=1999) == []
    assert framing.string_course_orders(_block(storeys=2, glazing="facade"), _regions(), seed=1999) == []


def test_an_opening_set_on_its_sill_stands_on_no_floor_line():
    m = _block(storeys=2)
    m.slots.append(_slot("ext_1_N_open0", "N", 0.0, 3.0, 1, 0.0, role="window", base=WALL_H + SLAB + 0.85, h=1.6))
    o = framing.string_course_orders(m, _regions(), seed=1999)
    assert "ext_1_N_open0" not in {x["slot_id"] for x in o}
