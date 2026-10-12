class_name RpgEnergy
extends Node
## The farmer's energy (T17.04): a maximum, spent by tools, restored by food and by sleep. At
## zero the farmer walks slowly and cannot use a tool. A child of the farm's mode.
##
## The number is kept in the flags of the game state (`farm.energy`), so it is saved with the
## game, a new game starts rested, and the save has no new key.

signal changed(value: int, maximum: int)

const FLAG_ENTITY := "farm"
const FLAG_KEY := "energy"
const MAX_ENERGY := 100

@export var max_energy: int = MAX_ENERGY

var value: int:
	get = get_value, set = set_value

var _own := MAX_ENERGY  # in a test without a game state

func get_value() -> int:
	var state := RpgUtil.state()
	if state == null:
		return clampi(_own, 0, max_energy)
	return clampi(RpgUtil.to_int(state.get_flag(FLAG_ENTITY, FLAG_KEY, max_energy), max_energy), 0, max_energy)

func set_value(amount: int) -> void:
	var before := get_value()
	var after := clampi(amount, 0, max_energy)
	_own = after
	var state := RpgUtil.state()
	if state != null:
		state.set_flag(FLAG_ENTITY, FLAG_KEY, after)
	if after != before:
		changed.emit(after, max_energy)

func is_exhausted() -> bool:
	return get_value() <= 0

## Takes `amount` away (a tool that did something). False at zero: nothing can be spent.
func spend(amount: int) -> bool:
	if is_exhausted():
		return false
	set_value(get_value() - maxi(0, amount))
	return true

## Gives `amount` back (food). Returns how much was taken: 0 when the farmer is rested.
func restore(amount: int) -> int:
	var before := get_value()
	set_value(before + maxi(0, amount))
	return get_value() - before

## A night's sleep.
func fill() -> void:
	set_value(max_energy)
