class_name RpgHurtbox
extends Area2D
## The part of an actor that can be hit. Layers: player hurtbox 9, enemy hurtbox 10.

signal damaged(info: RpgDamageInfo)

## Every hurtbox in the tree: what a shot flying on the ground (RpgProjectile.on_ground) looks at.
const GROUP := &"rpg_hurtboxes"
## The width of a body whose hurtbox has no shape it can measure.
const FALLBACK_WIDTH := 8.0

@export var team: StringName = &"player"
@export var health_path: NodePath = NodePath("../Health")
## Seconds of invulnerability after a hit (player 0.6, enemies 0.15).
@export var invuln_s: float = 0.0

var invulnerable_until_ms := 0

func _ready() -> void:
	add_to_group(GROUP)

## Where the body stands on the ground, in world coordinates: a rectangle around the feet of the
## node that holds the hurtbox (an actor's origin is its feet), as wide as the hurtbox's shape and
## as deep as it is wide (a body seen from above). It does not depend on how tall the body is: a
## shot flying on the ground of a top-down or isometric map meets a slime and a giant alike.
func ground_rect() -> Rect2:
	var holder := get_parent() as Node2D
	var feet := RpgUtil.world_position(holder) if holder != null else RpgUtil.world_position(self)
	var width := FALLBACK_WIDTH
	for child in get_children():
		var shape_node := child as CollisionShape2D
		if shape_node == null or shape_node.disabled or shape_node.shape == null:
			continue
		var rect := shape_node.shape as RectangleShape2D
		var circle := shape_node.shape as CircleShape2D
		var capsule := shape_node.shape as CapsuleShape2D
		if rect != null:
			width = rect.size.x
		elif circle != null:
			width = circle.radius * 2.0
		elif capsule != null:
			width = capsule.radius * 2.0
		width *= absf(shape_node.scale.x)
		break
	width *= _scale_in_world()
	return Rect2(feet - Vector2(width, width) * 0.5, Vector2(width, width))

func _scale_in_world() -> float:
	var out := 1.0
	var at: Node = self
	while at is Node2D:
		out *= absf((at as Node2D).scale.x)
		at = at.get_parent()
	return out

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
	var state := RpgUtil.state()
	var s := h.stats()
	if state != null and s != null and info.amount > 0:
		state.wear_from_hit(s)  # only gear with a durability wears (1.5.0)
	if invuln_s > 0.0:
		make_invulnerable(invuln_s)
	damaged.emit(info)
	return true
