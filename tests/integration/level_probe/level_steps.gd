extends RefCounted
## Test only (T17.33): plays the level the level probe made. A smoke steps script (copied into the
## project as res://rpggen/level_steps.gd and run with --rpg-smoke-steps): the game boots, the
## router takes the player to --rpg-level=<map>, the player walks and the screen is saved twice
## (--rpg-level-out=<prefix>: <prefix>_play.png as played, <prefix>_whole.png the whole level).
## Run with a window: the pictures need one.

func _arg(arg_name: String, fallback: String) -> String:
	var prefix := "--rpg-%s=" % arg_name
	for a in OS.get_cmdline_user_args():
		if String(a).begins_with(prefix):
			return String(a).trim_prefix(prefix)
	return fallback

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func steps() -> Array[Dictionary]:
	return [
		{"name": "boot", "fn": _boot, "timeout_s": 30.0},
		{"name": "level_opens", "fn": _opens, "timeout_s": 30.0},
		{"name": "player_walks", "fn": _walks, "timeout_s": 20.0},
		{"name": "whole_level", "fn": _whole, "timeout_s": 20.0},
	]

func _boot() -> String:
	var tree := _tree()
	while tree.current_scene == null or tree.current_scene.get("map_id") == null:
		await tree.process_frame
	return ""

func _opens() -> String:
	var tree := _tree()
	var level := _arg("level", "")
	var router := tree.root.get_node_or_null("SceneRouter")
	if router == null:
		return "no SceneRouter"
	while bool(router.call("is_busy")):
		await tree.process_frame
	router.call("go_to", level, &"default")
	var waited := 0
	while (tree.current_scene == null or tree.current_scene.scene_file_path != level) and waited < 1200:
		await tree.process_frame
		waited += 1
	if tree.current_scene == null or tree.current_scene.scene_file_path != level:
		return "the level did not open"
	while bool(router.call("is_busy")):
		await tree.process_frame
	for i in 60:
		await tree.process_frame
	return ""

func _player() -> Node2D:
	var players := _tree().get_nodes_in_group("player")
	return players[0] as Node2D if players.size() == 1 else null

func _walks() -> String:
	var tree := _tree()
	var p := _player()
	if p == null:
		return "no player"
	var x0 := p.global_position.x
	Input.action_press("move_right")
	for i in 40:
		await tree.physics_frame
	Input.action_release("move_right")
	for i in 20:
		await tree.process_frame
	await _save(_arg("level-out", "user://level") + "_play.png")
	var dx := p.global_position.x - x0
	return "" if dx >= 8.0 else "the player moved only %.1f px" % dx

func _whole() -> String:
	var tree := _tree()
	var layer := tree.current_scene.get_node_or_null("Ground") as TileMapLayer
	if layer == null:
		return "no ground"
	var rect := layer.get_used_rect()
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	for cell: Vector2i in [rect.position, Vector2i(rect.end.x - 1, rect.position.y), rect.end - Vector2i.ONE, Vector2i(rect.position.x, rect.end.y - 1)]:
		var at := layer.to_global(layer.map_to_local(cell))
		lo = lo.min(at)
		hi = hi.max(at)
	var tile := Vector2(layer.tile_set.tile_size)
	lo -= tile
	hi += tile
	var screen := tree.root.get_visible_rect().size
	var fit := minf(screen.x / maxf(1.0, hi.x - lo.x), screen.y / maxf(1.0, hi.y - lo.y))
	for node in tree.root.find_children("*", "CanvasLayer", true, false):
		(node as CanvasLayer).visible = false
	var camera := Camera2D.new()
	camera.zoom = Vector2(fit, fit)
	tree.current_scene.add_child(camera)
	camera.global_position = (lo + hi) / 2.0
	camera.make_current()
	for i in 10:
		await tree.process_frame
	await _save(_arg("level-out", "user://level") + "_whole.png")
	return ""

func _save(path: String) -> void:
	await RenderingServer.frame_post_draw
	var image := _tree().root.get_texture().get_image()
	print("[level] saved %s: %d" % [path, image.save_png(path)])
