@tool
extends RefCounted
class_name PatinaApply

# Reads a .patina.json manifest and applies the PS1 style to an imported Deli
# Counter shell (TDD 4.2, 5.4): a ShaderMaterial per surface role, white ambient,
# distance fog. Visual-only — collision shapes and markers are never touched.
#
# FIRST-RUN-IN-ENGINE: drafted against known-good Godot 4 patterns. The mapping
# from MeshInstance3D to surface role uses the manifest's kitbash[].mesh names
# (Patina preserves node names), falling back to per-mesh material assignment.

const PS1_SHADER := preload("res://addons/patina/ps1.gdshader")


static func apply_to_scene(root: Node, manifest_path: String) -> String:
	var f := FileAccess.open(manifest_path, FileAccess.READ)
	if f == null:
		return "Could not open %s" % manifest_path
	var manifest: Dictionary = JSON.parse_string(f.get_as_text())
	if manifest == null:
		return "Manifest is not valid JSON."

	var shader_cfg: Dictionary = manifest.get("shader", {})
	var surfaces: Dictionary = manifest.get("surfaces", {})
	var role_by_mesh := {}
	for hook in manifest.get("kitbash", []):
		role_by_mesh[hook.get("mesh", "")] = hook.get("role", "wall")

	var base_dir := manifest_path.get_base_dir()
	var applied := 0
	for mi in _all_mesh_instances(root):
		var role: String = role_by_mesh.get(mi.name, "")
		# Skip collision-only nodes defensively (they shouldn't be MeshInstances,
		# but never style anything that reads as collision).
		if mi.name.ends_with("-colonly") or mi.name.ends_with("-convcolonly"):
			continue
		var spec: Dictionary = surfaces.get(role, {})
		var mat := _make_material(shader_cfg, spec, base_dir)
		if mi.mesh:
			for s in mi.mesh.get_surface_count():
				mi.set_surface_override_material(s, mat)
			applied += 1

	_setup_environment(root, shader_cfg)
	return "Applied PS1 style to %d mesh(es)." % applied


static func _make_material(shader_cfg: Dictionary, spec: Dictionary, base_dir: String) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = PS1_SHADER
	mat.set_shader_parameter("jitter", shader_cfg.get("vertex_jitter", 64.0))
	mat.set_shader_parameter("affine_strength", shader_cfg.get("affine_strength", 0.85))
	mat.set_shader_parameter("color_depth", shader_cfg.get("color_depth", 16))
	mat.set_shader_parameter("dither", shader_cfg.get("dither", true))
	var amb: Array = shader_cfg.get("ambient", [1, 1, 1])
	mat.set_shader_parameter("ambient_color", Color(amb[0], amb[1], amb[2]))
	var tex_rel = spec.get("texture", null)
	if tex_rel != null:
		var tex := load(base_dir.path_join(tex_rel))
		if tex:
			mat.set_shader_parameter("use_texture", true)
			mat.set_shader_parameter("albedo_tex", tex)
	return mat


static func _setup_environment(root: Node, shader_cfg: Dictionary) -> void:
	var we := _find_or_make_world_environment(root)
	var env := we.environment if we.environment else Environment.new()
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	var amb: Array = shader_cfg.get("ambient", [1, 1, 1])
	env.ambient_light_color = Color(amb[0], amb[1], amb[2])
	env.ambient_light_energy = 1.0
	var fog: Dictionary = shader_cfg.get("fog", {})
	if fog.get("enabled", false):
		env.fog_enabled = true
		var fc: Array = fog.get("color", [0.1, 0.1, 0.12])
		env.fog_light_color = Color(fc[0], fc[1], fc[2])
		# depth fog mapped from the manifest's near/far
		env.fog_depth_begin = fog.get("near", 12.0)
		env.fog_depth_end = fog.get("far", 48.0)
	we.environment = env


static func _find_or_make_world_environment(root: Node) -> WorldEnvironment:
	for c in root.get_children():
		if c is WorldEnvironment:
			return c
	var we := WorldEnvironment.new()
	we.name = "PatinaEnvironment"
	root.add_child(we)
	if Engine.is_editor_hint() and root.get_tree():
		we.owner = root.get_tree().edited_scene_root
	return we


static func _all_mesh_instances(node: Node, acc: Array = []) -> Array:
	if node is MeshInstance3D:
		acc.append(node)
	for c in node.get_children():
		_all_mesh_instances(c, acc)
	return acc
