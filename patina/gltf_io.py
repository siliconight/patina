"""glTF I/O spine (TDD phase P0).

Reads a Deli Counter ``.glb`` into the :mod:`patina.mesh` IR and writes the IR
back out *deterministically* — same IR in, byte-identical ``.glb`` out, every
run, every machine. Determinism comes from controlling the writer end to end:

* one buffer, fixed bufferView / accessor ordering;
* fixed component types (positions/normals/uv float32, indices uint32,
  vertex colour float32 VEC4);
* a fixed ``asset.generator`` string (the release version, never a timestamp);
* no extension or metadata that varies between runs.

Note on "identical" (P0): re-emitting through a different writer than Blender's
is *not* byte-identical to Blender's original bytes — no two glTF exporters
agree to the byte. What P0 actually guarantees, and what the tests check, is
(a) geometry round-trips value-for-value (load → save → load preserves
positions / indices / normals / uv / colour), and (b) Patina's own output is
deterministic run-to-run. That is the meaningful, testable reading of "write
identical .glb".
"""

from __future__ import annotations

import json
import os
import struct
from typing import Optional

import numpy as np
import pygltflib as gl

from . import version
from .mesh import Mesh, MeshKind, Primitive, Scene, classify_kind

# glTF component types -> numpy dtype
_COMPONENT_DTYPE = {
    5120: np.int8, 5121: np.uint8, 5122: np.int16,
    5123: np.uint16, 5125: np.uint32, 5126: np.float32,
}
_COMPONENT_MAXNORM = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}
_TYPE_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

def _accessor_array(g: gl.GLTF2, blob: bytes, idx: int) -> np.ndarray:
    acc = g.accessors[idx]
    bv = g.bufferViews[acc.bufferView]
    dtype = _COMPONENT_DTYPE[acc.componentType]
    ncomp = _TYPE_NCOMP[acc.type]
    comp_size = np.dtype(dtype).itemsize
    elem_size = comp_size * ncomp
    base = (bv.byteOffset or 0) + (acc.byteOffset or 0)
    stride = bv.byteStride or elem_size
    out = np.empty((acc.count, ncomp), dtype=dtype)
    for i in range(acc.count):
        start = base + i * stride
        out[i] = np.frombuffer(blob, dtype=dtype, count=ncomp, offset=start)
    arr = out.astype(np.float32) if dtype != np.float32 else out
    if getattr(acc, "normalized", False) and acc.componentType in _COMPONENT_MAXNORM:
        arr = arr.astype(np.float32) / _COMPONENT_MAXNORM[acc.componentType]
    return arr


def _node_matrix(node: gl.Node) -> np.ndarray:
    if node.matrix:
        # glTF stores column-major; reshape row-major then transpose -> M (M @ col).
        return np.array(node.matrix, dtype=np.float64).reshape((4, 4)).T
    m = np.eye(4, dtype=np.float64)
    if node.scale:
        m = m @ np.diag([*node.scale, 1.0])
    if node.rotation:  # quaternion (x, y, z, w)
        x, y, z, w = node.rotation
        r = np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0],
            [0, 0, 0, 1],
        ], dtype=np.float64)
        m = r @ m
    if node.translation:
        t = np.eye(4, dtype=np.float64)
        t[:3, 3] = node.translation
        m = t @ m
    return m


def _triangulate(indices: Optional[np.ndarray], vcount: int, mode: int) -> np.ndarray:
    if indices is None:
        seq = np.arange(vcount, dtype=np.uint32)
    else:
        seq = indices.reshape(-1).astype(np.uint32)
    if mode in (4, None):                         # TRIANGLES
        return seq.reshape((-1, 3))
    if mode == 5:                                 # TRIANGLE_STRIP
        tris = [(seq[i], seq[i + 1], seq[i + 2]) if i % 2 == 0
                else (seq[i + 1], seq[i], seq[i + 2]) for i in range(len(seq) - 2)]
        return np.array(tris, dtype=np.uint32)
    if mode == 6:                                 # TRIANGLE_FAN
        tris = [(seq[0], seq[i], seq[i + 1]) for i in range(1, len(seq) - 1)]
        return np.array(tris, dtype=np.uint32)
    raise ValueError(f"unsupported primitive mode {mode}")


def load_glb(path: str) -> Scene:
    """Load a ``.glb`` (or ``.gltf``) into a Patina :class:`Scene`."""
    g = gl.GLTF2().load(path)
    blob = g.binary_blob() or b""
    scene = Scene(source_path=path)

    # Walk the default scene's node tree, accumulating world transforms.
    root_nodes = (g.scenes[g.scene or 0].nodes if g.scenes else range(len(g.nodes)))

    def walk(node_idx: int, parent_m: np.ndarray) -> None:
        node = g.nodes[node_idx]
        world = parent_m @ _node_matrix(node)
        if node.mesh is not None:
            gmesh = g.meshes[node.mesh]
            name = node.name or gmesh.name or f"mesh_{node.mesh}"
            mesh = Mesh(name=name, kind=classify_kind(name), transform=world)
            for prim in gmesh.primitives:
                attrs = prim.attributes
                pos = _accessor_array(g, blob, attrs.POSITION)
                idx = (_accessor_array(g, blob, prim.indices)
                       if prim.indices is not None else None)
                tris = _triangulate(idx, pos.shape[0], prim.mode)
                p = Primitive(
                    positions=pos.astype(np.float32),
                    indices=tris.astype(np.uint32),
                    normals=_accessor_array(g, blob, attrs.NORMAL) if attrs.NORMAL is not None else None,
                    uv0=_accessor_array(g, blob, attrs.TEXCOORD_0) if attrs.TEXCOORD_0 is not None else None,
                    uv1=_accessor_array(g, blob, attrs.TEXCOORD_1) if attrs.TEXCOORD_1 is not None else None,
                    color=_accessor_array(g, blob, attrs.COLOR_0) if attrs.COLOR_0 is not None else None,
                    material_name=(g.materials[prim.material].name
                                   if prim.material is not None and g.materials else None),
                )
                if p.color is not None and p.color.shape[1] == 3:  # pad VEC3 colour to RGBA
                    p.color = np.hstack([p.color, np.ones((p.color.shape[0], 1), np.float32)])
                mesh.primitives.append(p)
            scene.meshes.append(mesh)
        for child in (node.children or []):
            walk(child, world)

    for n in root_nodes:
        walk(n, np.eye(4, dtype=np.float64))

    # Pick up the sibling gameplay.json if present (markers / surface hints).
    scene.gameplay = _load_gameplay(path)
    # Pick up the sibling slots.json (DC's modular art-pass manifest, v1.x).
    scene.slots = _load_slots(path)
    return scene


