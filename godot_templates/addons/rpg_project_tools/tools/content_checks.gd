@tool
extends RefCounted
## Content checks of a project's maps, dialogue and resources. Run headless by
## builder/validate.gd and in the editor by the validator panel; both call run(), so they report
## the same findings.
##
## A finding is {code, detail, file, node}: `detail` fills the message template of the code
## (it already holds "file"), `file` is a res:// path and `node` a path inside the scene ("" when
## the finding is about the whole file).

const EntityIds := preload("entity_ids.gd")
const Condition := preload("res://addons/rpg_runtime/dialogue/condition.gd")
const Sequence := preload("res://addons/rpg_runtime/events/sequence.gd")
const EncounterTable := preload("res://addons/rpg_runtime/data/encounter_table.gd")
const JsonIo := preload("json_io.gd")
const MapGraph := preload("map_graph.gd")
const RoomCheck := preload("room_check.gd")

const MAPS_DIR := "res://game/maps"
## The stored world plan (T13.20): its maps are the ones rpggen can mend, so a door of theirs
## that leads nowhere is a warning (VAL-028), not an error.
const WORLD_PLAN := "res://rpggen/world_plan.json"
const DIALOGUE_DIR := "res://game/data/dialogue"
const ITEMS_DIR := "res://game/data/items"
const SEQUENCES_DIR := "res://game/data/sequences"
const ENEMIES_DIR := "res://game/data/enemies"
const SKILLS_DIR := "res://game/data/skills"
const ACTORS_DIR := "res://game/data/actors"
const SHOPS_DIR := "res://game/data/shops"
const QUESTS_DIR := "res://game/data/quests"
const SKILL_TREES_DIR := "res://game/data/skill_trees"
const ACHIEVEMENTS_DIR := "res://game/data/achievements"
const ITEM_SETS_DIR := "res://game/data/item_sets"
const RECIPES_DIR := "res://game/data/recipes"
const DialogueRunner := preload("res://addons/rpg_runtime/dialogue/dialogue_runner.gd")
const TURN_BASED_DIR := "res://addons/rpg_runtime/archetypes/turn_based/"
const PLACEHOLDER_DIR := "res://generated/debug_placeholders/"
const RESOURCE_ROOTS: Array[String] = ["res://generated", "res://game"]
const DOOR_SUFFIX := "/world/door.gd"
const SPAWN_SUFFIX := "/world/spawn_point.gd"
const TRIGGER_SUFFIX := "/world/trigger_area.gd"
const ZONE_SUFFIX := "/world/encounter_zone.gd"
const GATE_SUFFIX := "/world/gate.gd"
const SWITCH_SUFFIX := "/world/switch.gd"

## `dirs` overrides the folders that are checked (tests): maps, dialogue, items, sequences, enemies,
## skills, actors, shops, quests, skill_trees, achievements, item_sets, placeholders and resources
## (an Array of roots).
static func run(dirs: Dictionary = {}) -> Array:
	var findings: Array = []
	var cache := {}  # map path -> instantiated scene (or null), freed at the end
	var maps := list_files(JsonIo.to_str(dirs.get("maps", MAPS_DIR)), ["tscn"])
	_check_entity_ids(maps, cache, findings)
	var world := world_maps(JsonIo.to_str(dirs.get("world_plan", WORLD_PLAN)))
	_check_doors(maps, cache, findings, world)
	_check_rooms(maps, cache, findings)
	var plan_path := JsonIo.to_str(dirs.get("world_plan", WORLD_PLAN))
	var plan: Variant = JsonIo.read(plan_path) if FileAccess.file_exists(plan_path) else {}
	var plan_start := MapGraph.start_for(JsonIo.to_dict(plan))
	_check_world(maps, cache, JsonIo.to_str(dirs.get("start", plan_start)), findings)
	_check_dialogue(JsonIo.to_str(dirs.get("dialogue", DIALOGUE_DIR)), JsonIo.to_str(dirs.get("items", ITEMS_DIR)), known_ids(dirs), findings)
	var sequences_dir := JsonIo.to_str(dirs.get("sequences", SEQUENCES_DIR))
	_check_sequences(sequences_dir, dirs, findings)
	_check_triggers(maps, cache, sequences_dir, findings)
	_check_zones(maps, cache, findings)
	_check_locks(maps, cache, JsonIo.to_str(dirs.get("items", ITEMS_DIR)), findings)
	_check_battle_data(dirs, findings)
	_check_game_data(dirs, findings)
	var roots: Array = dirs.get("resources", RESOURCE_ROOTS)
	_check_placeholders(roots, JsonIo.to_str(dirs.get("placeholders", PLACEHOLDER_DIR)), findings)
	for key: Variant in cache.keys():
		var cached: Node = cache[key]
		if cached != null:
			cached.free()
	findings.sort_custom(_before)
	return findings

