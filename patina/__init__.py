"""Patina — an automated PS1-era styling pass for Deli Counter greyboxes.

Public, stable surface for the offline asset pass. The Godot side lives under
``godot/`` and is wired up in-engine, not imported here.
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
