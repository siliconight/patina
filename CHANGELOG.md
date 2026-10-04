# Changelog

All notable changes to Patina. Format follows [Keep a Changelog](https://keepachangelog.com/);
versioning follows [SemVer](https://semver.org/).

## [0.24.0] - which way is up is read off the file

### Fixed
- **A building taller than it is wide was dressed on its side.**
  `slots.detect_up_axis` took the axis with the smallest extent as up,
  reasoning that "a building is wide and shallow". Deli Counter 0.174.0's
  rowhome Empties are 6.3 m wide, 6.8-10.1 m tall and 12.3 m deep, so up
  read as **X** for all six. The three real buildings in the same level
  read Y.

  Every height-dependent pass then ran on the wrong axis: grime, banding and
  the anchors. In cold run 9147 every `ground_edge` and `wall_base` anchor
  on an Empty stood on its centre line (x = 0) at heights from 0 to 10 m, and
  `roofline` ran up a side wall. Built, that was curbs, base courses and
  gutters standing out of the walls at storey lines and diagonals -- the
  walker saw it in the frames and asked about the axes. Cold run 9146 (the
  0.174.0 shells) shows the same scatter, so it predates any change to the
  Empties since.

- **The rule now reads provenance first.** Blender's glTF exporter writes +Y
  up unless `export_yup=False`, and Deli Counter exports with the default
  (`deli_counter.py`, `bpy.ops.export_scene.gltf`).
  - `gltf_io.load_glb` sets `Scene.up_axis_hint`:
    - from `asset.extras.patina_up_axis` when Patina wrote the file;
    - else Y when `asset.generator` names `Khronos glTF Blender I/O`;
    - else None.
  - `save_glb` writes the hint into its output's `asset.extras`, because
    Patina replaces the generator string and would otherwise erase the
    evidence it read.
  - `detect_up_axis` returns the hint when there is one, and guesses from
    extents only when the file says nothing (the legacy `DeliCounter-fixture`
    shell, `tests/make_fixture.py`).
  - The run result names which it was: `up_axis_source`.

- **`version.py` said 0.22.0 through all of 0.23.0**, so 0.23.0's output was
  stamped `Patina 0.22.0`. It now matches `VERSION`.

`tests/test_up_axis_declared.py`. Against the real Empty shell (skipped
without a Deli Counter build beside this repo):
- it reads Y;
- the control: with the declaration stripped, the guess answers X;
- Patina's own output carries Y forward;
- end to end, the command Level Factory runs for an Empty puts every ground
  and wall-base anchor at the foot of a wall and spread along it.

And against the legacy fixture: a file that says nothing is still guessed,
Z.

## [0.23.0] - a zone dresses only the ground it owns

### Fixed
- **Overlapping zones dressed the same ground twice.** `zone_for` has said
  since it was written that the precedence rule travels in the data and that
  "a placement counted against two budgets is counted against neither" --
  and `plan` never called it. Each zone scattered over its own bounding
  box, and Lot's `open_ground` box is the whole plate, so open-ground
  clutter at MEDIUM landed on the roads (LOW), the sidewalks, the perimeter
  and the walks, on top of what those zones placed. Measured on cold run
  9141's shipped manifest: 2,436 of 5,232 placements stood where the
  precedence rule gives the ground to another zone; across families,
  open_ground on road_0 445, on the perimeter 238, on the sidewalks 265, on
  road_1 115, on walks 58 -- and all 256 pieces on the parking fields
  (0.29 a m2), the pebble-strewn aisles in the walker's frames.
- A candidate point is now kept only where `zone_for` names a zone of the
  placing zone's own FAMILY (`zone_family`: Lot's `zone_family:<f>` tag, or
  the zone's id). By family, not identity, because Lot chops a corridor
  into boxes that overlap at their joins and a point on a join is the same
  ground either way. Asked after the asset, scale and yaw draws, so a
  refusal does not shift the points after it; refused as
  `DRESS_REFUSED_ANOTHER_ZONES_GROUND`, recorded in `keep_out`.

The site-level effect -- fewer pieces on every road, sidewalk and edge, the
fields at a road's density with Lot 0.95.0 -- is measured on cold run 9143
(`docs/cold_runs/cold_9143/NOTES.md`).

`tests/test_surface_dressing.py`: open ground places nothing on a road's
ground and still dresses its own; a corridor's boxes share their join; the
control -- every zone given one family -- does put open ground on the road,
so the first test can fail; `zone_family` reads the tag or falls back to
the id.

## [0.22.0] - surface dressing stands on the surface under it

### Fixed
- **Every order was placed at pos z 0.0**, whatever was under it. Cold run
  9052's walk copy, read against the slabs of the scene it was placed on:
  2,500 of 4,909 instances more than 5 mm inside the slab under them -- 1,648
  inside a 0.0974 m sidewalk band, 739 in the road, 64 in a path, 49 in a
  kerb cut. `plan()` now reads the top of the surface under each placement
  from the `tops` block Lot 0.72.0's `site_surfaces` declares, at the
  position that ships (after rounding, so a point at a slab's edge is asked
  once), and writes it into pos[2].

### Added
- **`check_tops()`**: a surfaces block with no `tops`, a `tops_rule` other
  than the one this module implements (`TOPS_RULE`, matched verbatim), or a
  slab it does not recognise is a `PlanError`, not a plan at z 0.
- **`surface_top()`**: the height under a plan point by `TOPS_RULE`.
- **`DRESS_REFUSED_NO_SURFACE`**: a placement no declared slab holds is
  refused and recorded.
- **`DRESS_REFUSED_STRADDLES_STEP`** and `footprint_step()`: a placement whose
  footprint circle (the equal-area radius the exclusion test already uses)
  reaches a surface more than `STEP_TOLERANCE_M` (5 mm) above or below the
  one at its origin is refused. With the height alone, 9052's replan still
  had 26 origins exactly on the cross street's kerb lines -- the cluster
  scatter clamps strays onto their zone's edge, 784 of 4,948 orders sit on
  one -- where the band and the road both hold the point and float noise
  picks the top. A rise is tested exactly; a drop is sampled at 16 rim
  points, which can miss an overhang shallower than r(1 - cos(pi/16)), under
  2 mm at this layer's radii. 5 mm is the tolerance the heights were measured
  against, not a number derived from the art.
- **`audit(manifest, tops=...)`** reports `DRESS_OFF_SURFACE` for an order
  whose pos[2] is not the top under it. The manifest schema is closed, so the
  slabs are passed in; the CLI passes them.

### Changed
- `version.py` says 0.22.0. It had stayed at 0.21.0 through 0.21.1, so the
  manifests 0.21.1 wrote were stamped `patina 0.21.0`.

### Notes
- Measured through the pipeline's stages on scratch copies of cold run
  9052 (Lot 0.72.0 `site_surfaces` -> this planner -> Level Factory's
  `dressing_scene` writer, swapped into a copy of the walk package on Lot
  0.71.0 geometry): 4,690 instances, 0 more than 5 mm off the slab under
  them in the Lux-applied scene (`ground` 0/3,206, `sidewalk` 0/1,432,
  `wall_base` 0/52). Refused: 257 straddling a step (`sidewalk` 173, `road`
  52, `open` 20, `perimeter` 10, `path` 1, `wall_base` 1), 362 exclusions,
  404 instance budget. The same stages on 0.21.1: 4,948 instances, all at
  z 0, 2,587 more than 5 mm off.
- A refused placement draws no yaw, so the orders after it in the same zone
  take different assets and scales from the ones 0.21.1 would have written.
  Positions are drawn before any refusal and do not move.
- Tests: a placement on a raised band stands on its top; where slabs overlap
  the higher top wins, checked against an independent test; a yawed slab
  holds points along its own axis; the height is read at the rounded
  position; surfaces with no `tops`, another `tops_rule`, or a malformed slab
  are refused; a candidate over no surface is refused and recorded; audit
  catches an order at z 0 on a band; a placement on a kerb line is refused
  and the same placement 1 m inside the band is placed on it; footprint_step
  sees a rise, an overhang, flat ground on either side, and the plate's edge.
  All twelve fail on 0.21.1.

## [0.21.1] - the clutter asset set is tracked

### Added
- `patina/asset_sets/ground_clutter.json`: which Zoo species dresses which
  surface family (`pebble`, `rubble_frag` -> `ground_clutter`; `weed_tuft`
  -> `ground_cover`; `litter_scrap` -> `litter`). This is the `--asset-sets`
  input `surface_dressing` has required since 0.21.0, and it existed only as
  untracked scratch in the factory root's `_dress/` from 2026-08-19 (roadmap
  110). Level Factory 0.68.0 reads the species off it for the Zoo clutter
  build and hands it to the dressing pass, so one file decides both what the
  layer is built from and what it is planned with.

## [0.21.0] - surface_dressing has a command line, and takes its catalogue from measurements

### Added
- **`python -m patina.surface_dressing --surfaces ... --metrics ...
  --asset-sets ... --out ...`**, so a level_factory job can invoke the planner
  the way it invokes every other tool. `--audit` re-checks the finished
  manifest and exits non-zero on any finding.
- **`catalogue_from_metrics()`** builds the asset catalogue from
  `tools/shape_metrics.py --json` output -- measured heights, measured plan
  hull areas, real triangle counts off the built GLBs. A genome declares a
  RANGE; the honesty rule is about the object that actually exists.
  An asset the `asset_sets` map does not name is SKIPPED rather than guessed
  at: the family decides which zones an asset may dress, and inventing one
  would put litter on a gameplay path because nobody said not to.

### Notes
- The budget arguments accept the words `auto` and `none` as well as integers,
  because an adapter passes strings and `int("auto")` is a stack trace at job
  time rather than at configuration time. Tested.
- The full chain now runs from a shell, which is what an adapter will do:

      shape_metrics.py --dir <built glbs> --json  >  metrics.json
      site_surfaces.py <site spec>        --out   >  surfaces.json
      -m patina.surface_dressing --surfaces --metrics --asset-sets --out

  On the real coldrun_pawn_job site: 83 zones, 6 exclusions, 3,948 instances,
  511,712 triangles, 4 unique meshes, audit clean.

## [0.20.0] - Layer 3: planning surface dressing for a whole site

Patina's dressing pass has always been Layer 2 -- gutters, edge strips, curbs
bolted onto ONE BUILDING before assembly, with no concept of a site.
`docs/SURFACE_DRESSING.md` section 2 puts Layer 3 here too: after the
functional shell lock, dressing the ground and the seams of the whole place.

### Added
- **`patina/surface_dressing.py`** — consumes the zones, exclusions, capsule
  and bands that `lot/site_surfaces.py` emits plus a catalogue of built
  assets, and produces a complete `surface-dressing/1` manifest
  (`level_factory/schemas/surface_dressing.v1.json`).

  Both gates are enforced when the plan is MADE, not when it is validated. A
  planner that emits an illegal placement and leaves a downstream gate to
  catch it has produced a plan that cannot ship and spent the whole pipeline
  finding out.

      honesty    in_traversed_space AND height_m > unassisted_step_max AND
                 collision_policy == "none"  ->  refused. The number arrives
                 in the capsule block; this module never re-derives it.
      coverage   a zone's occluded fraction may not exceed
                 1 - surface_visibility.

  Density and visibility compose rather than compete: visibility decides the
  ALLOWANCE (gameplay_path 0.90 -> 10% may be hidden), density decides how
  much of that allowance is SPENT (low 0.35 ... very_high 1.0). Density can
  therefore never breach a budget; at most it fills it.

  `catalogue_entry` requires a MEASURED height and a triangle count, and
  refuses an alpha-cutout or translucent asset that does not declare how much
  of its footprint it actually hides. Opaque is the only case that is a fact
  rather than a measurement.

  `audit()` re-checks a finished manifest against both gates by summing the
  orders, not by reading the planner's own running total -- a check that
  reads the planner's arithmetic only proves the planner can add up.

- **`tests/test_surface_dressing.py`** — 33 tests. Every gate is falsified by
  constructing the case it is supposed to stop.

### The cost gate, which the other two never bounded
Run on the real `coldrun_pawn_job` site with real measured assets and no cost
budget, the coverage rules alone authorised **361,412 placements and 46.8
million triangles** — every one of them legal, every gate green. "How much of
the floor may I hide" and "what may this cost" are different questions and
only one of them was being asked.

And triangles are not what binds. This layer is a handful of meshes repeated
thousands of times, which is the case instancing exists for: as a MultiMesh,
ten thousand pebbles are one draw call. What binds is the INSTANCE count —
per-instance transforms, culling, and the manifest itself. So `plan()` takes
`instance_budget` and `tri_budget`, either may bind, both are allocated per
zone in proportion to that zone's own coverage allowance, and the cost block
reports instances, triangles and unique meshes together. The same site now
plans at 3,948 instances / 511,712 triangles / 4 meshes, with the audit clean.

### Fixed before it shipped
- **A per-zone candidate cap made density a function of how the site was
  chopped up.** 73 path segment zones took up to 400 candidates each while the
  7,973 m2 of open ground took 400 in total, so the site came out densest
  exactly where the guide says it should be sparsest. Budgets are now shared
  by area.
- **`ground` and `floor` in the anchor-cause table shadowed the exposure
  lookup**, collapsing a whole site's causes to two values. A cause that never
  varies is not a cause; the guide's rule 3 is that unexplained scatter reads
  as procedural noise.
- **The cost budgets truncated the candidate list silently.** Nothing reached
  `keep_out`, which is the exact failure the module's own docstring warns
  about: a planner that quietly places less than it was asked for is
  indistinguishable from one that had nothing to place. A clamp now reports
  itself, with the numbers, whether or not the in-loop refusal fires.

### Notes
- Determinism is `determinism.rng_for(seed, "surface_dressing", zone_id)`, so
  a zone's scatter does not move when another zone changes. With
  `instance_budget="auto"` the COUNT still scales with total dressable area,
  which is intended: a bigger site gets a bigger budget. The sequence is
  stable; only where it is truncated moves.
- This module places nothing in a scene. The level_factory job and the
  Presentation consumer are still to come.

## [0.19.0] - 2026-08-02

### Fixed
- **A slot's `dims` and `scale` are one measurement, not two factors**
  (`patina/slots.py`, `framing.py`, `paneling.py`). DC authors a wall
  remainder (`size_mod == "end"`) as a unit box and rides the real size on
  the per-slot scale, so `fit.dims` and `transform.scale` both encode the
  same box. Nine sites multiplied them, squaring every remainder wall: a
  3.7 m storey became 13.69 and put a `gutter_run` at z 12.61 on a
  building whose roof is at 7.4. Collapsed into one documented
  `Slot.size()`. Measured across two shipped manifests — 387 slots, every
  `end` slot has `scale == dims`, every `full` slot has `scale ==
  (1,1,1)`, zero exceptions. On `category5_baie_dore_001`, cover z_max
  drops 12.62 → 7.62 against a highest module top of 8.00; 45 of 1988
  orders move and 15 phantom panel rows disappear.
- **Ground dressing measured from the foundation, not the street**
  (`patina/anchors.py`). A wall segment is bucketed by wall *plane*, so
  every storey of a facade collapses into one row spanning `z_lo -4.30`
  (below the basement slab) to `z_hi 9.00` (the parapet) — 13.30 m
  against a walkable range of 12.00. `wall_base` and `ground_edge` emitted
  at `z_lo`, so every base course and curb was buried 4.30 m under the
  street. Both now take storey 0's floor plane from the slot manifest
  (`SlotManifest.storey_base`), which is 0.00 on every building measured.
  `roofline` is unchanged: a parapet cap a metre above the roof slab is
  architecture. Shells with no slots.json fall back to the segment
  minimum, which is correct for the single-storey shells that carry no
  manifest, and the CLI says which rule it used
  (`anchor_ground_plane`).
- **Conduit ran to nothing.** `exterior_light` (cover `conduit_run`) was
  placed at 0.75 of the segment's full height — 5.67 m, a third-storey
  height — on `light_spacing` centres, referring to no light at all. DC
  already derives every exterior wall pack and the storefront sign from
  the real door openings and ships them in `<name>.lights.json`, so a
  conduit now runs to the fixture it feeds: 60 invented runs at
  4.77..5.67 become 4 real ones at 2.45..2.85. For this kind `size` is
  the run length (ground plane → fixture) rather than a footprint hint,
  and `tag` carries the DC anchor id so a conduit is traceable to its
  light. With no light manifest, none are emitted — a conduit runs *to*
  something.
- `--extract-family IMAGE[:K]` split a Windows path on its drive-letter
  colon: `partition(":")` read `C:\Temp\ref.jpg:5` as image `C` and count
  `\Temp\ref.jpg:5`, and `int()` raised. Posix paths carry no drive
  letter, so the suite was green on Linux and red on the machine that
  runs the tool. Splits on the last colon now, and only when digits
  follow.

### Added
- `Scene.lights` / `gltf_io._load_lights` — the `<name>.lights.json`
  sidecar, read on the same convention as slots and gameplay. Patina
  still emits no lights; it reads these so dressing that depends on a
  fixture can be placed against the real one.
- `anchors.blender_to_canonical` — DC Blender Z-up into the frame the
  anchor math runs in, *composed* from `slots.blender_to_patina` and
  `_up_to_z` rather than written out, so it cannot drift from the passes
  it must agree with. For a DC export the vertical coordinate is
  unchanged, which is what lets a ground plane come straight off the slot
  manifest.
- `Slot.base_z` / `SlotManifest.storey_base` — a module's own floor plane
  and a storey's, in one place. `framing._base_z` now delegates.

## [0.18.0] - 2026-07-10

### Added
- **Facade kit** (`patina/framing.py`; `--frames`, `--gutters`,
  `--pilasters`, each with `--dressing` + a DC slots.json) — the rest of
  the architectural-depth bucket, as thin non-collision covers:
  - `--frames`: one `frame` order per doorway/window opening. DC exports
    the exact opening rect (`fit.openings`: width/height/sill), so frames
    target the hole, not the module — a 3.0x3.0 garage door and a
    sill-lifted window each get a correctly sized, correctly centred
    picture frame. `opening_kind` and `frame_width` ride the order.
  - `--gutters`: a `gutter_run` per exterior wall slot just under the
    roofline; sections join at module seams like real gutters.
  - `--pilasters`: a vertical `pilaster` at each exterior wall slot's left
    module seam — columns at sixth-gen fidelity. `size2` = [width, wall
    height].
- Trim atlas gained `frame` and `pilaster` pieces (regions shift; the
  atlas + manifest are always emitted as a set, so nothing desyncs).
- All three share the panel-fields contract: slots.json required,
  spec-space only, deterministic, zero geometry from Patina. Verified on
  gs_corner_station: 13 frames / 70 gutters / 70 pilasters joining 509
  panels + 211 anchor covers (873 orders). Pairs with **Zoo v0.26.0**.

## [0.17.0] - 2026-07-10

### Added
- **Panel fields** (`patina/paneling.py`, `--panel-fields` with `--dressing`):
  the highest-ROI facade cover. Every exterior wall slot gets a uniform grid
  of thin proud panel orders (cover `panel_field`, 3cm proud via Zoo) — same
  collision, and the gaps between panels give a flat greybox wall its shadow
  lines. Rides the modular alignment instead of geometry analysis: DC's
  slots.json already partitions facades into wall/doorway/window slots, so
  openings never need hole math — a doorway simply isn't a wall slot.
  Requires slots.json (skipped with a note otherwise) and spec-space
  manifests (refuses `--anchor-patina-space`).
- Orders carry `size2` = [face width, face height] (exact grid cells;
  `size` stays the scalar width so a pre-0.24 Zoo degrades to a strip
  instead of crashing). `--panel-size` (default 1.2m) / `--panel-gap`
  (default 3cm). Deterministic: grids are arithmetic; `seed_offset` from
  `(seed, "panel", slot_id, col, row)`. Budget-clamped (2000 orders).
- `dressing_manifest` gains `extra_orders` for pre-built spec-space orders.
- Verified against the real gs_corner_station shell: 509 panel orders
  across 70 exterior wall slots, joining the existing anchor covers.
  Pairs with **Zoo v0.24.0** (`panel_field` cover kind).

## [0.16.0] - 2026-07-10

### Added
- **Photo projection** (`patina/photo.py`, new `patina-photo` CLI): rectified
  photo regions as texture sources. One angled reference photo of a real
  storefront becomes several period-correct textures: mark each region's four
  corners (TL,TR,BR,BL) in a savable JSON spec, and Patina
  perspective-rectifies the quad, box-downscales at 2x supersampling,
  posterizes, optionally locks to a colour family (extracted from the same
  photo via the existing `families.extract`, so procedural slots harmonize
  with the photo textures), and optionally makes wall/floor regions
  seamlessly tileable (half-offset + blend band).
- Output drops straight into existing machinery: `<out>/<key>.png` per
  region, `<out>/overrides.json` ready for `--overrides` (marked
  `"process": false` — regions are already crushed, and `import_tile`'s
  square centre-crop would destroy non-square signs), `<out>/family.json`
  when extracted, and `<out>/photo_manifest.json` with the source sha256 +
  spec echo for traceability.
- Honest-seams position: choosing *which* rectangle of the world becomes a
  texture is human judgment and lives in the spec; everything after the
  corners is mechanical. Deterministic — pure function of source bytes +
  spec, no randomness.

## [0.15.0] — 2026-07-09

Surface mottle — the mid-frequency tonal breakup that stops big flat walls
reading as one uniform tone. The last texture-density gap after the look-dev
pass showed the grade was carrying the walls but the surfaces were too clean.

### Added
- **`--mottle`** (+ `--mottle-scale`): coherent per-vertex value variation from
  world position, summed over 3 octaves so adjacent vertices move together
  (weathered surface, not random speckle). Multiplier centred on 1.0 — only
  nudges value, never invents hue, so neutrals stay neutral. Unlike height-grime
  (a floor-ward ramp) and edge AO (darkens borders), mottle varies the *interior*
  of a face. Needs densify for vertex resolution (walls: 2880 → 13k+ verts →
  mottle reads). `~0.2-0.3` typical; `0` = off, byte-identical.

### Why it matters
- Confirmed via the look-dev harness (SkyMint dusk/blue-hour shots): at correct
  exposure the building holds up, but the big wall faces read flat. Mottle raises
  within-face value spread (0.097 → 0.108 at 0.30) so the surface has life once
  Lux light rakes across it. 190 tests.

## [0.14.0] — 2026-07-09

Arcade plane separation — punchy saturated near vs washed-out far.

### Added
- **`apply_separation`** + **`punch` depth preset** (`--depth punch`): the near
  field (low recession) gains saturation while the far field (high recession)
  desaturates and washes toward a light haze. Leans hard into plane separation
  for arcade/PS2 pop, on top of the atmospheric pass. `near_sat` / `far_wash`
  options; multiplicative near-punch so neutrals stay neutral.

### Honest scope
- This is a **view-independent vertex bake**, so it separates a building's *own*
  near/far faces — strong across a full level with deep sightlines, subtle on one
  compact shell (on `gs_corner_station` the recession weight only spans 0.65–1.0,
  so the building sits mostly in one plane). The **strong, camera-relative** far
  wash is Lux's runtime distance fog — see the `delco_arcade` Lux preset
  (Lux 0.9.2). Patina bakes the per-surface cue; Lux does the per-camera wash.
- Opt-in; `off` and byte-identical when unused. 187 tests.

## [0.13.1] — 2026-07-09

Pipeline smoke tests — prove the whole art-pass flow is repeatable before
building levels on it.

### Added
- **`smoke_offline.py`** — runs every stage that doesn't need Blender/Godot
  (DC manifest → Patina full art-pass → output integrity → cross-tool contracts
  → composite headroom) and *asserts* each output is valid: collision tri-count
  unchanged, vertex colour in range and not crushed, dressing covers all
  non-collision, instances/dressing schemas correct, the Zoo planner accepts the
  dressing manifest, and the preview reports OK. Fails loudly at the exact stage
  that drifts. Verified it both passes on a real `gs_corner_station` build and
  fails on missing/broken input.
- **`smoke_walk.ps1`** — the on-machine half: DC → Zoo build-kit → Patina → Zoo
  dress with a hard pass/fail gate after each stage (stops with a clear message
  instead of cascading), then opens Lux. Resolves Blender/Godot exes from their
  folders; cleans stale output first.

### Fixed
- The manifest now records the **`depth`** preset applied (it was applied but
  not recorded — caught by the smoke test). Downstream tools reading the
  manifest now know the depth used.

## [0.13.0] — 2026-07-09

The "look preview" release — see the composite before the engine walk.

### Added
- **`--preview`** (`patina/preview.py`): a small software rasteriser that
  renders the composite look — `band_light(N·L) × vertex_colour × albedo` with
  a Lux-like key light, banded diffuse and cool ambient — to `<out>.preview.png`.
  It stands in for Lux just enough to be honest about the multiply, so the
  over-darkening risk (three multiplicative bakes then Lux's own `× vertex_colour`)
  is visible offline.
- **Headroom report**: prints luma mean / p10 / crushed-fraction and an
  `OK` / `TOO DARK — reduce bake strengths` verdict. "Too dark" is now a number,
  not a vibe. Calibrated so bright bakes pass and a compressed-banding dark bake
  (mean < 0.25 or >12% near-black) flags.

### Finding
- On a real `gs_corner_station` delco build the full stack (family + `--depth lux`
  + `--slot-variation`) sits at luma mean ~0.54 with zero crushed pixels — barely
  darker than minimal. The over-darkening risk is not materialising on delco; the
  bakes are conservative. The preview makes that checkable per build.

### Notes
- Pure numpy, no bpy/Godot. Deterministic. Off by default. Does not replace the
  engine walk — it makes it faster and catches the darkening failure early.

## [0.12.1] — 2026-07-09

Reconcile the depth pass with Lux (the Godot runtime look framework), after
reading how Lux composes with the baked vertex colour.

### Fixed
- **Saturation gain is now multiplicative, not additive.** On a *neutral* grey
  (Zoo's default concrete) the additive gain invented a red hue from HSV's
  undefined-hue-at-zero — it would have tinted plain surfaces red in shadow.
  Multiplicative gain amplifies the chroma already present and leaves neutrals
  neutral (pinned by `test_neutral_stays_neutral_under_saturation`).

### Added
- **`lux` depth preset** — composes with Lux instead of fighting it. Lux does
  runtime light, so it owns shadow *colour* (`shadow_tint` / palette) and
  distance *fog*; the `lux` preset bakes only what Lux can't derive: shadow
  *saturation* (form, `shadow_warm=0`) and gentle *height* recession
  (`atmos_radial=0`, distance deferred to fog). `delco`/`exterior` stay for the
  standalone (no-Lux) case where Patina's vertex colour is the final look.
- **`docs/LOOK_PIPELINE.md`** — the full cross-tool composition chain (DC → Zoo
  → Patina → Lux), who owns which cue, and the reconciliations.

### Note
- These are the correct division under Lux: bake view-independent *form*, defer
  light-dependent *colour* to the renderer. Depth still off by default;
  byte-identical when off.

## [0.12.0] — 2026-07-09

The "depth & cohesion" release — colour-theory shading instead of flat value
multiply. Distilled from Arne Jansson's PSG tutorial and the depth/colour-theory
sources: shadows should gain *saturation* (not just darkness), receding surfaces
should drift toward a cool atmospheric grey (plane separation), and texture
should alternate warm/cool (not only brightness). A PS1-era look has no
real-time GI, so these depth cues are baked into vertex colour and tiles on
purpose — a deliberate departure from a strict unlit PBR albedo.

### Added
- **Depth pass** (`patina/depth.py`, `--depth PRESET`): layered over the nuance
  vertex-colour pass.
  - *Saturated shadow gradient* — the AO/grime shadow weight now drives a
    saturation gain and a warm/cool hue bias into shadow, not just value
    darkening (Jansson's "saturated gradients").
  - *Atmospheric recession* — a height + radial-distance weight pulls receding
    surfaces toward a cool desaturated target, separating foreground/background
    planes.
  - Presets `delco` / `exterior` / `off`; a theme may declare `"depth": "delco"`.
- **Texture temperature** (`patterns.py`, pattern `temp` 0..0.5): per-cell
  jitter can nudge warm/cool, not only brightness, so tiled surfaces read richer
  (Jansson's warm/dark alternation).

### Unchanged by construction
- Depth is opt-in: no `--depth`, no theme `depth`, and `temp` absent → vertex
  colour and tiles are byte-identical to v0.11 (pinned by
  `test_depth_off_byte_identical` and `test_pattern_temp_zero_identical`).
- Deterministic. Verified on delco: mean vertex saturation rises (shadows gain
  colour) with depth on, and the warm/cool spread widens with `temp`.

### Companion (Zoo 0.22.0)
- Zoo bakes an optional **directional ambient** (cool-from-above / warm-fill-
  below) into architectural-module vertex colour, so modules read with form
  before Patina runs — the same depth-from-ambient cue on the geometry side.

## [0.11.0] — 2026-07-09

The "trim sheets + dressing" release — the texture half of Zoo-built facade
dressing. Patina supplies a trim atlas and per-anchor non-collision cover build
orders; Zoo builds the geometry. Closes the loop the v0.8 anchors opened.

### Added
- **Trim-sheet atlas** (`--trim-sheet`, `patina/trim.py`): a family-locked
  posterized atlas of trim strips — roof edge, panel seam, pipe run, corner
  guard, foundation, conduit, flashing — packed into one power-of-two PNG with
  a per-piece UV-region map (`<out>.trim.png` + `<out>.trim.json`). Reuses the
  pattern generators and the family lock, so trim shares the building palette.
  The Q2/Steed trim sheet, done as texture (Patina's lane).
- **Dressing manifest** (`--dressing`, with `--anchors`): turns anchors into
  Zoo build orders — per anchor, a `<out>.dressing.json` record with the trim
  piece, its UV region, the position/normal (in the same DC Blender Z-up space
  as the anchors when a slots.json is present), a suggested cover kind
  (`edge_strip` / `base_course` / `curb` / `conduit_run`), and
  `collision: none`. Patina places + skins; Zoo builds the cover mesh.

### Guarantees / scope
- Patina still ships **zero geometry**: the trim sheet is a PNG, the dressing
  manifest is JSON. Covers are marked non-collision so the greybox collision is
  never touched. Deterministic; family-locked; opt-in.
- The Zoo consumer (a recipe that reads `dressing.json` and builds
  `collision: none` cover meshes) is a **written contract**
  (`docs/DRESSING_CONTRACT.md`), not yet implemented in Zoo — the Patina half
  ships tested; the Zoo recipe and the in-engine walk remain.

## [0.10.0] — 2026-07-09

The "per-slot variation" release — completes the modular alignment by targeting
individual slots, not just surface roles. DC's art-pass docs name per-instance
colour as the #1 lever against the "same module everywhere" failure mode,
driven deterministically from the seed; this is that lever.

### Added
- **Per-slot variation** (`--slot-variation`, `patina/slots.py`): with a DC
  `slots.json`, Patina computes a deterministic per-slot brightness factor
  (seeded by `slot_id`) and (a) **bakes it into the monolith's vertex colour**
  for faces spatially assigned to each slot (nearest role-matching slot centre),
  so identical `wall_delco_01` copies stop reading as mechanically repeated, and
  (b) **emits `<out>.instances.json`** — per-slot `{color, custom_data}` records
  in DC's placements `instance` shape, for the instanced-bake target to feed
  Godot's MultiMesh per-instance buffers. Same variation, both the monolith and
  instanced paths.
- `--slot-variation-strength` (default 0.12) tunes the jitter; the manifest
  reports faces varied + instance count.

### Guarantees
- Opt-in and family-locked: variation colours come from the reconciled family,
  so breaking repetition never breaks cohesion. Deterministic (seed + slot_id);
  the instance records are byte-identical across runs. Off by default and
  requires a slots.json, so all prior output is unaffected.

## [0.9.0] — 2026-07-09

The "modular alignment" release. Patina predated the DC/Zoo modular setup;
this brings it into alignment with Deli Counter 0.64 and Zoo 0.20 on three
fronts: the slot manifest, the coordinate contract, and the aesthetic seam.

### Fixed (the core misalignment)
- **Up-axis was hard-coded to Z.** A real DC `.glb` loads **Y-up** (standard
  Blender-Z-up → glTF-Y-up export conversion); Patina's own example shells
  were Z-up, which masked the bug. `surfaces.classify`, vertical banding,
  height-grime, and anchors all read the wrong axis on real DC data —
  classify was calling north-facing walls "floor." Patina now **detects the
  up axis** (`slots.detect_up_axis`, the min-range axis of a wide/shallow
  building) after bake and threads it through every height-dependent pass.
  Legacy Z-up shells (up_axis=2, the default) are byte-identical.

### Added
- **Reads `<name>.slots.json`** (`patina/slots.py`, `SlotManifest`): DC's
  modular manifest (slot_manifest 1.x) — per-module records keyed by
  `slot_id`, with role, `current_ref`, fit, and Blender-Z-up transforms.
  Loaded automatically as a sibling of the `.glb` (like `gameplay.json`);
  `--no-slots` opts out. This is the "per-part targeting instead of
  whole-mesh" DC's art-pass docs call for.
- **The shared coordinate contract.** `blender_to_patina` / `patina_to_blender`
  implement the exact glTF axis conversion, so anything Patina emits
  round-trips with DC's markers/slots. With a slots.json present, `--anchors`
  now emits in **DC's Blender Z-up space** (verified to overlay the slot
  extent — roofline at the true story height) and tags the sidecar with
  `building_id`; `--anchor-patina-space` keeps the old frame.
- **The Zoo aesthetic seam.** `slots.reconcile_family` maps a module theme to
  the Patina family sharing its palette (`delco` → `delco_faded`), so when a
  DC build carries a delco slot manifest Patina auto-locks to the matching
  family — Zoo's baked base style and Patina's nuance describe one world
  instead of fighting. Explicit `--family`/`--skin` still win.
- Manifest records a `slots` alignment block (version/building_id/theme/count;
  optional, schema back-compatible).

### Unchanged by construction
- No slots.json + Z-up geometry → every prior release's output is
  byte-identical (149 tests, incl. the legacy-shell paths). Alignment is
  additive and auto-detected.

## [0.8.0] — 2026-07-09

The "placement anchors" release — the honest way to unlock the geometry-bearing
art-pass items (roofline units, wall props, exterior lights, ground detail)
without a texture tool ever generating a mesh. Patina decides *where* dressing
goes from geometry it already understands; downstream tools (Lux for lights,
Zoo or a dressing kit for props) supply *what*.

### Added
- **Placement anchors** (`patina/anchors.py`, `--anchors`): a
  `<out>.anchors.json` sidecar of seeded, world-space placement points, each
  with a kind, surface normal, and size hint. Kinds derive from exterior-wall
  geometry: `roofline` (top edge, up-normal — HVAC/vents/silhouette breakers),
  `wall_base` (foot, outward normal — dumpsters/boxes/AC units),
  `exterior_light` (upper wall — lighting anchors), `ground_edge` (wall-meets-
  ground — curbs/weeds/covers). `--anchor-kinds` filters; density and a
  per-kind budget clamp mirror the decal pass.
- Anchors follow the established sidecar convention (like DC's `.lights.json`
  → Lot → Lux bridge) and the decal coordinate contract (baked world metres).
  A summary (`sidecar` + per-kind `counts`) is recorded in the manifest
  (optional block; schema back-compatible).

### Guarantees
- **Zero geometry, zero collision impact.** Anchors are visual-only metadata;
  the styled `.glb` is byte-identical whether or not `--anchors` is set (pinned
  by `test_cli_anchors_do_not_touch_geometry`). Off by default — it's a handoff
  artifact, not styling. Deterministic per seed.

### The division of labour, stated
Patina stays texture/colour-only. For the art-pass wishlist's geometry items,
Patina's contribution is *placement*, emitted here for geometry tools to fill —
not mesh generation inside Patina. This closes the loop opened by the v0.7
deferral note.

## [0.7.0] — 2026-07-09

The "vertical banding" release — material variation by world height, the
highest-ROI *no-geometry* art-pass move (Quake/Half-Life/PS2 wrapped the
greybox rather than rebuilding it). A wall reads as brick-base / painted-body /
flashing-cap instead of one flat material, and it costs zero geometry: bands
are chosen per vertex by world height and baked into vertex colour, so the
original collision/gameplay shell is untouched.

### Added
- **Vertical bands** (`patina/banding.py`): per-vertical-role band specs
  (`wall` / `exterior_wall` / `trim`), each a list of `{to: fraction, tint:
  hex}` boundaries over the shell's global height. Applied in the nuance
  vertex-colour pass, so in procedural mode the band tint multiplies the tiled
  albedo (shared pattern, banded colour).
- **Theme `bands` block** (validated at load); `delco_1997_gas_station` ships
  oxblood-brick base / concrete body / brass-flashing cap.
- **Skin auto-bands**: a generated skin derives bands from its 60/30/10
  (base = a shadow, body = a base, cap = the accent), so `--skin` walls band
  for free and stay in-family.
- Band colours **lock to the family** like every other tint; `--no-bands`
  disables. Active bands reported in the run summary.

### Unchanged by construction
- No declared bands (the `default` theme) -> the pass is a no-op and vertex
  colour is byte-identical to v0.6 (pinned by
  `test_no_bands_flag_and_default_identical`).

### Deferred (honest scope)
- **Per-band *pattern*** (brick vs concrete texture, not just colour) needs
  height-normalised UVs or a per-band material split — the geometry/engine
  risk class Patina holds until the addon gets its in-engine walk. Bands
  currently vary colour; the shared pattern is tinted per band.
- Most of the referenced art-pass list (surface panels, architectural depth,
  props, roofline units, utility networks, silhouette breakers) adds thin
  *geometry* and stays out of a texture tool. The natural next Patina role
  there is **placement annotation** (emit light/prop/roofline anchors into the
  manifest for Lux / Zoo / a dressing kit to fill), not mesh generation.

## [0.6.0] — 2026-07-09

The "procedural skin" release — generate a structured look from a few hex
colours + a style, the counterpart to v0.5's extract-from-photo. Uses the same
colour theory as GabagoolStudios' Color Swatch add-on: a **60/30/10** palette
(dominant / secondary / accent), each expanded into **shadow / base / light**.

### Added
- **Skin generator** (`patina/skins.py`): `generate(style, seeds)` builds a
  full 60/30/10 shadow/base/light palette from 1-3 hex seeds and a style.
  Seed 0 sets the dominant hue; seeds 1-2 pin secondary/accent; missing slots
  are filled by the style's **harmony** (monochrome / analogous /
  complementary / triad / split-complementary). Styles (`faded`, `grimy`,
  `neon`, `clean`, `sunbleached`, `nicotine`) carry the saturation/value and
  shadow/light discipline plus a default seed, so `--skin grimy` works alone.
- **`--skin STYLE[:SEEDS]`**: SEEDS = comma hex list *or* a color_swatch
  library / saved-palette json. A generated skin folds into the theme
  (per-role albedo + tint by 60/30/10 area logic — big surfaces get
  dominant/secondary, trim gets the accent) and brings its own family, so it
  locks for cohesion via the v0.5 pass. Applied *before* `--override`, so a
  manual bash still wins.
- **`--skin-from FILE`**: seed from a color_swatch library (liked colours) or
  a saved 60/30/10 palette.
- **Color Swatch interop**: `seeds_from_library` harvests liked hexes
  (tolerant of the JSON layout); `from_swatch_palette` imports a saved
  60/30/10 palette as-authored; `to_swatch_text` exports a labelled block that
  pastes back into the tool. Each run writes `<out>.skin.json` and
  `<out>.skin.txt`.

### Unchanged by construction
- No `--skin` -> nothing changes; the default and delco themes are
  byte-identical to v0.5 (pinned by `test_no_skin_byte_identical`).

## [0.5.0] — 2026-07-09

The "texture families" release. The cohesion in Quake 2 came from *constraint*
— every area reused a small, shared material library, assembled with id's
TextureBuild into texture families (Steed, "The Art of Quake 2"). Patina now
makes a limited shared palette the unit of reuse and locks every surface to
it.

### Added
- **Texture families** (`patina/families.py`): a family is a small ordered
  colour library (+ optional posterize discipline). Binding one runs a
  **palette-lock** pass that quantises every generated tile, imported photo
  and vertex tint to the nearest family colour — cohesion becomes literal
  (a whole level shares N colours), and the family is the reusable unit
  *across* levels.
- **`--family NAME|PATH`**: builtin (`delco_faded`) or a `family.json`. Point
  every shell at the same family and the game reads as one place.
- **`--extract-family IMAGE[:K]`**: derive a K-colour family from a reference
  photo/moodboard via deterministic k-means (k-means++ seeded init, fixed
  iterations), lock to it, and save it. The TextureBuild "build a set from a
  source" move.
- A theme may **declare** a default family (optional `family` field); `--family`
  / `--extract-family` override it.
- Every family run emits reusable artifacts: `<out>.family.json` (the shared
  library — commit it, reuse it everywhere) and `<out>.family.swatches.png`
  (the swatch catalog). The applied family is recorded in the manifest
  (optional `family` block; schema back-compatible).

### Unchanged by construction
- No family bound -> the lock pass is skipped and tiles/tints are
  byte-identical to v0.4 (pinned by `test_no_family_byte_identical`). The
  `default` and `delco_1997_gas_station` themes declare no family, so their
  default output is unchanged; cohesion is opt-in.

## [0.4.0] — 2026-07-09

The "art-bash" release — iterate on a look by swapping *one* surface at a
time instead of regenerating or hand-authoring the whole set.

### Added
- **Per-key overrides** (`patina/overrides.py`): substitute, per material
  key, an `image`/photo, replacement `albedo` colours, a vertex `tint`, or a
  `pattern` spec — layered *over* a theme. Sources, later wins:
  theme < `--overrides FILE` < repeated `--override KEY=VALUE`. An overridden
  key breaks its theme alias, so "just the exterior walls" means just those.
- **`--override KEY=VALUE`**: quick CLI bashing. `KEY=#hex[,#hex...]` recolours
  (albedo); `KEY=path/to/image.(png|jpg|jpeg|webp)` skins the key with a file.
- **`--overrides FILE`**: a *savable* bash session (JSON of
  `{key: {image|albedo|tint|pattern|process}}`) that lives in the project
  next to the theme; relative image paths resolve beside the file. The look
  you bashed your way to is reproducible.
- **Image import** (`palette.import_tile`): external images/photos are
  PS1-ified on import (centre-crop to square, box-resize to tile size,
  posterize) so a phone photo of a real surface becomes a period tile;
  `"process": false` passes authored pixel art through untouched. `byo` mode
  gains the same posterize-on-import path for consistency.
- Manifest records the applied overrides (new optional `overrides` block;
  schema stays back-compatible — not in `required`).

### Unchanged by construction
- No overrides -> tiles on disk are byte-identical to v0.3 (pinned by
  `test_no_override_is_byte_identical`). Default theme unaffected.

## [0.3.0] — 2026-07-08

The "Steed release" — pushing toward Quake-2-era art-department tooling
(reference: Paul Steed, "The Art of Quake 2", Game Developer, April 1998):
structured texture sets for skinning maps, and the first tools for skinning
models.

### Added
- **Structured tile patterns** (`patina/patterns.py`): `tile`, `checker`,
  `block` (running bond), `panel`, `plank` generators — deterministic,
  tileable by construction, posterized, with per-cell colour variety drawn
  from the theme's albedo variants. The generated set finally reads as
  *materials*, not tinted noise.
- **Theme `pattern` block**: per-material-key pattern specs in theme JSON,
  validated at load. The `delco_1997_gas_station` builtin now ships a full
  set (lino tile, drop-ceiling grid, cinderblock courses, panelled interior
  walls, planked trim; tar roof stays noise).
- **Paint templates** (`--templates`): per-material-key calibration sheets
  (metre grid, world scale, axis marks, key label; the generated tile as
  background in procedural mode) written to `<out>.templates/`. Completes
  the `byo` seam into a real paint-over workflow.
- **Start skins** (`--start-skins`, `--skin-size`): Texpaint-style
  triangle-unique multicolour sheets with wire lines, rendered from a mesh's
  *authored* UV0 — the model-skinning workflow's first tool. Meshes without
  UV0 (all Deli Counter greyboxes) are skipped and reported, never faked.
- `CHANGELOG.md` (this file), backfilled.

### Unchanged by construction
- The `default` theme's tiles, tints and file set remain byte-identical to
  v0.2 (pattern RNG streams are keyed `(seed, "pattern", …)`, disjoint from
  the `"palette"` streams; no-pattern keys take the v0.2 code path verbatim).
- Manifest schema unchanged (`0.2.0`); collision/nav/gameplay untouchable as
  ever.

## [0.2.0] — 2026-07-02
- Theme presets (JSON; builtin `default` + `delco_1997_gas_station`, user
  themes by path); `exterior_wall` / `roof` classification via visual-AABB
  heuristic; seeded, area-weighted, budget-clamped decal pass (bashing brief
  phase 1). `default` keeps v0.1.x tints and byte-identical tiles.

## [0.1.1] — 2026-06-25
- Fix reversed triangle winding in densified quad meshes.

## [0.1.0] — 2026-06-25
- Initial release: glTF I/O spine, vertex nuance (densify + procedural
  vertex colour), box-projection UVs, procedural/posterized textures,
  manifest + schema, Godot PS1 shader + addon (first-run-in-engine).
