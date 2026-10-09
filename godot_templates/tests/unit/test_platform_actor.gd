extends RefCounted
## T14.03: the platform actor and the metroidvania's player in a small room made in code: jump
## height, coyote time, the jump buffer, one-way platforms, ladders, hazards, the attack and the
## side-view animations.

const Fixtures := preload("../lib/fixtures.gd")
const SideTileset := preload("res://builder/lib/side_tileset.gd")
const PlayerRecipe := preload("res://builder/recipes/metroidvania/player_recipe.gd")

const TILE := 16
const FRAME := Vector2i(24, 24)
const GROUND := Vector2i(0, 0)
const ONE_WAY := Vector2i(1, 0)
const LADDER := Vector2i(2, 0)
const HAZARD := Vector2i(3, 0)
const BREAKABLE := Vector2i(4, 0)
const FLOOR_Y := 10  # the row of the floor: its top is at y = 160

# ---------------------------------------------------------------- the room

## A TileSet of five tiles: ground, a one-way plank, a ladder, spikes and a block that breaks.
static func tileset() -> TileSet:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(TILE, TILE)
	ts.add_physics_layer()
	ts.set_physics_layer_collision_layer(0, 1)
	ts.set_physics_layer_collision_mask(0, 0)
	SideTileset.ensure_layers(ts)
	var img := Image.create(TILE * 5, TILE, false, Image.FORMAT_RGBA8)
	img.fill(Color.GRAY)
	var src := TileSetAtlasSource.new()
	ts.add_source(src, 0)
	src.texture = ImageTexture.create_from_image(img)
	src.texture_region_size = Vector2i(TILE, TILE)
	var cell := Vector2i(TILE, TILE)
	var specs := {
		GROUND: [{"profile": "FULL"}, {}],
		ONE_WAY: [{"profile": "ONE_WAY"}, {}],
		LADDER: [{"profile": "LADDER"}, {}],
		HAZARD: [{"profile": "NONE"}, {"custom": {"hazard": true}}],
		BREAKABLE: [{"profile": "FULL"}, {"custom": {"breakable": true}}],
	}
	for coords: Vector2i in specs:
		src.create_tile(coords)
		var td := src.get_tile_data(coords, 0)
		var collision: Dictionary = specs[coords][0]
		if collision["profile"] == "FULL":
			td.add_collision_polygon(0)
			td.set_collision_polygon_points(0, 0, PackedVector2Array([Vector2(-8, -8), Vector2(8, -8), Vector2(8, 8), Vector2(-8, 8)]))
		SideTileset.configure_tile(td, {"role": "GROUND"}, specs[coords][1], collision, cell)
	return ts

class Room:
	var root: Node2D
	var layer: TileMapLayer
	var player: RpgPlatformPlayer
	var jumps := 0
	var landings := 0
	var returns := 0

	func fill(tile: Vector2i, from: Vector2i, to: Vector2i) -> void:
		for y in range(from.y, to.y + 1):
			for x in range(from.x, to.x + 1):
				layer.set_cell(Vector2i(x, y), 0, tile)

	## Puts the player's feet on the floor in the middle of column `x`.
	func stand_at(x: float, row: int = FLOOR_Y) -> void:
		player.position = Vector2((x + 0.5) * TILE, row * TILE)
		player.velocity = Vector2.ZERO
		player.move_x = 0.0
		player.move_y = 0.0
		player.jump_held = false

	func frames(count: int) -> void:
		for i in count:
			await root.get_tree().physics_frame

	## Waits until the player stands (at most two seconds).
	func settle() -> void:
		for i in 120:
			await root.get_tree().physics_frame
			if player.is_on_floor():
				return

	func close() -> void:
		root.get_parent().remove_child(root)
		root.free()

