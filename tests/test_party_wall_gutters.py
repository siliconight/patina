"""No gutter on an Empty's party wall (0.29.1).

Roadmap 184. Patina hung a gutter under every top-storey roofline, an Empty's
party walls included. Between two houses of one height that gutter was hidden;
beside a lower neighbour it stood exposed and, lit against an unlit wall, read
as lines floating in the sky (cold runs 9160 and 9161). A rowhouse roof drains
front and back, and the downspouts already keep to faces with openings.
"""
from patina import framing, trim
from patina.slots import Slot, SlotManifest

H = 3.1


def _wall(sid, side, x, y, story, rot, role="wall", openings_=None, dims=None, glazing=None):
    return Slot(slot_id=sid, role=role, current_ref=f"{role}_greybox_01", facing=side,
                story=story, translation=(x, y, story * H + H / 2.0), rot_y=rot,
                dims=dims or (2.0, 0.3, H), openings=openings_ or [], glazing=glazing)


def _house(glazing):
    """A 6 x 12 m two-storey house: walls on four sides, a window front (S)
    and back (N) on the top storey -- `glazing` on them -- and the long E/W
    faces blank, as an Empty's party walls are."""
    slots = []
    for st in range(2):
        for i in range(3):
            x = -2.0 + 2.0 * i
            slots.append(_wall(f"ext_{st}_N_seg{i}", "N", x, 6.0, st, 0.0))
            slots.append(_wall(f"ext_{st}_S_seg{i}", "S", x, -6.0, st, 180.0))
        for i in range(6):
            y = -5.0 + 2.0 * i
            slots.append(_wall(f"ext_{st}_E_seg{i}", "E", 3.0, y, st, 90.0))
            slots.append(_wall(f"ext_{st}_W_seg{i}", "W", -3.0, y, st, 270.0))
    for side, (y, rot) in {"N": (6.0, 0.0), "S": (-6.0, 180.0)}.items():
        slots.append(_wall(f"ext_1_{side}_open0", side, 0.0, y, 1, rot, role="window",
                           dims=(0.95, 0.3, H), glazing=glazing,
                           openings_=[{"kind": "window", "width": 0.95, "height": 1.6, "sill": 0.85}]))
    return SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                        module_size=2.0, space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def _faces(orders):
    return {(o["normal"][0], o["normal"][1]) for o in orders}


def test_an_empty_hangs_gutters_only_on_its_faces_with_openings():
    """FAILS ON 0.29.0: the party walls carried them too."""
    g = framing.gutter_orders(_house("facade"), _regions(), seed=1999)
    assert _faces(g) == {(0.0, 1.0), (0.0, -1.0)}


def test_a_free_standing_building_keeps_a_gutter_on_every_face():
    """The control: no slot is a facade, so a blank face is not a party wall."""
    g = framing.gutter_orders(_house(None), _regions(), seed=1999)
    assert _faces(g) == {(0.0, 1.0), (0.0, -1.0), (1.0, 0.0), (-1.0, 0.0)}


def test_an_empty_s_downspouts_hang_from_its_gutters():
    m = _house("facade")
    gutters = _faces(framing.gutter_orders(m, _regions(), seed=1999))
    pipes = _faces(framing.downspout_orders(m, _regions(), seed=1999))
    assert pipes and pipes <= gutters
