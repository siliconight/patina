"""An Empty's openings get stone lintels and sills (0.27.0).

The walker's South Philly photograph (the factory root's
`docs/reference/EMPTIES_COMPS.md`, "Window comps"): "white stone lintels and
sills over and under every window". Ordered for every opening on a facade
slot: a lintel over every window and door, a sill under every window. Zoo
(>= 1.71.0) builds them.
"""
import pytest

from patina import framing, openings, trim
from patina.slots import Slot, SlotManifest

WIN = {"kind": "window", "width": 0.95, "height": 1.6, "sill": 0.85}
DOOR = {"kind": "door", "width": 1.0, "height": 2.3, "sill": 0.0}


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def _manifest(glazing="facade"):
    def wall(sid, story, y):
        return Slot(slot_id=sid, role="wall", current_ref="wall_greybox_01", facing="N" if y > 0 else "S",
                    story=story, translation=(-1.5, y, story * 3.1 + 1.55), rot_y=0.0, dims=(2.0, 0.3, 3.1))
    win = Slot(slot_id="ext_1_N_open0", role="window", current_ref="window_greybox_01", facing="N",
               story=1, translation=(0.5, 6.0, 4.65), rot_y=0.0, dims=(0.95, 0.3, 3.1),
               openings=[dict(WIN)], glazing=glazing)
    door = Slot(slot_id="ext_0_N_open0", role="doorway", current_ref="doorway_greybox_01", facing="N",
                story=0, translation=(0.5, 6.0, 1.55), rot_y=0.0, dims=(1.0, 0.3, 3.1),
                openings=[dict(DOOR)], glazing=glazing)
    return SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                        module_size=2.0, space="spec/Blender Z-up raw coords",
                        slots=[wall("ext_0_N_seg0", 0, 6.0), wall("ext_1_N_seg0", 1, 6.0),
                               wall("ext_0_S_seg0", 0, -6.0), wall("ext_1_S_seg0", 1, -6.0), win, door])


def _orders(glazing="facade"):
    return framing.opening_trim_orders(_manifest(glazing), _regions(), seed=1999)


def test_a_window_gets_a_lintel_at_its_head_and_a_sill_at_its_sill():
    """FAILS ON 0.26.0: nothing ordered a lintel or a sill."""
    win = sorted((o["cover"], o["pos"][2]) for o in _orders() if o["slot_id"] == "ext_1_N_open0")
    # base 3.1: the sill line at 3.1 + 0.85, the head at 3.1 + 0.85 + 1.6
    assert win == [("lintel", pytest.approx(5.55)), ("window_sill", pytest.approx(3.95))]


def test_a_door_gets_a_lintel_and_no_sill():
    door = [o for o in _orders() if o["slot_id"] == "ext_0_N_open0"]
    assert [(o["cover"], o["pos"][2]) for o in door] == [("lintel", pytest.approx(2.3))]


def test_they_stand_on_the_wall_face_sized_to_their_opening():
    for o in _orders():
        assert o["pos"][:2] == pytest.approx([0.5, 6.15]) and o["normal"] == [0.0, 1.0, 0.0]
        assert o["size2"][0] == o["size"] and o["collision"] == "none"


def test_a_real_opening_gets_none():
    """The control: the same openings with something behind them."""
    assert _orders(glazing=None) == []


def test_the_keep_out_exempts_them_by_name():
    """A lintel sits on the head and a sill on the sill line, inside the
    opening box's margin; the rule lists them beside the window fixtures."""
    m = _manifest()
    boxes = openings.keep_out_boxes(m)
    orders = framing.opening_trim_orders(m, _regions(), seed=1999)
    assert any(any(openings._overlaps(openings.order_box(o), b) for b in boxes) for o in orders)
    kept, report = openings.apply(orders, boxes)
    assert kept == orders and report["dropped"] == {}
