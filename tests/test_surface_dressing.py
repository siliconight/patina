"""Layer 3 planning: both gates, and the cost model that was missing from them.

The gates are enforced when the plan is MADE, not when it is validated. A
planner that emits an illegal placement and leaves a downstream gate to catch
it has produced a plan that cannot ship and spent the whole pipeline finding
out. So these tests check the refusals as hard as they check the placements,
and every gate is falsified by constructing the case it is supposed to stop.
"""
from __future__ import annotations

import math

import pytest

from patina import surface_dressing as SD


STEP_MAX = 0.11716          # lot/site_steps.unassisted_step_max_m(0.4, 45)


def capsule():
    return {"radius_m": 0.4, "floor_max_angle_deg": 45.0,
            "unassisted_step_max_m": STEP_MAX,
            "source": "lot/site_steps.py:unassisted_step_max_m"}


def bands():
    return {"micro": {"min_m": 0.02, "max_m": 0.10},
            "low": {"min_m": 0.10, "max_m": 0.30},
            "medium": {"min_m": 0.30, "max_m": 0.70},
            "tall": {"min_m": 0.70, "max_m": 1.50}}


def zone(zid, exposure, density, rect, *, traversed=True, kind="ground"):
    return {"surface_zone_id": zid, "declared_by": "lot", "kind": kind,
            "traversed": traversed,
            "aabb": [rect[0], rect[1], 0.0, rect[2], rect[3], STEP_MAX],
            "tags": [], "exposure_class": exposure,
            "surface_visibility": SD_VIS[exposure], "density": density}


SD_VIS = {"gameplay_path": 0.90, "play_space": 0.70,
          "environmental_edge": 0.45, "decorative": 0.0}


def slab(name, centre, size, top, *, yaw=0.0, family="ground"):
    return {"name": name, "family": family, "centre": list(centre),
            "size": list(size), "yaw_deg": yaw, "top_m": top}


#: Every fixture stands on a plate big enough for all of them, at z 0, unless
#: a test says otherwise -- so the tests that are about budgets and gates are
#: not also about height.
PLATE = slab("Ground", (0.0, 0.0), (1000.0, 1000.0), 0.0)


def surfaces(zones, exclusions=(), tops=(PLATE,)):
    return {"space": SD.SPACE, "capsule": capsule(), "bands": bands(),
            "zones": list(zones), "exclusions": list(exclusions),
            "tops": list(tops), "tops_rule": SD.TOPS_RULE}


def small():
    return surfaces([
        zone("path", "gameplay_path", "low", (-10, -10, 10, 10)),
        zone("edge", "environmental_edge", "very_high", (10, -10, 40, 10)),
    ])


def cat(asset_id="pebble", asset_set="ground_clutter", **kw):
    base = dict(height_m=0.06, footprint_m2=0.03, tris=100)
    base.update(kw)
    return SD.catalogue_entry(asset_id, asset_set, **base)


def plan(surf=None, catalogue=None, **kw):
    kw.setdefault("site_id", "t")
    kw.setdefault("source", "t.tscn")
    kw.setdefault("seed", 1999)
    # `is None`, not `or`: an EMPTY catalogue is a real input that must raise,
    # and `or` would have quietly substituted the default for it.
    return SD.plan(surf if surf is not None else small(),
                   [cat()] if catalogue is None else catalogue, **kw)


# --- the catalogue refuses to guess ----------------------------------------

def test_opaque_occlusion_is_a_fact_and_needs_no_argument():
    assert cat()["occlusion"] == 1.0


def test_a_cutout_asset_must_declare_what_it_actually_hides():
    with pytest.raises(SD.PlanError) as e:
        SD.catalogue_entry("grass", "ground_cover", height_m=0.08,
                           footprint_m2=0.01, tris=22,
                           transparency="alpha_cutout")
    assert "occlusion" in str(e.value)