## A room with a floor from column 0 to `floor_to`, the player standing at column `x`.
func _room(floor_to: int = 30, x: float = 3.0) -> Room:
	var tree := Fixtures.tree()
	await tree.process_frame
	var room := Room.new()
	room.root = Node2D.new()
	room.root.name = "TestRoom"
	room.layer = TileMapLayer.new()
	room.layer.name = "Ground"
	room.layer.tile_set = tileset()
	room.root.add_child(room.layer)
	room.fill(GROUND, Vector2i(0, FLOOR_Y), Vector2i(floor_to, FLOOR_Y))
	room.player = PlayerRecipe.build_player("Player", null, FRAME, Vector2i(12, 23), TILE) as RpgPlatformPlayer
	room.root.add_child(room.player)
	room.stand_at(x)
	tree.root.add_child(room.root)
	(room.player.component("PlatformInput") as RpgPlatformInput).enabled = false  # the test drives
	room.player.jumped.connect(func() -> void: room.jumps += 1)
	room.player.landed.connect(func(_speed: float) -> void: room.landings += 1)
	room.player.returned_to_safe_ground.connect(func() -> void: room.returns += 1)
	await room.settle()
	return room

func _state(hp: int = 10) -> RpgGameState:
	var state := Fixtures.install_state() as RpgGameState
	state.player_stats.max_hp = hp
	state.player_stats.hp = hp
	state.player_stats.attack = 5
	return state

# ---------------------------------------------------------------- the formulas

func test_gravity_and_jump_speed_follow_from_height_and_time(t) -> void:
	t.near(RpgPlatformMath.gravity(52.0, 0.38), 2.0 * 52.0 / (0.38 * 0.38), 0.01)
	t.near(RpgPlatformMath.jump_speed(52.0, 0.38), 2.0 * 52.0 / 0.38, 0.01)
	t.near(RpgPlatformMath.apex(RpgPlatformMath.jump_speed(52.0, 0.38), RpgPlatformMath.gravity(52.0, 0.38)), 52.0, 0.01)
	t.eq(RpgPlatformMath.gravity(52.0, 0.0), 0.0)
	t.eq(RpgPlatformMath.cell_of(Vector2(33.0, -1.0), 16.0), Vector2i(2, -1))

func test_a_full_jump_reaches_its_height_and_a_released_one_is_lower(t) -> void:
	var height := 3.25 * TILE
	for fps: float in [30.0, 60.0, 120.0]:
		var peak := RpgPlatformMath.simulate_jump(height, 0.38, 1.0 / fps)
		t.ok(absf(peak - height) <= height * 0.02, "%.0f fps: %.2f px of %.2f" % [fps, peak, height])
	var released := RpgPlatformMath.simulate_jump(height, 0.38, 1.0 / 60.0, 0.1)
	t.ok(released < height * 0.8 and released > height * 0.2, "released after 0.1 s: %.2f px" % released)
	var with_fall := RpgPlatformMath.simulate_jump(height, 0.38, 1.0 / 60.0, -1.0, 1.6, 360.0)
	t.near(with_fall, RpgPlatformMath.simulate_jump(height, 0.38, 1.0 / 60.0), 0.01, "falling faster does not change the peak")

# ---------------------------------------------------------------- jumping

## The highest point (px above the floor) the player reaches within `count` frames.
func _rise(room: Room, count: int) -> float:
	var floor_y := room.player.position.y
	var top := floor_y
	for i in count:
		await room.frames(1)
		top = minf(top, room.player.position.y)
	return floor_y - top

func test_the_actor_jumps_three_and_a_quarter_tiles(t) -> void:
	var room: Room = await _room()
	t.ok(room.player.is_on_floor(), "the player stands on the floor")
	room.player.press_jump()
	var rise: float = await _rise(room, 45)
	t.ok(absf(rise - 52.0) <= 52.0 * 0.02 + 0.5, "a full jump: %.2f px" % rise)
	t.eq(room.jumps, 1)
	await room.settle()
	t.ok(room.landings >= 1, "landed")
	room.player.press_jump()
	await room.frames(4)
	room.player.release_jump()
	var short: float = await _rise(room, 45)
	t.ok(short < 40.0 and short > 8.0, "released early: %.2f px" % short)
	room.close()

