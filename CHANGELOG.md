# Changelog

All notable changes to Patina. Format follows [Keep a Changelog](https://keepachangelog.com/);
versioning follows [SemVer](https://semver.org/).

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
