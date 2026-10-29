"""Quoins up a civic building's corners (0.38.0, the factory's roadmap 324).

The slice's bank read as a two-storey commercial box. Dressed stone blocks at its outside corners, alternately long and
short on the two faces, closed round each corner by the bands' rule and kept clear of the bands themselves.
"""
import pytest

from patina import framing, trim
from patina.slots import SlotManifest
from tests.test_string_courses import _block, _regions  # noqa: F401  (the string courses' own fixture)


def _named(m, bid):
    return SlotManifest(version=m.version, building_id=bid, theme=m.theme, module_library=m.module_library,
                        module_size=m.module_size, space=m.space, slots=m.slots)


def test_a_bank_carries_quoins_and_a_shop_does_not():
    """FAILS ON 0.37.0: no quoins."""
    m = _block(storeys=2)
    bands = framing.string_course_orders(m, _regions(), seed=1999)
    bank = framing.quoin_orders(_named(m, "bank_branch_a02"), _regions(), seed=1999, bands=bands)
    assert bank and all(o["cover"] == "string_course" and o["anchor_kind"] == "quoin" for o in bank)
    assert framing.quoin_orders(_named(m, "card_shop_a01"), _regions(), seed=1999, bands=bands) == []


def test_blocks_alternate_close_their_corners_and_keep_clear_of_the_bands():
    m = _block(storeys=2)
    bands = framing.string_course_orders(m, _regions(), seed=1999)
    q = framing.quoin_orders(_named(m, "bank_branch_a02"), _regions(), seed=1999, bands=bands)
    face = 3.15                                                        # the fixture's walls' outer faces
    ne = [o for o in q if o["slot_id"].startswith("quoin_11_")]
    by_level = {}
    for o in ne:
        by_level.setdefault(o["pos"][2], []).append(o)
    lens = []
    for zc, pair in sorted(by_level.items()):
        n = next(o for o in pair if o["normal"][1] > 0.5)
        e = next(o for o in pair if o["normal"][0] > 0.5)
        assert n["pos"][0] + n["size2"][0] / 2 == pytest.approx(face + framing._BAND_PROUD)   # wraps the corner
        assert e["pos"][1] + e["size2"][0] / 2 == pytest.approx(face - framing._BAND_INTO)    # stops at its back
        lens.append(round(n["size2"][0], 3))
        for b in bands:                                                 # never across a band
            assert abs(zc - b["pos"][2]) >= (framing.QUOIN_H + b["size2"][1]) / 2
    # long and short on the N face, by course: a course skipped at a band breaks strict neighbour alternation, so
    # what is held is that both lengths stand at the corner, each with its wrap
    assert set(lens) == {round(framing.QUOIN_LONG + framing._BAND_PROUD, 3),
                         round(framing.QUOIN_SHORT + framing._BAND_PROUD, 3)}
