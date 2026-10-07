extends SceneTree
# Probe: APIs used by the action-RPG archetype (T9.06 navigation layer, raycast without a physics step).

func _initialize() -> void:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	print("PROBE nav_layers_count_start: ", ts.get_navigation_layers_count())
	ts.add_navigation_layer()
	print("PROBE nav_layers_count_after_add: ", ts.get_navigation_layers_count())
	var img := Image.create(16, 16, false, Image.FORMAT_RGBA8)
	img.fill(Color.RED)
	var src := TileSetAtlasSource.new()
	ts.add_source(src, 0)
	src.texture = ImageTexture.create_from_image(img)
	src.texture_region_size = Vector2i(16, 16)
	src.create_tile(Vector2i(0, 0))
	var td := src.get_tile_data(Vector2i(0, 0), 0)
	print("PROBE nav_polygon_default: ", td.get_navigation_polygon(0))
	var poly := NavigationPolygon.new()
	poly.vertices = PackedVector2Array([Vector2(-8, -8), Vector2(8, -8), Vector2(8, 8), Vector2(-8, 8)])
	poly.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	td.set_navigation_polygon(0, poly)
	print("PROBE nav_polygon_set: ", td.get_navigation_polygon(0) != null, " polys=", td.get_navigation_polygon(0).get_polygon_count())
	# Raycast right after adding a body (no physics step).
	var wall := StaticBody2D.new()
	wall.collision_layer = 1
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(8, 64)
	shape.shape = rect
	wall.add_child(shape)
	wall.position = Vector2(50, 0)
	root.add_child(wall)
	var body := Node2D.new()
	root.add_child(body)
	var ray := RayCast2D.new()
	ray.collision_mask = 1
	body.add_child(ray)
	ray.target_position = Vector2(100, 0)
	ray.force_raycast_update()
	print("PROBE raycast_hits_wall_without_step: ", ray.is_colliding())
	ray.target_position = Vector2(30, 0)
	ray.force_raycast_update()
	print("PROBE raycast_short_clear: ", not ray.is_colliding())
	var agent := NavigationAgent2D.new()
	agent.process_mode = Node.PROCESS_MODE_DISABLED
	print("PROBE nav_agent_ok: ", agent != null)
	print("PROBE inputmap_has_attack: ", InputMap.has_action("attack"))
	quit(0)
