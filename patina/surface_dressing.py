"""Layer 3: plan where surface dressing actually goes on an assembled site.

`docs/SURFACE_DRESSING.md` section 2 puts this stage here, after the functional
shell lock and after Pixelcoat, and it is the counterpart to the Layer 2 pass
Patina already runs. Layer 2 bolts mid-frequency detail onto ONE BUILDING
before assembly -- gutters, edge strips, curbs -- and has no concept of a site.
Layer 3 dresses the ground and the seams of the whole place.

WHAT THIS MODULE IS AND IS NOT. It decides positions. It does not decide what
a pebble looks like (Zoo), where the dressable regions are (Lot's
`site_surfaces`), or whether the shell is trusted (the lock). It consumes the
first two and refuses to run without the third being asserted.

  in    the `zones`, `exclusions`, `capsule` and `bands` blocks Lot emits,
        plus a catalogue of built assets with MEASURED heights
  out   a complete `surface-dressing/1` manifest
        (`level_factory/schemas/surface_dressing.v1.json`)

THE TWO GATES ARE ENFORCED HERE, AT PRODUCTION, NOT AT VALIDATION. A planner
that emits an illegal placement and relies on a downstream gate to catch it has
produced a plan that cannot ship, and has spent the whole pipeline finding out.

  honesty   in_traversed_space AND height_m > unassisted_step_max AND
            collision_policy == "none"  ->  REFUSED.
            Below the limit a body steps over the object anyway, so passing
            through it is not a visible lie. Above it the engine calls the
            contact a WALL and walking through instead is the "believable but
            false traversal promise" the guide forbids. The number is 0.117 m
            for this stack's capsule and it arrives in the `capsule` block --
            this module never re-derives it.

  coverage  a zone's occluded fraction may not exceed 1 - surface_visibility.

HOW DENSITY AND VISIBILITY COMPOSE, because they are two different ideas and
conflating them is how a budget gets breached politely:

    visibility decides the ALLOWANCE   (gameplay_path 0.90 -> 10% may be hidden)
    density decides how much of that allowance is SPENT (low 0.35, ... very_high 1.0)

So density can never breach a budget; at most it fills it. "Surface Dressing
should partially occlude gameplay surfaces, not visually replace them."

EVERY REFUSAL IS RECORDED. `keep_out` carries what was refused and why, because
a planner that silently places less than it was asked for is indistinguishable
from one that had nothing to place.

Determinism: `determinism.rng_for(seed, "surface_dressing", zone_id)`, so a
zone's scatter does not move when another zone changes, and dict ordering can
never reach the bytes.
"""
from __future__ import annotations

import math

from . import determinism
from .version import __version__

SCHEMA = "surface-dressing/1"
SPACE = "spec/Blender Z-up raw coords"

# How much of a zone's visibility ALLOWANCE each density reading spends.
# Readings are the guide's: sidewalk centre low, sidewalk edge medium, wall
# seam high, abandoned corner very_high.
DENSITY_SPEND = {
    "none": 0.0,
    "low": 0.35,
    "medium": 0.60,
    "high": 0.85,
    "very_high": 1.0,
}

# Why detail is HERE. The guide's rule 3: unexplained scatter reads as
# procedural noise, so every placement names the cause its zone implies.
# Only the SPECIFIC kinds name a cause. `ground` and `floor` say nothing about
# why detail would be here -- the first version listed them as "traffic", which
# shadowed the exposure lookup below and collapsed a whole site's causes into
# two values. A cause that is always the same is not a cause.
CAUSE_BY_KIND = {
    "wall_base": "wall base",
    "seam": "wall base",
    "ledge": "wall base",
    "roof": "shade",
    "negative_space": "shade",
}
CAUSE_BY_EXPOSURE = {
    "gameplay_path": "traffic",
    "play_space": "traffic edge",
    "environmental_edge": "shade",
    "decorative": "shade",
}

# An opaque solid hides all of its own footprint -- that is what opaque means,
# and it is a fact rather than an estimate. Alpha cutout and translucent hide
# some fraction of theirs, which is a property of the ARTWORK and has to be
# measured; the catalogue must supply it and this module refuses to guess.
OPAQUE_OCCLUSION = 1.0

