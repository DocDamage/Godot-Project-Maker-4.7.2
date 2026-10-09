extends RefCounted
## T14.07: the side-view enemies in a room made in code: the patrol turns at an edge and at a
## wall, the flyer chases and goes home, the shooter fires on sight only, the guardian's phases
## and what its defeat does, and that a defeated enemy stays away until the flag is cleared.

const Fixtures := preload("../lib/fixtures.gd")
const PlatformTests := preload("test_platform_actor.gd")
const EnemyRecipes := preload("res://builder/recipes/metroidvania/enemy_recipes.gd")
const RoomsRecipe := preload("res://builder/recipes/metroidvania/rooms_recipe.gd")
const SeedUtil := preload("res://builder/lib/seed_util.gd")

const TILE := 16
const FRAME := Vector2i(16, 16)
const FLOOR_Y := 10

func _room(floor_to: int = 40, x: float = 3.0) -> PlatformTests.Room:
	return await PlatformTests.new()._room(floor_to, x)

func _definition(kind: String, index: int = 0) -> Resource:
	return EnemyRecipes.definition({"slug": "crawler", "kind": kind, "index": index, "asset": {"id": "p.enemies.crawler_walk"}}, null, TILE)

## An enemy of `kind` in the room, its feet on the floor of column `x` (a flyer `up` tiles above).
func _enemy(room: PlatformTests.Room, kind: String, x: float, id: String = "room_02_enemy_001", up: float = 0.0) -> RpgSideEnemy:
	var def := _definition(kind)
	var node := EnemyRecipes.build_enemy({"slug": "crawler", "kind": kind, "index": 0}, null, FRAME, Vector2i(8, 15), TILE, def) as RpgSideEnemy
	node.entity_id = id
	node.position = Vector2((x + 0.5) * TILE, (FLOOR_Y - up) * TILE)
	room.root.add_child(node)
	return node

func _state(hp: int = 20) -> RpgGameState:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion")}) as RpgGameState
	state.player_stats.max_hp = hp
	state.player_stats.hp = hp
	state.player_stats.attack = 2
	state.player_stats.defense = 0
	state.player_stats.extra = {"crit_chance": 0.0}
	return state

# ---------------------------------------------------------------- the recipe

func test_the_kind_comes_from_the_tags_and_the_name(t) -> void:
	t.eq(EnemyRecipes.kind_for("crawler_walk"), "patrol")
	t.eq(EnemyRecipes.kind_for("bat_idle"), "flyer")
	t.eq(EnemyRecipes.kind_for("slime", ["fly"]), "flyer")
	t.eq(EnemyRecipes.kind_for("ghost_bird"), "flyer")
	t.eq(EnemyRecipes.kind_for("turret_a"), "shooter")
	t.eq(EnemyRecipes.kind_for("skeleton_archer"), "shooter")
	t.eq(EnemyRecipes.kind_for("slime", ["shoot"]), "shooter")
	t.eq(EnemyRecipes.kind_for("batman"), "patrol", "whole words only")
	t.eq(EnemyRecipes.display_name("crawler_walk"), "Crawler")

func test_definitions_and_scenes(t) -> void:
	var def := _definition("patrol", 2) as RpgEnemyDefinition
	t.eq([def.base_stats.max_hp, def.base_stats.attack, def.xp_reward, def.gold_reward], [5, 3, 8, 4])
	t.eq(def.behavior, {"kind": "patrol"})
	t.eq(def.display_name, "Crawler")
	t.ok(def.loot != null and def.loot.entries.size() == 1)
	var boss := _definition("guardian") as RpgEnemyDefinition
	t.eq(boss.base_stats.max_hp, 20, "20 HP at 16 px tiles")
	t.eq(boss.display_name, "Guardian")
	var double := EnemyRecipes.definition({"slug": "guardian", "kind": "guardian", "index": 0, "asset": {"id": "p.boss"}}, null, 32) as RpgEnemyDefinition
	t.eq(double.base_stats.max_hp, 40, "scaled by the tile size")
	for kind: String in ["patrol", "flyer", "shooter", "guardian"]:
		var node := EnemyRecipes.build_enemy({"slug": "e", "kind": kind, "index": 0}, null, FRAME, Vector2i(8, 15), TILE, _definition(kind))
		t.ok(node is RpgSideEnemy, kind)
		t.ok(node.get_collision_layer_value(3) and node.get_collision_mask_value(1) and node.get_collision_mask_value(11), "an enemy on the floor")
		for part: String in ["Visual", "Body", "Components/Stats", "Health", "Hurtbox", "AttackHitbox", "Persistent"]:
			t.ok(node.get_node_or_null(part) != null, "%s: %s" % [kind, part])
		var hitbox := node.get_node("AttackHitbox") as RpgHitbox
		t.ok(hitbox.team == &"enemy" and hitbox.get_collision_layer_value(8) and hitbox.get_collision_mask_value(9))
		node.free()
	t.ok(EnemyRecipes.build_enemy({"slug": "e", "kind": "flyer", "index": 0}, null, FRAME, Vector2i(8, 15), TILE, _definition("flyer")) is RpgFlyerEnemy)
	# the kind written in the definition wins over the one detected (it is the user's to change)
	var changed := _definition("patrol") as RpgEnemyDefinition
	changed.behavior = {"kind": "shooter"}
	var as_shooter := EnemyRecipes.build_enemy({"slug": "e", "kind": "patrol", "index": 0}, null, FRAME, Vector2i(8, 15), TILE, changed)
	t.ok(as_shooter is RpgShooterEnemy)
	as_shooter.free()
	var big := EnemyRecipes.build_enemy({"slug": "guardian", "kind": "guardian", "index": 0, "scale": 1.5}, null, FRAME, Vector2i(8, 15), TILE, boss)
	t.eq((big.get_node("Visual") as Node2D).scale, Vector2(1.5, 1.5), "an ordinary enemy as the guardian is drawn larger")
	big.free()

