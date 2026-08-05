# Room-by-Room Environment Dressing Checklist

The shared sheet for Zoo, Patina and Pixelcoat. Use it to dress each room,
corridor, exterior space and gameplay area consistently.

It supports environment artists, level designers, technical artists, the
procedural generation systems, the modular level-building tools, art reviews
and gameplay-readability reviews.

The goal is spaces that feel functional, inhabited and visually distinctive
without becoming cluttered or difficult to read.

Read alongside `pixelcoat/docs/CONTRAST_DIRECTION.md`, which covers the
material and contrast half. This sheet covers placement.

---

## Who owns what

| Sections | Owner | Why |
|---|---|---|
| 1–5 room intent, hierarchy, composition, zones | **Deli Counter** | Only the greybox knows a room's function, route and combat geometry |
| 6–8 prop clusters, three-scale rule, rhythm | **Zoo** | It builds the props and the kit's repeating modules |
| 9 texture-based dressing | **Pixelcoat** | Shallow detail lives in the grammar, not the mesh |
| 10–11 material and colour hierarchy | **Pixelcoat** | Theme profiles and the contrast budget |
| 12–13 lighting, motion | **Lux** / Zoo | |
| 14–17 story, wear, damage, repairs | **Patina** | It is the weathering and dressing pass |
| 18–22 vertical volume, routes, silhouettes, asymmetry, clutter pass | **Patina** + review | |
| 23–24 procedural rules, prop tagging | **Patina** + **Zoo** | The machine-readable half of this sheet |
| 25–26 scorecard, final review | Everyone | |

---

## 1. Define the room before dressing it

Complete a **Room Intent Card** before placing props.

**Room name** — a functional name. `Vehicle Maintenance Bay`, `Security
Checkpoint`, `Cold Storage`, `Cargo Sorting Room`, `Alien Power Chamber`,
`Apartment Kitchen`, `Rooftop Utility Area`. Never `Room 04`, `Large Room`,
`Hallway B`.

**Primary function** — what normally happens here. *"Workers receive damaged
vehicles, inspect them, replace components, and return them to service."*

**Current state** — one of: active · recently active · abandoned · damaged ·
occupied by another faction · under repair · converted to another use ·
partially operational · emergency state.

**Gameplay function** — all that apply: main traversal · combat arena ·
objective space · exploration space · transition space · puzzle space · safe
space · social space · stealth space · vehicle space · landmark · vista.

**Primary visual idea** — one dominant graphic concept. *A large vehicle
suspended over a maintenance pit. A glowing generator dividing the room
vertically. Repeating freezer doors making a horizontal rhythm. A broken
ceiling exposing rain and city light. One red emergency light punctuating an
otherwise dark room.*

**Primary landmark** — the object or feature the player should remember.

**Intended player read** — what they understand within three seconds.
*"This is a damaged repair bay. The suspended vehicle is the landmark. The
illuminated door behind it is the route forward."*

## 2. Establish the room hierarchy

Assign every major element to a priority tier.

1. **Gameplay-critical** — enemies, objectives, interactables, doors,
   traversal openings, pickups, hazards, vehicles, destructibles. Strongest
   contrast, saturation, luminance, animation, silhouette separation.
2. **Landmark** — hero machinery, major signage, large architectural features,
   unique faction elements, vistas, room-defining props. Memorable, but never
   overpowering active gameplay.
3. **Functional dressing** — workstations, storage, utilities, tools,
   furniture, supporting machinery, safety systems, maintenance equipment.
   These explain how the room operates.
4. **Narrative dressing** — repairs, damage, personal objects, activity
   residue, faction occupation, improvised changes.
5. **Background support** — quiet wall surfaces, structural repeats,
   noninteractive background props, distant machinery, low-contrast inserts.

Tier 4 and Tier 5 must never compete with Tier 1.

## 3. Validate the undressed room

Before adding small props, confirm the room works on architecture alone:
readable silhouette · visible entrance and exit · understandable floor levels ·
clearly located stairs and ramps · a dominant axis · major shapes readable at
thumbnail size · clean backgrounds behind important gameplay positions ·
areas of negative space · no dependence on clutter to feel complete.

**Do not use props to hide weak architecture.** Fix the shell first.

## 4. Establish the primary composition

Stand at the expected entry point and identify: foreground, middle ground,
background, focal point, route forward, secondary route, major light source,
major dark mass, primary colour accent.

