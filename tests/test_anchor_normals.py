"""A wall's anchors face out of the building and stand on its face (0.30.0, roadmap 221).

`anchors._up_to_z` views a Y-up shell by swapping two axes, a reflection, and the anchor pass took
its wall normals from cross products in that view: every one pointed into the building. On
strip_club_a01 all 10 wall segments did, and Zoo filed every base course and conduit with the
opposite side's merge. The inside of a wall was a segment too: a floor slab's edge 0.15 m in, on a
0.3 m wall's centre line, faces out and sits within `surfaces._BOUNDARY_TOL`, and 22 of the
club's 51 base courses stood on one. And a conduit stood where its wall pack does, 0.15 m off the
face (`docs/findings/patina_cover_normals/` at the factory root).

The shell here is built in memory, wound the way glTF winds a face seen from outside: a 20 x 12 m
box with 4 m walls, and two 0.3 m slabs whose edges stop on the walls' centre line, 0.15 m in --
a floor slab under the walls and a roof slab over them, as strip_club_a01's are. So the
centre-line faces run below the walls' faces and above them.
"""
import numpy as np

from patina import anchors, surfaces
from patina.mesh import Mesh, MeshKind, Primitive, Scene

HX, HZ, H = 10.0, 6.0, 4.0          # the shell's half-width (x), half-depth (z), height (y up)
IN = 0.15                           # the slab's edge, in from the wall's face


def _quad(c, u, v, n):
    """Two triangles over centre c, half-extents u and v, wound so their normal is n."""
    c, u, v, n = (np.asarray(a, dtype=np.float64) for a in (c, u, v, n))
    if np.dot(np.cross(u, v), n) < 0:
        u, v = v, u
    pts = [c - u - v, c + u - v, c + u + v, c - u + v]
    return pts, [(0, 1, 2), (0, 2, 3)]


def _mesh(name, quads):
    pos, idx = [], []
    for pts, tris in quads:
        base = len(pos)
        pos.extend(pts)
        idx.extend([(base + a, base + b, base + c) for a, b, c in tris])
    prim = Primitive(positions=np.array(pos, np.float32), indices=np.array(idx, np.uint32))
    return Mesh(name=name, kind=MeshKind.VISUAL, primitives=[prim])


def _shell(up_axis=1):
    """The shell, Y-up as Deli Counter's glTF is, or Z-up as a legacy shell (y and z swapped,
    which is a reflection, so every quad is re-wound to keep facing out)."""
    def p(x, y, z):                      # a point given (x, up, z) in the Y-up layout
        return (x, y, z) if up_axis == 1 else (x, z, y)

    def walls(hx, hz, y0, y1):
        cy, hy = (y0 + y1) / 2.0, (y1 - y0) / 2.0
        return [
            _quad(p(hx, cy, 0.0), p(0.0, 0.0, hz), p(0.0, hy, 0.0), p(1.0, 0.0, 0.0)),
            _quad(p(-hx, cy, 0.0), p(0.0, 0.0, hz), p(0.0, hy, 0.0), p(-1.0, 0.0, 0.0)),
            _quad(p(0.0, cy, hz), p(hx, 0.0, 0.0), p(0.0, hy, 0.0), p(0.0, 0.0, 1.0)),
            _quad(p(0.0, cy, -hz), p(hx, 0.0, 0.0), p(0.0, hy, 0.0), p(0.0, 0.0, -1.0)),
        ]
    roof = [_quad(p(0.0, H + 0.3, 0.0), p(HX, 0.0, 0.0), p(0.0, 0.0, HZ), p(0.0, 1.0, 0.0))]
    return Scene(meshes=[_mesh("ext_walls", walls(HX, HZ, 0.0, H) + roof),
                         _mesh("slab_0", walls(HX - IN, HZ - IN, -0.3, 0.0)),
                         _mesh("slab_1", walls(HX - IN, HZ - IN, H, H + 0.3))])


