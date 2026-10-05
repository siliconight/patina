"""A gutter runs the whole eave, over the top-floor windows too (0.25.1).

Cold run 9153's frames, close up: the pale gutter under each rowhome's
cornice stopped short at every top-floor window bay and started again past
it. `roofline_slots` returned the top storey's WALL slots, and a window is
a slot of its own, so the eave over it had no gutter.
"""
import json
from pathlib import Path

import pytest

from patina import framing, openings, slots, trim

BUILD = Path(__file__).resolve().parents[2] / "deli_counter" / "build"
ROWHOME = BUILD / "gs_empty_rowhome_f.slots.json"


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


@pytest.mark.skipif(not ROWHOME.is_file(), reason="no Deli Counter build beside this repo")
def test_the_front_gutter_runs_the_whole_eave_without_a_gap():
    """FAILS ON 0.25.0: a ~1 m gap over each top-floor window."""
    m = slots.parse(json.loads(ROWHOME.read_text(encoding="utf-8")))
    g = [o for o in framing.gutter_orders(m, _regions(), seed=1999)
         if [round(v) for v in o["normal"][:2]] == [0, -1]]
    spans = sorted((o["pos"][0] - o["size"] / 2.0, o["pos"][0] + o["size"] / 2.0) for o in g)
    assert spans
    reach = spans[0][1]
    for a, b in spans[1:]:
        assert a <= reach + 0.01, f"gap {reach:.3f} .. {a:.3f}"
        reach = max(reach, b)
    assert spans[0][0] == pytest.approx(-3.15, abs=0.02) and reach == pytest.approx(3.15, abs=0.02)


@pytest.mark.skipif(not ROWHOME.is_file(), reason="no Deli Counter build beside this repo")
def test_a_gutter_over_a_window_clears_the_opening():
    """The gutter hangs at the eave, above the window's head: the opening
    keep-out the dressing filter enforces finds nothing to drop."""
    m = slots.parse(json.loads(ROWHOME.read_text(encoding="utf-8")))
    boxes = openings.keep_out_boxes(m)
    g = framing.gutter_orders(m, _regions(), seed=1999)
    assert g and [o for o in g if openings.hits(o, boxes)] == []


def test_a_top_storey_opening_is_part_of_the_roofline_and_a_lower_one_is_not():
    from patina.slots import Slot, SlotManifest

    def s(sid, role, story, x):
        return Slot(slot_id=sid, role=role, current_ref=f"{role}_greybox_01", facing="N",
                    story=story, translation=(x, 6.0, story * 3.1 + 1.55), rot_y=0.0,
                    dims=(2.0 if role == "wall" else 0.95, 0.3, 3.1))
    m = SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                     module_size=2.0, space="spec/Blender Z-up raw coords",
                     slots=[s("ext_0_N_seg0", "wall", 0, -1.0), s("ext_0_N_open0", "window", 0, 1.0),
                            s("ext_1_N_seg0", "wall", 1, -1.0), s("ext_1_N_open0", "window", 1, 1.0)])
    assert sorted(x.slot_id for x in framing.roofline_slots(m)) == ["ext_1_N_open0", "ext_1_N_seg0"]