def test_a_cutout_asset_is_accepted_once_it_declares_it():
    c = SD.catalogue_entry("grass", "ground_cover", height_m=0.08,
                           footprint_m2=0.01, tris=22,
                           transparency="alpha_cutout", occlusion=0.4)
    assert c["occlusion"] == 0.4


def test_an_asset_with_no_triangle_count_is_refused():
    with pytest.raises(SD.PlanError):
        SD.catalogue_entry("x", "s", height_m=0.05, footprint_m2=0.01, tris=0)


# --- gate 1: the honesty rule ----------------------------------------------

def test_a_too_tall_asset_is_refused_in_traversed_space():
    tall = cat(asset_id="boulder", height_m=0.30)
    out = plan(catalogue=[tall])
    assert out["orders"] == []
    codes = {e["code"] for e in out["keep_out"]["entries"]}
    assert SD.CODE_TOO_TALL in codes


def test_the_same_asset_is_allowed_where_nobody_walks():
    """Falsification. If height alone refused it, the rule would be about
    height rather than about the promise the height makes."""
    tall = cat(asset_id="boulder", height_m=0.30)
    surf = surfaces([zone("ledge", "environmental_edge", "very_high",
                          (0, 0, 40, 40), traversed=False, kind="ledge")])
    out = plan(surf, [tall])
    assert out["orders"], "a tall asset off the walkable surface is legal"
    assert all(o["in_traversed_space"] is False for o in out["orders"])


def test_scaling_past_the_limit_is_refused_too():
    """The gate reads the MEASURED height after scale, not the base height."""
    out = plan(catalogue=[cat(height_m=STEP_MAX * 0.95)],
               scale_range=(1.0, 3.0))
    assert any(e["code"] == SD.CODE_TOO_TALL
               for e in out["keep_out"]["entries"])
    for o in out["orders"]:
        assert o["height_m"] <= STEP_MAX


def test_every_placement_clears_the_honesty_rule():
    out = plan()
    for o in out["orders"]:
        assert not (o["in_traversed_space"] and o["height_m"] > STEP_MAX
                    and o["collision_policy"] == "none")


def test_the_refusal_says_why_and_names_the_numbers():
    out = plan(catalogue=[cat(height_m=0.30)])
    why = out["keep_out"]["entries"][0]["why"]
    assert "0.117" in why and "traversal" in why


# --- gate 2: the visibility budget ------------------------------------------

def test_no_zone_is_occluded_past_its_budget():
    out = plan()
    for zid, spent in SD.coverage_by_zone(out).items():
        z = next(z for z in out["zones"] if z["surface_zone_id"] == zid)
        assert spent <= 1.0 - z["surface_visibility"] + 1e-9


def test_audit_catches_a_manifest_that_overspends():
    """Falsification: the audit must be able to fail, so hand it one."""
    out = plan()
    assert SD.audit(out) == []
    out["orders"][0]["coverage_contribution"] = 9.0
    codes = {f["code"] for f in SD.audit(out)}
    assert SD.CODE_BUDGET in codes


def test_audit_catches_collision_on_a_dressing_order():
    out = plan()
    out["orders"][0]["collision_policy"] = "convex"
    assert any(f["code"] == "DRESS_HAS_COLLISION" for f in SD.audit(out))


def test_audit_recomputes_instead_of_trusting_the_planner():
    """coverage_by_zone must read the orders. If it read a stored total, this
    mutation would be invisible."""
    out = plan()
    before = sum(SD.coverage_by_zone(out).values())
    out["orders"] = out["orders"][:1]
    assert sum(SD.coverage_by_zone(out).values()) < before


# --- gate 3: cost, which the other two never bounded ------------------------

def test_an_unbounded_plan_is_enormous_and_says_so():
    """The measurement that put this gate here. On the real site, coverage
    alone authorised 361,412 placements and 46.8M triangles -- every one
    legal, every other gate green."""
    free = plan(instance_budget=None, tri_budget=None)
    held = plan()
    assert len(free["orders"]) > len(held["orders"]) * 5
    assert any(e["code"] == SD.CODE_UNBOUNDED
               for e in free["keep_out"]["entries"])


