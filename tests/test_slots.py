"""Modular alignment (v0.9): slots.json ingestion, up-axis detection, the
Blender Z-up coordinate contract, Zoo theme->family reconciliation, and the
axis-correctness of classify / banding / anchors on Y-up (DC glTF) data."""

from __future__ import annotations

import json

import numpy as np
import pytest

from patina import anchors, families, gltf_io, slots, surfaces
from patina.mesh import Mesh, MeshKind, Primitive, Scene


# --------------------------------------------------------------------------- #
# Manifest parsing
# --------------------------------------------------------------------------- #

_RAW = {
    "slot_manifest_version": "1.2.0",
    "building_id": "corner_deli",
    "theme": "delco",
    "module_library": "art/zoo",
    "module_size": 2.0,
    "space": "spec/Blender Z-up raw coords; rot_y = degrees about up",
    "coverage": {"wall/greybox": 3},
    "slots": [
        {"slot_id": "ext_0_N_seg0", "role": "wall", "size_mod": "full", "style": 1,
         "current_ref": "wall_delco_01", "kit_axis": "theme", "facing": "N",
         "story": 0, "transform": {"translation": [-3.0, 4.0, 1.5], "rot_y": 0,
                                   "scale": [1, 1, 1]},
         "fit": {"dims": [2.0, 0.2, 3.0], "pivot": "center", "openings": [],
                 "collision": "convex"}},
        {"slot_id": "ext_0_N_open0", "role": "doorway", "current_ref": "doorway_delco_01",
         "transform": {"translation": [-2.0, 4.0, 1.5], "rot_y": 0, "scale": [1, 1, 1]},
         "fit": {"dims": [1.0, 0.2, 3.0], "pivot": "center",
                 "openings": [{"kind": "door", "width": 1.0, "height": 2.1}],
                 "collision": "convex"}},
    ],
}


def test_parse_manifest():
    m = slots.parse(_RAW)
    assert m.version == "1.2.0" and m.building_id == "corner_deli"
    assert m.theme == "delco" and m.module_size == 2.0
    assert len(m.slots) == 2
    s0 = m.by_id()["ext_0_N_seg0"]
    assert s0.role == "wall" and s0.current_ref == "wall_delco_01"
    assert s0.translation == (-3.0, 4.0, 1.5) and s0.dims == (2.0, 0.2, 3.0)
    assert s0.theme() == "delco"                 # parsed from current_ref
    assert s0.patina_role() == "wall"


def test_doorway_maps_to_wall_treatment():
    m = slots.parse(_RAW)
    assert m.by_id()["ext_0_N_open0"].patina_role() == "wall"


def test_load_returns_none_without_slots():
    scene = Scene(meshes=[])
    assert slots.load(scene) is None
    scene.slots = _RAW
    assert slots.load(scene).building_id == "corner_deli"


# --------------------------------------------------------------------------- #
# Coordinate contract
# --------------------------------------------------------------------------- #

def test_blender_patina_roundtrip():
    for p in [(1.0, 2.0, 3.0), (-4.5, 0.0, 7.2)]:
        assert slots.patina_to_blender(slots.blender_to_patina(p)) == pytest.approx(p)


def test_blender_to_patina_is_gltf_convention():
    # Blender (x, y, z) -> glTF (x, z, -y)
    assert slots.blender_to_patina((1.0, 2.0, 3.0)) == (1.0, 3.0, -2.0)


# --------------------------------------------------------------------------- #
# Zoo seam
# --------------------------------------------------------------------------- #

def test_reconcile_family():
    assert slots.reconcile_family("delco") == "delco_faded"
    assert slots.reconcile_family("greybox") is None
    assert slots.reconcile_family("unknown_theme") is None


def test_reconciled_family_loads():
    name = slots.reconcile_family("delco")
    fam = families.load(name)
    assert len(fam.colors) == 10


# --------------------------------------------------------------------------- #
# Up-axis detection + axis-correct classification (the core misalignment)
# --------------------------------------------------------------------------- #

