# MODULAR_ALIGNMENT.md

How Patina aligns with the Deli Counter / Zoo modular pipeline (v0.9).

## The setup Patina predated

- **Deli Counter (>=0.37, tested against 0.64)** emits `<name>.slots.json`
  (`slot_manifest_version` 1.x): one record per swappable module — wall
  segment, opening (doorway/window/breach), prop — with a stable `slot_id`, a
  `role`, a `current_ref` (`<type>_<theme>_<style>`), a `fit` block
  (dims/pivot/openings/collision), and a transform in **spec/Blender Z-up raw
  coords** (same space as `gameplay.json`).
- **Zoo (>=0.20)** builds `<role>_<theme>_<style>.glb` modules to fill those
  slots (`zoo_cli --build-kit slots.json --theme delco`) and its architectural
  species carry named styles including `delco` (a base colour + wear scalar).

## The three alignments

### 1. Up-axis (the real bug)

DC exports glTF with the standard Blender-Z-up -> glTF-Y-up conversion, so a
real DC `.glb` loads **Y-up** in Patina's baked space. Patina's own example
shells were authored Z-up, which masked it — `surfaces.classify`, banding,
`_height_grime`, and `anchors` all read axis 2 as "up" and silently mislabelled
real DC geometry (north-facing walls became "floor"). `slots.detect_up_axis`
picks the min-range axis (a building's height is its smallest extent) and every
height-dependent pass takes an `up_axis` argument. Default `up_axis=2` keeps
legacy Z-up output byte-identical.

### 2. slots.json ingestion

`gltf_io` loads a sibling `<name>.slots.json` into `scene.slots`; `slots.parse`
builds a `SlotManifest` of `Slot` records addressable by `slot_id`. This is the
per-part identity DC's `PLACEMENTS_MANIFEST.md` / `SLOT_MANIFEST.md` call the
prerequisite for "Patina / vertex-nuance — per-part targeting instead of
whole-mesh." `--no-slots` disables.

### 3. Coordinate contract + Zoo seam

- `blender_to_patina((x,y,z)) = (x, z, -y)` and its inverse implement the exact
  glTF axis conversion. With a slots.json present, `--anchors` emits in
  `spec/Blender Z-up raw coords` (verified against the slot extent: roofline
  lands at the true story height) tagged with `building_id`, so Lux/Zoo consume
  Patina anchors with the same transform code as DC's own manifests.
  `--anchor-patina-space` forces the old baked frame.
- `slots.reconcile_family(theme)` maps a module theme to the Patina family
  sharing its palette (`delco` -> `delco_faded`, `greybox` -> unstyled). When a
  DC build's manifest names a theme and no `--family`/`--skin` is given, Patina
  auto-locks to it — Zoo's baked base style and Patina's nuance describe one
  world. `register_theme_family` extends the map for new themes.

## Per-slot variation (v0.10)

Reading `slots.json` gives per-module identity by `slot_id`. `--slot-variation`
uses it to break modular repetition — DC's docs call per-instance colour the #1
aesthetic lever:

- Faces are assigned to the nearest role-matching slot centre (slot transform
  converted to Patina space; `module_size * 1.5` radius). DC blockout faces are
  flat-shaded vertex islands, so each vertex takes its face's slot factor cleanly.
- A deterministic factor `slot_factor(slot_id, seed, strength)` modulates those
  vertices' colour (the monolith path) and is emitted as `<out>.instances.json`
  — per-slot `{color, custom_data}` in DC's placements `instance` shape — for the
  instanced-bake target to feed Godot MultiMesh per-instance buffers (the
  instanced path). Same variation, both paths.
- Variation colours come from the reconciled family, so breaking repetition
  never breaks cohesion. Deterministic; opt-in; needs a slots.json.

## Division of labour (who owns the look)

- **Zoo** — module geometry, base material, a flat per-module style colour + wear.
- **Patina** — the rich nuance pass over it: family cohesion (palette-lock),
  vertical banding, decals, PS1 posterize/vertex-jitter, per-slot targeting.
- **DC** — the layout, the greybox, the slot keys, and the manifests.

## Guarantees

- Auto-detected and additive. No slots.json + Z-up geometry -> byte-identical to
  v0.8 (the whole pre-alignment test suite still passes).
- Patina still ships zero geometry and never touches collision.
