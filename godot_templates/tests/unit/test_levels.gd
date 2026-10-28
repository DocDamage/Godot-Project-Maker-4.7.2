extends RefCounted
## T18.20: height on diamonds: the levels of a map with height layers, the walls of each level,
## a ramp walked up smoothly, the way over the levels, and what reaches what.

const Fixtures := preload("../lib/fixtures.gd")

const FOOT := Vector2i(32, 16)
## A hill of four blocks 16 px high, and a ramp before it rising towards it (n: to y - 1).
const HILL: Array[Vector2i] = [Vector2i(4, 3), Vector2i(5, 3), Vector2i(4, 4), Vector2i(5, 4)]
const RAMP := Vector2i(4, 5)

## The atlas: (0, 0) ground, (1, 0) a block, (2, 0) a ramp, (3, 0) a plain storey.
func _tile_set() -> TileSet:
	var ts := TileSet.new()
	ts.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	ts.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	ts.tile_size = FOOT
	ts.add_custom_data_layer()
	ts.set_custom_data_layer_name(0, "lift")
	ts.set_custom_data_layer_type(0, TYPE_INT)
	ts.add_custom_data_layer()
	ts.set_custom_data_layer_name(1, "stack")
	ts.set_custom_data_layer_type(1, TYPE_STRING)
	var picture := Image.create(FOOT.x * 4, FOOT.y, false, Image.FORMAT_RGBA8)
	picture.fill(Color.DARK_GREEN)
	var src := TileSetAtlasSource.new()
	src.texture = ImageTexture.create_from_image(picture)
	src.texture_region_size = FOOT
	ts.add_source(src, 0)
	var data := [[0, ""], [16, "block"], [16, "ramp:0:16:n"], [20, "storey"]]
	for i in 4:
		src.create_tile(Vector2i(i, 0))
		var td := src.get_tile_data(Vector2i(i, 0), 0)
		td.set_custom_data("lift", data[i][0])
		td.set_custom_data("stack", data[i][1])
	return ts

func _map(with_height: bool = true) -> Node2D:
	var map := Node2D.new()
	var ts := _tile_set()
	var ground := TileMapLayer.new()
	ground.name = "Ground"
	ground.tile_set = ts
	for y in 10:
		for x in 10:
			ground.set_cell(Vector2i(x, y), 0, Vector2i(0, 0))
	map.add_child(ground)
	if with_height:
		var layer := TileMapLayer.new()
		layer.name = "Height 0"
		layer.tile_set = ts
		layer.set_meta(RpgLevels.HEIGHT_META, 0)
		for cell in HILL:
			layer.set_cell(cell, 0, Vector2i(1, 0))
		layer.set_cell(RAMP, 0, Vector2i(2, 0))
		map.add_child(layer)
	Fixtures.tree().root.add_child(map)
	return map

func _drop(map: Node2D) -> void:
	map.get_parent().remove_child(map)
	map.free()

func test_a_map_without_height_layers_has_no_levels(t) -> void:
	var map := _map(false)
	t.eq(RpgLevels.ensure(map), null, "nothing changes for it")
	_drop(map)

func test_the_levels_and_what_can_be_walked_on_each(t) -> void:
	var map := _map()
	var levels := RpgLevels.ensure(map)
	t.ok(levels != null)
	t.eq(levels.levels, [0, 16] as Array[int])
	t.eq(levels.top_of(Vector2i(4, 4)), 16)
	t.eq(levels.top_of(Vector2i(1, 1)), 0)
	t.ok(levels.walkable(Vector2i(4, 4), 16) and not levels.walkable(Vector2i(4, 4), 0), "on the hill, not into it")
	t.ok(levels.walkable(RAMP, 0) and levels.walkable(RAMP, 16), "a ramp has both ends")
	t.eq(RpgLevels.ensure(map), levels, "made once")
	_drop(map)

