extends RefCounted
## T16.05: the enemies of a shoot-em-up (popcorn, turret, asteroid, carrier), formations that
## move as one and their bonus, the power-ups, the shield, and the scenes and waves the recipes
## make of them.

const Fixtures := preload("../lib/fixtures.gd")
const StageRecipes := preload("res://builder/recipes/arcade/stage_recipes.gd")
const ShipRecipe := preload("res://builder/recipes/shmup/ship_recipe.gd")
const StageRecipe := preload("res://builder/recipes/shmup/stage_recipe.gd")
const EnemyRecipes := preload("res://builder/recipes/shmup/enemy_recipes.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")

const STEP := 0.125
const VIEW := Vector2i(320, 180)
const ENEMY := RpgShmupBulletPool.Team.ENEMY

func _enemy(behaviour: String, way: String = "vertical", powerup: PackedScene = null) -> RpgShmupEnemy:
	var enemy := EnemyRecipes.build_enemy(behaviour, null, Vector2i(16, 16), false, way, VIEW, 16, null, powerup) as RpgShmupEnemy
	enemy.auto_advance = false
	return enemy

func _ship(way: String = "vertical") -> RpgShmupShip:
	var ship := ShipRecipe.build_ship(null, Vector2i(24, 24), way, VIEW, 16, null) as RpgShmupShip
	ship.auto_advance = false
	(ship.get_node("Input") as RpgShmupShipInput).enabled = false
	return ship

func _field() -> Node2D:
	var holder := Node2D.new()
	Fixtures.tree().root.add_child(holder)
	var pool := RpgShmupBulletPool.new()
	pool.name = "Bullets"
	pool.auto_advance = false
	holder.add_child(pool)
	return holder

func _pool(holder: Node2D) -> RpgShmupBulletPool:
	return holder.get_node("Bullets") as RpgShmupBulletPool

func _put(holder: Node2D, enemy: RpgShmupEnemy, at: Vector2) -> void:
	enemy.pool_override = _pool(holder)
	enemy.position = at
	holder.add_child(enemy)

func _drop(node: Node) -> void:
	if node.get_parent() != null:
		node.get_parent().remove_child(node)
	node.free()

func _ctx(config: Dictionary = {}) -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"archetype": "shmup", "resolution": [VIEW.x, VIEW.y], "base_tile_size": 16, "seed": 7}
	ctx.config.merge(config, true)
	return ctx

# ---------------------------------------------------------------- what every enemy is

func test_an_enemy_has_health_points_and_is_gone_when_it_is_shot(t) -> void:
	await Fixtures.tree().process_frame
	var holder := _field()
	var enemy := _enemy("turret")
	_put(holder, enemy, Vector2(0, -40))
	t.eq([enemy.health, enemy.points, enemy.in_stage], [3, 300, true])
	t.ok(enemy.is_in_group(RpgShmupBulletPool.TARGET_GROUP), "the player's bullets find it")
	t.eq(enemy.travel(), Vector2.DOWN, "it comes from where the ship looks")
	var shot := [0]
	enemy.defeated.connect(func() -> void: shot[0] += 1)
	enemy.take_hit(2)
	t.eq([enemy.health, shot[0]], [1, 0])
	enemy.take_hit(0)
	enemy.take_hit(5)
	t.eq(shot[0], 1)
	t.ok(enemy.is_queued_for_deletion() and not enemy.is_in_group(RpgShmupBulletPool.TARGET_GROUP))
	enemy.take_hit(5)
	t.eq(shot[0], 1, "once")
	var side := _enemy("popcorn", "horizontal")
	t.eq([side.travel(), side.speed], [Vector2.LEFT, 56.0], "three and a half tiles a second, to the left")
	side.free()
	_drop(holder)

