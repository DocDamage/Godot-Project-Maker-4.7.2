extends RefCounted
## T16.09: the four guns of a run and gun and the pickup that swaps them, its five enemies, and
## a trap that stops the camera until it is destroyed.

const Fixtures := preload("../lib/fixtures.gd")
const Soldiers := preload("test_run_and_gun.gd")
const StageRecipe := preload("res://builder/recipes/run_and_gun/stage_recipe.gd")
const EnemyRecipes := preload("res://builder/recipes/run_and_gun/enemy_recipes.gd")
const RngBuild := preload("res://builder/recipes/run_and_gun/run_and_gun_build.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")

const TILE := 16
const VIEW := Vector2i(320, 180)
const FLOOR_Y := 9 * TILE
const PLAYER := RpgArcadeBulletPool.Team.PLAYER
const ENEMY := RpgArcadeBulletPool.Team.ENEMY

func _field(health: int = 1) -> Soldiers.Field:
	return await Soldiers.new()._field(health, false)

func _enemy(field: Soldiers.Field, behaviour: String, x: float, y: float = FLOOR_Y) -> RpgGunEnemy:
	var enemy := EnemyRecipes.build_enemy(behaviour, null, Vector2i(16, 24), Vector2i(8, 23), VIEW, TILE, null) as RpgGunEnemy
	enemy.position = Vector2(x, y)
	field.stage.entities().add_child(enemy)
	return enemy

# ---------------------------------------------------------------- the guns and the pickup

func test_each_gun_has_its_bullets_per_shot_and_its_reach(t) -> void:
	await Fixtures.tree().process_frame
	var pool := RpgArcadeBulletPool.new()
	pool.auto_advance = false
	Fixtures.tree().root.add_child(pool)
	var facts := {}
	for weapon: String in RpgSoldier.WEAPONS:
		var gun := Node.new()
		gun.set_script(load(RpgSoldier.WEAPONS[weapon]))
		var typed := gun as RpgGun
		t.ok(typed != null and typed.weapon == weapon, weapon)
		pool.clear(PLAYER)
		var sent := typed.shoot(pool, Vector2.ZERO, Vector2.RIGHT)
		# how far its bullets get in three seconds, with nothing in the way
		for i in 24:
			pool.advance(0.125, Rect2())
		var reach := 0.0
		for at in pool.positions(PLAYER):
			reach = maxf(reach, at.length())
		facts[weapon] = [sent, typed.rate, typed.pierce, typed.damage, pool.active(PLAYER), snappedf(reach, 1.0)]
		gun.free()
	t.eq(facts["machine_gun"], [1, 8.0, false, 1, 1, 720.0], "one bullet, fifteen tiles a second, as far as it flies")
	t.eq(facts["spread"], [5, 4.0, false, 1, 5, 672.0], "five bullets in a fan")
	t.eq(facts["laser"], [1, 3.0, true, 3, 1, 1344.0], "a beam: fast, strong, through everything")
	t.eq(facts["flame"], [1, 20.0, true, 1, 0, 0.0], "a flame is gone after four tiles")
	var flame := RpgFlameGun.new()
	t.eq([flame.range_px(), flame.bullet_speed()], [64.0, 144.0])
	pool.clear(PLAYER)
	flame.shoot(pool, Vector2.ZERO, Vector2.RIGHT)
	pool.advance(0.25, Rect2())
	t.eq(pool.active(PLAYER), 1, "36 px out")
	pool.advance(0.25, Rect2())
	t.eq(pool.active(PLAYER), 0, "past its four tiles")
	var fan := RpgSpreadGun.new().volley(Vector2.RIGHT)
	t.near(rad_to_deg(fan[0].angle_to(fan[4])), 40.0, 0.001, "forty degrees wide")
	flame.free()
	pool.get_parent().remove_child(pool)
	pool.free()