def _load_slots(glb_path: str) -> Optional[dict]:
    base = glb_path[:-4] if glb_path.lower().endswith(".glb") else glb_path
    for cand in (base + ".slots.json", glb_path + ".slots.json"):
        if os.path.exists(cand):
            with open(cand, "r", encoding="utf-8") as fh:
                return json.load(fh)
    return None


def _load_gameplay(glb_path: str) -> Optional[dict]:
    for cand in _gameplay_candidates(glb_path):
        if os.path.exists(cand):
            with open(cand, "r", encoding="utf-8") as fh:
                return json.load(fh)
    return None


def _gameplay_candidates(glb_path: str) -> list[str]:
    base = glb_path[:-4] if glb_path.lower().endswith(".glb") else glb_path
    # Deli Counter writes <name>.gameplay.json next to <name>.glb.
    return [base + ".gameplay.json", glb_path + ".gameplay.json"]


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

class _BufferBuilder:
    """Accumulates 4-byte-aligned bufferViews into one binary blob."""

    def __init__(self) -> None:
        self.data = bytearray()
        self.views: list[gl.BufferView] = []

    def add(self, raw: bytes, target: Optional[int]) -> int:
        while len(self.data) % 4 != 0:           # 4-byte alignment
            self.data.append(0)
        offset = len(self.data)
        self.data.extend(raw)
        self.views.append(gl.BufferView(
            buffer=0, byteOffset=offset, byteLength=len(raw), target=target))
        return len(self.views) - 1


def _matrix_to_column_major(m: np.ndarray) -> list[float]:
    return [float(v) for v in m.T.reshape(16)]


def save_glb(scene: Scene, path: str) -> None:
    """Serialise a :class:`Scene` to a deterministic ``.glb``."""
    g = gl.GLTF2()
    g.asset = gl.Asset(version="2.0", generator=f"Patina {version.__version__}")
    bb = _BufferBuilder()

    def push_accessor(arr: np.ndarray, ctype: int, atype: str,
                      target: int, with_minmax: bool = False) -> int:
        view = bb.add(np.ascontiguousarray(arr).tobytes(), target)
        acc = gl.Accessor(
            bufferView=view, componentType=ctype, count=int(arr.shape[0]), type=atype)
        if with_minmax:
            acc.min = [float(v) for v in arr.min(axis=0)]
            acc.max = [float(v) for v in arr.max(axis=0)]
        g.accessors.append(acc)
        return len(g.accessors) - 1

    material_index: dict[str, int] = {}

    def material_for(name: Optional[str]) -> Optional[int]:
        if name is None:
            return None
        if name not in material_index:
            g.materials.append(gl.Material(name=name))
            material_index[name] = len(g.materials) - 1
        return material_index[name]

    node_indices: list[int] = []
    for mesh in scene.meshes:
        gmesh = gl.Mesh(name=mesh.name)
        for p in mesh.primitives:
            attrs = gl.Attributes()
            attrs.POSITION = push_accessor(
                p.positions.astype(np.float32), 5126, "VEC3", 34962, with_minmax=True)
            if p.normals is not None:
                attrs.NORMAL = push_accessor(p.normals.astype(np.float32), 5126, "VEC3", 34962)
            if p.uv0 is not None:
                attrs.TEXCOORD_0 = push_accessor(p.uv0.astype(np.float32), 5126, "VEC2", 34962)
            if p.uv1 is not None:
                attrs.TEXCOORD_1 = push_accessor(p.uv1.astype(np.float32), 5126, "VEC2", 34962)
            if p.color is not None:
                attrs.COLOR_0 = push_accessor(p.color.astype(np.float32), 5126, "VEC4", 34962)
            iacc = push_accessor(p.indices.reshape(-1).astype(np.uint32), 5125, "SCALAR", 34963)
            gmesh.primitives.append(gl.Primitive(
                attributes=attrs, indices=iacc, mode=4,
                material=material_for(p.material_name)))
        g.meshes.append(gmesh)
        node = gl.Node(name=mesh.name, mesh=len(g.meshes) - 1)
        if not np.allclose(mesh.transform, np.eye(4)):
            node.matrix = _matrix_to_column_major(mesh.transform)
        g.nodes.append(node)
        node_indices.append(len(g.nodes) - 1)

    g.scenes = [gl.Scene(nodes=node_indices)]
    g.scene = 0
    g.buffers = [gl.Buffer(byteLength=len(bb.data))]
    g.bufferViews = bb.views
    g.set_binary_blob(bytes(bb.data))
    g.save_binary(path)


def round_trip(in_path: str, out_path: str) -> Scene:
    """P0 helper: load then save unchanged. Proves the I/O spine."""
    scene = load_glb(in_path)
    save_glb(scene, out_path)
    return scene
