# Patina — Design (condensed)

This is the working condensation of `Patina_TDD.docx`. The TDD is the canonical
spec; this file is what you read to understand the build.

## Pipeline position

The full greybox → stylized PS1 building chain is five steps. Patina owns the
automatable ones and leaves the two craft steps to humans:

1. Blockout (Deli Counter) — **upstream input.**
2. Vertex density + procedural vertex-colour nuance — **Patina (YES).**
3. Mesh art pass (hand-modeling) — human craft (Patina leaves kit-bash hooks).
4. UV unwrap + textures — **Patina partial:** auto box-UV + procedural stand-in;
   `byo` mode is the seam for real hand-painted textures.
5. PS1 render look (Godot shader) — **Patina (YES).**

## Thesis (inherited from Deli Counter)

* **Deterministic / byte-identical** — every effect is a pure function of
  geometry + a fixed seed. Verified by `test_determinism`.
* **Offline, no network, no AI.**
* **Replication-free baked shell** — static meshes + a manifest + a shader.
* **Everything optional / deletable** — separate repo, each stage toggleable.
* **Honest greybox by default** — Patina is opt-in by construction (a different
  tool); minimal/readability-first, never "beauty".

## Architecture

Two halves mirroring Deli Counter:

* **Offline asset pass (Python)** — `patina/`. Reads the `.glb` + gameplay.json,
  runs `nuance → uvproject → palette → decals` under a `--theme` preset, writes
  `shell.patina.glb` + `shell.patina.json`. Fully verifiable without an engine.
* **Godot addon (GDScript)** — `godot/addon/patina/`. Imports the styled `.glb`,
  reads the manifest, assigns the PS1 shader + material params per surface, sets
  white ambient + fog. First-run-in-engine.

The seam between them is a single styled `.glb` plus the small JSON manifest.

### Decision: pure-Python asset pass (not bpy) — please sanity-check

The TDD says "the Python asset pass is fully verifiable offline" and
"byte-identical across machines." To actually deliver both, the asset pass is
built on **pygltflib + numpy + Pillow**, not Blender (`bpy`):

* **Why.** A hand-rolled glTF writer gives true byte-identical determinism
  (Blender's exporter doesn't guarantee that across versions/machines) and lets
  the whole offline test suite run in CI with no engine. It also matches the
  TDD's "different dependency surface" rationale — Patina takes numpy/Pillow, not
  all of Blender.
* **Shared formula, not shared calls.** Deli Counter's `--vertex-nuance` is
  bpy/bmesh. Patina shares its *formula and constants* (the floor/wall/ceiling
  tints, AO 0.45, grime 0.25 over 0.6 m) re-implemented on raw buffers. The
  numbers are the contract; the look matches.
* **The one cost: bevel.** Geometric bevel (insetting hard edges) wants a real
  mesh kernel. In the pure-Python path it's **off by default**; when Blender is
  importable, `nuance.bevel()` bridges to it (the "calls Deli Counter's if
  present, else vendors a copy" path). The edge-cavity term in the vertex-colour
  AO stands in for bevel's light-catch read otherwise — and bevel is the "first
  thing to drop" for budget anyway (TDD §9).

If you'd rather the asset pass *be* Blender-headless (so bevel and selective
subdivision come for free and the toolchain is uniform with Deli Counter), that's
a legitimate fork — it trades byte-identical-determinism guarantees and CI
simplicity for geometry-kernel power. Flag it and it's a contained rewrite of
`gltf_io` + `nuance` against bpy; everything else (surfaces, palette, manifest,
CLI, Godot side) stays.

## Stages

* **5.1 Vertex nuance** — densify visual mesh toward ~0.5–1 m edges; procedural
  vertex colour = per-role base tint × fake-AO (edge/crevice darkening) × height
  grime. Densify is **per-face grid subdivision** (faces are axis-aligned
  rectangles), so density hits the target with no waste on thin faces and stays
  inside the ~150–2500 tri shell budget. Collision untouched; visual only.
* **5.2 Box-projection UVs** — project each face along its dominant world-space
  normal at fixed texel density, into a second UV channel. World space is taken
  *after baking the node transform into vertices*, which dodges the I-5 texel
  smear on non-uniformly scaled faces.
* **5.3 Procedural / posterized textures** — small (128–256 px), tileable,
  posterized to ~16 levels, per-surface-role, deterministic from seed + role.
  Modes: `vertex-color` (none) / `procedural` / `byo`. Since v0.3 a theme may
  request *structured* patterns per material key (tile/checker/block/panel/
  plank; `patterns.py`) — wrap-exact cell grids with per-cell colour variety,
  on RNG streams disjoint from the noise path so `default` stays
  byte-identical.
