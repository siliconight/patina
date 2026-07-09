# LOOK_PIPELINE.md

How the "look" composes across the four tools, and who owns which cue. This is
the map the depth/cohesion work needs so the tools reinforce instead of fight.

## The chain

Deli Counter emits the greybox shell + slots. Zoo builds module geometry and
bakes a base look into vertex colour. Patina applies the art-pass nuance into
that same vertex colour and the tiles. Lux, at runtime in Godot, lights it —
and **multiplies its lit result by the baked vertex colour** (`base *=
v_vertex_color` in `lux_stylized_standard.gdshader`) before its own banded
diffuse, shadow-tint, palette pull and distance fog.

So the composite a player sees is, roughly:

```
final = Lux_light( albedo_tile x vertex_colour ) x Lux_shadow_tint
        x Lux_palette , then fog / grade / dither / CRT
        |__________________|   |_________________________________|
         Zoo + Patina bake        Lux does at runtime
```

Everything is multiplicative and cumulative. That makes the division of labour
a correctness issue, not just taste: bake a cue Lux also applies, and it
double-counts or crosses.

## Who owns what

The principle: **bake the cues that must live in the albedo/vertex data because
nothing at runtime can derive them; defer the cues that depend on runtime light
to Lux.**

| Cue | Owner | Why |
| --- | --- | --- |
| Module form (cavity AO, bevel catch) | Zoo + Patina (vertex) | View-independent; Lux has no other source |
| Material banding (base/body/cap) | Patina (vertex + tile) | Authored intent, not lighting |
| Per-slot variation | Patina (vertex + instances) | Breaks repetition; Lux can't know slot identity |
| Texture (pattern, temperature) | Patina (tile) | Surface detail, not lighting |
| Trim / dressing | Patina atlas + Zoo geo | Placement + geometry |
| Shadow **saturation** (form) | Patina depth (vertex) | The chroma a cavity keeps; Lux bands value, not this |
| Directional **form** (soft cool-up/warm-down) | Zoo ambient (vertex) | The depth a surface has *before* light |
| Runtime light + real shadows | **Lux** | It is the renderer |
| Shadow **colour / tint** | **Lux** | Depends on the light; `shadow_tint` / palette shadow |
| Distance **haze** | **Lux** | Real world-space fog beats albedo-faked recession |
| Palette grade, banding, dither, CRT | **Lux** | Post/runtime |

## The reconciliations made (this is the important part)

Two cues were being baked *and* done by Lux, pulling opposite ways. Fixed:

1. **Shadow temperature.** Patina's `delco` depth preset warmed shadows; Lux's
   delco identity cools them (`shadow_tint` cool purple, palette shadow cool
   blue). Baking warm shadows under a cool-shadow renderer crosses to mud. →
   **Patina `lux` preset** bakes shadow *saturation* only, `shadow_warm = 0` —
   temperature deferred to Lux. (`delco`/`exterior` presets keep warmth for the
   *standalone* case where Patina's vertex colour is the final look.)

2. **Distance recession vs fog.** Patina's atmospheric pass faded distant verts
   toward a cool grey; Lux has real distance fog. → **`lux` preset** uses
   height-only recession (`atmos_radial = 0`); radial distance deferred to fog.

And a latent bug the Lux review surfaced: the saturation gain was *additive*,
which on a **neutral grey** (Zoo's default concrete) invented a red hue from
HSV's undefined-hue-at-zero. Made it **multiplicative** — it now amplifies the
chroma already present and leaves neutrals neutral. This matters most exactly
under the `lux` division, where Patina must add *no* colour Lux didn't ask for.

3. **Directional ambient vs sun.** Zoo bakes a cool-up/warm-down ambient; Lux's
   sun does runtime directional light. Zoo's is kept *subtle* (delco 0.35) and
   framed as "form before light" — the depth a surface has before any key light
   — not a second sun.

## Practical recipe (DC building, delco, with Lux at runtime)

```
zoo   --build-kit <b>.slots.json --theme delco      # modules, ambient form baked
patina <b>.glb --theme delco_1997_gas_station \
       --depth lux --slot-variation --anchors --dressing   # nuance, Lux-safe depth
zoo   --dress <b>.dressing.json --theme delco        # non-collision covers
# in Godot: LuxRoot + delco_summer_afternoon preset lights it all
```

Use `--depth delco` (not `lux`) only when the build is viewed **without** Lux
(previews, thumbnails, a non-Lux renderer) — then Patina owns the whole look.

## Still to verify (the engine walk)

- That the composite reads right on hardware: Zoo ambient × Patina depth ×
  Lux light shouldn't over-darken upward faces or crush cavities.
- Vertex-colour range: three multiplicative bakes (Zoo wear+ambient, Patina
  nuance+depth, per-slot) must not drive albedo so low that Lux's banding has
  nothing to work with. If it does, reduce strengths, don't clamp. **Check this
  offline first with `patina --preview`** — it renders the composite and reports
  a luma headroom verdict; on delco the full stack sits at ~0.54 mean (fine).
- `--depth lux` vs `delco` side by side under `delco_summer_afternoon`.

## Plane separation (arcade near/far pop)

"Punchy saturated near vs washed-out far" is split across the same seam as
everything else: **Patina bakes the per-surface cue, Lux does the per-camera
wash.** A vertex bake is view-independent, so it can only separate a surface's
own near/far faces (strong across a deep level, weak on one compact building).
The camera-relative wash — what actually washes out whatever is far from the
*player* — is Lux runtime distance fog.

- Patina: `--depth punch` (near_sat gains foreground saturation, far_wash
  desaturates + lifts background toward haze, by world recession).
- Lux: the `delco_arcade` preset — brighter HDR key (exposure 1.15, glow
  threshold 1.25), punchy saturation 1.22 / contrast 1.1, and cooler denser fog
  (0.006, cool-light colour) that builds the wash with camera distance.

Tune the two together in the look-dev harness (preset key 6 = Delco Arcade);
push fog for the far wash, saturation/exposure/glow for the near punch.