def test_the_instance_budget_binds():
    out = plan(instance_budget=40, tri_budget=None)
    assert out["cost"]["instances"] <= 40 + len(out["zones"])
    assert any(e["code"] == SD.CODE_INSTANCE_BUDGET
               for e in out["keep_out"]["entries"])


def test_the_triangle_budget_binds():
    out = plan(instance_budget=None, tri_budget=3000)
    assert out["cost"]["tris_total"] <= 3000 + 100 * len(out["zones"])
    assert any(e["code"] == SD.CODE_TRI_BUDGET
               for e in out["keep_out"]["entries"])


def test_cost_reports_unique_meshes_because_that_is_the_draw_calls():
    out = plan(catalogue=[cat(asset_id="a"), cat(asset_id="b")])
    assert out["cost"]["unique_meshes"] <= 2
    assert out["cost"]["instances"] == len(out["orders"])


def test_budget_is_shared_by_area_not_by_zone_count():
    """The bug this replaced: a per-zone cap made a site's density depend on
    how many boxes its paths were chopped into, and the site came out densest
    exactly where the guide says it should be sparsest."""
    chopped = surfaces(
        [zone(f"path{i}", "gameplay_path", "low",
              (i * 4 - 40, -2, i * 4 - 36, 2)) for i in range(20)]
        + [zone("edge", "environmental_edge", "very_high", (10, 10, 60, 60))])
    out = plan(chopped, [cat()])
    per = {}
    for o in out["orders"]:
        per[o["surface_zone_id"]] = per.get(o["surface_zone_id"], 0) + 1
    edge = per.get("edge", 0)
    paths = sum(v for k, v in per.items() if k.startswith("path"))
    assert edge > paths, (
        f"20 chopped path boxes took {paths} instances and the big edge zone "
        f"took {edge}; the split is deciding the density")


# --- the reading the guide asks for ----------------------------------------

def test_edges_are_denser_than_routes_per_square_metre():
    surf = surfaces([zone("path", "gameplay_path", "low", (-20, -20, 20, 20)),
                     zone("edge", "environmental_edge", "very_high",
                          (20, -20, 60, 20))])
    out = plan(surf, [cat()])
    area = 40.0 * 40.0
    per = {"path": 0, "edge": 0}
    for o in out["orders"]:
        per[o["surface_zone_id"]] += 1
    assert per["edge"] / area > per["path"] / area


def test_every_placement_names_a_cause():
    for o in plan()["orders"]:
        assert o["anchor_cause"]


def test_causes_are_not_all_the_same_value():
    """A cause that never varies is not a cause. The first version listed
    `ground` in the kind table, which shadowed the exposure lookup and
    collapsed a whole site to two values."""
    surf = surfaces([
        zone("path", "gameplay_path", "low", (-20, -20, 0, 20)),
        zone("edge", "environmental_edge", "very_high", (0, -20, 30, 20)),
        zone("wall", "environmental_edge", "high", (30, -20, 50, 20),
             kind="wall_base"),
    ])
    causes = {o["anchor_cause"] for o in plan(surf, [cat()])["orders"]}
    assert len(causes) >= 3, causes


def test_cleared_exclusions_records_what_was_tested():
    """The schema says an empty array means untested, not clean."""
    ex = [{"tag": "spawn", "declared_by": "lot", "pos": [0, 0, 0],
           "radius_m": 3.0}]
    out = plan(surfaces([zone("edge", "environmental_edge", "very_high",
                              (-30, -30, 30, 30))], ex), [cat()])
    assert out["orders"]
    for o in out["orders"]:
        assert o["cleared_exclusions"] == ["spawn"]


