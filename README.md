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

> Patina = vertex nuance + auto-UV + themed structured/posterized texture
> sets + a seeded decal pass + a Godot PS1 shader, applied to a Deli Counter
> greybox, with honest seams — paint templates and start skins — where human
> craft takes over.

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
| `--skin` | `STYLE[:SEEDS]` — procedurally generate a 60/30/10 shadow/base/light skin from a style + 1-3 hex seeds (or a color_swatch json), and lock to it. e.g. `--skin grimy:#4a5a3f`. |
| `--skin-from` | Seed a skin from a color_swatch library (liked colours) or a saved 60/30/10 palette json. |
| `--no-bands` | Disable vertical material-variation bands even when the theme/skin declares them. |
| `--anchors` | Emit a `<out>.anchors.json` sidecar of visual-only placement hints (roofline / wall_base / exterior_light / ground_edge) for downstream geometry tools. No geometry generated here. |
| `--anchor-kinds` | Limit anchor kinds (default: all four). |
| `--family` | Texture family: the shared, limited colour library every surface locks to for cohesion. Builtin (`delco_faded`) or a `family.json` path. Reuse across shells to unify a whole game. |
| `--extract-family` | `IMAGE[:K]` — derive a K-colour family from a reference photo (deterministic k-means), lock to it, save it as `<out>.family.json`. |
| `--override` | Art-bash one key: `KEY=#hex[,#hex...]` recolours (albedo), `KEY=image.(png\|jpg\|webp)` skins it. Repeatable; wins over `--overrides`. |
| `--overrides` | Saved bash session: JSON `{key: {image\|albedo\|tint\|pattern\|process}}`; relative image paths resolve beside the file. |
| `--no-decals` | Skip the theme's decal pass. |
| `--decal-scale` | Decal density multiplier (1.0 = theme's values). |
| `--templates` | Write per-material paint templates (metre grid + key label) to `<out>.templates/` — the byo painting workflow. |
| `--start-skins` | Write Texpaint-style triangle-unique start skins from authored UV0 (model skinning; UV0-less meshes are skipped). |
| `--skin-size` | Start-skin sheet size in px (default 256). |
| `--slot-variation` | With a DC `slots.json`: bake deterministic per-slot colour variation (keyed by `slot_id`) into vertex colour and emit `<out>.instances.json` — breaks modular repetition. |
| `--depth` | Layer colour-theory depth cues: a preset name (`lux`, `delco`, `exterior`) or `off`. |
| `--preview` | Render a composite look preview (`<out>.preview.png`) approximating vertex colour × Lux banded light, and report luma headroom. |
| `--trim-sheet` | Generate a family-locked trim atlas (roof edge, panel seam, pipe run, corner guard, foundation, conduit, flashing) + UV-region map. |
| `--dressing` | With `--anchors`: emit `<out>.dressing.json` — per-anchor non-collision cover build orders (trim piece + UV region + position) for Zoo. |
| `--slot-variation-strength` | Per-slot brightness jitter (0–0.5, default 0.12). |
| `--no-slots` | Ignore a sibling DC `slots.json` even when present (fall back to whole-mesh geometry-derived styling). |
| `--anchor-patina-space` | Emit anchors in Patina's baked Y-up space instead of DC's Blender Z-up (only relevant with a `slots.json`). |
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
| Structured tile patterns (v0.3) | **Offline-verified.** Deterministic, wrap-exact grids; per-cell variety; `default` byte-identical. |
| Paint templates + start skins (v0.3) | **Offline-verified.** Deterministic sheets; UV0-less meshes honestly skipped. |
| Per-key art-bash overrides (v0.4) | **Offline-verified.** Image/albedo/tint/pattern per key; no-override byte-identical; saved sessions recorded in the manifest. |
| Texture families (v0.5) | **Offline-verified.** Shared palette locked across every surface (cohesion); deterministic extraction; no-family byte-identical; family recorded in the manifest. |
| Procedural skins (v0.6) | **Offline-verified.** 60/30/10 shadow/base/light from hex + style; color_swatch interop; no-skin byte-identical. |
| Vertical banding (v0.7) | **Offline-verified.** Material variation by world height (base/body/cap) as vertex colour, no geometry; no-band byte-identical; bands lock to the family. |
| Placement anchors (v0.8) | **Offline-verified.** World-space dressing/light/prop placement in a sidecar for downstream geometry tools; deterministic; zero geometry/collision impact; opt-in. |
| Modular alignment (v0.9) | **Offline-verified on real DC builds.** Reads `slots.json`; auto-detects up-axis (Y-up DC glTF vs legacy Z-up); anchors in DC's Blender space; `delco` theme → `delco_faded` family. Legacy Z-up byte-identical. |
| Per-slot variation (v0.10) | **Offline-verified on real DC builds.** Deterministic per-`slot_id` colour variation baked to vertex colour + emitted as `instances.json` (DC per-instance shape); family-locked; opt-in. |
| Trim sheets + dressing (v0.11) | **Patina half offline-verified;** Zoo consumer built (Zoo 0.21.0). Family-locked trim atlas + per-anchor non-collision cover build orders. |
| Depth & cohesion (v0.12) | **Offline-verified.** Saturated shadow gradients + atmospheric recession baked to vertex colour; warm/cool texture temperature; opt-in, byte-identical off. |
| Per-key art-bash overrides (v0.4) | **Offline-verified.** Image/albedo/tint/pattern per key; no-override byte-identical; saved sessions in the manifest. |
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
albedo variants for the procedural tiles, role aliases, per-key **pattern**
specs (v0.3: `tile` / `checker` / `block` / `panel` / `plank` — structured,
tileable, posterized grids with per-cell colour variety drawn from the albedo
variants), and decal pools (type, target roles, density per 100 m²,
size/aspect/rotation, budget clamp).
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

## The painter's seam (v0.3): skinning maps, skinning models

v0.3's reference point is id's Quake 2 art workflow (Paul Steed, "The Art of
Quake 2", *Game Developer*, April 1998): hand-drawn base texture *sets*
skinned onto brushes at known scale, and Texpaint's triangle-unique "start
skins" generated from a model's mapping coordinates for artists to paint
over. Patina's honest analogs, all texture/colour only:

* **Texture sets.** Structured pattern generators plus per-cell variety from
  a theme's albedo variants stand in for a base set; one locked greybox +
  N themes = N dressed places.
* **`--templates` (map skinning).** Every generated tile has a fixed world
  scale (`--texel` m per tile) under the box projection, so Patina emits a
  calibration sheet per material key — metre grid, scale, axis marks, the
  stand-in tile as background. Paint over it in any 2D app, drop the result
  into a `byo` folder under the same name, re-run Patina. The tool did the
  unwrap and the scale math; the human does the painting.
* **`--start-skins` (model skinning).** For any visual mesh carrying an
  *authored* UV0 (props, fixtures — not greybox shells, which have none),
  Patina renders the Texpaint start skin: every triangle filled in a unique
  colour with wire lines on top. Coverage and problem areas are visible
  before a single pixel is painted.

Deferred to v0.4 (the model-skinning back half): a model mode that keys
materials and `byo` skins by *mesh name* instead of surface role, so a
painted start skin round-trips onto the prop; and Q2-style swap-skin variant
sets (worn/damaged) as theme vocabulary.

## The art-bash loop (v0.4): swap what you don't love

A theme gets you 80% of a look in one pass. The last 20% is taste, and taste
is per-surface: the floor's right but the exterior brick reads flat, or you
have a phone photo of an actual Delco wall you'd rather use. Overrides are the
iterate gear between "regenerate everything" and "hand-author the whole set" —
substitute *one material key* and re-run:

```bash
# quick bash from the CLI — recolour the floor, skin the exterior from a photo
patina shell.glb --theme delco_1997_gas_station \
  --override floor=#3b3a36,#45433d \
  --override exterior_wall=./ref/real_brick.jpg

# save the session so the look is reproducible in the repo
patina shell.glb --theme delco_1997_gas_station --overrides bash.json
```

An override can carry an `image` (PS1-ified on import — centre-cropped,
resized, posterized; `"process": false` for authored pixel art), replacement
`albedo` colours (keeps the pattern, recolours it), a vertex `tint`, or a
`pattern` spec. Layering is theme < `--overrides FILE` < `--override` flags,
merged field-wise, so a CLI colour tweak sits on top of a file's photo swap
without clobbering it. An overridden key **breaks its theme alias** — override
`exterior_wall` and it stops sharing the interior wall's tile, so you're
bashing exactly the surface you meant.

`bash.json` is a first-class project artifact: it lives next to the theme,
relative image paths resolve beside it, and the applied set is written into
the `.patina.json` manifest — the look you bashed your way to travels with the
level.

## Texture families (v0.5): the shared material library

Quake 2 feels cohesive because every area reuses a small, shared material
library — id assembled these *texture families* with TextureBuild (Steed,
"The Art of Quake 2"). Patina generates each surface independently, so nothing
enforces that the brick, the lino and the ceiling belong to the same world. A
**family** fixes that: it's a limited ordered colour library, and binding one
runs a **palette-lock** pass that quantises every tile, imported photo and
vertex tint to the nearest family colour.

```bash
# lock the whole level to a 10-colour late-90s Delco library
patina shell.glb --theme delco_1997_gas_station --family delco_faded

# build a family from a reference photo, lock to it, save it
patina shell.glb --theme delco_1997_gas_station --extract-family ./ref/moodboard.jpg:8
```

Cohesion becomes *literal*: after a lock, the entire tile set draws from N
colours (a Delco pass with `delco_faded` resolves to ~9 distinct colours
across every surface). And the family is the reusable unit **across areas** —
point every shell at the same `family.json` and the whole game reads as one
place, which is the actual source of Q2's cohesion:

```bash
for shell in levels/*.glb; do
  patina "$shell" --theme delco_1997_gas_station --family ./delco_faded.json
done
```

Each family run emits `<out>.family.json` (the shared library — commit it,
reuse it everywhere) and `<out>.family.swatches.png` (the swatch catalog), and
records the family in the manifest. A theme can also *declare* a default
family; `--family` / `--extract-family` override it. No family bound → the
lock pass is skipped and output is byte-identical to v0.4, so cohesion is
opt-in.

Overrides and families compose: art-bash a surface you don't love, then lock
the result to the family so your swap still belongs to the set.

## Procedural skins (v0.6): a look from hex + style

Where a family is *extracted* from a photo, a **skin** is *generated* from a
few hex colours and a style — the counterpart move. It uses the same colour
theory as GabagoolStudios' [Color Swatch](https://github.com/siliconight/color_swatch)
add-on: a **60/30/10** palette (a calm *dominant*, a mid *secondary*, a punchy
*accent*), each expanded into a **shadow / base / light** family.

```bash
# one seed + a mood: harmony fills the rest
patina shell.glb --skin grimy:#4a5a3f

# pin dominant + secondary by hand; accent comes from the complement
patina shell.glb --skin neon:#ff0055,#00ffcc

# style alone (uses the style's default seed)
patina shell.glb --skin nicotine
```

Seed 0 sets the dominant hue; seeds 1-2 pin the secondary and accent directly;
missing slots are filled by the style's **harmony** (monochrome, analogous,
complementary, triad, split-complementary). Styles (`faded`, `grimy`, `neon`,
`clean`, `sunbleached`, `nicotine`) carry the saturation/value and
shadow/light discipline. The generated skin maps to surfaces by 60/30/10 area
logic — big surfaces take dominant/secondary, trim takes the 10% accent — and
brings its own family, so it **locks for cohesion** through the v0.5 pass. A
grimy skin resolves to ~7 distinct colours across every surface.

**Color Swatch interop.** Point `--skin` (or `--skin-from`) at a
`color_swatch_library.json` and Patina seeds from your *liked* colours; point
it at a saved 60/30/10 palette and it imports the colours as-authored. Each
run writes `<out>.skin.json` and `<out>.skin.txt` (a labelled block you can
paste back into Color Swatch). The two tools chain: like colours in Color
Swatch → generate/keep a 60/30/10 there → skin a level with it here.

The pipeline order is skin → overrides → family-lock: the skin is the
generated base look, a manual `--override` bashes a surface on top of it, and
the lock unifies the result. No `--skin` → output is byte-identical to v0.5.

## Vertical banding (v0.7): material variation by height

Real buildings rarely use one material top-to-bottom — a base course of brick,
painted concrete in the middle, metal flashing at the cap. That "material
variation / colour blocking" is the highest-ROI *no-geometry* art-pass move
(Quake, Half-Life and PS2 games wrapped the greybox this way rather than
rebuilding it). Patina bands a wall by **world height**, chosen per vertex and
baked into vertex colour — the collision/gameplay shell is never touched, and
in procedural mode the band tint multiplies the tiled albedo, so a shared
cinderblock pattern still reads as brick-at-the-base.

The `delco_1997_gas_station` theme bands out of the box (oxblood brick / painted
concrete / brass flashing), and any generated skin auto-derives bands from its
60/30/10:

```bash
patina shell.glb --theme delco_1997_gas_station     # bands built in
patina shell.glb --skin grimy:#4a5a3f               # skin walls band for free
patina shell.glb --theme delco_1997_gas_station --no-bands   # flat walls
```

Bands are declared per vertical role (`wall` / `exterior_wall` / `trim`) as
`{to: fraction, tint: hex}` boundaries over the shell's global height; the
fraction is 0 at the floor and 1 at the ceiling, so a single-storey blockout
gets consistent band heights across every wall. Band colours **lock to the
family** like every other tint, so banding never breaks cohesion.

**Deferred, honestly:** varying the *pattern* per band (brick texture vs
concrete texture, not just colour) needs height-normalised UVs or a per-band
material split — the geometry/engine risk class Patina holds until the addon's
in-engine walk. Bands vary colour; the shared pattern is tinted per band.

## Placement anchors (v0.8): where dressing goes, not the dressing

The richest art-pass items — roofline units, wall-base props, exterior
lighting, ground detail, silhouette breakers — all add *geometry*, which a
texture tool has no business generating. But the hard, automatable part isn't
the mesh; it's *placement*. Patina already knows the roles, the AABB, which
faces are roofline, and where walls meet the ground, so `--anchors` emits a
`<out>.anchors.json` sidecar of seeded world-space placement points for a
geometry tool to fill:

```bash
patina shell.glb --theme delco_1997_gas_station --anchors
# -> shell.patina.anchors.json  (roofline:20, wall_base:16, exterior_light:12, ground_edge:28)
patina shell.glb --anchors --anchor-kinds roofline exterior_light
```

Each anchor carries a `kind`, world-space `pos` + surface `normal`, and a size
hint. Kinds derive from exterior-wall geometry: `roofline` (top edge, up-normal
— HVAC/vents/tanks), `wall_base` (foot, outward normal — dumpsters/boxes/AC
units), `exterior_light` (upper wall — lighting anchors), `ground_edge`
(wall-meets-ground — curbs/weeds/covers). Coordinates are in the styled
`.glb`'s baked world-metre space (the decal contract), and placement is
deterministic and budget-clamped.

This is the intended **division of labour**: Patina decides *where*, downstream
tools supply *what*. Anchors follow the same sidecar convention as Deli
Counter's `.lights.json` → Lot → Lux bridge, so Lux can bake exterior lights
from `exterior_light` anchors and Zoo or a dressing kit can instantiate props
at `wall_base` / `roofline`. Anchors are **visual-only metadata** — the styled
`.glb` is byte-identical whether or not `--anchors` is set, and nothing here
touches collision. Off by default; it's a handoff artifact.

## Modular alignment (v0.9): the DC/Zoo slot pipeline

Patina predated Deli Counter and Zoo moving to a modular slot setup. DC (0.64+)
now emits `<name>.slots.json` — one record per swappable module (wall segment,
opening, prop) keyed by a stable `slot_id`, with a role, a `current_ref` naming
a Zoo module (`wall_greybox_01`), a fit contract, and a transform in Blender
Z-up raw coords. Zoo (0.20+) builds `<role>_<theme>_<style>.glb` modules to
fill those slots and ships a named `delco` style. v0.9 brings Patina into line
on three fronts:

**1. The coordinate fix (the real misalignment).** A real DC `.glb` loads
**Y-up** — the standard Blender-Z-up to glTF-Y-up export conversion — while
Patina's own example shells were Z-up, which hid the bug. Surface
classification, banding, height-grime, and anchors all read the wrong axis on
real DC data (classify was labelling north-facing walls "floor"). Patina now
detects the up-axis after bake and threads it through every height-dependent
pass. Legacy Z-up shells are the default and stay byte-identical.

**2. Reads `slots.json`.** Loaded automatically as a sibling of the `.glb`
(like `gameplay.json`), giving Patina per-module identity by `slot_id` — the
"per-part targeting instead of whole-mesh" DC's art-pass docs call for.
`--no-slots` opts out.

**3. The Zoo aesthetic seam.** Zoo owns module geometry + a flat base style
colour; Patina owns the rich nuance pass (family cohesion, banding, decals, PS1
posterize). When a build's slot manifest names a theme, Patina reconciles it to
the matching family (`delco` -> `delco_faded`) and auto-locks, so the two tools
describe one world instead of fighting. And with a slots.json present,
`--anchors` emits in DC's Blender Z-up space (verified to overlay the slot
extent, roofline at the true story height) tagged with `building_id`, so Lux
and Zoo consume Patina's placements with the same transform code as DC's own
manifests.

