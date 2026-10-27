class_name RpgEnemyAi
extends RpgActor
## A real-time enemy. This script only holds the state machine (IDLE, WANDER, ALERT, CHASE, ATTACK,
## HURT, STUNNED, DEAD); what an enemy can do lives in the components under "Components":
## Detection (can_see_player), Chase (step), Wander, EnemyAttack (try_start), EnemyShoot,
## EnemyCharge and LootDrop (drop). The numbers come from `definition.behavior`; keys that are
## missing use DEFAULT_BEHAVIOR. `kind` picks how it fights:
##   melee    walks up to the player and swings (the default);
##   shooter  keeps its distance (`keep_away_px`) and fires projectiles from `shoot_range_px`;
##   turret   never moves and fires when it sees the player;
##   charger  winds up and dashes at the player from `charge_range_px`, then stands to recover.
## Layers: enemies (3); the hurtbox is on 10, the attack hitbox on 8.

signal state_changed(from: StringName, to: StringName)

const IDLE := &"IDLE"
const WANDER := &"WANDER"
const ALERT := &"ALERT"
const CHASE := &"CHASE"
const ATTACK := &"ATTACK"
const HURT := &"HURT"
const STUNNED := &"STUNNED"
const DEAD := &"DEAD"

const ALERT_S := 0.3
const HURT_S := 0.2
const DEAD_FREE_S := 0.6
## Pixel values of the defaults are written for 16 px tiles and scale with `tile_size`.
const DEFAULT_BEHAVIOR := {
	"kind": "melee",
	"vision_px": 96, "lose_px": 160, "attack_range_px": 18, "attack_cooldown_s": 1.2,
	"windup_s": 0.35, "active_s": 0.15, "move_speed": 45, "chase_speed": 60,
	"wander_radius_px": 32, "wander_pause_s": [1.0, 2.5], "knockback_resist": 0.0,
	"nav_mode": "direct",
	"shoot_range_px": 80, "keep_away_px": 40, "projectile_speed": 120, "projectile_range_px": 160,
	"shoot_windup_s": 0.45, "shoot_cooldown_s": 1.6,
	"charge_range_px": 72, "charge_speed": 180, "charge_windup_s": 0.5, "charge_s": 0.45,
	"charge_recover_s": 0.6, "charge_cooldown_s": 1.5,
}
const PIXEL_KEYS: Array[String] = ["vision_px", "lose_px", "attack_range_px", "move_speed", "chase_speed", "wander_radius_px", "shoot_range_px", "keep_away_px", "projectile_speed", "projectile_range_px", "charge_range_px", "charge_speed"]
const KINDS: Array[String] = ["melee", "shooter", "turret", "charger"]

@export var entity_id: String = ""
@export var tile_size: float = 16.0

var behavior: Dictionary = {}
## "melee", "shooter", "turret" or "charger" (from the behavior; unknown kinds fight as melee).
var kind := "melee"
var machine: RpgStateMachine  # created in _ready: a scene that is never entered into the tree must not leak a node
var detection: RpgDetection
var chase: RpgChase
var wander: RpgWander
var attack: RpgEnemyAttack
var shoot: RpgEnemyShoot
var charge: RpgEnemyCharge
var loot: RpgLootDrop
var health: RpgHealth
var hurtbox: RpgHurtbox
var hitbox: RpgHitbox

var _alert_label: Label
var _idle_wait := 0.0
var _returning_home := false
var _hit: RpgDamageInfo = null
var _base_tint := Color.WHITE

## The defaults (scaled to the tile size) with the keys of `overrides` on top.
static func merged_behavior(overrides: Dictionary, tile: float = 16.0) -> Dictionary:
	var out: Dictionary = DEFAULT_BEHAVIOR.duplicate(true)
	var scale := tile / 16.0
	for key in PIXEL_KEYS:
		out[key] = RpgUtil.to_float(out[key]) * scale
	for key: Variant in overrides.keys():
		if out.has(key):
			out[key] = overrides[key]
	return out