# ---------------------------------------------------------------- patrol

func test_the_patrol_turns_at_an_edge_and_at_a_wall(t) -> void:
	_state()
	var room: PlatformTests.Room = await _room(20, 1.0)  # the floor ends at column 20
	room.fill(PlatformTests.GROUND, Vector2i(10, FLOOR_Y - 3), Vector2i(10, FLOOR_Y - 1))  # a wall
	var enemy := _enemy(room, "patrol", 14.0) as RpgPatrolEnemy
	enemy.start_direction = 1
	enemy.direction = 1
	await room.frames(20)
	t.ok(enemy.is_on_floor() and enemy.direction == 1, "walking right")
	var turned := false
	var rightmost := 0.0
	for i in 400:
		await room.frames(1)
		rightmost = maxf(rightmost, enemy.position.x)
		if enemy.direction == -1:
			turned = true
			break
	t.ok(turned, "it turned at the edge")
	t.ok(rightmost < 21.0 * TILE and rightmost > 19.0 * TILE, "at the last tile of the floor: %.1f" % rightmost)
	t.ok(enemy.is_on_floor(), "and did not fall")
	t.eq(enemy.facing, -1)
	var leftmost := 99999.0
	turned = false
	for i in 600:
		await room.frames(1)
		leftmost = minf(leftmost, enemy.position.x)
		if enemy.direction == 1:
			turned = true
			break
	t.ok(turned, "it turned at the wall")
	t.ok(leftmost > 11.0 * TILE and leftmost < 12.2 * TILE, "beside the wall: %.1f" % leftmost)
	room.close()
	Fixtures.uninstall_state()

func test_an_enemy_hurts_on_contact_and_is_knocked_back_by_a_hit(t) -> void:
	var state := _state()
	var room: PlatformTests.Room = await _room(40, 6.0)
	var enemy := _enemy(room, "shooter", 6.4)  # it stands still: range 0 here
	(enemy as RpgShooterEnemy).range_tiles = 0.0
	await room.frames(40)
	t.ok(state.player_stats.hp < 20, "touching it hurts")
	# the player steps away, gets its breath back, and strikes from a blade's length
	room.stand_at(2.0)
	room.player.hurtbox.make_invulnerable(5.0)
	await room.frames(45)
	var hp := state.player_stats.hp
	room.stand_at(5.4)
	room.player.set_facing(1)
	await room.frames(3)
	var before := enemy.health.hp()
	t.ok(room.player.press_attack(), "the swing starts")
	var pushed := false
	for i in 24:
		await room.frames(1)
		if enemy.velocity.x > 1.0:
			pushed = true
	t.eq(enemy.health.hp(), before - 2, "the player's attack (2) against no defense")
	t.ok(pushed, "knocked back along the floor, away from the player")
	t.ok(state.player_stats.hp <= hp)
	room.close()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- flyer

func test_the_flyer_chases_within_five_tiles_and_returns_to_its_anchor(t) -> void:
	_state()
	var room: PlatformTests.Room = await _room(60, 3.0)
	var flyer := _enemy(room, "flyer", 20.0, "room_02_enemy_002", 4.0) as RpgFlyerEnemy
	var home := flyer.position
	await room.frames(30)
	t.ok(not flyer.chasing, "the player is far away")
	t.ok(flyer.position.distance_to(home) <= flyer.hover_px + 1.5, "it hovers at its anchor")
	t.ok(not flyer.is_on_floor(), "and does not fall")
	room.stand_at(17.0)  # within five tiles
	await room.frames(40)
	t.ok(flyer.chasing, "it comes for the player")
	t.ok(flyer.position.distance_to(home) > TILE, "it left its anchor")
	t.ok(flyer.position.x < home.x, "toward the player")
	room.stand_at(3.0)  # gone again
	await room.frames(150)
	t.ok(not flyer.chasing)
	t.ok(flyer.position.distance_to(home) <= flyer.hover_px + 2.0, "back home: %.1f px away" % flyer.position.distance_to(home))
	room.close()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- shooter