func test_a_high_jump_and_a_double_jump_need_their_abilities(t) -> void:
	var room: Room = await _room()
	room.player.press_jump()
	await room.frames(12)
	room.player.press_jump()  # in the air, without the ability: nothing
	await room.frames(2)
	t.eq(room.jumps, 1, "no second jump without double_jump")
	await room.settle()
	room.player.abilities_override = ["double_jump"]
	room.player.press_jump()
	await room.frames(12)
	room.player.press_jump()
	await room.frames(2)
	t.eq(room.jumps, 3, "a second jump in the air")
	room.player.press_jump()
	await room.frames(2)
	t.eq(room.jumps, 3, "once per airtime")
	await room.settle()
	room.player.abilities_override = ["high_jump"]
	room.player.press_jump()
	var rise: float = await _rise(room, 60)
	t.ok(absf(rise - 72.0) <= 72.0 * 0.03, "3.25 + 1.25 tiles: %.2f px" % rise)
	room.close()

## Runs right off the ledge and presses jump `late` frames after the floor is gone. True when the
## jump happened.
func _coyote(room: Room, late: int) -> bool:
	room.stand_at(9.0)
	await room.settle()
	var before := room.jumps
	room.player.move_x = 1.0
	for i in 120:
		await room.frames(1)
		if not room.player.is_on_floor():
			break
	await room.frames(late - 1)
	room.player.press_jump()
	await room.frames(2)
	room.player.move_x = 0.0
	return room.jumps > before

func test_coyote_time(t) -> void:
	var room: Room = await _room(10)
	room.fill(GROUND, Vector2i(0, 30), Vector2i(40, 30))  # a floor far below to land on
	t.ok(await _coyote(room, 5), "0.08 s after the ledge the jump still works")
	t.ok(not await _coyote(room, 9), "0.15 s after the ledge it is too late")
	room.close()

## Drops the player from 5 tiles up and presses jump `early` frames before it lands. True when it
## jumped on landing.
func _buffered(room: Room, early: int, frames_to_land: int) -> bool:
	room.stand_at(5.0, FLOOR_Y - 5)
	var before := room.jumps
	await room.frames(frames_to_land - early)
	room.player.press_jump()
	await room.frames(early + 3)
	var jumped := room.jumps > before
	await room.settle()
	return jumped

func test_the_jump_buffer(t) -> void:
	var room: Room = await _room()
	room.stand_at(5.0, FLOOR_Y - 5)
	var frames_to_land := 0
	for i in 120:
		await room.frames(1)
		frames_to_land += 1
		if room.player.is_on_floor():
			break
	t.ok(frames_to_land > 12 and frames_to_land < 60, "the drop takes %d frames" % frames_to_land)
	t.ok(await _buffered(room, 6, frames_to_land), "pressed 0.1 s before landing: jumps on landing")
	t.ok(not await _buffered(room, 10, frames_to_land), "pressed 0.17 s before landing: forgotten")
	room.close()

# ---------------------------------------------------------------- one-way platforms and ladders

