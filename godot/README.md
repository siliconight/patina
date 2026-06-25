# Patina — Godot side (PS1 render look)

This is the **in-engine half** of Patina (TDD phase P2). The offline Python pass
produces `shell.patina.glb` + `shell.patina.json`; this addon imports that and
applies the PS1 look: a per-surface PS1 shader, white ambient, and distance fog.

> **First-run-in-engine.** Everything under `godot/` is drafted against
> known-good Godot 4 patterns and verified to compile-shape only. It has **not**
> been walked in the editor yet. Confirm in Godot 4.7 before trusting
> auto-apply — same caveat bucket as Deli Counter's plugin dock. The asset pass
> (the Python side) is the part that's fully offline-verified.

## Install

1. Copy `addon/patina/` into your project at `res://addons/patina/`
   (the shader `ps1.gdshader` lives inside the addon, so it travels with it).
2. **Project → Project Settings → Plugins → Patina → Enable.**
3. A **Patina** dock appears (right-upper slot).

## Use

1. Import `shell.patina.glb` into the scene (drag it in, or instance it).
2. Select the imported shell's **root node** in the scene tree.
3. In the Patina dock: **Choose .patina.json…** → pick `shell.patina.json`
   (it sits next to the `.glb`).
4. Click **Apply PS1 style.** The dock reports how many meshes were styled.

That assigns a `ShaderMaterial` per surface role, sets white ambient lighting,
and turns on distance fog from the manifest. One step, like Deli Counter's
*Set up & Play*.

## What it does / doesn't touch

* **Visual only.** It assigns override materials and sets up a
  `WorldEnvironment`. It never edits geometry, collision shapes, or markers —
  those are the original Deli Counter shell's, re-emitted unchanged by the
  asset pass.
* Nodes whose names carry a collision suffix (`-colonly` / `-convcolonly`) are
  skipped defensively.

## The shader

`ps1.gdshader` is **in-house, written from scratch** (no vendored code), so the
licence is unambiguous. It implements the four PS1 tells: vertex snapping
(jitter), approximate affine mapping, colour-depth limit + ordered dither, and
it reads vertex colour as the lighting (paired with white ambient). Distance fog
is set on the environment.

If you'd rather wrap a known MIT/CC0 PS1 pack (TDD §9 suggests this), drop it in
beside `ps1.gdshader`, point `patina_apply.gd`'s `PS1_SHADER` preload at it, and
honour that pack's licence.

### Known soft spot: affine mapping

Godot doesn't expose a `noperspective` varying qualifier, so the affine term is
*approximated* (blend between perspective-correct and a UV×w / w trick via
`affine_strength`). If textures over-warp on big faces, the standard fix is more
densify in the asset pass (`--target-edge` smaller); you can also dial
`affine_strength` down. This is the single most likely thing to need a tweak on
your Godot version — check it first when you walk it.
