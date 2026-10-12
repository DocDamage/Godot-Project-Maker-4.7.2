extends RefCounted
## M4 smoke scenario (runs after the M1 steps): enter the starter building, leave it again and
## bump into a decoration.

const JsonUtil := preload("../lib/json_util.gd")

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	var list: Array[Dictionary] = []
	list.append({"name": "enter_building", "fn": _enter_building, "timeout_s": 15.0})
	list.append({"name": "exit_building", "fn": _exit_building, "timeout_s": 15.0})
	list.append({"name": "decor_blocks", "fn": _decor_blocks, "timeout_s": 20.0})
	list.append({"name": "walk_to_field", "fn": _walk_to_field, "timeout_s": 30.0})
	list.append({"name": "return_from_field", "fn": _return_from_field, "timeout_s": 30.0})
	if _has_areas():  # a world of areas (T13.20)
		list.append({"name": "world_doors", "fn": _world_doors, "timeout_s": 60.0})
	return list

## True when the project has a stored plan of areas. The plan file of a farm without areas
## (T17.05) holds only its crops.
func _has_areas() -> bool:
	if not FileAccess.file_exists("res://rpggen/world_plan.json"):
		return false
	return not JsonUtil.to_array(JsonUtil.to_dict(JsonUtil.read("res://rpggen/world_plan.json")).get("areas", [])).is_empty()

func _router() -> RpgSceneRouter:
	return _tree().root.get_node_or_null("SceneRouter") as RpgSceneRouter

func _player() -> RpgActor:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as RpgActor if players.size() == 1 else null

## Waits (physics frames) until the router is idle and the current scene is `map_name`.
func _wait_for_map(map_name: String, max_frames: int) -> bool:
	var tree := _tree()
	for i in max_frames:
		await tree.physics_frame
		var router := _router()
		var scene := tree.current_scene
		if router != null and not router.is_busy() and scene != null and scene.name == map_name:
			return true
	return false

func _find_doors(node: Node, out: Array) -> void:
	if node is Area2D and node.get("target_map") != null:
		out.append(node)
	for child in node.get_children():
		_find_doors(child, out)

func _enter_building() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	if scene == null or scene.name != "StarterMap":
		return "not in the starter map"
	var doors: Array[Area2D] = []
	_find_doors(scene, doors)
	var entrance: Area2D = null
	for d in doors:
		if JsonUtil.to_str(d.get("target_map")).ends_with("interior_1.tscn"):
			entrance = d
	if entrance == null:
		print("[rpggen] INFO enter_building: the starter map has no building entrance, step passes")
		return ""
	var p := _player()
	if p == null:
		return "no player"
	var tile := 16.0
	var ground := scene.get_node_or_null("Ground") as TileMapLayer
	if ground != null and ground.tile_set != null:
		tile = float(ground.tile_set.tile_size.y)
	p.global_position = entrance.global_position + Vector2(0, tile)
	await tree.physics_frame
	Input.action_press("move_up")
	var arrived := await _wait_for_map("Interior1", 240)
	Input.action_release("move_up")
	return "" if arrived else "walking up into the entrance did not open interior_1"

func _exit_building() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	if scene == null or scene.name != "Interior1":
		print("[rpggen] INFO exit_building: not inside the building, step passes")
		return ""
	var p := _player()
	if p == null:
		return "no player in the interior"
	# let go as soon as the door takes over: a player still walking while the starter map fades
	# in drifts from the spawn, by more than the tolerance on a slow machine
	Input.action_press("move_down")
	for i in 240:
		await tree.physics_frame
		if tree.current_scene != scene or _router().is_busy():
			break
	Input.action_release("move_down")
	var arrived := await _wait_for_map("StarterMap", 240)
	if not arrived:
		return "walking down to the exit did not return to the starter map"
	p = _player()
	var spawns: Array[Node2D] = []
	for node in tree.get_nodes_in_group("spawn_points"):
		if JsonUtil.to_str(node.get("spawn_id")).ends_with("_exit"):
			spawns.append(node)
	if spawns.is_empty() or p == null:
		return "the starter map has no building exit spawn"
	var dist := p.global_position.distance_to(spawns[0].global_position)
	return "" if dist <= 16.0 else "player is %.1f px from the exit spawn" % dist

## The door node called `door_name` below `scene`, or null.
func _door_named(scene: Node, door_name: String) -> Area2D:
	return scene.find_child(door_name, true, false) as Area2D