func test_a_pickup_swaps_the_gun_and_a_death_loses_it(t) -> void:
	var field: Soldiers.Field = await _field()
	var soldier := field.soldier
	t.eq(soldier.weapon(), "machine_gun", "what a soldier starts with")
	var changes: Array = []
	soldier.weapon_changed.connect(func(w: String) -> void: changes.append(w))
	t.ok(soldier.equip("spread"))
	t.eq([soldier.weapon(), soldier.gun().bullets_per_shot, soldier.gun().tile], ["spread", 5, 16.0])
	t.ok(soldier.equip("spread") and changes == ["spread"], "the same weapon again changes nothing")
	t.ok(not soldier.equip("banana") and soldier.weapon() == "spread")
	soldier.shooting = true
	await field.frames(3)
	t.eq(field.pool.active(PLAYER), 5, "the new gun fires at once")
	soldier.shooting = false
	soldier.die()
	t.eq(soldier.weapon(), "machine_gun", "a death costs the weapon")
	soldier.respawn()
	soldier.keep_weapon = true
	soldier.equip("laser")
	soldier.die()
	t.eq(soldier.weapon(), "laser", "unless the options keep it")
	field.drop()
	# the pickup on its carrier: shot, it falls and lies; touched, it is taken
	var other: Soldiers.Field = await _field()
	var pickup := EnemyRecipes.build_pickup({}, VIEW, TILE) as RpgWeaponPickup
	pickup.auto_advance = false
	pickup.weapon = "flame"
	pickup.position = Vector2(200, 60)
	other.stage.entities().add_child(pickup)
	t.ok(pickup.is_in_group(RpgArcadeBulletPool.TARGET_GROUP), "the carrier can be shot")
	for i in 8:
		pickup.advance(0.125)
	t.eq(pickup.position.x, 200.0 - 60.0, "it flies to the left")
	t.ok(pickup.position.y != 60.0, "weaving")
	pickup.take_hit(1)
	t.eq(pickup.state, RpgWeaponPickup.State.FALLING)
	t.ok(not pickup.is_in_group(RpgArcadeBulletPool.TARGET_GROUP))
	for i in 40:
		if pickup.state == RpgWeaponPickup.State.LYING:
			break
		pickup.advance(0.05)
	t.eq(pickup.state, RpgWeaponPickup.State.LYING, "it lies on the ground")
	t.near(pickup.position.y, FLOOR_Y - 8.0, 6.0)
	var picked: Array = []
	pickup.picked.connect(func(w: String) -> void: picked.append(w))
	other.soldier.position = Vector2(pickup.position.x, FLOOR_Y)
	await other.frames(2)
	pickup.advance(0.05)
	t.eq(picked, ["flame"])
	t.eq(other.soldier.weapon(), "flame")
	t.ok(pickup.is_queued_for_deletion())
	var missed := EnemyRecipes.build_pickup({}, VIEW, TILE) as RpgWeaponPickup
	missed.auto_advance = false
	missed.position = Vector2(100, 60)
	other.stage.entities().add_child(missed)
	missed.spawned_in_wave(RpgArcadeWave.from_dict({"weapon": "laser"}), 0)
	t.eq(missed.weapon, "laser", "the wave says which weapon it carries")
	for i in 40:
		missed.advance(0.125)
	t.ok(missed.is_queued_for_deletion(), "a carrier that is not shot flies off with it")
	other.drop()

# ---------------------------------------------------------------- the enemies

func test_a_runner_charges_and_jumps_at_the_soldier(t) -> void:
	var field: Soldiers.Field = await _field()
	var runner := _enemy(field, "runner", 250.0) as RpgRunnerEnemy
	t.eq([runner.health, runner.points], [1, 100])
	t.ok(runner.is_in_group(RpgArcadeBulletPool.TARGET_GROUP))
	await field.frames(30)
	t.ok(runner.position.x < 250.0 - 40.0 and runner.facing == -1, "half a second of charging to the left")
	var top := runner.position.y
	for i in 120:
		await Fixtures.tree().physics_frame
		if is_instance_valid(runner):
			top = minf(top, runner.position.y)
		if field.soldier.dead:
			break
	t.ok(top < FLOOR_Y - TILE, "near the soldier it jumps at it")
	t.ok(field.soldier.dead, "and its touch is a death")
	field.drop()

