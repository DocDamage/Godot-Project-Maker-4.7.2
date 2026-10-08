extends RefCounted
## Battle depth (T12.71): hit and evade, elements, MP and skills, statuses, the enemy AI rules,
## cure and MP items, MP on the stats.

const Fixtures := preload("../lib/fixtures.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")

## No spread, no crits; `roll` is every randf (0.5 hits everything that is not hopeless).
class FixedRng extends RpgRng:
	var roll := 0.5
	var draws := 0
	func randf_range(_a: float, _b: float) -> float:
		draws += 1
		return 1.0
	func randf() -> float:
		draws += 1
		return roll
	func randi_range(from: int, _to: int) -> int:
		return from
	func pick(items: Array) -> Variant:
		return null if items.is_empty() else items[0]

static func _skill(id: StringName, kind: RpgSkillDefinition.Kind, targets: int, mp: int, power: int, extra: Dictionary = {}) -> RpgSkillDefinition:
	var s := RpgSkillDefinition.new()
	s.id = id
	s.kind = kind
	s.targets = targets
	s.mp_cost = mp
	s.power = power
	for key: String in extra:
		s.set(key, extra[key])
	return s

static func _skills() -> Dictionary:
	var cures: Array[StringName] = [&"poison"]
	return {
		&"fire": _skill(&"fire", RpgSkillDefinition.Kind.MAGIC, RpgBattleCommand.TARGET_ONE_ENEMY, 3, 6, {"element": &"fire"}),
		&"blast": _skill(&"blast", RpgSkillDefinition.Kind.MAGIC, RpgBattleCommand.TARGET_ALL_ENEMIES, 4, 2),
		&"cure": _skill(&"cure", RpgSkillDefinition.Kind.HEAL, RpgBattleCommand.TARGET_ONE_ALLY, 2, 6, {"cures": cures}),
		&"hush": _skill(&"hush", RpgSkillDefinition.Kind.STATUS, RpgBattleCommand.TARGET_ONE_ENEMY, 1, 0, {"status": &"silence"}),
		&"lull": _skill(&"lull", RpgSkillDefinition.Kind.STATUS, RpgBattleCommand.TARGET_ONE_ENEMY, 0, 0, {"status": &"sleep"}),
		&"venom": _skill(&"venom", RpgSkillDefinition.Kind.PHYSICAL, RpgBattleCommand.TARGET_ONE_ENEMY, 0, 0, {"status": &"poison", "status_chance": 1.0}),
	}

static func _stats(hp: int, attack: int, defense: int, speed: int) -> RpgStats:
	var s := RpgStats.new()
	s.max_hp = hp
	s.hp = hp
	s.attack = attack
	s.defense = defense
	s.speed = speed
	return s

static func _enemy(id: String, hp: int, behavior: Dictionary = {}) -> RpgBattleActor:
	var def := RpgEnemyDefinition.new()
	def.id = StringName(id)
	def.behavior = behavior
	var stats := _stats(hp, 4, 1, 4)
	def.base_stats = stats
	var foe := RpgBattleActor.make(StringName(id), id.capitalize(), stats, false)
	foe.definition = def
	foe.behavior = behavior
	return foe

## The hero (hp 30, attack 10, defense 2, speed 6, magic 2, 10 MP, knows every test skill) against
## a slime and a bat (hp 40 each, attack 4, defense 1, speed 4).
func _battle(roll: float = 0.5) -> Dictionary:
	var state := Fixtures.install_state({&"antidote": _antidote(), &"ether": Fixtures.item(&"ether", 99, &"mp", 5)})
	state.player_stats = _stats(30, 10, 2, 6)
	state.player_stats.magic = 2
	state.player_stats.max_mp = 10
	state.player_stats.mp = 10
	var hero_def := RpgActorDefinition.new()
	hero_def.id = &"hero"
	hero_def.skills = {"fire": 1, "blast": 1, "cure": 1, "hush": 1, "lull": 5}
	var hero := RpgBattleActor.make(&"hero", "Hero", state.player_stats, true)
	hero.definition = hero_def
	var party: Array[RpgBattleActor] = [hero]
	var foes: Array[RpgBattleActor] = [_enemy("slime", 40), _enemy("bat", 40)]
	var c := RpgBattleController.new()
	var rng := FixedRng.new()
	rng.roll = roll
	c.rng = rng
	c.skills = _skills()
	c.set_actors(party, foes)
	return {"state": state, "c": c, "hero": hero, "slime": foes[0], "bat": foes[1], "rng": rng}

