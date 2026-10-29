"""A parapet's coping (0.33.0, the factory's roadmap 324).

A parapet's top was capped by the roofline anchors' 2 m `edge_strip`s, 2.5 m
apart with jitter and centred on the wall's outer face: a broken stick half off
the wall. A coping is one piece a run, over the whole wall, overhanging both
faces, and the strips it replaces are dropped.
"""
import pytest

from patina import framing, trim
from patina.slots import Slot, SlotManifest

O = framing.COPING_OVER
T, PH, STORY, BASE = 0.2, 1.1, 2, 7.2      # bank_branch_a02's parapet
HX, HY = 15.0, 11.0                         # its footprint's half-sizes


def _parapet(sid, side, x, y, run, rot):
    return Slot(slot_id=sid, role="wall", current_ref="wall_greybox_01", facing=side,
                story=STORY, translation=(x, y, BASE + PH / 2.0), rot_y=rot,
                dims=(run, T, PH))


def _ring(hx=HX, hy=HY, tiles=3):
    """Deli Counter's parapet ring (`_parapets`): N and S over the full width,
    corners included, E and W between their inner faces, each run in tiles."""
    slots = []
    for side, y, rot in (("N", hy - T / 2.0, 0.0), ("S", -hy + T / 2.0, 180.0)):
        run = 2 * hx / tiles
        for i in range(tiles):
            slots.append(_parapet(f"parapet_{side}_t0_{i}", side, -hx + run * (i + 0.5), y, run, rot))
    ey = 2 * hy - 2 * T
    for side, x, rot in (("E", hx - T / 2.0, 90.0), ("W", -hx + T / 2.0, 270.0)):
        run = ey / tiles
        for i in range(tiles):
            slots.append(_parapet(f"parapet_{side}_t{i}_0", side, x, -ey / 2.0 + run * (i + 0.5), run, rot))
    return slots


def _opening(side, x, y, rot, glazing):
    return Slot(slot_id=f"ext_1_{side}_open0", role="window", current_ref="window_greybox_01",
                facing=side, story=1, translation=(x, y, 5.0), rot_y=rot, dims=(0.95, T, 3.6),
                glazing=glazing, openings=[{"kind": "window", "width": 0.95, "height": 1.6, "sill": 0.85}])


def _manifest(slots):
    return SlotManifest(version="1.3.0", building_id="t", theme="greybox", module_library="art/zoo",
                        module_size=2.0, space="spec/Blender Z-up raw coords", slots=slots)


def _regions():
    return trim.build_sheet(size=64, seed=1999)[1]


def _rect(o):
    length, width = o["size2"]
    hx, hy = (length, width) if o["tangent"][0] else (width, length)
    x, y = o["pos"][:2]
    return (x - hx / 2, x + hx / 2, y - hy / 2, y + hy / 2)


def _overlap(a, b):
    w = min(a[1], b[1]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[2], b[2])
    return max(w, 0.0) * max(h, 0.0)


def test_one_coping_a_run_on_the_parapets_top():
    """FAILS ON 0.32.1: there was no coping."""
    cs = framing.coping_orders(_manifest(_ring()), _regions(), seed=1999)
    assert sorted(o["slot_id"][:9] for o in cs) == ["parapet_E", "parapet_N", "parapet_S", "parapet_W"]
    for o in cs:
        assert o["cover"] == "coping" and o["collision"] == "none"
        assert o["pos"][2] == pytest.approx(BASE + PH)
        assert o["normal"] == [0.0, 0.0, 1.0]
        assert len(o["slot_ids"]) == 3
        assert o["size2"][1] == pytest.approx(T + 2 * O)


def test_the_ring_is_capped_exactly_once_with_both_faces_overhung():
    """The four copings tile the parapet's plan grown by the overhang on both
    faces: no overlap anywhere, and their area is that whole ring's."""
    cs = framing.coping_orders(_manifest(_ring()), _regions(), seed=1999)
    rects = [_rect(o) for o in cs]
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert _overlap(a, b) == pytest.approx(0.0, abs=1e-9)
    outer = (2 * HX + 2 * O) * (2 * HY + 2 * O)
    inner = (2 * HX - 2 * T - 2 * O) * (2 * HY - 2 * T - 2 * O)
    area = sum((r[1] - r[0]) * (r[3] - r[2]) for r in rects)
    assert area == pytest.approx(outer - inner, abs=1e-6)
    assert min(r[0] for r in rects) == pytest.approx(-HX - O)
    assert max(r[3] for r in rects) == pytest.approx(HY + O)


def test_an_empty_does_not_overhang_its_party_walls():
    """An Empty's blank E and W are party walls: nothing crosses x = +-HX,
    where the next house stands. Front and back still overhang."""
    slots = _ring() + [_opening("N", 0.0, HY - T / 2, 0.0, "facade"),
                       _opening("S", 0.0, -HY + T / 2, 180.0, "facade")]
    cs = framing.coping_orders(_manifest(slots), _regions(), seed=1999)
    rects = [_rect(o) for o in cs]
    assert min(r[0] for r in rects) == pytest.approx(-HX)
    assert max(r[1] for r in rects) == pytest.approx(HX)
    assert max(r[3] for r in rects) == pytest.approx(HY + O)
    assert min(r[2] for r in rects) == pytest.approx(-HY - O)
    for i, a in enumerate(rects):
        for b in rects[i + 1:]:
            assert _overlap(a, b) == pytest.approx(0.0, abs=1e-9)


def test_a_building_with_no_parapet_gets_no_coping():
    assert framing.coping_orders(_manifest([_opening("N", 0.0, 5.0, 0.0, None)]),
                                 _regions(), seed=1999) == []


def test_a_parapet_tile_turned_against_its_side_refuses():
    bad = _ring()
    bad[0] = _parapet("parapet_N_t0_0", "N", -10.0, HY - T / 2, 10.0, 90.0)
    with pytest.raises(ValueError):
        framing.coping_orders(_manifest(bad), _regions(), seed=1999)


def _strip(x, y, z):
    return {"cover": "edge_strip", "pos": [x, y, z], "normal": [0.0, 0.0, 1.0]}


def test_the_roofline_strips_on_a_coped_parapet_are_dropped():
    """FAILS ON 0.32.1: the strips stayed. One on the parapet's top is the cap
    the coping replaces; one well below it, or off the parapet, is not."""
    cs = framing.coping_orders(_manifest(_ring()), _regions(), seed=1999)
    top = BASE + PH
    on = [_strip(-HX, 9.5, top), _strip(3.0, HY, top), _strip(HX, -HY + 0.05, top)]
    off = [_strip(-HX, 9.5, top - 3.0), _strip(40.0, 0.0, top), _strip(0.0, 0.0, top)]
    kept, dropped = framing.drop_capped_edge_strips(cs + on + off)
    assert dropped == 3
    assert [o for o in kept if o["cover"] == "edge_strip"] == off
    assert framing.drop_capped_edge_strips(on) == (on, 0)


def test_the_dressing_manifest_reports_what_it_superseded():
    cs = framing.coping_orders(_manifest(_ring()), _regions(), seed=1999)
    regions = _regions()
    dm = trim.dressing_manifest([], regions, seed=1999, source="t.glb", sheet_file="t.png",
                                space="spec/Blender Z-up raw coords",
                                extra_orders=cs + [_strip(-HX, 0.0, BASE + PH)])
    assert dm["counts"] == {"coping": 4}
    assert dm["superseded"] == {"edge_strip": 1}