func test_a_one_way_platform(t) -> void:
	var room: Room = await _room()
	room.fill(ONE_WAY, Vector2i(4, FLOOR_Y - 3), Vector2i(6, FLOOR_Y - 3))
	var top := float((FLOOR_Y - 3) * TILE)
	room.stand_at(5.0)
	await room.settle()
	t.ok(not room.player.standing_on_one_way(), "the floor is solid")
	room.player.press_jump()  # from below: through the platform
	await room.frames(20)
	t.ok(room.player.position.y < top, "passed through from below")
	await room.settle()
	t.near(room.player.position.y, top, 1.0, "and stands on it")
	t.ok(room.player.standing_on_one_way())
	room.player.move_y = 1.0
	room.player.press_jump()  # down + jump: through it
	await room.frames(4)
	room.player.move_y = 0.0
	room.player.release_jump()
	t.eq(room.jumps, 1, "dropping is not a jump")
	await room.frames(8)
	t.ok(room.player.position.y > top + 2.0, "dropped through")
	await room.settle()
	t.near(room.player.position.y, float(FLOOR_Y * TILE), 1.0, "back on the floor")
	await room.frames(14)
	t.ok(room.player.get_collision_mask_value(RpgSideTiles.ONE_WAY_LAYER), "the platform is solid again after 0.2 s")
	# on a solid floor down + jump is a jump
	room.stand_at(12.0)
	await room.settle()
	room.player.move_y = 1.0
	room.player.press_jump()
	await room.frames(3)
	t.eq(room.jumps, 2)
	room.close()

func test_a_ladder(t) -> void:
	var room: Room = await _room()
	room.fill(LADDER, Vector2i(8, FLOOR_Y - 6), Vector2i(8, FLOOR_Y - 1))
	room.stand_at(8.0)
	await room.settle()
	t.ok(room.player.ladder_here() and not room.player.on_ladder, "beside a ladder is not on it")
	room.player.move_y = -1.0
	await room.frames(30)
	t.ok(room.player.on_ladder, "up enters the ladder")
	var climbed := float(FLOOR_Y * TILE) - room.player.position.y
	t.near(climbed, 70.0 * 30.0 / 60.0, 3.0, "70 px/s: %.1f px in half a second" % climbed)
	room.player.move_y = 0.0
	var held := room.player.position.y
	await room.frames(20)
	t.near(room.player.position.y, held, 0.5, "no gravity on a ladder")
	room.player.press_jump()
	await room.frames(2)
	t.ok(not room.player.on_ladder and room.jumps == 1, "jump leaves the ladder")
	await room.settle()
	room.stand_at(8.0)
	await room.settle()
	room.player.move_y = -1.0
	await room.frames(20)
	room.player.move_y = 0.0
	room.player.move_x = 1.0
	await room.frames(20)
	t.ok(not room.player.on_ladder, "leaving the ladder's tiles ends the climb")
	room.close()

# ---------------------------------------------------------------- hazards

func test_a_hazard_hurts_and_returns_to_safe_ground(t) -> void:
	var state := _state(10)
	var room: Room = await _room()
	room.fill(HAZARD, Vector2i(12, FLOOR_Y - 1), Vector2i(12, FLOOR_Y - 1))
	room.stand_at(8.0)
	await room.settle()
	await room.frames(20)
	t.ok(room.player.has_safe_position, "a place stood on for 0.25 s is safe")
	var safe := room.player.safe_position
	room.player.move_x = 1.0
	for i in 90:
		await room.frames(1)
		if state.player_stats.hp < 10:
			break
	room.player.move_x = 0.0
	t.eq(state.player_stats.hp, 9, "a hazard costs one hit point")
	t.ok(room.player.hurtbox.is_invulnerable(), "0.6 s of invulnerability")
	t.ok(room.player.safe_position.x < 11.0 * TILE, "the ground beside the spikes is not safe ground")
	await room.frames(40)
	t.eq(room.returns, 1, "back within a second")
	t.ok(room.player.position.distance_to(room.player.safe_position) < TILE * 1.5, "on the last safe ground")
	t.ok(room.player.safe_position.x >= safe.x, "the safe place only moved forward")
	await room.frames(30)
	t.eq(state.player_stats.hp, 9, "one hit, not one per frame")
	t.ok(room.player.controllable(), "and the player moves again")
	room.close()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the attack

