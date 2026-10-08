extends SceneTree
# Run: godot --headless --path <proj> --script res://generated/builder/validate.gd
# Static checks run in _initialize; scene instantiation is a small state machine in _process
# because scenes need a frame in the tree.

const Paths := preload("lib/paths.gd")
const BuildContext := preload("lib/build_context.gd")
const Log := preload("lib/log.gd")
const JsonUtil := preload("lib/json_util.gd")

const CHECK_ROOTS: Array[String] = ["res://addons", "res://generated", "res://game"]
const RESOURCE_ROOTS: Array[String] = ["res://generated", "res://game"]
const CONTENT_CHECKS := "res://addons/rpg_project_tools/tools/content_checks.gd"
const ROUND_TRIP_TMP := "user://rt_test.tscn"
const MENU_SCENES: Array[String] = [
	"res://generated/scenes/ui/title_screen.tscn",
	"res://generated/scenes/ui/pause_menu.tscn",
	"res://generated/scenes/ui/inventory_menu.tscn",
	"res://generated/scenes/ui/status_menu.tscn",
	"res://generated/scenes/ui/save_load_menu.tscn",
	"res://generated/scenes/ui/settings_menu.tscn",
	"res://generated/scenes/ui/game_over.tscn",
]
const FOCUS_SETTLE_FRAMES := 4
const FOCUS_MAX_STEPS := 80

var _ctx: BuildContext
var _scenes: Array[String] = []
var _scene_index: int = 0
var _pending: Node = null
var _pending_path: String = ""
var _finished: bool = false
var _focus: Dictionary = {}  # state of the running menu focus walk (empty = none)

## One progress line per check (T12.19); the last one covers the scene loop of _process.
const STEP_TOTAL := 12
var _step_index := 0

func _announce(label: String) -> void:
	_step_index += 1
	Log.step("validate", _step_index, STEP_TOTAL, label)

func _initialize() -> void:
	var here: Script = get_script()
	var builder_dir: String = here.resource_path.get_base_dir()
	_ctx = BuildContext.new(builder_dir, "validate")
	if not _ctx.load_inputs():
		_finish()
		return
	_announce("scripts")
	_check_scripts()
	_announce("resources")
	var resources := _check_resources()
	_announce("dependencies")
	_check_dependencies(resources)
	_announce("main scene")
	_check_main_scene()
	_announce("autoloads")
	_check_autoloads()
	_announce("input actions")
	_check_input_actions()
	for path in resources:
		if JsonUtil.to_str(path).ends_with(".tscn"):
			_scenes.append(path)
	_announce("starter map")
	_check_map_round_trip("res://game/maps/starter_map.tscn")
	_announce("y-sort origins")
	_check_ysort_origins()
	_announce("y-sort parents")
	_check_ysort_parents()
	_announce("content")
	_check_content()
	_announce("sound bank")
	_check_sound_bank()
	_announce("scenes and menus")

func _process(_delta: float) -> bool:
	if _finished or _ctx == null:
		return false
	if _pending != null:
		if _pending_path in MENU_SCENES and _focus_walk_step():
			return false
		_pending.queue_free()
		_pending = null
		_pending_path = ""
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
	_pending_path = path
	_focus = {}
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

static func _list_files(dir_path: String, extensions: Array) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	var entries: Array[Array] = []
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		entries.append([name, dir.current_is_dir()])
		name = dir.get_next()
	dir.list_dir_end()
	entries.sort_custom(func(a: Array, b: Array) -> bool: return JsonUtil.to_str(a[0]) < JsonUtil.to_str(b[0]))
	for e: Array in entries:
		var entry_name: String = e[0]
		var is_dir: bool = e[1]
		var full: String = dir_path + "/" + entry_name
		if is_dir:
			if not entry_name.begins_with("."):
				found.append_array(_list_files(full, extensions))
		elif extensions.has(entry_name.get_extension()):
			found.append(full)
	return found

# ---------------------------------------------------------------- checks

