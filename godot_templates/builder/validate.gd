extends SceneTree
# Run: godot --headless --path <proj> --script res://generated/builder/validate.gd
# Static checks run in _initialize; scene instantiation is a small state machine in _process
# because scenes need a frame in the tree.

const Paths := preload("lib/paths.gd")
const BuildContext := preload("lib/build_context.gd")
const Log := preload("lib/log.gd")

const CHECK_ROOTS := ["res://addons", "res://generated", "res://game"]
const RESOURCE_ROOTS := ["res://generated", "res://game"]
const ROUND_TRIP_TMP := "user://rt_test.tscn"

var _ctx: RefCounted
var _scenes: Array = []
var _scene_index: int = 0
var _pending: Node = null
var _finished: bool = false

func _initialize() -> void:
	var builder_dir: String = get_script().resource_path.get_base_dir()
	_ctx = BuildContext.new(builder_dir, "validate")
	if not _ctx.load_inputs():
		_finish()
		return
	_check_scripts()
	var resources := _check_resources()
	_check_dependencies(resources)
	_check_main_scene()
	_check_autoloads()
	_check_input_actions()
	for path in resources:
		if String(path).ends_with(".tscn"):
			_scenes.append(path)
	_check_map_round_trip("res://game/maps/starter_map.tscn")
	_check_ysort_origins()
	_check_ysort_parents()

func _process(_delta: float) -> bool:
	if _finished or _ctx == null:
		return false
	if _pending != null:
		_pending.queue_free()
		_pending = null
		return false
	if _scene_index >= _scenes.size():
		_finish()
		return false
	var path: String = _scenes[_scene_index]
	_scene_index += 1
	var packed := load(path) as PackedScene
	if packed == null:
		return false  # already reported by the resource check
	var inst := packed.instantiate()
	if inst == null:
		_fail("VAL-004", {"file": path}, path)
		_item("scene_instantiate", path, false)
		return false
	_item("scene_instantiate", path, true)
	if path.begins_with(Paths.GEN_SCENES_DIR + "bootstrap/"):
		# The boot scene switches scenes in _ready(); instantiating it is enough here.
		inst.free()
		return false
	root.add_child(inst)
	_pending = inst
	return false

# ---------------------------------------------------------------- helpers

func _item(check: String, target: String, ok: bool) -> void:
	_ctx.results.add_item({"check": check, "target": target.trim_prefix("res://"), "ok": ok})

func _fail(code: String, detail: Dictionary, file: String = "") -> void:
	_ctx.results.add_issue(code, detail, file.trim_prefix("res://"))

func _finish() -> void:
	if _finished:
		return
	_finished = true
	var err: int = _ctx.results.write(Paths.RESULTS_VALIDATE)
	if err != OK:
		push_error("[RPG-VALIDATE] could not write results: %d" % err)
	Log.info("validate finished ok=%s" % str(_ctx.results.ok))
	quit(0 if _ctx.results.ok and err == OK else 1)

static func _list_files(dir_path: String, extensions: Array) -> Array:
	var found: Array = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	var entries: Array = []
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		entries.append([name, dir.current_is_dir()])
		name = dir.get_next()
	dir.list_dir_end()
	entries.sort_custom(func(a: Array, b: Array) -> bool: return String(a[0]) < String(b[0]))
	for e in entries:
		var full: String = dir_path + "/" + e[0]
		if e[1]:
			if not String(e[0]).begins_with("."):
				found.append_array(_list_files(full, extensions))
		elif extensions.has(String(e[0]).get_extension()):
			found.append(full)
	return found

# ---------------------------------------------------------------- checks

func _is_editor_only(script: GDScript) -> bool:
	var base := String(script.get_instance_base_type())
	return ClassDB.is_parent_class(base, "EditorPlugin") or ClassDB.is_parent_class(base, "EditorScript")

func _check_scripts() -> void:
	for root_dir in CHECK_ROOTS:
		for path in _list_files(root_dir, ["gd"]):
			var script: Variant = load(path)
			var ok: bool = script != null and script is GDScript
			if ok and not _is_editor_only(script):
				ok = (script as GDScript).can_instantiate()
			if not ok:
				_fail("VAL-001", {"file": path}, path)
			_item("script_parse", path, ok)