## A target: stats, health and an enemy hurtbox, `dx` px beside the player.
func _target(room: Room, dx: float, hp: int = 20) -> Node2D:
	var target := Node2D.new()
	target.name = "Target"
	var components := Node.new()
	components.name = "Components"
	target.add_child(components)
	var stats_node := RpgStatsComponent.new()
	stats_node.name = "Stats"
	components.add_child(stats_node)
	var health := RpgHealth.new()
	health.name = "Health"
	target.add_child(health)
	var hurtbox := RpgHurtbox.new()
	hurtbox.name = "Hurtbox"
	hurtbox.team = &"enemy"
	hurtbox.collision_layer = 0
	hurtbox.collision_mask = 0
	hurtbox.set_collision_layer_value(10, true)
	hurtbox.monitoring = false
	var shape := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(10, 14)
	shape.shape = rect
	hurtbox.add_child(shape)
	hurtbox.position = Vector2(0, -8)
	target.add_child(hurtbox)
	target.position = room.player.position + Vector2(dx, 0)
	room.root.add_child(target)
	var stats := RpgStats.new()
	stats.max_hp = hp
	stats.hp = hp
	stats.defense = 0
	stats.extra = {"crit_chance": 0.0}
	stats_node.stats = stats
	return target

func _hp(target: Node2D) -> int:
	return (target.get_node("Components/Stats") as RpgStatsComponent).stats.hp

func test_the_attack_hits_on_the_facing_side_only(t) -> void:
	var state := _state()
	state.player_stats.extra = {"crit_chance": 0.0}
	var room: Room = await _room()
	var right := _target(room, 20.0)
	var left := _target(room, -20.0)
	await room.frames(2)
	t.eq(room.player.facing, 1)
	t.ok(room.player.press_attack(), "the swing starts")
	t.ok(not room.player.press_attack(), "not twice at once")
	await room.frames(24)
	t.eq(_hp(right), 15, "the target on the facing side took the player's attack (5)")
	t.eq(_hp(left), 20, "the one behind did not")
	t.ok(not room.player.is_attacking() and not room.player.hitbox.active, "the swing is over")
	room.player.set_facing(-1)
	t.ok(room.player.press_attack())
	await room.frames(24)
	t.eq(_hp(left), 15)
	t.eq(_hp(right), 15)
	room.close()
	Fixtures.uninstall_state()

func test_break_blocks_needs_the_ability(t) -> void:
	var room: Room = await _room()
	room.fill(BREAKABLE, Vector2i(5, FLOOR_Y - 1), Vector2i(5, FLOOR_Y - 1))
	room.stand_at(3.6)
	await room.settle()
	room.player.press_attack()
	await room.frames(24)
	t.eq(room.layer.get_cell_source_id(Vector2i(5, FLOOR_Y - 1)), 0, "the block stands without the ability")
	room.player.abilities_override = ["break_blocks"]
	room.player.press_attack()
	await room.frames(24)
	t.eq(room.layer.get_cell_source_id(Vector2i(5, FLOOR_Y - 1)), -1, "the swing broke it")
	t.eq(room.layer.get_cell_source_id(Vector2i(5, FLOOR_Y)), 0, "the ground under it is not breakable")
	room.close()

# ---------------------------------------------------------------- animations

func _frames(names: Array, flipped: Array = []) -> SpriteFrames:
	var frames := SpriteFrames.new()
	for anim: String in names:
		frames.add_animation(anim)
		frames.add_frame(anim, PlaceholderTexture2D.new())
	for anim: String in flipped:
		frames.set_meta("flip_h_" + anim, true)
	return frames

func _driver(names: Array, flipped: Array = []) -> RpgAnimationDriver:
	var driver := RpgAnimationDriver.new()
	driver.sprite = AnimatedSprite2D.new()
	driver.sprite.sprite_frames = _frames(names, flipped)
	return driver

func _side(driver: RpgAnimationDriver, base: String, facing: int) -> Array:
	var anim := driver.play_side(base, facing)
	return [anim, driver.sprite.flip_h]