static func _before(a: Dictionary, b: Dictionary) -> bool:
	var ka := "%s|%s|%s|%s" % [a["file"], a["node"], a["code"], str(a["detail"])]
	var kb := "%s|%s|%s|%s" % [b["file"], b["node"], b["code"], str(b["detail"])]
	return ka < kb

static func finding(code: String, detail: Dictionary, file: String, node: String = "") -> Dictionary:
	var d := detail.duplicate()
	d["file"] = file.trim_prefix("res://")
	return {"code": code, "detail": d, "file": file, "node": node}

## Files below dir_path with one of the extensions, sorted by path, recursive.
static func list_files(dir_path: String, extensions: Array) -> Array[String]:
	var found: Array[String] = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return found
	var entries: Array[Array] = []
	dir.list_dir_begin()
	var entry := dir.get_next()
	while entry != "":
		entries.append([entry, dir.current_is_dir()])
		entry = dir.get_next()
	dir.list_dir_end()
	entries.sort_custom(func(a: Array, b: Array) -> bool: return JsonIo.to_str(a[0]) < JsonIo.to_str(b[0]))
	for e: Array in entries:
		var entry_name: String = e[0]
		var is_dir: bool = e[1]
		var full: String = dir_path + "/" + entry_name
		if is_dir:
			if not entry_name.begins_with("."):
				found.append_array(list_files(full, extensions))
		elif extensions.has(entry_name.get_extension()):
			found.append(full)
	return found

static func _instance(path: String, cache: Dictionary) -> Node:
	if not cache.has(path):
		var packed := ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
		cache[path] = packed.instantiate() if packed != null else null
	return cache[path]

static func _script_ends_with(node: Node, suffix: String) -> bool:
	var script: Script = node.get_script()
	return script != null and script.resource_path.ends_with(suffix)

static func _walk(node: Node, out: Array) -> void:
	out.append(node)
	for child in node.get_children():
		_walk(child, out)

# ---------------------------------------------------------------- entity ids (VAL-008, VAL-009)

static func _check_entity_ids(maps: Array[String], cache: Dictionary, findings: Array) -> void:
	var owners := {}  # id -> Array of map paths (one entry per node)
	for path in maps:
		var root := _instance(path, cache)
		if root == null:
			continue
		for node in EntityIds.entity_nodes(root):
			var id := str(node.get("entity_id"))
			if id == "":
				if EntityIds.is_persistent(node):
					var node_path := String(root.get_path_to(node))
					findings.append(finding("VAL-009", {"node": node_path}, path, node_path))
				continue
			if not owners.has(id):
				owners[id] = []
			var owner_files: Array = owners[id]
			owner_files.append(path)
	var ids: Array = owners.keys()
	ids.sort()
	for id: String in ids:
		var files: Array = owners[id]
		if files.size() < 2:
			continue
		var unique: Array = []
		for f: Variant in files:
			var shown := JsonIo.to_str(f).trim_prefix("res://")
			if not unique.has(shown):
				unique.append(shown)
		var first_file: String = files[0]
		findings.append(finding("VAL-008", {"id": id, "files": ", ".join(unique)}, first_file))

# ---------------------------------------------------------------- doors (VAL-016, VAL-017)

