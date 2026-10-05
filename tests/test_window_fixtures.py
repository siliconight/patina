"""An Empty's window fixtures: bars and air conditioners (0.26.0).

Deli Counter (>= 0.181.0) writes what hangs in each sealed window on its slot
-- `bars` on a barred pane, `ac` for a unit -- and this orders them for Zoo
(>= 1.69.0) to build: bars over the opening, a unit standing on the sill.
Only on a facade window: a real window is a firing line, and bars a bullet
passes through would lie about it.
"""
import glob
import json
from pathlib import Path

import pytest

from patina import framing, openings, slots, trim
from patina.slots import Slot, SlotManifest

BUILD = Path(__file__).resolve().parents[2] / "deli_counter" / "build"
OPENING = {"kind": "window", "width": 0.95, "height": 1.6, "sill": 0.85}


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def _manifest(**window):
    """A two-storey front at y = +6 and back at y = -6, so the footprint's
    centre -- and so which way is out -- is between them; one window on the
    front's upper storey carrying ``window``'s fields."""
    def wall(sid, story, y):
        return Slot(slot_id=sid, role="wall", current_ref="wall_greybox_01", facing="N" if y > 0 else "S",
                    story=story, translation=(-1.5, y, story * 3.1 + 1.55), rot_y=0.0, dims=(2.0, 0.3, 3.1))
    w = Slot(slot_id="ext_1_N_open0", role="window", current_ref="window_greybox_01", facing="N",
             story=1, translation=(0.5, 6.0, 4.65), rot_y=0.0, dims=(0.95, 0.3, 3.1),
             openings=[dict(OPENING)], **window)
    return SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                        module_size=2.0, space="spec/Blender Z-up raw coords",
                        slots=[wall("ext_0_N_seg0", 0, 6.0), wall("ext_1_N_seg0", 1, 6.0),
                               wall("ext_0_S_seg0", 0, -6.0), wall("ext_1_S_seg0", 1, -6.0), w])


def _orders(**window):
    return framing.window_fixture_orders(_manifest(**window), _regions(), seed=1999)


def test_parse_reads_what_hangs_in_a_window():
    """FAILS ON 0.25.1: the slot model dropped `glazing`, `pane`, `ac` and `bars`."""
    raw = {"slots": [{"slot_id": "w", "role": "window", "glazing": "facade", "pane": "dark_bars",
                      "bars": True, "fit": {"dims": [0.95, 0.3, 3.1], "openings": [OPENING]}},
                     {"slot_id": "x", "role": "window", "fit": {"dims": [0.95, 0.3, 3.1]}}]}
    a, b = slots.parse(raw).slots
    assert (a.glazing, a.pane, a.bars, a.ac) == ("facade", "dark_bars", True, False)
    assert (b.glazing, b.pane, b.bars, b.ac) == (None, None, False, False)


def test_a_barred_window_orders_bars_over_its_opening():
    (o,) = _orders(glazing="facade", pane="dark_bars", bars=True)
    assert o["cover"] == "window_bars" and o["slot_id"] == "ext_1_N_open0"
    # the opening's centre on the wall's outer face: base 3.1 + sill 0.85 +
    # half of 1.6; the face 0.15 out from the wall's centre line at y = 6
    assert o["pos"] == pytest.approx([0.5, 6.15, 4.75])
    assert o["normal"] == [0.0, 1.0, 0.0]
    assert o["size2"] == [0.95, 1.6] and o["collision"] == "none"


def test_a_unit_stands_on_the_sill():
    (o,) = _orders(glazing="facade", pane="dark", ac=True)
    assert o["cover"] == "ac_unit"
    assert o["pos"] == pytest.approx([0.5, 6.15, 3.95])
    assert o["size2"] == [0.95, 1.6]


def test_a_window_that_is_not_an_empty_s_orders_nothing():
    """The control: the same fields on a window with something behind it."""
    assert _orders(glazing=None, ac=True, bars=True) == []
    assert _orders(glazing="facade", pane="dark") == []


def test_the_keep_out_is_what_they_are_exempt_from():
    """They stand IN the opening, so its keep-out box holds them -- and the
    rule exempts them by name, as it does a frame. Without the exemption the
    filter would drop every one."""
    m = _manifest(glazing="facade", pane="dark_bars", bars=True, ac=True)
    boxes = openings.keep_out_boxes(m)
    orders = framing.window_fixture_orders(m, _regions(), seed=1999)
    assert {o["cover"] for o in orders} == {"window_bars", "ac_unit"}
    for o in orders:
        assert any(openings._overlaps(openings.order_box(o), b) for b in boxes), o["cover"]
        assert openings.hits(o, boxes) == []
    kept, report = openings.apply(orders, boxes)
    assert kept == orders and report["dropped"] == {}


@pytest.mark.skipif(not glob.glob(str(BUILD / "gs_empty_rowhome_*.slots.json")),
                    reason="no Deli Counter build beside this repo")
def test_the_built_rowhomes_get_one_order_per_fixture():
    for f in sorted(glob.glob(str(BUILD / "gs_empty_rowhome_*.slots.json"))):
        raw = json.loads(Path(f).read_text(encoding="utf-8"))
        m = slots.parse(raw)
        orders = framing.window_fixture_orders(m, _regions(), seed=1999)
        wins = [s for s in raw["slots"] if s.get("role") == "window"]
        assert sum(1 for o in orders if o["cover"] == "window_bars") == sum(1 for s in wins if s.get("bars")), f
        assert sum(1 for o in orders if o["cover"] == "ac_unit") == sum(1 for s in wins if s.get("ac")), f
