"""A roof that drains through its parapet (0.34.0, the factory's roadmap 324).

Seed 9082's bank hung a white gutter across every facade 1.4 m below its top, under its parapet: a flat roof behind a
parapet drains through a scupper, not into an eave gutter. On a side a parapet stands over, a building that is not an
Empty gets no gutter and its downspouts run to the roof's surface, ordered `head`.
"""
from patina import framing, trim
from patina.slots import Slot, SlotManifest

H, T = 3.6, 0.2


def _slot(sid, side, x, y, story, rot, role="wall", dims=None, glazing=None, openings_=None, z=None):
    return Slot(slot_id=sid, role=role, current_ref=f"{role}_greybox_01", facing=side, story=story,
                translation=(x, y, z if z is not None else story * H + 3.3 / 2.0), rot_y=rot,
                dims=dims or (2.0, 0.3, 3.3), glazing=glazing, openings=openings_ or [])


def _shop(glazing=None, parapet=True):
    """A 6 x 6 m one-storey shop: walls on four sides, a window on each, a roof slab 3.3 -> 3.6, and (when
    `parapet`) a 1.4 m parapet on each side standing on the wall tops (Deli Counter 0.292.0)."""
    slots = []
    for side, (x, y, rot) in {"N": (0, 3.0, 0.0), "S": (0, -3.0, 180.0), "E": (3.0, 0, 90.0),
                              "W": (-3.0, 0, 270.0)}.items():
        for i, a in enumerate((-2.0, 2.0)):
            sx, sy = (a, y) if side in "NS" else (x, a)
            slots.append(_slot(f"ext_0_{side}_seg{i}", side, sx, sy, 0, rot))
        slots.append(_slot(f"ext_0_{side}_open0", side, x, y, 0, rot, role="window", dims=(1.2, 0.3, 3.3),
                           glazing=glazing,
                           openings_=[{"kind": "window", "width": 1.2, "height": 1.4, "sill": 0.9}]))
        if parapet:
            slots.append(_slot(f"parapet_{side}_t0_0", side, x * 1.05, y * 1.05, 1, rot, dims=(6.3, T, 1.4),
                               z=3.3 + 0.7))
    slots.append(Slot(slot_id="roof_footprint", role="roof", current_ref="roof_greybox_01", story=1,
                      translation=(0.0, 0.0, 3.45), dims=(6.0, 6.0, 0.3)))
    return SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                        module_size=2.0, space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def test_a_parapeted_roof_drains_through_scuppers_not_gutters():
    """FAILS ON 0.33.1: a gutter on every side, under the parapet, and no head."""
    m = _shop()
    assert framing.scupper_sides(m) == {(0, 1): 3.6, (0, -1): 3.6, (1, 0): 3.6, (-1, 0): 3.6}
    assert framing.gutter_orders(m, _regions(), seed=1999) == []
    ds = framing.downspout_orders(m, _regions(), seed=1999)
    assert ds and all(o.get("head") for o in ds)
    for o in ds:                                          # from the ground to the roof's surface
        assert abs(o["pos"][2] + o["size"] / 2.0 - 3.6) < 1e-3
        assert abs(o["pos"][2] - o["size"] / 2.0) < 1e-3


def test_without_a_parapet_or_on_an_empty_the_gutter_stays():
    """The controls: no parapet, nothing to drain through; an Empty keeps the gutters the walker asked for."""
    for m in (_shop(parapet=False), _shop(glazing="facade")):
        assert framing.scupper_sides(m) == {}
        assert framing.gutter_orders(m, _regions(), seed=1999)
        assert not any(o.get("head") for o in framing.downspout_orders(m, _regions(), seed=1999))