def test_placements_keep_out_of_exclusions():
    ex = [{"tag": "spawn", "declared_by": "lot", "pos": [0, 0, 0],
           "radius_m": 8.0}]
    out = plan(surfaces([zone("edge", "environmental_edge", "very_high",
                              (-30, -30, 30, 30))], ex), [cat()])
    for o in out["orders"]:
        assert math.hypot(o["pos"][0], o["pos"][1]) > 8.0 - 1e-6
    assert any(e["code"] == SD.CODE_EXCLUDED
               for e in out["keep_out"]["entries"])


def test_height_band_matches_the_measured_height():
    for o in plan()["orders"]:
        assert o["height_band"] == SD.band_of(o["height_m"], bands())


# --- the manifest itself ----------------------------------------------------

def test_manifest_declares_its_schema_space_and_source():
    out = plan(locked_shell="sha256:abc")
    assert out["schema"] == "surface-dressing/1"
    assert out["space"] == SD.SPACE
    assert out["source"] == "t.tscn"
    assert out["locked_shell"] == "sha256:abc"


def test_a_y_up_surfaces_block_is_refused_not_reinterpreted():
    surf = small()
    surf["space"] = "glTF Y-up"
    with pytest.raises(SD.PlanError) as e:
        plan(surf)
    assert "sideways" in str(e.value)


def test_orders_carry_every_key_the_schema_requires():
    required = {"surface_zone_id", "asset_set", "asset_id", "placement_mode",
                "pos", "yaw", "scale", "height_m", "height_band",
                "collision_policy", "in_traversed_space", "seed_offset",
                "transparency"}
    for o in plan()["orders"]:
        assert required <= set(o)
        assert o["collision_policy"] == "none"


def test_every_order_names_a_zone_the_manifest_declares():
    out = plan()
    ids = {z["surface_zone_id"] for z in out["zones"]}
    assert all(o["surface_zone_id"] in ids for o in out["orders"])


def test_same_seed_is_byte_identical():
    import json
    assert json.dumps(plan()["orders"]) == json.dumps(plan()["orders"])


def test_a_different_seed_moves_the_scatter():
    import json
    assert json.dumps(plan()["orders"]) != json.dumps(plan(seed=2000)["orders"])


def test_a_zone_changing_does_not_reshuffle_another_zones_scatter():
    """rng_for is keyed by zone, so editing one zone cannot reshuffle another.
    Without that, adding a courtyard would redress the whole site.

    The SEQUENCE is what is stable, not the length: with `instance_budget`
    "auto" the budget scales with total dressable area, so a bigger site
    legitimately places more in every zone. The positions must be a prefix of
    each other, and with an explicit budget they must match outright."""
    a = plan()
    surf = small()
    surf["zones"].append(zone("extra", "play_space", "medium",
                              (100, 100, 140, 140)))
    b = SD.plan(surf, [cat()], site_id="t", source="t.tscn", seed=1999)
    pa = [o["pos"] for o in a["orders"] if o["surface_zone_id"] == "edge"]
    pb = [o["pos"] for o in b["orders"] if o["surface_zone_id"] == "edge"]
    n = min(len(pa), len(pb))
    assert n and pa[:n] == pb[:n]


def test_an_explicit_budget_makes_a_zone_fully_independent():
    """With the budget pinned, adding a zone elsewhere must not change this
    zone's share... which it does, because shares are proportional. So the
    thing that must hold is narrower and worth stating: the same zone, the
    same budget share, produces the same orders."""
    surf = small()
    a = SD.plan(surf, [cat()], site_id="t", source="t.tscn", seed=1999,
                instance_budget=200, tri_budget=None)
    b = SD.plan(surf, [cat()], site_id="t", source="t.tscn", seed=1999,
                instance_budget=200, tri_budget=None)
    assert [o["pos"] for o in a["orders"]] == [o["pos"] for o in b["orders"]]


def test_no_assets_at_all_is_an_error_not_an_empty_plan():
    with pytest.raises(SD.PlanError):
        plan(catalogue=[])


# --- the catalogue comes from measurements, not declarations ----------------

def _metrics_row(name, **kw):
    row = {"file": f"{name}_ab12cd.glb", "part_extent_up_max": 0.06,
           "plan_hull_area_m2": 0.03, "tris": 100}
    row.update(kw)
    return row


