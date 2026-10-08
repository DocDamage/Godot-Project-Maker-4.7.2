extends RefCounted
## The battle state machine with scripted choices (T7.02).

const Fixtures := preload("../lib/fixtures.gd")
const S := RpgBattleController.State

## No spread, no crits, the first target: every number in these tests can be worked out by hand.
class FixedRng extends RpgRng:
	var roll := 0.5
	func randf_range(_a: float, _b: float) -> float:
		return 1.0
	func randf() -> float:
		return roll
	func randi_range(from: int, _to: int) -> int:
		return from
	func pick(items: Array) -> Variant:
		return null if items.is_empty() else items[0]

func _potion() -> RpgItemDefinition:
	return Fixtures.item(&"potion", 99, &"heal", 10)

func _enemy_def(enemy_hp: int, enemy_attack: int, xp: int = 5, gold: int = 3) -> RpgEnemyDefinition:
	var def := RpgEnemyDefinition.new()
	def.id = &"slime"
	def.display_name = "Slime"
	var stats := RpgStats.new()
	stats.max_hp = enemy_hp
	stats.hp = enemy_hp
	stats.attack = enemy_attack
	stats.defense = 1
	stats.speed = 4
	def.base_stats = stats
	def.xp_reward = xp
	def.gold_reward = gold
	return def

## Hero (attack 10, defense 2, speed 6, hp 30) against one slime (defense 1, speed 4).
func _battle(enemy_hp: int = 30, enemy_attack: int = 4, rng: Variant = null) -> Dictionary:
	var state := Fixtures.install_state({&"potion": _potion()})
	state.player_stats = RpgStats.new()
	state.player_stats.max_hp = 30
	state.player_stats.hp = 30
	state.player_stats.attack = 10
	state.player_stats.defense = 2
	state.player_stats.speed = 6
	var data := RpgEncounterData.new()
	data.entity_id = "slime_1"
	data.enemies = [_enemy_def(enemy_hp, enemy_attack)]
	var controller := RpgBattleController.new()
	controller.setup(data, rng if rng != null else FixedRng.new())
	var states: Array = []
	controller.state_changed.connect(func(s: int) -> void: states.append(s))
	return {"state": state, "controller": controller, "states": states, "data": data}

func _done(b: Dictionary) -> void:
	(b["controller"] as Node).free()
	Fixtures.uninstall_state()

static func _attack_enemy_zero(_actor: RpgBattleActor, _battle: Variant) -> Dictionary:
	return {"command_id": &"attack", "target_index": 0}

