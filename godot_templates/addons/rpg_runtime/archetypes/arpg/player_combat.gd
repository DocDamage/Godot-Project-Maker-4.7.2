class_name RpgPlayerCombat
extends Node
## The player's combat state machine: IDLE, MOVE, ATTACK, HURT, DODGE, DEAD. A child of the player
## actor next to Health, Hurtbox and AttackHitbox (the arpg recipe adds them). The movement input is
## read by RpgPlayerInput; this node only takes over while an attack, a hurt reaction, a dodge or
## the death is running (it locks the actor's movement, facing and animation then).

signal state_changed(from: StringName, to: StringName)
signal attack_started
signal defeated  # the defeat policy is about to run (1.5 s after the death)

const IDLE := &"IDLE"
const MOVE := &"MOVE"
const ATTACK := &"ATTACK"
const HURT := &"HURT"
const DODGE := &"DODGE"
const DEAD := &"DEAD"

const DODGE_SPEED := 220.0
const DODGE_S := 0.2
const DODGE_COOLDOWN_S := 0.6
const HURT_S := 0.25
const GENERIC_ACTIVE_FROM := 0.08
const GENERIC_ACTIVE_TO := 0.2
const GENERIC_ATTACK_S := 0.35
const DEAD_DELAY_S := 1.5
## An attack pressed during the last part of an attack queues the next one.
const BUFFER_FRACTION := 0.3

var actor: RpgActor
var sprite: AnimatedSprite2D
var hitbox: RpgHitbox
var hurtbox: RpgHurtbox
var health: RpgHealth
var movement: RpgMovement
var swing: RpgSwingEffect
var machine: RpgStateMachine  # created in _ready: a scene that is never entered into the tree must not leak a node

var _driver := RpgAnimationDriver.new()
var _attack_time := 0.0
var _attack_seconds := GENERIC_ATTACK_S
var _attack_anim := ""
var _active_frames: Array[int] = []
var _buffered := false
var _heavy := false
var _dodge_ready_at_ms := 0
var _saved_speed := 80.0
var _hurt_knockback := Vector2.ZERO
var _dead_reported := false
var _flash: Tween = null

func _ready() -> void:
	actor = get_parent() as RpgActor
	if actor == null:
		push_error("[RPG-ARPG] PlayerCombat needs an RpgActor parent")
		return
	sprite = actor.get_node_or_null("Visual") as AnimatedSprite2D
	hitbox = actor.get_node_or_null("AttackHitbox") as RpgHitbox
	hurtbox = actor.get_node_or_null("Hurtbox") as RpgHurtbox
	health = actor.get_node_or_null("Health") as RpgHealth
	swing = actor.get_node_or_null("SwingEffect") as RpgSwingEffect
	movement = actor.component("Movement") as RpgMovement
	_driver.sprite = sprite
	machine = RpgStateMachine.new()
	machine.name = "States"
	add_child(machine)
	machine.add(IDLE, Callable(), _update_free)
	machine.add(MOVE, Callable(), _update_free)
	machine.add(ATTACK, _enter_attack, _update_attack, _exit_attack)
	machine.add(HURT, _enter_hurt, _update_hurt, _exit_hurt)
	machine.add(DODGE, _enter_dodge, _update_dodge, _exit_dodge)
	machine.add(DEAD, _enter_dead, _update_dead)
	machine.changed.connect(_on_machine_changed)
	if hitbox != null:
		hitbox.aim(actor.facing)
		hitbox.hit.connect(_on_hit_landed)
		actor.facing_changed.connect(_on_facing_changed)
	if hurtbox != null:
		hurtbox.damaged.connect(_on_damaged)
	if health != null:
		health.died.connect(_on_died)
	if sprite != null:
		sprite.frame_changed.connect(_update_hitbox_active)
	machine.go(IDLE)

func state() -> StringName:
	return machine.state

func is_dead() -> bool:
	return machine.state == DEAD

func _on_machine_changed(from: StringName, to: StringName) -> void:
	state_changed.emit(from, to)

