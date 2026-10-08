extends RefCounted
## RpgStats, RpgLootTable, RpgRng and the small data resources (T6.02).

func test_xp_to_next_curve(t) -> void:
	var s := RpgStats.new()
	t.eq(s.xp_to_next(), 10)
	s.level = 2
	t.eq(s.xp_to_next(), 28)
	s.level = 3
	t.eq(s.xp_to_next(), 52)

func test_get_stat_reads_properties_and_extra(t) -> void:
	var s := RpgStats.new()
	s.attack = 7
	s.extra = {"crit_chance": 0.25}
	t.near(s.get_stat(&"attack"), 7.0)
	t.near(s.get_stat(&"crit_chance"), 0.25)
	t.near(s.get_stat(&"nonexistent"), 0.0)

func test_modifiers_add_first_then_multiply(t) -> void:
	var s := RpgStats.new()
	s.attack = 10
	var mods := [
		{"stat": "attack", "add": 2},
		{"stat": "attack", "add": 3, "mul": 2.0},
		{"stat": "defense", "add": 99},
	]
	# (10 + 2 + 3) * 2.0
	t.near(s.get_stat(&"attack", mods), 30.0)

func test_add_experience_across_two_levels(t) -> void:
	var s := RpgStats.new()
	s.hp = 1
	# 10 to leave level 1, 28 to leave level 2: 38 reaches level 3 exactly.
	var gained := s.add_experience(38)
	t.eq(gained, 2)
	t.eq(s.level, 3)
	t.eq(s.experience, 0)
	t.eq(s.max_hp, 26)
	t.eq(s.attack, 7)
	t.eq(s.defense, 4)
	t.eq(s.speed, 6, "speed grows on every 2nd level only")
	t.eq(s.hp, s.max_hp, "hp refills on level up")

func test_add_experience_below_threshold_keeps_the_level(t) -> void:
	var s := RpgStats.new()
	t.eq(s.add_experience(9), 0)
	t.eq(s.level, 1)
	t.eq(s.experience, 9)
	t.eq(s.add_experience(0), 0)

func test_stats_round_trip_through_a_dictionary(t) -> void:
	var s := RpgStats.new()
	s.attack = 9
	s.hp = 4
	s.extra = {"crit_chance": 0.5, "n": 3}
	var parsed: Variant = JSON.parse_string(JSON.stringify(s.to_dict()))
	var back := RpgStats.from_dict(parsed)
	t.eq(back.attack, 9)
	t.eq(back.hp, 4)
	t.near(float(back.extra["crit_chance"]), 0.5)
	t.eq(back.extra["n"], 3)

func test_loot_roll_is_deterministic_for_a_seed(t) -> void:
	var table := RpgLootTable.new()
	table.entries = [
		{"item_id": "potion", "chance": 0.5, "min": 1, "max": 3},
		{"item_id": "gem", "chance": 1.0, "min": 2, "max": 2},
	]
	var a := RpgRng.new()
	a.seed_value(42)
	var b := RpgRng.new()
	b.seed_value(42)
	t.eq(table.roll(a), table.roll(b))
	var rolled := table.roll(a)
	var gem := 0
	for entry in rolled:
		if entry["item_id"] == &"gem":
			gem = int(entry["qty"])
	t.eq(gem, 2, "a chance of 1.0 always drops")

func test_loot_chance_zero_never_drops(t) -> void:
	var table := RpgLootTable.new()
	table.entries = [{"item_id": "potion", "chance": 0.0, "min": 1, "max": 1}]
	var rng := RpgRng.new()
	rng.seed_value(1)
	for i in 20:
		t.eq(table.roll(rng).size(), 0)

func test_rng_state_round_trip(t) -> void:
	var rng := RpgRng.new()
	rng.seed_value(7)
	rng.randf()
	var saved := rng.get_state()
	var expected := rng.randi_range(0, 1000000)
	rng.set_state(saved)
	t.eq(rng.randi_range(0, 1000000), expected)

func test_rng_pick_and_ranges(t) -> void:
	var rng := RpgRng.new()
	rng.seed_value(3)
	t.ok(rng.pick([]) == null)
	t.eq(rng.pick([5]), 5)
	var f := rng.randf_range(2.0, 3.0)
	t.ok(f >= 2.0 and f <= 3.0)
	var r := RpgRng.new()
	r.seed_value(3)
	var s := RpgRng.new()
	s.seed_value(3)
	t.eq(r.randf(), s.randf())

func test_data_resources_have_the_documented_defaults(t) -> void:
	var item := RpgItemDefinition.new()
	t.eq(item.max_stack, 99)
	t.eq(item.category, RpgItemDefinition.Category.CONSUMABLE)
	var enemy := RpgEnemyDefinition.new()
	t.eq(enemy.xp_reward, 5)
	t.eq(enemy.gold_reward, 3)
	var ng := RpgNewGameData.new()
	t.eq(ng.gold, 50)
	t.eq(ng.start_spawn, &"default")
	var enc := RpgEncounterData.new()
	t.ok(enc.can_escape)
	var res := RpgEncounterResult.new()
	t.eq(res.outcome, RpgEncounterResult.Outcome.VICTORY)
	var actor := RpgActorDefinition.new()
	t.ok(actor.base_stats == null)

func test_restore_numbers_turns_integral_floats_into_ints(t) -> void:
	var v: Variant = RpgUtil.restore_numbers({"a": 3.0, "b": [1.0, 2.5], "c": {"d": 4.0}})
	t.eq(typeof(v["a"]), TYPE_INT)
	t.eq(typeof(v["b"][0]), TYPE_INT)
	t.eq(typeof(v["b"][1]), TYPE_FLOAT)
	t.eq(typeof(v["c"]["d"]), TYPE_INT)