def _anchors(up_axis=1, **kw):
    scene = _shell(up_axis)
    surfaces.classify(scene, up_axis)
    opts = anchors.AnchorOptions(ground_z=0.0, **kw)
    return anchors.generate(scene, opts, seed=1999, up_axis=up_axis)


def _horizontal(vec, up_axis):
    return (vec[0], vec[2]) if up_axis == 1 else (vec[0], vec[1])


def test_the_slab_edge_is_classified_an_exterior_wall():
    """The premise: the inside of the wall reaches the anchor pass at all."""
    scene = _shell(1)
    surfaces.classify(scene, 1)
    for name in ("slab_0", "slab_1"):
        slab = next(m for m in scene.visual_meshes() if m.name == name)
        roles = slab.primitives[0].face_roles
        assert sum(1 for r in roles if r == surfaces.SurfaceRole.EXTERIOR_WALL) == 8, name


def test_every_wall_base_faces_out_of_a_y_up_shell():
    """FAILS on 0.29.2: every normal pointed at the centre."""
    got = [a for a in _anchors(1, kinds=("wall_base",)) if a.kind == "wall_base"]
    assert got
    for a in got:
        px, pz = _horizontal(a.pos, 1)
        nx, nz = _horizontal(a.normal, 1)
        assert a.normal[1] == 0.0
        assert nx * px + nz * pz > 0, (a.pos, a.normal)


def test_a_z_up_shell_still_faces_out():
    """No reflection, no negation: the legacy frame keeps passing."""
    got = [a for a in _anchors(2, kinds=("wall_base",)) if a.kind == "wall_base"]
    assert got
    for a in got:
        px, py = _horizontal(a.pos, 2)
        nx, ny = _horizontal(a.normal, 2)
        assert nx * px + ny * py > 0, (a.pos, a.normal)


def test_no_wall_base_stands_inside_the_wall():
    """FAILS on 0.29.2: the slab's edges were segments, and anchors stood 0.15 m in."""
    got = [a for a in _anchors(1, kinds=("wall_base",)) if a.kind == "wall_base"]
    for a in got:
        px, pz = _horizontal(a.pos, 1)
        on_face = abs(abs(px) - HX) < 1e-3 or abs(abs(pz) - HZ) < 1e-3
        assert on_face, a.pos


def test_a_point_behind_a_face_is_buried_and_one_above_it_is_not():
    def seg(fixed, z_lo, z_hi):
        return {"axis": 0, "along": 1, "normal": np.array([1.0, 0.0]), "fixed": fixed,
                "a_min": -9.5, "a_max": 9.5, "z_lo": z_lo, "z_hi": z_hi}
    face = seg(HX, 0.0, H)
    inner = seg(HX - IN, -0.3, H + 0.3)          # the centre line: slabs under and over the wall
    segs = [face, inner]
    assert anchors._buried(inner, 0.0, 0.0, segs)            # a base course at the foot
    assert not anchors._buried(inner, 0.0, H + 0.3, segs)    # the roof slab's edge, above the face
    assert not anchors._buried(face, 0.0, 0.0, segs)         # the face itself
    assert not anchors._buried(inner, 12.0, 0.0, segs)       # past the face's run
    # facing the other way, it is another wall, not this one's inside
    back = dict(inner, normal=np.array([-1.0, 0.0]))
    assert not anchors._buried(back, 0.0, 0.0, [face, back])


def test_a_conduit_runs_on_its_wall_not_at_its_pack():
    """FAILS on 0.29.2: the run stood where the pack is, 0.15 m off the face."""
    target = (((HX + 0.15, 0.0, 2.45), "ext_0_E_pack_1"),)    # canonical frame, z up
    got = [a for a in _anchors(1, kinds=("exterior_light",), conduit_targets=target)
           if a.kind == "exterior_light"]
    assert len(got) == 1
    a = got[0]
    assert a.pos[0] == HX                              # the east face's plane
    assert a.tag == "ext_0_E_pack_1"
    assert a.normal[0] > 0                             # and it faces out