func test_a_sniper_warns_and_fires_one_shot_at_the_soldier(t) -> void:
	var field: Soldiers.Field = await _field()
	var sniper := _enemy(field, "sniper", 280.0) as RpgSniperEnemy
	var warned := [0]
	sniper.telegraphed.connect(func() -> void: warned[0] += 1)
	await field.frames(100)
	t.near(sniper.position.x, 280.0, 0.5, "it stands")
	t.eq([sniper.facing, warned[0], sniper.shots], [-1, 0, 0], "it faces the soldier and waits")
	await field.frames(20)
	t.eq([warned[0], sniper.aiming, sniper.shots], [1, true, 0], "the warning, 0.6 s before the shot")
	await field.frames(40)
	t.eq([sniper.shots, sniper.aiming], [1, false], "one shot every two and a half seconds")
	var shot := field.pool.positions(ENEMY)
	t.eq(shot.size(), 1)
	t.ok(shot[0].x < 280.0 and absf(shot[0].y - sniper.hit_center().y) < 4.0, "flying at the soldier, who stands as high")
	# a soldier beyond its range is left alone
	sniper.range_tiles = 2.0
	await field.frames(200)
	t.eq(sniper.shots, 1)
	field.drop()

func test_a_turret_fires_a_fan_and_takes_several_hits(t) -> void:
	var field: Soldiers.Field = await _field(5)
	var turret := _enemy(field, "turret", 260.0) as RpgGunTurret
	turret.spawned_in_wave(RpgArcadeWave.from_dict({"fan": 5, "tough": 2, "fast": 2.0}), 0)
	t.eq([turret.health, turret.fan_count, turret.bullet_speed], [8, 5, 220.0], "what the wave makes of it")
	await field.frames(119)
	t.eq(turret.shots, 0)
	await field.frames(3)
	t.eq(turret.shots, 5, "a fan every two seconds")
	t.near(turret.position.x, 260.0, 0.5)
	var killed := [0]
	turret.defeated.connect(func() -> void: killed[0] += 1)
	field.pool.fire(PLAYER, Vector2(200, turret.hit_center().y), Vector2.RIGHT * 240.0, 3)
	await field.frames(30)
	t.eq([turret.health, killed[0]], [5, 0], "a bullet hits it")
	turret.take_hit(5)
	t.eq(killed[0], 1)
	t.ok(turret.is_queued_for_deletion())
	field.drop()

func test_a_jumper_hops_toward_the_soldier(t) -> void:
	var field: Soldiers.Field = await _field()
	var jumper := _enemy(field, "jumper", 280.0) as RpgJumperEnemy
	var grounded := 0
	var airborne := 0
	var floor_moves := 0
	var last_x := 280.0
	for i in 150:
		await Fixtures.tree().physics_frame
		if not is_instance_valid(jumper) or field.soldier.dead:
			break
		if jumper.is_on_floor():
			grounded += 1
			if absf(jumper.position.x - last_x) > 0.5:
				floor_moves += 1
		else:
			airborne += 1
		last_x = jumper.position.x
	t.ok(jumper.hops >= 2, "a hop a second: %d" % jumper.hops)
	t.ok(grounded > 20 and airborne > 20, "on the floor and in the air in turn")
	t.ok(jumper.position.x < 280.0 - 20.0, "toward the soldier")
	t.ok(floor_moves <= jumper.hops * 2, "it moves only while it is in the air (but for the frame it takes off or lands in): %d" % floor_moves)
	field.drop()

