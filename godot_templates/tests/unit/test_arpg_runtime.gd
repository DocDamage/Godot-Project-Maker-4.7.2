extends RefCounted
## The action-RPG archetype without a running game: damage primitives, the state machine, the
## enemy components and the quick item (T9.01 to T9.04).

const Fixtures := preload("../lib/fixtures.gd")
const ArpgBuild := preload("res://builder/recipes/arpg/arpg_build.gd")
const EnemyRecipes := preload("res://builder/recipes/arpg/enemy_recipes.gd")
const SwingRecipe := preload("res://builder/recipes/arpg/swing_recipe.gd")
const ActorBuild := preload("res://builder/lib/actor_build.gd")
const ARCH_DIR := "res://addons/rpg_runtime/archetypes/arpg"

func test_large_static_battler_art_keeps_a_reachable_combat_body_and_its_native_visual(t) -> void:
	var frames := SpriteFrames.new()
	frames.add_animation("idle_down")
	var node := EnemyRecipes.new()._build_scene(frames, {"frame": Vector2i(400, 400), "origin": Vector2i(200, 399)}, 16, RpgEnemyDefinition.new(), false, false, true)
	var hurt := node.get_node("Hurtbox") as Area2D
	var body := (hurt.get_node("Shape") as CollisionShape2D).shape as RectangleShape2D
	var player_body := ArpgBuild.body_size(Vector2i(16, 24), 16)
	t.ok(absf(hurt.position.y + 12.0) < (body.size.y + player_body.y) * 0.5, "standing actors' combat bands overlap despite different canvas sizes")
	var feet := (node.get_node("Feet") as CollisionShape2D).shape as RectangleShape2D
	t.ok(feet.size.x <= 16.0, "the portrait canvas does not push the player outside attack reach")
	var visual := node.get_node("Visual") as AnimatedSprite2D
	t.eq(visual.offset, Vector2(-200, -399))
	t.ok(visual.sprite_frames == frames and visual.scale == Vector2.ONE, "native art and pivot are preserved")
	ActorBuild.set_feet(node, {"feet": 64.0})
	t.eq(feet.size.x, 64.0, "the caller's explicit footprint still wins")
	node.free()

func _scripts(dir_path: String) -> Array[String]:
	var out: Array[String] = []
	var dir := DirAccess.open(dir_path)
	for f in dir.get_files():
		if f.ends_with(".gd"):
			out.append(dir_path + "/" + f)
	for d in dir.get_directories():
		out.append_array(_scripts(dir_path + "/" + d))
	return out

func test_every_archetype_script_parses(t) -> void:
	var paths := _scripts(ARCH_DIR)
	t.ok(paths.size() >= 19, "found %d scripts" % paths.size())
	for path in paths:
		var script := load(path) as GDScript
		t.ok(script != null and script.can_instantiate(), path)

## T14.01: the damage primitives live in combat/realtime/ (the metroidvania shares them); a script
## at each old path extends the moved one, so a user's preload of the old path gives the same class.
const REALTIME_DIR := "res://addons/rpg_runtime/combat/realtime"
const MOVED := ["damage_info", "hitbox", "hurtbox", "health", "projectile", "state_machine", "pickup", "screen_feedback"]

func test_the_realtime_set_moved_and_the_old_paths_still_work(t) -> void:
	for moved: String in MOVED:
		var real := load("%s/%s.gd" % [REALTIME_DIR, moved]) as GDScript
		var shim := load("%s/%s.gd" % [ARCH_DIR, moved]) as GDScript
		t.ok(real != null and real.get_global_name() != &"", "%s is a class in combat/realtime" % moved)
		t.ok(shim != null and shim.can_instantiate(), "%s: the old path loads" % moved)
		if real == null or shim == null:
			continue
		t.ok(shim.get_base_script() == real, "%s: the old path extends the moved script" % moved)
		t.eq(shim.get_global_name(), &"", "%s: the shim defines no class of its own" % moved)
	var old_hitbox: Variant = (load(ARCH_DIR + "/hitbox.gd") as GDScript).new()
	t.ok(old_hitbox is RpgHitbox, "a hitbox made from the old path is an RpgHitbox")
	(old_hitbox as Node).free()
	var old_info: Variant = (load(ARCH_DIR + "/damage_info.gd") as GDScript).new()
	t.ok(old_info is RpgDamageInfo)
	t.eq(RpgArpgMath.base_damage(10, 4), RpgRealtimeMath.base_damage(10, 4), "the formulas keep their action-RPG name")
	t.near(RpgArpgMath.CRIT_MULTIPLIER, RpgRealtimeMath.CRIT_MULTIPLIER)

## A hitbox finds its owner by its components, so the owner need not be a top-down actor.
func test_a_hitbox_reads_the_stats_of_any_owner_with_components(t) -> void:
	var fighter := _fighter("player", 9, 0, 10)
	var hitbox := fighter.get_node("AttackHitbox") as RpgHitbox
	t.ok(hitbox.owner_actor() == fighter)
	t.eq(RpgRealtimeMath.stats_of(fighter).attack, 9)
	t.eq(RpgRealtimeMath.stats_of(Node2D.new()), null, "no components, no stats")
	t.eq(RpgRealtimeMath.facing_of(fighter), Vector2.DOWN)
	fighter.facing = "left"
	t.eq(RpgRealtimeMath.facing_of(fighter), Vector2.LEFT)
	fighter.free()