func _ready() -> void:
	super._ready()
	var def := definition as RpgEnemyDefinition
	behavior = merged_behavior(def.behavior if def != null else {}, tile_size)
	detection = component("Detection") as RpgDetection
	chase = component("Chase") as RpgChase
	wander = component("Wander") as RpgWander
	attack = component("EnemyAttack") as RpgEnemyAttack
	kind = str(behavior.get("kind", "melee"))
	if not KINDS.has(kind):
		kind = "melee"
	shoot = _ensure_component("EnemyShoot", RpgEnemyShoot) as RpgEnemyShoot if kind in ["shooter", "turret"] else null
	charge = _ensure_component("EnemyCharge", RpgEnemyCharge) as RpgEnemyCharge if kind == "charger" else null
	loot = component("LootDrop") as RpgLootDrop
	health = get_node_or_null("Health") as RpgHealth
	hurtbox = get_node_or_null("Hurtbox") as RpgHurtbox
	hitbox = get_node_or_null("AttackHitbox") as RpgHitbox
	_alert_label = get_node_or_null("Alert") as Label
	var sprite := get_node_or_null("Visual") as AnimatedSprite2D
	if sprite != null:
		_base_tint = sprite.modulate
	configure()
	machine = RpgStateMachine.new()
	machine.name = "States"
	add_child(machine)
	machine.add(IDLE, _enter_idle, _update_idle)
	machine.add(WANDER, _enter_wander, _update_wander)
	machine.add(ALERT, _enter_alert, _update_alert, _exit_alert)
	machine.add(CHASE, _enter_chase, _update_chase)
	machine.add(ATTACK, _enter_attack, _update_attack, _exit_attack)
	machine.add(HURT, _enter_hurt, _update_hurt, _exit_hurt)
	machine.add(STUNNED, _enter_stunned, _update_stunned, _exit_hurt)
	machine.add(DEAD, _enter_dead, _update_dead)
	machine.changed.connect(_on_machine_changed)
	if health != null:
		health.died.connect(_on_died)
	if hurtbox != null:
		hurtbox.damaged.connect(_on_damaged)
	if hitbox != null:
		hitbox.aim(facing)
	machine.go(IDLE)

## The component of that name under "Components"; made (in _ready, never at load time) when an
## older enemy scene does not have it.
func _ensure_component(component_name: String, script: GDScript) -> Node:
	var found := component(component_name)
	if found != null:
		return found
	var holder := get_node_or_null("Components")
	if holder == null:
		return null
	var made: Node = script.new()
	made.name = component_name
	holder.add_child(made)
	if not made.is_node_ready() and not made.is_inside_tree():
		made.call("_ready")
	_cache_components()
	return made

## Hands the behavior numbers to the components.
func configure() -> void:
	if detection != null:
		detection.vision_px = RpgUtil.to_float(behavior["vision_px"])
	if chase != null:
		chase.speed = RpgUtil.to_float(behavior["chase_speed"])
		chase.lose_px = RpgUtil.to_float(behavior["lose_px"])
		chase.attack_range_px = RpgUtil.to_float(behavior["attack_range_px"])
		chase.nav_mode = str(behavior["nav_mode"])
	if wander != null:
		wander.speed = RpgUtil.to_float(behavior["move_speed"])
		wander.radius_px = RpgUtil.to_float(behavior["wander_radius_px"])
		var pause: Array = behavior["wander_pause_s"]
		wander.pause_range = Vector2(RpgUtil.to_float(pause[0]), RpgUtil.to_float(pause[1]))
		wander.home = global_position
		wander.seed_from(entity_id if entity_id != "" else String(name))
	if attack != null:
		attack.windup_s = RpgUtil.to_float(behavior["windup_s"])
		attack.active_s = RpgUtil.to_float(behavior["active_s"])
		attack.cooldown_s = RpgUtil.to_float(behavior["attack_cooldown_s"])
	if shoot != null:
		shoot.windup_s = RpgUtil.to_float(behavior["shoot_windup_s"])
		shoot.cooldown_s = RpgUtil.to_float(behavior["shoot_cooldown_s"])
		shoot.speed = RpgUtil.to_float(behavior["projectile_speed"])
		shoot.range_px = RpgUtil.to_float(behavior["projectile_range_px"])
	if charge != null:
		charge.windup_s = RpgUtil.to_float(behavior["charge_windup_s"])
		charge.dash_s = RpgUtil.to_float(behavior["charge_s"])
		charge.speed = RpgUtil.to_float(behavior["charge_speed"])
		charge.recover_s = RpgUtil.to_float(behavior["charge_recover_s"])
		charge.cooldown_s = RpgUtil.to_float(behavior["charge_cooldown_s"])