func _check_resources() -> Array:
	var paths: Array = []
	for root_dir in RESOURCE_ROOTS:
		paths.append_array(_list_files(root_dir, ["tres", "tscn"]))
	for path in paths:
		var res := load(path)
		if res == null:
			_fail("VAL-002", {"file": path}, path)
		_item("resource_load", path, res != null)
	return paths

static func _dependency_path(dep: String) -> String:
	var path := dep
	if dep.contains("::"):
		path = dep.get_slice("::", dep.get_slice_count("::") - 1)
	if path.begins_with("uid://"):
		var id := ResourceUID.text_to_id(path)
		if ResourceUID.has_id(id):
			return ResourceUID.get_id_path(id)
		return ""
	return path

func _check_dependencies(resources: Array) -> void:
	for path in resources:
		var ok := true
		for dep in ResourceLoader.get_dependencies(path):
			var dep_path := _dependency_path(String(dep))
			if dep_path == "" or not ResourceLoader.exists(dep_path):
				_fail("VAL-003", {"dep": dep_path if dep_path != "" else String(dep), "file": path}, path)
				ok = false
		_item("dependencies", path, ok)

func _check_main_scene() -> void:
	var main_scene := String(ProjectSettings.get_setting("application/run/main_scene", ""))
	var ok := main_scene != "" and ResourceLoader.exists(main_scene)
	if not ok:
		_fail("VAL-005", {})
	_item("main_scene", main_scene, ok)

func _check_autoloads() -> void:
	for prop in ProjectSettings.get_property_list():
		var name := String(prop["name"])
		if not name.begins_with("autoload/"):
			continue
		var value := String(ProjectSettings.get_setting(name)).trim_prefix("*")
		var ok := ResourceLoader.exists(value)
		if not ok:
			_fail("VAL-006", {"name": name.trim_prefix("autoload/")})
		_item("autoload", name, ok)

func _check_input_actions() -> void:
	var input: Dictionary = _ctx.config.get("input", {})
	var actions: Array = input.keys()
	actions.sort()
	for action in actions:
		var ok := InputMap.has_action(action) and InputMap.action_get_events(action).size() > 0
		if not ok:
			_fail("VAL-007", {"action": action})
		_item("input_action", String(action), ok)

func _collect_layers(node: Node, out: Array) -> void:
	if node is TileMapLayer:
		out.append(node)
	for child in node.get_children():
		_collect_layers(child, out)

func _cell_set(layer: TileMapLayer) -> Dictionary:
	var out := {}
	for c in layer.get_used_cells():
		out[c] = true
	return out

