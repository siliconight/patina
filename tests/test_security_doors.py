"""An Empty's iron security door (0.28.0).

Deli Counter (>= 0.182.0) writes `security_door: true` on a facade front
door's slot; this orders it for Zoo (>= 1.72.0) to build, in the doorway's
reveal. Only on a facade doorway: a real door is a way in.
"""
import pytest

from patina import framing, openings, slots, trim
from patina.slots import Slot, SlotManifest

DOOR = {"kind": "door", "width": 1.0, "height": 2.3, "sill": 0.0}


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def _manifest(**door):
    def wall(sid, story, y):
        return Slot(slot_id=sid, role="wall", current_ref="wall_greybox_01", facing="N" if y > 0 else "S",
                    story=story, translation=(-1.5, y, story * 3.1 + 1.55), rot_y=0.0, dims=(2.0, 0.3, 3.1))
    d = Slot(slot_id="ext_0_N_open0", role="doorway", current_ref="doorway_greybox_01", facing="N",
             story=0, translation=(0.5, 6.0, 1.55), rot_y=0.0, dims=(1.0, 0.3, 3.1),
             openings=[dict(DOOR)], **door)
    return SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                        module_size=2.0, space="spec/Blender Z-up raw coords",
                        slots=[wall("ext_0_N_seg0", 0, 6.0), wall("ext_0_S_seg0", 0, -6.0), d])


def _orders(**door):
    return framing.door_fixture_orders(_manifest(**door), _regions(), seed=1999)


def test_parse_reads_the_security_door():
    """FAILS ON 0.27.0: the slot model dropped `security_door`."""
    raw = {"slots": [{"slot_id": "d", "role": "doorway", "glazing": "facade", "security_door": True,
                      "fit": {"dims": [1.0, 0.3, 3.1], "openings": [DOOR]}}]}
    assert slots.parse(raw).slots[0].security_door is True


def test_a_secured_front_door_orders_one_at_the_opening_s_centre():
    (o,) = _orders(glazing="facade", security_door=True)
    assert o["cover"] == "security_door" and o["slot_id"] == "ext_0_N_open0"
    assert o["pos"] == pytest.approx([0.5, 6.15, 1.15]) and o["normal"] == [0.0, 1.0, 0.0]
    assert o["size2"] == [1.0, 2.3]


def test_a_real_door_or_an_unsecured_one_orders_none():
    assert _orders(glazing=None, security_door=True) == []
    assert _orders(glazing="facade") == []


def test_it_is_exempt_from_the_keep_out_beside_the_others():
    m = _manifest(glazing="facade", security_door=True)
    boxes = openings.keep_out_boxes(m)
    orders = framing.door_fixture_orders(m, _regions(), seed=1999)
    assert orders and all(any(openings._overlaps(openings.order_box(o), b) for b in boxes) for o in orders)
    kept, report = openings.apply(orders, boxes)
    assert kept == orders and report["dropped"] == {}
