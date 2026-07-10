"""Patina CLI — the single offline entry point (TDD 6).

Mirrors Deli Counter's ergonomics: one script, sensible defaults, every stage
toggleable. Pipeline order::

    load -> bake transforms -> densify -> bevel -> classify
         -> vertex colour -> box-UV -> palette -> write .glb + .patina.json

Usage::

    patina shell.glb [--mode vertex-color|procedural|byo] [--textures DIR]
                     [--no-bevel] [--no-densify] [--texel 2.0] [--seed 1999]
                     [--posterize 16] [--out shell.patina.glb] [--passthrough]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

from . import (anchors, banding, decals, depth as depth_mod, families, framing, paneling,
               gltf_io, manifest, nuance, overrides, palette, skins, slots,
               surfaces, templates, themes, trim, uvproject, version)
from .mesh import Scene, SurfaceRole


def _visual_z_range(scene: Scene, up_axis: int = 2) -> tuple[float, float]:
    """Global (min, max) along the up axis over all visual vertices — banding's
    height basis. up_axis is 2 (Z) for legacy shells, 1 (Y) for DC glTF."""
    import numpy as np
    lo, hi = np.inf, -np.inf
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.vertex_count():
                z = prim.positions[:, up_axis]
                lo, hi = min(lo, float(z.min())), max(hi, float(z.max()))
    return (0.0, 1.0) if lo == np.inf else (lo, hi)


def _visual_centroid(scene: Scene):
    """Centre of the visual AABB — the radial basis for atmospheric recession."""
    import numpy as np
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.vertex_count():
                lo = np.minimum(lo, prim.positions.min(0))
                hi = np.maximum(hi, prim.positions.max(0))
    return np.zeros(3, np.float32) if not np.isfinite(lo).all() \
        else ((lo + hi) / 2.0).astype(np.float32)


def _default_out(in_path: str) -> str:
    base = in_path[:-4] if in_path.lower().endswith(".glb") else in_path
    return base + ".patina.glb"


def run(args: argparse.Namespace) -> dict:
    """Execute the pass. Returns a dict of output paths + stats."""
    scene: Scene = gltf_io.load_glb(args.input)
    out_glb = args.out or _default_out(args.input)
    result = {"input": args.input, "output_glb": out_glb}

    if args.passthrough:
        gltf_io.save_glb(scene, out_glb)
        result["stats"] = scene.stats()
        result["mode"] = "passthrough"
        return result

    # Bake node transforms into vertices so every downstream stage works in
    # world-space metres (dodges the I-5 texel-smear / densify-by-local trap).
    scene.bake_visual_transforms()

    # v0.9 coordinate alignment: a real DC .glb bakes Y-up (glTF axis
    # conversion), while legacy hand-authored shells were Z-up. Detect it once
    # so height-dependent passes (banding, grime, anchors) read the right axis.
    up_axis = slots.detect_up_axis(scene)
    if up_axis != 2:
        result["up_axis"] = "XYZ"[up_axis]

    # Start skins (v0.3, model skinning): Texpaint-style triangle-unique
    # sheets from *authored* UV0, captured before densify so the sheet shows
    # the unwrap as authored, not the subdivided copy.
    tpl_dir = out_glb[:-4] + ".templates"
    if args.start_skins:
        written, skipped = templates.write_start_skins(
            scene, tpl_dir, size=args.skin_size)
        result["start_skins"] = len(written)
        if written:
            result["templates_dir"] = tpl_dir
        for name in skipped:
            print(f"[patina] start skin skipped for {name!r}: no authored UV0 "
                  "(box-projection UVs are not a paintable unwrap)",
                  file=sys.stderr)

    opts = nuance.NuanceOptions(
        densify=not args.no_densify,
        bevel=not args.no_bevel,
        vertex_color=True,
        target_edge=args.target_edge,
        max_subdiv=args.max_subdiv,
        mottle_strength=args.mottle,
        mottle_scale=args.mottle_scale,
    )
    if opts.densify:
        nuance.densify(scene, opts)
    beveled = nuance.bevel(scene, opts)          # bpy bridge; no-op if unavailable
    if opts.bevel and not beveled:
        print("[patina] geometric bevel skipped (no bpy bridge); "
              "edge-cavity AO stands in.", file=sys.stderr)

    theme = themes.load(args.theme)
    result["theme"] = theme.name

    # Modular alignment (v0.9): if DC emitted a sibling <name>.slots.json, read
    # it. It carries the building theme (greybox/delco/...) and per-slot records
    # keyed by slot_id — the modular pipeline Patina now targets per-part.
    slot_manifest = None if args.no_slots else slots.load(scene)
    if slot_manifest is not None:
        result["slots"] = {
            "version": slot_manifest.version,
            "building_id": slot_manifest.building_id,
            "theme": slot_manifest.theme,
            "count": len(slot_manifest.slots),
        }

    # Procedural skin (v0.6): generate a 60/30/10 shadow/base/light look from
    # hex seeds + a style (Color Swatch parity) and fold it into the theme.
    # Its family feeds the v0.5 lock. Applied before overrides so a manual
    # --override still wins over the generated look.
    skin = None
    if args.skin or args.skin_from:
        skin = skins.resolve(args.skin or "clean", seed_from=args.skin_from,
                             seed=args.seed)
        theme = skins.apply_to_theme(theme, skin)
        result["skin"] = skin.name
        result["skin_style"] = f"{skin.style}/{skin.harmony}"

    # Art-bash overrides (v0.4): theme < --overrides file < --override flags.
    ovr = overrides.merge(
        overrides.load_file(args.overrides) if args.overrides else {},
        overrides.parse_cli(args.override))
    if ovr:
        theme = overrides.apply_to_theme(theme, ovr)
        result["overrides"] = overrides.describe(ovr)

    # Texture family (v0.5): the shared, limited material library everything
    # locks to. Resolution, later wins: theme's declared family < --family <
    # --extract-family. None -> no lock pass, byte-identical to v0.4.
    family = None
    if args.extract_family:
        img, _, kstr = args.extract_family.partition(":")
        family = families.extract(img, int(kstr) if kstr else 8, seed=args.seed)
    elif args.family:
        family = families.load(args.family)
    elif skin is not None:
        family = skin.family()          # a generated skin brings its own library
    elif theme.family:
        family = families.load(theme.family)
    elif slot_manifest is not None:
        # v0.9 seam: honour the module theme DC/Zoo baked. A delco kit resolves
        # to Patina's delco_faded family so both describe one world; greybox
        # stays unstyled. Explicit --family/--skin still win (handled above).
        fam_name = slots.reconcile_family(slot_manifest.theme)
        if fam_name is not None:
            family = families.load(fam_name)
            result["family_from_slots"] = slot_manifest.theme
    if family is not None:
        result["family"] = family.name
        result["family_colors"] = list(family.colors)

    surfaces.classify(scene, up_axis)

    # Vertical bands (v0.7): material variation by world height. Skin-derived
    # bands win over a theme's declared bands; --no-bands disables. Colours
    # lock to the family like every other tint.
    band_raw = None
    if not args.no_bands:
        band_raw = skin.bands() if skin is not None else (theme.bands or None)
    bands = banding.parse(band_raw)
    if bands and family is not None:
        bands = banding.lock(bands, family)
    z_range = _visual_z_range(scene, up_axis)
    if bands:
        result["bands"] = sorted(r.value for r in bands)

    # Depth cues (v0.12): saturated shadow gradients + atmospheric recession.
    # --depth PRESET wins; else a theme's "depth" preset name; else off.
    depth_opts = depth_mod.DepthOptions()
    depth_name = args.depth if args.depth is not None else theme.depth
    if depth_name and depth_name != "off":
        depth_opts = depth_mod.DepthOptions.preset(depth_name)
        result["depth"] = depth_name
    depth_centroid = _visual_centroid(scene) if depth_opts.active() else None

    if opts.vertex_color:
        tints = {SurfaceRole(r): rgb for r in (sr.value for sr in SurfaceRole)
                 if (rgb := theme.tint_rgb(r)) is not None}
        if family is not None and tints:
            tints = {r: families.lock_tint(rgb, family) for r, rgb in tints.items()}
        nuance.vertex_color(scene, opts, tints=tints or None,
                            bands=bands or None, z_range=z_range,
                            up_axis=up_axis, depth_opts=depth_opts,
                            centroid=depth_centroid)

    # Per-slot variation (v0.10): break modular repetition. With a slots.json
    # and --slot-variation, bake a deterministic per-slot brightness factor
    # (keyed by slot_id) into the monolith's vertex colour, and emit the same
    # variation as per-slot instance color/custom_data for the DC instanced
    # bake. Needs vertex colour populated, so it runs after vertex_color.
    if slot_manifest is not None and args.slot_variation and opts.vertex_color:
        import json as _json
        varied = slots.apply_slot_variation(scene, slot_manifest, args.seed,
                                            strength=args.slot_variation_strength)
        side = slots.instances_sidecar(
            slot_manifest, family, args.seed,
            strength=args.slot_variation_strength,
            source=os.path.basename(out_glb))
        ipath = out_glb[:-4] + ".instances.json"
        with open(ipath, "w", encoding="utf-8") as fh:
            _json.dump(side, fh, indent=2, sort_keys=True)
            fh.write("\n")
        result["slot_variation"] = {"faces_varied": varied,
                                    "instances": side["count"],
                                    "sidecar": ipath}

    used_roles = {SurfaceRole(k) for k in surfaces.role_counts(scene)}
    textures_rel: dict[str, str] = {}
    tex_dir = out_glb[:-4] + ".textures"
    if args.mode != "vertex-color":
        uvproject.project(scene, texel=args.texel)
        pal_opts = palette.PaletteOptions(
            mode=args.mode, size=args.size, posterize=args.posterize,
            byo_dir=args.textures, seed=args.seed)
        tiles = palette.build_palette(used_roles, pal_opts, theme)
        if ovr:
            imaged = overrides.apply_images(tiles, ovr, pal_opts)
            if imaged:
                result.setdefault("overrides_imaged", imaged)
        # Palette-lock: snap every tile (procedural / byo / override image) to
        # the shared family library. This is where cohesion is enforced.
        if family is not None and tiles:
            families.lock_tiles(tiles, family)
        if tiles:
            os.makedirs(tex_dir, exist_ok=True)
            for key, data in tiles.items():
                fname = f"{key}.png"
                with open(os.path.join(tex_dir, fname), "wb") as fh:
                    fh.write(data)
            # Roles map to their theme material key's tile (aliases share).
            for r in used_roles:
                key = theme.material_key(r.value)
                if key in tiles:
                    textures_rel[r.value] = os.path.join(
                        os.path.basename(tex_dir), f"{key}.png")
            result["textures_dir"] = tex_dir

    # Emit the resolved family as a reusable artifact: the swatch catalog
    # (eyeball the library) and family.json (point every other shell at the
    # same file — that's how a whole game shares one limited palette).
    if family is not None:
        fbase = out_glb[:-4]
        with open(fbase + ".family.swatches.png", "wb") as fh:
            fh.write(families.swatch_sheet(family))
        families.save(family, fbase + ".family.json")
        result["family_swatches"] = fbase + ".family.swatches.png"
        result["family_json"] = fbase + ".family.json"

    # The generated skin's 60/30/10 record (reusable / re-importable, and a
    # Color-Swatch-style text export for pasting back into the tool).
    if skin is not None:
        sbase = out_glb[:-4]
        import json as _json
        with open(sbase + ".skin.json", "w", encoding="utf-8") as fh:
            _json.dump(skins.to_skin_json(skin), fh, indent=2)
            fh.write("\n")
        with open(sbase + ".skin.txt", "w", encoding="utf-8") as fh:
            fh.write(skins.to_swatch_text(skin))
        result["skin_json"] = sbase + ".skin.json"

    # Paint templates (v0.3, map skinning): per-material-key calibration
    # sheets for the byo painting workflow. In procedural mode the generated
    # tile is the template background (paint over the stand-in).
    if args.templates:
        keys = sorted({theme.material_key(r.value) for r in used_roles})
        backgrounds = tiles if args.mode == "procedural" else None
        written = templates.write_paint_templates(
            keys, tpl_dir, size=args.size, texel=args.texel,
            backgrounds=backgrounds)
        result["templates"] = len(written)
        result["templates_dir"] = tpl_dir

    # Decal pass (bashing brief step 3): seeded placements + posterized RGBA
    # stamps, emitted through the manifest. Visual-only; the Godot addon
    # instantiates them under a deletable PatinaDecals node.
    placements: list[decals.Placement] = []
    decal_tex_rel: dict[str, str] = {}
    if theme.decals and not args.no_decals:
        placements = decals.place(scene, theme, args.seed,
                                  density_scale=args.decal_scale)
        if placements:
            ddir = os.path.join(tex_dir, "decals")
            os.makedirs(ddir, exist_ok=True)
            for dtype in decals.used_types(placements):
                data = decals.generate_texture(dtype, args.seed,
                                               levels=args.posterize)
                with open(os.path.join(ddir, f"{dtype}.png"), "wb") as fh:
                    fh.write(data)
                decal_tex_rel[dtype] = os.path.join(
                    os.path.basename(tex_dir), "decals", f"{dtype}.png")
            result["decals"] = len(placements)
            result["textures_dir"] = tex_dir

    gltf_io.save_glb(scene, out_glb)

    # Placement anchors (v0.8): visual-only handoff for downstream geometry
    # tools. Patina decides WHERE dressing/lights/props go; Lux/Zoo/a dressing
    # kit supply WHAT. Off by default (it's a handoff artifact, not styling).
    anchor_list: list = []
    anchor_counts: dict = {}
    if args.anchors:
        import json
        aopts = anchors.AnchorOptions(
            kinds=tuple(args.anchor_kinds) if args.anchor_kinds
            else anchors.ANCHOR_KINDS)
        anchor_list = anchors.generate(scene, aopts, args.seed, up_axis)
        anchor_counts = anchors.kind_counts(anchor_list)
        # v0.9 alignment: when a DC building is in play (slots.json present, or
        # forced), emit anchors in DC's shared Blender Z-up space so Lux/Zoo
        # consume them with the same transform code as DC's own manifests.
        emit_list = anchor_list
        space = "baked_world_metres"
        building_id = None
        if slot_manifest is not None and not args.anchor_patina_space:
            emit_list = anchors.in_blender_space(anchor_list)
            space = "spec/Blender Z-up raw coords"
            building_id = slot_manifest.building_id
        sidecar = anchors.to_sidecar(emit_list, seed=args.seed,
                                     source=os.path.basename(out_glb),
                                     space=space, building_id=building_id)
        apath = out_glb[:-4] + ".anchors.json"
        with open(apath, "w", encoding="utf-8") as fh:
            json.dump(sidecar, fh, indent=2, sort_keys=True)
            fh.write("\n")
        result["anchors"] = apath
        result["anchor_counts"] = anchor_counts
        result["anchor_space"] = space

        # v0.11: dressing manifest — turn anchors into Zoo non-collision cover
        # build orders (trim piece + UV region), in the same space as the
        # anchors. Emits the trim atlas too. --trim-sheet emits the atlas alone.
        if args.dressing:
            sheet_bytes, regions = trim.build_sheet(
                size=args.size, seed=args.seed, family=family)
            sheet_path = out_glb[:-4] + ".trim.png"
            with open(sheet_path, "wb") as fh:
                fh.write(sheet_bytes)
            panels = []
            facade_flags = (args.panel_fields or args.frames or args.gutters
                            or args.pilasters)
            if facade_flags and slot_manifest is None:
                print("patina: facade-kit flags skipped (no DC slots.json "
                      "for this shell)")
            elif facade_flags and args.anchor_patina_space:
                raise SystemExit(
                    "patina: facade-kit flags emit spec-space orders and "
                    "cannot combine with --anchor-patina-space")
            elif facade_flags:
                if args.frames:
                    panels += framing.frame_orders(slot_manifest, regions,
                                                   seed=args.seed)
                if args.gutters:
                    panels += framing.gutter_orders(slot_manifest, regions,
                                                    seed=args.seed)
                if args.pilasters:
                    panels += framing.pilaster_orders(slot_manifest, regions,
                                                      seed=args.seed)
            if args.panel_fields and slot_manifest is not None \
                    and not args.anchor_patina_space:
                panels += paneling.panel_orders(
                    slot_manifest, regions, seed=args.seed,
                    panel=args.panel_size, gap=args.panel_gap)
            dm = trim.dressing_manifest(
                emit_list, regions, seed=args.seed,
                source=os.path.basename(out_glb),
                sheet_file=os.path.basename(sheet_path),
                space=space, building_id=building_id,
                extra_orders=panels)
            dpath = out_glb[:-4] + ".dressing.json"
            with open(dpath, "w", encoding="utf-8") as fh:
                json.dump(dm, fh, indent=2, sort_keys=True)
                fh.write("\n")
            result["trim_sheet"] = sheet_path
            result["dressing"] = {"orders": len(dm["orders"]),
                                  "covers": dm["counts"], "sidecar": dpath}

    # Trim sheet without dressing (atlas only — the texture half on its own).
    if args.trim_sheet and not result.get("trim_sheet"):
        import json as _json
        sheet_bytes, regions = trim.build_sheet(
            size=args.size, seed=args.seed, family=family)
        sheet_path = out_glb[:-4] + ".trim.png"
        with open(sheet_path, "wb") as fh:
            fh.write(sheet_bytes)
        rpath = out_glb[:-4] + ".trim.json"
        with open(rpath, "w", encoding="utf-8") as fh:
            _json.dump({"schema": "patina-trim/1",
                        "trim_sheet": os.path.basename(sheet_path),
                        "regions": trim.regions_dict(regions)}, fh,
                       indent=2, sort_keys=True)
            fh.write("\n")
        result["trim_sheet"] = sheet_path

    # Look preview (v0.13): render the composite (vertex colour x stand-in Lux
    # banded light) so the multiplicative-darkening risk is visible before the
    # engine walk. Reports luma headroom for Lux's bands.
    if args.preview:
        from . import preview as preview_mod
        try:
            from PIL import Image
            popts = preview_mod.PreviewOptions()
            pimg = preview_mod.render(scene, popts)
            stats = preview_mod.luma_stats(pimg, popts.bg)
            ppath = out_glb[:-4] + ".preview.png"
            Image.fromarray((pimg * 255).astype("uint8"), "RGB").save(ppath)
            result["preview"] = ppath
            result["preview_stats"] = stats
        except Exception as e:                       # preview is best-effort
            result["preview_error"] = str(e)

    man = manifest.build(scene, mode=args.mode, seed=args.seed,
                         textures=textures_rel, theme=theme,
                         decal_placements=placements,
                         decal_textures=decal_tex_rel,
                         overrides=result.get("overrides"),
                         family=family,
                         anchor_counts=anchor_counts or None,
                         slot_manifest=slot_manifest,
                         depth=result.get("depth"))
    manifest.validate(man)
    man_path = out_glb[:-4] + ".json"     # <name>.patina.json
    manifest.write(man, man_path)
    result["manifest"] = man_path

    # Re-emit the gameplay.json unchanged next to the styled output (Patina is
    # visual-only; markers/collision are the original's, untouched).
    if scene.gameplay is not None:
        import json
        gp_out = out_glb[:-4] + ".gameplay.json"
        with open(gp_out, "w", encoding="utf-8") as fh:
            json.dump(scene.gameplay, fh, indent=2)
        result["gameplay"] = gp_out

    result["stats"] = scene.stats()
    result["mode"] = args.mode
    result["roles"] = surfaces.role_counts(scene)
    return result


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="patina",
        description="Automated PS1-era styling pass for Deli Counter greyboxes.")
    p.add_argument("input", help="Deli Counter .glb shell")
    p.add_argument("--mode", choices=["vertex-color", "procedural", "byo"],
                   default="vertex-color",
                   help="vertex-color (default, lightest), procedural (generated tiles), "
                        "or byo (user texture folder)")
    p.add_argument("--textures", metavar="DIR", default=None,
                   help="byo mode: folder of low-res textures keyed by role "
                        "(floor/wall/ceiling/trim; exterior_wall/roof optional)")
    p.add_argument("--theme", default="default", metavar="NAME|PATH",
                   help="theme preset: builtin name "
                        f"({', '.join(themes.builtin_names())}) or a theme "
                        ".json path. default reproduces v0.1.x output.")
    p.add_argument("--skin", metavar="STYLE[:SEEDS]", default=None,
                   help="procedurally generate a skin: STYLE "
                        f"({', '.join(skins.style_names())}) optionally with "
                        "SEEDS = 1-3 #hex colours (dominant[,secondary,accent]) "
                        "or a color_swatch library/palette .json. Builds a "
                        "60/30/10 shadow/base/light look and locks to it. "
                        "e.g. --skin grimy:#4a5a3f  or  --skin neon:#ff0055,#00ffcc")
    p.add_argument("--skin-from", metavar="FILE", default=None,
                   help="seed a skin from a color_swatch library (liked "
                        "colours) or a saved 60/30/10 palette json; combine "
                        "with --skin STYLE to set the mood")
    p.add_argument("--family", metavar="NAME|PATH", default=None,
                   help="texture family: the shared, limited colour library "
                        "every surface locks to for cohesion. Builtin name "
                        f"({', '.join(families.builtin_names())}) or a "
                        "family.json path. Reuse the same family across every "
                        "shell to make the whole game read as one place.")
    p.add_argument("--extract-family", metavar="IMAGE[:K]", default=None,
                   help="derive a K-colour family from a reference image "
                        "(default K=8) via deterministic k-means, lock to it, "
                        "and save it as <out>.family.json. Overrides --family.")
    p.add_argument("--override", action="append", metavar="KEY=VALUE", default=[],
                   help="art-bash one material key: KEY=#hex[,#hex...] recolours "
                        "(albedo), KEY=path/to/image.(png|jpg|webp) skins it. "
                        "Repeatable; wins over --overrides. e.g. "
                        "--override floor=./ref/lino.jpg --override wall=#5a5348")
    p.add_argument("--overrides", metavar="FILE", default=None,
                   help="saved bash session: JSON of {key: {image|albedo|tint|"
                        "pattern|process}}; relative image paths resolve next "
                        "to the file")
    p.add_argument("--slot-variation", action="store_true",
                   help="with a DC slots.json: bake deterministic per-slot "
                        "colour variation (keyed by slot_id) into vertex colour "
                        "and emit <out>.instances.json (per-instance color/"
                        "custom_data) — breaks modular repetition")
    p.add_argument("--slot-variation-strength", type=float, default=0.12,
                   help="per-slot brightness jitter amount (0-0.5, default 0.12)")
    p.add_argument("--preview", action="store_true",
                   help="render a composite look preview (<out>.preview.png) "
                        "approximating vertex colour x Lux banded light, and "
                        "report luma headroom — surfaces the over-darkening risk "
                        "before the Godot engine walk")
    p.add_argument("--depth", metavar="PRESET", default=None,
                   help="layer colour-theory depth cues (saturated shadow "
                        "gradients + atmospheric recession): a preset name "
                        f"({', '.join(depth_mod.preset_names())}) or 'off'")
    p.add_argument("--trim-sheet", action="store_true",
                   help="generate a family-locked trim atlas (roof edge, panel "
                        "seam, pipe run, corner guard, foundation, conduit, "
                        "flashing) to <out>.trim.png + a UV-region map")
    p.add_argument("--frames", action="store_true",
                   help="with --dressing + slots.json: one frame cover order "
                        "per doorway/window opening (exact rect from DC's "
                        "fit.openings)")
    p.add_argument("--gutters", action="store_true",
                   help="with --dressing + slots.json: a gutter_run per "
                        "exterior wall slot, just under the roofline")
    p.add_argument("--pilasters", action="store_true",
                   help="with --dressing + slots.json: a vertical pilaster "
                        "at each exterior wall slot's module seam")
    p.add_argument("--panel-fields", action="store_true",
                   help="with --dressing + a DC slots.json: emit one "
                        "panel_field cover order per grid cell on every "
                        "exterior wall slot (thin proud panels; the "
                        "highest-ROI facade cover). Requires spec-space "
                        "manifests (not --anchor-patina-space)")
    p.add_argument("--panel-size", type=float, default=1.2,
                   help="target panel edge in metres (default 1.2)")
    p.add_argument("--panel-gap", type=float, default=0.03,
                   help="gap between panels in metres (default 0.03)")
    p.add_argument("--dressing", action="store_true",
                   help="with --anchors: emit <out>.dressing.json — per-anchor "
                        "non-collision cover build orders (trim piece + UV "
                        "region + position) for Zoo to build; emits the trim "
                        "atlas too")
    p.add_argument("--no-slots", action="store_true",
                   help="ignore a sibling DC slots.json even when present "
                        "(fall back to whole-mesh, geometry-derived styling)")
    p.add_argument("--anchors", action="store_true",
                   help="emit a <out>.anchors.json sidecar of visual-only "
                        "placement hints (roofline / wall_base / "
                        "exterior_light / ground_edge) for downstream geometry "
                        "tools (Lux/Zoo/dressing kit). Patina places; they "
                        "supply the mesh. Collision/gameplay untouched.")
    p.add_argument("--anchor-patina-space", action="store_true",
                   help="emit anchors in Patina's baked Y-up space instead of "
                        "DC's Blender Z-up (only relevant with a slots.json)")
    p.add_argument("--anchor-kinds", nargs="+", metavar="KIND",
                   choices=list(anchors.ANCHOR_KINDS), default=None,
                   help="limit anchor kinds (default: all — "
                        f"{', '.join(anchors.ANCHOR_KINDS)})")
    p.add_argument("--no-bands", action="store_true",
                   help="disable vertical material-variation bands even when "
                        "the theme/skin declares them")
    p.add_argument("--no-decals", action="store_true",
                   help="skip the theme's decal pass")
    p.add_argument("--decal-scale", type=float, default=1.0,
                   help="decal density multiplier (1.0 = theme's values)")
    p.add_argument("--no-bevel", action="store_true",
                   help="disable bevel sub-step (budget control)")
    p.add_argument("--no-densify", action="store_true",
                   help="disable densify sub-step (budget control)")
    p.add_argument("--mottle", type=float, default=0.0,
                   help="surface mottle strength: mid-freq value breakup on flat "
                        "faces so walls aren't one tone (0=off, ~0.2-0.3 typical). "
                        "Needs densify for resolution.")
    p.add_argument("--mottle-scale", type=float, default=1.5,
                   help="world-space size (m) of the largest mottle variation")
    p.add_argument("--texel", type=float, default=2.0,
                   help="world-space metres per texture tile (UV density)")
    p.add_argument("--posterize", type=int, default=16,
                   help="colour-depth target for generated textures (~16 = PS1)")
    p.add_argument("--size", type=int, default=128, help="generated tile size in px")
    p.add_argument("--seed", type=int, default=version.DEFAULT_SEED,
                   help="determinism seed (default matches Deli Counter)")
    p.add_argument("--target-edge", type=float, default=0.75,
                   help="densify target edge length in metres")
    p.add_argument("--max-subdiv", type=int, default=4,
                   help="max densify levels (budget clamp)")
    p.add_argument("--templates", action="store_true",
                   help="write per-material paint templates (metre grid + "
                        "key label) to <out>.templates/ — the byo painting "
                        "workflow")
    p.add_argument("--start-skins", action="store_true",
                   help="write Texpaint-style triangle-unique start skins "
                        "from authored UV0 to <out>.templates/ (model "
                        "skinning; meshes without UV0 are skipped)")
    p.add_argument("--skin-size", type=int, default=256,
                   help="start-skin sheet size in px")
    p.add_argument("--out", default=None, help="output .glb path "
                   "(default <input>.patina.glb)")
    p.add_argument("--passthrough", action="store_true",
                   help="P0 I/O spine only: load and re-emit, no styling")
    p.add_argument("--version", action="version",
                   version=f"Patina {version.__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not os.path.exists(args.input):
        print(f"[patina] input not found: {args.input}", file=sys.stderr)
        return 2
    res = run(args)
    print(f"[patina] {res.get('mode')} / theme={res.get('theme', 'default')} "
          f"-> {res['output_glb']}")
    if res.get("decals"):
        print(f"[patina] decals: {res['decals']} placed")
    if res.get("preview"):
        s = res["preview_stats"]
        flag = "OK" if s.get("headroom_ok") else "TOO DARK — reduce bake strengths"
        print(f"[patina] preview -> {res['preview']}")
        print(f"[patina]   luma mean {s.get('luma_mean')} p10 {s.get('luma_p10')} "
              f"crushed {s.get('crushed_frac')} -> {flag}")
    if res.get("depth"):
        print(f"[patina] depth cues: {res['depth']} (saturated shadows + atmosphere)")
    if res.get("trim_sheet"):
        print(f"[patina] trim sheet -> {res['trim_sheet']}")
    if res.get("dressing"):
        dg = res["dressing"]
        summary = ", ".join(f"{k}:{v}" for k, v in sorted(dg["covers"].items()))
        print(f"[patina] dressing -> {dg['sidecar']} ({dg['orders']} orders: {summary})")
    if res.get("slot_variation"):
        sv = res["slot_variation"]
        print(f"[patina] slot variation: {sv['faces_varied']} faces, "
              f"{sv['instances']} instances -> {sv['sidecar']}")
    if res.get("slots"):
        s = res["slots"]
        print(f"[patina] aligned to DC slots.json v{s['version']}: "
              f"{s['building_id']} / theme={s['theme']} ({s['count']} slots)")
    if res.get("family_from_slots"):
        print(f"[patina] family from slot theme '{res['family_from_slots']}'")
    if res.get("anchor_counts"):
        summary = ", ".join(f"{k}:{n}" for k, n in
                            sorted(res["anchor_counts"].items()))
        print(f"[patina] anchors -> {res['anchors']} ({summary})")
    if res.get("bands"):
        print(f"[patina] vertical bands: {', '.join(res['bands'])}")
    if res.get("skin"):
        print(f"[patina] skin: {res['skin']} ({res['skin_style']}) — "
              "60/30/10 generated, locked")
    if res.get("family"):
        print(f"[patina] family: {res['family']} "
              f"({len(res.get('family_colors', []))} colours) — all surfaces locked")
    if res.get("overrides"):
        for key, desc in res["overrides"].items():
            print(f"[patina] override {key}: {desc}")
    if res.get("templates"):
        print(f"[patina] paint templates: {res['templates']} "
              f"-> {res['templates_dir']}")
    if "start_skins" in res:
        print(f"[patina] start skins: {res['start_skins']} written")
    if "manifest" in res:
        print(f"[patina] manifest -> {res['manifest']}")
    s = res.get("stats", {})
    if s:
        print(f"[patina] visual {s.get('visual_tris')} tris "
              f"across {s.get('visual_meshes')} meshes; "
              f"collision {s.get('collision_tris')} tris (untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