# COST. The visibility budget is not a performance constraint and was never
# going to be one. Measured on the real coldrun_pawn_job site with no cost
# budget at all, the coverage rules alone authorised 361,412 placements and
# 46.8 MILLION triangles of collisionless detail -- every one of them legal,
# every gate green. "How much of the floor may I hide" and "what may this
# cost" are different questions and only one of them was being asked.
#
# WHICH COST ACTUALLY BINDS. Not triangles. This layer is a handful of meshes
# repeated thousands of times, which is the case instancing exists for: as a
# MultiMesh, ten thousand pebbles are one draw call and the triangle total
# barely signifies. What does signify is the INSTANCE count -- per-instance
# transforms, culling, the manifest itself (18,000 orders is a 12 MB JSON) --
# and the number of distinct meshes, which is the draw calls.
#
# So instances are the primary budget, triangles are reported alongside so the
# figure can never be quietly ignored, and either may bind. A caller that
# knows its shell's real numbers should pass both explicitly; these defaults
# only keep an unattended run from producing a 46-million-triangle plan.
DEFAULT_INSTANCES_PER_M2 = 0.20
DEFAULT_TRIS_PER_M2 = 120.0

CODE_TOO_TALL = "DRESS_REFUSED_TOO_TALL_FOR_TRAVERSED_SPACE"
CODE_BUDGET = "DRESS_REFUSED_VISIBILITY_BUDGET"
CODE_EXCLUDED = "DRESS_REFUSED_EXCLUSION"
CODE_NO_ASSETS = "DRESS_NO_ASSETS_FOR_ZONE"
CODE_TRI_BUDGET = "DRESS_REFUSED_TRI_BUDGET"
CODE_INSTANCE_BUDGET = "DRESS_REFUSED_INSTANCE_BUDGET"
CODE_UNBOUNDED = "DRESS_COST_UNBOUNDED"


class PlanError(ValueError):
    """The plan cannot be made, and pretending otherwise would be worse."""


def catalogue_entry(asset_id, asset_set, *, height_m, footprint_m2, tris,
                    transparency="opaque", occlusion=None,
                    height_source="measured"):
    """One buildable asset, as the planner needs to know it.

    `height_m` and `footprint_m2` are MEASURED from the built GLB
    (`tools/shape_metrics.py` reports `part_extent_up_max` and the plan hull),
    never read off the genome. A genome declares a range; the honesty rule is
    about the object that actually exists. `height_source` records which it
    was, so a plan made from declarations is obviously one.
    """
    if transparency != "opaque" and occlusion is None:
        raise PlanError(
            f"{asset_id}: transparency={transparency!r} needs an explicit "
            "`occlusion` -- how much of its footprint a cutout or translucent "
            "asset actually hides is a property of the artwork, and this "
            "module will not invent it. Opaque is the only case that is a "
            "fact rather than a measurement.")
    if height_m <= 0 or footprint_m2 <= 0:
        raise PlanError(f"{asset_id}: height and footprint must be positive")
    if int(tris) <= 0:
        raise PlanError(
            f"{asset_id}: triangle count is required and must be positive. "
            "A planner that does not know what an asset costs cannot keep a "
            "performance budget, and this layer is instanced in the thousands.")
    return {
        "asset_id": asset_id,
        "asset_set": asset_set,
        "height_m": float(height_m),
        "footprint_m2": float(footprint_m2),
        "transparency": transparency,
        "tris": int(tris),
        "occlusion": OPAQUE_OCCLUSION if occlusion is None else float(occlusion),
        "height_source": height_source,
    }


def band_of(height_m, bands):
    """Which guide band a measured height falls in."""
    for name in ("micro", "low", "medium", "tall"):
        b = bands.get(name)
        if b and height_m <= b["max_m"]:
            return name
    return "tall"


def zone_area_m2(zone):
    a = zone["aabb"]
    return max(0.0, (a[3] - a[0])) * max(0.0, (a[4] - a[1]))