func state() -> StringName:
	return machine.state

func is_dead() -> bool:
	return machine.state == DEAD

func _on_machine_changed(from: StringName, to: StringName) -> void:
	state_changed.emit(from, to)

func _stop() -> void:
	move_dir(Vector2.ZERO)

func _face_player() -> void:
	if detection != null and detection.player_alive():
		set_facing(RpgAnimationDriver.dir_to_facing(detection.player_position() - global_position))

func _detects() -> bool:
	if detection != null and input_enabled and detection.can_see_player():
		machine.go(ALERT)
		return true
	return false

# ---------------------------------------------------------------- IDLE / WANDER

func _enter_idle() -> void:
	_stop()
	_idle_wait = wander.pause_seconds() if wander != null else 1.0

func _update_idle(delta: float) -> void:
	if _detects():
		return
	_idle_wait -= delta
	if _idle_wait <= 0.0 and wander != null and kind != "turret":
		machine.go(WANDER)

func _enter_wander() -> void:
	if wander == null:
		return
	if _returning_home:
		wander.head_home()
	else:
		wander.pick_target()

func _update_wander(delta: float) -> void:
	if _detects():
		return
	if wander == null or wander.step(delta):
		_returning_home = false
		machine.go(IDLE)

# ---------------------------------------------------------------- ALERT / CHASE

func _enter_alert() -> void:
	_stop()
	_face_player()
	if _alert_label != null:
		_alert_label.visible = true

func _update_alert(_delta: float) -> void:
	if detection == null or not detection.player_alive():
		machine.go(IDLE)
	elif machine.time_in_state >= ALERT_S:
		machine.go(CHASE)

func _exit_alert() -> void:
	if _alert_label != null:
		_alert_label.visible = false

func _enter_chase() -> void:
	if chase != null:
		chase.reset()

func _update_chase(delta: float) -> void:
	if chase == null or detection == null or not detection.player_alive():
		machine.go(IDLE)
		return
	match kind:
		"shooter", "turret":
			_update_chase_ranged(delta)
			return
		"charger":
			chase.step(delta)
			if chase.gave_up():
				_returning_home = true
				machine.go(WANDER)
			elif charge != null and chase.distance() <= RpgUtil.to_float(behavior["charge_range_px"]) and charge.can_start() and detection.can_see_player():
				machine.go(ATTACK)
			return
	chase.step(delta)
	if chase.gave_up():
		_returning_home = true
		machine.go(WANDER)
	elif attack != null and chase.in_attack_range() and attack.can_start():
		machine.go(ATTACK)

## Shooters back off when the player is closer than `keep_away_px`, close in when farther than the
## shooting range and otherwise stand and face; turrets only turn. Both fire when they see the
## player within range.
func _update_chase_ranged(delta: float) -> void:
	var d := chase.distance()
	var shoot_range := RpgUtil.to_float(behavior["shoot_range_px"])
	if d > chase.lose_px:
		chase.step(delta)  # counts the time out of reach
		if kind == "turret":
			_stop()
		if chase.gave_up():
			_returning_home = kind != "turret"
			machine.go(WANDER if kind != "turret" else IDLE)
		return
	chase.reset()
	if kind == "shooter" and d < RpgUtil.to_float(behavior["keep_away_px"]):
		move_dir(-(detection.player_position() - detection.actor_position()).normalized())
	elif kind == "shooter" and d > shoot_range * 0.9:
		chase.step(delta)
	else:
		_stop()
		_face_player()
	if shoot != null and d <= shoot_range and shoot.can_start() and detection.can_see_player():
		machine.go(ATTACK)