func test_an_enemy_that_touches_the_ship_destroys_it_and_one_that_leaves_is_taken_away(t) -> void:
	await Fixtures.tree().process_frame
	var holder := _field()
	var ship := _ship()
	holder.add_child(ship)
	ship.position = Vector2(0, 60)
	ship.advance(STEP)
	var enemy := _enemy("popcorn")
	_put(holder, enemy, Vector2(0, -120))
	var gone := [0]
	enemy.defeated.connect(func() -> void: gone[0] += 1)
	for i in 24:  # 3 s at 56 px/s: from above the screen down to the ship
		enemy.advance(STEP)
	t.ok(not ship.dead, "168 px on: 12 px above the ship")
	for i in 2:
		enemy.advance(STEP)
	t.ok(ship.dead, "it flew into the ship")
	t.ok(not enemy.is_queued_for_deletion(), "and flies on")
	for i in 16:
		enemy.advance(STEP)
	t.ok(enemy.is_queued_for_deletion(), "below the screen it is taken away")
	t.eq(gone[0], 0, "which is not a kill")
	_drop(holder)

# ---------------------------------------------------------------- the four behaviours

func test_a_popcorn_flies_its_path_and_fires_one_aimed_shot(t) -> void:
	await Fixtures.tree().process_frame
	var holder := _field()
	var ship := _ship()
	holder.add_child(ship)
	ship.position = Vector2(40, 60)
	ship.advance(STEP)
	var ends := {}
	for path in RpgShmupPopcorn.PATHS:
		var enemy := _enemy("popcorn") as RpgShmupPopcorn
		enemy.path = path
		_put(holder, enemy, Vector2(-60, -114))
		for i in 8:
			enemy.advance(STEP)
		ends[path] = enemy.position - Vector2(-60, -114)
		_drop(enemy)
	t.eq(ends["straight"], Vector2(0, 56), "a second at 56 px/s")
	t.near((ends["dive"] as Vector2).y, 100.8, 0.001, "a dive is faster")
	t.near((ends["sweep"] as Vector2).y, 33.6, 0.001, "a sweep is slower")
	t.near((ends["sweep"] as Vector2).x, -sin(1.5) * 48.0, 0.001, "and goes far to the side")
	t.near((ends["sine"] as Vector2).x, -sin(3.0) * 24.0, 0.001, "a weave")
	t.eq(ends["close"], ends["straight"], "alone, a closing formation is a straight flight")
	t.eq(ends["swoop"], ends["straight"], "a swoop turns away later")
	var swooper := _enemy("popcorn") as RpgShmupPopcorn
	swooper.path = "swoop"
	_put(holder, swooper, Vector2(-60, -114))
	for i in 28:
		swooper.advance(STEP)
	t.ok(swooper.position.x < -90.0, "away to the side it came from")
	_drop(swooper)
	# the shot: one, a second in, at the ship
	var gunner := _enemy("popcorn") as RpgShmupPopcorn
	gunner.shoots = true
	_put(holder, gunner, Vector2(-60, -114))
	var pool := _pool(holder)
	for i in 7:
		gunner.advance(STEP)
	t.eq(pool.active(ENEMY), 0, "not before a second")
	gunner.advance(STEP)
	t.eq(pool.active(ENEMY), 1)
	var from := gunner.position
	for i in 16:
		gunner.advance(STEP)
	t.eq(pool.active(ENEMY), 1, "one shot")
	pool.advance(1.0, Rect2())
	var flown := pool.positions(ENEMY)[0] - from
	t.near(flown.length(), 88.0, 0.01, "five and a half tiles a second")
	t.near(flown.angle_to(ship.position - from), 0.0, 0.0001, "at the ship")
	_drop(holder)