# ---------------------------------------------------------------- fixtures

## A fighter: actor + Components/Stats + Health + Hurtbox + AttackHitbox, not in the tree. The
## stats component gets its RpgStats by hand (its _ready does not run outside the tree).
func _fighter(team: String, attack: int, defense: int, hp: int, invuln: float = 0.0) -> RpgActor:
	var actor := RpgActor.new()
	actor.name = "Fighter"
	var components := Node.new()
	components.name = "Components"
	actor.add_child(components)
	var stats_node := RpgStatsComponent.new()
	stats_node.name = "Stats"
	var stats := RpgStats.new()
	stats.attack = attack
	stats.defense = defense
	stats.max_hp = hp
	stats.hp = hp
	stats.extra = {"crit_chance": 0.0}
	stats_node.stats = stats
	components.add_child(stats_node)
	var health := RpgHealth.new()
	health.name = "Health"
	actor.add_child(health)
	var hurtbox := RpgHurtbox.new()
	hurtbox.name = "Hurtbox"
	hurtbox.team = StringName(team)
	hurtbox.invuln_s = invuln
	actor.add_child(hurtbox)
	var hitbox := RpgHitbox.new()
	hitbox.name = "AttackHitbox"
	hitbox.team = StringName(team)
	actor.add_child(hitbox)
	return actor

func _hurtbox(actor: Node) -> RpgHurtbox:
	return actor.get_node("Hurtbox") as RpgHurtbox

func _hitbox(actor: Node) -> RpgHitbox:
	return actor.get_node("AttackHitbox") as RpgHitbox

func _health(actor: Node) -> RpgHealth:
	return actor.get_node("Health") as RpgHealth

# ---------------------------------------------------------------- T9.01

func test_damage_formula(t) -> void:
	t.eq(RpgArpgMath.base_damage(10, 4), 8)
	t.eq(RpgArpgMath.base_damage(10, 5), 8, "defense / 2 rounds down")
	t.eq(RpgArpgMath.base_damage(1, 40), 1, "at least 1")
	t.eq(RpgArpgMath.base_damage(0, 0), 1)

func test_crits_multiply_by_one_and_a_half_and_use_the_rng(t) -> void:
	var rng := RpgRng.new()
	rng.seed_value(7)
	var crits := 0
	var total := 400
	for i in total:
		var rolled := RpgArpgMath.roll_damage(10, 0, 0.25, rng)
		if rolled["crit"]:
			crits += 1
			t.eq(rolled["amount"], 15)
		else:
			t.eq(rolled["amount"], 10)
	t.ok(crits > total * 0.15 and crits < total * 0.35, "about 25%% crits, got %d of %d" % [crits, total])
	t.eq(RpgArpgMath.roll_damage(10, 0, 0.0, rng)["crit"], false)
	t.eq(RpgArpgMath.roll_damage(10, 0, 1.0, rng)["crit"], true)
	var a := RpgRng.new()
	var b := RpgRng.new()
	a.seed_value(3)
	b.seed_value(3)
	t.eq(RpgArpgMath.roll_damage(9, 2, 0.5, a), RpgArpgMath.roll_damage(9, 2, 0.5, b), "same seed, same roll")

func test_active_frame_helpers(t) -> void:
	t.eq(RpgArpgMath.default_active_frames(4), [1, 2])
	t.eq(RpgArpgMath.default_active_frames(3), [1])
	t.eq(RpgArpgMath.default_active_frames(1), [0])
	t.eq(RpgArpgMath.default_active_frames(6), [2, 3])
	t.eq(RpgArpgMath.default_active_frames(0), [])
	var frames := SpriteFrames.new()
	frames.add_animation("attack_down")
	frames.set_animation_speed("attack_down", 10.0)
	for i in 4:
		frames.add_frame("attack_down", null, 1.0)
	t.near(RpgArpgMath.animation_seconds(frames, "attack_down"), 0.4)
	t.eq(RpgArpgMath.active_frames_of(frames, "attack_down"), [1, 2], "the middle third without meta")
	frames.set_meta("active_frames_attack_down", PackedInt32Array([3]))
	t.eq(RpgArpgMath.active_frames_of(frames, "attack_down"), [3])
	t.eq(RpgArpgMath.active_frames_of(frames, "missing"), [])

func test_a_hitbox_hits_the_same_hurtbox_once_per_activation(t) -> void:
	var player := _fighter("player", 10, 0, 20)
	var enemy := _fighter("enemy", 3, 0, 100)
	var hitbox := _hitbox(player)
	var target := _hurtbox(enemy)
	t.ok(not hitbox.try_hit(target), "an inactive hitbox hits nothing")
	hitbox.active = true
	t.ok(hitbox.try_hit(target), "the first contact lands")
	t.eq(_health(enemy).hp(), 90)
	t.ok(not hitbox.try_hit(target), "the same swing does not hit twice")
	hitbox.active = false
	hitbox.active = true
	t.ok(hitbox.try_hit(target), "a new activation hits again")
	t.eq(_health(enemy).hp(), 80)
	player.free()
	enemy.free()

