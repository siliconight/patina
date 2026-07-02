"""Extended classification (v0.2): exterior_wall and roof via the visual AABB.

Built on synthetic primitives rather than the shell fixture so the geometry
under test is exact: an outer box (its sides are the AABB boundary) plus an
inner box (its vertical faces must stay plain ``wall``).
"""

from __future__ import annotations

import numpy as np

from patina import surfaces
from patina.mesh import Mesh, MeshKind, Primitive, Scene, SurfaceRole
from tests.make_fixture import _unit_cube


def _box_mesh(name: str, scale, offset=(0, 0, 0)) -> Mesh:
    pos, nrm, idx = _unit_cube()
    pos = pos * np.array(scale, np.float32) + np.array(offset, np.float32)
    prim = Primitive(positions=pos.astype(np.float32),
                     indices=idx.astype(np.uint32),
                     normals=nrm.astype(np.float32))
    return Mesh(name=name, kind=MeshKind.VISUAL, primitives=[prim])


def _scene(*meshes) -> Scene:
    return Scene(meshes=list(meshes), gameplay=None)


def _roles(mesh: Mesh) -> set:
    return set(mesh.primitives[0].face_roles)


def test_single_box_gets_roof_and_exterior_walls():
    # 6x4x3 m box sitting on z=0.
    shell = _box_mesh("shell", (6, 4, 3), (0, 0, 1.5))
    sc = _scene(shell)
    surfaces.classify(sc)
    roles = list(shell.primitives[0].face_roles)
    # Top face -> roof, bottom -> ceiling (down-facing), four sides -> exterior.
    assert SurfaceRole.ROOF in set(roles)
    assert SurfaceRole.EXTERIOR_WALL in set(roles)
    assert SurfaceRole.WALL not in set(roles), "all vertical faces are on the AABB"
    n_ext = sum(1 for r in roles if r is SurfaceRole.EXTERIOR_WALL)
    assert n_ext == 8, "four quads (two tris each) should be exterior walls"


def test_inner_box_stays_interior():
    outer = _box_mesh("outer", (10, 10, 4), (0, 0, 2))
    inner = _box_mesh("inner_room", (2, 2, 2), (0, 0, 1))
    sc = _scene(outer, inner)
    surfaces.classify(sc)
    inner_roles = _roles(inner)
    assert SurfaceRole.EXTERIOR_WALL not in inner_roles
    assert SurfaceRole.WALL in inner_roles
    # Inner top (z=2) is well below AABB top (z=4) -> floor, not roof.
    assert SurfaceRole.ROOF not in inner_roles
    outer_roles = _roles(outer)
    assert SurfaceRole.EXTERIOR_WALL in outer_roles
    assert SurfaceRole.ROOF in outer_roles


def test_hint_still_overrides_exterior(tmp_path):
    shell = _box_mesh("counter_thing", (6, 4, 3), (0, 0, 1.5))
    sc = _scene(shell)
    surfaces.classify(sc)
    # Name token "counter" forces the whole mesh to trim, beating geometry.
    assert _roles(shell) == {SurfaceRole.TRIM}
