extends RefCounted
## World repair (T13.24): the three repairs on fixture worlds, what is left alone, what cannot be
## mended, the headless tool's result, and the dock's undoable Fix.

const Repair := preload("res://addons/rpg_project_tools/tools/world_repair.gd")
const MapGraph := preload("res://addons/rpg_project_tools/tools/map_graph.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")
const ValidatorPanel := preload("res://addons/rpg_project_tools/dock/validator_panel.gd")
const Tool := preload("res://builder/tools/world_repair.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")

const DIR := "user://world_repair"
const SIZE := Vector2i(12, 8)

var _roots: Array[Node] = []

func _setup() -> void:
	Maps.remove_tree(DIR)
	DirAccess.make_dir_recursive_absolute(DIR + "/maps")

func _finish() -> void:
	for root in _roots:
		if is_instance_valid(root):
			root.free()
	_roots.clear()
	Maps.remove_tree(DIR)

func _path(id: String) -> String:
	return DIR + "/maps/%s.tscn" % id

## A walled map of SIZE cells: floor inside, a solid tile all around (`solid_everywhere` makes
## every cell solid), with SpawnPoints and Triggers holders.
func _map(id: String, solid_everywhere: bool = false) -> Node2D:
	var root := Maps.map(id)
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_physics_layer()
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(Image.create(32, 16, false, Image.FORMAT_RGBA8))
	source.texture_region_size = Vector2i(16, 16)
	ts.add_source(source, 0)
	source.create_tile(Vector2i(0, 0))
	source.create_tile(Vector2i(1, 0))
	var wall := source.get_tile_data(Vector2i(1, 0), 0)
	wall.add_collision_polygon(0)
	wall.set_collision_polygon_points(0, 0, PackedVector2Array([Vector2(-8, -8), Vector2(8, -8), Vector2(8, 8), Vector2(-8, 8)]))
	var layer := TileMapLayer.new()
	layer.name = "Ground"
	layer.tile_set = ts
	root.add_child(layer)
	for y in SIZE.y:
		for x in SIZE.x:
			var border := x == 0 or y == 0 or x == SIZE.x - 1 or y == SIZE.y - 1
			layer.set_cell(Vector2i(x, y), 0, Vector2i(1, 0) if border or solid_everywhere else Vector2i(0, 0))
	for holder_name: String in ["SpawnPoints", "Triggers"]:
		var holder := Node2D.new()
		holder.name = holder_name
		root.add_child(holder)
	return root

func _door(root: Node2D, node_name: String, cell: Vector2i, target: String, spawn: String) -> void:
	var door := Maps.door(root.get_node("Triggers"), node_name, target, spawn)
	door.position = Vector2(cell) * 16.0 + Vector2(8, 8)

func _spawn(root: Node2D, spawn_id: String, cell: Vector2i) -> void:
	var marker := Maps.spawn(root.get_node("SpawnPoints"), spawn_id, spawn_id)
	marker.position = Vector2(cell) * 16.0 + Vector2(8, 8)

func _instance(path: String) -> Node:
	var root := (ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_MAIN)
	_roots.append(root)
	return root

func _paths(ids: Array) -> Array[String]:
	var out: Array[String] = []
	for id: String in ids:
		out.append(_path(id))
	return out

func _kinds(actions: Array[Dictionary]) -> Array:
	var out: Array = []
	for action in actions:
		out.append("%s:%s" % [action["kind"], str(action["map"]).get_file().get_basename()])
	return out

## Plans with fresh instances; they are freed by _finish().
func _plan(ids: Array, plan: Dictionary = {}) -> Array[Dictionary]:
	var cache := {}
	return Repair.plan_repairs(_paths(ids), plan, func(path: String) -> Node:
		if not cache.has(path):
			cache[path] = _instance(path)
		return cache[path], _path("a"))

func _run(ids: Array, plan: Dictionary = {}, dry_run: bool = false, limited: bool = false, only: Array[String] = []) -> Dictionary:
	assert(not ids.is_empty())
	return Tool.run(DIR + "/maps", plan, dry_run, limited, only, _path("a"))

