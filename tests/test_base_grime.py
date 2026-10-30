"""Grime along a ground storey's base (0.40.0, the factory's roadmap 324).

Zoo (>= 1.154.0) builds a `stain_base` in the wall's own skin and Level Factory (>= 0.271.0) draws it; Patina says
where: along each span of a ground storey's side between its corners and the openings that come down into the band,
one order a span, in the run's wall kind.
"""
import json
import pathlib

from patina import framing, openings, slots

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def _manifest(name):
    return slots.parse(json.loads((FIXTURES / f"stains_{name}.slots.json").read_text(encoding="utf-8")))


def _side_spans(m, key):
    """(a, b, covered) along a side, in the same frame `base_grime_orders` measures."""
    center, thick = slots.footprint_center(m), slots.modal_thickness(m)
    group = [s for s in m.slots if "_".join(str(s.slot_id).split("_")[:3]) == key and s.dims]
    first = group[0]
    along = slots.wall_frame(first, center, thick)[2]
    out = []
    for s in group:
        run = slots.wall_frame(s, center, thick)[0]
        p = ((s.translation[0] - first.translation[0]) * along[0]
             + (s.translation[1] - first.translation[1]) * along[1])
        wall = "glass" not in str(s.material) and s.glazing != "storefront"
        out.append((p - run / 2, p + run / 2,
                    wall and all(o.get("sill", 0.0) >= framing.GRIME_CLEAR for o in s.openings)))
    return sorted(out)


def test_grime_along_every_ground_side_in_the_walls_kind():
    """FAILS ON 0.39.0: no grime."""
    m = _manifest("bank_branch_a02")
    got = framing.base_grime_orders(m, [], seed=1999)
    assert got and all(o["cover"] == "stain_base" for o in got)
    # the run's own kind each side -- the bank's flanks are wood panel at street level -- and never its glass: the
    # street front is a storefront, glass to its foot, and gets none
    assert {o["wall_material"] for o in got} == {"concrete", "wood_panel"}
    assert {"_".join(str(o["slot_id"]).split("_")[:3]) for o in got} == {"ext_0_N", "ext_0_E", "ext_0_W"}
    for o in got:
        width, height = o["size2"]
        assert width >= framing.GRIME_MIN_SPAN and framing.GRIME_H[0] <= height <= framing.GRIME_H[1]


def test_the_band_stands_on_the_storeys_foot_and_on_the_wall():
    m = _manifest("bank_branch_a02")
    feet = {s.base_z() for s in m.slots if str(s.slot_id).startswith("ext_0_")}
    for o in framing.base_grime_orders(m, [], seed=1999):
        assert abs(o["pos"][2] - min(feet)) < 1e-6
        assert abs(sum(c * c for c in o["normal"]) - 1.0) < 1e-6 and o["normal"][2] == 0


def test_a_span_ends_at_every_opening_that_comes_into_the_band():
    """The bank's north side: a breach at 0 m cuts the band in two."""
    m = _manifest("bank_branch_a02")
    got = [o for o in framing.base_grime_orders(m, [], seed=1999) if str(o["slot_id"]).startswith("ext_0_N")]
    spans = _side_spans(m, "ext_0_N")
    covered = sum(b - a for a, b, ok in spans if ok)
    cuts = sum(1 for a, b, ok in spans if not ok)
    assert cuts >= 1
    # every covered metre is under exactly one order, and the orders are fewer than the covered slots
    assert abs(sum(o["size2"][0] for o in got) - covered) < 0.05 + framing.GRIME_MIN_SPAN * len(spans)
    assert len(got) < sum(1 for _a, _b, ok in spans if ok)


def test_one_order_a_span_never_one_a_module():
    m = _manifest("card_shop_a01")
    got = framing.base_grime_orders(m, [], seed=1999)
    modules = [s for s in m.slots if str(s.slot_id).startswith("ext_0_") and s.role == "wall"]
    assert got and len(got) < len(modules)


def test_deterministic_for_a_seed():
    m = _manifest("gas_station_a02")
    assert framing.base_grime_orders(m, [], seed=5) == framing.base_grime_orders(m, [], seed=5)


def test_the_grime_survives_the_keep_out_filter():
    """FAILS WITHOUT `stain_base` IN `openings.EXEMPT`: a span ends at a door's jamb, inside the door's margin."""
    m = _manifest("bank_branch_a02")
    got = framing.base_grime_orders(m, [], seed=1999)
    kept, rep = openings.apply(got, openings.keep_out_boxes(m))
    assert got and len(kept) == len(got) and not rep["dropped"]