func test_the_walls_of_each_level(t) -> void:
	var map := _map()
	var levels := RpgLevels.ensure(map)
	var below := levels.wall_cells(0)
	for cell in HILL:
		t.ok(below.has(cell), "the side of the hill blocks below it: %s" % cell)
	t.ok(not below.has(RAMP), "the ramp does not")
	var above := levels.wall_cells(16)
	for cell: Vector2i in [Vector2i(3, 3), Vector2i(6, 4), Vector2i(4, 2), Vector2i(5, 5), Vector2i(3, 5)]:
		t.ok(above.has(cell), "the edge of the hill blocks on it: %s" % cell)
	t.ok(not above.has(RAMP) and not above.has(Vector2i(4, 4)), "but not the ramp down, nor the hill")
	var body := levels.get_child(1) as StaticBody2D
	t.eq(body.collision_layer, 1 << (RpgLevels.FIRST_LAYER), "a layer of its own, the second level's")
	_drop(map)

func test_a_ramp_is_walked_up_smoothly(t) -> void:
	var map := _map()
	var levels := RpgLevels.ensure(map)
	var middle := RpgIso.cell_position(map, RAMP)
	t.near(levels.height_at(middle), 8.0, 0.5, "half way up in its middle")
	var up := RpgIso.cell_position(map, RAMP + Vector2i(0, -1)) - middle
	t.ok(levels.height_at(middle + up * 0.45) > 14.0, "near its top")
	t.ok(levels.height_at(middle - up * 0.45) < 2.0, "near its foot")
	var body := CharacterBody2D.new()
	var visual := Node2D.new()
	visual.name = "Visual"
	visual.position = Vector2(0, -4)
	body.add_child(visual)
	map.add_child(body)
	body.collision_mask = 1
	body.global_position = middle + up * 0.4
	levels.follow(body, visual)
	t.ok(visual.position.y < -4.0 - 12.0, "its picture is drawn higher")
	t.eq(body.collision_mask, 1 | (1 << RpgLevels.FIRST_LAYER), "the world and the wall of the upper level")
	body.global_position = RpgIso.cell_position(map, Vector2i(1, 1))
	levels.follow(body, visual)
	t.eq(visual.position.y, -4.0, "down on the ground again")
	t.eq(body.collision_mask, 1 | (1 << (RpgLevels.FIRST_LAYER - 1)))
	t.eq(RpgLevels.level_of(body), 0.0)
	_drop(map)

func test_the_way_up_goes_by_the_ramp(t) -> void:
	var map := _map()
	var levels := RpgLevels.ensure(map)
	var from := RpgIso.cell_position(map, Vector2i(1, 6))
	var to := RpgIso.cell_position(map, Vector2i(5, 3))
	var way := levels.path(from, to)
	t.ok(not way.is_empty(), "there is a way")
	var cells: Array[Vector2i] = []
	for point in way:
		cells.append(RpgIso.cell_at(map, point))
	t.ok(cells.has(RAMP), "up the ramp: %s" % [cells])
	t.eq(cells[cells.size() - 1], Vector2i(5, 3))
	for i in range(1, cells.size()):
		t.ok(not (HILL.has(cells[i]) and not HILL.has(cells[i - 1]) and cells[i - 1] != RAMP), "onto the hill only from the ramp")
	# on the ground around the hill: no step onto it
	var around := levels.path(from, RpgIso.cell_position(map, Vector2i(7, 3)))
	for point in around:
		t.ok(not HILL.has(RpgIso.cell_at(map, point)), "around it")
	_drop(map)

func test_what_reaches_what(t) -> void:
	t.ok(RpgLevels.reaches(0.0, 0.0), "on one level")
	t.ok(not RpgLevels.reaches(0.0, 16.0), "a shot from below does not reach up the hill")
	t.ok(RpgLevels.reaches(16.0, 0.0), "from above it falls")
	var a := Node.new()
	var b := Node.new()
	a.set_meta(&"rpg_level", 16.0)
	t.ok(not RpgLevels.same_level(a, b))
	b.set_meta(&"rpg_level", 14.0)
	t.ok(RpgLevels.same_level(a, b))
	a.free()
	b.free()

# ---------------------------------------------------------------- walked with the physics

## An actor of the map: a body on the player's layer that bumps into the world and the levels,
## with a picture to raise. Its levels are found by RpgActor itself, each physics step.
func _walker(map: Node2D, cell: Vector2i) -> RpgActor:
	var actor := RpgActor.new()
	actor.collision_layer = 1 << 1
	actor.collision_mask = 1
	var shape := CollisionShape2D.new()
	var circle := CircleShape2D.new()
	circle.radius = 3.0
	shape.shape = circle
	actor.add_child(shape)
	var visual := Node2D.new()
	visual.name = "Visual"
	actor.add_child(visual)
	actor.motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	map.add_child(actor)
	actor.global_position = RpgIso.cell_position(map, cell)
	return actor

