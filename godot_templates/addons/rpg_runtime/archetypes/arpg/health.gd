class_name RpgHealth
extends Node
## Hit points of an actor. The numbers live in the actor's RpgStats (found through the Stats
## component at `stats_path`), so the player's health is GameState.player_stats.hp.

signal died
signal changed(hp: int, max_hp: int)

@export var stats_path: NodePath = NodePath("../Components/Stats")

var _dead := false

func _component() -> RpgStatsComponent:
	return get_node_or_null(stats_path) as RpgStatsComponent

## The RpgStats this health reads, or null while there is none.
func stats() -> RpgStats:
	var comp := _component()
	return comp.stats if comp != null else null

func hp() -> int:
	var s := stats()
	return s.hp if s != null else 0

func max_hp() -> int:
	var s := stats()
	return s.max_hp if s != null else 0

func is_dead() -> bool:
	var s := stats()
	return _dead or (s != null and s.hp <= 0)

## hp -= amount (never below 0); emits `changed`, and `died` once when it reaches 0.
func take(info: RpgDamageInfo) -> void:
	var comp := _component()
	if comp == null or comp.stats == null or _dead or info == null:
		return
	var dealt := comp.take_damage(info.amount)
	if dealt > 0:
		changed.emit(comp.stats.hp, comp.stats.max_hp)
	if comp.stats.hp <= 0 and not _dead:
		_dead = true
		died.emit()

func heal(n: int) -> void:
	var comp := _component()
	if comp == null or comp.stats == null:
		return
	if comp.heal(n) > 0:
		changed.emit(comp.stats.hp, comp.stats.max_hp)
	if comp.stats.hp > 0:
		_dead = false

## Back to full health (respawn).
func revive() -> void:
	var s := stats()
	if s == null:
		return
	s.hp = s.max_hp
	_dead = false
	changed.emit(s.hp, s.max_hp)