func test_hitboxes_ignore_their_own_team(t) -> void:
	var a := _fighter("player", 10, 0, 20)
	var b := _fighter("player", 10, 0, 20)
	var hitbox := _hitbox(a)
	hitbox.active = true
	t.ok(not hitbox.try_hit(_hurtbox(b)))
	t.eq(_health(b).hp(), 20)
	t.ok(not hitbox.try_hit(_hurtbox(a)), "and never the owner")
	a.free()
	b.free()

func test_invulnerability_window(t) -> void:
	var player := _fighter("player", 5, 0, 30, RpgArpgMath.PLAYER_INVULN_S)
	var hurtbox := _hurtbox(player)
	var info := RpgDamageInfo.new()
	info.amount = 4
	t.ok(hurtbox.receive(info))
	t.eq(_health(player).hp(), 26)
	t.ok(hurtbox.is_invulnerable())
	t.ok(not hurtbox.receive(info), "a second hit inside the window does nothing")
	t.eq(_health(player).hp(), 26)
	hurtbox.invulnerable_until_ms = Time.get_ticks_msec() - 1  # the window is over
	t.ok(hurtbox.receive(info))
	t.eq(_health(player).hp(), 22)
	hurtbox.invulnerable_until_ms = 0
	hurtbox.make_invulnerable(0.5)
	t.ok(not hurtbox.receive(info), "make_invulnerable (the dodge) blocks hits too")
	t.near(RpgArpgMath.PLAYER_INVULN_S, 0.6)
	t.near(RpgArpgMath.ENEMY_INVULN_S, 0.15)
	player.free()

func test_health_reaches_zero_and_died_is_emitted_once(t) -> void:
	var enemy := _fighter("enemy", 1, 0, 5)
	var health := _health(enemy)
	var box := {"died": 0, "changed": 0, "last": -1}
	health.died.connect(func() -> void: box["died"] += 1)
	health.changed.connect(func(hp: int, _max: int) -> void:
		box["changed"] += 1
		box["last"] = hp)
	var info := RpgDamageInfo.new()
	info.amount = 3
	health.take(info)
	t.eq(box["last"], 2)
	info.amount = 50
	health.take(info)
	t.eq(health.hp(), 0, "never below 0")
	t.eq(box["died"], 1)
	health.take(info)
	t.eq(box["died"], 1, "a dead actor is not killed twice")
	t.eq(box["changed"], 2)
	t.ok(health.is_dead())
	health.heal(3)
	t.eq(health.hp(), 3)
	t.ok(not health.is_dead())
	health.revive()
	t.eq(health.hp(), 5)
	enemy.free()

func test_the_damage_uses_the_attacker_stats_and_the_defenders_defense(t) -> void:
	var player := _fighter("player", 12, 0, 20)
	var enemy := _fighter("enemy", 3, 8, 100)
	var hitbox := _hitbox(player)
	var state := Fixtures.install_state()
	state.rng.seed_value(5)
	hitbox.active = true
	var info := hitbox.build_info(_hurtbox(enemy))
	var expected := RpgArpgMath.base_damage(12, 8)
	t.ok(info.amount == expected or info.amount == int(round(expected * 1.5)), "amount %d" % info.amount)
	t.eq(info.source, player)
	enemy.position = Vector2(10, 0)
	info = hitbox.build_info(_hurtbox(enemy))
	t.ok(info.knockback.x > 0.0 and absf(info.knockback.y) < 0.001, "knockback points away from the attacker")
	t.near(info.knockback.length(), hitbox.knockback_strength)
	Fixtures.uninstall_state()
	player.free()
	enemy.free()

func test_hitbox_aims_toward_the_facing(t) -> void:
	var hitbox := RpgHitbox.new()
	hitbox.center = Vector2(0, -12)
	hitbox.reach = Vector2(8, 10)
	hitbox.aim("right")
	t.eq(hitbox.position, Vector2(8, -12))
	hitbox.aim("up")
	t.eq(hitbox.position, Vector2(0, -22))
	hitbox.aim("down")
	t.eq(hitbox.position, Vector2(0, -2))
	hitbox.aim("left")
	t.eq(hitbox.position, Vector2(-8, -12))
	hitbox.free()

# ---------------------------------------------------------------- T9.02

func test_state_machine_transitions(t) -> void:
	var machine := RpgStateMachine.new()
	var log: Array = []
	machine.add(&"A", func() -> void: log.append("enter A"), func(_d: float) -> void: log.append("update A"), func() -> void: log.append("exit A"))
	machine.add(&"B", func() -> void: log.append("enter B"))
	machine.changed.connect(func(from: StringName, to: StringName) -> void: log.append("%s>%s" % [from, to]))
	machine.go(&"A")
	machine._physics_process(0.1)
	machine.go(&"B")
	machine._physics_process(0.1)
	t.eq(log, ["enter A", ">A", "update A", "exit A", "enter B", "A>B"])
	t.eq(machine.state, &"B")
	t.near(machine.time_in_state, 0.1)
	machine.go(&"B")
	t.near(machine.time_in_state, 0.0)
	machine.enabled = false
	machine._physics_process(1.0)
	t.near(machine.time_in_state, 0.0, 0.0001)
	machine.free()

