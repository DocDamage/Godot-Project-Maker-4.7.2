extends RefCounted
## T16.04: the ship of a shoot-em-up, its weapon, the bullet pool, the enemies' patterns, the
## bomb, and the scenes the recipes build, in both orientations.

const Fixtures := preload("../lib/fixtures.gd")
const ArcadeBuild := preload("res://builder/recipes/arcade/arcade_build.gd")
const StageRecipes := preload("res://builder/recipes/arcade/stage_recipes.gd")
const HudRecipe := preload("res://builder/recipes/arcade/hud_recipe.gd")
const ShmupBuild := preload("res://builder/recipes/shmup/shmup_build.gd")
const ShipRecipe := preload("res://builder/recipes/shmup/ship_recipe.gd")
const StageRecipe := preload("res://builder/recipes/shmup/stage_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")

const STEP := 0.125  # exact in binary
const VIEW := Vector2i(320, 180)
const PLAYER := RpgArcadeBulletPool.Team.PLAYER
const ENEMY := RpgArcadeBulletPool.Team.ENEMY

## Something a bullet can hit.
class Target extends Node2D:
	var hit_radius := 6.0
	var taken := 0

	func _ready() -> void:
		add_to_group(RpgArcadeBulletPool.TARGET_GROUP)

	func take_hit(damage: int) -> void:
		taken += damage

func _frames() -> SpriteFrames:
	var frames := SpriteFrames.new()
	frames.remove_animation(&"default")
	for anim: String in ["idle_down", "walk_left", "walk_right", "walk_up", "walk_down"]:
		frames.add_animation(anim)
		frames.add_frame(anim, PlaceholderTexture2D.new())
	return frames

func _ship(way: String) -> RpgShmupShip:
	var ship := ShipRecipe.build_ship(_frames(), Vector2i(24, 24), way, VIEW, 16, null) as RpgShmupShip
	ship.auto_advance = false
	(ship.get_node("Input") as RpgShmupShipInput).enabled = false
	return ship

func _pool() -> RpgArcadeBulletPool:
	var pool := RpgArcadeBulletPool.new()
	pool.auto_advance = false
	Fixtures.tree().root.add_child(pool)
	return pool

func _drop(node: Node) -> void:
	if node.get_parent() != null:
		node.get_parent().remove_child(node)
	node.free()

func _ctx(config: Dictionary = {}) -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"archetype": "shmup", "resolution": [VIEW.x, VIEW.y], "base_tile_size": 16, "seed": 7}
	ctx.config.merge(config, true)
	return ctx

# ---------------------------------------------------------------- the mode's geometry

func test_the_orientation_gives_the_axis_the_play_area_and_the_start(t) -> void:
	t.eq(RpgShmupMath.forward_of("vertical"), Vector2.UP)
	t.eq(RpgShmupMath.forward_of("horizontal"), Vector2.RIGHT)
	t.eq([RpgShmupMath.axis_of("vertical"), RpgShmupMath.axis_of("horizontal")], ["up", "right"])
	t.eq(RpgShmupMath.play_area(Vector2(320, 180), "vertical"), Rect2(-120, -90, 240, 180), "four wide for three high, in the middle")
	t.eq(RpgShmupMath.play_area(Vector2(200, 180), "vertical"), Rect2(-100, -90, 200, 180), "never wider than the screen")
	t.eq(RpgShmupMath.play_area(Vector2(320, 180), "horizontal"), Rect2(-160, -90, 320, 180), "the whole screen")
	t.eq(RpgShmupMath.start_offset(Vector2(320, 180), "vertical"), Vector2(0, 63), "near the bottom")
	t.eq(RpgShmupMath.start_offset(Vector2(320, 180), "horizontal"), Vector2(-112, 0), "near the left")

# ---------------------------------------------------------------- the ship

func test_the_ship_flies_and_stays_inside_the_play_area_in_both_orientations(t) -> void:
	for way: String in ["vertical", "horizontal"]:
		var ship := _ship(way)
		ship.area_center = Vector2(1000, 500)
		ship.position = ship.area_center + RpgShmupMath.start_offset(Vector2(VIEW), way)
		t.eq(ship.speed, 120.0, "seven and a half tiles a second")
		t.eq(ship.forward(), RpgShmupMath.forward_of(way))
		var start := ship.position
		ship.move = Vector2(1, 0)
		ship.advance(STEP)
		t.eq(ship.position, start + Vector2(15, 0), way)
		ship.move = Vector2(1, 1)
		ship.advance(STEP)
		t.near(ship.position.distance_to(start + Vector2(15, 0)), 15.0, 0.001, "a diagonal is no faster")
		ship.move = Vector2(0, -1)
		ship.focusing = true
		var before := ship.position
		ship.advance(STEP)
		t.eq(ship.position, before + Vector2(0, -7.5), "focus halves the speed")
		ship.focusing = false
		# every edge: the picture stays inside (12 px of a 24 px ship are kept free)
		var area := ship.play_area
		for push: Vector2 in [Vector2.LEFT, Vector2.UP, Vector2.RIGHT, Vector2.DOWN]:
			ship.move = push
			for i in 40:
				ship.advance(STEP)
		t.eq(ship.offset(), Vector2(area.end.x - 12, area.end.y - 12), way + ": stopped at the right and the bottom")
		ship.move = Vector2(-1, -1)
		for i in 60:
			ship.advance(STEP)
		t.eq(ship.offset(), area.position + Vector2(12, 12), way + ": and at the left and the top")
		# the play area moves with the screen, and the ship with it
		ship.move = Vector2.ZERO
		ship.area_center += RpgShmupMath.forward_of(way) * 100.0
		ship.advance(STEP)
		t.eq(ship.position, ship.area_center + area.position + Vector2(12, 12), way + ": carried along by the scrolling")
		ship.free()