func test_a_formation_moves_as_one_and_a_circle_closes(t) -> void:
	await Fixtures.tree().process_frame
	for way: String in ["vertical", "horizontal"]:
		var holder := _field()
		var wave := RpgArcadeWave.from_dict({"formation": "v", "count": 5, "gap": 20})
		var members: Array[RpgShmupPopcorn] = []
		var plain := RpgArcadeWave.offsets("v", 5, 20.0)
		for i in 5:
			var enemy := _enemy("popcorn", way) as RpgShmupPopcorn
			_put(holder, enemy, Vector2(0, -100) + plain[i])
			enemy.spawned_in_wave(wave, i)
			members.append(enemy)
		t.eq(members[0].path, "dive", "a V dives")
		var lead := members[0].position
		var shape: Array = members.map(func(m: RpgShmupPopcorn) -> Vector2: return m.position - lead)
		if way == "vertical":
			t.eq(shape[1], Vector2(-20, -20), "the others behind the point, to the left and the right")
		else:
			t.near((shape[1] as Vector2).distance_to(Vector2(20, -20)), 0.0, 0.001, "turned for a game that scrolls right: behind is to the right")
		for i in 8:
			for enemy in members:
				enemy.advance(STEP)
		var after: Array = members.map(func(m: RpgShmupPopcorn) -> Vector2: return m.position - members[0].position)
		for i in 5:
			t.near((after[i] as Vector2).distance_to(shape[i]), 0.0, 0.001, way + ": the formation keeps its shape")
		t.near((members[0].position - lead).distance_to(members[0].travel() * 100.8), 0.0, 0.001, way + ": and dives together")
		_drop(holder)
	var holder := _field()
	var ring := RpgArcadeWave.from_dict({"formation": "circle", "count": 6, "gap": 30})
	var around := RpgArcadeWave.offsets("circle", 6, 30.0)
	var circle: Array[RpgShmupPopcorn] = []
	for i in 6:
		var enemy := _enemy("popcorn") as RpgShmupPopcorn
		_put(holder, enemy, Vector2(0, -60) + around[i])
		enemy.spawned_in_wave(ring, i)
		circle.append(enemy)
	t.eq(circle[0].path, "close")
	for i in 16:
		for enemy in circle:
			enemy.advance(STEP)
	var middle := Vector2.ZERO
	for enemy in circle:
		middle += enemy.position / 6.0
	t.near(middle.distance_to(Vector2(0, -60 + 112)), 0.0, 0.001, "the middle flies straight")
	for enemy in circle:
		t.near(enemy.position.distance_to(middle), 30.0 * 0.5, 0.001, "two seconds on, the circle is half as wide")
	var line := RpgArcadeWave.from_dict({"formation": "line", "count": 3, "path": "sine", "shoots": true, "drop": "bomb"})
	var named: Array = []
	for i in 3:
		var enemy := _enemy("popcorn") as RpgShmupPopcorn
		_put(holder, enemy, Vector2.ZERO)
		enemy.spawned_in_wave(line, i)
		named.append([enemy.path, enemy.shoots, enemy.drop])
	t.eq(named, [["sine", true, ""], ["sine", true, ""], ["sine", true, "bomb"]], "the entry of the wave names the path; the last one carries the drop")
	_drop(holder)

func test_a_turret_sits_in_the_stage_and_fires_a_fan_while_it_is_on_the_screen(t) -> void:
	await Fixtures.tree().process_frame
	var holder := _field()
	var ship := _ship()
	holder.add_child(ship)
	ship.position = Vector2(0, 60)
	ship.advance(STEP)
	var turret := _enemy("turret") as RpgShmupTurret
	_put(holder, turret, Vector2(-50, -40))
	var pool := _pool(holder)
	for i in 15:
		turret.advance(STEP)
	t.eq(turret.position, Vector2(-50, -40), "it does not move by itself")
	t.eq(pool.active(ENEMY), 0)
	turret.advance(STEP)
	t.eq(pool.active(ENEMY), 3, "a fan of three every two seconds")
	pool.advance(0.5, Rect2())
	var shots := pool.positions(ENEMY)
	var toward := (ship.position - turret.position).normalized()
	var angles: Array = []
	for at in shots:
		angles.append(snappedf(rad_to_deg(toward.angle_to(at - turret.position)), 0.01))
	angles.sort()
	t.eq(angles, [-15.0, 0.0, 15.0], "thirty degrees wide, the middle one at the ship")
	for i in 16:
		turret.advance(STEP)
	t.eq(pool.active(ENEMY), 6)
	# the screen scrolls on and leaves it behind: it stops firing and is taken away
	pool.clear(ENEMY)
	turret.area_center = Vector2(0, -200)
	for i in 16:
		turret.advance(STEP)
	t.eq(pool.active(ENEMY), 0, "off the screen it does not fire")
	t.ok(turret.is_queued_for_deletion(), "behind the screen")
	_drop(holder)