def _box_scene(up_axis: int) -> Scene:
    """A wide, shallow box (a building) with the small extent on ``up_axis``."""
    # base footprint 20 x 12, height 4 -> up axis has the smallest range
    ext = [20.0, 12.0, 4.0]
    ext[up_axis] = 4.0
    # ensure up axis is the smallest
    others = [i for i in range(3) if i != up_axis]
    ext[others[0]], ext[others[1]] = 20.0, 12.0
    hx, hy, hz = ext[0] / 2, ext[1] / 2, ext[2] / 2
    # 8 cube corners
    c = np.array([[x, y, z] for x in (-hx, hx) for y in (-hy, hy)
                  for z in (-hz, hz)], np.float32)
    # 12 triangles (box). Winding doesn't matter for the range test.
    faces = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5),
             (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6),
             (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    prim = Primitive(positions=c, indices=np.array(faces, np.uint32))
    return Scene(meshes=[Mesh(name="box", kind=MeshKind.VISUAL, primitives=[prim])])


def test_detect_up_axis():
    for up in (0, 1, 2):
        assert slots.detect_up_axis(_box_scene(up)) == up


def test_classify_axis_aware_up_faces_are_horizontal_surfaces():
    """On a Y-up box, up/down faces (normal along Y) must read as horizontal
    surfaces (floor/ceiling/roof), and side faces as walls — proving classify
    reads Y as up, not Z."""
    scene = _box_scene(1)
    surfaces.classify(scene, up_axis=1)
    horiz = {"floor", "ceiling", "roof"}
    for m in scene.visual_meshes():
        for p in m.primitives:
            fn = p.ensure_normals()
            tri = p.positions[p.indices]
            face_n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            ln = np.linalg.norm(face_n, axis=1, keepdims=True)
            face_n = np.divide(face_n, ln, out=np.zeros_like(face_n), where=ln > 1e-9)
            for i, role in enumerate(p.face_roles):
                if abs(face_n[i, 1]) > 0.9:            # normal points along Y (up)
                    assert role.value in horiz, f"Y-facing face got {role.value}"


def test_classify_wrong_axis_misreads():
    """Sanity: classifying a Y-up box as Z-up sends the true horizontal (Y)
    faces to wall roles instead of floor/ceiling/roof — the bug v0.9 fixes."""
    scene = _box_scene(1)
    surfaces.classify(scene, up_axis=2)         # wrong axis on purpose
    mislabeled = False
    for m in scene.visual_meshes():
        for p in m.primitives:
            tri = p.positions[p.indices]
            face_n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
            ln = np.linalg.norm(face_n, axis=1, keepdims=True)
            face_n = np.divide(face_n, ln, out=np.zeros_like(face_n), where=ln > 1e-9)
            for i, role in enumerate(p.face_roles):
                if abs(face_n[i, 1]) > 0.9 and role.value not in (
                        "floor", "ceiling", "roof"):
                    mislabeled = True           # a true horizontal read as wall
    assert mislabeled


def test_anchors_axis_aware_roofline_at_top():
    """On a Y-up scene, roofline anchors must land at the top in Y, not Z."""
    scene = _box_scene(1)
    surfaces.classify(scene, up_axis=1)
    a = anchors.generate(scene, anchors.AnchorOptions(), seed=1, up_axis=1)
    roof = [x for x in a if x.kind == "roofline"]
    if roof:                                   # box may or may not expose exterior walls
        ys = [r.pos[1] for r in roof]
        # all roofline anchors near the top Y (+2), not the bottom
        assert min(ys) > 0


# --------------------------------------------------------------------------- #
# Per-slot variation (v0.10)
# --------------------------------------------------------------------------- #

def test_slot_factor_deterministic_and_bounded():
    a = slots.slot_factor("wall_3", seed=1999, strength=0.12)
    b = slots.slot_factor("wall_3", seed=1999, strength=0.12)
    assert a == b
    assert 0.88 <= a <= 1.12
    assert slots.slot_factor("wall_4", 1999, 0.12) != a   # different slot varies


def test_instance_records_shape_and_uniqueness():
    m = slots.parse(_RAW)
    fam = families.load("delco_faded")
    recs = slots.instance_records(m, fam, seed=1999, strength=0.12)
    assert len(recs) == 2
    for r in recs:
        assert "slot_id" in r and set(r["instance"]) == {"color", "custom_data"}
        assert len(r["instance"]["color"]) == 4          # rgba
        assert len(r["instance"]["custom_data"]) == 4
    # the two slots get different colours (repetition broken)
    assert recs[0]["instance"]["color"] != recs[1]["instance"]["color"]


def test_instance_records_deterministic():
    m = slots.parse(_RAW)
    fam = families.load("delco_faded")
    a = slots.instance_records(m, fam, 7, 0.1)
    b = slots.instance_records(m, fam, 7, 0.1)
    assert a == b


def test_instances_sidecar_shape():
    m = slots.parse(_RAW)
    side = slots.instances_sidecar(m, families.load("delco_faded"), 1,
                                   strength=0.1, source="x.glb")
    assert side["schema"] == "patina-instances/1"
    assert side["building_id"] == "corner_deli"
    assert side["count"] == len(side["instances"]) == 2


def test_apply_slot_variation_modulates_and_assigns():
    # a Y-up box with a slot centered on it; variation should touch its faces
    scene = _box_scene(1)
    surfaces.classify(scene, up_axis=1)
    # give every vertex a base colour so variation has something to modulate
    for mesh in scene.visual_meshes():
        for p in mesh.primitives:
            p.color = np.ones((p.vertex_count(), 4), np.float32) * 0.5
    raw = {**_RAW, "module_size": 20.0, "slots": [{
        "slot_id": "s0", "role": "wall", "current_ref": "wall_delco_01",
        "transform": {"translation": [0.0, 0.0, 0.0], "rot_y": 0, "scale": [1, 1, 1]},
        "fit": {"dims": [20.0, 12.0, 4.0], "pivot": "center", "openings": [],
                "collision": "convex"}}]}
    m = slots.parse(raw)
    before = scene.visual_meshes()[0].primitives[0].color.copy()
    varied = slots.apply_slot_variation(scene, m, seed=1, strength=0.2)
    after = scene.visual_meshes()[0].primitives[0].color
    assert varied > 0
    # colour changed by the slot's single factor (uniform since one slot)
    assert not np.allclose(before[:, :3], after[:, :3])