func _is_editor_only(script: GDScript) -> bool:
	var base := String(script.get_instance_base_type())
	return ClassDB.is_parent_class(base, "EditorPlugin") or ClassDB.is_parent_class(base, "EditorScript")

func _check_scripts() -> void:
	for root_dir in CHECK_ROOTS:
		for path in _list_files(root_dir, ["gd"]):
			var script: Resource = load(path)
			var gd := script as GDScript
			var ok: bool = gd != null
			if ok and not _is_editor_only(gd):
				ok = gd.can_instantiate()
			if not ok:
				_fail("VAL-001", {"file": path}, path)
			_item("script_parse", path, ok)

func _check_resources() -> Array[String]:
	var paths: Array[String] = []
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

func _check_dependencies(resources: Array[String]) -> void:
	for path in resources:
		var ok := true
		for dep in ResourceLoader.get_dependencies(path):
			var dep_path := _dependency_path(String(dep))
			if dep_path == "" or not ResourceLoader.exists(dep_path):
				_fail("VAL-003", {"dep": dep_path if dep_path != "" else String(dep), "file": path}, path)
				ok = false
		_item("dependencies", path, ok)

func _check_main_scene() -> void:
	var main_scene := JsonUtil.to_str(ProjectSettings.get_setting("application/run/main_scene", ""))
	var ok := main_scene != "" and ResourceLoader.exists(main_scene)
	if not ok:
		_fail("VAL-005", {})
	_item("main_scene", main_scene, ok)

func _check_autoloads() -> void:
	for prop in ProjectSettings.get_property_list():
		var name := JsonUtil.to_str(prop["name"])
		if not name.begins_with("autoload/"):
			continue
		var value := JsonUtil.to_str(ProjectSettings.get_setting(name)).trim_prefix("*")
		var ok := ResourceLoader.exists(value)
		if not ok:
			_fail("VAL-006", {"name": name.trim_prefix("autoload/")})
		_item("autoload", name, ok)

func _check_input_actions() -> void:
	var input: Dictionary = _ctx.section("input")
	var actions: Array = input.keys()
	actions.sort()
	for action: String in actions:
		var ok := InputMap.has_action(action) and InputMap.action_get_events(action).size() > 0
		if not ok:
			_fail("VAL-007", {"action": action})
		_item("input_action", JsonUtil.to_str(action), ok)

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
	var layers: Array[TileMapLayer] = []
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
		for layer_path: NodePath in before.keys():
			var layer := reloaded.get_node_or_null(layer_path) as TileMapLayer
			var original: Dictionary = before[layer_path]
			if layer == null:
				ok = false
				failed_layer = JsonUtil.to_str(layer_path)
				break
			var now := _cell_set(layer)
			var expected := original.duplicate()
			expected[test_cell] = true
			if now.keys().size() != expected.keys().size() or not now.has(test_cell):
				ok = false
				failed_layer = JsonUtil.to_str(layer_path)
				break
			for c: Vector2i in original.keys():
				if not now.has(c):
					ok = false
					failed_layer = JsonUtil.to_str(layer_path)
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

# ---------------------------------------------------------------- content (T8.04)
# Entity ids, doors, dialogue and placeholders: the same checks the editor's validator panel runs
# (they live in the tools addon, which a project without the editor tools does not have).

func _check_content() -> void:
	if not ResourceLoader.exists(CONTENT_CHECKS):
		return
	var checks: Resource = load(CONTENT_CHECKS)
	if checks == null:
		return
	var findings: Array = checks.call("run")
	for f: Dictionary in findings:
		var detail: Dictionary = f["detail"]
		_fail(JsonUtil.to_str(f["code"]), detail, JsonUtil.to_str(f["file"]))
	_item("content_checks", "res://game", findings.is_empty())

# ---------------------------------------------------------------- sound slots (VAL-020)

const SOUND_BANK_PATH := "res://rpggen/sound_bank.json"