func test_an_asteroid_drifts_stops_bullets_and_breaks_once_in_two(t) -> void:
	await Fixtures.tree().process_frame
	var holder := _field()
	var rock := _enemy("asteroid") as RpgShmupAsteroid
	rock.drift = Vector2(8, 16)
	_put(holder, rock, Vector2(0, -40))
	var pool := _pool(holder)
	t.eq([rock.health, rock.points, rock.hit_radius], [4, 50, 6.4])
	for i in 8:
		rock.advance(STEP)
	t.eq(rock.position, Vector2(8, -24), "it drifts")
	pool.fire(RpgShmupBulletPool.Team.PLAYER, Vector2(8, 0), Vector2.UP * 160.0, 1)
	for i in 3:
		pool.advance(STEP, Rect2())
	t.eq(pool.active(RpgShmupBulletPool.Team.PLAYER), 0, "a bullet stops at it")
	t.eq(rock.health, 3)
	var pieces := rock.pieces()
	t.eq(pieces.size(), 2)
	t.eq([pieces[0].fragment, pieces[0].health, pieces[0].points], [true, 1, 25])
	t.near(pieces[0].hit_radius, 6.4 * 0.6, 0.001)
	t.eq(pieces[0].scale, Vector2(0.6, 0.6), "smaller")
	t.eq(pieces[0].drift - pieces[1].drift, Vector2(-60, 0), "they fly apart")
	t.eq(pieces[0].pieces().size(), 0, "a piece does not break again")
	for piece in pieces:
		piece.free()
	rock.take_hit(9)
	await Fixtures.tree().process_frame
	var left: Array = holder.get_children().filter(func(n: Node) -> bool: return n is RpgShmupAsteroid and not n.is_queued_for_deletion())
	t.eq(left.size(), 2, "shot, it leaves its two pieces")
	t.ok((left[0] as RpgShmupAsteroid).is_in_group(RpgShmupBulletPool.TARGET_GROUP), "which can be shot too")
	var wave := RpgArcadeWave.from_dict({"formation": "line", "count": 3})
	var drifts: Array = []
	for i in 3:
		var one := _enemy("asteroid") as RpgShmupAsteroid
		one.spawned_in_wave(wave, i)
		drifts.append(one.drift)
		one.free()
	t.eq(drifts, [Vector2(-10, 6), Vector2(10, 10), Vector2(-10, 14)], "every rock of a wave a little differently, the same every time")
	_drop(holder)

func test_a_carrier_comes_in_stays_releases_escorts_and_leaves_a_power_up(t) -> void:
	await Fixtures.tree().process_frame
	var holder := _field()
	var capsule := PackedScene.new()
	var made := EnemyRecipes.build_powerup([] as Array[Texture2D], "vertical", VIEW, 16)
	capsule.pack(made)
	made.free()
	var escort := PackedScene.new()
	var small := _enemy("popcorn")
	escort.pack(small)
	small.free()
	var carrier := _enemy("carrier", "vertical", capsule) as RpgShmupCarrier
	carrier.escort_scene = escort
	carrier.drop = "weapon:spread"
	_put(holder, carrier, Vector2(0, -114))
	t.eq([carrier.health, carrier.points, carrier.speed], [12, 800, 24.0])
	for i in 28:  # 3.5 s at 24 px/s: 84 px, to a third of the way into the screen
		carrier.advance(STEP)
	t.near(carrier.position.y, -30.0, 0.001, "a third of the way in")
	t.ok(not carrier.is_holding())
	var escorts := func() -> Array:
		return holder.get_children().filter(func(n: Node) -> bool: return n is RpgShmupPopcorn)
	for i in 24:
		carrier.advance(STEP)
	t.near(carrier.position.y, -30.0, 0.001, "it stays there")
	t.ok(carrier.position.x != 0.0, "weaving")
	t.eq([carrier.released, escorts.call().size()], [1, 1], "an escort every two and a half seconds")
	for i in 160:
		carrier.advance(STEP)
	t.eq(carrier.released, 4, "four and no more")
	t.ok(carrier.position.y > -30.0, "after eighteen seconds it flies on")
	carrier.take_hit(12)
	await Fixtures.tree().process_frame
	var left: Array = holder.get_children().filter(func(n: Node) -> bool: return n is RpgShmupPowerup)
	t.eq(left.size(), 1, "shot, it leaves its power-up")
	t.eq((left[0] as RpgShmupPowerup).kind, "weapon:spread")
	_drop(holder)

