extends Node
## Test only (T17.33): a picture of the level the level probe made. Run in a window (a picture
## needs one) as the scene res://rpggen/level_shot.tscn, so the runtime's autoloads are there for
## the scenes placed in it:
##
##   godot --path <project> res://rpggen/level_shot.tscn -- --level=<res path> --out=<png>
##
## The level is loaded, a camera of its own is put over the used cells of its Ground layer (and
## what was placed), zoomed so all of it fits, the HUD of anything placed is hidden, and the
## screen is saved. The game is not played: an assets-only project has none.

func _arg(arg_name: String, fallback: String) -> String:
	var prefix := "--%s=" % arg_name
	for a in OS.get_cmdline_user_args():
		if String(a).begins_with(prefix):
			return String(a).trim_prefix(prefix)
	return fallback

func _ready() -> void:
	_shoot.call_deferred()

func _shoot() -> void:
	var tree := get_tree()
	var packed := load(_arg("level", "")) as PackedScene
	if packed == null:
		print("[level] no level")
		tree.quit(1)
		return
	var level := packed.instantiate()
	add_child(level)
	for i in 30:
		await tree.process_frame
	var ground := level.get_node_or_null("Ground") as TileMapLayer
	var lo := Vector2(INF, INF)
	var hi := Vector2(-INF, -INF)
	if ground != null and ground.tile_set != null:
		var rect := ground.get_used_rect()
		for cell: Vector2i in [rect.position, Vector2i(rect.end.x - 1, rect.position.y), rect.end - Vector2i.ONE, Vector2i(rect.position.x, rect.end.y - 1)]:
			var at := ground.to_global(ground.map_to_local(cell))
			lo = lo.min(at)
			hi = hi.max(at)
		lo -= Vector2(ground.tile_set.tile_size)
		hi += Vector2(ground.tile_set.tile_size)
	for node in level.find_children("*", "Node2D", true, false):
		if node.get_parent() != null and String(node.get_parent().name) == "Entities":
			lo = lo.min((node as Node2D).global_position - Vector2(48, 64))
			hi = hi.max((node as Node2D).global_position + Vector2(48, 16))
	if not is_finite(lo.x):
		lo = Vector2.ZERO
		hi = Vector2(640, 360)
	for node in tree.root.find_children("*", "CanvasLayer", true, false):
		(node as CanvasLayer).visible = false
	var screen := tree.root.get_visible_rect().size
	var fit := minf(screen.x / maxf(1.0, hi.x - lo.x), screen.y / maxf(1.0, hi.y - lo.y))
	var camera := Camera2D.new()
	camera.zoom = Vector2(fit, fit)
	add_child(camera)
	camera.global_position = (lo + hi) / 2.0
	camera.make_current()
	for i in 10:
		await tree.process_frame
	await RenderingServer.frame_post_draw
	var image := tree.root.get_texture().get_image()
	var out := _arg("out", "user://level.png")
	print("[level] saved %s: %d" % [out, image.save_png(out)])
	tree.quit(0)
