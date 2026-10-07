class_name RpgTurnManager
extends RefCounted
## Orders the actions of one round.

## `entries` is [{actor: RpgBattleActor, command: RpgBattleCommand}]. Returns them sorted by
## (command priority desc, speed desc, player side first, id asc). Equal speeds are settled by
## the player side and then the id, never by chance, so a round is reproducible.
static func order(entries: Array) -> Array:
	var sorted := entries.duplicate()
	sorted.sort_custom(_before)
	return sorted

static func _before(a: Dictionary, b: Dictionary) -> bool:
	var actor_a: RpgBattleActor = a["actor"]
	var actor_b: RpgBattleActor = b["actor"]
	var prio_a: int = (a["command"] as RpgBattleCommand).priority
	var prio_b: int = (b["command"] as RpgBattleCommand).priority
	if prio_a != prio_b:
		return prio_a > prio_b
	if actor_a.stats.speed != actor_b.stats.speed:
		return actor_a.stats.speed > actor_b.stats.speed
	if actor_a.is_player_side != actor_b.is_player_side:
		return actor_a.is_player_side
	return String(actor_a.id) < String(actor_b.id)