# ---------------------------------------------------------------- formations and their bonus

func test_a_formation_shot_whole_pays_a_bonus_and_one_that_lost_an_enemy_does_not(t) -> void:
	await Fixtures.tree().process_frame
	Fixtures.install_state()
	var plan := [{"exit": "clear_waves", "waves": [
		{"id": "a", "formation": "line", "count": 3, "points": 100, "bonus": 500},
		{"id": "b", "formation": "line", "count": 2, "points": 100, "bonus": 500, "trigger": "after", "after": "a"},
	]}]
	var stage := StageRecipes.build_stage(0, plan[0], VIEW, Vector2(160, 150)) as RpgArcadeStage
	stage.auto_advance = false
	stage.enemy_factory = func(_wave: RpgArcadeWave) -> Node2D: return _enemy("popcorn")
	Fixtures.tree().root.add_child(stage)
	var mode := RpgShmupMode.new()
	mode.auto_screens = true
	mode.sequence = RpgArcadeStageSequence.from_array(plan)
	Fixtures.tree().root.add_child(mode)
	mode.bind_stage(stage)
	var bonuses: Array = []
	stage.formation_bonus.connect(func(points: int) -> void: bonuses.append(points))
	stage.advance(STEP)
	var first: Array = stage.entities().get_children()
	t.eq(first.size(), 3)
	for enemy: RpgShmupEnemy in first:
		enemy.take_hit(1)
	await Fixtures.tree().process_frame
	t.eq(bonuses, [500])
	t.eq(mode.score.points, 300 + 500, "three kills and the bonus of the formation")
	stage.advance(STEP)
	var second: Array = stage.entities().get_children().filter(func(n: Node) -> bool: return n is RpgShmupEnemy and not n.is_queued_for_deletion())
	t.eq(second.size(), 2)
	(second[0] as RpgShmupEnemy).take_hit(1)
	(second[1] as RpgShmupEnemy).queue_free()  # it got away
	await Fixtures.tree().process_frame
	t.eq(bonuses, [500], "no bonus for a formation that lost one")
	t.eq(mode.score.points, 900)
	# what a carrier releases is scored without a wave
	var extra := _enemy("popcorn")
	stage.adopt(extra, Vector2(10, 10))
	extra.take_hit(1)
	t.eq(mode.score.points, 1000)
	await Fixtures.tree().process_frame
	_drop(stage)
	_drop(mode)
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- power-ups and the shield

func test_a_power_up_raises_the_weapon_to_the_third_level_and_no_further(t) -> void:
	await Fixtures.tree().process_frame
	Fixtures.install_state()
	var mode := RpgShmupMode.new()
	Fixtures.tree().root.add_child(mode)
	mode.phase = RpgArcadeMode.Phase.PLAYING
	var ship := _ship()
	var weapon := ship.weapon()
	RpgShmupPowerup.apply("weapon_up", ship, mode)
	RpgShmupPowerup.apply("weapon_up", ship, mode)
	t.eq([weapon.level, mode.score.points], [3, 0])
	RpgShmupPowerup.apply("weapon_up", ship, mode)
	t.eq([weapon.level, mode.score.points], [3, 500], "at the third level a capsule is points")
	RpgShmupPowerup.apply("weapon:laser", ship, mode)
	t.eq([weapon.kind, weapon.level], ["laser", 3], "another weapon keeps the level")
	RpgShmupPowerup.apply("bomb", ship, mode)
	t.eq(ship.bomb().count, 4)
	RpgShmupPowerup.apply("life", ship, mode)
	t.eq(mode.lives.count, 4)
	mode.lives.count = RpgArcadeLives.MAX_LIVES
	RpgShmupPowerup.apply("life", ship, mode)
	t.eq([mode.lives.count, mode.score.points], [RpgArcadeLives.MAX_LIVES, 1000], "a life too many is points")
	RpgShmupPowerup.apply("points", ship, mode)
	t.eq(mode.score.points, 1500)
	RpgShmupPowerup.apply("weapon_up", null, null)  # nobody to give it to: nothing happens
	for kind in RpgShmupPowerup.KINDS:
		t.ok(RpgShmupPowerup.tint_of(kind).a == 1.0, kind)
	ship.free()
	_drop(mode)
	Fixtures.uninstall_state()

