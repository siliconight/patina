"""A stain where a roof's water leaves it, and an Empty told apart from a storey nobody reaches (0.41.0).

Zoo (>= 1.153.0) builds a `stain_streak` and Level Factory (>= 0.271.0) draws it; Patina says where: under each
conductor head and in drips under every exposed parapet. And `is_empty`: Deli Counter 0.295.0 paints the windows of a
storey nobody reaches, and "any slot glazed `facade`" read the slice's bank as an Empty -- no scuppers, no string
course, no quoins, a gutter under its parapet. The fixtures are the live builds (Deli Counter 0.295.1), trimmed to their
wall, parapet and roof slots.
"""
import json
import pathlib

from patina import framing, openings, slots

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def _manifest(name):
    return slots.parse(json.loads((FIXTURES / f"runoff_{name}.slots.json").read_text(encoding="utf-8")))


def _orders(name):
    m = _manifest(name)
    ds = framing.downspout_orders(m, [], seed=1999, keep_out=openings.keep_out_boxes(m))
    return m, ds, framing.runoff_orders(m, [], seed=1999, downspouts=ds)


def test_a_storey_nobody_reaches_does_not_make_a_building_an_empty():
    """FAILS ON 0.40.0: the bank, its upper storey painted, read as an Empty."""
    bank = _manifest("bank_branch_a02")
    assert any(s.glazing == "facade" for s in bank.slots)          # its painted upper windows
    # the bank keeps what a civic building carries -- asked first, so 0.40.0 fails on the behaviour, not a name
    assert len(framing.scupper_sides(bank)) == 4
    bands = framing.string_course_orders(bank, [], seed=1999)
    assert bands and framing.quoin_orders(bank, [], seed=1999, bands=bands)
    assert not framing.is_empty(bank)
    assert framing.is_empty(_manifest("gs_empty_rowhome_a"))


def test_a_streak_under_every_conductor_head():
    m, ds, got = _orders("card_shop_a01")
    heads = [d for d in ds if d.get("head")]
    under = [o for o in got if not str(o["slot_id"]).startswith("parapet_")]
    assert heads and len(under) == len(heads)
    for o, d in zip(under, heads):
        assert o["cover"] == "stain_streak" and o["wall_material"] == "brick"
        width, run = o["size2"]
        assert framing.HEAD_WIDE[0] <= width <= framing.HEAD_WIDE[1] and run <= framing.HEAD_RUN[1]
        # centred on its pipe, starting at the head
        assert o["pos"][:2] == d["pos"][:2] and abs(o["pos"][2] - (d["pos"][2] + d["size"] / 2.0)) < 1e-3


def test_drips_under_every_parapet_a_person_sees_and_none_on_a_party_wall():
    _m, _ds, got = _orders("bank_branch_a02")
    drips = [o for o in got if str(o["slot_id"]).startswith("parapet_")]
    assert drips and {o["wall_material"] for o in drips} == {"concrete"}
    for o in drips:
        width, run = o["size2"]
        assert framing.DRIP_WIDE[0] <= width <= framing.DRIP_WIDE[1] and framing.DRIP_RUN[0] <= run <= framing.DRIP_RUN[1]
        assert o["normal"][2] == 0 and abs(sum(c * c for c in o["normal"]) - 1.0) < 1e-6
    # an Empty's party walls carry none: every drip on a rowhome faces its street or its yard
    _m, _ds, row = _orders("gs_empty_rowhome_a")
    assert row and {tuple(o["normal"]) for o in row} <= {(0.0, 1.0, 0.0), (0.0, -1.0, 0.0)}


def test_the_cli_hands_the_gutters_downspouts_to_the_runoff():
    src = (pathlib.Path(framing.__file__).parent / "cli.py").read_text(encoding="utf-8")
    assert "downspouts = []" in src and "panels += downspouts" in src
    assert "framing.runoff_orders(\n                    slot_manifest, regions, seed=args.seed, downspouts=downspouts)" in src