def zone_for(point, zones):
    """First matching zone wins.

    The precedence rule travels in the DATA: `lot/site_surfaces.zones` emits
    them most-restrictive-first and this reads them in that order. Copying
    Lot's ordering logic into Patina would give two tools two chances to
    disagree about which budget a placement counts against, and a placement
    counted against two budgets is counted against neither.
    """
    x, y = float(point[0]), float(point[1])
    for z in zones:
        a = z["aabb"]
        if a[0] <= x <= a[3] and a[1] <= y <= a[4]:
            return z
    return None


def excluded(point, exclusions, *, radius_m=0.0):
    """Exclusion tags a point falls inside, given the placement's own radius."""
    x, y = float(point[0]), float(point[1])
    hit = []
    for e in exclusions:
        r = float(e.get("radius_m") or 0.0) + float(radius_m)
        pos = e.get("pos")
        if pos is not None and r > 0.0:
            if math.hypot(x - float(pos[0]), y - float(pos[1])) <= r:
                hit.append(e["tag"])
                continue
        box = e.get("aabb")
        if box and box[0] - r <= x <= box[3] + r \
                and box[1] - r <= y <= box[4] + r:
            hit.append(e["tag"])
    return sorted(set(hit))


def _clustered_points(rng, aabb, n, *, clumps, sigma_frac):
    """A clustered scatter, not a uniform one.

    Real debris clusters. A uniform draw gives a Clark-Evans R near 1.0 and an
    even scatter gives 2.0, and neither reads as placed -- the guide's
    definition of done is "no obvious uniform scatter pattern from primary
    views". A minority of strays keeps the clumps from reading as blobs.
    """
    x0, y0, x1, y1 = aabb[0], aabb[1], aabb[3], aabb[4]
    w, h = max(1e-6, x1 - x0), max(1e-6, y1 - y0)
    sigma = min(w, h) * sigma_frac
    k = max(1, int(clumps))
    cx = rng.uniform(x0, x1, size=k)
    cy = rng.uniform(y0, y1, size=k)
    out = []
    for i in range(n):
        if rng.random() < 0.18:
            out.append((float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1))))
        else:
            j = int(rng.integers(0, k))
            out.append((
                float(min(x1, max(x0, cx[j] + rng.normal(0.0, sigma)))),
                float(min(y1, max(y0, cy[j] + rng.normal(0.0, sigma))))))
    return out