# ---------------------------------------------------------------- T9.03

func test_behavior_defaults_and_overrides(t) -> void:
	var b := RpgEnemyAi.merged_behavior({}, 16.0)
	t.eq(b["vision_px"], 96.0)
	t.eq(b["attack_cooldown_s"], 1.2)
	t.eq(b["nav_mode"], "direct")
	t.eq(b["wander_pause_s"], [1.0, 2.5])
	var scaled := RpgEnemyAi.merged_behavior({"vision_px": 50, "chase_speed": 99, "turn_based": {"attack": 1.0}, "windup_s": 0.5}, 32.0)
	t.eq(scaled["vision_px"], 50, "an explicit value is used as it is")
	t.eq(scaled["chase_speed"], 99)
	t.eq(scaled["lose_px"], 320.0, "defaults scale with the tile size")
	t.eq(scaled["windup_s"], 0.5)
	t.ok(not scaled.has("turn_based"), "unknown keys are ignored")
	var seeded := EnemyRecipes.behavior_for(16, "direct")
	for key in RpgEnemyAi.DEFAULT_BEHAVIOR.keys():
		t.ok(seeded.has(key), key)
	t.eq(EnemyRecipes.behavior_for(32, "agent")["vision_px"], 192)
	t.eq(EnemyRecipes.behavior_for(32, "agent")["nav_mode"], "agent")

## An enemy-like actor with detection, chase and attack components, not in the tree.
func _enemy_parts(player_at: Vector2) -> Dictionary:
	var actor := RpgActor.new()
	actor.name = "Enemy"
	actor.position = Vector2.ZERO
	var components := Node.new()
	components.name = "Components"
	actor.add_child(components)
	var movement := RpgMovement.new()
	movement.name = "Movement"
	components.add_child(movement)
	var detection := RpgDetection.new()
	detection.name = "Detection"
	detection.actor = actor
	detection.fake_player_position = player_at
	components.add_child(detection)
	var chase := RpgChase.new()
	chase.name = "Chase"
	chase.actor = actor
	chase.detection = detection
	components.add_child(chase)
	var attack := RpgEnemyAttack.new()
	attack.name = "EnemyAttack"
	attack.actor = actor
	components.add_child(attack)
	var hitbox := RpgHitbox.new()
	hitbox.name = "AttackHitbox"
	hitbox.team = &"enemy"
	actor.add_child(hitbox)
	attack.hitbox = hitbox
	return {"actor": actor, "detection": detection, "chase": chase, "attack": attack, "hitbox": hitbox}

func test_detection_needs_range_and_a_clear_line(t) -> void:
	var parts := _enemy_parts(Vector2(50, 0))
	var detection: RpgDetection = parts["detection"]
	detection.vision_px = 96.0
	t.ok(detection.can_see_player(), "in range and nothing in the way (no Sight node: clear)")
	detection.fake_player_position = Vector2(200, 0)
	t.ok(not detection.can_see_player(), "out of range")
	detection.fake_player_position = Vector2(96, 0)
	t.ok(detection.can_see_player(), "exactly at the vision radius")
	t.near(detection.distance_to_player(), 96.0)
	# The real raycast against a real wall is exercised by the smoke step enemy_detects.
	(parts["actor"] as Node).free()

func test_chase_gives_up_after_lose_px_for_two_seconds(t) -> void:
	var parts := _enemy_parts(Vector2(300, 0))
	var chase: RpgChase = parts["chase"]
	chase.lose_px = 160.0
	chase.lose_time_s = 2.0
	var frames := 0
	while not chase.gave_up() and frames < 400:
		chase.step(1.0 / 60.0)
		frames += 1
	t.ok(chase.gave_up())
	t.ok(frames >= 120 and frames <= 122, "gave up after %d frames (about 2 s)" % frames)
	# Coming back in range resets the timer.
	var detection: RpgDetection = parts["detection"]
	detection.fake_player_position = Vector2(100, 0)
	chase.step(1.0 / 60.0)
	t.ok(not chase.gave_up())
	t.ok(not chase.in_attack_range())
	detection.fake_player_position = Vector2(10, 0)
	t.ok(chase.in_attack_range())
	(parts["actor"] as Node).free()

func test_chase_moves_toward_the_player(t) -> void:
	var parts := _enemy_parts(Vector2(100, 0))
	var chase: RpgChase = parts["chase"]
	var actor: RpgActor = parts["actor"]
	chase.speed = 60.0
	chase.step(0.016)
	var movement := actor.component("Movement") as RpgMovement
	t.eq(movement.desired, Vector2.RIGHT)
	t.near(movement.speed, 60.0)
	t.eq(actor.facing, "right")
	(parts["detection"] as RpgDetection).fake_player_position = Vector2(-100, 0)
	chase.step(0.016)
	t.eq(movement.desired, Vector2.LEFT)
	actor.free()

