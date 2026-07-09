# DRESSING_CONTRACT.md

The contract between Patina (v0.11) and a future Zoo dressing recipe. Patina
supplies the trim atlas + placement; Zoo builds non-collision cover geometry.
This is the seam that lets the two tools dress a greybox together without Patina
generating geometry.

## What Patina emits

Running `patina <shell>.glb --anchors --dressing` produces, alongside the styled
`.glb`:

- **`<out>.trim.png`** — a family-locked, posterized trim atlas. Seven strips
  stacked top-to-bottom: `roof_edge`, `panel_seam`, `pipe_run`, `corner_guard`,
  `foundation`, `conduit`, `flashing`. Colours come from the reconciled family
  (e.g. `delco_faded`), so trim shares the building palette.
- **`<out>.dressing.json`** — the build orders:

```json
{
  "schema": "patina-dressing/1",
  "space": "spec/Blender Z-up raw coords",
  "building_id": "gs_corner_station",
  "trim_sheet": "gs_corner_station.patina.trim.png",
  "trim_regions": { "roof_edge": [u0, v0, u1, v1], ... },
  "counts": { "edge_strip": 64, "curb": 64, "base_course": 50, "conduit_run": 33 },
  "orders": [
    {
      "anchor_kind": "roofline",
      "cover": "edge_strip",
      "collision": "none",
      "trim_piece": "roof_edge",
      "uv_region": [0.0, 0.0, 1.0, 0.1406],
      "pos": [-16.0, 10.06, 4.2],
      "normal": [0.0, 0.0, 1.0],
      "size": 0.6,
      "seed_offset": 377990
    }
  ]
}
```

## What Zoo should build (the recipe to write)

A recipe `dress_from_manifest(dressing_json)` that, per order:

1. Reads `pos` / `normal` / `size` — already in **Blender Z-up raw coords** (the
   same space as `slots.json` and `gameplay.json`), so no transform is needed;
   they drop straight into the DC world.
2. Builds a **thin cover mesh** for the `cover` kind:
   - `edge_strip` (roofline) — a capping strip along the top edge; extrude the
     `roof_edge` region a few cm proud.
   - `base_course` (wall_base) — a foundation band at the wall foot from the
     `foundation` region.
   - `curb` (ground_edge) — a low ground-meet strip.
   - `conduit_run` (exterior_light) — a thin conduit up the wall to the light,
     from the `conduit` region.
3. UV-maps the mesh to `uv_region` on `trim_sheet` (the atlas is already
   authored; the recipe only assigns UVs).
4. Marks the mesh **`collision: none`** (the order says so explicitly) — the DC
   greybox collision is authoritative and must not change.
5. Uses `seed_offset` for any per-cover jitter so dressing stays deterministic
   with the rest of the build.

## Invariants

- **Non-collision only.** Every order is `collision: none`. Covers are visual;
  they never alter the gameplay shell. This is the same non-promise Patina holds
  throughout.
- **Space.** `pos`/`normal` are Blender Z-up raw coords when a `slots.json` was
  present (the default for a DC build). With `--anchor-patina-space` they are in
  Patina's baked Y-up frame instead — the `space` field says which.
- **Palette.** The atlas is family-locked, so covers share the building's
  limited palette out of the box — dressing never breaks cohesion.
- **Determinism.** Orders and the atlas are deterministic in the build seed;
  `seed_offset` extends that to any Zoo-side variation.

## Status

- Patina half (atlas + manifest): implemented and tested (v0.11).
- Zoo half (the `dress_from_manifest` recipe): **not yet built** — this doc is
  the spec.
- In-engine walk: still required to confirm covers render correctly over DC's
  collision in Godot (the standing Patina caveat).