func test_the_shield_takes_one_hit(t) -> void:
	var ship := _ship()
	var seen: Array = []
	ship.shield_changed.connect(func(on: bool) -> void: seen.append(on))
	RpgShmupPowerup.apply("shield", ship, null)
	t.ok(ship.shielded)
	t.ok(not ship.hit(), "the shield takes the hit")
	t.ok(not ship.shielded and not ship.dead)
	t.eq(seen, [true, false])
	t.ok(ship.is_invulnerable(), "and the ship is safe for a moment")
	for i in 4:
		ship.advance(STEP)
	t.ok(not ship.is_invulnerable(), "half a second")
	t.ok(ship.hit() and ship.dead, "the next hit is the ship's")
	ship.free()

func test_a_capsule_drifts_to_the_ship_s_side_and_is_picked_up_by_a_touch(t) -> void:
	await Fixtures.tree().process_frame
	var holder := _field()
	var ship := _ship()
	holder.add_child(ship)
	ship.position = Vector2(0, 60)
	ship.advance(STEP)
	var capsule := EnemyRecipes.build_powerup([] as Array[Texture2D], "vertical", VIEW, 16) as RpgShmupPowerup
	capsule.auto_advance = false
	capsule.kind = "bomb"
	capsule.position = Vector2(0, -20)
	holder.add_child(capsule)
	t.eq([capsule.speed, capsule.pick_radius], [32.0, 14.4])
	var picked: Array = []
	capsule.picked.connect(func(kind: String) -> void: picked.append(kind))
	for i in 16:
		capsule.advance(STEP)
	t.eq(capsule.position, Vector2(0, 44), "down, to where the ship flies")
	t.eq(picked, [])
	capsule.advance(STEP)
	t.eq(picked, ["bomb"], "within reach of the ship")
	t.eq(ship.bomb().count, 4)
	t.ok(capsule.is_queued_for_deletion())
	var missed := EnemyRecipes.build_powerup([] as Array[Texture2D], "horizontal", VIEW, 16) as RpgShmupPowerup
	missed.auto_advance = false
	missed.position = Vector2(100, -80)
	holder.add_child(missed)
	for i in 80:
		missed.advance(STEP)
	t.ok(missed.position.x < -160.0 and missed.is_queued_for_deletion(), "one that is missed leaves by the ship's edge")
	_drop(holder)

# ---------------------------------------------------------------- the recipes

func test_the_first_stage_has_ten_waves_of_mixed_enemies(t) -> void:
	for way: String in ["vertical", "horizontal"]:
		var waves := StageRecipe.waves(way, Vector2(VIEW), 16, 3)
		t.eq(waves.size(), 10)
		var kinds := {}
		var ats: Array = []
		for raw: Variant in waves:
			var entry: Dictionary = raw
			var wave := RpgArcadeWave.from_dict(entry)
			kinds[wave.enemy] = int(kinds.get(wave.enemy, 0)) + 1
			ats.append(wave.at)
			t.eq(wave.trigger, "progress")
			t.ok(ResourceLoader.exists(wave.scene) or wave.scene.begins_with("res://generated/scenes/shmup/enemies/"), wave.scene)
			var front := RpgShmupMath.forward_of(way)
			if wave.anchor == "screen":
				t.near(wave.position.dot(front), (180.0 if way == "vertical" else 320.0) * 0.5 + 24.0, 0.001, "just beyond the front edge")
			else:
				t.ok(wave.enemy in ["turret", "asteroid"], "what sits in the stage is placed in the stage")
		t.eq(kinds, {"popcorn": 6, "turret": 2, "asteroid": 1, "carrier": 1})
		var sorted := ats.duplicate()
		sorted.sort()
		t.eq(ats, sorted, "in the order they come")
		t.ok(ats[9] < (180.0 if way == "vertical" else 320.0) * 6.0, "all before the end of the stage")
		var drops: Array = waves.filter(func(w: Dictionary) -> bool: return w.has("drop"))
		t.eq(drops.size(), 1)
		t.eq([drops[0]["id"], drops[0]["drop"]], ["w08", "weapon_up"], "the fifth formation of small enemies carries a power-up")
		var scenes: Array = []
		for w: Dictionary in waves:
			if w["enemy"] == "popcorn":
				scenes.append(String(w["scene"]).get_file())
				t.eq(w["bonus"], 500)
		t.eq(scenes, ["popcorn_01.tscn", "popcorn_02.tscn", "popcorn_03.tscn", "popcorn_01.tscn", "popcorn_02.tscn", "popcorn_03.tscn"], "the small enemies take turns")
	t.eq(StageRecipe.waves("vertical", Vector2(VIEW), 16, 3), StageRecipe.waves("vertical", Vector2(VIEW), 16, 3), "the same every time")