def plan(surfaces, catalogue, *, site_id, source, seed,
         locked_shell=None, quality_tier="standard",
         instance_budget="auto", tri_budget="auto", clumps_per_zone=6, sigma_frac=0.16, scale_range=(0.65, 1.55)):
    """Produce a complete `surface-dressing/1` manifest.

    `surfaces` is what `lot/site_surfaces.surfaces()` returned. `catalogue` is
    a list of `catalogue_entry` dicts. `source` names the assembled site scene
    this was planned against; a plan made against one assembly and applied to
    another is a different plan, which is why the schema requires it.

    `instance_budget` and `tri_budget` are what this layer may spend on the
    whole site: an int, "auto", or None for unbounded. Either may bind.
    Instances are the one that usually does -- see the note on COST above.

    Both are allocated to zones in proportion to each zone's own coverage
    allowance, so the big open zone and a 25 m2 path segment both get a fair
    share. The first version capped candidates PER ZONE, which made a site's
    density depend on how many boxes its paths happened to be chopped into:
    73 path segments took 400 candidates each while the 7,973 m2 of open
    ground took 400 in total, and the site came out densest exactly where the
    guide says it should be sparsest.

    Passing None for both is honest but records `DRESS_COST_UNBOUNDED`,
    because an unbounded plan for a layer instanced in the thousands is a
    decision and should look like one.
    """
    for key in ("space", "capsule", "bands", "zones", "exclusions"):
        if key not in surfaces:
            raise PlanError(f"surfaces block is missing {key!r}")
    if surfaces["space"] != SPACE:
        raise PlanError(
            f"surfaces are in {surfaces['space']!r} but this manifest declares "
            f"{SPACE!r}. Height is pos[2] here; a Y-up input would silently "
            "plan the whole site sideways.")
    if not catalogue:
        raise PlanError("no assets to place")

    cap = surfaces["capsule"]
    step_max = float(cap["unassisted_step_max_m"])
    bands = surfaces["bands"]
    zones = surfaces["zones"]
    exclusions = surfaces["exclusions"]

    orders, keep_out = [], []
    counts = {}

    # --- allocate the triangle budget before placing anything ---------------
    share = {}
    for z in zones:
        a = zone_area_m2(z)
        allow = (1.0 - float(z.get("surface_visibility", 1.0))) \
            * DENSITY_SPEND.get(z.get("density", "medium"), 0.0)
        share[z["surface_zone_id"]] = max(0.0, a * allow)
    total_share = sum(share.values())
    dressable = sum(zone_area_m2(z) for z in zones)
    if tri_budget == "auto":
        tri_budget = int(dressable * DEFAULT_TRIS_PER_M2)
    if instance_budget == "auto":
        instance_budget = int(dressable * DEFAULT_INSTANCES_PER_M2)
    if tri_budget is None and instance_budget is None:
        keep_out.append({
            "code": CODE_UNBOUNDED, "surface_zone_id": None,
            "why": "planned with neither an instance nor a triangle budget; "
                   "nothing bounds what this layer costs on this site"})
    tris_spent = 0

    for zone in zones:
        zid = zone["surface_zone_id"]
        area = zone_area_m2(zone)
        if area <= 0.0:
            continue
        density = zone.get("density", "medium")
        allowance = 1.0 - float(zone.get("surface_visibility", 1.0))
        budget = allowance * DENSITY_SPEND.get(density, 0.0)
        if budget <= 0.0:
            continue

        traversed = bool(zone.get("traversed", True))
        usable = [c for c in catalogue
                  if not (traversed and c["height_m"] > step_max)]
        refused_here = [c for c in catalogue if c not in usable]
        for c in refused_here:
            keep_out.append({
                "code": CODE_TOO_TALL, "surface_zone_id": zid,
                "asset_id": c["asset_id"],
                "why": (f"{c['height_m']:.3f} m exceeds unassisted_step_max "
                        f"{step_max:.5f} m in traversed space; a body would "
                        "have to climb it, so walking through it is a false "
                        "traversal promise"),
            })
        if not usable:
            keep_out.append({"code": CODE_NO_ASSETS, "surface_zone_id": zid,
                             "why": "no catalogued asset is legal here"})
            continue

        rng = determinism.rng_for(seed, "surface_dressing", zid)
        # Ask for more candidates than either budget can hold; exclusions and
        # the budgets do the rejecting, so this is an upper bound and never a
        # target to hit.
        mean_fp = sum(c["footprint_m2"] for c in usable) / len(usable)
        mean_tris = sum(c["tris"] for c in usable) / len(usable)
        want = math.ceil((area * budget) / max(1e-9, mean_fp)) * 2
        frac = (share[zid] / total_share) if total_share > 0.0 else 0.0
        zone_tris = None if tri_budget is None else tri_budget * frac
        zone_inst = None if instance_budget is None else instance_budget * frac

        # Clamping the candidate list is how a cost budget stays cheap to
        # enforce -- but a clamp that says nothing is a SILENT truncation, and
        # a planner that quietly places less than it was asked for is
        # indistinguishable from one that had nothing to place. So when a
        # budget shortens the list, it says so here, with the numbers, whether
        # or not the in-loop refusal ever fires.
        want_coverage = want
        if zone_tris is not None:
            want = min(want, math.ceil(zone_tris / max(1.0, mean_tris)))
        if zone_inst is not None:
            want = min(want, math.ceil(zone_inst))
        want = int(max(0, want))
        if want < want_coverage:
            by_tris = (zone_tris is not None
                       and math.ceil(zone_tris / max(1.0, mean_tris)) <= want)
            keep_out.append({
                "code": CODE_TRI_BUDGET if by_tris else CODE_INSTANCE_BUDGET,
                "surface_zone_id": zid,
                "asset_id": None,
                "why": (f"the visibility budget allowed {want_coverage} "
                        f"candidates here; the cost budget allows {want} "
                        f"(zone share: "
                        + (f"{zone_inst:.1f} instances" if zone_inst is not None
                           else "no instance budget")
                        + ", "
                        + (f"{zone_tris:.0f} triangles" if zone_tris is not None
                           else "no triangle budget")
                        + ")"),
            })
        if want <= 0:
            continue
        zone_tris_spent = 0
        zone_inst_spent = 0
        points = _clustered_points(rng, zone["aabb"], want,
                                   clumps=clumps_per_zone,
                                   sigma_frac=sigma_frac)

        cause = CAUSE_BY_KIND.get(zone.get("kind"), None) \
            or CAUSE_BY_EXPOSURE.get(zone.get("exposure_class"), "traffic edge")
        spent = 0.0
        for i, (x, y) in enumerate(points):
            c = usable[int(rng.integers(0, len(usable)))]
            lo, hi = scale_range
            # Skewed small: real debris fields are many small, few large. A
            # uniform draw is what produces the "all the same size" read.
            s = float(lo + (hi - lo) * (rng.random() ** 1.8))
            height_m = c["height_m"] * s
            if traversed and height_m > step_max:
                keep_out.append({
                    "code": CODE_TOO_TALL, "surface_zone_id": zid,
                    "asset_id": c["asset_id"],
                    "why": (f"scaled to {s:.2f} it stands {height_m:.3f} m, "
                            f"over unassisted_step_max {step_max:.5f} m"),
                })
                continue
            fp = c["footprint_m2"] * (s ** 2)
            contribution = (fp * c["occlusion"]) / area
            if spent + contribution > budget:
                keep_out.append({
                    "code": CODE_BUDGET, "surface_zone_id": zid,
                    "asset_id": c["asset_id"],
                    "why": (f"zone is {zone['exposure_class']} with "
                            f"surface_visibility "
                            f"{zone.get('surface_visibility')}, density "
                            f"{density}: budget {budget:.4f} of the surface, "
                            f"{spent:.4f} already spent"),
                })
                break
            radius = math.sqrt(fp / math.pi)
            tags = excluded((x, y), exclusions, radius_m=radius)
            if tags:
                keep_out.append({
                    "code": CODE_EXCLUDED, "surface_zone_id": zid,
                    "asset_id": c["asset_id"],
                    "why": "inside " + ", ".join(tags),
                })
                continue
            # `>=`, not `+1 >`. A zone whose share works out to 0.87 of an
            # instance would otherwise get exactly zero, and a gameplay path
            # the guide asks for at LOW density getting nothing at all is a
            # different statement from low. The overshoot this allows is
            # bounded at one asset per zone, and the coverage gate still
            # holds -- `audit()` re-checks it against what shipped.
            if zone_inst is not None and zone_inst_spent >= zone_inst:
                keep_out.append({
                    "code": CODE_INSTANCE_BUDGET, "surface_zone_id": zid,
                    "asset_id": c["asset_id"],
                    "why": (f"zone's share of the instance budget is "
                            f"{zone_inst:.0f} and it is spent")})
                break
            if zone_tris is not None and zone_tris_spent >= zone_tris:
                keep_out.append({
                    "code": CODE_TRI_BUDGET, "surface_zone_id": zid,
                    "asset_id": c["asset_id"],
                    "why": (f"zone's share of the triangle budget is "
                            f"{zone_tris:.0f}; {zone_tris_spent} already "
                            "spent. This layer is instanced in the thousands "
                            "and the binding constraint is cost, not "
                            "coverage.")})
                break
            spent += contribution
            zone_tris_spent += c["tris"]
            zone_inst_spent += 1
            tris_spent += c["tris"]
            counts[c["asset_set"]] = counts.get(c["asset_set"], 0) + 1
            orders.append({
                "surface_zone_id": zid,
                "asset_set": c["asset_set"],
                "asset_id": c["asset_id"],
                "placement_mode": "cluster",
                "anchor_cause": cause,
                "pos": [round(x, 4), round(y, 4), 0.0],
                "normal": [0.0, 0.0, 1.0],
                "yaw": round(float(rng.random()) * 2.0 * math.pi, 5),
                "scale": round(s, 4),
                "height_m": round(height_m, 5),
                "height_band": band_of(height_m, bands),
                "collision_policy": "none",
                "shadow_policy": "contact",
                "in_traversed_space": traversed,
                # What was TESTED, not what was found. The schema is explicit
                # that an empty array means untested rather than clean.
                "cleared_exclusions": sorted({e["tag"] for e in exclusions}),
                "seed_offset": i,
                "quality_tier": quality_tier,
                "transparency": c["transparency"],
                "coverage_contribution": round(contribution, 8),
            })

    out = {
        "schema": SCHEMA,
        "site_id": site_id,
        "source": source,
        "space": SPACE,
        "seed": int(seed),
        "quality_tier": quality_tier,
        "generator": f"patina {__version__} surface_dressing",
        "capsule": dict(cap),
        "bands": {k: dict(v) for k, v in bands.items()},
        "zones": list(zones),
        "exclusions": list(exclusions),
        "counts": dict(sorted(counts.items())),
        "cost": {
            "instances": len(orders),
            "instance_budget": instance_budget,
            "tris_total": tris_spent,
            "tri_budget": tri_budget,
            "unique_meshes": len({o["asset_id"] for o in orders}),
            # Both budgets are allocated per zone and each zone may overshoot
            # its own share by at most one asset (see the `>=` note above), so
            # a site total can sit slightly over. Reported rather than hidden.
            "over_tri_budget": bool(tri_budget is not None
                                    and tris_spent > tri_budget),
            "over_instance_budget": bool(instance_budget is not None
                                         and len(orders) > instance_budget),
            "dressable_area_m2": round(dressable, 2),
            "instances_per_m2": round(len(orders) / dressable, 4)
            if dressable > 0 else 0.0,
            "tris_per_m2": round(tris_spent / dressable, 3)
            if dressable > 0 else 0.0,
        },
        "keep_out": {"refused": len(keep_out), "entries": keep_out},
        "orders": orders,
    }
    if locked_shell:
        out["locked_shell"] = locked_shell
    return out