# ---------------------------------------------------------------- ATTACK

func _enter_attack() -> void:
	_stop()
	_face_player()
	match kind:
		"shooter", "turret":
			if shoot != null:
				shoot.try_start(detection.player_position() if detection != null else global_position)
		"charger":
			if charge != null:
				charge.try_start(detection.player_position() if detection != null else global_position)
		_:
			if attack != null:
				attack.try_start()

func _update_attack(delta: float) -> void:
	var finished := true
	match kind:
		"shooter", "turret":
			_stop()
			finished = shoot == null or shoot.update(delta)
		"charger":
			finished = charge == null or charge.update(delta)  # the dash moves the enemy itself
		_:
			_stop()
			finished = attack == null or attack.update(delta)
	if finished:
		machine.go(CHASE)

func _exit_attack() -> void:
	if attack != null:
		attack.cancel()
	if shoot != null:
		shoot.cancel()
	if charge != null:
		charge.cancel()

# ---------------------------------------------------------------- HURT / STUNNED

func _on_damaged(info: RpgDamageInfo) -> void:
	if machine.state == DEAD or (health != null and health.is_dead()):
		return
	_hit = info
	machine.go(STUNNED if info.stun_s > 0.0 else HURT)

func _apply_knockback() -> void:
	_stop()
	var movement := component("Movement") as RpgMovement
	if movement != null and _hit != null:
		movement.external_velocity = _hit.knockback * (1.0 - clampf(RpgUtil.to_float(behavior["knockback_resist"]), 0.0, 1.0))
	var sprite := get_node_or_null("Visual") as AnimatedSprite2D
	if sprite != null:
		sprite.modulate = Color(1.0, 0.6, 0.6)
		var tween := create_tween()
		tween.tween_property(sprite, "modulate", _base_tint, HURT_S)

func _enter_hurt() -> void:
	_apply_knockback()

func _update_hurt(_delta: float) -> void:
	if machine.time_in_state >= HURT_S:
		machine.go(CHASE)

func _exit_hurt() -> void:
	pass

func _enter_stunned() -> void:
	_apply_knockback()

func _update_stunned(_delta: float) -> void:
	var seconds := _hit.stun_s if _hit != null else HURT_S
	if machine.time_in_state >= maxf(seconds, HURT_S):
		machine.go(CHASE)

# ---------------------------------------------------------------- DEAD

func _on_died() -> void:
	machine.go(DEAD)

func _enter_dead() -> void:
	_stop()
	if hitbox != null:
		hitbox.active = false
	if hurtbox != null:
		hurtbox.set_deferred("monitorable", false)
	set_deferred("collision_layer", 0)
	set_deferred("collision_mask", 0)
	var sprite := get_node_or_null("Visual") as AnimatedSprite2D
	if sprite != null:
		if _driver.has_animation("death", facing):
			animation_locked = true
			_driver.play_exact("death", facing)
		elif sprite.sprite_frames != null and sprite.sprite_frames.has_animation("death"):
			animation_locked = true
			sprite.flip_h = false
			sprite.play("death")
		else:
			var fade := create_tween()
			fade.tween_property(sprite, "modulate:a", 0.0, DEAD_FREE_S)
	if loot != null:
		loot.drop()
	var state := RpgUtil.state()
	var def := definition as RpgEnemyDefinition
	if state != null and entity_id != "":
		state.set_flag(entity_id, "defeated", true)
	if entity_id != "":
		RpgUtil.emit(&"entity_defeated", [entity_id])
	if state != null and def != null:
		state.note_defeat(def.id)  # the counters of achievements (1.5.0)
	if state != null and def != null and def.xp_reward > 0:
		var levels: int = state.give_experience(def.xp_reward)
		if levels > 0:
			RpgUtil.notify(RpgArpgText.t("ARPG_LEVEL_UP", [state.player_stats.level]))

func _update_dead(_delta: float) -> void:
	if machine.time_in_state >= DEAD_FREE_S:
		queue_free()
