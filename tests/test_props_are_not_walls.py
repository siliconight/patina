"""A prop is not the building (0.31.0, factory roadmap 248).

Deli Counter greyboxes every `prop` slot as a visual box in the shell GLB, named by its `slot_id`, and some stand
proud of a wall: a rowhome's stoop (Deli Counter 0.211.0), a corner shop's awning (0.219.0), a walk-up's fire escape
(0.220.0). `surfaces.classify` took the building's bounds from every visual mesh, so such a box moved a face's bound
out past the wall. The wall stopped reading as exterior and the box's face read as exterior instead, and the anchor
pass -- which reads exterior-wall faces only -- moved that front's coping, base course and curbs onto the box.
Measured on cold run 9303's gs_midrise_a: its front anchors roofline 12 -> 1, ground edge 8 -> 1, wall base 4 -> 1,
the one of each on the stack's box face, 1.34 m off the wall.

A mesh `classify` is told is a prop is left out of the bounds and never reads as exterior wall or roof; its faces
keep the role their normals give, and a gameplay hint still wins. The CLI names the slots.json's `prop` slots
(`SlotManifest.prop_ids`). A shell with no slots.json reads as before: nothing names its props.

FAILS ON 0.30.0: `classify` takes no `props`, and `SlotManifest` has no `prop_ids`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from patina import anchors, gltf_io, slots, surfaces
from patina.mesh import Mesh, MeshKind, Primitive, Scene, SurfaceRole
from tests.make_fixture import _unit_cube

BUILD = Path(__file__).resolve().parents[2] / "deli_counter" / "build"
#: a walk-up's fire escape (Deli Counter 0.220.0), a corner shop's awning (0.219.0), a rowhome's stoop (0.211.0)
SHELLS = ("gs_midrise_a", "gs_cornershop_c", "gs_empty_rowhome_a")


def _box(name, scale, offset) -> Mesh:
    pos, nrm, idx = _unit_cube()
    pos = pos * np.array(scale, np.float32) + np.array(offset, np.float32)
    prim = Primitive(positions=pos.astype(np.float32), indices=idx.astype(np.uint32),
                     normals=nrm.astype(np.float32))
    return Mesh(name=name, kind=MeshKind.VISUAL, primitives=[prim])


def _front_roles(mesh: Mesh) -> set:
    """The roles of a box's -Y face: the triangles whose three corners all stand at its least y."""
    prim = mesh.primitives[0]
    tris = prim.positions[prim.indices]
    front = np.all(np.abs(tris[:, :, 1] - prim.positions[:, 1].min()) < 1e-6, axis=1)
    return {r for r, f in zip(prim.face_roles, front) if f}


def _street():
    """A 6 x 4 x 9 m block on z = 0, its front at y = -2, and a fire escape's box 1.2 m deep against that front,
    from a storey up to under the roof."""
    shell = _box("ext_shell", (6, 4, 9), (0, 0, 4.5))
    stack = _box("fire_escape_1", (2.6, 1.2, 6), (1.5, -2.6, 6))
    return shell, stack, Scene(meshes=[shell, stack], gameplay=None)


def test_unnamed_the_stack_takes_the_front():
    """The defect, kept as the reason the manifest is needed: 0.30.0's reading, and still what a shell with no
    slots.json gets."""
    shell, stack, sc = _street()
    surfaces.classify(sc)
    assert _front_roles(shell) == {SurfaceRole.WALL}
    assert _front_roles(stack) == {SurfaceRole.EXTERIOR_WALL}


