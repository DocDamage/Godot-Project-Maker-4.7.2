class_name RpgPlatformPlayer
extends RpgPlatformActor
## The metroidvania's player: the platform actor plus what only the player does. It attacks with
## the shared hitbox, is hurt through the shared hurtbox, loses a hit point on a hazard and is put
## back on the last safe ground, talks to what is beside it, and at 0 HP hands over to the
## archetype's defeat policy. Its abilities are those of the saved game (GameState.abilities).

signal attack_started
signal was_hurt(amount: int)
signal returned_to_safe_ground
signal defeated  # the defeat policy is about to run

const GENERIC_ATTACK_S := 0.3
const GENERIC_ACTIVE_FROM := 0.06
const GENERIC_ACTIVE_TO := 0.2
const HURT_S := 0.25
const HURT_KNOCKBACK := 90.0
const HURT_HOP := 70.0
const DEAD_DELAY_S := 1.0

var health: RpgHealth
var hurtbox: RpgHurtbox
var hitbox: RpgHitbox
## Where a hazard sends the player back to: the last place stood on for SAFE_GROUND_S.
var safe_position := Vector2.ZERO
var has_safe_position := false

var _input: RpgPlatformInput
var _interaction: Area2D
var _prompt: Label = null
var _safe_cell := Vector2i(-99999, -99999)
var _safe_time := 0.0
var _return_left := -1.0
var _tile_hazards := RpgTileHazards.new()
var _attacking := false
var _attack_time := 0.0
var _attack_seconds := GENERIC_ATTACK_S
var _attack_anim := ""
var _active_frames: Array[int] = []
var _hurt_left := 0.0
var _dead := false
var _dead_time := 0.0
var _dead_reported := false
var _flash: Tween = null

func _ready() -> void:
	super._ready()
	health = get_node_or_null("Health") as RpgHealth
	hurtbox = get_node_or_null("Hurtbox") as RpgHurtbox
	hitbox = get_node_or_null("AttackHitbox") as RpgHitbox
	_interaction = get_node_or_null("Interaction") as Area2D
	_input = component("PlatformInput") as RpgPlatformInput
	if hurtbox != null:
		hurtbox.damaged.connect(_on_damaged)
	if health != null:
		health.died.connect(_on_died)
	if hitbox != null:
		_aim_hitbox()
		facing_changed.connect(_on_facing_changed)

func poll_input() -> void:
	if _input != null:
		_input.poll(self)

## The abilities of the saved game; without one (a test), those set on the actor.
func has_ability(id: StringName) -> bool:
	var state := RpgUtil.state()
	if state != null:
		var granted: Variant = state.get("abilities")
		if granted is Array:
			var list: Array = granted
			if list.has(String(id)):
				return true
	return super.has_ability(id)

func is_dead() -> bool:
	return _dead

func is_attacking() -> bool:
	return _attacking

func step(delta: float) -> void:
	if _dead:
		move_x = 0.0
		super.step(delta)
		_step_dead(delta)
		return
	super.step(delta)
	_step_attack(delta)
	_step_hurt(delta)
	_step_hazards(delta)
	_step_safe_ground(delta)
	_update_prompt()

# ---------------------------------------------------------------- attack

func _on_facing_changed(_f: int) -> void:
	if not _attacking:
		_aim_hitbox()

## The attack area sits on the facing side of the body.
func _aim_hitbox() -> void:
	if hitbox != null:
		hitbox.position = hitbox.center + Vector2(facing * hitbox.reach.x, 0.0)

## Attack was pressed: one swing on the facing side. Nothing while hurt, dead or already swinging.
func press_attack() -> bool:
	if _dead or _attacking or _hurt_left > 0.0 or _return_left >= 0.0 or not controllable():
		return false
	_attacking = true
	_attack_time = 0.0
	_attack_anim = ""
	_active_frames = []
	_attack_seconds = GENERIC_ATTACK_S
	_aim_hitbox()
	var sprite := _driver.sprite
	if sprite != null and _driver.has_side("attack"):
		_attack_anim = _driver.play_side("attack", facing, true)
		sprite.speed_scale = 1.0
		_attack_seconds = RpgRealtimeMath.animation_seconds(sprite.sprite_frames, _attack_anim)
		_active_frames = RpgRealtimeMath.active_frames_of(sprite.sprite_frames, _attack_anim)
		animation_locked = true
	if _attack_seconds <= 0.0:
		_attack_seconds = GENERIC_ATTACK_S
	facing_locked = true
	attack_started.emit()
	RpgUtil.emit(&"attack_started", [self])
	_update_hitbox()
	return true

func _step_attack(delta: float) -> void:
	if not _attacking:
		return
	_attack_time += delta
	_update_hitbox()
	if hitbox != null and hitbox.active:
		break_blocks()
	if _attack_time >= _attack_seconds:
		_end_attack()

func _update_hitbox() -> void:
	if hitbox == null:
		return
	var on := false
	var sprite := _driver.sprite
	if _attack_anim != "" and sprite != null:
		on = sprite.animation == _attack_anim and _active_frames.has(sprite.frame) and _attack_time < _attack_seconds
	else:
		on = _attack_time >= GENERIC_ACTIVE_FROM and _attack_time < GENERIC_ACTIVE_TO
	hitbox.active = on

