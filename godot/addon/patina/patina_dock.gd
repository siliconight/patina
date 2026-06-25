@tool
extends Control

# Patina dock — minimal UI built in code (no .tscn needed). Pick a styled scene
# root and its .patina.json, click Apply. FIRST-RUN-IN-ENGINE: walk to confirm.

const Apply := preload("res://addons/patina/patina_apply.gd")

var editor: EditorInterface
var _manifest_path: String = ""
var _status: Label


func _init() -> void:
	name = "Patina"
	custom_minimum_size = Vector2(220, 0)


func _ready() -> void:
	var vb := VBoxContainer.new()
	vb.anchors_preset = Control.PRESET_TOP_WIDE
	add_child(vb)

	var title := Label.new()
	title.text = "Patina — PS1 style"
	vb.add_child(title)

	var pick := Button.new()
	pick.text = "Choose .patina.json…"
	pick.pressed.connect(_on_pick)
	vb.add_child(pick)

	var apply := Button.new()
	apply.text = "Apply PS1 style"
	apply.pressed.connect(_on_apply)
	vb.add_child(apply)

	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.text = "Select the styled scene root, then choose its manifest."
	vb.add_child(_status)


func _on_pick() -> void:
	var dlg := EditorFileDialog.new()
	dlg.file_mode = EditorFileDialog.FILE_MODE_OPEN_FILE
	dlg.access = EditorFileDialog.ACCESS_RESOURCES
	dlg.add_filter("*.json", "Patina manifest")
	dlg.file_selected.connect(func(p): _manifest_path = p; _status.text = "Manifest: %s" % p)
	add_child(dlg)
	dlg.popup_centered_ratio(0.6)


func _on_apply() -> void:
	if _manifest_path == "":
		_status.text = "Choose a .patina.json first."
		return
	var sel := editor.get_selection().get_selected_nodes()
	if sel.is_empty():
		_status.text = "Select the imported shell's root node in the scene tree."
		return
	var report := Apply.apply_to_scene(sel[0], _manifest_path)
	_status.text = report
