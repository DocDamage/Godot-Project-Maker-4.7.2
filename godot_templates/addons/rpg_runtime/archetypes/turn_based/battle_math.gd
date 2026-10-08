class_name RpgBattleMath
extends RefCounted
## The battle formulas as pure static functions. `rng` is an RpgRng (tests hand over a subclass
## that returns fixed numbers).

const SPREAD_MIN := 0.9
const SPREAD_MAX := 1.1
const CRIT_CHANCE := 0.05
const CRIT_MULTIPLIER := 1.5
const DEFEND_FACTOR := 0.5
const ESCAPE_BASE := 0.5
const ESCAPE_PER_SPEED := 0.05
const ESCAPE_MIN := 0.1
const ESCAPE_MAX := 0.95

static func base_damage(attack: int, defense: int) -> int:
	return maxi(1, attack * 2 - defense)

## {amount: int, crit: bool}. Draws two numbers in a fixed order: the spread, then the crit roll.
static func roll_damage(attack: int, defense: int, defending: bool, rng: RpgRng) -> Dictionary:
	var base := base_damage(attack, defense)
	var spread: float = rng.randf_range(SPREAD_MIN, SPREAD_MAX)
	var crit: bool = rng.randf() < CRIT_CHANCE
	var multiplier := CRIT_MULTIPLIER if crit else 1.0
	var dmg := maxi(1, floori(base * spread * multiplier))
	if defending:
		dmg = maxi(1, floori(dmg * DEFEND_FACTOR))
	return {"amount": dmg, "crit": crit}

## Escape chance from the speeds of both sides: clamp(0.5 + (party_avg - enemy_avg) * 0.05, 0.1, 0.95).
static func escape_chance(party_speeds: Array, enemy_speeds: Array) -> float:
	return clampf(ESCAPE_BASE + (_average(party_speeds) - _average(enemy_speeds)) * ESCAPE_PER_SPEED, ESCAPE_MIN, ESCAPE_MAX)

static func _average(values: Array) -> float:
	if values.is_empty():
		return 0.0
	var total := 0.0
	for v: Variant in values:
		total += RpgUtil.to_float(v)
	return total / values.size()