def test_catalogue_is_built_from_measured_glb_metrics():
    cat = SD.catalogue_from_metrics(
        [_metrics_row("pebble"), _metrics_row("weed_tuft", tris=154)],
        {"pebble": "ground_clutter", "weed_tuft": "ground_cover"})
    assert {c["asset_id"] for c in cat} == {"pebble", "weed_tuft"}
    assert all(c["height_source"] == "measured" for c in cat)
    assert next(c for c in cat if c["asset_id"] == "weed_tuft")["tris"] == 154


def test_an_unmapped_asset_is_skipped_not_guessed():
    """The family decides which zones an asset may dress. Inventing one would
    put litter on a gameplay path because nobody said not to."""
    cat = SD.catalogue_from_metrics(
        [_metrics_row("pebble"), _metrics_row("mystery")],
        {"pebble": "ground_clutter"})
    assert [c["asset_id"] for c in cat] == ["pebble"]


def test_metrics_rows_that_errored_are_skipped():
    cat = SD.catalogue_from_metrics(
        [{"file": "broken.glb", "error": "not a GLB"}, _metrics_row("pebble")],
        {"pebble": "ground_clutter", "broken": "ground_clutter"})
    assert [c["asset_id"] for c in cat] == ["pebble"]


# --- the CLI ----------------------------------------------------------------

def _cli_fixture(tmp_path):
    import json
    surf = surfaces([zone("edge", "environmental_edge", "very_high",
                          (-30, -30, 30, 30))])
    (tmp_path / "surfaces.json").write_text(json.dumps(surf), encoding="utf-8")
    (tmp_path / "metrics.json").write_text(
        json.dumps([_metrics_row("pebble")]), encoding="utf-8")
    (tmp_path / "sets.json").write_text(
        json.dumps({"asset_sets": {"pebble": "ground_clutter"}}),
        encoding="utf-8")
    return [str(tmp_path / "surfaces.json"), str(tmp_path / "metrics.json"),
            str(tmp_path / "sets.json")]


def test_cli_writes_a_manifest(tmp_path):
    import json
    s, m, a = _cli_fixture(tmp_path)
    out = tmp_path / "dress.json"
    rc = SD.main(["--surfaces", s, "--metrics", m, "--asset-sets", a,
                  "--site-id", "t", "--source", "t.tscn",
                  "--out", str(out), "--audit"])
    assert rc == 0
    man = json.loads(out.read_text(encoding="utf-8"))
    assert man["schema"] == "surface-dressing/1"
    assert man["orders"] and man["cost"]["instances"] == len(man["orders"])


def test_cli_budget_words_are_accepted():
    """"auto" and "none" have to survive the shell, because an adapter passes
    strings and an int() on "auto" is a stack trace at job time."""
    import json
    import tempfile
    import pathlib
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        s, m, a = _cli_fixture(tmp)
        for words in (["--instance-budget", "auto", "--tri-budget", "none"],
                      ["--instance-budget", "50", "--tri-budget", "auto"]):
            out = tmp / "o.json"
            rc = SD.main(["--surfaces", s, "--metrics", m, "--asset-sets", a,
                          "--site-id", "t", "--source", "t.tscn",
                          "--out", str(out)] + words)
            assert rc == 0
            assert json.loads(out.read_text(encoding="utf-8"))["orders"]


def test_cli_reports_an_empty_catalogue_instead_of_planning_nothing(tmp_path):
    import json
    s, m, _ = _cli_fixture(tmp_path)
    bad = tmp_path / "nomatch.json"
    bad.write_text(json.dumps({"asset_sets": {"nothing": "x"}}),
                   encoding="utf-8")
    rc = SD.main(["--surfaces", s, "--metrics", m, "--asset-sets", str(bad),
                  "--site-id", "t", "--source", "t.tscn"])
    assert rc == 2