func test_the_ship_is_one_point_to_hit_and_leans_when_its_sheet_has_the_frames(t) -> void:
	var ship := _ship("vertical")
	t.eq(ship.hit_radius, 1.0)
	t.eq(((ship.get_node("Body") as CollisionShape2D).shape as CircleShape2D).radius, 1.0)
	t.eq(ship.half_size, Vector2(12, 12))
	var visual := ship.get_node("Visual") as AnimatedSprite2D
	t.eq(visual.animation, &"idle_down", "level flight")
	t.eq(visual.rotation, 0.0)
	ship.move = Vector2(-1, 0)
	ship.advance(STEP)
	t.eq(visual.animation, &"walk_left")
	ship.move = Vector2(1, -1)
	ship.advance(STEP)
	t.eq(visual.animation, &"walk_right")
	ship.move = Vector2(0, -1)
	ship.advance(STEP)
	t.eq(visual.animation, &"idle_down", "up and down do not lean a ship that looks up")
	ship.free()
	var side := _ship("horizontal")
	t.near((side.get_node("Visual") as AnimatedSprite2D).rotation, PI * 0.5, 0.0001, "turned to the right")
	side.move = Vector2(0, -1)
	side.advance(STEP)
	t.eq((side.get_node("Visual") as AnimatedSprite2D).animation, &"walk_up", "a ship that looks right leans up and down")
	side.free()
	var hero := ShipRecipe.build_ship(_frames(), Vector2i(16, 24), "horizontal", VIEW, 16, null, false)
	t.eq((hero.get_node("Visual") as AnimatedSprite2D).rotation, 0.0, "a picture that is no ship is not laid on its side")
	hero.free()
	var plain := SpriteFrames.new()
	t.eq(RpgShmupShip.bank_animation(plain, -1.0, "vertical"), &"default", "a sheet without the frames keeps what it has")
	var named := SpriteFrames.new()
	named.add_animation(&"bank_left")
	t.eq(RpgShmupShip.bank_animation(named, -1.0, "vertical"), &"bank_left", "its own name comes first")

func test_a_hit_destroys_the_ship_and_it_returns_blinking_for_three_seconds(t) -> void:
	await Fixtures.tree().process_frame
	var holder := Node2D.new()
	Fixtures.tree().root.add_child(holder)
	var ship := _ship("vertical")
	holder.add_child(ship)
	ship.position = Vector2(0, 60)
	ship.advance(STEP)
	var weapon := ship.weapon()
	weapon.level = 3
	ship.bomb().count = 0
	var events: Array = []
	ship.destroyed.connect(func() -> void: events.append("destroyed"))
	ship.respawned.connect(func() -> void: events.append("respawned"))
	ship.move = Vector2(1, 0)
	ship.advance(STEP)
	t.ok(ship.hit(), "a hit destroys it")
	t.eq(events, ["destroyed"])
	t.ok(ship.dead and not (ship.get_node("Visual") as CanvasItem).visible)
	t.eq(weapon.level, 1, "the weapon is back at its first level")
	t.ok(not ship.hit(), "a destroyed ship is not hit again")
	var at := ship.position
	ship.advance(STEP)
	t.eq(ship.position, at, "and does not fly")
	ship.respawn()
	t.eq(events, ["destroyed", "respawned"])
	t.eq(ship.position, Vector2(0, 60), "back where the stage began")
	t.eq(ship.bomb().count, 3, "with the starting bombs")
	t.ok(ship.is_invulnerable() and not ship.dead)
	t.ok(not ship.hit(), "nothing hits it while it blinks")
	var shown: Array = []
	ship.move = Vector2.ZERO
	for i in 23:
		ship.advance(STEP)
		shown.append((ship.get_node("Visual") as CanvasItem).visible)
	t.ok(ship.is_invulnerable(), "2.875 s: still safe")
	t.ok(shown.has(true) and shown.has(false), "it blinks")
	ship.advance(STEP)
	t.ok(not ship.is_invulnerable(), "three seconds")
	t.ok((ship.get_node("Visual") as CanvasItem).visible, "and is seen again")
	t.ok(ship.hit())
	_drop(holder)

# ---------------------------------------------------------------- the weapon