func test_the_recipes_build_the_enemy_scenes_and_share_out_the_pictures(t) -> void:
	var frames := SpriteFrames.new()
	for behaviour: String in ["popcorn", "turret", "asteroid", "carrier"]:
		var drawn := EnemyRecipes.build_enemy(behaviour, null, Vector2i(16, 16), false, "vertical", VIEW, 16, null, null)
		t.ok(drawn is RpgShmupEnemy, behaviour)
		t.ok(drawn.get_node("Visual") is Polygon2D, behaviour + ": a drawn shape without a picture")
		var packed := PackedScene.new()
		t.eq(packed.pack(drawn), OK)
		var again := packed.instantiate()
		t.eq(again.get_child_count(), 1, behaviour)
		again.free()
		drawn.free()
	var ship := EnemyRecipes.build_enemy("popcorn", frames, Vector2i(24, 24), true, "vertical", VIEW, 16, null, null)
	t.eq((ship.get_node("Visual") as Node2D).rotation, 0.0, "an enemy ship is drawn as it comes: looking down")
	t.near((ship as RpgShmupEnemy).hit_radius, 9.6, 0.001)
	ship.free()
	var side := EnemyRecipes.build_enemy("popcorn", frames, Vector2i(24, 24), true, "horizontal", VIEW, 16, null, null)
	t.near((side.get_node("Visual") as Node2D).rotation, PI * 0.5, 0.0001, "and is turned to look left in a game that scrolls right")
	side.free()
	var slime := EnemyRecipes.build_enemy("popcorn", frames, Vector2i(16, 16), false, "horizontal", VIEW, 16, null, null)
	t.eq((slime.get_node("Visual") as Node2D).rotation, 0.0, "what is no ship is not turned")
	slime.free()
	var big := EnemyRecipes.build_enemy("carrier", frames, Vector2i(24, 24), true, "vertical", VIEW, 16, null, null, 2.0)
	t.eq((big.get_node("Visual") as Node2D).scale, Vector2(2, 2), "a carrier made of the small enemy's picture")
	t.near((big as RpgShmupEnemy).hit_radius, 19.2, 0.001)
	big.free()
	var ctx := _ctx()
	t.eq(EnemyRecipes.roster(ctx), {"popcorn": [], "turret": {}, "asteroid": {}, "carrier": {}}, "a catalog without enemies")
	t.eq(EnemyRecipes.popcorn_count(ctx), 1, "one drawn small enemy at least")
	t.eq(EnemyRecipes.new().outputs(ctx), PackedStringArray([
		"res://generated/scenes/shmup/enemies/popcorn_01.tscn", "res://generated/scenes/shmup/enemies/turret.tscn",
		"res://generated/scenes/shmup/enemies/asteroid.tscn", "res://generated/scenes/shmup/enemies/carrier.tscn",
		"res://generated/scenes/shmup/powerup.tscn"]))
	var capsule := EnemyRecipes.build_powerup([] as Array[Texture2D], "vertical", VIEW, 16)
	t.ok(capsule is RpgShmupPowerup and capsule.get_node("Visual") is Sprite2D)
	capsule.free()