static func _spawn_ids(root: Node) -> Array[String]:
	var nodes: Array[Node] = []
	_walk(root, nodes)
	var out: Array[String] = []
	for n in nodes:
		if _script_ends_with(n, SPAWN_SUFFIX):
			out.append(str(n.get("spawn_id")))
	return out

## The map paths (res://) of the stored world plan; empty without one.
static func world_maps(plan_path: String) -> Array[String]:
	var out: Array[String] = []
	var plan: Variant = JsonIo.read(plan_path) if FileAccess.file_exists(plan_path) else null
	if not (plan is Dictionary):
		return out
	var table: Dictionary = plan
	var areas: Variant = table.get("areas", [])
	if areas is Array:
		var list: Array = areas
		for raw: Variant in list:
			if raw is Dictionary:
				var area: Dictionary = raw
				var map := JsonIo.to_str(area.get("map", ""))
				out.append(map if map.contains("://") else "res://" + map)
	# the farm of a farm's plan (T17.06) is the world's too: its way out to the village is one
	# rpggen can mend, in a project whose village was made before the farm had a map
	var farm_map := JsonIo.to_str(JsonIo.to_dict(JsonIo.to_dict(table.get("farm", {})).get("map", {})).get("map", ""))
	if farm_map != "":
		out.append(farm_map if farm_map.contains("://") else "res://" + farm_map)
	return out

## VAL-027: a map the starter map cannot reach through doors (a warning: an island may be meant).
static func _check_world(maps: Array[String], cache: Dictionary, start: String, findings: Array) -> void:
	var graph := MapGraph.read(maps, func(path: String) -> Node: return _instance(path, cache))
	for path in MapGraph.unreachable(graph, start):
		findings.append(finding("VAL-027", {"map": path.get_file().get_basename()}, path))

static func _check_doors(maps: Array[String], cache: Dictionary, findings: Array, world: Array[String] = []) -> void:
	for path in maps:
		var root := _instance(path, cache)
		if root == null:
			continue
		var nodes: Array[Node] = []
		_walk(root, nodes)
		for node in nodes:
			# the exit of a side-view room (T14.06) is checked like a door, and is always the
			# world's: a missing partner is a warning rpggen can mend
			var is_exit := _script_ends_with(node, MapGraph.ROOM_EXIT_SUFFIX)
			if not is_exit and not _script_ends_with(node, DOOR_SUFFIX):
				continue
			var target := str(node.get("target_room" if is_exit else "target_map"))
			if target == "":
				continue  # a door that is not wired up yet (the runtime warns when it is used)
			var node_path := String(root.get_path_to(node))
			var mendable := is_exit or world.has(path) or world.has(target)  # rpggen can repair its world
			if not ResourceLoader.exists(target):
				if mendable:
					findings.append(finding("VAL-028", {"node": node_path, "what": "the map %s" % target.get_file()}, path, node_path))
				else:
					findings.append(finding("VAL-016", {"node": node_path, "target": target}, path, node_path))
				continue
			var spawn := str(node.get("target_exit" if is_exit else "target_spawn"))
			var target_root := _instance(target, cache)
			if target_root != null and not _spawn_ids(target_root).has(spawn):
				if mendable:
					findings.append(finding("VAL-028", {"node": node_path, "what": "the spawn point '%s' in %s" % [spawn, target.get_file()]}, path, node_path))
				else:
					findings.append(finding("VAL-017", {"node": node_path, "spawn": spawn, "target": target}, path, node_path))

# ---------------------------------------------------------------- rooms as painted (VAL-033)

## Whether the player gets through each side-view room as it is painted (room_check.gd): exits
## open, platforms that can be landed on, things standing on the floor, every exit up reached.
## The physics copy needs a node in the tree: the main loop's root (a validation run's, the
## editor's); without one the rooms are not checked.
## The room check alone (VAL-033), for a caller whose tree was not running when `run` was called:
## validate.gd runs the content checks in its _initialize and this in its _process.
static func room_findings(dirs: Dictionary = {}) -> Array:
	var findings: Array = []
	var cache := {}
	_check_rooms(list_files(JsonIo.to_str(dirs.get("maps", MAPS_DIR)), ["tscn"]), cache, findings)
	for key: Variant in cache.keys():
		var cached: Node = cache[key]
		if cached != null:
			cached.free()
	findings.sort_custom(_before)
	return findings