func _on_facing_changed(_f: String) -> void:
	# The area follows the facing, but never moves during a swing.
	if hitbox != null and not hitbox.active and machine.state != ATTACK:
		hitbox.aim(actor.facing)

## A heavy attack that lands gets a hit-stop and a camera shake (Settings > Screen shake).
func _on_hit_landed(_target: RpgHurtbox) -> void:
	if _heavy and machine.state == ATTACK:
		RpgScreenFeedback.heavy_hit(actor.get_node_or_null("Camera") as Camera2D)

func _pressed(action: String) -> bool:
	return InputMap.has_action(action) and Input.is_action_just_pressed(action)

# ---------------------------------------------------------------- IDLE / MOVE

func _update_free(_delta: float) -> void:
	if not actor.input_enabled:
		return
	var moving := actor.velocity.length() > 1.0
	if moving and machine.state == IDLE:
		machine.go(MOVE)
		return
	if not moving and machine.state == MOVE:
		machine.go(IDLE)
		return
	if _pressed("attack"):
		_heavy = false
		machine.go(ATTACK)
	elif _pressed("secondary_attack"):
		_heavy = true
		machine.go(ATTACK)
	elif _pressed("dodge") and Time.get_ticks_msec() >= _dodge_ready_at_ms:
		machine.go(DODGE)

# ---------------------------------------------------------------- ATTACK

func _enter_attack() -> void:
	_attack_time = 0.0
	_buffered = false
	actor.move_locked = true
	actor.facing_locked = true
	if movement != null:
		movement.desired = Vector2.ZERO
	if hitbox != null:
		hitbox.aim(actor.facing)
		hitbox.heavy = _heavy
	_attack_anim = ""
	_active_frames = []
	var slow := RpgArpgMath.HEAVY_DURATION_MULT if _heavy else 1.0
	if sprite != null and _driver.has_animation("attack", actor.facing):
		_attack_anim = _driver.play_exact("attack", actor.facing)
		_attack_seconds = RpgArpgMath.animation_seconds(sprite.sprite_frames, _attack_anim)
		_active_frames = RpgArpgMath.active_frames_of(sprite.sprite_frames, _attack_anim)
		if _heavy:
			sprite.speed_scale = RpgArpgMath.HEAVY_ANIM_SPEED
			_attack_seconds /= RpgArpgMath.HEAVY_ANIM_SPEED
		actor.animation_locked = true
	else:
		_attack_seconds = GENERIC_ATTACK_S * slow
		if swing != null and hitbox != null:
			swing.play_at(hitbox.position, RpgArpgMath.facing_vector(actor.facing), GENERIC_ACTIVE_TO * slow)
	if _attack_seconds <= 0.0:
		_attack_seconds = GENERIC_ATTACK_S * slow
	attack_started.emit()
	RpgUtil.emit(&"attack_started", [actor])
	_update_hitbox_active()

func _update_attack(delta: float) -> void:
	_attack_time += delta
	_update_hitbox_active()
	if not _heavy and actor.input_enabled and _pressed("attack") and _attack_time >= _attack_seconds * (1.0 - BUFFER_FRACTION):
		_buffered = true
	if _attack_time >= _attack_seconds:
		if _buffered and actor.input_enabled:
			_heavy = false
			machine.go(ATTACK)  # restarts the state: the queued attack
		else:
			machine.go(IDLE)

func _update_hitbox_active() -> void:
	if hitbox == null or machine.state != ATTACK:
		return
	var on := false
	if _attack_anim != "":
		on = sprite != null and sprite.animation == _attack_anim and _active_frames.has(sprite.frame) and _attack_time < _attack_seconds
	else:
		var slow := RpgArpgMath.HEAVY_DURATION_MULT if _heavy else 1.0
		on = _attack_time >= GENERIC_ACTIVE_FROM * slow and _attack_time < GENERIC_ACTIVE_TO * slow
	hitbox.active = on