func test_a_wall_cannon_is_shut_opens_fires_and_can_be_hit_while_open(t) -> void:
	var field: Soldiers.Field = await _field(5)
	var cannon := _enemy(field, "wall_cannon", 260.0, FLOOR_Y - 40.0) as RpgWallCannon
	var events: Array = []
	cannon.opened.connect(func() -> void: events.append("open"))
	cannon.closed.connect(func() -> void: events.append("shut"))
	await field.frames(60)
	t.eq(cannon.position, Vector2(260, FLOOR_Y - 40.0), "part of the scenery: it does not fall")
	t.ok(not cannon.open and not cannon.vulnerable())
	cannon.take_hit(99)
	t.eq(cannon.health, 5, "shut, nothing hurts it")
	await field.frames(125)
	t.eq(events, ["open"], "it opens every three seconds")
	t.eq(cannon.shots, 0)
	await field.frames(35)
	t.eq(cannon.shots, 1, "and fires once while it is open")
	cannon.take_hit(2)
	t.eq(cannon.health, 3, "open, it can be hit")
	await field.frames(50)
	t.eq(events, ["open", "shut"])
	t.ok(not cannon.open)
	field.drop()

# ---------------------------------------------------------------- waves and the camera

func test_a_trap_stops_the_camera_until_it_is_destroyed(t) -> void:
	var field: Soldiers.Field = await _field()
	Fixtures.install_state()
	var plan := {"axis": "right", "speed": 0.0, "length": 320.0, "exit": "reach_end", "waves": [
		{"id": "runners", "enemy": "runner", "count": 2, "gap": 32, "trigger": "progress", "at": 20, "anchor": "stage", "position": [420, FLOOR_Y]},
		{"id": "trap", "enemy": "turret", "count": 2, "gap": 48, "trigger": "progress", "at": 100, "anchor": "stage", "position": [360, FLOOR_Y], "blocking": true},
	]}
	field.stage.enemy_factory = func(wave: RpgArcadeWave) -> Node2D:
		return EnemyRecipes.build_enemy(wave.enemy, null, Vector2i(16, 24), Vector2i(8, 23), VIEW, TILE, null)
	field.stage.setup(plan)
	var mode := RpgRunAndGunMode.new()
	mode.auto_screens = true
	mode.sequence = RpgArcadeStageSequence.from_array([plan])
	Fixtures.tree().root.add_child(mode)
	mode.bind_stage(field.stage)
	var soldier := field.soldier
	var scroll := field.stage.scroller()
	soldier.set("_safe_left", 600.0)
	soldier.move_x = 1.0
	var runners: Array = []
	for i in 400:
		await Fixtures.tree().physics_frame
		runners = field.stage.entities().get_children().filter(func(n: Node) -> bool: return n is RpgRunnerEnemy)
		if not runners.is_empty():
			break
	t.eq(runners.size(), 2, "the runners come when the camera has gone 20 px")
	t.near((runners[1] as Node2D).position.x - (runners[0] as Node2D).position.x, 32.0, 0.5, "in a line on the ground")
	for runner: RpgRunnerEnemy in runners:
		runner.take_hit(1)
	t.eq(mode.score.points, 200)
	for i in 600:
		await Fixtures.tree().physics_frame
		if scroll.is_held():
			break
	t.ok(scroll.is_held(), "the trap holds the camera")
	t.near(scroll.progress, 100.0, 3.0)
	var held_at := scroll.progress
	await field.frames(120)
	t.eq(scroll.progress, held_at, "however far the soldier runs")
	t.near(soldier.position.x, held_at + 320.0 - soldier.body_width() * 0.5, 1.0, "the right edge of the screen stops it")
	var turrets: Array = field.stage.entities().get_children().filter(func(n: Node) -> bool: return n is RpgGunTurret)
	t.eq(turrets.size(), 2)
	for turret: RpgGunTurret in turrets:
		t.ok(turret.position.x < held_at + 320.0, "the trap stands on the screen")
	(turrets[0] as RpgGunTurret).die()
	await field.frames(5)
	t.ok(scroll.is_held(), "one turret is left")
	(turrets[1] as RpgGunTurret).die()
	await field.frames(5)
	t.ok(not scroll.is_held(), "destroyed, the camera is free")
	await field.frames(60)
	t.ok(scroll.progress > held_at, "and follows again")
	mode.get_parent().remove_child(mode)
	mode.free()
	field.drop()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the recipes