def test_named_the_stack_leaves_the_front_to_the_wall():
    shell, stack, sc = _street()
    surfaces.classify(sc, props=frozenset({"fire_escape_1"}))
    assert _front_roles(shell) == {SurfaceRole.EXTERIOR_WALL}
    roles = set(stack.primitives[0].face_roles)
    assert roles <= {SurfaceRole.WALL, SurfaceRole.FLOOR, SurfaceRole.CEILING}, roles
    # the shell reads exactly as it reads standing alone
    alone = _box("ext_shell", (6, 4, 9), (0, 0, 4.5))
    surfaces.classify(Scene(meshes=[alone], gameplay=None))
    assert list(shell.primitives[0].face_roles) == list(alone.primitives[0].face_roles)


def test_a_prop_over_the_roof_does_not_take_the_roof():
    shell = _box("ext_shell", (6, 4, 9), (0, 0, 4.5))
    dish = _box("roof_dish", (1, 1, 1.5), (0, 0, 9.75))
    surfaces.classify(Scene(meshes=[shell, dish], gameplay=None))
    assert SurfaceRole.ROOF not in set(shell.primitives[0].face_roles)     # unnamed: the bound moved up
    shell = _box("ext_shell", (6, 4, 9), (0, 0, 4.5))
    dish = _box("roof_dish", (1, 1, 1.5), (0, 0, 9.75))
    surfaces.classify(Scene(meshes=[shell, dish], gameplay=None), props=frozenset({"roof_dish"}))
    assert SurfaceRole.ROOF in set(shell.primitives[0].face_roles)
    assert SurfaceRole.ROOF not in set(dish.primitives[0].face_roles)


def test_a_hint_still_wins_over_a_prop():
    """Authored intent overrides geometry, a prop's included."""
    shell, stack, sc = _street()
    sc.gameplay = {"surfaces": [{"mesh": "fire_escape_1", "role": "exterior_wall"}]}
    surfaces.classify(sc, props=frozenset({"fire_escape_1"}))
    assert set(stack.primitives[0].face_roles) == {SurfaceRole.EXTERIOR_WALL}
    assert _front_roles(shell) == {SurfaceRole.EXTERIOR_WALL}


def test_the_manifest_names_its_props():
    m = slots.parse({"slots": [
        {"slot_id": "ext_0_S_seg0", "role": "wall"},
        {"slot_id": "fire_escape_1", "role": "prop"},
        {"slot_id": "stoop_landing", "role": "prop"},
        {"slot_id": "ext_0_S_open0", "role": "window"},
    ]})
    assert m.prop_ids() == frozenset({"fire_escape_1", "stoop_landing"})


def _anchors(name: str, how: str):
    """A real shell's anchors, the CLI's way from load to `anchors.generate`, with its props named (`named`), not
    named (`unnamed`, 0.30.0's reading) or taken out of the scene (`removed`, the building alone)."""
    scene = gltf_io.load_glb(str(BUILD / (name + ".glb")))
    m = slots.load(scene)
    assert m is not None, "no slots.json beside " + name
    props = m.prop_ids()
    if how == "removed":
        scene.meshes = [x for x in scene.meshes if x.name not in props]
    scene.bake_visual_transforms()
    up = slots.detect_up_axis(scene)
    surfaces.classify(scene, up, props=props if how == "named" else frozenset())
    out = anchors.generate(scene, anchors.AnchorOptions(ground_z=m.storey_base(0)), 1999, up)
    return sorted((a.kind, a.pos, a.normal, a.tangent) for a in out), props


@pytest.mark.parametrize("name", SHELLS)
def test_a_real_shell_s_props_change_none_of_its_anchors(name):
    """The building's anchors with its props named are its anchors with them taken away; unnamed they are not,
    which is the defect and proves this can fail."""
    if not (BUILD / (name + ".glb")).is_file():
        pytest.skip("no Deli Counter build of %s beside this repo" % name)
    named, props = _anchors(name, "named")
    removed, _ = _anchors(name, "removed")
    unnamed, _ = _anchors(name, "unnamed")
    assert props, name + " names no prop"
    assert {n for n in props if n.startswith(("fire_escape_", "shop_awning", "stoop_"))}, props
    assert named == removed
    assert unnamed != removed