func test_the_attack_telegraphs_then_hits_then_cools_down(t) -> void:
	var parts := _enemy_parts(Vector2(10, 0))
	var attack: RpgEnemyAttack = parts["attack"]
	var hitbox: RpgHitbox = parts["hitbox"]
	attack.windup_s = 0.35
	attack.active_s = 0.15
	attack.cooldown_s = 1.2
	t.ok(attack.can_start())
	t.ok(attack.try_start())
	t.ok(not attack.try_start(), "no second start while attacking")
	t.eq(attack.phase, RpgEnemyAttack.Phase.WINDUP)
	var finished := false
	var t_active := -1.0
	var elapsed := 0.0
	while not finished and elapsed < 2.0:
		finished = attack.update(0.01)
		elapsed += 0.01
		if t_active < 0.0 and hitbox.active:
			t_active = elapsed
	t.ok(finished)
	t.ok(t_active >= 0.34 and t_active <= 0.37, "the hitbox became active after the windup (%.2f s)" % t_active)
	t.ok(elapsed >= 0.49 and elapsed <= 0.52, "the whole attack took %.2f s" % elapsed)
	t.ok(not hitbox.active)
	t.ok(not attack.can_start(), "the cooldown starts when the attack ends")
	attack._physics_process(1.0)
	t.ok(not attack.can_start())
	attack._physics_process(0.3)
	t.ok(attack.can_start(), "ready after the 1.2 s cooldown")
	# A cancelled attack also leaves the hitbox off.
	attack.try_start()
	attack.update(0.4)
	t.ok(hitbox.active)
	attack.cancel()
	t.ok(not hitbox.active)
	t.ok(not attack.can_start())
	(parts["actor"] as Node).free()

func test_loot_rolls_use_the_game_rng(t) -> void:
	var state := Fixtures.install_state()
	var actor := RpgActor.new()
	var def := RpgEnemyDefinition.new()
	var loot_table := RpgLootTable.new()
	loot_table.entries.assign([{"item_id": "potion", "chance": 1.0, "min": 2, "max": 2}, {"item_id": "gem", "chance": 0.0}])
	def.loot = loot_table
	actor.definition = def
	var drop := RpgLootDrop.new()
	drop.actor = actor
	var rolled := drop.roll()
	t.eq(rolled.size(), 1)
	t.eq(rolled[0]["item_id"], &"potion")
	t.eq(rolled[0]["qty"], 2)
	Fixtures.uninstall_state()
	drop.free()
	actor.free()

func test_a_pickup_adds_its_item_and_stays_when_the_bag_is_full(t) -> void:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion", 99, &"heal", 10)})
	var pickup := RpgPickup.create(&"potion", 3, null)
	t.eq(pickup.collision_layer, 1 << 4, "interactables layer (5)")
	t.eq(pickup.collision_mask, 1 << 1, "looks for the player (2)")
	t.ok(pickup.get_node_or_null("Sprite") != null and pickup.get_node_or_null("Shape") != null)
	t.ok(pickup.collect())
	t.eq(state.inventory.count(&"potion"), 3)
	t.ok(not pickup.collect(), "collected once")
	var full := RpgPickup.create(&"potion", 1, null)
	state.inventory.capacity = 1
	state.inventory.slots.clear()
	state.inventory.add(&"other", 1)
	t.ok(not full.collect(), "nothing fitted: the pickup stays")
	Fixtures.uninstall_state()
	pickup.free()
	full.free()

# ---------------------------------------------------------------- quick item (T9.04)

func test_quick_item_defaults_to_the_first_consumable(t) -> void:
	var potion := Fixtures.item(&"potion", 99, &"heal", 10)
	var elixir := Fixtures.item(&"elixir", 99, &"heal", 30)
	var key := Fixtures.item(&"key")
	key.category = RpgItemDefinition.Category.KEY
	var state := Fixtures.install_state({&"potion": potion, &"elixir": elixir, &"key": key})
	var mode := RpgArpgMode.new()
	t.eq(mode.quick_item(), &"", "nothing yet")
	state.inventory.add(&"key", 1)
	state.inventory.add(&"elixir", 2)
	state.inventory.add(&"potion", 1)
	t.eq(mode.quick_item(), &"elixir", "the first consumable, not the key")
	t.ok(mode.set_quick_item(&"potion"))
	t.eq(mode.quick_item(), &"potion")
	t.ok(not mode.set_quick_item(&"unknown"))
	state.inventory.remove(&"potion", 1)
	t.eq(mode.quick_item(), &"elixir", "an used-up selection falls back to the default")
	t.eq(state.get_flag("arpg_hud", "quick_item"), "potion", "the choice is a flag, so it is saved")
	mode.free()
	Fixtures.uninstall_state()

func test_using_the_quick_item_heals_and_keeps_the_item_at_full_health(t) -> void:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion", 99, &"heal", 10)})
	var mode := RpgArpgMode.new()
	state.inventory.add(&"potion", 2)
	state.player_stats.max_hp = 20
	state.player_stats.hp = 20
	t.ok(not mode.use_quick_item(), "full health: refused")
	t.eq(state.inventory.count(&"potion"), 2)
	state.player_stats.hp = 8
	t.ok(mode.use_quick_item())
	t.eq(state.player_stats.hp, 18)
	t.eq(state.inventory.count(&"potion"), 1)
	mode.free()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- recipes (T9.05, T9.03)