Confirm the focal point is not centred by accident · the path is visible ·
important silhouettes do not overlap · large forms create framing · the scene
has both active and quiet areas · the landmark is at least partly visible ·
the strongest contrast supports the intended read.

## 5. Divide the room into dressing zones

**Gameplay clear zone** — main path, combat lanes, dodge space, vehicle path,
enemy approach, objective interaction area. Allowed: floor markings, embedded
detail, low-profile debris, wall-mounted systems, nonblocking effects.
Forbidden: loose collision, dense prop piles, high-contrast background noise,
small objects that resemble pickups, bright decorative lights.

**Functional zone** — equipment that explains the room: workbench, storage
rack, terminal, tool station, utility pipe, maintenance cart, control panel.

**Narrative zone** — storytelling: abandoned lunch, open locker, emergency
repair, damaged machinery, faction graffiti, discarded equipment, recent
struggle.

**Landmark zone** — reserved space around the major feature. Do not crowd it.

**Quiet zone** — at least one area intentionally restrained: a broad wall,
open floor, dark upper space, fogged background, empty structural bay. Quiet
zones are what make the dressed areas work.

## 6. Build functional prop clusters

Each cluster describes **one** activity or system.

- **Anchor prop** — one dominant object: generator, desk, vehicle, storage
  rack, medical bed, furnace, terminal, crane control station.
- **Supporting props** — two to four related objects: tool case, replacement
  component, chair, fuel container, cable spool, monitor, pallet, barrier.
- **Activity evidence** — one detail showing recent use: open drawer,
  pulled-out chair, active screen, loose tool, spilled liquid, missing
  component, temporary cable, half-loaded container.
- **Contact detail** — one grounding element: shadow, floor stain, wheel mark,
  dust boundary, cable connection, wall attachment, anchor bolts.
- **Accent** — no more than one: amber work light, green display, red warning
  label, cyan component, white painted number.

Validate: the props relate to one another · the cluster has one dominant
silhouette · it does not block movement · it contains a size hierarchy · it has
negative space around it · it contains no unrelated filler.

## 7. Use the three-scale rule

Every important dressed area contains three scales.

- **Large** — machinery, storage unit, vehicle, structural support, large
  furniture, major pipe.
- **Medium** — control panel, tool cart, container, chair, junction box, sign.
- **Small** — tool, cup, cable, fastener, handwritten label, debris, screen.

A room filled with only small props feels noisy and lacks structure.

## 8. Establish architectural rhythm

Identify the repeating elements — wall bays, ceiling beams, floor plates,
columns, windows, lights, doors, pipe supports, storage modules — use them for
coherence, then interrupt selectively:

```
repeat · repeat · repeat · INTERRUPT · resume
```

Interruptions: missing panel, different material, damage, bright insert, open
bay, faction modification, active terminal, structural collapse. **Do not
interrupt every repetition.**

## 9. Apply texture-based dressing

Use pixel art and low-resolution textures for shallow detail instead of
geometry: panel divisions, painted bevels, rivets, vents, access hatches,
grilles, fasteners, signs, labels, material transitions, shallow recesses,
warning stripes, small lights, repair plates.

Each texture contains a broad quiet field, a structural frame, one or two
medium details, one optional accent, and controlled wear. Never fill the whole
texture with equal contrast.

Pixel cluster check: pixels form intentional clusters · single-pixel noise is
limited · shading uses a small value range · important edges read at distance ·
material cues are exaggerated enough to read · painted depth does not conflict
with the mesh.

## 10. Apply material hierarchy

- **Quiet environment** — higher roughness, restrained saturation, broad value
  regions, limited specular, minimal emissive.
- **Functional props** — moderate roughness variation, clear material
  boundaries, controlled highlights, small functional emissives, stronger local
  contrast.
- **Hero and faction props** — lower roughness, glossy or reflective inserts,
  stronger saturation, distinct response, iridescence, animated emissive,
  strong silhouette lighting.

Do not give every prop a premium material response.

## 11. Add colour punctuation

**Base palette** for most surfaces: gray, brown, rust, desaturated green,
weathered blue, dirty beige, charcoal.
**Supporting accent** for area identity: amber, dark red, muted yellow, pale
green, cool blue.
**Reserved gameplay colours** — protected for enemies, pickups, objectives,
hazards, interactive objects, faction technology.