func test_the_shooter_fires_on_sight_only(t) -> void:
	_state()
	var room: PlatformTests.Room = await _room(60, 3.0)
	var shooter := _enemy(room, "shooter", 20.0, "room_02_enemy_003") as RpgShooterEnemy
	await room.frames(110)
	t.eq(shooter.shots, 0, "17 tiles away: out of range")
	room.stand_at(14.0)  # six tiles away, nothing between them
	room.player.hurtbox.make_invulnerable(30.0)
	await room.frames(20)
	t.ok(shooter.sees(room.player))
	t.eq(shooter.facing, -1, "it looks at the player")
	await room.frames(100)
	t.ok(shooter.shots >= 1, "it fires")
	t.ok(shooter.last_shot.team == &"enemy" and shooter.last_shot.velocity.x < 0.0, "at the player")
	var count := shooter.shots
	await room.frames(95)
	t.eq(shooter.shots, count + 1, "every 1.5 s")
	# a wall between them: no line of sight, no shot
	room.fill(PlatformTests.GROUND, Vector2i(17, FLOOR_Y - 4), Vector2i(17, FLOOR_Y - 1))
	await room.frames(4)
	t.ok(not shooter.sees(room.player), "a wall is in the way")
	count = shooter.shots
	await room.frames(120)
	t.eq(shooter.shots, count, "it holds its fire")
	room.close()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the guardian

func test_the_guardian_phases_change_at_the_thresholds(t) -> void:
	t.eq(RpgGuardian.phase_for(20, 20), 1)
	t.eq(RpgGuardian.phase_for(14, 20), 1, "above two thirds")
	t.eq(RpgGuardian.phase_for(13, 20), 2)
	t.eq(RpgGuardian.phase_for(7, 20), 2, "above one third")
	t.eq(RpgGuardian.phase_for(6, 20), 3)
	t.eq(RpgGuardian.phase_for(1, 20), 3)
	t.eq(RpgGuardian.phase_for(5, 0), 1)
	_state()
	var room: PlatformTests.Room = await _room(60, 3.0)
	var guardian := _enemy(room, "guardian", 30.0, "room_02_guardian") as RpgGuardian
	await room.frames(10)
	var phases: Array = []
	guardian.phase_changed.connect(func(phase: int) -> void: phases.append(phase))
	var blow := RpgDamageInfo.new()
	blow.amount = 7
	guardian.health.take(blow)
	t.eq([guardian.phase, phases], [2, [2]], "13 of 20")
	guardian.health.take(blow)
	t.eq([guardian.phase, phases], [3, [2, 3]], "6 of 20")
	t.near(guardian.speed_factor(), 1.5, 0.001, "the last phase is faster")
	room.close()
	Fixtures.uninstall_state()

func test_the_guardian_telegraphs_lunges_and_slams(t) -> void:
	_state()
	var room: PlatformTests.Room = await _room(60, 20.0)
	room.root.set_script(load("res://addons/rpg_runtime/world/map_root.gd"))
	room.player.hurtbox.make_invulnerable(60.0)
	var guardian := _enemy(room, "guardian", 30.0, "room_02_guardian") as RpgGuardian
	var attacks: Array = []
	guardian.attacked.connect(func(kind: StringName) -> void: attacks.append(kind))
	var saw_telegraph := false
	var still := true
	for i in 200:
		await room.frames(1)
		if guardian.mode == RpgGuardian.TELEGRAPH:
			saw_telegraph = true
			still = still and absf(guardian.velocity.x) < 1.0
		if not attacks.is_empty():
			break
	t.ok(saw_telegraph and still, "it stops before it attacks")
	t.eq(attacks, [&"lunge"], "the first phase only lunges")
	var lunge_speed := 0.0
	for i in 12:
		await room.frames(1)
		lunge_speed = maxf(lunge_speed, absf(guardian.velocity.x))
	t.near(lunge_speed, 60.0 * 2.5, 2.0, "a lunge at two and a half times its speed")
	t.ok(guardian.velocity.x < 0.0 or guardian.position.x < 30.5 * TILE, "toward the player on its left")
	# the second phase: every other attack is the slam, and a rock falls where the player stands
	var blow := RpgDamageInfo.new()
	blow.amount = 8
	guardian.health.take(blow)
	t.eq(guardian.phase, 2)
	for i in 900:
		await room.frames(1)
		if attacks.has(&"slam") and guardian.last_rock != null:
			break
	t.ok(attacks.has(&"slam"), "it jumps: %s" % str(attacks))
	t.ok(guardian.last_rock != null, "and a rock falls when it lands")
	if guardian.last_rock != null and is_instance_valid(guardian.last_rock):
		t.ok(guardian.last_rock.velocity.y > 0.0 and guardian.last_rock.team == &"enemy", "straight down")
		t.near(guardian.last_rock.position.x, room.player.position.x, TILE * 3.0, "over the player")
	room.close()
	Fixtures.uninstall_state()