func test_the_drawn_swing_has_four_frames_with_an_outline(t) -> void:
	var frames := SwingRecipe.drawn_frames(16)
	t.ok(frames.has_animation("swing"))
	t.eq(frames.get_frame_count("swing"), 4)
	t.ok(not frames.get_animation_loop("swing"))
	var first := frames.get_frame_texture("swing", 0).get_image()
	t.eq(first.get_size(), Vector2i(24, 24), "tile x 1.5")
	var last := frames.get_frame_texture("swing", 3).get_image()
	var white_first := 0
	var white_last := 0
	var dark_last := 0
	for y in 24:
		for x in 24:
			var c0 := first.get_pixel(x, y)
			var c3 := last.get_pixel(x, y)
			if c0 == Color.WHITE:
				white_first += 1
			if c3 == Color.WHITE:
				white_last += 1
			elif c3.a > 0.0:
				dark_last += 1
				t.ok(c3.a == 1.0 and c3.r < 0.2, "the outline is solid dark")
	t.ok(white_first > 0 and white_last > white_first, "the arc grows: %d -> %d" % [white_first, white_last])
	t.ok(dark_last > 0, "there is an outline")
	t.eq(SwingRecipe.drawn_frames(32).get_frame_texture("swing", 0).get_image().get_size(), Vector2i(48, 48))

func test_body_and_reach_follow_the_frame_and_the_tile(t) -> void:
	var body := ArpgBuild.body_size(Vector2i(16, 24), 16)
	t.eq(body, Vector2(8, 14.4))
	t.eq(ArpgBuild.body_center(Vector2i(16, 24)), Vector2(0, -12))
	t.eq(ArpgBuild.reach(Vector2i(16, 24), 16), Vector2(8, 12))
	var big := ArpgBuild.reach(Vector2i(64, 64), 32)
	t.eq(big, Vector2(24, 24), "a big frame does not push the hitbox out of reach")

func test_player_and_enemy_parts_have_the_documented_layers(t) -> void:
	var player := _actor_player()
	ArpgBuild.augment_player(player, Vector2i(16, 24), Vector2i(8, 23), 16)
	var hurt := player.get_node("Hurtbox") as Area2D
	var hit := player.get_node("AttackHitbox") as Area2D
	t.eq(hurt.collision_layer, 1 << 8, "player hurtbox on layer 9")
	t.eq(hurt.collision_mask, 0)
	t.eq(hit.collision_layer, 1 << 6, "player hitbox on layer 7")
	t.eq(hit.collision_mask, 1 << 9, "looking at layer 10")
	t.ok(not hit.monitoring and (hit.get_node("Shape") as CollisionShape2D).disabled, "the hitbox starts inactive")
	for child in ["Health", "PlayerCombat", "SwingEffect"]:
		t.ok(player.get_node_or_null(child) != null, child)
	player.free()
	var enemy := _actor_enemy()
	ArpgBuild.augment_enemy(enemy, Vector2i(16, 24), 16, false)
	t.eq((enemy.get_node("Hurtbox") as Area2D).collision_layer, 1 << 9, "enemy hurtbox on layer 10")
	t.eq((enemy.get_node("AttackHitbox") as Area2D).collision_layer, 1 << 7, "enemy hitbox on layer 8")
	t.eq((enemy.get_node("AttackHitbox") as Area2D).collision_mask, 1 << 8, "looking at layer 9")
	t.eq(enemy.collision_layer, 1 << 2, "enemies layer 3")
	t.eq((enemy.get_node("Sight") as RayCast2D).collision_mask, 1, "the line of sight sees the world only")
	t.eq((enemy.get_node("Navigation") as Node).process_mode, Node.PROCESS_MODE_DISABLED, "direct mode: the agent is off")
	for child in ["Detection", "Chase", "Wander", "EnemyAttack", "LootDrop"]:
		t.ok(enemy.get_node("Components").get_node_or_null(child) != null, child)
	enemy.free()

func _actor_player() -> CharacterBody2D:
	return preload("res://builder/lib/actor_build.gd").build("player", "Player", null, Vector2i(16, 24), Vector2i(8, 23), 16)

func _actor_enemy() -> CharacterBody2D:
	return preload("res://builder/lib/actor_build.gd").build("base", "Enemy", null, Vector2i(16, 24), Vector2i(8, 23), 16)

func test_enemy_slugs_and_scaling(t) -> void:
	t.eq(EnemyRecipes.scaled(0)["hp"], 12)
	t.eq(EnemyRecipes.scaled(2)["attack"], 6)
	t.eq(EnemyRecipes.display_name("slime_idle"), "Slime")
	t.eq(EnemyRecipes.slugs_for(["a.b.slime", "a.b.bat"]), ["slime", "bat"])