func test_the_recipes_build_the_enemies_and_the_first_stage_has_its_waves(t) -> void:
	for behaviour in EnemyRecipes.BEHAVIOURS:
		var enemy := EnemyRecipes.build_enemy(behaviour, null, Vector2i(16, 24), Vector2i(8, 23), VIEW, TILE, null)
		t.ok(enemy is RpgGunEnemy, behaviour)
		t.ok(enemy.get_node_or_null("Shape") is Polygon2D, behaviour + ": a drawn shape without a picture")
		t.ok(enemy.get_collision_layer_value(3) and enemy.get_collision_mask_value(1), behaviour)
		t.eq((enemy as RpgGunEnemy).fixed, behaviour == "wall_cannon", behaviour)
		enemy.free()
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"archetype": "run_and_gun", "resolution": [VIEW.x, VIEW.y], "base_tile_size": TILE}
	var who := EnemyRecipes.roster(ctx)
	t.eq(who.keys(), ["runner", "sniper", "turret", "jumper", "wall_cannon"])
	t.eq(EnemyRecipes.pickup_assets(ctx), {})
	t.eq(EnemyRecipes.new().outputs(ctx).size(), 9, "five enemies, the pickup and three bosses")
	var waves := StageRecipe.waves(VIEW, TILE)
	t.eq(waves.size(), 9)
	var kinds := {}
	for raw: Variant in waves:
		var entry: Dictionary = raw
		kinds[entry["enemy"]] = int(kinds.get(entry["enemy"], 0)) + 1
		var wave := RpgArcadeWave.from_dict(entry)
		t.eq([wave.trigger, wave.anchor], ["progress", "stage"])
		var first_x := wave.position.x - (wave.count - 1) * wave.gap * 0.5
		if wave.blocking:
			t.ok(first_x > wave.at + 160.0 and first_x < wave.at + 320.0, "a trap stands on the screen")
		else:
			t.eq(first_x, wave.at + 320.0 + 24.0, "just beyond the right edge")
	t.eq(kinds, {"runner": 2, "sniper": 1, "pickup": 3, "jumper": 1, "turret": 1, "wall_cannon": 1})
	var weapons: Array = waves.filter(func(w: Dictionary) -> bool: return w["enemy"] == "pickup").map(func(w: Dictionary) -> String: return w["weapon"])
	t.eq(weapons, ["spread", "laser", "flame"], "the three other guns, one after another")
	t.eq((waves[2] as Dictionary)["scene"], RngBuild.PICKUP_PATH)
	t.eq((waves[0] as Dictionary)["scene"], "res://generated/scenes/run_and_gun/enemies/runner.tscn")
	var pickup := EnemyRecipes.build_pickup({}, VIEW, TILE)
	t.ok(pickup is RpgWeaponPickup and pickup.get_node("Visual") is Sprite2D)
	pickup.free()

# ---------------------------------------------------------------- the bosses and the plan (T16.10)

func _boss(field: Soldiers.Field, kind: String, at: Vector2) -> RpgGunBoss:
	var boss := EnemyRecipes.build_boss(kind, null, Vector2i(48, 48), VIEW, TILE, null) as RpgGunBoss
	boss.auto_advance = false
	boss.intro_s = 0.25
	boss.defeat_s = 0.25
	boss.position = at
	field.stage.entities().add_child(boss)
	return boss