func test_setup_builds_both_sides(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	t.eq(c.party.size(), 1)
	t.eq(c.enemies.size(), 1)
	t.ok(c.party[0].is_player_side and not c.enemies[0].is_player_side)
	t.ok(c.party[0].stats == b["state"].player_stats, "the player side shares the live GameState stats")
	t.ok(c.enemies[0].stats != b["data"].enemies[0].base_stats, "enemies fight with a copy")
	t.eq(c.enemies[0].display_name, "Slime")
	t.eq(c.commands.size(), 5)
	var ids: Array = []
	for command in c.commands:
		ids.append(String(command.id))
	t.eq(ids, ["attack", "defend", "item", "skill", "run"])
	_done(b)

func test_two_rounds_to_victory_with_exact_numbers(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	c.auto_choose = _attack_enemy_zero
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.VICTORY)
	# Round 1: hero hits for 19 (30 -> 11), the slime hits for 6 (30 -> 24).
	# Round 2: hero hits for 19 and the slime is down: its action is skipped.
	t.eq(b["states"], [S.INIT, S.ROUND_START, S.PLAYER_CHOOSE, S.ENEMY_CHOOSE, S.EXECUTE, S.CHECK,
		S.ROUND_START, S.PLAYER_CHOOSE, S.ENEMY_CHOOSE, S.EXECUTE, S.CHECK, S.VICTORY, S.END])
	t.eq(b["state"].player_stats.hp, 24)
	t.eq(c.enemies[0].stats.hp, 0)
	t.eq(c.round_number, 2)
	var hits_on_hero := 0
	for entry in c.history:
		if entry["type"] == "damage" and entry["target"] == c.party[0]:
			hits_on_hero += 1
	t.eq(hits_on_hero, 1, "the slime's second action was skipped when it died mid-round")
	_done(b)

func test_defending_halves_the_damage_until_the_next_round(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	var hp_after_check: Array = []
	c.state_changed.connect(func(s: int) -> void:
		if s == S.CHECK:
			hp_after_check.append(b["state"].player_stats.hp))
	var round_counter := [0]
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary:
		round_counter[0] += 1
		return {"command_id": &"defend"} if round_counter[0] == 1 else {"command_id": &"attack", "target_index": 0}
	await c.run()
	t.eq(hp_after_check[0], 27, "round 1: 6 damage halved to 3")
	t.eq(hp_after_check[1], 21, "round 2: the guard is gone, full 6 damage")
	_done(b)

func test_defend_acts_first_even_when_slower(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	c.party[0].stats.speed = 1  # slower than the slime
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary: return {"command_id": &"defend"}
	var rounds := [0]
	c.state_changed.connect(func(s: int) -> void:
		if s == S.CHECK:
			rounds[0] += 1
			if rounds[0] == 1:
				c.escaped = true)  # one round is enough
	await c.run()
	t.eq(b["state"].player_stats.hp, 27, "the slime's hit was already halved")
	_done(b)

func test_defeat(t) -> void:
	var b := _battle(30, 99)
	var c: RpgBattleController = b["controller"]
	b["state"].player_stats.hp = 5
	c.party[0].stats.speed = 1  # the slime strikes first
	c.auto_choose = _attack_enemy_zero
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.DEFEAT)
	t.eq(b["states"].slice(-3), [S.CHECK, S.DEFEAT, S.END])
	t.eq(b["state"].player_stats.hp, 0)
	t.eq(result.xp, 0)
	_done(b)

func test_rewards_are_applied_on_victory(t) -> void:
	var b := _battle(10, 4)  # one hit kills
	var c: RpgBattleController = b["controller"]
	var def: RpgEnemyDefinition = b["data"].enemies[0]
	def.xp_reward = 7
	def.gold_reward = 12
	var loot := RpgLootTable.new()
	loot.entries = [{"item_id": "potion", "chance": 1.0, "min": 2, "max": 2}]
	def.loot = loot
	c.setup(b["data"], FixedRng.new())  # rebuild with the edited definition
	var gold_before: int = b["state"].gold
	var seen := []
	RpgUtil.events().experience_gained.connect(func(_id: StringName, amount: int) -> void: seen.append(amount))
	c.auto_choose = _attack_enemy_zero
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.VICTORY)
	t.eq(result.xp, 7)
	t.eq(result.gold, 12)
	t.eq(result.items, [{"item_id": &"potion", "qty": 2}])
	t.eq(result.entity_id, "slime_1")
	t.eq(b["state"].gold, gold_before + 12)
	t.eq(b["state"].inventory.count(&"potion"), 2)
	t.eq(b["state"].player_stats.experience, 7)
	t.eq(seen, [7])
	_done(b)

func test_enough_experience_emits_level_up(t) -> void:
	var b := _battle(10, 4)
	var c: RpgBattleController = b["controller"]
	(b["data"].enemies[0] as RpgEnemyDefinition).xp_reward = 25  # level 1 needs 10, level 2 needs 28
	c.setup(b["data"], FixedRng.new())
	var levels: Array = []
	RpgUtil.events().level_up.connect(func(_id: StringName, level: int) -> void: levels.append(level))
	c.auto_choose = _attack_enemy_zero
	await c.run()
	t.eq(levels, [2])
	t.eq(b["state"].player_stats.level, 2)
	t.eq(c.level_ups.size(), 1)
	t.eq(c.level_ups[0]["level"], 2)
	_done(b)

func test_run_escapes_with_a_good_roll(t) -> void:
	var rng := FixedRng.new()
	rng.roll = 0.0
	var b := _battle(30, 4, rng)
	var c: RpgBattleController = b["controller"]
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary: return {"command_id": &"run"}
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.ESCAPED)
	t.eq(b["states"].slice(-3), [S.CHECK, S.ESCAPED, S.END])
	t.eq(b["state"].player_stats.hp, 30, "the slime's action was skipped after the escape")
	t.eq(result.xp, 0)
	_done(b)

func test_a_failed_escape_loses_the_round(t) -> void:
	var rng := FixedRng.new()
	rng.roll = 0.99
	var b := _battle(30, 4, rng)
	var c: RpgBattleController = b["controller"]
	var asked := [0]
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary:
		asked[0] += 1
		if asked[0] == 2:
			rng.roll = 0.5  # 0.99 would also miss every attack (the hit chance is 0.99)
		return {"command_id": &"run"} if asked[0] == 1 else {"command_id": &"attack", "target_index": 0}
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.VICTORY)
	t.eq(c.round_number, 3, "one lost round, then two rounds of attacks")
	_done(b)

func test_running_is_refused_when_escape_is_not_allowed(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	b["data"].can_escape = false
	c.can_escape = false
	t.ok(not c.command_by_id(&"run").can_use(c.party[0], c))
	var rounds := [0]
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary:
		rounds[0] += 1
		return {"command_id": &"run"}  # refused: becomes an attack
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.VICTORY)
	_done(b)