func _done(b: Dictionary) -> void:
	(b["c"] as Node).free()
	Fixtures.uninstall_state()

static func _antidote() -> RpgItemDefinition:
	var item := Fixtures.item(&"antidote", 99, &"cure")
	var cures: Array[StringName] = [&"poison"]
	item.cures = cures
	return item

static func _texts(entries: Array) -> Array[String]:
	var out: Array[String] = []
	for e: Dictionary in entries:
		out.append(str(e["text"]))
	return out

## Runs one command for `actor` the way a round does (targets as the controller would pick them).
static func _act(c: RpgBattleController, actor: RpgBattleActor, raw: Dictionary) -> Array[Dictionary]:
	var choice: Dictionary = c._sanitize(actor, raw)
	var command: RpgBattleCommand = choice["command"]
	var chosen: Array[RpgBattleActor] = choice["targets"]
	actor.chosen_item = choice["item_id"]
	actor.chosen_skill = choice["skill_id"]
	var out := command.execute(actor, chosen, c)
	actor.chosen_skill = &""
	actor.chosen_item = &""
	return out

# ---------------------------------------------------------------- hit and evade, elements

func test_hit_chance_from_speed_evade_and_blind(t) -> void:
	t.near(RpgBattleMath.hit_chance(6, 4, 0.0), 0.99)
	t.near(RpgBattleMath.hit_chance(4, 6, 0.0), 0.91)
	t.near(RpgBattleMath.hit_chance(5, 5, 0.25), 0.70)
	t.near(RpgBattleMath.hit_chance(20, 1, 0.0), 1.0, 0.0001)
	t.near(RpgBattleMath.hit_chance(1, 60, 0.0), 0.3)
	t.near(RpgBattleMath.hit_chance(5, 5, 0.0, 0.5), 0.475)
	var rng := FixedRng.new()
	t.ok(RpgBattleMath.roll_hit(1.0, rng) and rng.draws == 0, "a sure hit draws nothing")
	rng.roll = 0.96
	t.ok(not RpgBattleMath.roll_hit(0.95, rng) and rng.draws == 1)

func test_element_rates(t) -> void:
	t.eq(RpgBattleMath.apply_rate(10, 1.0), 10)
	t.eq(RpgBattleMath.apply_rate(10, 2.0), 20)
	t.eq(RpgBattleMath.apply_rate(9, 0.5), 4)
	t.eq(RpgBattleMath.apply_rate(1, 0.5), 1, "a resisted hit still does 1")
	t.eq(RpgBattleMath.apply_rate(10, 0.0), 0)
	t.eq(RpgBattleMath.apply_rate(10, -1.0), -10, "absorbed: negative")
	var b := _battle()
	var slime: RpgBattleActor = b["slime"]
	(slime.definition as RpgEnemyDefinition).element_rates = {"fire": 2.0, &"ice": 0.5}
	t.near(slime.element_rate(&"fire"), 2.0)
	t.near(slime.element_rate(&"ice"), 0.5, 0.0001)
	t.near(slime.element_rate(&"thunder"), 1.0)
	t.near(slime.element_rate(&""), 1.0)
	# the player side: the definition and what it wears, the lowest listed rate counts
	var state: Node = b["state"]
	var cloak := Fixtures.item(&"cloak", 1)
	cloak.category = RpgItemDefinition.Category.ARMOR
	cloak.element_rates = {"fire": 0.5}
	var immune: Array[StringName] = [&"sleep"]
	cloak.status_immune = immune
	state.items[&"cloak"] = cloak
	var hero: RpgBattleActor = b["hero"]
	hero.actor_definition().element_rates = {"fire": 2.0}
	t.near(hero.element_rate(&"fire"), 2.0, 0.0001)
	state.inventory.add(&"cloak")
	t.ok(state.equip(&"hero", &"cloak"))
	t.near(hero.element_rate(&"fire"), 0.5, 0.0001)
	t.ok(hero.is_immune(&"sleep") and not hero.add_status(&"sleep"), "worn immunity")
	_done(b)

