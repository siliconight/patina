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
  runs `nuance → uvproject → palette`, writes `shell.patina.glb` +
  `shell.patina.json`. Fully verifiable without an engine.
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
  Modes: `vertex-color` (none) / `procedural` / `byo`.
* **5.4 PS1 shader (Godot)** — vertex jitter, approximate affine, colour-depth +
  dither, vertex-lit + white ambient, distance fog. In-house shader.

## Testing split

* **Offline (CI, no engine):** determinism, UV uniformity, collision untouched
  (name + hash), budget, vertex-colour bounded, manifest validity. All green.
* **In-engine (first-run):** visual walk of the PS1 look; collision/markers
  still walk identically; shader performance at the higher vertex count.

The Python asset pass is fully verifiable offline. The Godot addon and shader
are first-run-in-engine. This doc does not claim otherwise.
