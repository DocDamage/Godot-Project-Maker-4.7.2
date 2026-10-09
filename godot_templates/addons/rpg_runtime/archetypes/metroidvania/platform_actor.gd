class_name RpgPlatformActor
extends CharacterBody2D
## A character seen from the side: it runs, jumps and falls. The base of the metroidvania's player
## (RpgPlatformPlayer). Behaviour beyond the movement lives in components under the "Components"
## child, as on the top-down RpgActor, so the shared stats and damage code works on both.
##
## The movement is driven by a few intentions (`move_x`, `move_y`, `jump_held`, press_jump(),
## press_dash()); the player's input component sets them, and so can a test or a cutscene.

signal landed(speed: float)
signal jumped
signal facing_changed(f: int)
signal dashed

const DASH_S := 0.18
const DASH_SPEED_MUL := 3.0
const DASH_COOLDOWN_S := 0.6
const HIGH_JUMP_TILES := 1.25
## After a wall jump the input does not steer for this long, so the jump leaves the wall.
const WALL_JUMP_LOCK_S := 0.15

@export var definition: RpgActorDefinition
@export var run_speed := 110.0  # px/s at 16 px tiles; scaled by tile_size / 16
@export var jump_height_tiles := 3.25  # the peak of a full jump
@export var jump_time_to_peak := 0.38  # s; gravity and jump speed derive from these two
@export var fall_gravity_mul := 1.6  # falls faster than it rises
@export var coyote_s := 0.1
@export var jump_buffer_s := 0.12
@export var max_fall_speed := 360.0
## The tile size of the rooms (set by the recipe): speeds are scaled by tile_size / 16.
@export var tile_size := 16.0

var facing := 1  # -1 left, 1 right; flips the sprite, never the body
var on_ladder := false
var input_enabled := true
## Set while an attack or a hurt reaction plays: the input does not move the actor.
var move_locked := false
var facing_locked := false
## While true the actor does not pick its own animation (an attack or a hurt one is playing).
var animation_locked := false
## Intentions: left/right (-1..1), up/down (-1 up, 1 down) and whether jump is held.
var move_x := 0.0
var move_y := 0.0
var jump_held := false
## Multiplies the run speed for the moment (an enemy's lunge, a slow walk).
var speed_scale := 1.0
## Abilities of an actor that is not the player (and of tests): ids such as "double_jump".
var abilities_override: Array = []
## The tile layers looked at for ladders, hazards and one-way platforms; found in the map when empty.
var tile_layers: Array[TileMapLayer] = []

var _components: Dictionary = {}
var _driver := RpgAnimationDriver.new()
var _coyote := 0.0
var _buffer := 0.0
var _jump_cut := false
var _air_jumps := 0
var _drop_left := 0.0
var _was_on_floor := false
var _dash_left := 0.0
var _dash_cooldown := 0.0
var _dash_used := false
var _dash_dir := 1
var _dash_wanted := false
var _wall_lock := 0.0
var _layers_root: Node = null
var _found_layers: Array[TileMapLayer] = []

func _ready() -> void:
	_cache_components()
	_driver.sprite = get_node_or_null("Visual") as AnimatedSprite2D
	motion_mode = CharacterBody2D.MOTION_MODE_GROUNDED
	up_direction = Vector2.UP
	floor_snap_length = px(3.0)
	_animate()

func _cache_components() -> void:
	_components.clear()
	var holder := get_node_or_null("Components")
	if holder != null:
		for child in holder.get_children():
			_components[String(child.name)] = child

## Component name -> node, cached from the "Components" child.
func components() -> Dictionary:
	if _components.is_empty():
		_cache_components()
	return _components

func component(component_name: String) -> Node:
	return components().get(component_name)

# ---------------------------------------------------------------- numbers

## A length written for 16 px tiles, in this game's pixels.
func px(value: float) -> float:
	return value * tile_size / RpgPlatformMath.BASE_TILE

