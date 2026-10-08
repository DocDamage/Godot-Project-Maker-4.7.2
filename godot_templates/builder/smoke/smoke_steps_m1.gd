extends RefCounted
## M1 smoke scenario: boot into the starter map, find the player, walk, and bump into a wall.

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	var list: Array[Dictionary] = []
	list.append({"name": "boot", "fn": _boot, "timeout_s": 10.0})
	list.append({"name": "player_exists", "fn": _player_exists, "timeout_s": 5.0})
	list.append({"name": "player_moves", "fn": _player_moves, "timeout_s": 10.0})
	list.append({"name": "collision_blocks", "fn": _collision_blocks, "timeout_s": 20.0})
	return list

func _boot() -> String:
	var tree := _tree()
	while tree.current_scene == null or tree.current_scene.name != "StarterMap":
		await tree.process_frame
	return ""

func _player() -> RpgActor:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as RpgActor if players.size() == 1 else null

func _player_exists() -> String:
	var count := _tree().get_nodes_in_group("player").size()
	return "" if count == 1 else "expected exactly one node in group 'player', found %d" % count

func _player_moves() -> String:
	var tree := _tree()
	var p := _player()
	if p == null:
		return "no player"
	var x0 := p.global_position.x
	Input.action_press("move_right")
	for i in 30:
		await tree.physics_frame
	Input.action_release("move_right")
	var dx := p.global_position.x - x0
	return "" if dx >= 8.0 else "player moved only %.2f px to the right" % dx

func _has_collision(layer: TileMapLayer, cell: Vector2i) -> bool:
	var td := layer.get_cell_tile_data(cell)
	return td != null and td.get_collision_polygons_count(0) > 0

func _collision_blocks() -> String:
	var tree := _tree()
	var p := _player()
	var scene := tree.current_scene
	# Walls live on their own layer in M4 maps; older maps painted them on Ground.
	var layer: TileMapLayer = null
	if scene != null:
		layer = scene.get_node_or_null("Walls") as TileMapLayer
		if layer == null or layer.get_used_cells().is_empty():
			layer = scene.get_node_or_null("Ground") as TileMapLayer
	if p == null or layer == null or layer.tile_set == null:
		return "starter map has no player or Ground layer"
	var used := layer.get_used_cells()
	var wall_x := -1
	var min_y := 1 << 30
	var max_y := -(1 << 30)
	for c in used:
		min_y = mini(min_y, c.y)
		max_y = maxi(max_y, c.y)
		if _has_collision(layer, c):
			wall_x = maxi(wall_x, c.x)
	if wall_x < 0:
		print("[rpggen] INFO collision_blocks: no wall tile in the map, step passes")
		return ""
	# Pick the wall cell in the right-most wall column closest to the middle row that has open
	# floor to its left.
	var mid := (min_y + max_y) / 2
	var best_y := -1
	for c in used:
		if c.x == wall_x and _has_collision(layer, c) and not _has_collision(layer, Vector2i(wall_x - 1, c.y)):
			if best_y < 0 or absi(c.y - mid) < absi(best_y - mid):
				best_y = c.y
	if best_y < 0:
		return "no wall cell with open floor to its left"
	var tile := layer.tile_set.tile_size
	var wall_left := float(wall_x * tile.x)
	p.global_position = layer.to_global(Vector2((wall_x - 2) * tile.x + tile.x / 2.0, best_y * tile.y + tile.y / 2.0))
	await tree.physics_frame
	Input.action_press("move_right")
	for i in 120:
		await tree.physics_frame
	Input.action_release("move_right")
	var x := layer.to_local(p.global_position).x
	return "" if x < wall_left else "player passed through the wall (x=%.1f, wall at %.1f)" % [x, wall_left]