func test_the_bullets_of_a_shot_by_kind_and_level(t) -> void:
	var counts := {}
	for kind in RpgShmupWeapon.KINDS:
		counts[kind] = [RpgShmupWeapon.bullet_count(kind, 1), RpgShmupWeapon.bullet_count(kind, 2), RpgShmupWeapon.bullet_count(kind, 3)]
	t.eq(counts, {"straight": [1, 2, 3], "spread": [3, 5, 7], "laser": [1, 1, 1], "homing": [1, 2, 3]})
	t.eq(RpgShmupWeapon.bullet_count("spread", 9), 7, "no level above the third")
	var widths: Array = []
	for level in [1, 2, 3]:
		widths.append(RpgShmupWeapon.shots("laser", level)[0]["width"])
	t.eq(widths, [1.0, 2.0, 3.0], "a thicker laser")
	var leans: Array = RpgShmupWeapon.shots("spread", 1).map(func(s: Dictionary) -> float: return s["lean"])
	t.eq(leans, [-12.0, 0.0, 12.0])
	t.eq(RpgShmupWeapon.shots("spread", 3)[6]["lean"], 32.0, "a wider spread")
	var sides: Array = RpgShmupWeapon.shots("straight", 3).map(func(s: Dictionary) -> float: return s["side"])
	t.eq(sides, [-6.0, 0.0, 6.0], "side by side")
	var weapon := RpgShmupWeapon.new()
	t.ok(weapon.level_up() and weapon.level_up())
	t.ok(not weapon.level_up() and weapon.level == 3, "to the third level and no further")
	weapon.set_kind("banana")
	t.eq(weapon.kind, "straight")
	weapon.set_kind("spread")
	t.eq([weapon.kind, weapon.level], ["spread", 3], "another kind keeps the level")
	weapon.free()

func test_the_weapon_fires_at_its_rate_into_the_pool_toward_where_the_ship_looks(t) -> void:
	await Fixtures.tree().process_frame
	var pool := _pool()
	var weapon := RpgShmupWeapon.new()
	weapon.rate = 4.0
	weapon.bullet_speed = 200.0
	weapon.kind = "spread"
	var fired: Array = []
	weapon.fired.connect(func(n: int) -> void: fired.append(n))
	t.eq(weapon.advance(STEP, false, pool, Vector2.ZERO, Vector2.UP), 0, "not while the button is up")
	t.eq(weapon.advance(STEP, true, pool, Vector2(50, 50), Vector2.UP), 3, "the first shot at once")
	t.eq(weapon.advance(STEP, true, pool, Vector2(50, 50), Vector2.UP), 0, "four shots a second: one every two steps")
	t.eq(weapon.advance(STEP, true, pool, Vector2(50, 50), Vector2.UP), 3)
	t.eq(fired, [3, 3])
	t.eq(pool.active(PLAYER), 6)
	pool.advance(1.0, Rect2())
	var flown := pool.positions(PLAYER)
	t.near(flown[1].x, 50.0, 0.001)
	t.near(flown[1].y, 50.0 - 200.0, 0.001, "straight up")
	t.ok(flown[0].x < 50.0 and flown[2].x > 50.0, "the others lean to the left and the right")
	t.near(flown[0].distance_to(Vector2(50, 50)), 200.0, 0.01, "every bullet at the weapon's speed")
	pool.clear(PLAYER)
	weapon.kind = "straight"
	weapon.level = 2
	weapon.shoot(pool, Vector2.ZERO, Vector2.RIGHT)
	pool.advance(0.5, Rect2())
	var pair: Array = Array(pool.positions(PLAYER))
	pair.sort()
	t.eq(pair, [Vector2(100, -3), Vector2(100, 3)], "a ship that looks right fires right, side by side")
	weapon.free()
	_drop(pool)

# ---------------------------------------------------------------- the pool

func test_the_pool_holds_its_bullets_and_uses_them_again(t) -> void:
	var pool := RpgArcadeBulletPool.new()
	t.eq([pool.capacity(PLAYER), pool.capacity(ENEMY)], [400, 1000])
	for i in 400:
		t.eq(pool.fire(PLAYER, Vector2(i, 0), Vector2.UP * 100.0), i)
	t.eq(pool.fire(PLAYER, Vector2.ZERO, Vector2.UP), -1, "every bullet is flying: nothing is fired")
	t.eq(pool.active(PLAYER), 400)
	t.eq(pool.fire(ENEMY, Vector2.ZERO, Vector2.DOWN), 0, "the enemies have their own")
	# the ones that leave the screen come back to the pool
	var view := Rect2(0, -100, 200, 200)
	pool.advance(STEP, view)
	t.eq(pool.active(PLAYER), 216, "x 0..215 is inside the screen and its margin of 16 px")
	t.eq(pool.fire(PLAYER, Vector2(5, 5), Vector2.ZERO), 399, "a freed bullet is used again")
	for i in 20:
		pool.advance(STEP, view)
	t.eq(pool.active(PLAYER), 1, "they flew off the top; the one that stands still is left")
	t.eq(pool.positions(PLAYER), PackedVector2Array([Vector2(5, 5)]))
	t.eq(pool.clear(PLAYER), 1)
	t.eq(pool.clear(PLAYER), 0)
	for i in 1100:
		pool.fire(ENEMY, Vector2.ZERO, Vector2.ZERO)
	t.eq(pool.active(ENEMY), 1000, "a thousand and no more")
	t.eq(pool.clear(ENEMY), 1000)
	t.eq(pool.fire(ENEMY, Vector2.ZERO, Vector2.ZERO) >= 0, true)
	pool.free()