Confirm: the most saturated element has a reason · decorative props do not
borrow gameplay colours · accents appear in clusters, not everywhere · rooms
use controlled accent variation · the room reads in grayscale.

## 12. Add lighting as dressing

Add lighting *after* the prop composition works. Every light performs a role:
general visibility, navigation, landmark emphasis, functional explanation,
mood, gameplay readability, faction identification, narrative state. **Remove
lights with no role.**

Pattern: broad environmental light · localized functional light · one
controlled accent · darkness or lower contrast around unimportant areas.

Confirm: the brightest area supports gameplay or the landmark · decorative
lights do not overpower objectives · common enemy backgrounds stay readable ·
prop clusters feel grouped by light · lighting does not flatten material
differences · the room varies between light and dark.

## 13. Add environmental motion

Fan rotation, belt movement, blinking display, dripping fluid, steam vent,
swinging cable, moving shadow, electrical flicker, scrolling pixel display,
distant machinery, floating dust.

Budget: one primary ambient motion, two or three secondary, minimal
background. Gameplay motion must stay dominant.

Confirm: motion has a visible cause · it does not pull attention from
objectives · repeated animation is not perfectly synchronized · animated props
have appropriate sound · motion supports the room's function.

## 14. Add environmental story layers

In chronological order — and only the layers the room's state supports.

1. **Original construction** — base architecture, permanent machinery,
   original signs, standard materials, installed utilities.
2. **Normal use** — wear, storage, routine tools, traffic marks, maintenance
   access.
3. **Long-term change** — repairs, replacement components, faction occupation,
   converted use, added cables, modified lighting.
4. **Recent event** — fresh damage, open doors, active alarms, displaced props,
   temporary barricades, unfinished work, abandoned equipment.

## 15. Add wear based on cause

Never randomly.

- **Foot traffic** — between doors, around workstations, near stairs, at queue
  areas, beside frequently used machinery.
- **Hand contact** — handles, around switches, railings, terminal edges,
  cabinet doors.
- **Vehicle contact** — bumper height, narrow turns, loading bays, floor
  guides, barriers.
- **Water** — streaks below leaks, pools at low points, corrosion at joints,
  darkening around drains, deposits around pipes.
- **Heat** — discoloration near exhausts, soot above vents, burn marks near
  failures, faded paint around hot machinery.

## 16. Add damage with cause and direction

Every major damage event answers: what caused it · from which direction · what
material failed · where debris travelled · what was exposed · how occupants
responded.

A complete event may include impact point, broken surface, exposed structure,
debris field, burn or residue, emergency response, changed lighting, temporary
repair, altered path. **Avoid damage decals without supporting evidence.**

## 17. Add repairs and adaptations

Bolted patch, welded plate, replacement panel, temporary brace, mismatched
component, external cable, handwritten warning, portable light, improvised
barrier, patched pipe, repainted marking. Repairs should look **less
integrated** than the original construction.

## 18. Dress the full vertical volume

- **Floor** — drainage, floor markings, traffic wear, embedded systems,
  damage, low-profile props.
- **Interaction** — controls, handles, signs, work surfaces, doors, windows,
  storage.
- **Upper wall** — pipes, cable trays, ventilation, lighting, structural
  transitions, upper machinery.
- **Ceiling** — major supports, suspended equipment, maintenance access, large
  shadow forms, ventilation, cranes, hanging systems.

Do not place detail in every zone. Use vertical distribution for depth.

## 19. Frame doors and routes

Important routes are recognizable through multiple signals: structural frame,
floor transition, light, material change, sign, colour accent, clear negative
space, prop orientation, repeated lines leading toward the opening.

**Never place bright decorative clusters beside false routes.**

## 20. Protect gameplay silhouettes

From every major combat position confirm: enemies visible · doors readable ·
cover shapes clear · pickups not blending into debris · objectives not hidden ·
hazards visible during effects · stairs and ladders cleanly outlined ·
decorative elements not resembling interactive objects.

Reduce background detail where silhouettes fail.

## 21. Add controlled asymmetry

One damaged side · uneven prop distribution · different equipment states · one
active workstation · one blocked bay · one faction-modified corner · uneven
lighting · different storage amounts. Never random asymmetry without a
functional reason.

## 22. Perform the clutter pass