func test_the_three_bosses_stand_walk_and_fly_and_fire_their_attacks(t) -> void:
	var field: Soldiers.Field = await _field(5)
	var soldier := field.soldier
	var phases := [
		{"until": 0.5, "movement": "still", "attacks": ["aimed"], "interval": 1.0, "telegraph_s": 0.25, "count": 2, "fast": 1.0},
		{"until": 0.0, "movement": "still", "attacks": ["fan"], "interval": 1.0, "telegraph_s": 0.25, "count": 5, "fast": 2.0},
	]
	var wall := _boss(field, "wall", Vector2(280, FLOOR_Y))
	t.eq([wall.kind, wall.hit_radius, wall.bullet_speed, wall.walk_px], ["wall", 21.6, 110.0, 96.0])
	t.ok(wall.is_in_group(RpgArcadeBulletPool.TARGET_GROUP))
	t.eq(wall.hit_center(), wall.global_position + Vector2(0, -21.6), "its feet are on the floor: what is hit is above them")
	wall.setup({"kind": "wall", "health": 40, "points": 5000, "phases": phases})
	wall.begin()
	wall.take_hit(10)
	t.eq(wall.health, 40, "it cannot be hurt during its intro")
	wall.advance(0.25)
	for i in 8:
		wall.advance(0.125)
	t.eq(field.pool.active(ENEMY), 2, "two aimed shots after a second")
	t.eq(wall.position, Vector2(280, FLOOR_Y), "a wall stands")
	field.pool.advance(0.25, Rect2())
	for at in field.pool.positions(ENEMY):
		t.ok(at.x < 280.0, "toward the soldier")
	field.pool.clear(ENEMY)
	# the soldier's bullets hit it, and at half its health the second phase begins
	field.pool.fire(PLAYER, Vector2(200, FLOOR_Y - 20), Vector2.RIGHT * 240.0, 20)
	await field.frames(30)
	t.eq([wall.health, wall.phase_index()], [20, 1])
	t.eq(wall.volley("fan").size(), 5)
	t.near(wall.volley("fan")[0].length(), 220.0, 0.001, "twice as fast")
	t.eq([wall.volley("burst").size(), wall.volley("rain").size(), wall.volley("ring").size(), wall.volley("aimed").size()], [15, 5, 5, 5])
	for velocity in wall.volley("rain"):
		t.ok(velocity.y > 0.0, "rain falls")
	var events: Array = []
	wall.defeated.connect(func() -> void: events.append("defeated"))
	wall.take_hit(99)
	t.eq(events, ["defeated"])
	t.ok(not wall.is_in_group(RpgArcadeBulletPool.TARGET_GROUP))
	wall.advance(0.25)
	t.ok(wall.is_queued_for_deletion())
	# the walker goes out to the left and comes back; the flyer sweeps in the air
	var walker := _boss(field, "walker", Vector2(280, FLOOR_Y))
	walker.setup({"kind": "walker", "health": 40, "phases": [{"until": 0.0, "movement": "walk", "attacks": [], "speed": 1.0}]})
	walker.begin()
	walker.advance(0.25)
	var xs: Array = []
	for i in 32:
		walker.advance(0.125)
		xs.append(walker.position.x)
	t.near(xs[15], 280.0 - 96.0, 0.01, "two seconds out: as far as it walks")
	t.near(xs[31], 280.0, 0.01, "and two back")
	t.near(xs[7] - xs[6], xs[1] - xs[0], 0.001, "at a steady pace")
	t.eq(walker.position.y, float(FLOOR_Y), "on the floor")
	var flyer := _boss(field, "flyer", Vector2(200, 40))
	flyer.setup({"kind": "flyer", "health": 40, "phases": [{"until": 0.0, "movement": "sweep", "attacks": ["rain"], "interval": 1.0, "count": 4}]})
	t.eq(flyer.hit_center(), flyer.global_position, "what is hit is its middle")
	flyer.begin()
	flyer.advance(0.25)
	var left := 200.0
	var right := 200.0
	for i in 60:
		flyer.advance(0.125)
		left = minf(left, flyer.position.x)
		right = maxf(right, flyer.position.x)
	t.ok(left < 200.0 - 50.0 and right > 200.0 + 50.0, "it sweeps to both sides")
	t.ok(absf(flyer.position.y - 40.0) <= 6.0, "and stays in the air")
	# a touch of a boss hurts the soldier
	soldier.position = Vector2(walker.position.x, FLOOR_Y)
	await field.frames(2)
	walker.advance(0.125)
	t.eq(soldier.health, 4)
	field.drop()