func test_bullets_hit_targets_and_the_ship(t) -> void:
	await Fixtures.tree().process_frame
	var holder := Node2D.new()
	Fixtures.tree().root.add_child(holder)
	var pool := RpgArcadeBulletPool.new()
	pool.auto_advance = false
	holder.add_child(pool)
	var target := Target.new()
	target.position = Vector2(0, -80)
	holder.add_child(target)
	var hits: Array = []
	pool.player_bullet_hit.connect(func(_who: Node2D, damage: int) -> void: hits.append(damage))
	pool.fire(PLAYER, Vector2.ZERO, Vector2.UP * 160.0, 2)
	pool.fire(PLAYER, Vector2(40, 0), Vector2.UP * 160.0, 2)
	for i in 4:
		pool.advance(STEP, Rect2())
	t.eq([target.taken, hits], [2, [2]], "the bullet under the target hits it")
	t.eq(pool.active(PLAYER), 1, "and is gone; the one beside it flies on")
	pool.clear(PLAYER)
	# a laser goes through, a homing bullet turns
	pool.fire(PLAYER, Vector2(0, -75), Vector2.UP * 8.0, 3, 2.0, "laser", false, true)
	pool.advance(STEP, Rect2())
	pool.advance(STEP, Rect2())
	t.eq(target.taken, 8, "a laser hurts as long as it is in the target")
	t.eq(pool.active(PLAYER), 1)
	pool.clear(PLAYER)
	target.taken = 0
	pool.fire(PLAYER, Vector2(60, 0), Vector2.UP * 160.0, 1, 2.0, "missile", true)
	for i in 12:
		pool.advance(STEP, Rect2())
	t.eq(target.taken, 1, "a homing bullet 60 px to the side finds the target")
	# the enemies' bullets look for the ship, and for one point of it
	var ship := _ship("vertical")
	holder.add_child(ship)
	ship.position = Vector2(0, 60)
	ship.advance(STEP)
	pool.fire(ENEMY, Vector2(6, 0), Vector2.DOWN * 160.0)
	for i in 6:
		pool.advance(STEP, Rect2())
	t.ok(not ship.dead, "6 px beside the middle of a 24 px ship is a miss")
	pool.clear(ENEMY)
	RpgShmupEnemyBullet.fire(pool, Vector2(0, -20), RpgShmupEnemyBullet.aimed(Vector2(0, -20), ship.position, 160.0))
	for i in 4:
		pool.advance(STEP, Rect2())
	t.ok(ship.dead, "a bullet through its middle destroys it")
	t.eq(pool.active(ENEMY), 0)
	_drop(holder)

# ---------------------------------------------------------------- the patterns

func test_the_patterns_of_the_enemies(t) -> void:
	t.eq(RpgShmupEnemyBullet.aimed(Vector2.ZERO, Vector2(0, 50), 80.0), PackedVector2Array([Vector2(0, 80)]))
	t.eq(RpgShmupEnemyBullet.aimed(Vector2(3, 3), Vector2(3, 3), 80.0), PackedVector2Array([Vector2(0, 80)]), "on top of the target: down")
	var ring := RpgShmupEnemyBullet.ring(8, 100.0)
	t.eq(ring.size(), 8)
	var sum := Vector2.ZERO
	for velocity in ring:
		t.near(velocity.length(), 100.0, 0.001)
		sum += velocity
	t.near(sum.length(), 0.0, 0.001, "all around")
	t.near(ring[0].angle(), 0.0, 0.0001)
	t.near(RpgShmupEnemyBullet.ring(8, 100.0, 0.5)[0].angle(), 0.5, 0.0001, "the phase turns it")
	var fan := RpgShmupEnemyBullet.fan(Vector2.DOWN, 5, 60.0, 90.0)
	t.eq(fan.size(), 5)
	t.near(fan[2].angle_to(Vector2.DOWN), 0.0, 0.0001, "the middle one at the ship")
	t.near(absf(rad_to_deg(fan[0].angle_to(fan[4]))), 60.0, 0.001, "sixty degrees from end to end")
	t.eq(RpgShmupEnemyBullet.fan(Vector2.DOWN, 1, 60.0, 90.0), PackedVector2Array([Vector2(0, 90)]))
	var first := RpgShmupEnemyBullet.spiral(0, 3, 70.0, 10.0)
	var third := RpgShmupEnemyBullet.spiral(2, 3, 70.0, 10.0)
	t.eq(first.size(), 3)
	t.near(rad_to_deg(first[0].angle_to(third[0])), 20.0, 0.001, "ten degrees a volley")
	t.eq(RpgShmupEnemyBullet.fire(null, Vector2.ZERO, ring), 0)