func _codes() -> Array:
	var out: Array = []
	for finding: Dictionary in ContentChecks.run({"maps": DIR + "/maps", "start": _path("a"), "world_plan": DIR + "/none.json", "dialogue": DIR + "/x", "items": DIR + "/x", "resources": [DIR + "/x"], "placeholders": DIR + "/x/"}):
		out.append(finding["code"])
	return out

# ---------------------------------------------------------------- surveying a map

func test_a_map_is_surveyed_for_floor_and_walls(t) -> void:
	_setup()
	var a := _map("a")
	var info := Repair.survey(a)
	t.eq(info["tile"], 16)
	t.eq(info["rect"], Rect2i(Vector2i.ZERO, SIZE))
	t.ok(Repair.walkable(info, Vector2i(1, 1)) and not Repair.walkable(info, Vector2i(0, 1)), "the border is solid")
	t.ok(not Repair.walkable(info, Vector2i(40, 40)), "nothing painted there")
	t.eq(Repair.cell_of(info, Vector2(24, 40)), Vector2i(1, 2))
	t.eq(Repair.center_of(info, Vector2i(1, 2)), Vector2(24, 40))
	t.eq(Repair.edge_of(info, Vector2i(10, 4)), "E")
	t.eq(Repair.edge_of(info, Vector2i(5, 1)), "N")
	t.eq(Repair.nearest_walkable(info, Vector2i(0, 0), Vector2i(-1, -1)), Vector2i(1, 1))
	t.eq(Repair.nearest_walkable(info, Vector2i(60, 60), Vector2i(-1, -1)), Vector2i(-1, -1), "further than three tiles")
	# a door stands on the floor beside the wall, and the player arrives one cell further in
	t.eq(Repair.place_on_edge(info, "W"), {"door": Vector2i(1, 4), "spawn": Vector2i(2, 4)})
	t.eq(Repair.place_on_edge(info, "S", 0.0), {"door": Vector2i(1, 6), "spawn": Vector2i(1, 5)}, "scanned from the wanted place outwards")
	t.eq(Repair.place_on_edge(Repair.survey(_keep(_map("x", true))), "W"), {}, "no floor at all")
	a.free()
	_finish()

func _keep(root: Node2D) -> Node2D:
	_roots.append(root)
	return root

# ---------------------------------------------------------------- the three repairs

func test_a_door_to_a_missing_spawn_gets_its_spawn_and_a_door_back(t) -> void:
	_setup()
	var a := _map("a")
	_door(a, "ToB", Vector2i(10, 3), _path("b"), "from_a")
	Maps.save(a, _path("a"))
	Maps.save(_map("b"), _path("b"))
	t.eq(_codes(), ["VAL-017"], "the door arrives nowhere")
	var actions := _plan(["a", "b"])
	t.eq(_kinds(actions), ["spawn:b", "spawn:a", "door:b"])
	t.eq(actions[0]["spawn_id"], "from_a")
	t.eq(actions[0]["position"], Vector2(2 * 16 + 8, 3 * 16 + 8), "the opposite edge, the same offset, one cell in from the door")
	t.eq(actions[0]["facing"], "right")
	t.eq(actions[2]["position"], Vector2(1 * 16 + 8, 3 * 16 + 8))
	t.eq([actions[2]["target_map"], actions[2]["target_spawn"]], [_path("a"), "from_b"])
	t.ok(str(actions[0]["what"]).contains("added the spawn point from_a"))
	var result := _run(["a", "b"])
	t.eq(result["repairs"].size(), 3)
	t.eq(result["unfixable"], [])
	t.eq(result["repairs"][0]["map"], _path("b"))
	t.eq(_codes(), [], "mended")
	t.eq(_plan(["a", "b"]), [] as Array[Dictionary], "a second run finds nothing to do")
	_finish()