Remove props that repeat information already communicated · do not relate to
nearby objects · block navigation · compete with gameplay · break the palette ·
create excessive edge density · add collision without value · exist only
because a surface looked empty.

**Empty space is an intentional design tool.**

---

# The machine-readable half

Sections 23 and 24 are not prose. They are a specification for Patina and Zoo.

## 23. Procedural dressing rules

A procedural system must not scatter props uniformly. It uses **semantic
zones, cluster rules and budgets**.

### Required room metadata

`room function · gameplay function · faction · current state · age ·
primary route · secondary route · combat zones · quiet zones ·
landmark position · accent colour · dressing density`

### Placement priority

1. Landmark
2. Functional anchor props
3. Supporting cluster props
4. Utility connections
5. Narrative variation
6. Decals
7. Small clutter
8. Ambient effects

### Cluster rules

Each cluster uses one cluster type · has one anchor · uses two to four support
objects · includes one state variation · maintains a clear perimeter · avoids
gameplay paths · aligns with walls, work surfaces or machinery · faces the
expected user direction.

### Exclusion rules

Never place clutter inside main traversal · in door swing areas · on stair
treads · on ladder access points · in objective interaction zones · behind
common enemy silhouettes · in vehicle lanes · within a landmark's visual
breathing space.

### Density rules

Approximate maximum coverage of visual and floor area — not prop count.

| Zone | Coverage |
|---|---|
| Main path | 0–5% |
| Combat space | 5–15% |
| Functional edge | 15–30% |
| Narrative corner | 25–45% |
| Hero cluster | manual or custom template |

## 24. Prop tagging

Every asset carries metadata so the generator can build coherent clusters
rather than random collections.

- **Function** — storage · maintenance · security · medical · food · office ·
  power · cooling · waste · transport · communication
- **Scale** — small · medium · large · hero
- **Placement** — floor · wall · ceiling · surface · hanging · corner · edge ·
  embedded
- **State** — clean · used · damaged · broken · open · closed · powered ·
  unpowered · leaking · repaired
- **Visual priority** — quiet · support · accent · landmark · gameplay
- **Collision** — none · minor · blocking · cover · traversable
- **Faction** — neutral · civilian · industrial · human military · alien ·
  occupier · improvised

## 25. Room dressing scorecard

Score 0–2 each: **function · composition · gameplay readability · prop
relationships · colour control · material hierarchy · story · density ·
vertical dressing · cohesion**.

- 0 — absent or actively harmful
- 1 — partial
- 2 — clear and intentional

**17–20** strong · **13–16** functional, needs refinement · **9–12**
inconsistent · **0–8** rebuild the dressing concept.

A deliberately quiet room does not need a perfect score, but it must still
pass gameplay, composition, function and cohesion.

## 26. Final review

Purpose clear · one dominant visual idea · memorable landmark · readable path ·
coherent prop clusters · props physically related to nearby systems · quiet
space remains · density varies · clean silhouettes · texture supports form ·
intentional pixel value clusters · clear material hierarchy · protected
strongest colours · decorative emissives not competing · lighting supports
composition · controlled ambient motion · wear follows contact and gravity ·
damage has a cause · repairs show continued use · vertical space considered ·
unnecessary props removed · readable during combat · readable at thumbnail ·
readable in grayscale · richer because details relate to each other, not
because every surface is full.

## Condensed recipe

1. Define function, state, gameplay purpose, visual idea.
2. Validate the architecture before adding clutter.
3. Identify gameplay-clear, functional, narrative, landmark and quiet zones.
4. Place one landmark.
5. Build functional prop clusters with anchors and supporting evidence.
6. Establish architectural repetition.
7. Interrupt it selectively.
8. Use pixel textures for shallow construction detail.
9. Apply material and colour hierarchy.
10. Add lighting and limited motion.
11. Add history through wear, damage, repairs, occupation.
12. Protect gameplay silhouettes.
13. Remove unnecessary dressing.
14. Score and review.

## Final principle

A living environment is not one that contains the most objects. It is one
where architecture, props, textures, light, wear, sound and movement all
suggest that the space has a purpose, has been used, and is changing over
time.

---

# Appendix — where we actually stand

Measured 2026-08-05 against a shipped `shell.gameplay.json` from
`lot_demo_001.deli_generate.candidate.seed_5017` (86,358 bytes), not from
reading the code.

## §23's twelve required room metadata fields