# ---------------------------------------------------------------- the bomb

func test_a_bomb_clears_the_enemy_bullets_and_hurts_what_is_on_the_screen(t) -> void:
	await Fixtures.tree().process_frame
	var holder := Node2D.new()
	Fixtures.tree().root.add_child(holder)
	var pool := RpgArcadeBulletPool.new()
	pool.auto_advance = false
	holder.add_child(pool)
	var near := Target.new()
	near.position = Vector2(20, -40)
	holder.add_child(near)
	var far := Target.new()
	far.position = Vector2(900, 0)
	holder.add_child(far)
	var ship := _ship("vertical")
	holder.add_child(ship)
	ship.position = Vector2(0, 60)
	ship.advance(STEP)
	var bomb := ship.bomb()
	var log: Array = []
	bomb.used.connect(func(cleared: int, hit: int) -> void: log.append([cleared, hit]))
	t.eq(RpgShmupEnemyBullet.fire(pool, Vector2(0, -50), RpgShmupEnemyBullet.ring(30, 10.0)), 30)
	pool.fire(PLAYER, Vector2(0, 40), Vector2.ZERO)
	ship.pool_override = pool
	ship.press_bomb()
	ship.advance(STEP)
	t.eq(pool.active(ENEMY), 0, "every enemy bullet is gone")
	t.eq(pool.active(PLAYER), 1, "the player's own stay")
	t.eq([near.taken, far.taken], [20, 0], "what is on the screen is hurt, what is far off is not")
	t.eq(log, [[30, 1]])
	t.eq(bomb.count, 2)
	ship.press_bomb()
	ship.advance(STEP)
	ship.press_bomb()
	ship.advance(STEP)
	t.eq(bomb.count, 0)
	t.ok(not bomb.use(pool), "none left")
	t.eq(log.size(), 3)
	t.ok(bomb.add() and bomb.count == 1)
	bomb.count = RpgShmupBomb.MAX_BOMBS
	t.ok(not bomb.add())
	_drop(holder)

# ---------------------------------------------------------------- a stage, flown

func test_the_ship_flies_shoots_and_dies_in_a_stage_in_both_orientations(t) -> void:
	await Fixtures.tree().process_frame
	for way: String in ["vertical", "horizontal"]:
		Fixtures.install_state()
		var ctx := _ctx({"starter_map": {"orientation": way}})
		var plan := StageRecipe.plan(ctx)
		t.eq(plan[0]["axis"], RpgShmupMath.axis_of(way))
		t.eq([plan[0]["speed"], plan[0]["exit"]], [40.0, "reach_end"])
		t.eq(plan[0]["length"], 6.0 * (180 if way == "vertical" else 320), "six screens long")
		var root := StageRecipes.build_stage(0, plan[0], VIEW, Vector2(VIEW) * 0.5 + RpgShmupMath.start_offset(Vector2(VIEW), way))
		var background := StageRecipe.build_background(ctx, way, Vector2(VIEW))
		root.add_child(background)
		var pool := RpgArcadeBulletPool.new()
		pool.name = "Bullets"
		pool.auto_advance = false
		root.add_child(pool)
		var ship := _ship(way)
		ship.position = root.get_spawn(&"default").position
		root.add_child(ship)
		var stage := root as RpgArcadeStage
		stage.auto_advance = false
		Fixtures.tree().root.add_child(stage)
		var mode := RpgShmupMode.new()
		mode.auto_screens = true
		mode.orientation = way
		mode.sequence = RpgArcadeStageSequence.from_array(StageRecipes.with_scenes(plan))
		Fixtures.tree().root.add_child(mode)
		mode.bind_stage(stage)
		t.ok(mode.ship == ship, "the mode found the ship of the stage")
		t.eq(ship.pool(), pool)
		# a second of flight: the stage scrolls, the ship keeps its place on the screen and fires
		ship.advance(0.0)  # the ship takes its place on the screen
		var on_screen := ship.position - stage.scroller().view_center()
		var shots := [0]
		ship.weapon().fired.connect(func(_n: int) -> void: shots[0] += 1)
		ship.shooting = true
		for i in 8:
			stage.advance(STEP)
			ship.advance(STEP)
			pool.advance(STEP, Rect2(stage.scroller().view_center() - Vector2(VIEW) * 0.5, Vector2(VIEW)))
		t.eq(stage.scroller().progress, 40.0, way)
		t.eq(stage.scroller().offset(), RpgShmupMath.forward_of(way) * 40.0)
		t.eq(ship.position - stage.scroller().view_center(), on_screen, "the ship rides with the screen")
		t.eq(shots[0], 8, "eight shots a second")
		t.ok(pool.active(PLAYER) > 0 and pool.active(PLAYER) <= 8, "those that left the screen are back in the pool")
		for at in pool.positions(PLAYER):
			t.ok((at - ship.position).dot(ship.forward()) > 0.0, "every bullet is ahead of the ship")
		# three hits: two lives lost and the ship back each time, then the game is over
		ship.shooting = false
		var lost: Array = []
		mode.life_lost.connect(func(left: int) -> void: lost.append(left))
		var over := [0]
		mode.game_over.connect(func() -> void: over[0] += 1)
		for life in 3:
			ship.hit()
			await Fixtures.tree().process_frame
			if life < 2:
				t.ok(not ship.dead and ship.is_invulnerable(), "back and blinking")
				for i in 24:
					ship.advance(STEP)
		t.eq([lost, over[0]], [[2, 1], 1], way + ": the third hit ends the game")
		t.eq(mode.lives.count, 3, "and Continue gives the lives back")
		for node: Node in [stage, mode]:
			_drop(node)
		Fixtures.uninstall_state()

