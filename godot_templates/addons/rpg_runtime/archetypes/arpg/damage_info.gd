class_name RpgDamageInfo
extends RefCounted
## One hit, passed from a hitbox to a hurtbox.

var amount: int = 0
var source: Node = null  # the attacker actor
var knockback: Vector2 = Vector2.ZERO  # direction * strength (px/s impulse)
var stun_s: float = 0.0
var crit := false
