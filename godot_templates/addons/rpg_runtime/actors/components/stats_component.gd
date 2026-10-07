class_name RpgStatsComponent
extends Node
## Holds an actor's RpgStats. The player shares GameState.player_stats; everyone else gets a copy
## of the definition's base stats.

signal hp_changed(hp: int, max_hp: int)
signal died

var stats: RpgStats
var actor: RpgActor

func _ready() -> void:
	actor = _find_actor()
	if actor != null and actor.is_in_group("player"):
		var state := RpgUtil.state()
		if state != null and state.get("player_stats") != null:
			stats = state.get("player_stats")
	if stats == null:
		if actor != null and actor.definition != null and actor.definition.base_stats != null:
			stats = actor.definition.base_stats.duplicate(true) as RpgStats
		else:
			stats = RpgStats.new()

func _find_actor() -> RpgActor:
	var node := get_parent()
	while node != null:
		if node is RpgActor:
			return node
		node = node.get_parent()
	return null

func is_player() -> bool:
	return actor != null and actor.is_in_group("player")

func is_dead() -> bool:
	return stats != null and stats.hp <= 0

## Applies already-computed damage (at least 1 when amount > 0). Returns the damage dealt.
func take_damage(amount: int) -> int:
	if stats == null or amount <= 0 or stats.hp <= 0:
		return 0
	var dealt := mini(amount, stats.hp)
	stats.hp -= dealt
	hp_changed.emit(stats.hp, stats.max_hp)
	if is_player():
		RpgUtil.emit(&"player_damaged", [dealt])
	if stats.hp <= 0:
		died.emit()
	return dealt

## Heals up to max_hp. Returns the amount healed.
func heal(amount: int) -> int:
	if stats == null or amount <= 0:
		return 0
	var healed := mini(amount, stats.max_hp - stats.hp)
	if healed <= 0:
		return 0
	stats.hp += healed
	hp_changed.emit(stats.hp, stats.max_hp)
	if is_player():
		RpgUtil.emit(&"player_healed", [healed])
	return healed