func test_a_planned_pair_is_mended_where_the_plan_put_it(t) -> void:
	_setup()
	var a := _map("a")
	_door(a, "a_door_b", Vector2i(10, 3), _path("b"), "from_a")
	_spawn(a, "from_b", Vector2i(9, 3))
	Maps.save(a, _path("a"))
	Maps.save(_map("b"), _path("b"))
	var plan := {"areas": [
		{"id": "a", "map": _path("a"), "doors": []},
		{"id": "b", "map": _path("b"), "doors": [{"id": "b_door_a", "cell": [5, 1], "spawn": [5, 2], "spawn_id": "from_a", "facing": "down", "to_map": _path("a"), "to_spawn": "from_b"}]},
	]}
	var actions := _plan(["a", "b"], plan)
	t.eq(_kinds(actions), ["spawn:b", "door:b"], "the source has its spawn already: none is added there")
	t.eq(actions[0]["position"], Vector2(5 * 16 + 8, 2 * 16 + 8), "the plan's cell, not the geometry's")
	t.eq(actions[0]["facing"], "down")
	t.eq(actions[1]["name"], "b_door_a")
	t.eq(actions[1]["position"], Vector2(5 * 16 + 8, 1 * 16 + 8))
	t.eq(actions[1]["target_spawn"], "from_b")
	_finish()

func test_a_door_to_a_missing_map_is_pointed_at_the_map_the_plan_paired_it_with(t) -> void:
	_setup()
	var a := _map("a")
	_door(a, "a_door_b", Vector2i(10, 3), _path("gone"), "from_a")
	_spawn(a, "from_b", Vector2i(9, 3))
	Maps.save(a, _path("a"))
	var b := _map("b")
	_door(b, "b_door_a", Vector2i(1, 3), _path("a"), "from_b")
	_spawn(b, "from_a", Vector2i(2, 3))
	Maps.save(b, _path("b"))
	t.eq(_codes(), ["VAL-016", "VAL-027"], "the door leads to no map, so b cannot be reached either")
	var plan := {"grid": {"a": [0, 0], "b": [1, 0]}, "areas": [
		{"id": "a", "map": _path("a"), "doors": [{"id": "a_door_b", "to_map": _path("b"), "to_spawn": "from_a"}]},
		{"id": "b", "map": _path("b"), "doors": []},
	]}
	var actions := _plan(["a", "b"], plan)
	t.eq(_kinds(actions), ["retarget:a"])
	t.eq([actions[0]["target_map"], actions[0]["target_spawn"]], [_path("b"), "from_a"])
	_run(["a", "b"], plan)
	t.eq(_codes(), [])
	# without a pair in the plan: the nearest map on the plan's grid; without a plan: nothing safe
	plan["areas"][0]["doors"] = []
	a = _instance(_path("a")) as Node2D
	a.get_node("Triggers/a_door_b").set("target_map", _path("gone"))
	_roots.erase(a)
	Maps.save(a, _path("a"))
	actions = _plan(["a", "b"], plan)
	t.eq(_kinds(actions), ["retarget:a"])
	t.eq(actions[0]["target_map"], _path("b"))
	actions = _plan(["a", "b"])
	t.eq(_kinds(actions), ["unfixable:a", "door:a"], "the broken door is left; b is joined by a new one")
	t.ok(str(actions[0]["what"]).contains("knows no other map"))
	t.eq([actions[1]["target_map"], actions[1]["target_spawn"]], [_path("b"), "from_a"], "to the spawn b already has")
	t.eq([actions[0]["cause_node"], actions[1]["cause_node"]], ["Triggers/a_door_b", ""], "each answers its own finding")
	t.eq(Repair.actions_for(actions, _path("b"), "").size(), 1)
	_finish()

func test_a_map_that_cannot_be_reached_gets_a_door_pair(t) -> void:
	_setup()
	Maps.save(_map("a"), _path("a"))
	Maps.save(_map("c"), _path("c"))
	t.eq(_codes(), ["VAL-027"])
	var actions := _plan(["a", "c"])
	t.eq(_kinds(actions), ["spawn:c", "door:c", "spawn:a", "door:a"], "not in a plan: joined to the start map")
	var result := _run(["a", "c"])
	t.eq(result["repairs"].size(), 4)
	t.eq(_codes(), [])
	var graph := MapGraph.read(_paths(["a", "c"]), func(path: String) -> Node: return _instance(path))
	t.ok(MapGraph.has_door(graph, _path("a"), _path("c")) and MapGraph.has_door(graph, _path("c"), _path("a")))
	t.eq(MapGraph.dangling(graph, func(path: String) -> bool: return FileAccess.file_exists(path)), [] as Array[Dictionary])
	_finish()

