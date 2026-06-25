@tool
extends EditorPlugin

# Patina editor plugin (TDD 5.4 / P2). Adds a dock with a one-click
# "Apply PS1 style" button, mirroring Deli Counter's "Set up & Play" ergonomics.
#
# FIRST-RUN-IN-ENGINE: drafted against known-good Godot 4 EditorPlugin patterns.
# Confirm in Godot 4.7 (the @tool dock first-run caveat, same bucket as Deli
# Counter's plugin dock).

const Dock := preload("res://addons/patina/patina_dock.gd")

var _dock: Control


func _enter_tree() -> void:
	_dock = Dock.new()
	_dock.editor = get_editor_interface()
	add_control_to_dock(EditorPlugin.DOCK_SLOT_RIGHT_UL, _dock)


func _exit_tree() -> void:
	if _dock:
		remove_control_from_docks(_dock)
		_dock.queue_free()
		_dock = null
