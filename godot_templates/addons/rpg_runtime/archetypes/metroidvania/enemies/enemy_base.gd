class_name RpgSideEnemy
extends RpgPlatformActor
## An enemy of a side-view room: the platform actor (it stands on floors and falls) with the shared
## health and hurtbox, and a hitbox that hurts on contact. The kinds (patrol, flyer, shooter and
## the guardian) extend this and say what it does in think().
##
## A defeated enemy stays defeated (the flag `<entity_id>.defeated`, read by RpgPersistent when
## the room is entered) until the player rests at a save station, which brings the enemies back.

signal died

const HURT_STUN_S := 0.2
const CONTACT_REARM_S := 0.5
const FADE_S := 0.35

@export var entity_id: String = ""
## How far a hit pushes it along the floor, in px/s at 16 px tiles.
@export var knockback: float = 80.0

var health: RpgHealth
var hurtbox: RpgHurtbox
## The hitbox that hurts whoever touches the enemy ("AttackHitbox").
var contact: RpgHitbox
var dead := false

var _stun := 0.0
var _rearm := 0.0
var _tint: Tween = null

func _ready() -> void:
	super._ready()
	health = get_node_or_null("Health") as RpgHealth
	hurtbox = get_node_or_null("Hurtbox") as RpgHurtbox
	contact = get_node_or_null("AttackHitbox") as RpgHitbox
	if hurtbox != null:
		hurtbox.damaged.connect(_on_damaged)
	if health != null:
		health.died.connect(_on_died)
	if contact != null:
		contact.position = contact.center  # around the body: touching it from either side hurts
		contact.active = true

## The player of the room this enemy is in, or null.
func find_player() -> Node2D:
	if not is_inside_tree():
		return null
	var room := _map_root()
	for node in get_tree().get_nodes_in_group("player"):
		if node is Node2D and (room == null or room.is_ancestor_of(node)):
			return node
	return null

## Where a body is: the middle of it, for sight lines and distances.
static func middle_of(body: Node2D) -> Vector2:
	if body.has_method(&"body_center"):
		var at: Vector2 = body.call(&"body_center")
		return at
	return body.global_position + Vector2(0, -8)

## Tiles between this enemy and `other`.
func tiles_to(other: Node2D) -> float:
	return body_center().distance_to(middle_of(other)) / maxf(1.0, tile_size)

func is_stunned() -> bool:
	return _stun > 0.0

func step(delta: float) -> void:
	if dead:
		return
	_stun = maxf(0.0, _stun - delta)
	if contact != null:  # a hitbox hits a hurtbox once per activation: arm it again and again
		_rearm -= delta
		if _rearm <= 0.0:
			_rearm = CONTACT_REARM_S
			contact.active = false
			contact.active = true
	if _stun > 0.0 or RpgSequenceRunner.running():
		move_x = 0.0
	else:
		think(delta)
	move(delta)

## What the enemy wants to do this step: set move_x, jump, shoot. The base enemy stands.
func think(_delta: float) -> void:
	move_x = 0.0

## How the enemy moves this step: the platform actor's step (gravity, floors). A flyer has its own.
func move(delta: float) -> void:
	super.step(delta)

func _on_damaged(info: RpgDamageInfo) -> void:
	if dead:
		return
	_stun = HURT_STUN_S
	var push := signf(info.knockback.x) if info != null and info.knockback.x != 0.0 else -float(facing)
	velocity.x = push * px(knockback)
	_wall_lock = HURT_STUN_S
	flash(Color(1.0, 0.45, 0.45), 0.2)

## Tints the sprite for a moment (a hit, the guardian's telegraph).
func flash(color: Color, seconds: float) -> void:
	var sprite := _driver.sprite
	if sprite == null or not is_inside_tree():
		return
	if _tint != null and _tint.is_valid():
		_tint.kill()
	sprite.modulate = color
	_tint = create_tween()
	_tint.tween_property(sprite, "modulate", Color.WHITE, seconds)

func _on_died() -> void:
	if dead:
		return
	dead = true
	velocity = Vector2.ZERO
	if contact != null:
		contact.active = false
	if hurtbox != null:
		hurtbox.set_deferred("monitorable", false)
	var state := RpgUtil.state()
	if state != null and entity_id != "":
		state.set_flag(entity_id, "defeated", true)
	reward()
	on_defeated()
	died.emit()
	RpgUtil.emit(&"entity_defeated", [entity_id])
	var sprite := _driver.sprite
	if sprite != null and is_inside_tree():
		var fade := create_tween()
		fade.tween_property(sprite, "modulate:a", 0.0, FADE_S)
		fade.tween_callback(queue_free)
	else:
		queue_free()

## What a kind does when it is defeated (the guardian opens the room).
func on_defeated() -> void:
	pass

## Experience and gold of the definition, and its loot as pickups where the enemy stood.
func reward() -> Array[Dictionary]:
	var dropped: Array[Dictionary] = []
	var state := RpgUtil.state()
	var def := definition as RpgEnemyDefinition
	if state == null or def == null:
		return dropped
	if def.xp_reward > 0 and state.give_experience(def.xp_reward) > 0:
		RpgUtil.notify(RpgMetroidvaniaStrings.t("MV_LEVEL_UP", [state.player_stats.level]))
	if def.gold_reward > 0:
		state.gold = RpgUtil.to_int(state.gold) + def.gold_reward
		RpgUtil.notify(RpgMetroidvaniaStrings.t("MV_GOLD_GAINED", [def.gold_reward]))
	if def.loot != null:
		dropped = def.loot.roll(state.rng)
	var parent := get_parent()
	for i in dropped.size():
		if parent == null:
			break
		var id: StringName = dropped[i]["item_id"]
		var item_def: RpgItemDefinition = state.items.get(id)
		var pickup := RpgPickup.create(id, RpgUtil.to_int(dropped[i]["qty"]), item_def.icon if item_def != null else null)
		pickup.position = position + Vector2((i - (dropped.size() - 1) * 0.5) * 8.0, -2.0)
		parent.add_child.call_deferred(pickup)
	return dropped
