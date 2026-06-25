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

## What you get if you stop at Patina

Greybox + vertex nuance + procedural textures + PS1 shader, with no hand
modeling or painting, yields a stylized, atmospheric, recognizably-PS1 space.
Not production-final for a flagship title, but genuinely shippable for game-jam,
prototype, and stylized-indie contexts — precisely because the PS1 aesthetic is
forgiving of low detail by design.