# --- where a placement stands ----------------------------------------------
# Cold run 9052: every order at pos z 0.0, 2,500 of 4,909 instances more than
# 5 mm inside the slab under them, 1,648 of those inside a 0.0974 m sidewalk
# band. The height is the top of the surface Lot declares under the point.

SIDEWALK_TOP = 0.0974          # lot SIDEWALK_H on 9052's contract
PLATE_TOP = -0.002             # lot PLATE_TOP


def test_a_placement_on_a_raised_band_stands_on_its_top():
    band = slab("sidewalk_0L_0", (10.0, 2.0), (20.0, 4.0), SIDEWALK_TOP,
                family="sidewalk")
    plate = slab("Ground", (0.0, 0.0), (200.0, 200.0), PLATE_TOP)
    surf = surfaces([zone("walk", "environmental_edge", "very_high",
                          (0, 0, 20, 4), kind="sidewalk")], tops=(plate, band))
    out = plan(surf)
    assert out["orders"]
    assert {o["pos"][2] for o in out["orders"]} == {SIDEWALK_TOP}


def test_where_slabs_overlap_the_highest_top_is_the_surface():
    """A zone laid half over a band: the half on the band stands on the band,
    the rest on the plate. Checked per order against an independent
    axis-aligned test, not against `surface_top`."""
    band = slab("sidewalk", (5.0, 0.0), (10.0, 40.0), SIDEWALK_TOP,
                family="sidewalk")
    plate = slab("Ground", (0.0, 0.0), (200.0, 200.0), PLATE_TOP)
    surf = surfaces([zone("edge", "environmental_edge", "very_high",
                          (0, -20, 20, 20))], tops=(plate, band))
    out = plan(surf)
    on_band = [o for o in out["orders"] if o["pos"][0] <= 10.0]
    off_band = [o for o in out["orders"] if o["pos"][0] > 10.0]
    assert on_band and off_band
    assert all(o["pos"][2] == SIDEWALK_TOP for o in on_band)
    assert all(o["pos"][2] == PLATE_TOP for o in off_band)


def test_a_yawed_slab_holds_points_along_its_own_axis():
    diag = [slab("path_0", (0.0, 0.0), (10.0, 2.0), 0.012, yaw=45.0,
                 family="path")]
    assert SD.surface_top((3.0, 3.0), diag) == 0.012
    assert SD.surface_top((3.0, -3.0), diag) is None


def test_the_height_is_read_where_the_placement_ships(monkeypatch):
    """Rounding moves a point: 5.00004 is off a slab ending at x = 5.0, and
    the 5.0 it ships as is on it. The height has to be the shipped point's.
    A point on a slab's edge straddles it, so the step refusal is switched
    off here to isolate the rounding."""
    step = slab("step", (2.5, 0.0), (5.0, 10.0), 0.1)
    plate = slab("Ground", (0.0, 0.0), (200.0, 200.0), 0.0)
    monkeypatch.setattr(SD, "STEP_TOLERANCE_M", 1.0)
    monkeypatch.setattr(SD, "_clustered_points",
                        lambda rng, aabb, n, **kw: [(5.00004, 1.0)])
    surf = surfaces([zone("edge", "environmental_edge", "very_high",
                          (0, -5, 10, 5))], tops=(plate, step))
    out = plan(surf, instance_budget=None, tri_budget=None)
    assert [o["pos"] for o in out["orders"]] == [[5.0, 1.0, 0.1]]


def test_surfaces_without_tops_are_refused_not_planned_at_zero():
    surf = small()
    del surf["tops"]
    with pytest.raises(SD.PlanError) as e:
        plan(surf)
    assert "tops" in str(e.value)


def test_tops_declared_under_another_rule_are_refused():
    surf = small()
    surf["tops_rule"] = "the lowest top wins"
    with pytest.raises(SD.PlanError):
        plan(surf)


def test_an_unrecognised_slab_is_refused():
    surf = small()
    surf["tops"] = [{"name": "Ground", "centre": [0, 0], "size": [100, 100],
                     "yaw_deg": 0.0}]                     # no top_m
    with pytest.raises(SD.PlanError):
        plan(surf)