```bash
# a real DC build: Patina auto-detects slots.json + up-axis + theme family
patina gs_corner_station.glb --mode procedural --anchors
# -> aligned to DC slots.json v1.x: gs_corner_station / theme=delco (84 slots)
# -> family from slot theme 'delco'  (locks to delco_faded)
# -> anchors in spec/Blender Z-up raw coords
```

**Per-slot variation (v0.10).** Reading `slots.json` gives Patina per-module
identity by `slot_id`, and the payoff is the repetition-breaking DC's docs call
the #1 aesthetic lever. `--slot-variation` computes a deterministic per-slot
brightness factor (seeded by `slot_id`) and bakes it into the monolith's vertex
colour for each slot's faces, so identical `wall_delco_01` copies stop reading
as mechanically repeated — and emits `<out>.instances.json` with per-slot
`{color, custom_data}` in DC's placements shape, so the instanced-bake target
feeds the same variation to Godot's MultiMesh per-instance buffers. Variation
colours come from the reconciled family, so breaking repetition never breaks
cohesion.

```bash
patina gs_corner_station.glb --mode procedural --slot-variation
# -> slot variation: 10041 faces, 84 instances -> ...instances.json
```

Alignment is additive and auto-detected: no slots.json + Z-up geometry -> output
is byte-identical to v0.8. `--slot-variation` is opt-in and needs a slots.json.

