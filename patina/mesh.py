"""In-memory mesh representation (the IR Patina stages operate on).

The asset pass loads a Deli Counter ``.glb`` into this IR, runs stages over the
VISUAL meshes only, and serialises it back out. The two hard rules from the
TDD live here:

* **Collision is sacred.** Meshes whose node name carries a Deli Counter
  collision suffix (``-colonly`` / ``-convcolonly`` / ``-col`` / ``-convcol``)
  are classified ``COLLISION`` and never modified by any stage. They round-trip
  value-for-value, which is what the ``test_collision_untouched`` assertion
  checks (name + vertex hash, per TDD 8.1).

* **World space is the truth for scale.** Deli Counter scales unit cubes
  non-uniformly via node scale. Before any geometry or UV stage runs we *bake*
  the node transform into the vertices and reset the node to identity — exactly
  as Deli Counter's ``--vertex-nuance`` does. That single move dodges the texel
  smear / densify-by-local-units trap (TDD 5.2, review item I-5) for every
  downstream stage at once.

This module has no dependency on numpy-heavy stage code or on glTF I/O; it is
the shared vocabulary between them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

# Deli Counter encodes collision intent in the node/mesh name suffix so Godot's
# glTF importer auto-generates the collision shape. Patina reads the same
# convention to decide what it must never touch.
COLLISION_SUFFIXES = ("-convcolonly", "-colonly", "-convcol", "-col")


class MeshKind(str, Enum):
    VISUAL = "visual"
    COLLISION = "collision"


class SurfaceRole(str, Enum):
    """Per-face role used to pick tints, materials and texture variants.

    Roles are derived from face normals (and, where available, gameplay.json
    surface hints). They are intentionally coarse — the PS1 look does not need
    more than floor / wall / ceiling / trim to read.
    """

    FLOOR = "floor"
    WALL = "wall"                     # interior / undetermined vertical
    EXTERIOR_WALL = "exterior_wall"   # vertical face on the shell's outer AABB
    CEILING = "ceiling"
    ROOF = "roof"                     # up-facing face at the shell's top
    TRIM = "trim"
    UNKNOWN = "unknown"


def classify_kind(name: str) -> MeshKind:
    """VISUAL unless the name carries a Deli Counter collision suffix."""
    lname = (name or "").lower()
    for suffix in COLLISION_SUFFIXES:
        if lname.endswith(suffix):
            return MeshKind.COLLISION
    return MeshKind.VISUAL


@dataclass
class Primitive:
    """One glTF primitive: triangles plus per-vertex attributes.

    All arrays are float32/uint32 numpy arrays in *local* space until
    :func:`Mesh.bake_transform` runs, after which positions/normals are in
    world (metre) space and the owning node is identity.
    """

    positions: np.ndarray              # (V, 3) float32
    indices: np.ndarray                # (T, 3) uint32 (triangulated)
    normals: Optional[np.ndarray] = None       # (V, 3) float32
    uv0: Optional[np.ndarray] = None           # (V, 2) float32
    uv1: Optional[np.ndarray] = None           # (V, 2) float32  (Patina's box-UV channel)
    color: Optional[np.ndarray] = None         # (V, 4) float32  (vertex colour, 0..1)
    material_name: Optional[str] = None
    # Per-face surface role, filled by surfaces.classify(). Length == len(indices).
    face_roles: Optional[np.ndarray] = None    # (T,) object/str array

    def vertex_count(self) -> int:
        return int(self.positions.shape[0])

    def triangle_count(self) -> int:
        return int(self.indices.shape[0])

    def ensure_normals(self) -> np.ndarray:
        """Return per-vertex normals, computing flat-shaded ones if absent."""
        if self.normals is not None:
            return self.normals
        n = np.zeros_like(self.positions)
        tris = self.positions[self.indices]            # (T, 3, 3)
        face_n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        norm = np.linalg.norm(face_n, axis=1, keepdims=True)
        face_n = np.divide(face_n, norm, out=np.zeros_like(face_n), where=norm > 1e-12)
        for k in range(3):
            np.add.at(n, self.indices[:, k], face_n)
        norm = np.linalg.norm(n, axis=1, keepdims=True)
        n = np.divide(n, norm, out=np.zeros_like(n), where=norm > 1e-12)
        self.normals = n.astype(np.float32)
        return self.normals

    def geometry_hash(self) -> str:
        """Stable hash of positions+indices (used for the collision-untouched test)."""
        h = hashlib.sha256()
        # Round positions so float noise from a faithful round-trip doesn't trip
        # the assertion; collision is never edited so any change is structural.
        h.update(np.round(self.positions.astype(np.float64), 6).tobytes())
        h.update(np.ascontiguousarray(self.indices.astype(np.uint32)).tobytes())
        return h.hexdigest()


@dataclass
class Mesh:
    """A named mesh object (node + its primitives) with a TRS transform."""

    name: str
    kind: MeshKind
    primitives: list[Primitive] = field(default_factory=list)
    # 4x4 column-major-as-rows numpy matrix (node world transform). Identity
    # after bake_transform() for visual meshes.
    transform: np.ndarray = field(default_factory=lambda: np.eye(4, dtype=np.float64))
    baked: bool = False

    def is_visual(self) -> bool:
        return self.kind == MeshKind.VISUAL

    def bake_transform(self) -> None:
        """Fold the node transform into vertex data; reset node to identity.

        Mirrors Deli Counter's nuance pass. Positions are transformed by the
        full 4x4; normals by the inverse-transpose of the 3x3 (correct under
        non-uniform scale). Idempotent.
        """
        if self.baked or np.allclose(self.transform, np.eye(4)):
            self.transform = np.eye(4, dtype=np.float64)
            self.baked = True
            return
        m = self.transform
        rot = m[:3, :3]
        normal_mat = np.linalg.inv(rot).T
        for p in self.primitives:
            pos = p.positions.astype(np.float64)
            ones = np.ones((pos.shape[0], 1))
            world = (np.hstack([pos, ones]) @ m.T)[:, :3]
            p.positions = world.astype(np.float32)
            if p.normals is not None:
                n = (p.normals.astype(np.float64) @ normal_mat.T)
                ln = np.linalg.norm(n, axis=1, keepdims=True)
                n = np.divide(n, ln, out=np.zeros_like(n), where=ln > 1e-12)
                p.normals = n.astype(np.float32)
        self.transform = np.eye(4, dtype=np.float64)
        self.baked = True


@dataclass
class Scene:
    """Everything Patina knows about the loaded asset."""

    meshes: list[Mesh] = field(default_factory=list)
    # Carries through bits we don't model (camera, extra scene metadata) so the
    # writer can faithfully re-emit a Deli-Counter-shaped file.
    source_path: Optional[str] = None
    gameplay: Optional[dict] = None    # parsed <name>.gameplay.json, if present
    slots: Optional[dict] = None       # parsed <name>.slots.json (DC modular manifest), if present

    def visual_meshes(self) -> list[Mesh]:
        return [m for m in self.meshes if m.is_visual()]

    def collision_meshes(self) -> list[Mesh]:
        return [m for m in self.meshes if not m.is_visual()]

    def bake_visual_transforms(self) -> None:
        """Bake transforms on every visual mesh (collision left untouched)."""
        for m in self.visual_meshes():
            m.bake_transform()

    def collision_signature(self) -> dict[str, str]:
        """{collision mesh name -> geometry hash}; the pre/post invariant."""
        sig: dict[str, str] = {}
        for m in self.collision_meshes():
            parts = [p.geometry_hash() for p in m.primitives]
            sig[m.name] = hashlib.sha256("".join(parts).encode()).hexdigest()
        return sig

    def stats(self) -> dict:
        vtris = sum(p.triangle_count() for m in self.visual_meshes() for p in m.primitives)
        ctris = sum(p.triangle_count() for m in self.collision_meshes() for p in m.primitives)
        return {
            "visual_meshes": len(self.visual_meshes()),
            "collision_meshes": len(self.collision_meshes()),
            "visual_tris": vtris,
            "collision_tris": ctris,
        }
