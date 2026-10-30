"""A stain where water runs down a wall, below every exterior window's sill (0.39.0, the factory's roadmap 324).

Zoo (>= 1.153.0) builds a `stain_streak` in the wall's own skin and Level Factory (>= 0.271.0) draws it; Patina says
where: under each exterior window with a sill, in the WALL RUN's kind (a window slot's own material is its pane's),
split into streaks under a wide sill, and never across a door's lane.
"""
import json
import pathlib

import pytest

from patina import framing, slots

#: Deli Counter 0.294.0's built slots for three of the vertical slice's buildings, cut to their exterior slots (what
#: `stain_orders` reads; the centre and wall thickness come from the same walls)
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def _manifest(name):
    return slots.parse(json.loads((FIXTURES / f"stains_{name}.slots.json").read_text(encoding="utf-8")))


def test_a_stain_below_every_exterior_window_in_the_walls_kind():
    """FAILS ON 0.38.1: no stains, and a slot carried no material."""
    m = _manifest("bank_branch_a02")
    got = framing.stain_orders(m, [], seed=1999)
    assert got and all(o["cover"] == "stain_streak" for o in got)
    assert {o["wall_material"] for o in got} == {"concrete"}               # the run's wall, never its glass
    windows = {s.slot_id: s for s in m.slots if s.role == "window" and str(s.slot_id).startswith("ext_")}
    assert {o["slot_id"] for o in got} <= set(windows)
    for o in got:
        s = windows[o["slot_id"]]
        sill = min(float(op["sill"]) for op in s.openings)
        assert o["pos"][2] == pytest.approx(s.base_z() + sill - framing.STAIN_BELOW_SILL, abs=1e-3)
        assert o["pos"][2] - o["size2"][1] >= s.base_z()                    # never past the storey's foot


def test_a_storefront_run_takes_its_wall_kind_not_its_glass():
    for name in ("card_shop_a01", "gas_station_a02"):
        got = framing.stain_orders(_manifest(name), [], seed=1)
        assert got and not any("glass" in o["wall_material"] for o in got), name


def test_a_wide_sill_sheds_in_separate_streaks():
    got = framing.stain_orders(_manifest("card_shop_a01"), [], seed=1)
    assert max(o["size2"][0] for o in got) <= framing.STAIN_STREAK_MAX + 1e-9
    per = {}
    for o in got:
        per[o["slot_id"]] = per.get(o["slot_id"], 0) + 1
    assert max(per.values()) > 1


def test_deterministic_for_a_seed():
    m = _manifest("bank_branch_a02")
    assert framing.stain_orders(m, [], seed=5) == framing.stain_orders(m, [], seed=5)
    assert framing.stain_orders(m, [], seed=5) != framing.stain_orders(m, [], seed=6)


def test_the_stains_survive_the_keep_out_filter():
    """FAILS WITHOUT `stain_streak` IN `openings.EXEMPT`: slice 17's first build shipped no stain -- every one hangs
    inside its own window's margin, and the dressing's keep-out filter dropped all 16 on the bank."""
    from patina import openings
    m = _manifest("bank_branch_a02")
    got = framing.stain_orders(m, [], seed=1999)
    boxes = openings.keep_out_boxes(m)
    kept, rep = openings.apply(got, boxes)
    assert got and len(kept) == len(got) and not rep["dropped"]