func _tile_px(scene: Node) -> float:
	var ground := scene.get_node_or_null("Ground") as TileMapLayer
	return float(ground.tile_set.tile_size.x) if ground != null and ground.tile_set != null else 16.0

## Stands the player `tiles` tiles from `door` on the `side` (-1 west, +1 east) and walks toward it
## until the map changes (at most `frames` physics frames).
func _walk_through(door: Area2D, side: int, action: String, frames: int) -> void:
	var tree := _tree()
	var p := _player()
	var tile := _tile_px(tree.current_scene)
	p.global_position = door.global_position + Vector2(side * 1.5 * tile, 0.0)
	await tree.physics_frame
	var scene_before := tree.current_scene
	Input.action_press(action)
	for i in frames:
		await tree.physics_frame
		if tree.current_scene != scene_before or _router().is_busy():
			break
	Input.action_release(action)

## The east exit of the starter map leads to the field, and the game knows where the player is.
func _walk_to_field() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	if scene == null or scene.name != "StarterMap":
		return "not in the starter map"
	var door := _door_named(scene, "starter_map_east_exit")
	if door == null:
		print("[rpggen] INFO walk_to_field: this starter map has no east exit, step passes")
		return ""
	await _walk_through(door, -1, "move_right", 180)
	if not await _wait_for_map("Field1", 600):
		return "walking into the east exit did not open the field map"
	var state := tree.root.get_node_or_null("GameState") as RpgGameState
	if state != null and not JsonUtil.to_str(state.current_map).ends_with("field_1.tscn"):
		return "GameState.current_map is %s, not the field map" % JsonUtil.to_str(state.current_map)
	var spawn := tree.current_scene.get_node_or_null("SpawnPoints/west_entry") as Node2D
	var p := _player()
	if spawn == null or p == null or p.global_position.distance_to(spawn.global_position) > 48.0:
		return "the player did not arrive at the west entry of the field"
	return ""

## A world of areas (T13.20): the village's first door leads to its area, the player arrives at
## that area's spawn point, and the door back leads to the village again.
func _world_doors() -> String:
	var tree := _tree()
	var plan := JsonUtil.to_dict(JsonUtil.read("res://rpggen/world_plan.json")) if FileAccess.file_exists("res://rpggen/world_plan.json") else {}
	var village := {}
	for raw: Variant in JsonUtil.to_array(plan.get("areas", [])):
		if JsonUtil.to_str(JsonUtil.to_dict(raw).get("id", "")) == "starter_map":
			village = JsonUtil.to_dict(raw)
	var doors := JsonUtil.to_array(village.get("doors", []))
	if doors.is_empty():
		return "the world plan gives the village no door"
	var scene := tree.current_scene
	if scene == null or scene.name != "StarterMap":
		return "not in the starter map"
	var origin := _player().global_position
	var out := JsonUtil.to_dict(doors[0])
	var area_id := JsonUtil.to_str(out.get("to", ""))
	var door := _door_named(scene, JsonUtil.to_str(out.get("id", "")))
	if door == null:
		# a starter map from before the areas were asked for keeps its doors as they are
		print("[rpggen] INFO world_doors: the starter map is older than the world (no door %s): nothing to walk through" % JsonUtil.to_str(out.get("id", "")))
		return ""
	var steps := {"E": [-1, "move_right"], "W": [1, "move_left"], "N": [0, "move_up"], "S": [0, "move_down"]}
	var going: Array = steps[JsonUtil.to_str(out.get("edge", "E"))]
	await _walk_into(door, JsonUtil.to_str(out.get("edge", "E")), JsonUtil.to_str(going[1]))
	if not await _wait_for_map(area_id.to_pascal_case(), 600):
		return "walking into %s did not open the area %s" % [door.name, area_id]
	var p := _player()
	var arrive := tree.current_scene.get_node_or_null("SpawnPoints/" + JsonUtil.to_str(out.get("to_spawn", ""))) as Node2D
	if arrive == null or p == null or p.global_position.distance_to(arrive.global_position) > 48.0:
		return "the player did not arrive at %s of the area %s" % [JsonUtil.to_str(out.get("to_spawn", "")), area_id]
	var back: Area2D = null
	var back_edge := "W"
	for raw: Variant in JsonUtil.to_array(plan.get("areas", [])):
		var area := JsonUtil.to_dict(raw)
		if JsonUtil.to_str(area.get("id", "")) != area_id:
			continue
		for raw_door: Variant in JsonUtil.to_array(area.get("doors", [])):
			var way := JsonUtil.to_dict(raw_door)
			if JsonUtil.to_str(way.get("to", "")) == "starter_map":
				back = _door_named(tree.current_scene, JsonUtil.to_str(way.get("id", "")))
				back_edge = JsonUtil.to_str(way.get("edge", "W"))
	if back == null:
		return "the area %s has no door back to the village" % area_id
	var coming: Array = steps[back_edge]
	await _walk_into(back, back_edge, JsonUtil.to_str(coming[1]))
	if not await _wait_for_map("StarterMap", 600):
		return "the door of %s did not bring the player back to the village" % area_id
	var home := tree.current_scene.get_node_or_null("SpawnPoints/from_" + area_id) as Node2D
	p = _player()
	if home == null or p == null or p.global_position.distance_to(home.global_position) > 48.0:
		return "the player did not arrive at from_%s of the village" % area_id
	p.global_position = origin  # the later steps start where the earlier ones left the player
	await tree.physics_frame
	await tree.physics_frame
	print("[rpggen] INFO world_doors: went to %s and back" % area_id)
	return ""