## Every slot of the sound bank must point at a stream that loads.
func _check_sound_bank() -> void:
	if not FileAccess.file_exists(SOUND_BANK_PATH):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SOUND_BANK_PATH))
	if not parsed is Dictionary:
		_fail("VAL-020", {"slot": "(file)", "path": SOUND_BANK_PATH}, SOUND_BANK_PATH)
		return
	var ok := true
	var table: Dictionary = parsed
	for slot: Variant in table.keys():
		var path := JsonUtil.to_str(table[slot])
		if not ResourceLoader.exists(path) or not load(path) is AudioStream:
			ok = false
			_fail("VAL-020", {"slot": JsonUtil.to_str(slot), "path": path}, path)
	_item("sound_bank", SOUND_BANK_PATH, ok)

# ---------------------------------------------------------------- Y-sort (T4.07)
# Headless mode renders nothing, so Y-sort is checked logically: a visual's bottom edge sits on the
# node origin (y = 0), and every placed entity has a Y-sorted parent.

const ORIGIN_TOLERANCE := 2.0
const ENTITY_DIRS: Array[String] = ["res://generated/scenes/objects/", "res://generated/scenes/actors/"]

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
			var visuals: Array[Node2D] = []
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
		var entities: Array[Node] = []
		_collect_entities(inst, entities)
		var ok := true
		for e in entities:
			var parent: Node = e.get_parent()
			if not (parent is CanvasItem and (parent as CanvasItem).y_sort_enabled):
				_fail("VAL-015", {"node": String(inst.get_path_to(e)), "file": path}, path)
				ok = false
		inst.free()
		_item("ysort_parent", path, ok)

# ---------------------------------------------------------------- menu focus (VAL-011)
# Each menu scene stays in the tree for as long as the walk takes: wait a few frames for the
# initial focus, then press ui_down once per frame and follow gui_get_focus_owner() until it
# cycles. Every visible, enabled button must have been reached.

static func _focusables(node: Node, out: Array) -> void:
	if node is Control:
		var c := node as Control
		if not c.visible:
			return
		if c.focus_mode != Control.FOCUS_NONE and (node is BaseButton or node is Slider):
			if not (node is BaseButton and (node as BaseButton).disabled):
				out.append(c)
	for child in node.get_children():
		_focusables(child, out)

func _menu_problem(reason: String) -> void:
	_fail("VAL-011", {"scene": _pending_path.get_file(), "reason": reason}, _pending_path)
	_item("ui_focus", _pending_path, false)

func _press_ui_down() -> void:
	for pressed: bool in [true, false]:
		var ev := InputEventAction.new()
		ev.action = "ui_down"
		ev.pressed = pressed
		Input.parse_input_event(ev)

## One frame of the walk. Returns true while it still needs more frames.
func _focus_walk_step() -> bool:
	if _focus.is_empty():
		_focus = {"frame": 0, "phase": "settle", "visited": [], "initial": null, "all": []}
	var f := _focus
	f["frame"] += 1
	var owner_now: Control = root.gui_get_focus_owner()
	match f["phase"]:
		"settle":
			if f["frame"] < FOCUS_SETTLE_FRAMES:
				return true
			var all: Array = []
			_focusables(_pending, all)
			f["all"] = all
			if all.is_empty():
				_menu_problem("no focusable control")
				return false
			if owner_now == null or not _pending.is_ancestor_of(owner_now):
				_menu_problem("nothing has focus after opening")
				return false
			f["initial"] = owner_now
			f["visited"] = [owner_now]
			f["phase"] = "press"
			_press_ui_down()
			f["phase"] = "read"
			return true
		"read":
			f["phase"] = "press"
			var visited: Array = f["visited"]
			if owner_now == null or owner_now == f["initial"] or visited.has(owner_now) or visited.size() >= FOCUS_MAX_STEPS:
				var missed: Array = []
				var all_controls: Array = f["all"]
				for c: Control in all_controls:
					if not visited.has(c):
						missed.append(JsonUtil.to_str(c.name))
				if missed.is_empty():
					_item("ui_focus", _pending_path, true)
				else:
					_menu_problem("not reachable with ui_down: %s" % ", ".join(missed))
				return false
			visited.append(owner_now)
			_press_ui_down()
			f["phase"] = "read"
			return true
	return false
