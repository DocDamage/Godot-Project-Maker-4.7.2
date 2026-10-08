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
const HIT_BASE := 0.95
const HIT_PER_SPEED := 0.02
const HIT_MIN := 0.3
const MAGIC_PER_POINT := 2

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

## Chance (0..1) that an attack lands: 0.95 + (speed - target speed) x 0.02 - evade, clamped to
## 0.3..1, then times `factor` (blind halves it).
static func hit_chance(speed: int, target_speed: int, evade: float, factor: float = 1.0) -> float:
	return clampf(HIT_BASE + (speed - target_speed) * HIT_PER_SPEED - evade, HIT_MIN, 1.0) * factor

## True when the attack lands. Draws one number, and none when the chance is 1 or more.
static func roll_hit(chance: float, rng: RpgRng) -> bool:
	if chance >= 1.0:
		return true
	return rng.randf() < chance

## Magic damage before the element: (power + magic x 2 - resistance) x spread, at least 1. One draw.
static func roll_magic(power: int, magic: int, resistance: int, rng: RpgRng) -> int:
	var base := maxi(1, power + magic * MAGIC_PER_POINT - resistance)
	return maxi(1, floori(base * rng.randf_range(SPREAD_MIN, SPREAD_MAX)))

## Healing: (power + magic x 2) x spread, at least 1. One draw.
static func roll_heal(power: int, magic: int, rng: RpgRng) -> int:
	return maxi(1, floori(maxi(1, power + magic * MAGIC_PER_POINT) * rng.randf_range(SPREAD_MIN, SPREAD_MAX)))

## Damage after the target's element rate: weak doubles, 0 is none, a negative rate heals (the
## result is negative then).
static func apply_rate(amount: int, rate: float) -> int:
	if rate == 1.0:
		return amount
	if rate == 0.0:
		return 0
	var scaled := floori(absf(amount * rate))
	var at_least := maxi(1, scaled)
	return -at_least if rate < 0.0 else at_least

## True when a status with this chance takes hold. Draws one number unless the chance is 0 or 1.
static func roll_chance(chance: float, rng: RpgRng) -> bool:
	if chance >= 1.0:
		return true
	if chance <= 0.0:
		return false
	return rng.randf() < chance

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
