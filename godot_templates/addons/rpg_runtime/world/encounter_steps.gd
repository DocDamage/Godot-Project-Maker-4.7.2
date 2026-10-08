class_name RpgEncounterSteps
extends RefCounted
## Counts the tiles the player walks and, at every step, asks the encounter zone under the player
## whether a random battle starts (RpgEncounterZone.roll, GameState's seeded RNG). The turn-based
## mode owns one. After a battle a few steps bring no battle (`grace_steps`).

## A jump of more than this many tiles between two frames is a door or a load, not walking.
const TELEPORT_TILES := 2.0
const GRACE_STEPS := 6

var tile_px := 16.0
## Steps that bring no battle (anywhere); set after every battle.
var grace_steps := 0
## Whole steps counted since this counter was made.
var steps_taken := 0
var _walked := 0.0
var _has_last := false
var _last := Vector2.ZERO

## Forget where the player was (a new map, a battle, a cutscene): the next position starts afresh.
func reset() -> void:
	_has_last = false
	_walked = 0.0

## The whole steps walked since the last call, given where the player is now.
func walk(at: Vector2) -> int:
	if not _has_last:
		_has_last = true
		_last = at
		return 0
	var d := at.distance_to(_last)
	_last = at
	if d > TELEPORT_TILES * tile_px:
		_walked = 0.0
		return 0
	_walked += d
	var steps := floori(_walked / tile_px)
	_walked -= steps * tile_px
	steps_taken += steps
	return steps

## One step at `at` in `map`: the zone that brings a battle now, or null. A grace step brings none.
func step(map: Node, at: Vector2, rng: RpgRng) -> RpgEncounterZone:
	if grace_steps > 0:
		grace_steps -= 1
		return null
	var zone := RpgEncounterZone.zone_at(map, at)
	if zone == null:
		return null
	return zone if zone.roll(rng) else null

## The tile size of a map, 16 when it has no tiles (RpgUtil.map_tile_px).
static func tile_of(map: Node) -> float:
	return float(RpgUtil.map_tile_px(map))