func _end_attack() -> void:
	_attacking = false
	facing_locked = false
	if hitbox != null:
		hitbox.active = false
	if _hurt_left <= 0.0:
		animation_locked = false
	_aim_hitbox()

## The global rectangle the attack covers.
func attack_rect() -> Rect2:
	var size := Vector2(tile_size, tile_size) * 0.9
	if hitbox != null:
		var shape := hitbox.get_node_or_null("Shape") as CollisionShape2D
		if shape != null and shape.shape is RectangleShape2D:
			size = (shape.shape as RectangleShape2D).size
		return Rect2(RpgUtil.world_position(hitbox) - size * 0.5, size)
	return Rect2(body_center() + Vector2(facing * tile_size * 0.75, 0.0) - size * 0.5, size)

## With the `break_blocks` ability the swing breaks the breakable tiles it covers; the cells are
## remembered in the saved game. Returns how many broke.
func break_blocks() -> int:
	if not has_ability(&"break_blocks"):
		return 0
	var broken := 0
	for pair: Array in RpgSideTiles.cells_in(layers(), attack_rect(), RpgSideTiles.BREAKABLE):
		var layer: TileMapLayer = pair[0]
		var cell: Vector2i = pair[1]
		layer.erase_cell(cell)
		broken += 1
		var state := RpgUtil.state()
		if state != null and state.has_method(&"remember_broken_cell"):
			state.call(&"remember_broken_cell", room_id(), cell)
	if broken > 0:
		play_sound(&"sfx_hit")
	return broken

## The id of the room the player is in ("" outside a map).
func room_id() -> String:
	var root := _map_root()
	if root is RpgMapRoot:
		return String((root as RpgMapRoot).map_id)
	return ""

# ---------------------------------------------------------------- hurt

func _on_damaged(info: RpgDamageInfo) -> void:
	was_hurt.emit(info.amount if info != null else 0)
	if _dead or (health != null and health.is_dead()):
		return
	var push := signf(info.knockback.x) if info != null and info.knockback.x != 0.0 else -float(facing)
	_start_hurt(push)

func _start_hurt(push: float) -> void:
	_hurt_left = HURT_S
	if _attacking:
		_end_attack()
	move_locked = true
	on_ladder = false
	velocity = Vector2(push * px(HURT_KNOCKBACK), -px(HURT_HOP))
	_wall_lock = HURT_S  # the knockback is not steered away
	if _driver.has_side("hurt"):
		_driver.play_side("hurt", facing, true)
		animation_locked = true
	var sprite := _driver.sprite
	if sprite != null and is_inside_tree():
		if _flash != null and _flash.is_valid():
			_flash.kill()
		_flash = create_tween()
		_flash.tween_property(sprite, "modulate", Color(1.0, 0.45, 0.45), 0.05)
		_flash.tween_property(sprite, "modulate", Color.WHITE, 0.2)

func _step_hurt(delta: float) -> void:
	if _hurt_left <= 0.0:
		return
	_hurt_left -= delta
	if _hurt_left <= 0.0 and _return_left < 0.0:
		move_locked = false
		animation_locked = false

# ---------------------------------------------------------------- hazards and safe ground

## The points of the body looked at for hazards: the feet and the middle, a little inside.
func _probe_points() -> Array[Vector2]:
	var feet := RpgUtil.world_position(self)
	var half := maxf(1.0, body_width() * 0.5 - 1.0)
	var mid := -body_height() * 0.5
	return [
		feet + Vector2(0.0, -2.0), feet + Vector2(-half, -2.0), feet + Vector2(half, -2.0),
		feet + Vector2(0.0, mid), feet + Vector2(-half, mid), feet + Vector2(half, mid),
	]

func touching_hazard() -> bool:
	var all := layers()
	for point in _probe_points():
		if RpgSideTiles.has_at(all, point, RpgSideTiles.HAZARD):
			return true
	return false

func _invulnerable() -> bool:
	return hurtbox != null and hurtbox.is_invulnerable()

## Touching a hazard costs a hit point, gives a moment of invulnerability and, after a short fade,
## puts the player back on the last safe ground.
func _step_hazards(delta: float) -> void:
	_tile_hazards.tick(delta)
	if _return_left >= 0.0:
		_return_left -= delta
		if _return_left < 0.0:
			_return_to_safe_ground()
		return
	if _dead or _invulnerable() or not touching_hazard():
		return
	var spec := RpgTileHazards.at(layers(), _probe_points(), RpgPlatformMath.HAZARD_INVULN_S)
	if not _tile_hazards.consume(spec):
		return
	var info := RpgDamageInfo.new()
	info.amount = RpgUtil.to_int(spec["damage"])
	if health != null:
		health.take(info)
	else:
		var stats := component("Stats") as RpgStatsComponent
		if stats != null:
			stats.take_damage(info.amount)
	if hurtbox != null:
		hurtbox.make_invulnerable(RpgUtil.to_float(spec["cooldown"], RpgPlatformMath.HAZARD_INVULN_S))
	was_hurt.emit(info.amount)
	if _dead or (health != null and health.is_dead()):
		return
	_start_hurt(-float(facing))
	_return_left = RpgPlatformMath.HAZARD_RETURN_S
	_fade(1.0, RpgPlatformMath.HAZARD_RETURN_S)