func test_an_area_of_the_plan_is_joined_to_its_neighbour_on_the_grid(t) -> void:
	_setup()
	for id: String in ["a", "b", "c"]:
		var root := _map(id)
		if id == "a":
			_door(root, "a_door_b", Vector2i(10, 3), _path("b"), "from_a")
			_spawn(root, "from_b", Vector2i(9, 3))
		if id == "b":
			_door(root, "b_door_a", Vector2i(1, 3), _path("a"), "from_b")
			_spawn(root, "from_a", Vector2i(2, 3))
		Maps.save(root, _path(id))
	# c lies south of b on the grid: it is joined to b, not to the start map
	var plan := {"grid": {"a": [0, 0], "b": [1, 0], "c": [1, 1]}, "areas": [
		{"id": "a", "map": _path("a"), "doors": []}, {"id": "b", "map": _path("b"), "doors": []}, {"id": "c", "map": _path("c"), "doors": []},
	]}
	var actions := _plan(["a", "b", "c"], plan)
	t.eq(_kinds(actions), ["spawn:c", "door:c", "spawn:b", "door:b"])
	t.eq(actions[1]["name"], "c_door_b")
	t.eq(actions[1]["position"], Vector2(6 * 16 + 8, 1 * 16 + 8), "the middle of c's north edge")
	t.eq(actions[3]["position"], Vector2(6 * 16 + 8, 6 * 16 + 8), "the middle of b's south edge")
	# an area with no reachable neighbour on the grid is reported, not guessed at
	plan["grid"]["c"] = [5, 5]
	actions = _plan(["a", "b", "c"], plan)
	t.eq(_kinds(actions), ["unfixable:c"])
	t.ok(str(actions[0]["what"]).contains("no reachable map lies beside it"))
	_finish()

# ---------------------------------------------------------------- what is left alone

func test_a_door_with_its_partner_is_untouched(t) -> void:
	_setup()
	var a := _map("a")
	_door(a, "ToB", Vector2i(10, 3), _path("b"), "from_a")
	_spawn(a, "from_b", Vector2i(9, 3))
	Maps.save(a, _path("a"))
	var b := _map("b")
	_door(b, "ToA", Vector2i(1, 3), _path("a"), "from_b")
	_spawn(b, "from_a", Vector2i(2, 3))
	Maps.save(b, _path("b"))
	var before := [FileAccess.get_file_as_string(_path("a")), FileAccess.get_file_as_string(_path("b"))]
	t.eq(_plan(["a", "b"]), [] as Array[Dictionary])
	var result := _run(["a", "b"])
	t.eq(result, {"repairs": [], "skipped": [], "unfixable": []})
	t.eq([FileAccess.get_file_as_string(_path("a")), FileAccess.get_file_as_string(_path("b"))], before, "no file is written")
	_finish()

func test_a_map_with_no_free_floor_is_reported_and_not_written(t) -> void:
	_setup()
	Maps.save(_map("a"), _path("a"))
	Maps.save(_map("c", true), _path("c"))
	var before := FileAccess.get_file_as_string(_path("c"))
	var actions := _plan(["a", "c"])
	t.eq(_kinds(actions), ["unfixable:c"])
	t.ok(str(actions[0]["what"]).contains("no cell is free on both sides (tried E of a.tscn"), str(actions[0]["what"]))
	var result := _run(["a", "c"])
	t.eq(result["repairs"], [])
	t.eq(result["unfixable"].size(), 1)
	t.eq(result["unfixable"][0]["kind"], "unfixable")
	t.eq(FileAccess.get_file_as_string(_path("c")), before)
	t.eq(FileAccess.get_file_as_string(_path("a")).contains("a_door_c"), false, "the start map got no half of a pair")
	_finish()

# ---------------------------------------------------------------- the tool

