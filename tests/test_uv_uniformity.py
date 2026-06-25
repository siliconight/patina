"""Box-UV uniformity: texel density is uniform across non-uniformly scaled
faces — the explicit I-5 smear trap (TDD 5.2, 8.1)."""

from __future__ import annotations

from patina import gltf_io, nuance, surfaces, uvproject


def test_uv_density_uniform(shell):
    scene = gltf_io.load_glb(shell)
    scene.bake_visual_transforms()      # world space BEFORE projecting (the fix)
    nuance.densify(scene, nuance.NuanceOptions())
    surfaces.classify(scene)
    texel = 2.0
    uvproject.project(scene, texel=texel)
    report = uvproject.density_report(scene, texel)
    # Every face should report ~1/texel regardless of how it was scaled.
    assert report["max_rel_error"] < 0.02, report


def test_every_visual_face_has_uv(shell):
    scene = gltf_io.load_glb(shell)
    scene.bake_visual_transforms()
    surfaces.classify(scene)
    uvproject.project(scene, texel=2.0)
    for mesh in scene.visual_meshes():
        for prim in mesh.primitives:
            assert prim.uv1 is not None
            assert prim.uv1.shape[0] == prim.vertex_count()