## Never saves over the real map: the modified copy goes to user://.
func _check_map_round_trip(map_path: String) -> void:
	if not ResourceLoader.exists(map_path):
		return
	var packed := load(map_path) as PackedScene
	if packed == null:
		return
	var inst := packed.instantiate()
	var layers: Array = []
	_collect_layers(inst, layers)
	var before := {}
	var test_cell := Vector2i(-100, -100)
	for layer in layers:
		var ts: TileSet = layer.tile_set
		if ts == null or ts.get_source_count() == 0:
			continue
		var src := ts.get_source(ts.get_source_id(0)) as TileSetAtlasSource
		if src == null or src.get_tiles_count() == 0:
			continue
		before[inst.get_path_to(layer)] = _cell_set(layer)
		layer.set_cell(test_cell, ts.get_source_id(0), src.get_tile_id(0), 0)
	var copy := PackedScene.new()
	var ok := copy.pack(inst) == OK and ResourceSaver.save(copy, ROUND_TRIP_TMP) == OK
	var failed_layer := ""
	if ok:
		var reloaded := (ResourceLoader.load(ROUND_TRIP_TMP, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate()
		for layer_path in before.keys():
			var layer := reloaded.get_node_or_null(layer_path) as TileMapLayer
			var original: Dictionary = before[layer_path]
			if layer == null:
				ok = false
				failed_layer = String(layer_path)
				break
			var now := _cell_set(layer)
			var expected := original.duplicate()
			expected[test_cell] = true
			if now.keys().size() != expected.keys().size() or not now.has(test_cell):
				ok = false
				failed_layer = String(layer_path)
				break
			for c in original.keys():
				if not now.has(c):
					ok = false
					failed_layer = String(layer_path)
					break
			if not ok:
				break
		reloaded.free()
	else:
		failed_layer = "(pack/save)"
	inst.free()
	if FileAccess.file_exists(ROUND_TRIP_TMP):
		DirAccess.remove_absolute(ROUND_TRIP_TMP)
	if not ok:
		_fail("VAL-010", {"layer": failed_layer}, map_path)
	_item("map_round_trip", map_path, ok)

# ---------------------------------------------------------------- Y-sort (T4.07)
# Headless mode renders nothing, so Y-sort is checked logically: a visual's bottom edge sits on the
# node origin (y = 0), and every placed entity has a Y-sorted parent.

const ORIGIN_TOLERANCE := 2.0
const ENTITY_DIRS := ["res://generated/scenes/objects/", "res://generated/scenes/actors/"]

## Bottom edge (y, relative to the scene root) of a Sprite2D / AnimatedSprite2D, or NAN.
static func visual_bottom(visual: Node2D, scene_root: Node) -> float:
	var tex: Texture2D = null
	var offset := Vector2.ZERO
	var centered := true
	if visual is Sprite2D:
		tex = (visual as Sprite2D).texture
		offset = (visual as Sprite2D).offset
		centered = (visual as Sprite2D).centered
	elif visual is AnimatedSprite2D:
		var animated := visual as AnimatedSprite2D
		if animated.sprite_frames != null and animated.sprite_frames.has_animation(animated.animation) 				and animated.sprite_frames.get_frame_count(animated.animation) > 0:
			tex = animated.sprite_frames.get_frame_texture(animated.animation, 0)
		offset = animated.offset
		centered = animated.centered
	if tex == null:
		return NAN
	var y := offset.y
	if centered:
		y -= tex.get_size().y / 2.0
	var node: Node = visual
	while node != null and node != scene_root:
		if node is Node2D:
			y += (node as Node2D).position.y
		node = node.get_parent()
	return y + tex.get_size().y

func _collect_visuals(node: Node, out: Array) -> void:
	if node is Sprite2D or node is AnimatedSprite2D:
		out.append(node)
	for child in node.get_children():
		_collect_visuals(child, out)

func _check_ysort_origins() -> void:
	for dir_path in ENTITY_DIRS:
		for path in _list_files(dir_path.trim_suffix("/"), ["tscn"]):
			var packed := load(path) as PackedScene
			if packed == null:
				continue
			var inst := packed.instantiate()
			var visuals: Array = []
			_collect_visuals(inst, visuals)
			var ok := true
			for v in visuals:
				var bottom := visual_bottom(v, inst)
				if not is_nan(bottom) and absf(bottom) > ORIGIN_TOLERANCE:
					_fail("VAL-014", {"file": path, "y": "%.1f" % bottom}, path)
					ok = false
			inst.free()
			_item("ysort_origin", path, ok)

func _collect_entities(node: Node, out: Array) -> void:
	for child in node.get_children():
		if child.scene_file_path != "" and ENTITY_DIRS.any(func(d: String) -> bool: return child.scene_file_path.begins_with(d)):
			out.append(child)
		else:
			_collect_entities(child, out)

func _check_ysort_parents() -> void:
	for path in _list_files("res://game/maps", ["tscn"]):
		var packed := load(path) as PackedScene
		if packed == null:
			continue
		var inst := packed.instantiate()
		var entities: Array = []
		_collect_entities(inst, entities)
		var ok := true
		for e in entities:
			var parent: Node = e.get_parent()
			if not (parent is CanvasItem and (parent as CanvasItem).y_sort_enabled):
				_fail("VAL-015", {"node": String(inst.get_path_to(e)), "file": path}, path)
				ok = false
		inst.free()
		_item("ysort_parent", path, ok)
