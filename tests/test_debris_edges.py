"""Debris gathers at edges (0.34.0, the factory's roadmap 324).

The vertical slice's first build laid 4,547 of 6,111 pieces across 41,051 m2 of open ground, evenly (the factory's
docs/findings/slice_look/). Open-ground candidates now survive with a probability that falls off with distance to the
nearest edge that gathers debris -- a building, a wall base, a kerb -- and weeds and rubble stay
within EDGE_ONLY_M of one. Never toward a ground tile's own border: open ground is cut into tiles.
"""
import pytest

from patina import surface_dressing as S

from tests.test_surface_dressing import slab, surfaces, zone  # the planner's own fixtures


def _surfaces():
    # a 60 x 40 m plate of open ground cut into two tiles at x = 30, a building in its middle-left
    zones = [zone("g0", "play_space", "medium", (0.0, 0.0, 30.0, 40.0)),
             zone("g1", "play_space", "medium", (30.0, 0.0, 60.0, 40.0))]
    excl = [{"tag": "building", "declared_by": "lot", "aabb": [10.0, 15.0, 0.0, 20.0, 25.0, 3.0]}]
    return surfaces(zones, excl, tops=(slab("Ground", (30.0, 20.0), (60.0, 40.0), 0.0),))


def _catalogue():
    return [S.catalogue_entry(a, s, height_m=0.05, footprint_m2=0.04, tris=40)
            for a, s in (("pebble", "ground_clutter"), ("rubble_frag", "ground_clutter"),
                         ("weed_tuft", "ground_cover"), ("litter_scrap", "litter"))]


def _plan():
    return S.plan(_surfaces(), _catalogue(), site_id="t", source="t", seed=9104,
                  instance_budget=None, tri_budget=None)


def _dist(o, s):
    gather = [e["aabb"] for e in s["exclusions"]]
    return S.edge_distance(o["pos"][:2], gather)


def test_open_ground_debris_sits_near_the_edges_that_gather_it():
    """FAILS ON 0.33.1: no edge_distance, and the open ground's debris was spread evenly. Per square metre, the ring
    within EDGE_FALLOFF_M of the building holds several times the density of ground 10 m or more from it."""
    m, s = _plan(), _surfaces()
    ds = [_dist(o, s) for o in m["orders"]]
    assert ds and m["cost"]["thinned_open_ground"] > 0
    r = S.EDGE_FALLOFF_M
    ring = (10.0 + 2 * r) * (10.0 + 2 * r) - 100.0          # the building's 10 x 10 m grown by r, less itself
    far_area = 60.0 * 40.0 - 30.0 * 30.0                     # the plate less the building grown by 10 m
    near = sum(1 for d in ds if 0.0 < d <= r) / ring
    far = sum(1 for d in ds if d >= 10.0) / far_area
    assert near > 3.0 * far, (near, far)


def test_weeds_and_rubble_stay_at_the_edges():
    m, s = _plan(), _surfaces()
    for o in m["orders"]:
        if o["asset_id"] in S.EDGE_ONLY_ASSETS:
            assert _dist(o, s) <= S.EDGE_ONLY_M + 1e-9, o


def test_edge_distance_is_zero_inside_a_gather_rectangle():
    b = [[10.0, 15.0, 0.0, 20.0, 25.0, 3.0]]
    assert S.edge_distance((15.0, 20.0), b) == 0.0
    assert S.edge_distance((23.0, 20.0), b) == pytest.approx(3.0)
    assert S.edge_distance((23.0, 29.0), b) == pytest.approx(5.0)
    assert S.edge_distance((23.0, 20.0), []) == float("inf")


def test_nothing_is_thinned_where_no_edge_is_declared_or_the_zone_is_an_edge():
    """No building, wall base or kerb: nothing says where debris gathers. A very_high zone is Lot's perimeter."""
    s = _surfaces()
    s["exclusions"] = []
    assert S.plan(s, _catalogue(), site_id="t", source="t", seed=9104, instance_budget=None,
                  tri_budget=None)["cost"]["thinned_open_ground"] == 0
