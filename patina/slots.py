"""Modular alignment (v0.9): the DC/Zoo slot pipeline.

Patina predates the modular setup. Deli Counter (>=0.37) now emits a
``<name>.slots.json`` — one record per swappable module (wall segment, opening,
prop) with a stable ``slot_id`` join key, a ``role``, a ``current_ref`` naming a
Zoo module (``wall_greybox_01``), a ``fit`` contract (dims/pivot/openings/
collision), and a transform in **raw spec / Blender Z-up coords**. Zoo
(>=0.20) builds ``<role>_<theme>_<style>.glb`` modules to fill those slots and
already carries a named ``delco`` style (a base colour + wear scalar).

DC's own art-pass docs name the downstream this unlocks: *"Patina /
vertex-nuance — per-part targeting instead of whole-mesh."* This module is that
alignment. It does three things:

1. **Reads the manifest** (:func:`load`, :class:`SlotManifest`) so Patina can
   target styling *per slot / per module* by ``slot_id`` instead of one flat
   whole-mesh pass. Slots carry role, so a slot-driven run reuses the whole
   family/band/skin stack keyed to the slot instead of a geometric guess.

2. **Speaks the shared coordinate contract.** DC manifests are Blender Z-up raw
   coords (``[x, y, z]`` with z up), the same space ``gameplay.json`` markers
   use. Patina bakes its working glTF into world metres (y-up-ish per the glTF
   axis convention). :func:`blender_to_patina` / :func:`patina_to_blender`
   convert between them so anything Patina emits round-trips with DC's markers
   and slots — never a second, incompatible space.

3. **Draws the Zoo seam.** Zoo owns module *geometry + base material + a flat
   style colour*; Patina owns the *rich nuance pass* (family cohesion, banding,
   decals, PS1 posterize) applied per module. :func:`reconcile_family` maps a
   Zoo theme name to the Patina family that shares its palette, so a
   Zoo-``delco`` kit and Patina's ``delco_faded`` family agree instead of
   fighting. The base style colour Zoo bakes becomes the *floor* Patina's
   nuance modulates, not a competing coat.

This module is read/align only: it changes no geometry and needs no slots.json
to run (Patina's whole-mesh path stays the default when the manifest is
absent), so every prior release's output is unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

# Zoo theme name -> Patina family that shares its palette. The seam: Zoo bakes a
# flat base colour per module; Patina's family is the shared limited library the
# nuance pass locks to. They must name the same world.
_THEME_FAMILY = {
    "delco": "delco_faded",
    "greybox": None,          # greybox is unstyled; Patina leaves it neutral
}

# DC slot roles -> Patina SurfaceRole values. DC's vocabulary is module-kind
# (wall/doorway/window/breach/prop/...); Patina's is surface-kind. Openings and
# props map to the treatment their host surface would get.
_ROLE_MAP = {
    "wall": "wall",
    "wallEnd": "wall",
    "doorway": "wall",
    "window": "wall",
    "breach": "wall",
    "floor": "floor",
    "ceiling": "ceiling",
    "roof": "roof",
    "trim": "trim",
    "prop": "trim",           # props read as detail/trim for tinting purposes
}


@dataclass
class Slot:
    """One record from a DC slots.json (the fields Patina uses)."""

    slot_id: str
    role: str                         # DC module-kind
    current_ref: str                  # <type>_<theme>_<style>
    kit_axis: str = "theme"
    style: int = 1
    size_mod: str = "full"
    facing: Optional[str] = None
    story: Optional[int] = None
    translation: tuple = (0.0, 0.0, 0.0)   # Blender Z-up raw coords
    rot_y: float = 0.0
    scale: tuple = (1.0, 1.0, 1.0)
    dims: Optional[tuple] = None
    pivot: str = "center"
    collision: str = "convex"
    openings: list = field(default_factory=list)

    def patina_role(self) -> str:
        return _ROLE_MAP.get(self.role, "wall")

    def theme(self) -> Optional[str]:
        """Theme token parsed from current_ref (``wall_greybox_01`` -> greybox)."""
        parts = self.current_ref.split("_")
        return parts[1] if len(parts) >= 2 else None


@dataclass
class SlotManifest:
    version: str
    building_id: str
    theme: str
    module_library: str
    module_size: float
    space: str
    slots: list[Slot]
    coverage: dict = field(default_factory=dict)

    def by_id(self) -> dict[str, Slot]:
        return {s.slot_id: s for s in self.slots}

    def role_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for s in self.slots:
            out[s.role] = out.get(s.role, 0) + 1
        return out


def parse(raw: dict) -> SlotManifest:
    """Parse a loaded slots.json dict into a :class:`SlotManifest`."""
    slots = []
    for r in raw.get("slots", []):
        t = r.get("transform", {})
        fit = r.get("fit", {})
        slots.append(Slot(
            slot_id=r["slot_id"],
            role=r.get("role", "wall"),
            current_ref=r.get("current_ref", ""),
            kit_axis=r.get("kit_axis", "theme"),
            style=int(r.get("style", 1)),
            size_mod=r.get("size_mod", "full"),
            facing=r.get("facing"),
            story=r.get("story"),
            translation=tuple(t.get("translation", (0.0, 0.0, 0.0))),
            rot_y=float(t.get("rot_y", 0.0)),
            scale=tuple(t.get("scale", (1.0, 1.0, 1.0))),
            dims=tuple(fit["dims"]) if fit.get("dims") else None,
            pivot=fit.get("pivot", "center"),
            collision=fit.get("collision", "convex"),
            openings=list(fit.get("openings", [])),
        ))
    return SlotManifest(
        version=raw.get("slot_manifest_version", "0"),
        building_id=raw.get("building_id", ""),
        theme=raw.get("theme", "greybox"),
        module_library=raw.get("module_library", "art/zoo"),
        module_size=float(raw.get("module_size", 2.0)),
        space=raw.get("space", ""),
        slots=slots,
        coverage=dict(raw.get("coverage", {})),
    )


def load(scene) -> Optional[SlotManifest]:
    """The parsed manifest for a scene, or None if it carries no slots.json."""
    if getattr(scene, "slots", None) is None:
        return None
    return parse(scene.slots)


# --------------------------------------------------------------------------- #
# Coordinate contract
# --------------------------------------------------------------------------- #
# DC/gameplay/slots space is Blender Z-up raw coords: +Z up, +Y "north"/depth.
# glTF (Patina's baked working space) is Y-up: the glTF importer maps Blender
# (x, y, z) -> (x, z, -y). Patina bakes in that Y-up glTF space. To hand a
# position back to DC's world we invert it.

def blender_to_patina(p) -> tuple:
    """Blender Z-up (x, y, z) -> glTF/Patina Y-up (x, z, -y)."""
    x, y, z = p
    return (float(x), float(z), float(-y))


def patina_to_blender(p) -> tuple:
    """glTF/Patina Y-up (x, y, z) -> Blender Z-up (x, -z, y)."""
    x, y, z = p
    return (float(x), float(-z), float(y))


def slot_position_patina(slot: Slot) -> tuple:
    """A slot's translation in Patina's working (baked glTF) space."""
    return blender_to_patina(slot.translation)


def detect_up_axis(scene) -> int:
    """Which axis index is 'up' in the baked scene (0=X, 1=Y, 2=Z).

    The coordinate seam Patina predates: DC exports glTF with the standard
    Blender-Z-up -> glTF-Y-up conversion, so a real DC ``.glb`` loads **Y-up**
    in Patina's baked space. Patina's own hand-authored example shells were
    Z-up, which masked the difference — banding, anchors and grime all assumed
    Z-up and silently read the wrong axis on real data.

    A building is wide and shallow: the vertical extent (wall height, a few
    metres) is the *smallest* of the three axis ranges. Detecting up as the
    min-range axis makes the height-dependent passes correct for both DC's
    Y-up exports and legacy Z-up shells, with no per-file configuration.
    """
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.vertex_count():
                lo = np.minimum(lo, prim.positions.min(0))
                hi = np.maximum(hi, prim.positions.max(0))
    if not np.isfinite(lo).all():
        return 2                       # empty scene -> conventional Z-up
    ranges = hi - lo
    return int(np.argmin(ranges))


# --------------------------------------------------------------------------- #
# The Zoo aesthetic seam
# --------------------------------------------------------------------------- #

def reconcile_family(theme: str) -> Optional[str]:
    """Patina family name that shares a Zoo theme's palette (None if unstyled).

    This is the seam: Zoo bakes a flat base colour + wear per module under a
    theme name; Patina's family is the shared limited library its nuance pass
    locks to. Mapping them here keeps a Zoo-``delco`` kit and Patina's
    ``delco_faded`` family describing one world instead of two.
    """
    return _THEME_FAMILY.get(theme)


def register_theme_family(theme: str, family: Optional[str]) -> None:
    """Extend the Zoo-theme -> Patina-family map (for new themes)."""
    _THEME_FAMILY[theme] = family


def slot_tint_floor(scene, base_color=None):
    """The flat base colour Zoo baked (per-slot), as a modulation floor.

    Zoo already bakes a base style colour into each module. Patina's nuance
    multiplies *over* geometry-derived tints; when styling a Zoo module we want
    the nuance to ride on top of Zoo's base rather than replace it. This returns
    the base colour to use as that floor (falls back to a neutral grey).
    """
    return np.array(base_color if base_color is not None else (0.5, 0.49, 0.46),
                    np.float32)


# --------------------------------------------------------------------------- #
# Per-slot variation (v0.10): break modular repetition per slot_id
# --------------------------------------------------------------------------- #
# DC's art-pass docs name per-instance colour as the #1 lever against the
# "same module everywhere" failure mode, driven deterministically from the
# seed. A DC building instances one `wall_delco_01` mesh N times; without
# variation every copy is identical. Patina computes a deterministic per-slot
# factor (seeded by slot_id) and (a) bakes it into the monolith's vertex colour
# for faces spatially assigned to that slot, and (b) emits it as an `instance`
# record ({color, custom_data}) in the DC placements shape for the instanced
# bake target to feed Godot's per-instance buffers. Same variation, both paths.

from .determinism import rng_for   # noqa: E402  (kept local to this section)


def slot_factor(slot_id: str, seed: int, strength: float) -> float:
    """Deterministic per-slot brightness factor in [1-strength, 1+strength]."""
    r = rng_for(seed, "slot", slot_id)
    return float(1.0 + (r.random() * 2.0 - 1.0) * strength)


def _centers_by_role(manifest: SlotManifest):
    """{patina_role: [(slot_id, center_xyz_patina), ...]} for face assignment."""
    from collections import defaultdict
    out = defaultdict(list)
    for s in manifest.slots:
        c = np.array(blender_to_patina(s.translation), np.float32)
        out[s.patina_role()].append((s.slot_id, c))
    return out


def assign_faces(prim, centers_by_role, max_dist: float) -> np.ndarray:
    """(T,) array of slot_id (or '') per face — nearest role-matching slot
    center within ``max_dist``. Faces with no nearby matching slot stay ''."""
    if prim.face_roles is None:
        return np.array([""] * prim.triangle_count(), dtype=object)
    cent = prim.positions[prim.indices].mean(axis=1)          # (T,3)
    out = np.empty(prim.triangle_count(), dtype=object)
    out[:] = ""
    md2 = max_dist * max_dist
    for t, role in enumerate(prim.face_roles):
        cands = centers_by_role.get(role.value) or centers_by_role.get("wall")
        if not cands:
            continue
        d = [float(np.sum((cent[t] - c) ** 2)) for _, c in cands]
        j = int(np.argmin(d))
        if d[j] <= md2:
            out[t] = cands[j][0]
    return out


def apply_slot_variation(scene, manifest: SlotManifest, seed: int,
                         strength: float = 0.12) -> int:
    """Bake per-slot brightness variation into the monolith's vertex colour.

    For each visual face, assign it to the nearest role-matching slot and
    multiply its vertices' colour by that slot's factor. DC blockout faces are
    flat-shaded vertex islands (no shared vertices), so a vertex takes its one
    face's factor cleanly. Returns the count of faces varied.
    """
    centers = _centers_by_role(manifest)
    max_dist = manifest.module_size * 1.5
    factors = {s.slot_id: slot_factor(s.slot_id, seed, strength)
               for s in manifest.slots}
    varied = 0
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            if prim.color is None or prim.face_roles is None:
                continue
            face_sid = assign_faces(prim, centers, max_dist)
            vfac = np.ones(prim.vertex_count(), np.float32)
            for t, tri in enumerate(prim.indices):
                sid = face_sid[t]
                if sid:
                    f = factors[sid]
                    varied += 1
                    for vi in tri:
                        vfac[vi] = f
            prim.color[:, :3] = np.clip(prim.color[:, :3] * vfac[:, None], 0.0, 1.0)
    return varied


def _role_base_color(role: str, family) -> np.ndarray:
    """A representative family colour for a role's instance base (mid for big
    surfaces, a warmer pick for trim/prop). Neutral grey with no family."""
    if family is None:
        return np.array((0.5, 0.49, 0.46), np.float32)
    pal = family.palette_rgb()                # luma-sorted
    idx = {"floor": len(pal) // 3, "wall": len(pal) // 2,
           "ceiling": 2 * len(pal) // 3, "trim": len(pal) - 1,
           "roof": 1}.get(role, len(pal) // 2)
    return pal[min(idx, len(pal) - 1)]


def instance_records(manifest: SlotManifest, family, seed: int,
                     strength: float = 0.12) -> list[dict]:
    """Per-slot ``instance`` records in DC's placements shape.

    Each record is ``{slot_id, instance: {color: [r,g,b,a], custom_data:
    [wear,0,0,0]}}`` — the per-instance colour/custom-data buffers the DC
    instanced-bake target feeds to Godot's MultiMesh, so identical modules vary
    without duplicating the mesh. Deterministic and family-locked.
    """
    recs = []
    for s in manifest.slots:
        r = rng_for(seed, "slot", s.slot_id)
        f = 1.0 + (r.random() * 2.0 - 1.0) * strength
        wear = round(float(r.random()), 3)
        base = _role_base_color(s.patina_role(), family)
        col = np.clip(base * f, 0.0, 1.0)
        recs.append({
            "slot_id": s.slot_id,
            "instance": {
                "color": [round(float(c), 3) for c in col] + [1.0],
                "custom_data": [wear, 0.0, 0.0, 0.0],
            },
        })
    return recs


def instances_sidecar(manifest: SlotManifest, family, seed: int, *,
                      strength: float, source: str) -> dict:
    """The ``<out>.instances.json`` payload for the DC instanced-bake target."""
    return {
        "schema": "patina-instances/1",
        "source": source,
        "building_id": manifest.building_id,
        "theme": manifest.theme,
        "seed": seed,
        "variation_strength": strength,
        "space": "spec/Blender Z-up raw coords",
        "note": "per-slot instance color/custom_data; keyed by slot_id; "
                "feeds MultiMesh per-instance buffers, breaks modular repetition",
        "count": len(manifest.slots),
        "instances": instance_records(manifest, family, seed, strength),
    }
