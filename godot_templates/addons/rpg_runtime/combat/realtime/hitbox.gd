class_name RpgHitbox
extends Area2D
## A damaging area that is switched on only while an attack can hit. Layers: player hitbox 7
## (mask 10), enemy hitbox 8 (mask 9). Every hurtbox is hit at most once per activation.

signal hit(hurtbox: RpgHurtbox)

## Attack value used when the owner has no stats.
@export var damage: int = 1
@export var knockback_strength: float = 160.0
@export var team: StringName = &"player"
@export var stun_s: float = 0.0
## Set by the player's heavy attack for the length of one swing.
var heavy := false
## Where the area sits relative to the owner's feet: `center` is the middle of the body, and the
## area is moved `reach` further out toward the facing direction by aim().
@export var center: Vector2 = Vector2(0, -12)
@export var reach: Vector2 = Vector2(8, 8)

var active := false:
	set = set_active
var _hit_this_swing: Dictionary = {}  # hurtbox instance_id -> true; cleared when activated
var _fallback_rng := RpgRng.new()

func _ready() -> void:
	area_entered.connect(_on_area_entered)
	_apply_active()

func set_active(value: bool) -> void:
	if value == active:
		return
	active = value
	if value:
		_hit_this_swing.clear()
	_apply_active()

func _apply_active() -> void:
	if not is_inside_tree():
		monitoring = active
		for child in get_children():
			if child is CollisionShape2D:
				(child as CollisionShape2D).disabled = not active
		return
	set_deferred("monitoring", active)
	for child in get_children():
		if child is CollisionShape2D:
			(child as CollisionShape2D).set_deferred("disabled", not active)

## Moves the area toward `facing`. Callers do not aim during an active swing.
func aim(facing: String) -> void:
	position = center + RpgRealtimeMath.facing_vector(facing) * reach

## The actor that swings this hitbox: the nearest ancestor with components (an RpgActor, or a
## side-view actor, which has the same `component(name)`).
func owner_actor() -> Node2D:
	return RpgRealtimeMath.actor_of(self)

func _attacker_stats() -> RpgStats:
	return RpgRealtimeMath.stats_of(owner_actor())

func _on_area_entered(area: Area2D) -> void:
	try_hit(area)

func _physics_process(_delta: float) -> void:
	if not active or not monitoring:
		return
	# Hurtboxes that were already inside when the swing began do not emit area_entered.
	for area in get_overlapping_areas():
		try_hit(area)

## Applies the hit when `area` is an enemy hurtbox not hit during this swing. Returns true on a hit.
func try_hit(area: Area2D) -> bool:
	var hurtbox := area as RpgHurtbox
	if not active or hurtbox == null or hurtbox.team == team:
		return false
	var id := hurtbox.get_instance_id()
	if _hit_this_swing.has(id):
		return false
	_hit_this_swing[id] = true
	var landed := hurtbox.receive(build_info(hurtbox))
	if landed:
		var state := RpgUtil.state()
		var stats := _attacker_stats()
		if state != null and stats != null:
			state.wear_stats(stats, &"weapon")  # only gear with a durability wears (1.5.0)
		hit.emit(hurtbox)
	return landed

func build_info(hurtbox: RpgHurtbox) -> RpgDamageInfo:
	var info := RpgDamageInfo.new()
	var actor := owner_actor()
	info.source = actor
	var stats := _attacker_stats()
	var state := RpgUtil.state()
	var attack := damage
	if stats != null:
		attack = roundi(state.effective_stat(stats, &"attack")) if state != null else stats.attack
	var crit_chance := RpgRealtimeMath.DEFAULT_CRIT_CHANCE
	if stats != null:
		crit_chance = RpgUtil.to_float(stats.extra.get("crit_chance", RpgRealtimeMath.DEFAULT_CRIT_CHANCE))
	var rng: RpgRng = state.rng if state != null else _fallback_rng
	var rolled := RpgRealtimeMath.roll_damage(attack, hurtbox.defense(), crit_chance, rng)
	info.amount = RpgUtil.to_int(rolled["amount"])
	if heavy:
		info.amount = RpgRealtimeMath.heavy_damage(info.amount)
	info.crit = RpgUtil.to_bool(rolled["crit"])
	info.stun_s = stun_s
	var from := actor.global_position if actor != null else global_position
	var target := hurtbox.get_parent() as Node2D
	var away := (target.global_position if target != null else hurtbox.global_position) - from
	if away.length() < 0.01:
		away = RpgRealtimeMath.facing_of(actor) if actor != null else Vector2.DOWN
	info.knockback = away.normalized() * knockback_strength * (RpgRealtimeMath.HEAVY_KNOCKBACK_MULT if heavy else 1.0)
	return info
