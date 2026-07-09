# The seams: where human craft takes over

This is the section that keeps the tool honest. Patina is explicit about the two
craft steps it does **not** perform, and is designed to make starting them easy
rather than to fake them.

## Step 3 — mesh art pass (assist, don't replace)

Patina cannot invent what a wall should look like as a building. What it does:

* **Kit-bash hooks.** `shell.patina.json` marks each visual mesh with its role
  and world-space bounds (`kitbash[]`), so a human — or a future kit — can swap
  a plain wall for a detailed modeled piece at the same transform.
* **Clean re-import.** Geometry is grouped and named (Patina preserves node
  names), so a modeler can replace pieces in Blender and re-run Patina without
  losing the styling setup.

* **Start skins (v0.3).** For replacement pieces (or any prop) that carry an
  authored UV0, `--start-skins` renders the Texpaint-style triangle-unique
  sheet so the modeler/painter sees coverage before painting. Greybox shells
  have no authored UV0 and are skipped honestly.

**Explicit non-promise:** Patina ships zero detailed building geometry. The
blockout-plus look comes from *style*, not modeled detail.

## Step 4 — hand-painted textures (stand-in, not forgery)

Patina's procedural/posterized textures are honest stand-ins. When a project
wants real art, **`byo` mode is the seam**: drop hand-painted low-res textures
into a folder, named by surface role —

```
my_textures/
  floor.png
  wall.png
  ceiling.png
  trim.png
```

— and run `patina shell.glb --mode byo --textures ./my_textures`. Patina maps
them via the same box-projection UVs. The tool did the unwrap; the human did the
painting.

Since v0.3, `--templates` makes this seam drawable: each material key gets a
calibration sheet (metre grid, world scale, the current stand-in tile as
background) at the exact scale the box projection will map the painted result
back at — the Q2 practice of painting tiles at known world scale, minus the
guesswork.

## What you get if you stop at Patina

Greybox + vertex nuance + procedural textures + PS1 shader, with no hand
modeling or painting, yields a stylized, atmospheric, recognizably-PS1 space.
Not production-final for a flagship title, but genuinely shippable for game-jam,
prototype, and stylized-indie contexts — precisely because the PS1 aesthetic is
forgiving of low detail by design.

### Art-bash overrides (v0.4): the seam per surface

`byo` is all-or-nothing; overrides make the same seam addressable one key at a
time. `--override KEY=image.jpg` skins a single surface from a photo (PS1-ified
on import) while everything else stays generated; `--override KEY=#hex` and a
saved `--overrides bash.json` session cover recolour/tint/pattern swaps. The
tool still did the unwrap and the scale; the human decides, per surface,
whether the generated stand-in survives. A saved session is reproducible and
rides along in the manifest.

### Vertical banding (v0.7) stays inside the non-promise

Banding adds material *variation* (brick base / concrete body / flashing cap)
with zero geometry — it is vertex colour chosen by world height, so the greybox
collision round-trips untouched. The richer, geometry-bearing art-pass items
(surface panels, architectural depth, props, roofline units, silhouette
breakers) remain out of scope; the intended Patina contribution there is
placement *annotation* in the manifest for downstream geometry tools, not mesh
generation here.

### Placement anchors (v0.8): the geometry seam, without geometry

Patina will not generate building geometry — but it *will* say where geometry
should go. `--anchors` emits world-space placement points (roofline, wall base,
exterior light, ground edge) from the geometry Patina already classifies, in a
sidecar a downstream tool reads to instantiate real meshes. Patina places;
Lux / Zoo / a dressing kit supply the mesh. The anchor sidecar is visual-only
metadata; the styled `.glb` and its collision are unchanged.
