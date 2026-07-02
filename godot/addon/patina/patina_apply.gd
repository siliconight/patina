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
	var n_decals := _apply_decals(root, manifest, base_dir)
	if n_decals >= 0:
		return "Applied PS1 style to %d mesh(es); %d decal(s)." % [applied, n_decals]
	return "Applied PS1 style to %d mesh(es)." % applied


# Decal pass (manifest schema 0.2.0+): instantiate Decal nodes under a single
# deletable "PatinaDecals" node. Re-applying rebuilds it from scratch, so the
# pass stays reproducible. Positions/normals are in the styled .glb's baked
# space, which the glTF importer preserves node-for-node, so they are used as
# local transforms under the shell root.
# FIRST-RUN-IN-ENGINE: walk to confirm projection direction and fade.
static func _apply_decals(root: Node, manifest: Dictionary, base_dir: String) -> int:
	var dec: Dictionary = manifest.get("decals", {})
	var instances: Array = dec.get("instances", [])
	var textures: Dictionary = dec.get("textures", {})

	var old := root.get_node_or_null("PatinaDecals")
	if old:
		old.free()
	if instances.is_empty():
		return -1 if not dec else 0

	var holder := Node3D.new()
	holder.name = "PatinaDecals"
	root.add_child(holder)
	if Engine.is_editor_hint() and root.get_tree():
		holder.owner = root.get_tree().edited_scene_root

	var tex_cache := {}
	var made := 0
	for inst in instances:
		var dtype: String = inst.get("type", "")
		if not textures.has(dtype):
			continue
		if not tex_cache.has(dtype):
			tex_cache[dtype] = load(base_dir.path_join(textures[dtype]))
		var tex: Texture2D = tex_cache[dtype]
		if tex == null:
			continue

		var d := Decal.new()
		d.name = "%s_%d" % [dtype, made]
		d.texture_albedo = tex
		var size: Array = inst.get("size", [0.5, 0.5])
		d.size = Vector3(size[0], 0.3, size[1])   # y = projection depth
		d.cull_mask = 0xFFFFF
		d.albedo_mix = 1.0

		var p: Array = inst.get("pos", [0, 0, 0])
		var nrm: Array = inst.get("normal", [0, 0, 1])
		# Patina's baked space is Z-up (the Deli Counter contract), and these
		# transforms are local under the shell root, so "up" here is +Z.
		var up := Vector3(0, 0, 1)
		var n := Vector3(nrm[0], nrm[1], nrm[2]).normalized()
		if n.length_squared() < 0.5:
			n = up
		# Decal projects along local -Y; aim -Y into the surface (Y = normal).
		# With up as the helper, the decal's texture V axis lands world-vertical
		# on walls, which is what "rot: vertical" streak decals rely on.
		var helper := up if absf(n.dot(up)) < 0.99 else Vector3.RIGHT
		var x := helper.cross(n).normalized()
		var z := x.cross(n).normalized()
		var basis := Basis(x, n, z)
		basis = basis.rotated(n, deg_to_rad(inst.get("rot", 0.0)))
		d.transform = Transform3D(basis, Vector3(p[0], p[1], p[2]) + n * 0.05)

		holder.add_child(d)
		if Engine.is_editor_hint() and root.get_tree():
			d.owner = root.get_tree().edited_scene_root
		made += 1
	return made


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