## The physics copy of a room lives under the tree's root: before the root is in the tree (a
## SceneTree script's _initialize) there is no physics to ask, and the rooms wait for room_findings.
static func _check_rooms(maps: Array[String], cache: Dictionary, findings: Array) -> void:
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null or tree.root == null or not tree.root.is_inside_tree():
		return
	for path in maps:
		var root := _instance(path, cache)
		if not RoomCheck.is_room(root):
			continue
		for issue: Dictionary in RoomCheck.new().check_room(root, tree.root):
			var node := JsonIo.to_str(issue.get("node", ""))
			findings.append(finding("VAL-033", {"node": node if node != "" else "The room", "problem": JsonIo.to_str(issue["message"])}, path, node))

# ---------------------------------------------------------------- dialogue (VAL-018, VAL-019)

## The shop, quest and actor ids that exist, as the dialogue events name them (T13.13): a shop and
## an actor by their file name (that is how the game finds them), a quest by its `id`.
static func known_ids(dirs: Dictionary = {}) -> Dictionary:
	var shops: Array[String] = []
	for path in list_files(JsonIo.to_str(dirs.get("shops", SHOPS_DIR)), ["tres"]):
		shops.append(path.get_file().get_basename())
	var actors: Array[String] = []
	for path in list_files(JsonIo.to_str(dirs.get("actors", ACTORS_DIR)), ["tres"]):
		actors.append(path.get_file().get_basename())
	return {"shop": shops, "quest": _item_ids(JsonIo.to_str(dirs.get("quests", QUESTS_DIR))), "actor": actors}

static func _item_ids(items_dir: String) -> Array[String]:
	var ids: Array[String] = []
	for path in list_files(items_dir, ["tres"]):
		var res := load(path)
		if res != null and res.get("id") != null:
			ids.append(str(res.get("id")))
	return ids

## Item ids an expression refers to: its item:<id>[>=N] atoms.
static func condition_items(expr: String) -> Array[String]:
	var out: Array[String] = []
	for token in expr.strip_edges().split(" ", false):
		if token.begins_with("item:"):
			out.append(token.trim_prefix("item:").get_slice(">=", 0))
	return out

## Item ids an event refers to: give_item:<id>[:qty] and take_item:<id>[:qty].
static func event_items(event: String) -> Array[String]:
	var parts := event.strip_edges().split(":")
	if parts.size() >= 2 and (parts[0] == "give_item" or parts[0] == "take_item"):
		return [parts[1]]
	return []

static func _check_dialogue(dialogue_dir: String, items_dir: String, ids: Dictionary, findings: Array) -> void:
	var files := list_files(dialogue_dir, ["tres"])
	if files.is_empty():
		return
	var known := _item_ids(items_dir)
	for path in files:
		var res := load(path)
		if res == null or res.get("lines") == null:
			continue
		var lines: Array = res.get("lines")
		var reported := {}
		for i in lines.size():
			var line: Object = lines[i]
			if line == null:
				continue
			var conditions: Array[String] = [str(line.get("condition"))]
			var line_choices: Array = line.get("choices")
			for choice: Object in line_choices:
				if choice != null:
					conditions.append(str(choice.get("condition")))
			for expr in conditions:
				if Condition.mixes_operators(expr):
					findings.append(finding("VAL-018", {"n": i + 1}, path))
					break
			var refs: Array = []  # [kind, id] of everything the line names
			for expr in conditions:
				for item in condition_items(expr):
					refs.append(["item", item])
			var line_events: Variant = line.get("events")
			for event: Variant in line_events:
				for item in event_items(str(event)):
					refs.append(["item", item])
				refs.append_array(DialogueRunner.event_refs(str(event).strip_edges()))
			for ref: Array in refs:
				var kind := str(ref[0])
				var id := str(ref[1])
				var exists: Array = known if kind == "item" else ids.get(kind, [])
				var key := "%s:%s" % [kind, id]
				if not exists.has(id) and not reported.has(key):
					reported[key] = true
					findings.append(finding("VAL-019", {"item": id, "kind": kind, "n": i + 1}, path))