func test_a_dry_run_writes_nothing_and_only_limits_what_is_written(t) -> void:
	_setup()
	var a := _map("a")
	_door(a, "ToB", Vector2i(10, 3), _path("b"), "from_a")
	Maps.save(a, _path("a"))
	Maps.save(_map("b"), _path("b"))
	var before := [FileAccess.get_file_as_string(_path("a")), FileAccess.get_file_as_string(_path("b"))]
	var dry := _run(["a", "b"], {}, true)
	t.eq(dry["repairs"].size(), 3, "it says what it would do")
	t.eq([FileAccess.get_file_as_string(_path("a")), FileAccess.get_file_as_string(_path("b"))], before)
	# only b may be written (a was edited by its owner): a's repair is listed, not done
	var only: Array[String] = [_path("b")]
	var limited := _run(["a", "b"], {}, false, true, only)
	t.eq(limited["repairs"].size(), 2)
	t.eq(limited["skipped"].size(), 1)
	t.eq(limited["skipped"][0]["map"], _path("a"))
	t.eq(FileAccess.get_file_as_string(_path("a")), before[0], "the edited map is not touched")
	t.ok(FileAccess.get_file_as_string(_path("b")) != before[1])
	t.eq(Repair.line({"kind": "spawn", "map": "res://game/maps/x.tscn", "what": "w"}), {"kind": "spawn", "map": "game/maps/x.tscn", "node": "", "what": "w"})
	_finish()

func test_a_repaired_map_keeps_what_it_had(t) -> void:
	_setup()
	var a := _map("a")
	_door(a, "ToB", Vector2i(10, 3), _path("b"), "from_a")
	Maps.save(a, _path("a"))
	var b := _map("b")
	Maps.entity(Maps.entities_of(b), "Chest", "b_chest_001")
	_spawn(b, "default", Vector2i(5, 5))
	Maps.save(b, _path("b"))
	_run(["a", "b"])
	var again := _instance(_path("b"))
	t.ok(again.get_node_or_null("YSorted/Entities/Chest") != null, "nothing the person placed is removed")
	t.eq((again.get_node("SpawnPoints/default") as Node2D).position, Vector2(5 * 16 + 8, 5 * 16 + 8), "or moved")
	t.eq(str(again.get_node("SpawnPoints/from_a").get("spawn_id")), "from_a")
	t.eq(str(again.get_node("Triggers/b_door_a").get("target_map")), _path("a"))
	t.eq((again.get_node("Ground") as TileMapLayer).get_used_cells().size(), SIZE.x * SIZE.y, "the tiles are as they were")
	_finish()

# ---------------------------------------------------------------- the dock's Fix

func test_the_docks_fix_is_one_undo_step_each(t) -> void:
	_setup()
	var a := _map("a")
	_door(a, "ToB", Vector2i(10, 3), _path("gone"), "from_a")
	_roots.append(a)
	var undo := UndoRedo.new()
	var spawns := a.get_node("SpawnPoints")
	var action := {"kind": "spawn", "map": _path("a"), "node": "SpawnPoints/from_b", "spawn_id": "from_b", "position": Vector2(40, 40), "facing": "left", "what": "w"}
	ValidatorPanel.do_fix(action, a, undo)
	t.eq(spawns.get_child_count(), 1)
	t.eq(spawns.get_child(0).owner, a, "it will be saved with the scene")
	t.ok(undo.undo())
	t.eq(spawns.get_child_count(), 0, "Ctrl+Z takes the spawn point away again")
	t.ok(undo.redo())
	t.eq(String(spawns.get_child(0).name), "from_b")
	var door := a.get_node("Triggers/ToB")
	ValidatorPanel.do_fix({"kind": "retarget", "map": _path("a"), "node": "Triggers/ToB", "target_map": _path("b"), "target_spawn": "from_a", "what": "w"}, a, undo)
	t.eq(str(door.get("target_map")), _path("b"))
	undo.undo()
	t.eq(str(door.get("target_map")), _path("gone"))
	ValidatorPanel.do_fix({"kind": "door", "map": _path("a"), "node": "Triggers/a_door_c", "name": "a_door_c", "position": Vector2(24, 24), "target_map": _path("c"), "target_spawn": "from_a", "what": "w"}, a, null)
	t.ok(a.get_node_or_null("Triggers/a_door_c/Shape") != null, "without an undo history it is done directly")
	ValidatorPanel.do_fix({"kind": "unfixable", "map": _path("a"), "node": "", "what": "w"}, a, undo)
	t.eq(a.get_node("Triggers").get_child_count(), 2, "an unfixable finding changes nothing")
	t.eq(ValidatorPanel.fixable_codes(), ["VAL-016", "VAL-017", "VAL-027", "VAL-028"])
	undo.free()
	_finish()