* **5.3b Painter tooling (v0.3)** — `--templates` emits per-key calibration
  sheets (metre grid at the box projection's world scale) for the byo
  paint-over workflow; `--start-skins` emits Texpaint-style triangle-unique
  sheets from authored UV0 for model skinning. Both deterministic; both
  inputs to human craft, not substitutes (`templates.py`).
* **5.3c Art-bash overrides (v0.4)** — per material key, substitute an
  image/photo, albedo colours, tint, or pattern, layered over the theme
  (theme < `--overrides` file < `--override` flags, field-wise). Theme-level
  substitutions fold into an effective `Theme` before styling; image swaps
  apply to the built tile set (`overrides.py`, `palette.import_tile`). No
  overrides -> byte-identical to v0.3. Applied set recorded in the manifest.
* **5.4 Texture families (v0.5)** — a shared, limited colour library
  (`families.py`). Binding a family runs a palette-lock pass that quantises
  every tile (procedural / byo / override image) and vertex tint to the
  nearest library colour, so a whole level — and every level sharing the
  family — reads cohesively. Families load by builtin name or `family.json`,
  or extract deterministically from a reference image (seeded k-means). A
  theme may declare a default family; CLI flags override. No family ->
  lock pass skipped, byte-identical to v0.4. Family recorded in the manifest.
  This is the id TextureBuild / texture-family idea: cohesion from constraint,
  not per-texture polish.
* **5.5 Procedural skins (v0.6)** — generate a structured look from hex seeds
  + a style instead of extracting one (`skins.py`). Builds a 60/30/10
  (dominant/secondary/accent) palette, each with a shadow/base/light triad,
  using the same colour theory as the Color Swatch add-on. Seeds pin slots;
  harmony (mono/analogous/complementary/triad/split) fills the rest; style
  sets sat/val + contrast discipline. A skin folds into the theme as per-role
  albedo/tint (60/30/10 area mapping) and yields a family for the lock pass;
  applied before overrides so manual bashes win. Interops with color_swatch
  (seed from liked colours, import a saved palette, export labelled text). No
  skin -> byte-identical to v0.5.
* **5.6 Vertical banding (v0.7)** — material variation by world height
  (`banding.py`): per-vertical-role band specs of {to-fraction, tint} over the
  shell's global Z, applied in the vertex-colour pass (band tint multiplies the
  tiled albedo in procedural mode). No geometry — collision untouched. Themes
  declare bands; skins auto-derive them from the 60/30/10; colours lock to the
  family. No bands -> byte-identical to v0.6. Per-band *pattern* (height-
  normalised UVs / material split) is deferred with the geometry/engine class.
* **5.7 Placement anchors (v0.8)** — `anchors.py`, `--anchors`. Patina emits a
  `<out>.anchors.json` sidecar of seeded world-space placement points
  (roofline / wall_base / exterior_light / ground_edge) derived from
  exterior-wall geometry, for downstream geometry tools to fill (Lux lights via
  the `.lights.json`/Lot/Lux convention; Zoo / dressing kit props). Baked
  world-metre coordinates (decal contract), deterministic, budget-clamped.
  Visual-only metadata: the styled `.glb` is byte-identical with or without
  `--anchors`, collision untouched. This is the division of labour — Patina
  places, geometry tools supply the mesh — that keeps the non-promise intact
  while covering the geometry-bearing art-pass items.
* **6. Modular alignment (v0.9)** — `slots.py`. Patina predated the DC/Zoo
  modular setup; this aligns it. (a) **Up-axis detection** after bake: a real
  DC `.glb` is Y-up (glTF export conversion), legacy shells are Z-up; the
  min-range axis of a wide/shallow building is "up", threaded through classify,
  banding, grime and anchors (all previously hard-coded Z). (b) **Reads
  `slots.json`** as a sibling — the modular manifest keyed by `slot_id`, for
  per-part targeting. (c) **Coordinate contract** — `blender_to_patina` /
  `patina_to_blender` implement the exact glTF axis conversion so emitted
  anchors round-trip with DC markers/slots. (d) **Zoo seam** —
  `reconcile_family` maps a module theme to the Patina family sharing its
  palette (`delco` -> `delco_faded`); Zoo owns geometry + base style, Patina
  owns the nuance pass. Additive/auto-detected; Z-up + no-slots byte-identical.
* **6.1 Per-slot variation (v0.10)** — `--slot-variation`. Faces are assigned to
  the nearest role-matching slot centre; a deterministic per-slot factor
  (seed + slot_id) modulates their vertex colour (monolith) and is emitted as
  `<out>.instances.json` per-slot color/custom_data in DC's placements shape
  (instanced bake). Family-locked so repetition-breaking keeps cohesion. Opt-in;
  needs a slots.json.
* **7. Trim sheets + dressing (v0.11)** — `trim.py`, `--trim-sheet` /
  `--dressing`. A family-locked posterized trim atlas (roof edge / panel seam /
  pipe run / corner guard / foundation / conduit / flashing) with a per-piece UV
  map, plus a dressing manifest that turns anchors into Zoo non-collision cover
  build orders (trim piece + UV region + Blender-space position + `collision:
  none`). Patina supplies texture + placement; Zoo builds geometry. Zero geometry
  in Patina; the Zoo consumer is specced in docs/DRESSING_CONTRACT.md.
* **5.4 PS1 shader (Godot)** — vertex jitter, approximate affine, colour-depth +
  dither, vertex-lit + white ambient, distance fog. In-house shader.

## Testing split

* **Offline (CI, no engine):** determinism, UV uniformity, collision untouched
  (name + hash), budget, vertex-colour bounded, manifest validity. All green.
* **In-engine (first-run):** visual walk of the PS1 look; collision/markers
  still walk identically; shader performance at the higher vertex count.

The Python asset pass is fully verifiable offline. The Godot addon and shader
are first-run-in-engine. This doc does not claim otherwise.