func jump_height_px() -> float:
	var tiles := jump_height_tiles + (HIGH_JUMP_TILES if has_ability(&"high_jump") else 0.0)
	return tiles * tile_size

func gravity_px() -> float:
	return RpgPlatformMath.gravity(jump_height_tiles * tile_size, jump_time_to_peak)

## The take-off speed: with the gravity of a plain jump, so a high jump is a longer jump.
func jump_speed_px() -> float:
	return sqrt(2.0 * gravity_px() * jump_height_px())

## Whether this actor has an ability. The player reads the saved game (RpgPlatformPlayer).
func has_ability(id: StringName) -> bool:
	return abilities_override.has(String(id)) or abilities_override.has(id)

# ---------------------------------------------------------------- intentions

## Jump was pressed: it happens now, or within `jump_buffer_s` when the actor lands in time.
func press_jump() -> void:
	_buffer = jump_buffer_s
	jump_held = true

func release_jump() -> void:
	jump_held = false

func press_dash() -> void:
	_dash_wanted = true

func set_facing(f: int) -> void:
	var wanted := -1 if f < 0 else 1
	if wanted == facing:
		return
	facing = wanted
	facing_changed.emit(facing)

## What the scene router and a loaded save hand over: a facing number, or its text ("-1", "left").
func apply_facing(value: Variant) -> void:
	var text := str(value)
	if text == "left" or text.begins_with("-"):
		set_facing(-1)
	elif text == "right" or text.is_valid_int() or text.is_valid_float():
		set_facing(1)

func is_dashing() -> bool:
	return _dash_left > 0.0

## Seconds until the dash can be used again.
func dash_cooldown_left() -> float:
	return maxf(0.0, _dash_cooldown)

func controllable() -> bool:
	return input_enabled and not move_locked and not RpgSequenceRunner.running()

# ---------------------------------------------------------------- the step

func _physics_process(delta: float) -> void:
	poll_input()
	step(delta)

## Reads the input into the intentions. The base actor has none.
func poll_input() -> void:
	pass

## One physics step: timers, ladder, dash, run, jump, gravity, move, landing, animation.
func step(delta: float) -> void:
	var floor_now := is_on_floor()
	if floor_now:
		_coyote = coyote_s
		_air_jumps = 0
		_dash_used = false
	else:
		_coyote = maxf(0.0, _coyote - delta)
	_dash_cooldown = maxf(0.0, _dash_cooldown - delta)
	_wall_lock = maxf(0.0, _wall_lock - delta)
	if _drop_left > 0.0:
		_drop_left -= delta
		if _drop_left <= 0.0:
			set_collision_mask_value(RpgSideTiles.ONE_WAY_LAYER, true)
	var can_act := controllable()
	var want_x := clampf(move_x, -1.0, 1.0) if can_act else 0.0
	var want_y := clampf(move_y, -1.0, 1.0) if can_act else 0.0
	if not can_act:
		_buffer = 0.0
		_dash_wanted = false

	if _step_ladder(delta, want_x, want_y, floor_now) or _step_dash(delta, want_x):
		_after_move(floor_now, 0.0)
		return

	if _wall_lock <= 0.0:
		velocity.x = want_x * px(run_speed) * speed_scale
	if want_x != 0.0 and not facing_locked and _wall_lock <= 0.0:
		set_facing(1 if want_x > 0.0 else -1)

	if _buffer > 0.0:
		_try_jump(floor_now, want_y)
	if not jump_held and velocity.y < 0.0 and not _jump_cut:
		velocity.y *= RpgPlatformMath.JUMP_CUT  # released early: a lower jump
		_jump_cut = true

	var pull := gravity_px() * (fall_gravity_mul if velocity.y > 0.0 else 1.0)
	var cap := px(max_fall_speed)
	if _wall_sliding(want_x):
		cap *= RpgPlatformMath.WALL_SLIDE_FACTOR
	# Half of the step's gravity before the move and half after: the jump follows its parabola.
	velocity.y = RpgPlatformMath.fall_step(velocity.y, pull, delta * 0.5, cap)
	var fall_speed := velocity.y
	move_and_slide()
	if not is_on_floor():
		velocity.y = RpgPlatformMath.fall_step(velocity.y, pull, delta * 0.5, cap)
	_buffer = maxf(0.0, _buffer - delta)
	_after_move(floor_now, fall_speed)

