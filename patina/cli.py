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

from . import gltf_io, manifest, nuance, palette, surfaces, uvproject, version
from .mesh import Scene, SurfaceRole


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

    opts = nuance.NuanceOptions(
        densify=not args.no_densify,
        bevel=not args.no_bevel,
        vertex_color=True,
        target_edge=args.target_edge,
        max_subdiv=args.max_subdiv,
    )
    if opts.densify:
        nuance.densify(scene, opts)
    beveled = nuance.bevel(scene, opts)          # bpy bridge; no-op if unavailable
    if opts.bevel and not beveled:
        print("[patina] geometric bevel skipped (no bpy bridge); "
              "edge-cavity AO stands in.", file=sys.stderr)

    surfaces.classify(scene)
    if opts.vertex_color:
        nuance.vertex_color(scene, opts)

    used_roles = {SurfaceRole(k) for k in surfaces.role_counts(scene)}
    textures_rel: dict[str, str] = {}
    if args.mode != "vertex-color":
        uvproject.project(scene, texel=args.texel)
        pal_opts = palette.PaletteOptions(
            mode=args.mode, size=args.size, posterize=args.posterize,
            byo_dir=args.textures, seed=args.seed)
        tiles = palette.build_palette(used_roles, pal_opts)
        if tiles:
            tex_dir = out_glb[:-4] + ".textures"
            os.makedirs(tex_dir, exist_ok=True)
            for role, data in tiles.items():
                fname = f"{role}.png"
                with open(os.path.join(tex_dir, fname), "wb") as fh:
                    fh.write(data)
                textures_rel[role] = os.path.join(os.path.basename(tex_dir), fname)
            result["textures_dir"] = tex_dir

    gltf_io.save_glb(scene, out_glb)

    man = manifest.build(scene, mode=args.mode, seed=args.seed, textures=textures_rel)
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
                        "(floor/wall/ceiling/trim)")
    p.add_argument("--no-bevel", action="store_true",
                   help="disable bevel sub-step (budget control)")
    p.add_argument("--no-densify", action="store_true",
                   help="disable densify sub-step (budget control)")
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
    print(f"[patina] {res.get('mode')} -> {res['output_glb']}")
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