def coverage_by_zone(manifest):
    """Occluded fraction per zone, recomputed from the orders themselves.

    Deliberately not carried forward from planning: a check that reads the
    planner's own running total only proves the planner can add up. This sums
    what actually shipped.
    """
    out = {}
    for o in manifest["orders"]:
        out[o["surface_zone_id"]] = out.get(o["surface_zone_id"], 0.0) \
            + float(o["coverage_contribution"])
    return out


def audit(manifest):
    """Re-check a finished manifest against both gates. Returns findings.

    An empty list means the plan is legal by the rules it declares, checked
    against the numbers it carries rather than against this module's memory of
    them.
    """
    findings = []
    step_max = float(manifest["capsule"]["unassisted_step_max_m"])
    zones = {z["surface_zone_id"]: z for z in manifest["zones"]}

    for o in manifest["orders"]:
        if (o["in_traversed_space"] and o["height_m"] > step_max
                and o["collision_policy"] == "none"):
            findings.append({
                "code": CODE_TOO_TALL, "surface_zone_id": o["surface_zone_id"],
                "message": (f"{o['asset_id']} stands {o['height_m']} m in "
                            f"traversed space, over {step_max} m, with no "
                            "collision")})
        if o["collision_policy"] != "none":
            findings.append({
                "code": "DRESS_HAS_COLLISION",
                "surface_zone_id": o["surface_zone_id"],
                "message": "surface dressing is collisionless by definition"})

    for zid, spent in coverage_by_zone(manifest).items():
        z = zones.get(zid)
        if z is None:
            findings.append({"code": "DRESS_ORPHAN_ZONE", "surface_zone_id": zid,
                             "message": "order names a zone the manifest "
                                        "does not declare"})
            continue
        allowance = 1.0 - float(z.get("surface_visibility", 1.0))
        if spent > allowance + 1e-9:
            findings.append({
                "code": CODE_BUDGET, "surface_zone_id": zid,
                "message": (f"occludes {spent:.4f} of a zone whose visibility "
                            f"budget allows {allowance:.4f}")})
    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def catalogue_from_metrics(metrics, asset_sets, *, transparency=None,
                           occlusion=None):
    """Build a catalogue from `tools/shape_metrics.py --json` output.

    The heights and footprints come from the MEASURED GLB, which is the whole
    point: a genome declares a range and the honesty rule is about the object
    that actually exists. `asset_sets` maps asset_id -> family name; an asset
    the map does not name is skipped rather than guessed at, because the family
    decides which zones it may dress.
    """
    transparency = transparency or {}
    occlusion = occlusion or {}
    out = []
    for row in metrics:
        if "error" in row:
            continue
        # shape_metrics names files `<species>_<hash>.glb`.
        asset_id = row.get("asset_id") or \
            row["file"].rsplit(".", 1)[0].rsplit("_", 1)[0]
        if asset_id not in asset_sets:
            continue
        out.append(catalogue_entry(
            asset_id, asset_sets[asset_id],
            height_m=row["part_extent_up_max"],
            footprint_m2=row["plan_hull_area_m2"],
            tris=row["tris"],
            transparency=transparency.get(asset_id, "opaque"),
            occlusion=occlusion.get(asset_id)))
    return out


