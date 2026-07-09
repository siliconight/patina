"""The ``.patina.json`` style manifest (TDD 4.2, 5.4, 7.1).

This small JSON file is the seam between the offline asset pass and the Godot
addon. It says, per surface role, which material/shader settings to apply, what
the PS1 shader parameters are, and — for the modeler handoff — the role and
world-space bounds of every visual mesh (the kit-bash hooks of 7.1).

Determinism note: the manifest contains no timestamps and lists everything in
sorted order, so two runs on the same input produce byte-identical JSON.
"""

from __future__ import annotations

import json
import os
from importlib import resources

import jsonschema

from . import version
from .mesh import Scene, SurfaceRole
from .surfaces import role_counts


# Default PS1 shader parameters (the in-engine half reads these). Tuned to the
# "minimal / readability-first" principle, not maximal grunge.
def default_shader() -> dict:
    return {
        "name": "ps1",
        "vertex_jitter": 64,        # snap grid resolution; lower = more jitter
        "affine_strength": 0.85,    # 1.0 = full affine (no perspective correct)
        "color_depth": 16,          # levels per channel
        "dither": True,
        "ambient": [1.0, 1.0, 1.0], # white ambient; lighting comes from vertex colour
        "fog": {"enabled": True, "color": [0.10, 0.10, 0.12],
                "near": 12.0, "far": 48.0},
    }


def _surface_block(used_roles: set[SurfaceRole], textures: dict[str, str],
                   mode: str) -> dict:
    block: dict[str, dict] = {}
    for r in sorted(used_roles, key=lambda x: x.value):
        entry = {
            "vertex_color": True,
            "uv_channel": "uv1",
            "texture": textures.get(r.value),     # None in vertex-color mode
        }
        block[r.value] = entry
    return block


def build(scene: Scene, *, mode: str, seed: int,
          textures: dict[str, str] | None = None,
          shader: dict | None = None,
          theme=None,
          decal_placements: list | None = None,
          decal_textures: dict[str, str] | None = None,
          overrides: dict[str, str] | None = None,
          family=None,
          anchor_counts: dict[str, int] | None = None,
          slot_manifest=None, depth: str | None = None) -> dict:
    textures = textures or {}
    used = {r for r in (SurfaceRole(k) for k in role_counts(scene))}
    kitbash = []
    for mesh in sorted(scene.visual_meshes(), key=lambda m: m.name):
        pts = [p.positions for p in mesh.primitives if p.vertex_count()]
        if not pts:
            continue
        import numpy as np
        allp = np.vstack(pts)
        # Majority role for the whole mesh (handoff granularity is the piece).
        rc: dict[str, int] = {}
        for prim in mesh.primitives:
            if prim.face_roles is None:
                continue
            for role in prim.face_roles:
                rc[role.value] = rc.get(role.value, 0) + 1
        kitbash.append({
            "mesh": mesh.name,
            "role": max(rc, key=rc.get) if rc else SurfaceRole.UNKNOWN.value,
            "bounds_min": [round(float(v), 4) for v in allp.min(0)],
            "bounds_max": [round(float(v), 4) for v in allp.max(0)],
        })
    instances = [{
        "type": p.type,
        "pos": list(p.pos),
        "normal": list(p.normal),
        "size": list(p.size),
        "rot": p.rot,
    } for p in (decal_placements or [])]
    return {
        "schema": version.MANIFEST_SCHEMA_VERSION,
        "generator": f"Patina {version.__version__}",
        "source": os.path.basename(scene.source_path or ""),
        "seed": seed,
        "mode": mode,
        "theme": {
            "name": getattr(theme, "name", "default"),
            "palette": dict(getattr(theme, "palette", {}) or {}),
        },
        "shader": shader or default_shader(),
        "surfaces": _surface_block(used, textures, mode),
        "decals": {
            "textures": dict(decal_textures or {}),
            "instances": instances,
        },
        "kitbash": kitbash,
        "stats": scene.stats(),
        **({"overrides": dict(overrides)} if overrides else {}),
        **({"family": {"name": family.name, "colors": list(family.colors)}}
           if family is not None else {}),
        **({"anchors": {"sidecar": "<out>.anchors.json",
                        "counts": dict(sorted(anchor_counts.items()))}}
           if anchor_counts else {}),
        **({"slots": {"aligned": True,
                      "manifest_version": slot_manifest.version,
                      "building_id": slot_manifest.building_id,
                      "theme": slot_manifest.theme,
                      "slot_count": len(slot_manifest.slots)}}
           if slot_manifest is not None else {}),
        **({"depth": depth} if depth else {}),
    }


def write(manifest: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")


def load_schema() -> dict:
    with resources.files("patina.schema").joinpath("patina.schema.json").open("r") as fh:
        return json.load(fh)


def validate(manifest: dict) -> None:
    """Raise jsonschema.ValidationError if the manifest is malformed."""
    jsonschema.validate(manifest, load_schema())
    # Cross-check: every surface role resolves to a spec (TDD 8.1).
    for role, spec in manifest.get("surfaces", {}).items():
        if "vertex_color" not in spec or "uv_channel" not in spec:
            raise jsonschema.ValidationError(f"surface {role!r} missing material spec")
    # Cross-check: every placed decal resolves to a texture the addon can load.
    dec = manifest.get("decals", {})
    tex = dec.get("textures", {})
    for inst in dec.get("instances", []):
        if inst.get("type") not in tex:
            raise jsonschema.ValidationError(
                f"decal instance type {inst.get('type')!r} has no texture entry")