func test_heavy_attack_numbers(t) -> void:
	t.eq(RpgArpgMath.heavy_damage(1), 2, "always more than the light attack")
	t.eq(RpgArpgMath.heavy_damage(8), 14, "8 x 1.75")
	t.eq(RpgArpgMath.heavy_damage(10), 18, "17.5 rounds up")
	for base in range(1, 50):
		t.ok(RpgArpgMath.heavy_damage(base) > base, "heavy > light at %d" % base)

func test_heavy_hitbox_scales_damage_and_knockback(t) -> void:
	var light := _fighter("player", 12, 0, 20)
	var target := _fighter("enemy", 1, 0, 40)
	var hitbox: RpgHitbox = light.get_node("AttackHitbox")
	var hurtbox: RpgHurtbox = target.get_node("Hurtbox")
	var normal := hitbox.build_info(hurtbox)
	hitbox.heavy = true
	var heavy := hitbox.build_info(hurtbox)
	t.ok(heavy.amount > normal.amount, "heavy deals more")
	t.ok(heavy.knockback.length() > normal.knockback.length(), "heavy pushes further")
	light.free()
	target.free()

# ---------------------------------------------------------------- T13.15: followers help

const STEP := 1.0 / 60.0

## A follower with the assist parts, not in the tree: {node, assist, stats}.
func _helper(attack: int, hp: int) -> Dictionary:
	var player := Node2D.new()
	var node := RpgFollowers.make_follower(null, player)
	player.free()
	var stats := RpgStats.new()
	stats.attack = attack
	stats.max_hp = hp
	stats.hp = hp
	var assist := RpgAssist.attach(node, stats, 16.0)
	return {"node": node, "assist": assist, "stats": stats}

func _steps(assist: RpgAssist, seconds: float, player_at: Vector2, enemies: Array[Node2D]) -> void:
	for i in ceili(seconds / STEP):
		assist.step(STEP, player_at, enemies)

func test_a_follower_walks_to_an_enemy_near_the_player_and_hits_it(t) -> void:
	var parts := _helper(7, 20)
	var node: Node2D = parts["node"]
	var assist: RpgAssist = parts["assist"]
	var enemy := _fighter("enemy", 3, 0, 100)
	enemy.position = Vector2(40, 0)  # 2.5 tiles from the player
	var enemies: Array[Node2D] = [enemy]
	assist.step(STEP, Vector2.ZERO, enemies)
	t.ok(assist.is_held(), "it leaves the trail")
	t.eq(assist.target, enemy)
	_steps(assist, 0.5, Vector2.ZERO, enemies)
	t.ok(absf(node.position.distance_to(enemy.position) - 16.0) < 1.0, "it stands one tile beside the enemy: %s" % node.position)
	t.eq(node.get_meta("facing"), "right")
	t.eq(assist.hitbox.damage, 7, "the swing uses the member's attack")
	t.ok(assist.cooldown_left > 0.0, "it has swung")
	# a swing lasts 0.15 s and comes every 1.2 s
	assist.cooldown_left = 0.0
	assist.step(STEP, Vector2.ZERO, enemies)
	t.ok(assist.hitbox.active)
	t.ok(assist.hitbox.try_hit(_hurtbox(enemy)), "the swing lands on the enemy")
	t.ok(_health(enemy).hp() < 100)
	_steps(assist, RpgAssist.SWING_ACTIVE_S + STEP, Vector2.ZERO, enemies)
	t.ok(not assist.hitbox.active, "the swing is over")
	t.ok(absf(assist.cooldown_left - (RpgAssist.SWING_EVERY_S - RpgAssist.SWING_ACTIVE_S)) < 0.05)
	node.free()
	enemy.free()

func test_a_follower_ignores_far_enemies_and_returns_when_the_player_walks_away(t) -> void:
	var parts := _helper(7, 20)
	var node: Node2D = parts["node"]
	var assist: RpgAssist = parts["assist"]
	var enemy := _fighter("enemy", 3, 0, 100)
	enemy.position = Vector2(64, 0)  # 4 tiles: too far
	var enemies: Array[Node2D] = [enemy]
	assist.step(STEP, Vector2.ZERO, enemies)
	t.ok(not assist.is_held(), "an enemy 4 tiles from the player is left alone")
	enemy.position = Vector2(32, 0)
	_steps(assist, 0.5, Vector2.ZERO, enemies)
	t.ok(assist.is_held())
	# the player walks away: the follower goes back to its place on the trail, then lets go
	var far := Vector2(-200, 0)
	node.set_meta("home", far + Vector2(16, 0))
	assist.step(STEP, far, enemies)
	t.eq(assist.target, null)
	t.ok(assist.is_held(), "it walks back, it does not jump")
	_steps(assist, 4.0, far, enemies)
	t.ok(not assist.is_held(), "back on the trail")
	t.ok(node.position.distance_to(far + Vector2(16, 0)) <= 2.5, str(node.position))
	# switched off it only follows
	assist.enabled = false
	enemy.position = far + Vector2(20, 0)
	assist.step(STEP, far, enemies)
	t.ok(not assist.is_held())
	node.free()
	enemy.free()