# ---------------------------------------------------------------- the recipes

func test_the_recipes_build_the_ship_the_explosion_and_the_background(t) -> void:
	var burst := ShipRecipe.build_explosion(_frames())
	t.ok(burst is RpgArcadeExplosion)
	var packed := PackedScene.new()
	t.eq(packed.pack(burst), OK)
	burst.free()
	var ship := ShipRecipe.build_ship(_frames(), Vector2i(24, 24), "horizontal", VIEW, 32, packed)
	t.ok(ship is RpgShmupShip)
	var typed := ship as RpgShmupShip
	t.eq([typed.speed, typed.orientation, typed.play_area], [240.0, "horizontal", Rect2(-160, -90, 320, 180)])
	t.eq(typed.explosion_scene, packed)
	t.ok(typed.weapon() != null and typed.bomb() != null and typed.get_node_or_null("Input") is RpgShmupShipInput)
	t.eq(typed.weapon().bullet_speed, 512.0)
	t.ok(typed.get_collision_layer_value(2) and typed.collision_mask == 0, "the player's layer, and it runs into nothing")
	var saved := PackedScene.new()
	t.eq(saved.pack(typed), OK)
	var again := saved.instantiate() as RpgShmupShip
	t.eq(again.get_child_count(), 5, "Visual, Body, Weapon, Bomb and Input are saved with it")
	again.free()
	typed.free()
	# a pack without a background gets stars; the layers loop along the way of the game
	var ctx := _ctx()
	t.eq(StageRecipe.background_layers(ctx), [] as Array[Dictionary])
	for way: String in ["vertical", "horizontal"]:
		var background := StageRecipe.build_background(ctx, way, Vector2(VIEW))
		t.eq(background.get_child_count(), 3, "a backdrop and two layers of stars")
		var backdrop := background.get_child(0) as Parallax2D
		t.eq(backdrop.scroll_scale, Vector2.ZERO, "the backdrop stays on the screen")
		var layer := background.get_child(1) as Parallax2D
		var stars := layer.get_child(0) as RpgShmupStarfield
		t.eq(layer.repeat_size, Vector2(0, 180) if way == "vertical" else Vector2(320, 0), way)
		t.eq(layer.scroll_scale, Vector2(1.0, 0.2) if way == "vertical" else Vector2(0.2, 1.0))
		t.ok(layer.repeat_times >= 3)
		t.eq(stars.stars().size(), 40)
		t.eq(stars.stars(), stars.stars(), "the same stars every time")
		for star: Array in stars.stars():
			t.ok(Rect2(Vector2.ZERO, Vector2(VIEW)).has_point(star[0]))
		t.ok((background.get_child(2) as Parallax2D).scroll_scale != layer.scroll_scale, "the nearer layer is faster")
		background.free()
	t.eq(ShmupBuild.orientation(_ctx({"starter_map": {"orientation": "horizontal"}})), "horizontal")
	t.eq(ShmupBuild.orientation(_ctx({"starter_map": {"orientation": "sideways"}})), "vertical")
	t.eq(ShmupBuild.view(ctx), VIEW)
	t.eq([ShmupBuild.bullet_kind("pack.bullets.laser_blue"), ShmupBuild.bullet_kind("pack.fx.rocket"),
		ShmupBuild.bullet_kind("pack.enemy_shot"), ShmupBuild.bullet_kind("pack.bullets.bullet")], ["laser", "missile", "enemy", "bullet"])
	t.eq(HudRecipe.script_for("shmup"), "res://addons/rpg_runtime/archetypes/shmup/ui/shmup_hud.gd")
	t.eq(HudRecipe.script_for("pinball"), ArcadeBuild.HUD_SCRIPT, "a kind without rows of its own has the framework HUD")

