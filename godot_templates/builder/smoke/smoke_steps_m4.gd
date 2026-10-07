extends RefCounted
## M4 smoke scenario (runs after the M1 steps): enter the starter building, leave it again and
## bump into a decoration.

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	var list: Array[Dictionary] = []
	list.append({"name": "enter_building", "fn": _enter_building, "timeout_s": 15.0})
	list.append({"name": "exit_building", "fn": _exit_building, "timeout_s": 15.0})
	list.append({"name": "decor_blocks", "fn": _decor_blocks, "timeout_s": 20.0})
	return list

func _router() -> Node:
	return _tree().root.get_node_or_null("SceneRouter")

func _player() -> Node2D:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as Node2D if players.size() == 1 else null

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
	var doors: Array = []
	_find_doors(scene, doors)
	var entrance: Area2D = null
	for d in doors:
		if String(d.get("target_map")).ends_with("interior_1.tscn"):
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
	Input.action_press("move_down")
	var arrived := await _wait_for_map("StarterMap", 240)
	Input.action_release("move_down")
	if not arrived:
		return "walking down to the exit did not return to the starter map"
	p = _player()
	var spawns: Array = []
	for node in tree.get_nodes_in_group("spawn_points"):
		if String(node.get("spawn_id")).ends_with("_exit"):
			spawns.append(node)
	if spawns.is_empty() or p == null:
		return "the starter map has no building exit spawn"
	var dist := p.global_position.distance_to((spawns[0] as Node2D).global_position)
	return "" if dist <= 16.0 else "player is %.1f px from the exit spawn" % dist

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