func _after_move(floor_before: bool, fall_speed: float) -> void:
	var floor_now := is_on_floor()
	if floor_now and not floor_before:
		landed.emit(fall_speed)
		play_sound(&"sfx_land")
	_was_on_floor = floor_now
	_animate()

## Pushing into a wall while falling, with the wall jump ability: the fall is slowed.
func _wall_sliding(want_x: float) -> bool:
	if not has_ability(&"wall_jump") or not is_on_wall_only() or velocity.y <= 0.0 or want_x == 0.0:
		return false
	return signf(want_x) == -signf(get_wall_normal().x)

func is_wall_sliding() -> bool:
	return _wall_sliding(clampf(move_x, -1.0, 1.0) if controllable() else 0.0)

func _try_jump(floor_now: bool, want_y: float) -> void:
	if floor_now and want_y > 0.5 and standing_on_one_way():
		# down + jump on a one-way platform: fall through it
		_drop_left = RpgPlatformMath.DROP_THROUGH_S
		set_collision_mask_value(RpgSideTiles.ONE_WAY_LAYER, false)
		_buffer = 0.0
		_coyote = 0.0
		return
	if _coyote > 0.0:
		_jump()
	elif has_ability(&"wall_jump") and is_on_wall_only():
		var away := signf(get_wall_normal().x)
		_jump()
		velocity.x = away * px(run_speed)
		_wall_lock = WALL_JUMP_LOCK_S
		if away != 0.0 and not facing_locked:
			set_facing(int(away))
	elif has_ability(&"double_jump") and _air_jumps < 1:
		_air_jumps += 1
		_jump()

func _jump() -> void:
	velocity.y = -jump_speed_px()
	_coyote = 0.0
	_buffer = 0.0
	_jump_cut = false
	on_ladder = false
	jumped.emit()
	play_sound(&"sfx_jump")

## The dash: a short burst along the facing, without gravity. One per airtime, with a cooldown.
func _step_dash(delta: float, _want_x: float) -> bool:
	if _dash_wanted:
		_dash_wanted = false
		if has_ability(&"dash") and _dash_left <= 0.0 and _dash_cooldown <= 0.0 and not _dash_used:
			_dash_left = DASH_S
			_dash_cooldown = DASH_COOLDOWN_S
			_dash_used = not is_on_floor()
			_dash_dir = facing
			on_ladder = false
			var hurtbox := get_node_or_null("Hurtbox") as RpgHurtbox
			if hurtbox != null:
				hurtbox.make_invulnerable(DASH_S)
			dashed.emit()
			play_sound(&"sfx_dash")
	if _dash_left <= 0.0:
		return false
	_dash_left -= delta
	velocity = Vector2(_dash_dir * px(run_speed) * DASH_SPEED_MUL, 0.0)
	move_and_slide()
	if _dash_left <= 0.0 or is_on_wall():
		_dash_left = 0.0
		velocity.x = 0.0
	return true