def test_a_candidate_over_no_surface_is_refused_and_says_so():
    half = slab("Ground", (5.0, 0.0), (10.0, 40.0), 0.0)
    surf = surfaces([zone("edge", "environmental_edge", "very_high",
                          (0, -20, 20, 20))], tops=(half,))
    out = plan(surf)
    assert out["orders"]
    assert all(o["pos"][0] <= 10.0 for o in out["orders"])
    assert SD.CODE_NO_SURFACE in {e["code"] for e in out["keep_out"]["entries"]}


def test_audit_catches_an_order_standing_off_its_surface():
    band = slab("sidewalk", (0.0, 0.0), (200.0, 200.0), SIDEWALK_TOP)
    surf = surfaces([zone("walk", "environmental_edge", "very_high",
                          (0, 0, 20, 4))], tops=(band,))
    out = plan(surf)
    assert SD.audit(out, tops=[band]) == []
    out["orders"][0]["pos"][2] = 0.0                      # 0.21's answer
    codes = [f["code"] for f in SD.audit(out, tops=[band])]
    assert codes == [SD.CODE_OFF_SURFACE]


def _one_point(monkeypatch, x, y):
    monkeypatch.setattr(SD, "_clustered_points",
                        lambda rng, aabb, n, **kw: [(x, y)])


def _kerb():
    band = slab("sidewalk", (5.0, 0.0), (10.0, 40.0), SIDEWALK_TOP,
                family="sidewalk")
    plate = slab("Ground", (0.0, 0.0), (200.0, 200.0), PLATE_TOP)
    return plate, band


def test_a_placement_on_a_kerb_line_is_refused_not_given_either_height(monkeypatch):
    """9052's replan: 26 origins exactly on the cross street's kerb lines,
    where the band and the road both hold the point and float noise picks."""
    plate, band = _kerb()
    _one_point(monkeypatch, 10.0, 2.0)
    surf = surfaces([zone("edge", "environmental_edge", "very_high",
                          (0, -20, 20, 20))], tops=(plate, band))
    out = plan(surf, instance_budget=None, tri_budget=None)
    assert out["orders"] == []
    assert SD.CODE_STRADDLES_STEP in {e["code"] for e in out["keep_out"]["entries"]}


def test_the_same_placement_clear_of_the_kerb_stands_on_the_band(monkeypatch):
    """Falsification: the refusal is about the step, not about the band."""
    plate, band = _kerb()
    _one_point(monkeypatch, 9.0, 2.0)
    surf = surfaces([zone("edge", "environmental_edge", "very_high",
                          (0, -20, 20, 20))], tops=(plate, band))
    out = plan(surf, instance_budget=None, tri_budget=None)
    assert [o["pos"] for o in out["orders"]] == [[9.0, 2.0, SIDEWALK_TOP]]


def test_footprint_step_sees_a_rise_and_an_overhang():
    plate, band = _kerb()
    slabs = [plate, band]
    # on the plate, 5 cm from the band's face, 10 cm radius: the band rises
    assert abs(SD.footprint_step((10.05, 0.0), 0.1, slabs, PLATE_TOP)
               - (SIDEWALK_TOP - PLATE_TOP)) < 1e-9
    # on the band, 5 cm from its edge: the rim hangs over the plate
    assert abs(SD.footprint_step((9.95, 0.0), 0.1, slabs, SIDEWALK_TOP)
               - (SIDEWALK_TOP - PLATE_TOP)) < 1e-9
    # clear of the edge on either side: flat
    assert SD.footprint_step((10.2, 0.0), 0.1, slabs, PLATE_TOP) == 0.0
    assert SD.footprint_step((9.8, 0.0), 0.1, slabs, SIDEWALK_TOP) == 0.0
    # over the edge of the world
    assert SD.footprint_step((99.95, 0.0), 0.1, slabs, PLATE_TOP) == math.inf