func test_the_hud_has_the_bombs_and_the_weapon(t) -> void:
	await Fixtures.tree().process_frame
	var hud := HudRecipe.build_hud(HudRecipe.script_for("shmup")) as RpgShmupHud
	t.ok(hud != null)
	Fixtures.tree().root.add_child(hud)
	hud.set_process(false)
	var ship := _ship("vertical")
	ship.weapon().kind = "spread"
	ship.weapon().level = 2
	hud.show_ship(ship)
	t.eq([hud.row_text("bombs"), hud.row_text("weapon")], ["Bombs: 3", "Spread Lv 2"])
	ship.bomb().count = 1
	hud.show_ship(ship)
	t.eq(hud.row_text("bombs"), "Bombs: 1")
	hud.show_ship(null)
	t.eq([hud.row_text("bombs"), hud.row_text("weapon")], ["", ""])
	for kind in RpgShmupWeapon.KINDS:
		t.ok(RpgShmupStrings.weapon_name(kind) != "SHM_WEAPON_" + kind.to_upper(), kind)
	ship.free()
	_drop(hud)

# ---------------------------------------------------------------- the HUD, the title (T16.07)

const ShmupHud := preload("res://builder/recipes/shmup/hud_recipe.gd")
const SAVE_DIR := "user://test_shmup_saves"

func _saves() -> Node:
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER)
	save.dir = SAVE_DIR
	if DirAccess.dir_exists_absolute(SAVE_DIR):
		for file: String in DirAccess.get_files_at(SAVE_DIR):
			DirAccess.remove_absolute(SAVE_DIR.path_join(file))
	return save

func test_the_hud_shows_the_lives_the_score_the_weapon_and_the_high_score(t) -> void:
	await Fixtures.tree().process_frame
	Fixtures.install_state()
	_saves()
	RpgArcadeHighScores.submit("ANA", 4200, 2)
	var plan := [{"title": "Nebula", "exit": "custom", "waves": []}]
	var stage := StageRecipes.build_stage(0, plan[0], VIEW, Vector2(160, 150)) as RpgArcadeStage
	stage.auto_advance = false
	var ship := _ship("vertical")
	stage.add_child(ship)
	Fixtures.tree().root.add_child(stage)
	var mode := RpgShmupMode.new()
	mode.auto_screens = true
	mode.start_lives = 5
	mode.sequence = RpgArcadeStageSequence.from_array(plan)
	Fixtures.tree().root.add_child(mode)
	var hud := ShmupHud.build_hud("vertical") as RpgShmupHud
	Fixtures.tree().root.add_child(hud)
	hud.set_process(false)
	hud.bind(mode)
	mode.bind_stage(stage)
	hud.show_ship(mode.ship)
	t.eq([hud.lives_text(), hud.score_text(), hud.stage_text()], ["Lives: 5", "Score: 0", "Nebula"], "the lives of the options")
	t.eq([hud.row_text("bombs"), hud.row_text("weapon")], ["Bombs: 3", "Shot Lv 1"])
	t.eq(hud.high_score_text(), "Hi: 4200", "the best run of the table")
	for i in 5:
		mode.score.add_kill(100)
	mode.lives.lose()
	ship.weapon().level_up()
	ship.weapon().set_kind("laser")
	ship.bomb().use(null)
	hud.show_ship(mode.ship)
	t.eq([hud.lives_text(), hud.score_text(), hud.multiplier_text()], ["Lives: 4", "Score: 500", "x2"])
	t.eq([hud.row_text("bombs"), hud.row_text("weapon")], ["Bombs: 2", "Laser Lv 2"])
	t.eq(hud.high_score_text(), "Hi: 4200")
	mode.score.add_bonus(5000)
	t.eq(hud.high_score_text(), "Hi: 5500", "a run that passes the best score is the high score")
	for node: Node in [hud, stage, mode]:
		_drop(node)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_a_game_that_scrolls_up_has_side_panels_and_one_that_scrolls_right_has_none(t) -> void:
	await Fixtures.tree().process_frame
	var up := ShmupHud.build_hud("vertical") as RpgShmupHud
	t.ok(up.panels)
	Fixtures.tree().root.add_child(up)
	up.set_process(false)
	# the layout for a screen of 320 x 180: the play area is 240 wide, 40 px are left on each side
	t.ok(not up.lay_out_panels(Vector2(320, 180)), "40 px is too narrow for a panel")
	t.ok(up.lay_out_panels(Vector2(640, 360)), "80 px on each side of a 480 px play area")
	t.eq(up.panel_width(), 80.0)
	var left := up.get_node("PanelLeft") as ColorRect
	var right := up.get_node("PanelRight") as ColorRect
	t.eq([left.position, left.size], [Vector2.ZERO, Vector2(80, 360)])
	t.eq([right.position, right.size], [Vector2(560, 0), Vector2(80, 360)])
	t.ok(left.get_index() < up.get_node("Left").get_index(), "the panels lie behind the texts")
	_drop(up)
	var side := ShmupHud.build_hud("horizontal") as RpgShmupHud
	t.ok(not side.panels)
	Fixtures.tree().root.add_child(side)
	side.set_process(false)
	t.ok(side.get_node_or_null("PanelLeft") == null)
	t.eq(side.get_node("Right/HighScore").get_parent().name, &"Right", "the high score under the score")
	t.ok(side.get_node_or_null("Left/Lives") != null, "the lives stay on the left")
	_drop(side)
	t.eq(ShmupHud.new().outputs(null), PackedStringArray(["res://generated/scenes/ui/hud_arcade.tscn"]))