func test_a_follower_stays_within_six_tiles_and_picks_the_nearest_living_enemy(t) -> void:
	t.eq(RpgAssist.leashed(Vector2(200, 0), Vector2.ZERO, 96.0), Vector2(96, 0))
	t.eq(RpgAssist.leashed(Vector2(50, 0), Vector2.ZERO, 96.0), Vector2(50, 0))
	var near := _fighter("enemy", 1, 0, 10)
	near.position = Vector2(20, 0)
	var nearer := _fighter("enemy", 1, 0, 10)
	nearer.position = Vector2(0, 10)
	var both: Array[Node2D] = [near, nearer]
	t.eq(RpgAssist.nearest_enemy(Vector2.ZERO, both, 48.0), nearer)
	t.eq(RpgAssist.nearest_enemy(Vector2(500, 0), both, 48.0), null)
	near.free()
	nearer.free()

func test_a_follower_cannot_die_it_is_down_for_five_seconds(t) -> void:
	var parts := _helper(7, 20)
	var node: Node2D = parts["node"]
	var assist: RpgAssist = parts["assist"]
	var stats: RpgStats = parts["stats"]
	var enemy := _fighter("enemy", 99, 0, 100)
	enemy.position = Vector2(24, 0)
	var enemies: Array[Node2D] = [enemy]
	_steps(assist, 0.2, Vector2.ZERO, enemies)
	var box := {"down": 0, "up": 0}
	assist.downed.connect(func() -> void: box["down"] += 1)
	assist.recovered.connect(func() -> void: box["up"] += 1)
	var enemy_hitbox := _hitbox(enemy)
	enemy_hitbox.active = true
	t.ok(enemy_hitbox.try_hit(assist.hurtbox), "an enemy can hit the follower")
	t.eq(stats.hp, 0)
	t.ok(assist.is_downed())
	t.eq(box["down"], 1)
	t.ok(not assist.is_held() and not assist.hitbox.active, "it stops fighting")
	t.ok(node.modulate.a < 1.0)
	enemy_hitbox.active = false
	enemy_hitbox.active = true
	t.ok(not enemy_hitbox.try_hit(assist.hurtbox), "it cannot be hit while it is down")
	_steps(assist, RpgAssist.DOWNED_S - 0.5, Vector2.ZERO, enemies)
	t.ok(assist.is_downed() and not assist.is_held())
	_steps(assist, 0.6, Vector2.ZERO, enemies)
	t.ok(not assist.is_downed())
	t.eq(stats.hp, 20, "back at full health")
	t.eq(box["up"], 1)
	t.eq(node.modulate.a, 1.0)
	assist.step(STEP, Vector2.ZERO, enemies)
	t.ok(assist.is_held(), "and it fights again")
	node.free()
	enemy.free()
	# a member saved at 0 HP starts down
	var player := Node2D.new()
	var again := RpgFollowers.make_follower(null, player)
	player.free()
	stats.hp = 0
	t.ok(RpgAssist.attach(again, stats, 16.0).is_downed())
	again.free()

func test_the_mode_gives_the_first_two_followers_an_assist_and_the_hud_a_bar_each(t) -> void:
	var mode := RpgArpgMode.new()
	var player := Node2D.new()
	var state := RpgGameState.new()
	var changes := {"n": 0}
	mode.party_health_changed.connect(func() -> void: changes["n"] += 1)
	var nodes: Array[Node2D] = []
	for i in 3:
		var stats := RpgStats.new()
		stats.max_hp = 10 + i
		stats.hp = 5
		state.party.append({"actor_id": StringName("ally_%d" % i), "stats": stats})
		var node := RpgFollowers.make_follower(null, player)
		mode.customize_follower(node, state.party[i], i)
		nodes.append(node)
	t.ok(nodes[0].get_node_or_null("Assist") != null and nodes[1].get_node_or_null("Assist") != null)
	t.ok(nodes[2].get_node_or_null("Assist") == null, "the third follower only follows")
	var info := RpgDamageInfo.new()
	info.amount = 2
	(nodes[0].get_node("Health") as RpgHealth).take(info)
	t.eq(changes["n"], 1, "the HUD is told")
	# the HUD: a bar per member under the player's HP row
	var hud := RpgArpgHud.new()
	var column := VBoxContainer.new()
	var row := HBoxContainer.new()
	var hp_bar := ProgressBar.new()
	hp_bar.custom_minimum_size = Vector2(72, 8)
	row.add_child(hp_bar)
	column.add_child(row)
	column.add_child(Label.new())
	hud.add_child(column)
	hud._refresh_party(state, hp_bar)
	var box := column.get_node("Party") as VBoxContainer
	t.eq(box.get_index(), 1, "right under the HP row")
	t.eq(box.get_child_count(), 3)
	var first := box.get_node("Member_ally_0") as ProgressBar
	t.eq(first.value, 3.0)
	t.eq(first.max_value, 10.0)
	t.ok(first.custom_minimum_size.x < 72.0)
	state.party.remove_at(0)
	hud._refresh_party(state, hp_bar)
	t.eq(box.get_child_count(), 2)
	t.eq(String(box.get_child(0).name), "Member_ally_1")
	state.party.clear()
	hud._refresh_party(state, hp_bar)
	t.ok(not box.visible)
	hud.free()
	for node in nodes:
		node.free()
	player.free()
	mode.free()
	state.free()