# ---------------------------------------------------------------- sequences (VAL-023)

## A file an id names: <dir>/<id>.tres, or the id itself when it is a path.
static func _file_of(ref: String, dir_path: String) -> String:
	return ref if ref.contains("://") else "%s/%s.tres" % [dir_path, ref]

## The problems of one sequence's commands: Sequence.problems_of plus what they refer to (called
## sequences, dialogue files, enemies, maps) that does not exist.
static func sequence_problems(commands: Array, dirs: Dictionary = {}) -> Array[String]:
	var out := Sequence.problems_of(commands)
	var sequences_dir := JsonIo.to_str(dirs.get("sequences", SEQUENCES_DIR))
	var dialogue_dir := JsonIo.to_str(dirs.get("dialogue", DIALOGUE_DIR))
	var enemies_dir := JsonIo.to_str(dirs.get("enemies", ENEMIES_DIR))
	for i in commands.size():
		var command := JsonIo.to_dict(commands[i])
		var name := JsonIo.to_str(command.get("cmd", ""))
		var where := "command %d (%s)" % [i + 1, name]
		match name:
			"call":
				var called := JsonIo.to_str(command.get("sequence", ""))
				if called != "" and not ResourceLoader.exists(_file_of(called, sequences_dir)):
					out.append("%s calls the unknown sequence '%s'" % [where, called])
			"show_dialogue":
				var dialogue := JsonIo.to_str(command.get("dialogue", ""))
				if dialogue != "" and not ResourceLoader.exists(_file_of(dialogue, dialogue_dir)):
					out.append("%s shows the missing dialogue '%s'" % [where, dialogue])
			"start_battle":
				for enemy: Variant in JsonIo.to_array(command.get("enemies", [])):
					if not ResourceLoader.exists(_file_of(JsonIo.to_str(enemy), enemies_dir)):
						out.append("%s fights the unknown enemy '%s'" % [where, JsonIo.to_str(enemy)])
			"change_map":
				var map := JsonIo.to_str(command.get("map", ""))
				if map != "" and not ResourceLoader.exists(map):
					out.append("%s goes to the missing map '%s'" % [where, map])
	return out

static func _check_sequences(sequences_dir: String, dirs: Dictionary, findings: Array) -> void:
	for path in list_files(sequences_dir, ["tres"]):
		var res := load(path)
		if res == null or res.get("commands") == null:
			continue
		var commands: Array = res.get("commands")
		for problem in sequence_problems(commands, dirs):
			findings.append(finding("VAL-023", {"problem": problem}, path))

## Trigger areas that run no sequence, a missing one, or fire once without an entity id to remember it by.
static func _check_triggers(maps: Array[String], cache: Dictionary, sequences_dir: String, findings: Array) -> void:
	for path in maps:
		var root := _instance(path, cache)
		if root == null:
			continue
		var nodes: Array[Node] = []
		_walk(root, nodes)
		for node in nodes:
			if not _script_ends_with(node, TRIGGER_SUFFIX):
				continue
			var node_path := String(root.get_path_to(node))
			var sequence := JsonIo.to_str(node.get("sequence_id"))
			var embedded: Variant = node.get("sequence")
			var problems: Array[String] = []
			if embedded is Resource:
				var inner: Resource = embedded
				var commands: Array = inner.get("commands") if inner.get("commands") != null else []
				for found in sequence_problems(commands):
					problems.append("the trigger %s: %s" % [node_path, found])
			elif sequence == "":
				problems.append("the trigger %s runs no sequence" % node_path)
			elif not ResourceLoader.exists(_file_of(sequence, sequences_dir)):
				problems.append("the trigger %s runs the missing sequence '%s'" % [node_path, sequence])
			if JsonIo.to_bool(node.get("once")) and JsonIo.to_str(node.get("entity_id")) == "":
				problems.append("the trigger %s fires once but has no entity_id to remember it by" % node_path)
			for problem in problems:
				findings.append(finding("VAL-023", {"problem": problem}, path, node_path))