## The cell an actor of the test's map stands on (the map is no RpgMapRoot: the actor's own
## map_cell asks the router's).
func _cell(map: Node2D, actor: Node2D) -> Vector2i:
	return RpgIso.cell_at(map, actor.global_position)

## Walks `actor` towards the middle of `cell` for `steps` physics steps (or until it is there).
func _walk(actor: RpgActor, map: Node2D, cell: Vector2i, steps: int = 240) -> void:
	var goal := RpgIso.cell_position(map, cell)
	for i in steps:
		var to := goal - actor.global_position
		if to.length() < 1.0:
			break
		actor.velocity = to.normalized() * 60.0
		actor.move_and_slide()
		await Fixtures.tree().physics_frame

func test_an_actor_walks_up_the_ramp_and_not_through_or_off_the_hill(t) -> void:
	var map := _map()
	RpgLevels.ensure(map)
	var actor := _walker(map, Vector2i(7, 4))
	await Fixtures.tree().physics_frame
	await Fixtures.tree().physics_frame
	# into the side of the hill from the east: it stops before it
	await _walk(actor, map, Vector2i(3, 4), 60)
	t.ok(not HILL.has(_cell(map, actor)), "the side of the hill blocks it (it stands at %s)" % _cell(map, actor))
	t.eq(RpgLevels.level_of(actor), 0.0, "and it is on the ground")
	# up the ramp onto the hill
	actor.global_position = RpgIso.cell_position(map, Vector2i(4, 7))
	await _walk(actor, map, RAMP)
	await _walk(actor, map, Vector2i(4, 4))
	t.eq(_cell(map, actor), Vector2i(4, 4), "up the ramp")
	t.near(RpgLevels.level_of(actor), 16.0, 0.5, "on the hill")
	t.near((actor.get_node("Visual") as Node2D).position.y, -16.0, 0.5, "drawn that much higher")
	# off its edge: it stays on top
	await _walk(actor, map, Vector2i(4, 0), 90)
	t.ok(HILL.has(_cell(map, actor)), "the edge holds it (it stands at %s, %s)" % [_cell(map, actor), actor.global_position])
	await _walk(actor, map, Vector2i(8, 4), 90)
	t.ok(HILL.has(_cell(map, actor)), "on every side but the ramp's (it stands at %s, %s)" % [_cell(map, actor), actor.global_position])
	# and down the ramp again
	await _walk(actor, map, Vector2i(4, 4))
	await _walk(actor, map, RAMP)
	await _walk(actor, map, Vector2i(4, 7))
	t.eq(_cell(map, actor), Vector2i(4, 7), "down the ramp")
	t.eq(RpgLevels.level_of(actor), 0.0)
	_drop(map)

func test_a_shot_from_below_does_not_hit_what_stands_on_the_hill(t) -> void:
	var map := _map()
	RpgLevels.ensure(map)
	var shooter := _walker(map, Vector2i(5, 8))
	var target := _walker(map, Vector2i(4, 4))
	var hurtbox := RpgHurtbox.new()
	hurtbox.team = &"enemy"
	hurtbox.collision_layer = 1 << 9
	target.add_child(hurtbox)
	await Fixtures.tree().physics_frame
	await Fixtures.tree().physics_frame
	t.near(RpgLevels.level_of(target), 16.0, 0.5, "the target stands on the hill")
	var shot := RpgProjectile.create(shooter, shooter.global_position, Vector2.UP, &"player", 120.0, 200.0)
	t.ok(shot.get_collision_mask_value(RpgLevels.FIRST_LAYER), "from the ground, the hill's side stops it")
	map.add_child(shot)
	t.eq(shot.targets().size(), 0, "nothing up there is in its reach")
	target.global_position = RpgIso.cell_position(map, Vector2i(7, 7))
	await Fixtures.tree().physics_frame
	t.eq(shot.targets().size(), 1, "on the ground it is")
	shot.free()
	_drop(map)
