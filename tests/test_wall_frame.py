"""Which way does a slot face? One answer, for both of DC's conventions.

Deli Counter writes two into one manifest and its own composer says so:

    "each module is oriented by FITTING its footprint to the greybox slot's
     extent instead of trusting the slot's raw rot_y -- walls (world-oriented
     by deli) fit at 0 deg, canonical openings at 90/270."
                                        -- themed_tscn.write_themed_tscn

Patina was never told and applied ``rot_y`` to everything, so every east and
west WALL got rotated twice: its 2 m run read as 0.35 m and its 0.35 m
thickness read as 2 m. 124 of 299 wall slots in the measured building. What
shipped was 35 cm gutter stubs every 2 m, floating 1.0 m off the facade --
``d/2`` of a two-metre "thickness".

The slot records below are copied verbatim from
``category5_baie_dore_001``; that is the point of them.
"""

import pytest

from patina import framing, trim
from patina.slots import Slot, SlotManifest
from patina import slots as S


def _wall(slot_id, rot_y, dims, translation, story=1):
    return Slot(slot_id=slot_id, role="wall", current_ref="wall_greybox_01",
                facing=slot_id.split("_")[2], story=story,
                translation=translation, rot_y=rot_y, dims=dims)


#: Verbatim off the shipped manifest. North is run-first; west is thin-first.
NORTH = _wall("ext_1_N_seg0", 0.0, (2.0, 0.35, 3.7), (-21.0, 16.0, 5.85))
WEST = _wall("ext_1_W_seg0", 270.0, (0.35, 2.0, 3.7), (-22.0, -15.0, 5.85))
EAST = _wall("ext_1_E_seg0", 90.0, (0.35, 2.0, 3.7), (22.0, -15.0, 5.85))
SOUTH = _wall("ext_1_S_seg0", 180.0, (2.0, 0.35, 3.7), (-21.0, -16.0, 5.85))


def _manifest(slots):
    return SlotManifest(version="1.2.0", building_id="t", theme="greybox",
                        module_library="art/zoo", module_size=2.0,
                        space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    _, regions = trim.build_sheet(size=64, seed=1999)
    return regions


BOX = _manifest([NORTH, SOUTH, EAST, WEST])
CENTER = (0.0, 0.0)


# --------------------------------------------------------------------------- #
# The rule
# --------------------------------------------------------------------------- #

def test_thin_first_dims_are_already_world_oriented():
    """The discriminator, and why it needs nothing hard-coded: a wall is long
    on one horizontal axis and thin on the other, and the canonical order is
    (run, thickness). Dims listing the thin axis first have been rotated."""
    assert S.world_oriented(WEST) and S.world_oriented(EAST)
    assert not S.world_oriented(NORTH) and not S.world_oriented(SOUTH)


def test_the_run_is_two_metres_on_every_wall_of_the_box():
    """It read 0.35 on the east and west walls -- the thickness."""
    for w in (NORTH, SOUTH, EAST, WEST):
        run, thick, _along, _out = S.wall_frame(w, CENTER)
        assert (run, thick) == (2.0, 0.35), w.slot_id


def test_the_wall_runs_along_the_axis_its_dims_say():
    assert S.wall_frame(NORTH, CENTER)[2] == (1.0, 0.0)
    assert S.wall_frame(WEST, CENTER)[2] == (0.0, 1.0)


def test_the_outward_normal_points_out_on_all_four_sides():
    """The axis and the side are two independent mistakes; this is the side."""
    assert S.wall_frame(NORTH, CENTER)[3] == pytest.approx((0.0, 1.0))
    assert S.wall_frame(SOUTH, CENTER)[3] == pytest.approx((0.0, -1.0))
    assert S.wall_frame(EAST, CENTER)[3] == pytest.approx((1.0, 0.0))
    assert S.wall_frame(WEST, CENTER)[3] == pytest.approx((-1.0, 0.0))


def test_a_canonical_opening_still_uses_its_rot_y():
    """The other convention, and it must keep working. A west DOORWAY is
    authored run-first at rot 270 -- exactly the record DC emits."""
    door = Slot(slot_id="ext_0_W_open0", role="doorway",
                current_ref="doorway_greybox_01", facing="W",
                translation=(-22.0, 0.0, 1.9), rot_y=270.0,
                dims=(1.2, 0.35, 3.7),
                openings=[{"kind": "door", "width": 1.2, "height": 2.2,
                           "sill": 0.0}])
    run, thick, along, out = S.wall_frame(door, CENTER)
    assert (run, thick) == (1.2, 0.35)
    assert along == pytest.approx((0.0, -1.0))      # runs down the west face
    assert out == pytest.approx((-1.0, 0.0))        # faces the street


def test_wall_thickness_is_not_dims_1():
    assert S.wall_thickness(WEST) == 0.35
    assert S.wall_thickness(NORTH) == 0.35


# --------------------------------------------------------------------------- #
# What it shipped as
# --------------------------------------------------------------------------- #

def test_a_west_gutter_is_a_full_run_on_the_wall_not_a_stub_in_the_air():
    """The measured defect, both halves of it in one assertion.

        ext_1_W_seg0  pos [-23.0, -15.0, 7.62]  size 0.35

    The wall face is at -22.175. A 35 cm bar 0.8 m clear of it, every 2 m.
    """
    o = next(x for x in framing.gutter_orders(BOX, _regions(), seed=1999)
             if x["slot_id"] == "ext_1_W_seg0")
    assert o["size"] == pytest.approx(2.0)              # was 0.35
    assert o["pos"][0] == pytest.approx(-22.175)        # was -23.0
    assert o["pos"][1] == pytest.approx(-15.0)
    assert o["normal"] == [-1.0, 0.0, 0.0]


def test_gutters_abut_along_a_wall_line():
    """Sections join at module seams -- that is what makes a run a run rather
    than a dashed line. Four 2 m modules down the west face, no gaps."""
    walls = [_wall("ext_1_W_seg%d" % i, 270.0, (0.35, 2.0, 3.7),
                   (-22.0, -15.0 + 2.0 * i, 5.85)) for i in range(4)]
    orders = framing.gutter_orders(_manifest(walls), _regions(), seed=1999)
    spans = sorted((o["pos"][1] - o["size"] / 2.0,
                    o["pos"][1] + o["size"] / 2.0) for o in orders)
    for (_a0, a1), (b0, _b1) in zip(spans, spans[1:]):
        assert b0 == pytest.approx(a1)


def test_a_north_wall_is_unchanged_by_all_of_this():
    """Run-first dims at rot 0 were always right and must stay byte-identical,
    or the fix is a second bug wearing the first one's clothes."""
    o = next(x for x in framing.gutter_orders(BOX, _regions(), seed=1999)
             if x["slot_id"] == "ext_1_N_seg0")
    assert o["size"] == pytest.approx(2.0)
    assert o["pos"] == [-21.0, 16.175, 7.62]
    assert o["normal"] == [0.0, 1.0, 0.0]


def test_the_room_inset_uses_the_real_thickness():
    """`_story_wall_depth` took a MAXIMUM of dims[1] over the storey, so one
    east wall reported the building's walls as 2.0 m thick and every room was
    inset by 1.0 m. That is why the intrusion check read 0 on a building whose
    dressing was measurably inside its rooms."""
    from patina import openings
    assert openings._story_wall_depth(BOX, 1) == pytest.approx(0.35)
