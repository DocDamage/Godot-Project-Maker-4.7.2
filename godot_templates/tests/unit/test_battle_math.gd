extends RefCounted
## Battle formulas and turn order (T7.01, T7.02).

## A stand-in for RpgRng: fixed spread and crit roll.
class FixedRng extends RefCounted:
	var spread := 1.0
	var roll := 0.5
	func randf_range(_a: float, _b: float) -> float:
		return spread
	func randf() -> float:
		return roll

func _rng(spread: float, roll: float) -> FixedRng:
	var r := FixedRng.new()
	r.spread = spread
	r.roll = roll
	return r

# ---------------------------------------------------------------- damage table (hand-computed)

func test_damage_table_with_fixed_numbers(t) -> void:
	# attack, defense, defending, spread, crit roll -> expected damage
	var cases := [
		[5, 2, false, 1.0, 0.5, 8],     # base 8
		[1, 10, false, 1.0, 0.5, 1],    # base max(1, -8) = 1
		[10, 3, false, 1.1, 0.5, 18],   # 17 * 1.1 = 18.7 -> 18
		[10, 3, false, 0.9, 0.5, 15],   # 17 * 0.9 = 15.3 -> 15
		[10, 3, false, 1.0, 0.01, 25],  # crit: 17 * 1.5 = 25.5 -> 25
		[10, 3, true, 1.0, 0.5, 8],     # defending: 17 / 2 = 8.5 -> 8
		[1, 10, true, 1.0, 0.5, 1],     # defending never goes below 1
		[10, 3, false, 1.0, 0.05, 17],  # a roll of exactly 0.05 is not a crit
		[10, 3, true, 1.0, 0.0, 12],    # crit then defend: 25 / 2 = 12.5 -> 12
	]
	for c in cases:
		var out := RpgBattleMath.roll_damage(c[0], c[1], c[2], _rng(c[3], c[4]))
		t.eq(out["amount"], c[5], "attack %d defense %d defending %s spread %s roll %s" % [c[0], c[1], c[2], c[3], c[4]])
	t.eq(RpgBattleMath.roll_damage(10, 3, false, _rng(1.0, 0.01))["crit"], true)
	t.eq(RpgBattleMath.roll_damage(10, 3, false, _rng(1.0, 0.5))["crit"], false)

func test_damage_with_a_seeded_rng_is_reproducible(t) -> void:
	var first: Array = []
	var second: Array = []
	for pass_index in 2:
		var rng := RpgRng.new()
		rng.seed_value(12345)
		var target := first if pass_index == 0 else second
		for i in 5:
			target.append(RpgBattleMath.roll_damage(10, 3, false, rng)["amount"])
	t.eq(first, second)
	for amount in first:
		t.ok(amount >= 15 and amount <= 25, "within the spread and crit range: %d" % amount)
	# Pinned values for seed 12345 (attack 10, defense 3): a change here means the draw order
	# or the formula changed.
	t.eq(first, [16, 15, 18, 17, 18])

# ---------------------------------------------------------------- escape

func test_escape_chance_follows_the_speed_difference(t) -> void:
	t.near(RpgBattleMath.escape_chance([5], [5]), 0.5)
	t.near(RpgBattleMath.escape_chance([10], [5]), 0.75)
	t.near(RpgBattleMath.escape_chance([4, 6], [5]), 0.5, 0.0001)
	t.near(RpgBattleMath.escape_chance([5], [8]), 0.35)

func test_escape_chance_is_clamped(t) -> void:
	t.near(RpgBattleMath.escape_chance([100], [1]), 0.95)
	t.near(RpgBattleMath.escape_chance([1], [100]), 0.1)
	t.near(RpgBattleMath.escape_chance([], []), 0.5)

# ---------------------------------------------------------------- turn order

func _actor(actor_id: String, speed: int, player_side: bool) -> RpgBattleActor:
	var stats := RpgStats.new()
	stats.speed = speed
	return RpgBattleActor.make(StringName(actor_id), actor_id, stats, player_side)

func _entry(actor: RpgBattleActor, priority: int) -> Dictionary:
	var command := RpgBattleCommand.new()
	command.priority = priority
	return {"actor": actor, "command": command}

func _ids(entries: Array) -> Array:
	var out: Array = []
	for e in entries:
		out.append(String(e["actor"].id))
	return out

func test_order_by_priority_then_speed(t) -> void:
	var slow := _actor("slow", 3, true)
	var fast := _actor("fast", 9, false)
	var guard := _actor("guard", 1, true)
	var order := RpgTurnManager.order([_entry(slow, 0), _entry(fast, 0), _entry(guard, 10)])
	t.eq(_ids(order), ["guard", "fast", "slow"])

func test_speed_ties_go_to_the_player_side_then_the_id(t) -> void:
	var order := RpgTurnManager.order([
		_entry(_actor("b_enemy", 5, false), 0),
		_entry(_actor("z_hero", 5, true), 0),
		_entry(_actor("a_enemy", 5, false), 0),
		_entry(_actor("a_hero", 5, true), 0),
	])
	t.eq(_ids(order), ["a_hero", "z_hero", "a_enemy", "b_enemy"])

func test_order_does_not_depend_on_the_input_order(t) -> void:
	var actors := [_actor("a", 5, true), _actor("b", 5, false), _actor("c", 7, false), _actor("d", 5, true)]
	var entries: Array = []
	for a in actors:
		entries.append(_entry(a, 0))
	var expected := _ids(RpgTurnManager.order(entries))
	entries.reverse()
	t.eq(_ids(RpgTurnManager.order(entries)), expected)
