"""Generate a synthetic Deli-Counter-shaped asset for tests and examples.

Deli Counter exports unit cubes scaled non-uniformly via *node* transform, a
dual VISUAL + COLLISION mesh set (collision named with a ``-colonly`` suffix),
and a sibling ``<name>.gameplay.json``. This fixture reproduces that shape so
Patina's stages and tests run against something faithful without needing
Blender or a real Deli Counter install.

Run directly to (re)write ``examples/shell.glb`` + ``examples/shell.gameplay.json``::

    python -m tests.make_fixture
"""

from __future__ import annotations

import json
import os

import numpy as np
import pygltflib as gl


def _unit_cube() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flat-shaded unit cube centred at origin: 24 verts, 12 tris, +normals."""
    faces = {
        (0, 0, 1): [(-.5, -.5, .5), (.5, -.5, .5), (.5, .5, .5), (-.5, .5, .5)],     # +Z top
        (0, 0, -1): [(-.5, .5, -.5), (.5, .5, -.5), (.5, -.5, -.5), (-.5, -.5, -.5)], # -Z bottom
        (1, 0, 0): [(.5, -.5, -.5), (.5, .5, -.5), (.5, .5, .5), (.5, -.5, .5)],      # +X
        (-1, 0, 0): [(-.5, -.5, .5), (-.5, .5, .5), (-.5, .5, -.5), (-.5, -.5, -.5)], # -X
        (0, 1, 0): [(.5, .5, -.5), (-.5, .5, -.5), (-.5, .5, .5), (.5, .5, .5)],      # +Y
        (0, -1, 0): [(-.5, -.5, -.5), (.5, -.5, -.5), (.5, -.5, .5), (-.5, -.5, .5)], # -Y
    }
    pos, nrm, idx = [], [], []
    for normal, quad in faces.items():
        base = len(pos)
        pos.extend(quad)
        nrm.extend([normal] * 4)
        idx.extend([(base, base + 1, base + 2), (base, base + 2, base + 3)])
    return (np.array(pos, np.float32), np.array(nrm, np.float32),
            np.array(idx, np.uint32))


def build(path: str) -> None:
    pos, nrm, idx = _unit_cube()
    g = gl.GLTF2()
    g.asset = gl.Asset(version="2.0", generator="DeliCounter-fixture")
    data = bytearray()
    views, accessors = [], []

    def add_view(raw: bytes, target: int) -> int:
        while len(data) % 4:
            data.append(0)
        views.append(gl.BufferView(buffer=0, byteOffset=len(data),
                                   byteLength=len(raw), target=target))
        data.extend(raw)
        return len(views) - 1

    def add_acc(arr, ctype, atype, target, minmax=False) -> int:
        v = add_view(np.ascontiguousarray(arr).tobytes(), target)
        a = gl.Accessor(bufferView=v, componentType=ctype,
                        count=int(arr.shape[0]), type=atype)
        if minmax:
            a.min = [float(x) for x in arr.min(0)]
            a.max = [float(x) for x in arr.max(0)]
        accessors.append(a)
        return len(accessors) - 1

    # One shared cube mesh, instanced by several scaled nodes.
    pa = add_acc(pos, 5126, "VEC3", 34962, minmax=True)
    na = add_acc(nrm, 5126, "VEC3", 34962)
    ia = add_acc(idx.reshape(-1), 5125, "SCALAR", 34963)
    cube = gl.Mesh(name="cube", primitives=[gl.Primitive(
        attributes=gl.Attributes(POSITION=pa, NORMAL=na), indices=ia, mode=4)])
    g.meshes.append(cube)

    # name -> (translation, scale). Non-uniform scale is the point (I-5 trap).
    pieces = {
        "floor": ([0, 0, 0], [8, 6, 0.2]),
        "ceiling": ([0, 0, 4], [8, 6, 0.2]),
        "wall_north": ([0, 3, 2], [8, 0.2, 4]),
        "wall_south": ([0, -3, 2], [8, 0.2, 4]),
        "wall_east": ([4, 0, 2], [0.2, 6, 4]),
        "wall_west": ([-4, 0, 2], [0.2, 6, 4]),
        "counter": ([1.5, -1.5, 0.5], [3, 1, 1]),         # trim-ish small box
        "floor-colonly": ([0, 0, 0], [8, 6, 0.2]),        # COLLISION twin, untouched
    }
    nodes = []
    for name, (t, s) in pieces.items():
        nodes.append(len(g.nodes))
        g.nodes.append(gl.Node(name=name, mesh=0, translation=t, scale=s))

    g.scenes = [gl.Scene(nodes=nodes)]
    g.scene = 0
    g.buffers = [gl.Buffer(byteLength=len(data))]
    g.bufferViews = views
    g.accessors = accessors
    g.set_binary_blob(bytes(data))
    g.save_binary(path)

    # Sibling gameplay.json (markers + surface hints; Patina re-emits unchanged).
    gameplay = {
        "schema": "1.6.0",
        "name": os.path.splitext(os.path.basename(path))[0],
        "mode": "heist",
        "markers": [
            {"id": "SPAWN_0", "pos": [-3, -2, 0]},
            {"id": "LOOT_0", "pos": [1.5, -1.5, 1.0]},
            {"id": "EXIT_0", "pos": [3.5, 2.5, 0]},
        ],
        "surfaces": [{"mesh": "counter", "role": "trim"}],
    }
    with open(os.path.splitext(path)[0] + ".gameplay.json", "w", encoding="utf-8") as fh:
        json.dump(gameplay, fh, indent=2)


if __name__ == "__main__":
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, "examples", "shell.glb")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    build(out)
    print(f"wrote {out} and {os.path.splitext(out)[0]}.gameplay.json")