func test_play_side_picks_and_mirrors(t) -> void:
	var right := _driver(["run_right"])
	t.eq(_side(right, "run", 1), ["run_right", false])
	t.eq(_side(right, "run", -1), ["run_right", true], "mirrored for the left")
	var side := _driver(["jump_side"])
	t.eq(_side(side, "jump", 1), ["jump_side", false])
	t.eq(_side(side, "jump", -1), ["jump_side", true])
	var both := _driver(["idle_right", "idle_left"])
	t.eq(_side(both, "idle", -1), ["idle_left", false], "the pack's own left animation is not mirrored")
	t.eq(_side(both, "idle", 1), ["idle_right", false])
	var mirrored_left := _driver(["walk_right", "walk_left"], ["walk_left"])
	t.eq(_side(mirrored_left, "run", -1), ["walk_left", true], "a left the adapter made by mirroring keeps its flip")
	var bare := _driver(["fall"])
	t.eq(_side(bare, "fall", -1), ["fall", true], "no direction in the name")
	var assumed := _driver(["dash_down"])
	t.eq(_side(assumed, "dash", 1), ["dash_down", false], "a strip without a direction is stored as _down")
	var walk := _driver(["walk_down"])
	t.eq(_side(walk, "run", -1), ["walk_down", true], "run is walk in a pack that says walk")
	var only_left := _driver(["idle_left"])
	t.eq(_side(only_left, "idle", 1), ["idle_left", true], "only a left animation: mirrored for the right")
	t.eq(right.play_side("climb", 1), "", "no such animation")
	t.ok(right.has_side("run") and not right.has_side("climb"))
	for driver: RpgAnimationDriver in [right, side, both, mirrored_left, bare, assumed, walk, only_left]:
		driver.sprite.free()

func test_the_actor_picks_its_animation_and_falls_back_to_idle_in_the_air(t) -> void:
	var room: Room = await _room()
	var sprite := room.player.get_node("Visual") as AnimatedSprite2D
	sprite.sprite_frames = _frames(["idle_down", "walk_down", "jump_down", "fall_down"])
	await room.frames(2)
	t.eq(String(sprite.animation), "idle_down")
	room.player.move_x = -1.0
	await room.frames(3)
	t.eq(String(sprite.animation), "walk_down")
	t.ok(sprite.flip_h and room.player.facing == -1, "the sprite is flipped, the body is not")
	t.eq(room.player.scale, Vector2.ONE)
	room.player.move_x = 0.0
	room.player.press_jump()
	await room.frames(4)
	t.eq(String(sprite.animation), "jump_down")
	await room.frames(30)
	t.eq(String(sprite.animation), "fall_down")
	await room.settle()
	await room.frames(2)
	sprite.sprite_frames = _frames(["idle_down", "walk_down"])  # a top-down character: no jump, no fall
	room.player.press_jump()
	await room.frames(6)
	t.eq(String(sprite.animation), "idle_down", "the idle frame in the air (ASSET-030)")
	room.close()

func test_the_player_scene_has_its_parts_and_no_camera(t) -> void:
	var player := PlayerRecipe.build_player("Player", null, FRAME, Vector2i(12, 23), TILE)
	t.ok(player is RpgPlatformPlayer)
	for part: String in ["Visual", "Body", "Components/Stats", "Components/PlatformInput", "Health", "Hurtbox", "AttackHitbox", "Interaction"]:
		t.ok(player.get_node_or_null(part) != null, part)
	t.eq(player.find_children("*", "Camera2D", true, false).size(), 0, "the room owns the camera")
	t.ok(player.is_in_group("player"))
	t.ok(player.get_collision_layer_value(2) and player.get_collision_mask_value(1) and player.get_collision_mask_value(11))
	t.ok(not player.get_collision_mask_value(3), "enemies hurt by their hitbox, they do not block")
	t.eq(RpgRealtimeMath.actor_of(player.get_node("AttackHitbox")), player, "the shared hitbox finds its owner")
	player.free()