func test_skill_is_disabled_without_known_skills(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	t.ok(not c.command_by_id(&"skill").can_use(c.party[0], c), "the hero has no definition, so no skills")
	t.eq(c.command_by_id(&"skill").label, "BATTLE_SKILL")
	_done(b)

func test_item_heals_and_is_consumed(t) -> void:
	var b := _battle(30, 4)
	var c: RpgBattleController = b["controller"]
	b["state"].player_stats.hp = 10
	b["state"].inventory.add(&"potion", 2)
	var item: RpgItemCommand = c.command_by_id(&"item")
	t.ok(item.can_use(c.party[0], c))
	var used := [false]
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary:
		if not used[0]:
			used[0] = true
			return {"command_id": &"item", "target_index": 0, "item_id": &"potion"}
		return {"command_id": &"attack", "target_index": 0}
	var hp_after_first_round := [-1]
	c.state_changed.connect(func(s: int) -> void:
		if s == S.CHECK and hp_after_first_round[0] < 0:
			hp_after_first_round[0] = b["state"].player_stats.hp)
	await c.run()
	t.eq(b["state"].inventory.count(&"potion"), 1)
	# Round 1: the hero is faster (speed 6 vs 4), heals 10 -> 20 first, then the slime hits for 6 -> 14.
	t.eq(hp_after_first_round[0], 14)
	_done(b)

func test_item_command_needs_a_usable_item(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	t.ok(not c.command_by_id(&"item").can_use(c.party[0], c), "no potion in the inventory")
	b["state"].inventory.add(&"potion", 1)
	t.ok(c.command_by_id(&"item").can_use(c.party[0], c))
	_done(b)

func test_a_potion_at_full_health_has_no_effect_and_is_kept(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	b["state"].inventory.add(&"potion", 1)
	var user := c.party[0]
	user.chosen_item = &"potion"
	var entries := c.command_by_id(&"item").execute(user, [user] as Array[RpgBattleActor], c)
	t.eq(entries[0]["type"], "text")
	t.eq(b["state"].inventory.count(&"potion"), 1)
	_done(b)

func test_enemy_heals_itself_when_low(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	var enemy := c.enemies[0]
	enemy.behavior = {"items": ["potion"]}
	c._give_items(enemy, enemy.behavior["items"])
	enemy.stats.hp = 5  # below 25% of 30
	var choice := c._choose_enemy(enemy)
	t.eq(choice["command"].id, &"item")
	t.eq(choice["item_id"], &"potion")
	enemy.stats.hp = 20
	var attack := c._choose_enemy(enemy)
	t.eq(attack["command"].id, &"attack", "healthy enemies attack")
	t.ok(attack["targets"][0] == c.party[0])
	_done(b)

func test_enemy_weights_can_choose_defend(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["controller"]
	var enemy := c.enemies[0]
	enemy.behavior = {"turn_based": {"attack": 0.0, "defend": 1.0}}
	t.eq(c._choose_enemy(enemy)["command"].id, &"defend")
	enemy.behavior = {"turn_based": {"attack": 1.0, "defend": 0.0}}
	t.eq(c._choose_enemy(enemy)["command"].id, &"attack")
	_done(b)

func test_the_same_seed_gives_the_same_battle(t) -> void:
	var finals: Array = []
	for i in 2:
		var rng := RpgRng.new()
		rng.seed_value(777)
		var b := _battle(60, 6, rng)
		var c: RpgBattleController = b["controller"]
		c.auto_choose = _attack_enemy_zero
		await c.run()
		finals.append([b["state"].player_stats.hp, c.round_number, c.history.size()])
		_done(b)
	t.eq(finals[0], finals[1])

func test_two_enemies_get_letters_and_the_hero_works_through_both(t) -> void:
	var state := Fixtures.install_state({&"potion": _potion()})
	state.player_stats = RpgStats.new()
	state.player_stats.attack = 10
	state.player_stats.speed = 6
	var def := _enemy_def(15, 1)
	var data := RpgEncounterData.new()
	data.enemies = [def, def]
	var c := RpgBattleController.new()
	c.setup(data, FixedRng.new())
	t.eq(c.enemies[0].display_name, "Slime A")
	t.eq(c.enemies[1].display_name, "Slime B")
	t.ok(c.enemies[0].stats != c.enemies[1].stats, "each enemy has its own stats")
	c.auto_choose = _attack_enemy_zero
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.VICTORY)
	t.eq(result.xp, 10)
	c.free()
	Fixtures.uninstall_state()
