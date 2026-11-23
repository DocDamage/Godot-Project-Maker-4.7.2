extends RefCounted

const Settings := preload("res://builder/lib/tile_hazards.gd")
const ActorBuild := preload("res://builder/lib/actor_build.gd")

func test_individual_tiles_damage_cooldown_disabled_layers_and_iso_coordinates(t) -> void:
	var layer := TileMapLayer.new()
	var ts := TileSet.new()
	ts.tile_size = Vector2i(32, 16)
	ts.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	ts.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	var image := Image.create(64, 32, false, Image.FORMAT_RGBA8)
	image.fill(Color.GREEN)
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(image)
	source.texture_region_size = Vector2i(32, 32)
	ts.add_source(source, 0)
	source.create_tile(Vector2i.ZERO)
	source.create_tile(Vector2i(1, 0))
	Settings.configure(ts, source.get_tile_data(Vector2i.ZERO, 0), {"custom": {"hazard": true, "hazard_damage": 7, "hazard_cooldown": 2.5}})
	Settings.configure(ts, source.get_tile_data(Vector2i(1, 0), 0), {"custom": {"hazard": false, "hazard_damage": 99}})
	layer.tile_set = ts
	layer.position = Vector2(100, 200)
	layer.set_cell(Vector2i(3, 2), 0, Vector2i.ZERO)
	layer.set_cell(Vector2i(4, 2), 0, Vector2i(1, 0))
	var layers: Array[TileMapLayer] = [layer]
	var points: Array[Vector2] = [layer.position + layer.map_to_local(Vector2i(3, 2))]
	var spec := RpgTileHazards.at(layers, points)
	t.eq(spec, {"damage": 7, "cooldown": 2.5})
	var timer := RpgTileHazards.new()
	t.ok(timer.consume(spec))
	t.ok(not timer.consume(spec), "the same frame cannot hit twice")
	timer.tick(2.49)
	t.ok(not timer.consume(spec))
	timer.tick(0.02)
	t.ok(timer.consume(spec))
	points[0] = layer.position + layer.map_to_local(Vector2i(4, 2))
	t.eq(RpgTileHazards.at(layers, points), {}, "the neighboring tile is harmless")
	layer.enabled = false
	points[0] = layer.position + layer.map_to_local(Vector2i(3, 2))
	t.eq(RpgTileHazards.at(layers, points), {})
	var map := RpgMapRoot.new()
	map.add_child(layer)
	layer.enabled = true
	var actor := ActorBuild.build("player", "Player", null, Vector2i(16, 24), Vector2i(8, 23), 16) as RpgActor
	map.add_child(actor)
	actor.position = points[0]
	var stats := actor.component("Stats") as RpgStatsComponent
	stats._ready()
	stats.stats.hp = 30
	actor._physics_process(0.01)
	t.eq(stats.stats.hp, 23, "the player actually takes this tile's damage")
	actor._physics_process(0.5)
	t.eq(stats.stats.hp, 23, "the timer blocks repeated physics-frame hits")
	actor._physics_process(2.0)
	t.eq(stats.stats.hp, 16)
	layer.enabled = false
	actor._physics_process(3.0)
	t.eq(stats.stats.hp, 16, "a disabled map layer cannot hurt the player")
	map.free()