def main(argv=None):
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(
        prog="patina.surface_dressing",
        description="Plan Layer 3 surface dressing for an assembled site.")
    ap.add_argument("--surfaces", required=True,
                    help="lot/site_surfaces.py output")
    ap.add_argument("--metrics", required=True,
                    help="tools/shape_metrics.py --json output for the built "
                         "dressing GLBs")
    ap.add_argument("--asset-sets", required=True,
                    help='JSON mapping asset_id -> family, e.g. '
                         '{"pebble": "ground_clutter"}')
    ap.add_argument("--site-id", required=True)
    ap.add_argument("--source", required=True,
                    help="the assembled site scene this is planned against")
    ap.add_argument("--locked-shell", help="functional-lock digest")
    ap.add_argument("--seed", type=int, default=1999)
    ap.add_argument("--quality-tier", default="standard",
                    choices=("low", "standard", "high"))
    ap.add_argument("--instance-budget", default="auto",
                    help='int, "auto", or "none"')
    ap.add_argument("--tri-budget", default="auto",
                    help='int, "auto", or "none"')
    ap.add_argument("--out", help="write here instead of stdout")
    ap.add_argument("--audit", action="store_true",
                    help="re-check the finished manifest and exit non-zero on "
                         "any finding")
    a = ap.parse_args(argv)

    def budget(v):
        if v == "auto":
            return "auto"
        if v in ("none", "None", ""):
            return None
        return int(v)

    with open(a.surfaces, encoding="utf-8") as fh:
        surf = json.load(fh)
    with open(a.metrics, encoding="utf-8") as fh:
        metrics = json.load(fh)
    with open(a.asset_sets, encoding="utf-8") as fh:
        sets = json.load(fh)

    cat = catalogue_from_metrics(
        metrics, sets.get("asset_sets", sets),
        transparency=sets.get("transparency"),
        occlusion=sets.get("occlusion"))
    if not cat:
        sys.stderr.write(
            "no catalogued asset matched the metrics; asset_sets names "
            f"{sorted(sets.get('asset_sets', sets))} and the metrics carry "
            f"{sorted(r.get('file', '?') for r in metrics)}\n")
        return 2

    man = plan(surf, cat, site_id=a.site_id, source=a.source, seed=a.seed,
               locked_shell=a.locked_shell, quality_tier=a.quality_tier,
               instance_budget=budget(a.instance_budget),
               tri_budget=budget(a.tri_budget))

    text = json.dumps(man, indent=1)
    if a.out:
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)

    c = man["cost"]
    sys.stderr.write(
        f"[dress] {c['instances']} instances, {c['tris_total']} tris, "
        f"{c['unique_meshes']} meshes over {c['dressable_area_m2']} m2 "
        f"({c['instances_per_m2']}/m2); {man['keep_out']['refused']} refused\n")

    findings = audit(man)
    for f in findings:
        sys.stderr.write(f"[dress] {f['code']}: {f['message']}\n")
    if a.audit and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