func _exit_attack() -> void:
	if hitbox != null:
		hitbox.active = false
		hitbox.heavy = false
	if sprite != null:
		sprite.speed_scale = 1.0
	_heavy = false
	if swing != null:
		swing.stop_effect()
	actor.move_locked = false
	actor.facing_locked = false
	actor.animation_locked = false
	_attack_anim = ""

# ---------------------------------------------------------------- HURT

func _on_damaged(info: RpgDamageInfo) -> void:
	if machine.state == DEAD or (health != null and health.is_dead()):
		return
	_hurt_knockback = info.knockback
	machine.go(HURT)

func _enter_hurt() -> void:
	actor.move_locked = true
	actor.facing_locked = true
	if movement != null:
		movement.desired = Vector2.ZERO
		movement.external_velocity = _hurt_knockback
	if sprite != null:
		if _driver.has_animation("hurt", actor.facing):
			_driver.play_exact("hurt", actor.facing)
			actor.animation_locked = true
		elif sprite.sprite_frames != null and sprite.sprite_frames.has_animation("hurt"):
			sprite.flip_h = false
			sprite.play("hurt")
			actor.animation_locked = true
		else:
			_flash_sprite()

func _update_hurt(_delta: float) -> void:
	if machine.time_in_state >= HURT_S:
		machine.go(IDLE)

func _exit_hurt() -> void:
	actor.move_locked = false
	actor.facing_locked = false
	actor.animation_locked = false

func _flash_sprite() -> void:
	if sprite == null:
		return
	if _flash != null and _flash.is_valid():
		_flash.kill()
	sprite.modulate = Color(1.0, 0.35, 0.35)
	_flash = create_tween()
	_flash.tween_property(sprite, "modulate", Color.WHITE, HURT_S)

# ---------------------------------------------------------------- DODGE

func _enter_dodge() -> void:
	_dodge_ready_at_ms = Time.get_ticks_msec() + int(DODGE_COOLDOWN_S * 1000.0)
	actor.move_locked = true
	actor.facing_locked = true
	if hurtbox != null:
		hurtbox.make_invulnerable(DODGE_S)
	if movement != null:
		_saved_speed = movement.speed
		movement.speed = DODGE_SPEED
		movement.desired = RpgArpgMath.facing_vector(actor.facing)

func _update_dodge(_delta: float) -> void:
	if machine.time_in_state >= DODGE_S:
		machine.go(IDLE)

func _exit_dodge() -> void:
	if movement != null:
		movement.desired = Vector2.ZERO
		movement.speed = _saved_speed
	actor.move_locked = false
	actor.facing_locked = false

## Seconds until the dodge can be used again.
func dodge_cooldown_left() -> float:
	return maxf(0.0, float(_dodge_ready_at_ms - Time.get_ticks_msec()) / 1000.0)

# ---------------------------------------------------------------- DEAD

func _on_died() -> void:
	machine.go(DEAD)

func _enter_dead() -> void:
	_dead_reported = false
	actor.input_enabled = false
	actor.move_locked = true
	actor.facing_locked = true
	actor.animation_locked = false
	if hitbox != null:
		hitbox.active = false
	if swing != null:
		swing.stop_effect()
	if movement != null:
		movement.desired = Vector2.ZERO
	if hurtbox != null:
		hurtbox.set_deferred("monitorable", false)
	if sprite == null:
		return
	if _driver.has_animation("death", actor.facing):
		_driver.play_exact("death", actor.facing)
		actor.animation_locked = true
	elif sprite.sprite_frames != null and sprite.sprite_frames.has_animation("death"):
		sprite.flip_h = false
		sprite.play("death")
		actor.animation_locked = true
	else:
		var fade := create_tween()
		fade.tween_property(sprite, "modulate:a", 0.0, DEAD_DELAY_S * 0.8)

func _update_dead(_delta: float) -> void:
	if _dead_reported or machine.time_in_state < DEAD_DELAY_S:
		return
	_dead_reported = true
	defeated.emit()
	var router := RpgUtil.router()
	var combat: Variant = router.get("combat") if router != null else null
	if combat != null and combat.has_method("apply_defeat"):
		combat.call("apply_defeat")