# ---------------------------------------------------------------- encounter zones (VAL-024)

## Zones without a table, with a table whose groups are broken, or with no shape and no cells layer.
static func _check_zones(maps: Array[String], cache: Dictionary, findings: Array) -> void:
	for path in maps:
		var root := _instance(path, cache)
		if root == null:
			continue
		var nodes: Array[Node] = []
		_walk(root, nodes)
		for node in nodes:
			if not _script_ends_with(node, ZONE_SUFFIX):
				continue
			var node_path := String(root.get_path_to(node))
			var problems: Array[String] = []
			var table: Variant = node.get("table")
			if table is Resource:
				var table_res: Resource = table
				problems.append_array(EncounterTable.problems_of(JsonIo.to_array(table_res.get("groups"))))
			else:
				problems.append("it has no encounter table")
			var shaped := false
			for child in node.get_children():
				if child is CollisionPolygon2D or child is CollisionShape2D:
					shaped = true
			var layer_path := JsonIo.to_str(node.get("cells_layer")) if node.get("cells_layer") != null else ""
			if not shaped and layer_path == "" and root.find_child("Encounters", true, false) == null:
				problems.append("it has no shape, no cells layer and the map has no Encounters layer")
			for problem in problems:
				findings.append(finding("VAL-024", {"node": node_path, "problem": problem}, path, node_path))

# ---------------------------------------------------------------- gates, switches, locked doors (VAL-025)

## Gates and locked doors whose key item does not exist, gates that can never open, and gates,
## switches and locked doors without the entity id their state is saved under.
static func _check_locks(maps: Array[String], cache: Dictionary, items_dir: String, findings: Array) -> void:
	var known := _item_ids(items_dir)
	for path in maps:
		var root := _instance(path, cache)
		if root == null:
			continue
		var nodes: Array[Node] = []
		_walk(root, nodes)
		for node in nodes:
			var is_gate := _script_ends_with(node, GATE_SUFFIX)
			var is_switch := _script_ends_with(node, SWITCH_SUFFIX)
			var is_door := _script_ends_with(node, DOOR_SUFFIX)
			if not (is_gate or is_switch or is_door):
				continue
			var node_path := String(root.get_path_to(node))
			var key := JsonIo.to_str(node.get("key_item")) if node.get("key_item") != null else ""
			var problems: Array[String] = []
			if key != "" and not known.has(key):
				problems.append("it needs the unknown item '%s'" % key)
			if is_gate and key == "" and JsonIo.to_str(node.get("open_when")) == "":
				problems.append("it has neither a key item nor an open_when condition, so it never opens")
			if (is_gate or is_switch or (is_door and key != "")) and JsonIo.to_str(node.get("entity_id")) == "":
				problems.append("it has no entity_id, so its state is not saved")
			for problem in problems:
				findings.append(finding("VAL-025", {"node": node_path, "problem": problem}, path, node_path))

# ---------------------------------------------------------------- battle data (VAL-026)