func test_a_miss_is_logged_and_does_nothing(t) -> void:
	var b := _battle(0.995)
	var c: RpgBattleController = b["c"]
	var slime: RpgBattleActor = b["slime"]
	var entries := _act(c, b["hero"], {"command_id": &"attack", "target_index": 0})
	t.eq(entries.size(), 1)
	t.eq(entries[0]["type"], "miss")
	t.eq(entries[0]["text"], "Hero attacks Slime, but misses.")
	t.eq(slime.stats.hp, 40)
	slime.add_status(&"sleep")
	entries = _act(c, b["hero"], {"command_id": &"attack", "target_index": 0})
	t.eq(entries[0]["type"], "damage", "a sleeping target is always hit")
	t.ok(not slime.has_status(&"sleep"), "and the hit wakes it")
	t.ok(_texts(entries).has("Slime wakes up."))
	_done(b)

# ---------------------------------------------------------------- skills and MP

func test_the_skill_list_follows_level_mp_and_silence(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var hero: RpgBattleActor = b["hero"]
	var skill_command: RpgSkillCommand = c.command_by_id(&"skill")
	var ids: Array[String] = []
	for s in skill_command.usable_skills(hero, c):
		ids.append(String(s.id))
	t.eq(ids, ["blast", "cure", "fire", "hush"], "lull is learned at level 5")
	hero.stats.mp = 2
	ids.clear()
	for s in skill_command.usable_skills(hero, c):
		ids.append(String(s.id))
	t.eq(ids, ["cure", "hush"], "only what 2 MP pays for")
	hero.stats.mp = 10
	hero.add_status(&"silence")
	t.ok(not skill_command.can_use(hero, c), "silence blocks every skill")
	var choice: Dictionary = c._sanitize(hero, {"command_id": &"skill", "skill_id": &"fire"})
	t.eq((choice["command"] as RpgBattleCommand).id, &"attack", "a blocked skill becomes an attack")
	hero.remove_status(&"silence")
	choice = c._sanitize(hero, {"command_id": &"skill", "skill_id": &"lull"})
	t.eq((choice["command"] as RpgBattleCommand).id, &"attack", "so does one the hero does not know yet")
	var at_five: Array[StringName] = [&"blast", &"cure", &"fire", &"hush", &"lull"]
	t.eq(hero.actor_definition().skills_at(5), at_five)
	_done(b)

func test_fire_hits_a_weakness_and_costs_mp(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var slime: RpgBattleActor = b["slime"]
	(slime.definition as RpgEnemyDefinition).element_rates = {"fire": 2.0}
	var entries := _act(c, b["hero"], {"command_id": &"skill", "skill_id": &"fire", "target_index": 0})
	# power 6 + magic 2 x 2 - resistance 0 = 10, doubled by the weakness
	t.eq(slime.stats.hp, 20)
	t.eq((b["hero"] as RpgBattleActor).stats.mp, 7)
	var lines: Array[String] = ["Hero uses Fire!", "Slime takes 20 damage.", "A weak spot!"]
	t.eq(_texts(entries), lines)
	(slime.definition as RpgEnemyDefinition).element_rates = {"fire": -1.0}
	entries = _act(c, b["hero"], {"command_id": &"skill", "skill_id": &"fire", "target_index": 0})
	t.eq(slime.stats.hp, 30, "absorbed: healed by 10")
	t.eq(entries[1]["type"], "heal")
	(slime.definition as RpgEnemyDefinition).element_rates = {"fire": 0}
	entries = _act(c, b["hero"], {"command_id": &"skill", "skill_id": &"fire", "target_index": 0})
	t.eq(slime.stats.hp, 30)
	t.eq(entries[1]["text"], "Slime is unaffected.")
	_done(b)

func test_a_skill_for_all_enemies_and_one_for_an_ally(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var hero: RpgBattleActor = b["hero"]
	var choice: Dictionary = c._sanitize(hero, {"command_id": &"skill", "skill_id": &"blast"})
	t.eq((choice["targets"] as Array).size(), 2, "both enemies")
	_act(c, hero, {"command_id": &"skill", "skill_id": &"blast"})
	t.eq((b["slime"] as RpgBattleActor).stats.hp, 34, "2 + 2 x 2 = 6 each")
	t.eq((b["bat"] as RpgBattleActor).stats.hp, 34)
	hero.stats.hp = 10
	hero.add_status(&"poison")
	var entries := _act(c, hero, {"command_id": &"skill", "skill_id": &"cure", "target_index": 0})
	t.eq(hero.stats.hp, 20, "6 + 2 x 2")
	t.ok(not hero.has_status(&"poison"))
	t.ok(_texts(entries).has("Hero recovers from Poison."))
	t.eq(hero.stats.mp, 4, "10 - 4 - 2")
	_done(b)

func test_status_skills_and_a_physical_skill(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var hero: RpgBattleActor = b["hero"]
	var slime: RpgBattleActor = b["slime"]
	var entries := _act(c, hero, {"command_id": &"skill", "skill_id": &"hush", "target_index": 0})
	t.ok(slime.has_status(&"silence"))
	t.eq(entries[1]["text"], "Slime is silenced.")
	t.eq(entries[1]["status"], &"silence")
	entries = _act(c, hero, {"command_id": &"skill", "skill_id": &"hush", "target_index": 0})
	t.ok(slime.has_status(&"silence"), "cast again it is renewed")
	var stone: RpgEnemyDefinition = slime.definition
	var immune: Array[StringName] = [&"poison"]
	stone.status_immune = immune
	var bat: RpgBattleActor = b["bat"]
	entries = RpgBattleEffects.use_skill(bat, slime, c.skill(&"venom"), c)
	t.eq(slime.stats.hp, 33, "venom: attack 4 x 2 - defense 1 = 7")
	t.ok(not slime.has_status(&"poison"), "immune")
	entries = RpgBattleEffects.use_skill(slime, hero, c.skill(&"venom"), c)
	t.ok(hero.has_status(&"poison"))
	_done(b)

# ---------------------------------------------------------------- statuses

func test_poison_ticks_and_regen_heals_until_it_wears_off(t) -> void:
	var b := _battle()
	var hero: RpgBattleActor = b["hero"]
	hero.add_status(&"poison")
	var entries := RpgBattleEffects.end_of_round(hero)
	t.eq(hero.stats.hp, 27, "an eighth of 30, rounded down")
	t.eq(entries[0]["text"], "Hero takes 3 damage from Poison.")
	t.eq(hero.statuses[&"poison"], 0, "poison lasts the whole battle")
	hero.remove_status(&"poison")
	hero.add_status(&"regen")
	for i in 3:
		RpgBattleEffects.end_of_round(hero)
	t.eq(hero.stats.hp, 30, "regen heals a tenth (3) a round, up to the most")
	t.ok(hero.has_status(&"regen"))
	entries = RpgBattleEffects.end_of_round(hero)
	t.ok(not hero.has_status(&"regen"), "four rounds")
	t.ok(_texts(entries).has("Hero: Regen wore off."))
	var slime: RpgBattleActor = b["slime"]
	slime.stats.hp = 2
	slime.add_status(&"poison")
	entries = RpgBattleEffects.end_of_round(slime)
	t.ok(not slime.alive and slime.statuses.is_empty(), "poison can finish a battler")
	t.ok(_texts(entries).has("Slime is defeated."))
	_done(b)

func test_sleep_skips_turns_and_ends(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var slime: RpgBattleActor = b["slime"]
	var bat: RpgBattleActor = b["bat"]
	bat.stats.hp = 1
	var hero: RpgBattleActor = b["hero"]
	c._choices = {hero: c._sanitize(hero, {"command_id": &"attack", "target_index": 1}), slime: c._choose_enemy(slime), bat: c._choose_enemy(bat)}
	slime.add_status(&"sleep")  # after choosing: it fell asleep before its turn
	await c._execute_round()
	await c._end_round()
	t.ok(_texts(c.history).has("Slime is asleep."), "its turn is skipped")
	t.eq(c._idle_choice(slime)["command"].id, &"idle", "one asleep when the round starts does not choose")
	t.eq((b["hero"] as RpgBattleActor).stats.hp, 30, "nobody hit the hero")
	t.eq(slime.statuses[&"sleep"], 2, "a round counted down")
	RpgBattleEffects.end_of_round(slime)
	var entries := RpgBattleEffects.end_of_round(slime)
	t.ok(not slime.has_status(&"sleep") and _texts(entries).has("Slime wakes up."))
	_done(b)

func test_haste_and_slow_change_the_order_and_cancel_each_other(t) -> void:
	var b := _battle()
	var hero: RpgBattleActor = b["hero"]
	var slime: RpgBattleActor = b["slime"]
	var attack := RpgAttackCommand.new()
	slime.add_status(&"haste")
	t.eq(slime.stat(&"speed"), 6)
	var order := RpgTurnManager.order([{"actor": hero, "command": attack}, {"actor": slime, "command": attack}])
	t.eq((order[0]["actor"] as RpgBattleActor), hero, "6 against 6: the player side first")
	hero.add_status(&"slow")
	order = RpgTurnManager.order([{"actor": hero, "command": attack}, {"actor": slime, "command": attack}])
	t.eq((order[0]["actor"] as RpgBattleActor), slime)
	hero.add_status(&"haste")
	t.ok(hero.has_status(&"haste") and not hero.has_status(&"slow"))
	_done(b)

func test_blind_halves_the_hit_and_attacks_carry_statuses(t) -> void:
	var b := _battle(0.6)
	var c: RpgBattleController = b["c"]
	var hero: RpgBattleActor = b["hero"]
	var slime: RpgBattleActor = b["slime"]
	hero.add_status(&"blind")
	var entries := _act(c, hero, {"command_id": &"attack", "target_index": 0})
	t.eq(entries[0]["type"], "miss", "0.99 x 0.5 < 0.6")
	var def: RpgEnemyDefinition = slime.definition
	def.attack_status = &"poison"
	def.attack_status_chance = 1.0
	_act(c, slime, {"command_id": &"attack", "target_index": 0})
	t.ok(hero.has_status(&"poison"), "the slime's attack poisons")
	_done(b)

# ---------------------------------------------------------------- the enemy AI rules

func test_rule_conditions(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var slime: RpgBattleActor = b["slime"]
	var bat: RpgBattleActor = b["bat"]
	var hero: RpgBattleActor = b["hero"]
	c.round_number = 4
	t.ok(RpgBattleAi.holds("", slime, c) and RpgBattleAi.holds("always", slime, c))
	t.ok(RpgBattleAi.holds("every:2 and round>=4", slime, c))
	t.ok(not RpgBattleAi.holds("every:3", slime, c))
	t.ok(not RpgBattleAi.holds("hp<50", slime, c))
	slime.stats.hp = 19
	t.ok(RpgBattleAi.holds("hp<50 and hp>=40", slime, c), "19 of 40 is 47 %")
	t.ok(not RpgBattleAi.holds("alone", slime, c) and not RpgBattleAi.holds("ally_down", slime, c))
	bat.stats.hp = 0
	t.ok(RpgBattleAi.holds("alone and ally_down", slime, c))
	t.ok(RpgBattleAi.holds("foe_lacks:poison", slime, c))
	hero.add_status(&"poison")
	t.ok(RpgBattleAi.holds("foe_has:poison", slime, c))
	t.ok(not RpgBattleAi.holds("foe_lacks:poison", slime, c))
	t.ok(RpgBattleAi.holds("foe_hp<=100 and mp>=0", slime, c))
	b["state"].set_flag("boss", "angry", true)
	t.ok(RpgBattleAi.holds("flag:boss.angry", slime, c), "story conditions work too")
	_done(b)

func test_rules_choose_skills_targets_and_run_once(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var slime: RpgBattleActor = b["slime"]
	var hero: RpgBattleActor = b["hero"]
	slime.behavior = {"turn_based_rules": [
		{"when": "hp<50", "use": "cure", "target": "weakest", "once": true},
		{"when": "foe_lacks:silence", "use": "hush"},
		{"when": "every:2", "use": "defend"},
	]}
	var choice: Dictionary = c._choose_enemy(slime)
	t.eq(choice["skill_id"], &"hush", "the second rule: the hero is not silenced yet")
	t.eq((choice["targets"] as Array)[0], hero)
	hero.add_status(&"silence")
	c.round_number = 2
	choice = c._choose_enemy(slime)
	t.eq((choice["command"] as RpgBattleCommand).id, &"defend")
	slime.stats.hp = 10
	choice = c._choose_enemy(slime)
	t.eq(choice["skill_id"], &"cure")
	t.eq((choice["targets"] as Array)[0], slime, "weakest of its side")
	choice = c._choose_enemy(slime)
	t.eq((choice["command"] as RpgBattleCommand).id, &"defend", "the cure rule ran once")
	c.round_number = 3
	choice = c._choose_enemy(slime)
	t.eq((choice["command"] as RpgBattleCommand).id, &"attack", "no rule holds: the weights (attack)")
	_done(b)

func test_weights_name_skills_and_mp_limits_them(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var slime: RpgBattleActor = b["slime"]
	slime.behavior = {"turn_based": {"fire": 1.0}}
	var choice: Dictionary = c._choose_enemy(slime)
	t.eq(choice["skill_id"], &"fire", "an enemy without MP casts freely")
	slime.stats.max_mp = 2
	slime.stats.mp = 2
	choice = c._choose_enemy(slime)
	t.eq((choice["command"] as RpgBattleCommand).id, &"attack", "fire costs 3: an attack instead")
	slime.stats.mp = 5
	slime.chosen_skill = &"fire"
	var hero_side: Array[RpgBattleActor] = [b["hero"]]
	c.command_by_id(&"skill").execute(slime, hero_side, c)
	t.eq(slime.stats.mp, 2)
	_done(b)

func test_rule_problems(t) -> void:
	var known: Array = [&"attack", &"defend", &"fire"]
	t.eq(RpgBattleAi.problems_of(null, known).size(), 0)
	t.eq(RpgBattleAi.problems_of([{"when": "hp<50 and every:2 and flag:a.b", "use": "fire", "target": "weakest"}], known).size(), 0)
	var found := RpgBattleAi.problems_of([
		{"use": "ice"},
		{"when": "hp<<5", "use": "attack"},
		{"use": "defend", "target": "nearest"},
		{"when": "has:doom", "use": "attack"},
		"attack",
	], known)
	t.eq(found.size(), 5, str(found))
	t.ok(found[0].contains("'ice'"))
	t.ok(found[1].contains("'hp<<5'"))
	t.ok(found[2].contains("'nearest'"))
	t.ok(found[3].contains("'has:doom'"))
	t.ok(found[4].contains("not a dictionary"))
	t.eq(RpgBattleAi.problems_of("x", known), PackedStringArray(["turn_based_rules is not a list"]))

# ---------------------------------------------------------------- items and MP on the stats

func test_cure_and_mp_items(t) -> void:
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var state: Node = b["state"]
	var hero: RpgBattleActor = b["hero"]
	state.inventory.add(&"antidote", 2)
	state.inventory.add(&"ether", 1)
	var item: RpgItemCommand = c.command_by_id(&"item")
	t.eq(item.usable_items(hero, c).size(), 2)
	var entries := _act(c, hero, {"command_id": &"item", "item_id": &"antidote", "target_index": 0})
	t.eq(entries[0]["text"], "It had no effect.", "nothing to cure: the antidote is kept")
	t.eq(state.inventory.count(&"antidote"), 2)
	hero.add_status(&"poison")
	entries = _act(c, hero, {"command_id": &"item", "item_id": &"antidote", "target_index": 0})
	t.ok(not hero.has_status(&"poison"))
	t.eq(state.inventory.count(&"antidote"), 1)
	t.ok(not state.inventory.use(&"ether", hero.stats), "MP is full")
	hero.stats.mp = 3
	entries = _act(c, hero, {"command_id": &"item", "item_id": &"ether", "target_index": 0})
	t.eq(hero.stats.mp, 8)
	t.eq(entries[0]["text"], "Hero uses Ether on Hero: 5 MP restored.")
	_done(b)

func test_mp_grows_saves_and_refills(t) -> void:
	var s := RpgStats.new()
	s.add_experience(s.xp_to_next())
	t.eq(s.max_mp, 0, "no MP, none gained")
	s.max_mp = 6
	s.mp = 1
	s.add_experience(s.xp_to_next())
	t.eq(s.max_mp, 8)
	t.eq(s.mp, 8, "a level refills it")
	var restored := RpgStats.from_dict(s.to_dict())
	t.eq(restored.max_mp, 8)
	t.eq(restored.mp, 8)
	var old := s.to_dict()
	old.erase("max_mp")
	old.erase("mp")
	t.eq(RpgStats.from_dict(old).max_mp, 0, "a save from before MP")
	var state := Fixtures.install_state()
	state.player_stats.max_mp = 5
	state.player_stats.mp = 0
	state.heal_party_full()
	t.eq(state.player_stats.mp, 5)
	t.eq(RpgUtil.max_mp(state.player_stats), 5)
	Fixtures.uninstall_state()

func test_skill_problems(t) -> void:
	var fine := _skills()
	for id: StringName in fine:
		t.eq((fine[id] as RpgSkillDefinition).problems().size(), 0, String(id))
	var bad := _skill(&"", RpgSkillDefinition.Kind.STATUS, 7, -1, 0, {"status": &"doom"})
	var found := bad.problems()
	t.eq(found.size(), 4, str(found))
	var empty := _skill(&"nothing", RpgSkillDefinition.Kind.STATUS, 1, 0, 0)
	t.ok(empty.problems()[0].contains("no status"))
	t.eq(_skill(&"fire", RpgSkillDefinition.Kind.MAGIC, 1, 0, 0).label(), "Fire")

func test_the_battle_data_check_val_026(t) -> void:
	var dir := "user://test_battle_data"
	Maps.remove_tree(dir)
	for sub: String in ["skills", "actors", "enemies", "items"]:
		DirAccess.make_dir_recursive_absolute(dir + "/" + sub)
	ResourceSaver.save(_skills()[&"fire"], dir + "/skills/fire.tres")
	ResourceSaver.save(_skill(&"doom", RpgSkillDefinition.Kind.STATUS, 1, 0, 0, {"status": &"doom"}), dir + "/skills/doom.tres")
	var actor := RpgActorDefinition.new()
	actor.id = &"mira"
	actor.skills = {"fire": 1, "zap": 3}
	ResourceSaver.save(actor, dir + "/actors/mira.tres")
	var enemy := RpgEnemyDefinition.new()
	enemy.id = &"slime"
	enemy.attack_status = &"rot"
	enemy.behavior = {"turn_based": {"attack": 1.0, "fire": 0.5, "dance": 1.0}, "turn_based_rules": [{"when": "hp<50", "use": "ice"}]}
	ResourceSaver.save(enemy, dir + "/enemies/slime.tres")
	var item := _antidote()
	var odd: Array[StringName] = [&"poison", &"curse"]
	item.cures = odd
	ResourceSaver.save(item, dir + "/items/antidote.tres")
	var found: Array[String] = []
	for f in ContentChecks.run({"maps": dir + "/none", "items": dir + "/items", "dialogue": dir + "/none", "skills": dir + "/skills", "actors": dir + "/actors", "enemies": dir + "/enemies", "resources": [dir + "/none"], "placeholders": dir + "/none/"}):
		if f["code"] == "VAL-026":
			found.append("%s: %s" % [str(f["file"]).get_file(), f["detail"]["problem"]])
	found.sort()
	t.eq(found.size(), 6, str(found))
	t.ok(found[0].begins_with("antidote.tres") and found[0].contains("'curse'"))
	t.ok(found[1].begins_with("doom.tres") and found[1].contains("unknown status 'doom'"))
	t.ok(found[2].begins_with("mira.tres") and found[2].contains("'zap'"))
	var slime_lines := "\n".join(found.slice(3))
	t.ok(slime_lines.contains("'rot'") and slime_lines.contains("'dance'") and slime_lines.contains("'ice'"), slime_lines)
	Maps.remove_tree(dir)

# ---------------------------------------------------------------- the battle UI

## An RpgBattleUi with the unique-named nodes the scene recipe makes (outside the tree).
static func _ui() -> RpgBattleUi:
	var ui := RpgBattleUi.new()
	var layout := [
		["CommandPanel", PanelContainer.new(), ""], ["Commands", VBoxContainer.new(), "CommandPanel"],
		["ItemSubmenu", PanelContainer.new(), ""], ["ItemList", VBoxContainer.new(), "ItemSubmenu"],
		["BattleLog", PanelContainer.new(), ""], ["LogLabel", Label.new(), "BattleLog"],
		["PartyStatus", VBoxContainer.new(), ""], ["EnemyStatus", VBoxContainer.new(), ""],
	]
	for spec: Array in layout:
		var node: Node = spec[1]
		node.name = spec[0]
		var parent: Node = ui if spec[2] == "" else ui.get_node("%" + str(spec[2]))
		parent.add_child(node)
		node.owner = ui
		node.unique_name_in_owner = true
	ui._ready()
	return ui

func test_the_ui_lists_skills_and_shows_mp_and_statuses(t) -> void:
	var english := Fixtures.install_english()
	var b := _battle()
	var c: RpgBattleController = b["c"]
	var hero: RpgBattleActor = b["hero"]
	var ui := _ui()
	ui.bind(c, Callable())
	var numbers: Label = ui.get_node("%PartyStatus").get_child(0).get_child(2)
	t.eq(numbers.text, "HP 30/30  MP 10/10")
	hero.add_status(&"poison")
	hero.add_status(&"blind")
	ui.refresh()
	var name_label: Label = ui.get_node("%PartyStatus").get_child(0).get_child(0)
	t.eq(name_label.text, "Hero [Poison, Blind]")
	ui._actor = hero
	ui._mode = &"commands"
	ui._on_command_pressed(c.command_by_id(&"skill"))
	var list := ui.get_node("%ItemList")
	var texts: Array[String] = []
	for child in list.get_children():
		texts.append((child as Button).text)
	t.eq(texts, ["Blast  4 MP", "Cure  2 MP", "Fire  3 MP", "Hush  1 MP"] as Array[String])
	t.ok((ui.get_node("%ItemSubmenu") as Control).visible)
	var chosen: Array = []
	ui.choice_made.connect(func(choice: Dictionary) -> void: chosen.append(choice))
	(list.get_child(0) as Button).pressed.emit()  # blast: all enemies, no target to pick
	t.eq(chosen.size(), 1)
	t.eq(chosen[0], {"command_id": &"skill", "target_index": 0, "skill_id": &"blast"})
	hero.add_status(&"silence")
	ui._mode = &"commands"
	ui._show_skills(c.command_by_id(&"skill"))
	t.eq((list.get_child(0) as Label).text, "No skills to use", "silenced")
	ui.free()
	_done(b)
	Fixtures.uninstall_english(english)