## Stands the player on the floor in front of a door in the wall on `edge` and walks into it.
func _walk_into(door: Area2D, edge: String, action: String) -> void:
	var tree := _tree()
	var p := _player()
	var tile := _tile_px(tree.current_scene)
	var inward := {"E": Vector2(-1, 0), "W": Vector2(1, 0), "N": Vector2(0, 1), "S": Vector2(0, -1)}
	var step: Vector2 = inward[edge]
	p.global_position = door.global_position + step * 1.5 * tile
	await tree.physics_frame
	var scene_before := tree.current_scene
	Input.action_press(action)
	for i in 180:
		await tree.physics_frame
		if tree.current_scene != scene_before or _router().is_busy():
			break
	Input.action_release(action)

func _return_from_field() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	if scene == null or scene.name != "Field1":
		print("[rpggen] INFO return_from_field: not in the field map, step passes")
		return ""
	var door := _door_named(scene, "field_1_west_exit")
	if door == null:
		return "the field map has no west exit"
	await _walk_through(door, 1, "move_left", 180)
	if not await _wait_for_map("StarterMap", 600):
		return "walking into the west exit did not bring the player back to the starter map"
	var state := tree.root.get_node_or_null("GameState") as RpgGameState
	if state != null and not JsonUtil.to_str(state.current_map).ends_with("starter_map.tscn"):
		return "GameState.current_map is %s, not the starter map" % JsonUtil.to_str(state.current_map)
	var spawn := tree.current_scene.get_node_or_null("SpawnPoints/east_entry") as Node2D
	var p := _player()
	if spawn == null or p == null or p.global_position.distance_to(spawn.global_position) > 48.0:
		return "the player did not arrive at the east entry of the starter map"
	return ""

func _decor_blocks() -> String:
	var tree := _tree()
	var scene := tree.current_scene
	var p := _player()
	if scene == null or scene.name != "StarterMap" or p == null:
		return "not in the starter map"
	var obstacle: StaticBody2D = null
	for node in scene.find_children("Decor*", "StaticBody2D", true, false):
		if node.get_node_or_null("Footprint") != null:
			obstacle = node
			break
	if obstacle == null:
		print("[rpggen] INFO decor_blocks: no obstacle decoration in the map, step passes")
		return ""
	var poly := (obstacle.get_node("Footprint") as CollisionPolygon2D).polygon
	var left := 1e9
	var top := 1e9
	var bottom := -1e9
	for pt in poly:
		left = minf(left, pt.x)
		top = minf(top, pt.y)
		bottom = maxf(bottom, pt.y)
	var middle_y := obstacle.global_position.y + (top + bottom) / 2.0
	var edge_x := obstacle.global_position.x + left
	p.global_position = Vector2(edge_x - 24.0, middle_y + 3.0)
	await tree.physics_frame
	Input.action_press("move_right")
	for i in 120:
		await tree.physics_frame
	Input.action_release("move_right")
	return "" if p.global_position.x < edge_x else "player walked through the decoration (x=%.1f, edge at %.1f)" % [p.global_position.x, edge_x]