func _return_to_safe_ground() -> void:
	_return_left = -1.0
	if has_safe_position:
		global_position = safe_position
	velocity = Vector2.ZERO
	_wall_lock = 0.0
	_hurt_left = 0.0
	move_locked = false
	animation_locked = false
	_fade(0.0, 0.2)
	returned_to_safe_ground.emit()

func _fade(alpha: float, seconds: float) -> void:
	var router := RpgUtil.router()
	if router == null or not is_inside_tree():
		return
	var tween := create_tween()
	tween.tween_method(router.set_fade_alpha, router.fade_alpha(), alpha, seconds)

## A cell is safe after standing on it for SAFE_GROUND_S with no hazard beside the feet.
func _step_safe_ground(delta: float) -> void:
	if not is_on_floor() or _return_left >= 0.0 or _hurt_left > 0.0 or _dead:
		_safe_time = 0.0
		return
	var at := RpgUtil.world_position(self)
	var cell := RpgPlatformMath.cell_of(at, tile_size)
	if cell != _safe_cell:
		_safe_cell = cell
		_safe_time = 0.0
		return
	_safe_time += delta
	if _safe_time < RpgPlatformMath.SAFE_GROUND_S:
		return
	var all := layers()
	for dx: float in [-tile_size, 0.0, tile_size]:
		if RpgSideTiles.has_at(all, at + Vector2(dx, -2.0), RpgSideTiles.HAZARD):
			return
	safe_position = at
	has_safe_position = true

# ---------------------------------------------------------------- death

func _on_died() -> void:
	if _dead:
		return
	_dead = true
	_dead_time = 0.0
	_dead_reported = false
	input_enabled = false
	_return_left = -1.0
	_hurt_left = 0.0
	if _attacking:
		_end_attack()
	if hurtbox != null:
		hurtbox.set_deferred("monitorable", false)
	var sprite := _driver.sprite
	if sprite == null:
		return
	if _driver.has_side("death"):
		_driver.play_side("death", facing, true)
		animation_locked = true
	elif is_inside_tree():
		var fade := create_tween()
		fade.tween_property(sprite, "modulate:a", 0.0, DEAD_DELAY_S * 0.8)

func _step_dead(delta: float) -> void:
	_dead_time += delta
	if _dead_reported or _dead_time < DEAD_DELAY_S:
		return
	_dead_reported = true
	defeated.emit()
	var router := RpgUtil.router()
	var combat: RpgCombatMode = router.combat if router != null else null
	if combat != null and combat.has_method("apply_defeat"):
		combat.call("apply_defeat")

# ---------------------------------------------------------------- interaction

func _can_use(node: Node) -> bool:
	return node != self and node.has_method("interact")

## The nearest thing with `interact(actor)` beside the player (within a tile, on either side).
func find_target() -> Node:
	if _interaction == null:
		return null
	var best: Node = null
	var best_dist := INF
	var candidates: Array[Node] = []
	candidates.append_array(_interaction.get_overlapping_bodies())
	candidates.append_array(_interaction.get_overlapping_areas())
	var feet := global_position
	for c in candidates:
		if not _can_use(c) or not (c is Node2D):
			continue
		if c.has_method("can_interact") and not RpgUtil.to_bool(c.call("can_interact", self)):
			continue
		var d := feet.distance_to((c as Node2D).global_position)
		if d < best_dist:
			best_dist = d
			best = c
	return best

## Calls `interact(self)` on the target and turns to it. False when nothing is in reach.
func try_interact() -> bool:
	if _dead or not controllable():
		return false
	var target := find_target()
	if target == null:
		return false
	var dx := (target as Node2D).global_position.x - global_position.x
	if absf(dx) > 1.0:
		set_facing(1 if dx > 0.0 else -1)
	RpgUtil.emit(&"interaction_started", [target])
	target.call("interact", self)
	RpgUtil.emit(&"interaction_finished", [target])
	return true

## The key hint above what the player can interact with (the glyph of `interact`).
func _update_prompt() -> void:
	if _interaction == null or not is_inside_tree():
		return
	var target: Node = find_target() if controllable() and not _dead else null
	if target == null:
		if _prompt != null:
			_prompt.visible = false
		return
	if _prompt == null:
		_prompt = Label.new()
		_prompt.name = "Prompt"
		_prompt.top_level = true
		_prompt.z_index = 50
		_prompt.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(_prompt)
	_prompt.text = RpgInputGlyphs.glyph("interact")
	_prompt.size = _prompt.get_minimum_size()
	_prompt.visible = true
	_prompt.global_position = (target as Node2D).global_position + Vector2(-_prompt.size.x / 2.0, -tile_size * 1.8 - _prompt.size.y)
