extends SceneTree
# Probe: a FULL collision polygon (tile-centered coordinates) on a painted tile blocks a point
# query at the tile's top-left + 1px. Needs physics frames, so it runs from _process.

var _frames: int = 0
var _layer: TileMapLayer

func _initialize() -> void:
	var img := Image.create(16, 16, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 0, 0, 1))
	var tex := ImageTexture.create_from_image(img)
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	ts.add_physics_layer()
	ts.set_physics_layer_collision_layer(0, 1)
	var src := TileSetAtlasSource.new()
	ts.add_source(src, 0)
	src.texture = tex
	src.texture_region_size = Vector2i(16, 16)
	src.create_tile(Vector2i(0, 0))
	var td := src.get_tile_data(Vector2i(0, 0), 0)
	var pts := PackedVector2Array([Vector2(0, 0), Vector2(16, 0), Vector2(16, 16), Vector2(0, 16)])
	var centered := PackedVector2Array()
	for p in pts:
		centered.append(p - Vector2(8, 8))
	td.add_collision_polygon(0)
	td.set_collision_polygon_points(0, 0, centered)
	_layer = TileMapLayer.new()
	_layer.tile_set = ts
	_layer.set_cell(Vector2i(2, 3), 0, Vector2i(0, 0), 0)
	root.add_child(_layer)

func _physics_process(_delta: float) -> bool:
	_frames += 1
	if _frames < 3:
		return false
	var space := _layer.get_world_2d().direct_space_state
	var q := PhysicsPointQueryParameters2D.new()
	q.collide_with_bodies = true
	q.collision_mask = 1
	q.position = Vector2(2 * 16 + 1, 3 * 16 + 1)
	var hit := space.intersect_point(q, 4)
	q.position = Vector2(0 * 16 + 1, 0 * 16 + 1)
	var miss := space.intersect_point(q, 4)
	print("PROBE tile_collision: hit_on_tile=", hit.size(), " hit_elsewhere=", miss.size())
	quit(0)
	return true