func test_the_title_screen_gets_high_scores_and_the_table_closes_on_cancel(t) -> void:
	await Fixtures.tree().process_frame
	_saves()
	RpgArcadeHighScores.submit("BO", 900, 1)
	var title := Control.new()
	var box := VBoxContainer.new()
	title.add_child(box)
	for button_name: String in ["NewGame", "Credits", "Quit"]:
		var button := Button.new()
		button.name = button_name
		button.unique_name_in_owner = true
		box.add_child(button)
		button.owner = title
	Fixtures.tree().root.add_child(title)
	var mode := RpgShmupMode.new()
	Fixtures.tree().root.add_child(mode)
	mode.customize_title_screen(title)
	mode.customize_title_screen(title)
	var names: Array = box.get_children().map(func(n: Node) -> String: return n.name)
	t.eq(names, ["NewGame", "HighScores", "Credits", "Quit"], "once, above the credits")
	var entry := box.get_node("HighScores") as Button
	t.eq(entry.text, "High scores")
	t.eq(entry.get_node(entry.focus_neighbor_bottom).name, &"Credits", "it is in the focus chain")
	entry.pressed.emit()
	var table: RpgArcadeHighScoreTable = null
	for child in title.get_children():
		if child is RpgArcadeHighScoreTable:
			table = child
	t.ok(table != null, "the table opens over the title")
	var texts: Array = table.find_children("*", "Label", true, false).map(func(l: Label) -> String: return l.text)
	t.ok(texts.has("BO") and texts.has("900"))
	var cancel := InputEventAction.new()
	cancel.action = &"ui_cancel"
	cancel.pressed = true
	table._unhandled_input(cancel)
	t.ok(table.is_queued_for_deletion(), "cancel closes it")
	for node: Node in [title, mode]:
		_drop(node)
	Fixtures.uninstall("SaveManager")

# ---------------------------------------------------------------- the weapon of the run

func _weapon_stage(index: int, plan: Array) -> RpgArcadeStage:
	var stage := StageRecipes.build_stage(index, plan[index], VIEW, Vector2(160, 150)) as RpgArcadeStage
	stage.auto_advance = false
	stage.add_child(_ship("vertical"))
	Fixtures.tree().root.add_child(stage)
	return stage

func test_the_weapon_goes_on_to_the_next_stage_and_into_the_saved_run(t) -> void:
	await Fixtures.tree().process_frame
	var state := Fixtures.install_state() as RpgGameState
	_saves()
	var plan := [{"exit": "custom", "waves": []}, {"exit": "custom", "waves": []}]
	var mode := RpgShmupMode.new()
	mode.auto_screens = true
	mode.sequence = RpgArcadeStageSequence.from_array(plan)
	Fixtures.tree().root.add_child(mode)
	var first := _weapon_stage(0, plan)
	mode.bind_stage(first)
	t.eq([mode.weapon, mode.ship.weapon().kind, mode.ship.weapon().level], ["", "straight", 1])
	mode.ship.weapon().set_kind("laser")
	mode.ship.weapon().level_up()
	first.cleared.emit()
	t.eq(mode.weapon, "laser:2", "what the ship had when the stage was cleared")
	var second := _weapon_stage(1, plan)
	mode.bind_stage(second)
	t.ok(mode.ship.get_parent() == second)
	t.eq([mode.ship.weapon().kind, mode.ship.weapon().level], ["laser", 2], "the next ship has it")
	var saved := JSON.stringify(state.to_dict())
	# the saved game that is continued begins its stage with that weapon
	state.new_game()
	mode._on_game_loaded(0)
	var fresh := _weapon_stage(0, plan)
	mode.bind_stage(fresh)
	t.eq([mode.weapon, mode.ship.weapon().kind, mode.ship.weapon().level], ["", "straight", 1], "a new game")
	state.from_dict(RpgUtil.restore_numbers(JSON.parse_string(saved)))
	mode._on_game_loaded(1)
	var loaded := _weapon_stage(1, plan)
	mode.bind_stage(loaded)
	t.eq(mode.stages().index, 1)
	t.eq([mode.ship.weapon().kind, mode.ship.weapon().level], ["laser", 2], "Continue has the weapon")
	# a level the game does not have is brought into its range; a name that is no weapon is left out
	mode.weapon = "plasma:9"
	mode._give_weapon()
	t.eq([mode.ship.weapon().kind, mode.ship.weapon().level], ["laser", RpgShmupWeapon.MAX_LEVEL])
	# Continue after the last life: the first weapon, as after a death
	mode.continued.emit()
	t.eq(mode.weapon, "")
	for node: Node in [first, second, fresh, loaded, mode]:
		_drop(node)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()