func test_defeating_the_guardian_opens_the_exits_and_grants_the_ability(t) -> void:
	var state := _state()
	var english := Fixtures.install_english()
	var room: PlatformTests.Room = await _room(60, 3.0)
	var guardian := _enemy(room, "guardian", 30.0, "room_02_guardian") as RpgGuardian
	guardian.grants = &"double_jump"
	var gate := RpgGate.new()
	gate.entity_id = "room_02_gate_e"
	gate.open_when = "flag:room_02_guardian.defeated"
	gate.size = Vector2(TILE, TILE * 3)
	gate.position = Vector2(50.5 * TILE, FLOOR_Y * TILE)
	room.root.add_child(gate)
	await room.frames(4)
	t.ok(not gate.open, "the exit is shut while the guardian lives")
	t.ok(not state.has_ability(&"double_jump"))
	var gold := state.gold
	var died: Array = []
	guardian.died.connect(func() -> void: died.append(1))
	var blow := RpgDamageInfo.new()
	blow.amount = 99
	guardian.health.take(blow)
	t.eq(died.size(), 1)
	t.ok(guardian.dead)
	t.eq(state.get_flag("room_02_guardian", "defeated"), true, "defeated:<id> is set")
	t.ok(gate.open, "the exit opens")
	t.ok(state.has_ability(&"double_jump"), "the first ability of the plan is the player's")
	t.eq(state.gold, gold + 40)
	await room.frames(40)
	t.ok(not is_instance_valid(guardian), "it is gone")
	var drops := 0
	for child in room.root.get_children():
		if child is RpgPickup:
			drops += 1
	t.eq(drops, 1, "it leaves a potion")
	room.close()
	Fixtures.uninstall_english(english)
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- persistence

func test_a_defeated_enemy_stays_away_until_its_flag_is_cleared(t) -> void:
	var state := _state()
	var room: PlatformTests.Room = await _room(40, 3.0)
	var enemy := _enemy(room, "patrol", 20.0, "room_03_enemy_001")
	await room.frames(4)
	var blow := RpgDamageInfo.new()
	blow.amount = 99
	enemy.health.take(blow)
	t.eq(state.get_flag("room_03_enemy_001", "defeated"), true)
	await room.frames(40)
	t.ok(not is_instance_valid(enemy))
	# the room is entered again: the enemy's scene is there, and takes itself out
	var again := _enemy(room, "patrol", 20.0, "room_03_enemy_001")
	var other := _enemy(room, "patrol", 25.0, "room_03_enemy_002")
	await room.frames(3)
	t.ok(not is_instance_valid(again), "dead stays dead across a room change")
	t.ok(is_instance_valid(other), "the one that was not defeated is there")
	# a save and a load keep it so
	var saved := state.to_dict()
	state.new_game()
	state.from_dict(saved)
	t.eq(state.get_flag("room_03_enemy_001", "defeated"), true)
	# resting at a save station clears the flag (T14.08): the enemy is back
	state.set_flag("room_03_enemy_001", "defeated", false)
	var back := _enemy(room, "patrol", 20.0, "room_03_enemy_001")
	await room.frames(3)
	t.ok(is_instance_valid(back), "back after the rest")
	room.close()
	Fixtures.uninstall_state()

func test_the_rooms_recipe_places_enemies_and_shuts_the_guardians_room(t) -> void:
	# without enemy scenes (this template project has none built) a room gets no enemy, and the
	# guardian's ability lies where the guardian would stand: nothing is left unreachable
	var cases: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tests/fixtures/room_plan_cases.json"))
	var plan: Dictionary = cases["default"]["rooms"]
	var guardian_room := RoomsRecipe.room_by_id(plan, str(plan["guardian"]))
	t.ok(guardian_room.has("guardian") and guardian_room["guardian"]["grants"] == "double_jump")
	t.eq(guardian_room["kind"], "guardian")
	var exits: Array = guardian_room["exits"]
	for exit_spec: Dictionary in exits:
		t.ok(exit_spec["edge"] in ["E", "W"], "the guardian's room has side exits only: a gate fits each")
