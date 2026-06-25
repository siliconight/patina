"""P0 I/O spine: geometry round-trips value-for-value, writer is deterministic."""

from __future__ import annotations

import numpy as np

from patina import gltf_io


def _world_positions(mesh):
    out = []
    for p in mesh.primitives:
        ones = np.ones((p.positions.shape[0], 1))
        out.append((np.hstack([p.positions, ones]) @ mesh.transform.T)[:, :3])
    return np.vstack(out)


def test_writer_is_deterministic(shell, tmp_path):
    scene = gltf_io.load_glb(shell)
    a, b = tmp_path / "a.glb", tmp_path / "b.glb"
    gltf_io.save_glb(scene, str(a))
    gltf_io.save_glb(scene, str(b))
    assert a.read_bytes() == b.read_bytes()


def test_geometry_round_trips(shell, tmp_path):
    s1 = gltf_io.load_glb(shell)
    out = tmp_path / "rt.glb"
    gltf_io.save_glb(s1, str(out))
    s2 = gltf_io.load_glb(str(out))

    m1 = {m.name: m for m in s1.meshes}
    m2 = {m.name: m for m in s2.meshes}
    assert set(m1) == set(m2)
    for name in m1:
        w1 = np.sort(_world_positions(m1[name]).round(4), axis=0)
        w2 = np.sort(_world_positions(m2[name]).round(4), axis=0)
        assert np.allclose(w1, w2, atol=1e-4), name


def test_collision_detected(shell):
    scene = gltf_io.load_glb(shell)
    assert len(scene.collision_meshes()) == 1
    assert scene.collision_meshes()[0].name.endswith("-colonly")
    assert len(scene.visual_meshes()) == 7


def test_gameplay_sidecar_loaded(shell):
    scene = gltf_io.load_glb(shell)
    assert scene.gameplay is not None
    assert len(scene.gameplay["markers"]) == 3