## Skills that are not well formed; actors, enemies and items that name an unknown skill or status;
## enemy rules and weights that use something that is neither a command nor a skill. Only where the
## turn-based runtime is installed: its scripts are loaded by path, because an action RPG's copy of
## the runtime does not have them.
static func _check_battle_data(dirs: Dictionary, findings: Array) -> void:
	if not ResourceLoader.exists(TURN_BASED_DIR + "battle_status.gd"):
		return
	var status_script: Script = load(TURN_BASED_DIR + "battle_status.gd")
	var skill_script: Script = load(TURN_BASED_DIR + "skill_definition.gd")
	var ai_script: Script = load(TURN_BASED_DIR + "battle_ai.gd")
	var controller_script: Script = load(TURN_BASED_DIR + "battle_controller.gd")
	var statuses: Array = status_script.call("names")
	var skills_dir := JsonIo.to_str(dirs.get("skills", SKILLS_DIR))
	var skills: Dictionary = skill_script.call("load_dir", skills_dir)
	for path in list_files(skills_dir, ["tres"]):
		var skill := load(path) as Resource
		if skill == null or not skill.has_method("problems"):
			continue
		var problems: PackedStringArray = skill.call("problems")
		for problem in problems:
			findings.append(finding("VAL-026", {"problem": "skill: " + problem}, path))
	var uses: Array = skills.keys()
	var commands: Array = controller_script.call("load_commands")
	for command: Resource in commands:
		uses.append(command.get("id"))
	for dir_key: String in ["actors", "enemies"]:
		var fallback := ACTORS_DIR if dir_key == "actors" else ENEMIES_DIR
		for path in list_files(JsonIo.to_str(dirs.get(dir_key, fallback)), ["tres"]):
			var actor := load(path) as RpgActorDefinition
			if actor == null:
				continue
			var problems := traits_problems(actor.status_immune, actor.attack_status, statuses)
			for skill_id: Variant in actor.skills.keys():
				if not skills.has(StringName(str(skill_id))):
					problems.append("it knows the unknown skill '%s'" % skill_id)
			var enemy := actor as RpgEnemyDefinition
			if enemy != null:
				problems.append_array(behavior_problems(enemy.behavior, uses))
				var rule_problems: PackedStringArray = ai_script.call("problems_of", enemy.behavior.get("turn_based_rules"), uses)
				for problem in rule_problems:
					problems.append(problem)
			for problem in problems:
				findings.append(finding("VAL-026", {"problem": problem}, path))
	for path in list_files(JsonIo.to_str(dirs.get("items", ITEMS_DIR)), ["tres"]):
		var item := load(path) as RpgItemDefinition
		if item == null:
			continue
		var problems := traits_problems(item.status_immune, item.attack_status, statuses)
		for cured in item.cures:
			if not statuses.has(cured):
				problems.append("it cures the unknown status '%s'" % cured)
		for problem in problems:
			findings.append(finding("VAL-026", {"problem": problem}, path))

## VAL-034 (1.5.0): what the quests, skill trees and achievements say is wrong with them
## (their `problems()`), an item whose `set_id` names no set, and a shop's row of an item that has
## no file (1.5.0, T18.02).
static func _check_game_data(dirs: Dictionary, findings: Array) -> void:
	for kind: Array in [["quests", QUESTS_DIR, "quest"], ["skill_trees", SKILL_TREES_DIR, "skill tree"], ["achievements", ACHIEVEMENTS_DIR, "achievement"], ["item_sets", ITEM_SETS_DIR, "item set"]]:
		for path in list_files(JsonIo.to_str(dirs.get(kind[0], kind[1])), ["tres"]):
			var res := load(path) as Resource
			if res == null or not res.has_method("problems"):
				continue
			var problems: Array = res.call("problems")
			for problem: Variant in problems:
				findings.append(finding("VAL-034", {"problem": "%s: %s" % [kind[2], problem]}, path))
	var sets_dir := JsonIo.to_str(dirs.get("item_sets", ITEM_SETS_DIR))
	for path in list_files(JsonIo.to_str(dirs.get("items", ITEMS_DIR)), ["tres"]):
		var item := load(path) as RpgItemDefinition
		if item != null and item.set_id != &"" and not ResourceLoader.exists("%s/%s.tres" % [sets_dir, item.set_id]):
			findings.append(finding("VAL-034", {"problem": "the item belongs to the set '%s', which has no file in %s" % [item.set_id, sets_dir]}, path))
	var item_ids := _item_ids(JsonIo.to_str(dirs.get("items", ITEMS_DIR)))
	# the recipes of crafting (T18.14): their own problems, the items and the stations they name
	var stations := station_ids(dirs)
	for path in list_files(JsonIo.to_str(dirs.get("recipes", RECIPES_DIR)), ["tres"]):
		var made := load(path) as RpgRecipe
		if made == null:
			continue
		var problems: Array[String] = made.problems()
		for item_id in made.items():
			if not item_ids.has(item_id):
				problems.append("'%s' has no file in %s" % [item_id, JsonIo.to_str(dirs.get("items", ITEMS_DIR))])
		if made.station != &"" and not stations.has(String(made.station)):
			problems.append("it is made at the station '%s', which no map has" % made.station)
		for problem in problems:
			findings.append(finding("VAL-034", {"problem": "recipe: " + problem}, path))
	for path in list_files(JsonIo.to_str(dirs.get("shops", SHOPS_DIR)), ["tres"]):
		var shop := load(path) as RpgShopDefinition
		if shop != null:
			for problem in shop.stock_problems(item_ids):
				findings.append(finding("VAL-034", {"problem": "shop: " + problem}, path))