| Field | Status | What we carry |
|---|---|---|
| Room function | partial | `room.id` is functional (`lobby`, `manager_office`, `security_room`, `vault_room`) — passes §1's naming rule. But `role` is a *gameplay* role, not a function; there is no "Vehicle Maintenance Bay" field |
| Gameplay function | **yes** | `role` (`public_entry`/`fortifiable`/`connector`/`objective_room`) + `combat_range` + `fortifiable` + `objective` |
| Faction | no | — |
| Current state | no | — nothing carries active/abandoned/damaged |
| Age | no | — |
| Primary route | partial | `circulation_contract.stairs[]` carries `role` and `facing`; `markers` carry `crew_spawn` and `responder_spawn`. No route geometry |
| Secondary route | no | — |
| Combat zones | partial | `combat_range` per room, plus 9 cover markers. No zone geometry |
| **Quiet zones** | **no** | — and this is the one everything else waits on |
| Landmark position | **yes** | 2 `landmark` markers |
| Accent colour | no | `rarity_color` exists in the schema and is `null` |
| Dressing density | no | — |

**Three present, three partial, six absent.** The absent six are exactly what
§23's cluster, exclusion and density rules consume.

## The finding that matters

**Patina already has the gameplay data and does not read it.**

`patina/cli.py:499` — *"Re-emit the gameplay.json unchanged next to the styled
output (Patina is visual-only; markers/collision are the original's,
untouched.)"* — so `scene.gameplay` is loaded into memory in the same run that
decides where dressing goes, and is passed straight through.

What is sitting in that object, unread, on a single demo building:

```
markers      14   cover_low 7 · cover_high 2 · landmark 2 · crew_spawn 1
                  responder_spawn 1 · camera_socket 1
objectives    2   with room, position, duration, required
zones         2   extraction · secure, each with bounds and centre
rooms         4   with bounds, role, combat_range, fortifiable, objective
surface_roles 303  wall 189 · stair 57 · window 30 · prop 11 · doorway 7
                   floor 4 · breach 4 · ceiling 1
```

§23's exclusion rules need *objective interaction zones*, *behind common enemy
silhouettes* and *main traversal*. Those are `objectives[]`, the cover markers,
and the spawn-to-objective line — all present, all already loaded.

This also corrects `CONTRAST_DIRECTION.md` §3.3 (Pa2), which claimed Patina
"runs per-building, before Lot places anything on the site, so the firing lanes
do not exist yet." True of *site-level* lanes between buildings. Not true of
the per-building combat data, which is right there.

## First moves, in order

1. **Read `scene.gameplay` in the dressing pass.** No new data, no new
   pipeline stage, no schema change. Exclusion radius around `objectives[]`
   and the cover markers is the whole of §23's exclusion rules that we can
   satisfy today.
2. **Derive quiet zones instead of authoring them.** A quiet zone is a wall
   segment behind a cover marker, on the line a defender's silhouette will be
   read against. `markers[cover_*]` plus `room.bounds` is enough to compute
   one. This is §5's quiet zone, §11's "keep common combat backgrounds
   visually quiet", and §20 — one derivation serving three clauses.
3. **Add `state` and `faction` to the room schema.** Two enum fields in Deli
   Counter, and §14's story layers and §24's faction tag become expressible.
   Everything in §14–17 is blocked on `state` alone.
4. **Tag the props (§24).** `surface_roles` already separates `prop` (11) from
   structure. The seven tag axes are authoring on the Zoo genome, not code.
5. **Density budgets (§23).** Meaningless until zones exist; sequence after 2.

## What this sheet does not yet have a mechanism for

Stated plainly so it is not mistaken for done:

- **No quiet tier in the kit.** §2 tier 5 and §5's quiet zone have no module
  to point at until the `relief: {reveal: 0}` style is proven in a build.
- **No accent mechanism.** §6's "one accent per cluster" and §11's reserved
  gameplay colours need an emissive path. Zero grammars in the library emit.
- **No cluster concept anywhere.** §6 and §23's cluster rules describe an
  anchor plus supports plus evidence. Patina places single covers.
- **No three-scale rule.** §7 needs a size hierarchy in the prop set; the
  demo building carries 11 props total across 4 rooms.
- **Wear is not cause-driven.** §15 wants wear at contact points. Patina's
  weathering is procedural over the whole surface.
