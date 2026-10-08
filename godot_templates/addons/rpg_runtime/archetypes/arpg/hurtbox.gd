class_name RpgHurtbox
extends Area2D
## The part of an actor that can be hit. Layers: player hurtbox 9, enemy hurtbox 10.

signal damaged(info: RpgDamageInfo)

@export var team: StringName = &"player"
@export var health_path: NodePath = NodePath("../Health")
## Seconds of invulnerability after a hit (player 0.6, enemies 0.15).
@export var invuln_s: float = 0.0

var invulnerable_until_ms := 0

func health() -> RpgHealth:
	return get_node_or_null(health_path) as RpgHealth

func is_invulnerable() -> bool:
	return Time.get_ticks_msec() < invulnerable_until_ms

## Makes the owner immune for `seconds` (the dodge uses it). Never shortens an existing window.
func make_invulnerable(seconds: float) -> void:
	invulnerable_until_ms = maxi(invulnerable_until_ms, Time.get_ticks_msec() + int(seconds * 1000.0))

## The owner's defense, for the damage formula.
func defense() -> int:
	var h := health()
	var s := h.stats() if h != null else null
	if s == null:
		return 0
	var state := RpgUtil.state()
	return roundi(state.effective_stat(s, &"defense")) if state != null else s.defense

## Returns true when the hit landed.
func receive(info: RpgDamageInfo) -> bool:
	if info == null or is_invulnerable() or RpgSequenceRunner.running():
		return false
	var h := health()
	if h == null or h.is_dead():
		return false
	h.take(info)
	if invuln_s > 0.0:
		make_invulnerable(invuln_s)
	damaged.emit(info)
	return true