## The station ids the maps have (`station_id = &"<id>"` of an RpgStation in a scene) and those a
## farm's stored plan puts on its maps (its workbench, T18.15; its kitchen, T18.16).
static func station_ids(dirs: Dictionary) -> Array[String]:
	var out: Array[String] = []
	var marker := RegEx.create_from_string("station_id = &\"([a-z0-9_]+)\"")
	for path in list_files(JsonIo.to_str(dirs.get("maps", MAPS_DIR)), ["tscn"]):
		for found in marker.search_all(FileAccess.get_file_as_string(path)):
			if not out.has(found.get_string(1)):
				out.append(found.get_string(1))
	var plan := JsonIo.to_dict(JSON.parse_string(FileAccess.get_file_as_string(JsonIo.to_str(dirs.get("world_plan", WORLD_PLAN))))) if FileAccess.file_exists(JsonIo.to_str(dirs.get("world_plan", WORLD_PLAN))) else {}
	var farm_map := JsonIo.to_dict(JsonIo.to_dict(plan.get("farm", {})).get("map", {}))
	for station: String in ["workbench", "kitchen"]:
		if farm_map.has(station) and not out.has(station):
			out.append(station)
	return out

## Unknown statuses (not in `statuses`) in an immunity list or an attack's status.
static func traits_problems(immune: Array[StringName], attack_status: StringName, statuses: Array) -> Array[String]:
	var out: Array[String] = []
	for status in immune:
		if not statuses.has(status):
			out.append("it is immune to the unknown status '%s'" % status)
	if attack_status != &"" and not statuses.has(attack_status):
		out.append("its attack inflicts the unknown status '%s'" % attack_status)
	return out

## The turn-based weights of an enemy's behavior: every key must be a command or a skill (`uses`).
static func behavior_problems(behavior: Dictionary, uses: Array) -> Array[String]:
	var out: Array[String] = []
	var weights: Variant = behavior.get("turn_based", {})
	if weights is Dictionary:
		var weight_dict: Dictionary = weights
		for key: Variant in weight_dict.keys():
			if not uses.has(StringName(str(key))):
				out.append("its turn_based weights name '%s', which is neither a command nor a skill" % key)
	return out

# ---------------------------------------------------------------- placeholders (VAL-012)

static func _check_placeholders(roots: Array, placeholder_dir: String, findings: Array) -> void:
	for root_dir: String in roots:
		for path in list_files(root_dir, ["tres", "tscn"]):
			for dep in ResourceLoader.get_dependencies(path):
				if _dependency_path(String(dep)).begins_with(placeholder_dir):
					findings.append(finding("VAL-012", {}, path))
					break

## The file a ResourceLoader.get_dependencies entry points to ("" for an unknown uid).
static func _dependency_path(dep: String) -> String:
	var path := dep
	if dep.contains("::"):
		path = dep.get_slice("::", dep.get_slice_count("::") - 1)
	if path.begins_with("uid://"):
		var id := ResourceUID.text_to_id(path)
		return ResourceUID.get_id_path(id) if ResourceUID.has_id(id) else ""
	return path