func test_spikes_hurt_the_soldier(t) -> void:
	var field: Soldiers.Field = await _field(3)
	var soldier := field.soldier
	var ground := field.stage.get_node("Ground") as TileMapLayer
	ground.set_cell(Vector2i(8, 8), 0, Soldiers.PlatformTests.HAZARD)
	t.ok(not soldier.touching_hazard())
	soldier.position = Vector2(8.5 * TILE, FLOOR_Y)
	await field.frames(3)
	t.eq(soldier.health, 2, "a tile of spikes costs a hit")
	t.ok(soldier.is_invulnerable(), "and leaves a moment to step off them")
	await field.frames(10)
	t.eq(soldier.health, 2)
	field.drop()

func test_the_stage_of_a_plan_is_painted_from_its_tiles(t) -> void:
	var rows: Array = []
	for y in 12:
		rows.append("..........")
	rows[7] = "....==...."
	rows[8] = ".......^.."
	rows[9] = "###..#####"
	rows[10] = "###..#####"
	rows[11] = "###..#####"
	var tile_set := Soldiers.PlatformTests.tileset()
	var tile := func(coords: Vector2i) -> Dictionary: return {"source_id": 0, "coords": coords}
	var kit := {"top": tile.call(Soldiers.PlatformTests.GROUND), "fill": tile.call(Soldiers.PlatformTests.GROUND),
		"one_way": [tile.call(Soldiers.PlatformTests.ONE_WAY), tile.call(Soldiers.PlatformTests.ONE_WAY), tile.call(Soldiers.PlatformTests.ONE_WAY)],
		"ladder": {}, "hazard": tile.call(Soldiers.PlatformTests.HAZARD), "breakable": {}}
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"archetype": "run_and_gun", "resolution": [VIEW.x, VIEW.y], "base_tile_size": TILE}
	var stage := {"axis": "right", "speed": 0.0, "length": 0.0, "exit": "reach_end", "start": [24.0, 144.0]}
	var root := StageRecipe.build_stage(ctx, 1, stage, tile_set, kit, rows) as RpgArcadeStage
	t.ok(root != null and root.stage_index == 1)
	var ground := root.get_node("Ground") as TileMapLayer
	var platforms := root.get_node("Platforms") as TileMapLayer
	var hazards := root.get_node("Hazards") as TileMapLayer
	t.eq(ground.get_used_cells().size(), 24, "three rows of ground with a gap two wide")
	t.eq(ground.get_cell_source_id(Vector2i(3, 9)), -1, "the gap has no bottom")
	t.eq(platforms.get_used_cells(), [Vector2i(4, 7), Vector2i(5, 7)] as Array[Vector2i])
	t.eq(hazards.get_used_cells(), [Vector2i(7, 8)] as Array[Vector2i])
	t.ok(ground.collision_enabled and platforms.collision_enabled and not hazards.collision_enabled)
	t.eq(root.get_spawn(&"default").position, Vector2(24, 144), "the start of the plan")
	t.eq((root.get_node("Bullets") as RpgArcadeBulletPool).wall_mask, 1)
	root.free()
	t.eq(StageRecipe.stored_plan(), [], "the template project has no stored plan")
	t.eq(StageRecipe.plan(ctx).size(), 1, "so one flat stage")
	for kind in RngBuild.BOSS_KINDS:
		var boss := EnemyRecipes.build_boss(kind, null, Vector2i(48, 48), VIEW, TILE, null)
		t.ok(boss is RpgGunBoss and (boss as RpgGunBoss).kind == kind, kind)
		t.eq((boss.get_node("Visual") as Node2D).position, Vector2.ZERO if kind == "flyer" else Vector2(0, -24), kind)
		boss.free()
	t.eq([RngBuild.boss_path("flyer"), RngBuild.boss_path("nobody")],
		["res://generated/scenes/run_and_gun/boss_flyer.tscn", "res://generated/scenes/run_and_gun/boss_wall.tscn"])
