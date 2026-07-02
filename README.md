# Patina

*An automated PS1-era styling pass for Deli Counter greyboxes.*

Patina is a separate, optional sibling tool to **Deli Counter**. It takes a Deli
Counter greybox (`shell.glb` + `shell.gameplay.json`) and applies every step of
the "look like a PS1-era building" pipeline that can be *honestly automated*,
then hands the result to Godot ready to render in a PS1 style.

It does **not** pretend to automate art. Turning a blockout into a
production-final, hand-modeled, hand-textured building is irreducible creative
labor. Patina automates the mechanical steps that bracket that labor — vertex
nuance, box-projection UVs, procedural/posterized textures, and the PS1 render
setup — and marks the seams where a modeler or texture artist takes over.

## The one-line scope

> Patina = vertex nuance + auto-UV + themed procedural/posterized textures +
> a seeded decal pass + a Godot PS1 shader, applied to a Deli Counter greybox,
> with honest seams where human craft takes over.

Since v0.2, Patina is also the home of the **texture/colour bashing**
direction: theme presets turn one locked, playable greybox into many *places*
(materials, palettes, decals) without ever touching collision, nav geometry or
gameplay anchors. Lock the level first. Dress it second. Never break
collision.

## What it is not

No generative-AI meshes or textures. No hand-modeling automation. No
hand-painted texture synthesis. No runtime composition. Not a renderer. **Never
modifies collision.** (See `docs/SEAMS.md` and the TDD non-goals.)

## Install

```bash
pip install -e .          # or: pip install -r requirements.txt
```

Requires Python ≥ 3.10. Dependencies: `numpy`, `pillow`, `pygltflib`
(`jsonschema` for manifest validation). No network, no Blender required for the
asset pass.

## Use (offline asset pass)

```bash
# Lightest, most authentic to a blockout-plus: vertex nuance only, no textures.
patina shell.glb

# Generated PS1 tiles:
patina shell.glb --mode procedural

# Bring your own low-res textures keyed by role (floor/wall/ceiling/trim):
patina shell.glb --mode byo --textures ./my_textures

# Budget control / tuning:
patina shell.glb --no-bevel --no-densify --target-edge 1.0 --posterize 16

# Theme it: 1997 Delco gas station palette + grime decal pass:
patina shell.glb --mode procedural --theme delco_1997_gas_station

# Project-specific look: same JSON shape as the builtins, kept in your repo:
patina shell.glb --mode procedural --theme ./themes/delco_bank.json
```

Outputs, next to the input:

* `shell.patina.glb` — styled geometry + vertex colours (+ UVs/textures in
  textured modes).
* `shell.patina.json` — style manifest the Godot addon reads (shader params,
  per-surface specs, kit-bash hooks).
* `shell.patina.textures/` — generated tiles (textured modes only).
* `shell.patina.gameplay.json` — the original gameplay.json, re-emitted
  unchanged (Patina is visual-only).

Then in Godot: see [`godot/README.md`](godot/README.md) — enable the addon,
import the `.glb`, click **Apply PS1 style**.

## CLI

| Flag | Effect |
|------|--------|
| `--mode` | `vertex-color` (default, lightest), `procedural`, or `byo`. |
| `--textures DIR` | byo mode: folder of textures keyed by role. |
| `--no-bevel` / `--no-densify` | Disable individual nuance sub-steps (budget). |
| `--texel` | World-space metres per texture tile (UV density). |
| `--posterize N` | Colour-depth target for generated textures (~16 = PS1). |
| `--target-edge` / `--max-subdiv` | Densify density + budget clamp. |
| `--seed` | Determinism seed (default 1999, matches Deli Counter). |
| `--theme` | Theme preset: builtin name (`default`, `delco_1997_gas_station`) or a theme `.json` path. `default` keeps the v0.1.x look. |
| `--no-decals` | Skip the theme's decal pass. |
| `--decal-scale` | Decal density multiplier (1.0 = theme's values). |
| `--out` | Output path (default `<input>.patina.glb`). |
| `--passthrough` | P0 I/O spine only: load + re-emit, no styling. |

## Status & honest verification

| Part | State |
|------|-------|
| glTF I/O spine (P0) | **Offline-verified.** Round-trips value-for-value; deterministic writer. |
| Vertex nuance — densify + vertex colour (P1) | **Offline-verified.** Budget-sane, bounded colour, shares Deli Counter's formula. |
| Box-projection UVs (P3) | **Offline-verified.** Uniform texel density across non-uniform scale. |
| Procedural/posterized textures (P4) | **Offline-verified.** Deterministic, tileable, posterized. |
| Manifest + schema | **Offline-verified.** Schema-validates; every role and decal resolves. |
| Theme presets (v0.2) | **Offline-verified.** Deterministic; `default` keeps v0.1.x tints and byte-identical tiles. |
| Extended classification (v0.2) | **Offline-verified.** `exterior_wall` / `roof` via visual-AABB heuristic; concave footprints conservatively fall back to `wall`. |
| Decal pass — placement + stamps (v0.2) | **Offline-verified.** Seeded, area-weighted, budget-clamped; per-spec RNG streams. |
| Decal pass — Godot `Decal` instantiation (v0.2) | **First-run-in-engine.** Walk to confirm projection direction, vertical-streak orientation and fade. |
| Geometric bevel | **Deferred / bridged.** Off in the pure-Python path; bridges to Deli Counter's bpy pass when Blender is importable. Edge-cavity AO stands in for the look. |
| PS1 shader + Godot addon (P2) | **First-run-in-engine.** Drafted against known-good patterns; walk in Godot 4.7 to confirm. |

Run the offline suite:

```bash
pytest -q
```

See `docs/DESIGN.md` for the condensed design and the architecture decision
(pure-Python asset pass vs bpy), and `docs/SEAMS.md` for where human craft takes
over.

## Themes (v0.2)

A theme is plain JSON bundling a palette, per-role vertex tints, per-role
albedo variants for the procedural tiles, role aliases, and decal pools
(type, target roles, density per 100 m², size/aspect/rotation, budget clamp).
Everything a theme does is expressed as material overrides, vertex colour and
`Decal` nodes — a theme has **no vocabulary** for collision, nav or gameplay
anchors, so playtest data survives any theme by construction.

The decal pass writes placements into `shell.patina.json`
(`decals.instances[]`) and posterized RGBA stamps into
`shell.patina.textures/decals/`; the Godot addon instantiates them under a
single deletable `PatinaDecals` node. Re-applying rebuilds it from scratch.

Deferred, deliberately (in bashing-brief order): trim/edge dressing, then
conservative visual-only props. Both add generated *geometry*, which is a new
risk class — the decal pass gets walked in-engine first.

## Relationship to Deli Counter

Patina depends on Deli Counter's **output contract**, not its code: it reads
`<name>.glb` (VISUAL + COLLISION dual mesh, `-colonly`/`-convcolonly` suffixes)
and `<name>.gameplay.json` (markers, surfaces), and re-emits collision and
markers unchanged. The vertex-nuance formula is shared by design — the numbers
are the contract. Deli Counter still "makes models, not levels"; Patina styles
models, it does not add gameplay.

## Licence

See `LICENSE` (placeholder — choose before publishing; the TDD suggests MIT/CC0,
which also keeps any future vendored shader clean).
