"""Manifest validity: schema-validates, every surface role resolves (TDD 8.1)."""

from __future__ import annotations

from patina import gltf_io, manifest, nuance, surfaces


def _scene(shell):
    scene = gltf_io.load_glb(shell)
    scene.bake_visual_transforms()
    nuance.densify(scene, nuance.NuanceOptions())
    surfaces.classify(scene)
    nuance.vertex_color(scene, nuance.NuanceOptions())
    return scene


def test_manifest_schema_validates(shell):
    scene = _scene(shell)
    man = manifest.build(scene, mode="vertex-color", seed=1999)
    manifest.validate(man)               # raises on failure
    assert man["generator"].startswith("Patina ")
    assert man["mode"] == "vertex-color"


def test_every_surface_role_resolves(shell):
    scene = _scene(shell)
    man = manifest.build(scene, mode="vertex-color", seed=1999)
    counts = surfaces.role_counts(scene)
    for role in counts:
        assert role in man["surfaces"]
        assert "vertex_color" in man["surfaces"][role]


def test_kitbash_hooks_cover_every_visual_mesh(shell):
    scene = _scene(shell)
    man = manifest.build(scene, mode="vertex-color", seed=1999)
    names = {k["mesh"] for k in man["kitbash"]}
    assert names == {m.name for m in scene.visual_meshes()}
    for hook in man["kitbash"]:
        assert len(hook["bounds_min"]) == 3 and len(hook["bounds_max"]) == 3