## Climbing: up or down over a ladder tile enters; jump or leaving the tile exits.
func _step_ladder(_delta: float, want_x: float, want_y: float, floor_now: bool) -> bool:
	var here := ladder_here()
	if on_ladder and (not here or (floor_now and want_y > 0.0)):
		on_ladder = false
	elif not on_ladder and here and absf(want_y) > 0.5 and not (floor_now and want_y > 0.0):
		on_ladder = true
		_air_jumps = 0
		_dash_used = false
	if not on_ladder:
		return false
	if _buffer > 0.0:
		_jump()  # jump off the ladder
		return false
	velocity = Vector2(want_x * px(run_speed) * 0.5, want_y * px(RpgPlatformMath.LADDER_SPEED))
	if want_x != 0.0 and not facing_locked:
		set_facing(1 if want_x > 0.0 else -1)
	move_and_slide()
	_coyote = coyote_s  # stepping off a ladder still allows a jump
	return true

# ---------------------------------------------------------------- tiles

## The tile layers of the map this actor is in (found once per map).
func layers() -> Array[TileMapLayer]:
	if not tile_layers.is_empty():
		return tile_layers
	var root := _map_root()
	if root != _layers_root or (_found_layers.is_empty() and root != null):
		_layers_root = root
		_found_layers = RpgSideTiles.layers_of(root)
	return _found_layers

## Forget the layers found (a room was swapped under the same parent).
func refresh_layers() -> void:
	_layers_root = null
	_found_layers = []

## The map this actor is in: its RpgMapRoot ancestor, else its topmost ancestor.
func _map_root() -> Node:
	var node := get_parent()
	var top := node
	while node != null:
		if node is RpgMapRoot:
			return node
		top = node
		node = node.get_parent()
	return top

## The middle of the body, as a global point.
func body_center() -> Vector2:
	return RpgUtil.world_position(self) + Vector2(0.0, -body_height() * 0.5)

func body_height() -> float:
	var shape := get_node_or_null("Body") as CollisionShape2D
	if shape != null and shape.shape is RectangleShape2D:
		return (shape.shape as RectangleShape2D).size.y
	return tile_size

func body_width() -> float:
	var shape := get_node_or_null("Body") as CollisionShape2D
	if shape != null and shape.shape is RectangleShape2D:
		return (shape.shape as RectangleShape2D).size.x
	return tile_size * 0.5

func ladder_here() -> bool:
	return RpgSideTiles.has_at(layers(), body_center(), RpgSideTiles.LADDER)

## True when the cell under the feet is a one-way platform.
func standing_on_one_way() -> bool:
	var feet := RpgUtil.world_position(self)
	var all := layers()
	for dx: float in [0.0, -body_width() * 0.5 + 1.0, body_width() * 0.5 - 1.0]:
		if RpgSideTiles.one_way_at(all, feet + Vector2(dx, 2.0)):
			return true
	return false

# ---------------------------------------------------------------- animation and sound

## The animation of the moment: climb, dash, jump or fall in the air, run or idle on the floor.
func _animate() -> void:
	if animation_locked or _driver.sprite == null:
		return
	if on_ladder:
		_play_first(["climb", "idle"])
		_driver.sprite.speed_scale = 1.0 if velocity.length() > 1.0 else 0.0
		return
	_driver.sprite.speed_scale = 1.0
	if is_dashing():
		_play_first(["dash", "run", "idle"])
	elif not is_on_floor() and not _was_on_floor:
		_play_first(["jump", "idle"] if velocity.y < 0.0 else ["fall", "jump", "idle"])
	elif absf(velocity.x) > 1.0:
		_play_first(["run", "idle"])
	else:
		_play_first(["idle", "run"])

func _play_first(bases: Array) -> void:
	for base: String in bases:
		if _driver.has_side(base):
			_driver.play_side(base, facing)
			return

## Plays "<base>" for the facing and holds it (a cutscene's `animate`) until release_animation().
func hold_animation(base: String) -> bool:
	if not _driver.has_side(base):
		return false
	_driver.play_side(base, facing, true)
	animation_locked = true
	return true

func release_animation() -> void:
	animation_locked = false
	_animate()

## Plays a sound slot through the game's audio service (silent when the slot is unset).
func play_sound(slot: StringName) -> void:
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	if audio != null and audio.has_method("play"):
		audio.call("play", slot)
