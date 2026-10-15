"""Patina — an automated PS1-era styling pass for Deli Counter greyboxes.

Public, stable surface for the offline asset pass. There is no Godot side since
0.32.0: the engine look is Lux's, and the styled ``.glb`` imports as any glTF does.
"""

from .version import __version__, DEFAULT_SEED, MANIFEST_SCHEMA_VERSION
from .mesh import Mesh, MeshKind, Primitive, Scene, SurfaceRole
from .gltf_io import load_glb, save_glb, round_trip

__all__ = [
    "__version__",
    "DEFAULT_SEED",
    "MANIFEST_SCHEMA_VERSION",
    "Mesh",
    "MeshKind",
    "Primitive",
    "Scene",
    "SurfaceRole",
    "load_glb",
    "save_glb",
    "round_trip",
]