## Trim sheets + dressing (v0.11): the texture half of Zoo dressing

The geometry-bearing art-pass items (facade panels, trim caps, roofline vents)
are Zoo's to build — but they need a *texture atlas* and a *placement contract*,
which are Patina's. v0.11 supplies both, so Patina and Zoo can dress a greybox
together without Patina generating a single vertex.

- `--trim-sheet` packs a **trim atlas**: roof edge, panel seam, pipe run, corner
  guard, foundation, conduit, flashing — each a family-locked posterized strip —
  into one power-of-two PNG with a per-piece UV-region map. This is the Q2/Steed
  trim sheet done as texture.
- `--dressing` (with `--anchors`) turns anchors into **Zoo build orders**: per
  anchor, a `dressing.json` record naming the trim piece, its UV region, the
  position/normal (in DC's Blender Z-up space when a slots.json is present), a
  suggested cover kind, and `collision: none`.

```bash
patina gs_corner_station.glb --mode procedural --anchors --dressing
# -> trim sheet -> ...trim.png   (family-locked atlas)
# -> dressing -> ...dressing.json (211 orders: edge_strip:64, curb:64, base_course:50, conduit_run:33)
```

Patina places and skins; **Zoo builds** the `collision: none` cover meshes from
the orders. Patina ships zero geometry and never touches collision. The Zoo
consumer recipe is specced in `docs/DRESSING_CONTRACT.md` and remains to be
built on the Zoo side (plus the in-engine walk to confirm covers render right
over DC's collision).

## Depth & cohesion (v0.12): colour-theory shading

Patina's nuance AO/grime darkened *value* only — a flat multiply that reads
dull, exactly the mistake painters warn against. v0.12 layers colour-theory
depth cues over the vertex-colour pass, distilled from Arne Jansson's PSG
tutorial and the depth/colour-theory sources:

- **Saturated shadow gradients** — the shadow/cavity transition *gains
  saturation* and a warm/cool bias, so form reads as colour, not just darkness.
- **Atmospheric recession** — surfaces that recede (by height and distance from
  the building centre) drift toward a cool desaturated grey, separating
  foreground and background planes.
- **Texture temperature** — a pattern's per-cell `temp` nudges warm/cool, not
  only brightness, so tiled surfaces read richer (Jansson's warm/dark
  alternation).

```bash
patina shell.glb --theme delco_1997_gas_station --depth lux    # composes with Lux at runtime
patina shell.glb --theme delco_1997_gas_station --depth delco  # standalone (no Lux) — owns the whole look
patina shell.glb --depth exterior      # stronger plane separation, standalone
```

Use `--depth lux` when Lux lights the scene in Godot: Lux owns runtime light, so
it owns shadow *colour* and distance *fog*, and the `lux` preset bakes only what
Lux can't derive — shadow *saturation* (form) and gentle height recession. Use
`--depth delco`/`exterior` only when the build is viewed **without** Lux. See
`docs/LOOK_PIPELINE.md` for the full DC → Zoo → Patina → Lux composition and who
owns which cue. Run `--preview` to render an offline composite and get a luma
headroom verdict before opening Godot — it flags over-darkening (the risk from
three multiplicative bakes feeding Lux's `× vertex_colour`) as a number.

A PS1-era look has no real-time GI, so these cues are baked into vertex colour
and tiles on purpose — a deliberate departure from a strict unlit PBR *albedo*.
Depth is opt-in and deterministic; with no `--depth` (and no theme `depth`)
output is byte-identical to v0.11. On the geometry side, Zoo (0.22.0) bakes a
matching cool-up / warm-down directional ambient into module vertex colour, so
modules have form before Patina runs.

## Smoke tests — is the pipeline repeatable?

Before building levels on the flow, prove it holds end to end:

```bash
# offline: DC manifest -> Patina art-pass -> integrity + contracts + headroom
python smoke_offline.py <deli_counter_build_dir> --zoo <zoo_repo>
```

```powershell
# on-machine: DC -> Zoo build-kit -> Patina -> Zoo dress, gated at each stage, then Lux
.\smoke_walk.ps1
```

`smoke_offline.py` asserts each output is *valid*, not just present — collision
untouched, vertex colour in range and uncrushed, dressing covers all
non-collision, schemas correct, the Zoo planner accepts the dressing manifest,
and the composite preview reports OK. It fails at the exact stage that drifts.
`smoke_walk.ps1` gates the Blender/Godot half the same way. Run these after any
change to DC specs, Zoo species, or the coordinate conventions.

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
