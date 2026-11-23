class_name RpgSoldier
extends RpgPlatformActor
## The player of a run and gun: the platform actor (run, a jump as high as the button is held,
## coyote time, one-way platforms, ladders) with a gun that is aimed eight ways. The stick or
## the arrows set the aim: up, the diagonals, forward, and straight down while in the air. Down
## on the ground is a crouch: the soldier is lower to hit and fires forward. `aim_lock` holds
## the soldier in place so that it can aim without walking.
##
## One hit is a death (`max_health` 1, the genre's rule; up to 5 makes it forgiving). A soldier
## that died comes back from the top of the screen and cannot be hit for a moment. The camera is
## led to the right by the soldier and never goes back; the left edge of the screen is a wall,
## or kills, as `left_edge_kills` says. A fall out of the stage is a death.
##
## The soldier is told what to want (`move_x`, `move_y`, press_jump, `jump_held`, `shooting`,
## `aim_locked`, press_grenade, press_grapple): RpgSoldierInput tells it from the input actions,
## a test tells it directly. Its children: `Visual`, `Body`, `Gun`, `Input` and `Muzzle` (the
## flash), and `Grapple` when the game has the grapple arm.
##
## The grapple (RpgGrapple) is fired along the aim; a hook that holds swings the soldier or
## hoists it, and the button again (or jump) lets go with the speed of the swing. A soldier
## with `can_jump` off does not jump: the arm does the climbing. Down with jump still drops
## through a plank.

signal destroyed
signal respawned
signal was_hit(health_left: int)
signal grenade_thrown(grenade: Node2D)
signal weapon_changed(weapon: String)
signal grapple_fired
signal grapple_hooked(at: Vector2)

const BLINK_S := 0.1
const FLASH_S := 0.06
## How far ahead of the middle of the screen the soldier may run before the camera follows, as a
## part of the screen's width (negative: behind the middle).
const LEAD := -0.1
## A grenade leaves at this speed, in tiles a second, up and forward.
const THROW := Vector2(7.0, -9.0)
## The weapons a soldier can carry and the script of each.
const WEAPONS := {
	"machine_gun": "res://addons/rpg_runtime/archetypes/run_and_gun/weapons/machine_gun.gd",
	"spread": "res://addons/rpg_runtime/archetypes/run_and_gun/weapons/spread.gd",
	"laser": "res://addons/rpg_runtime/archetypes/run_and_gun/weapons/laser.gd",
	"flame": "res://addons/rpg_runtime/archetypes/run_and_gun/weapons/flame.gd",
}
const DEFAULT_WEAPON := "machine_gun"

@export var max_health: int = 1
@export var invulnerable_s: float = 2.0
@export var left_edge_kills: bool = true
## A death costs the weapon (the genre's rule): the soldier comes back with the machine gun.
@export var keep_weapon: bool = false
@export var grenades: int = 3
@export var max_grenades: int = 9
@export var grenade_scene: PackedScene = null
@export var explosion_scene: PackedScene = null
## The size of the screen in px.
@export var view: Vector2 = Vector2(640, 360)
@export var shoot_sound: StringName = &"sfx_shoot"
## Off: the jump button does nothing (the game's option `jump`; it needs the grapple).
@export var can_jump: bool = true
@export var grapple_sound: StringName = &"sfx_grapple"

var health := 1
var dead := false
var shooting := false
var aim_locked := false
var crouching := false
## The way the gun points now, a unit vector.
var aim := Vector2.RIGHT
## The radius of what can be hit, in px (smaller while crouched).
var hit_radius := 8.0
## The pool the soldier fires into when it is not in a stage (a test).
var pool_override: RpgArcadeBulletPool = null
## Reads the input every step; a test or a smoke step turns it off and tells the soldier itself.
var input_node_enabled := true

var _safe_left := 0.0
var _tile_hazards := RpgTileHazards.new()
var _grenade_asked := false
var _flash_left := 0.0
var _start := Vector2.ZERO
var _started := false
var _grapple_asked := false
## After letting go of a swing: its speed is kept until the soldier lands or meets a wall.
var _carried := false

func _ready() -> void:
	super._ready()
	health = max_health
	add_to_group(RpgArcadeBulletPool.SHIP_GROUP)
	_size_hit()

func poll_input() -> void:
	var input := get_node_or_null("Input")
	if input_node_enabled and input != null and input.has_method(&"poll"):
		input.call(&"poll", self)

func gun() -> RpgGun:
	return get_node_or_null("Gun") as RpgGun

## The name of the weapon in hand.
func weapon() -> String:
	var held := gun()
	return held.weapon if held != null else ""

## Takes another weapon (a pickup): the gun in hand is replaced. False for a name that is no
## weapon; true also when it is the one already held.
func equip(weapon_name: String) -> bool:
	if not WEAPONS.has(weapon_name):
		return false
	if weapon() == weapon_name:
		return true
	var script := load(RpgUtil.to_str(WEAPONS[weapon_name])) as GDScript
	if script == null:
		return false
	var old := gun()
	if old != null:
		old.name = "OldGun"
		remove_child(old)
		old.queue_free()
	var made := Node.new()
	made.set_script(script)
	made.name = "Gun"
	made.set(&"tile", tile_size)
	add_child(made)
	weapon_changed.emit(weapon_name)
	return true

func stage() -> RpgArcadeStage:
	var node := get_parent()
	while node != null:
		if node is RpgArcadeStage:
			return node as RpgArcadeStage
		node = node.get_parent()
	return null

func pool() -> RpgArcadeBulletPool:
	if pool_override != null:
		return pool_override
	var found := stage()
	return found.get_node_or_null("Bullets") as RpgArcadeBulletPool if found != null else null

func is_invulnerable() -> bool:
	return _safe_left > 0.0

## The middle of what can be hit, as a global point: the middle of the body, lower in a crouch.
func hit_center() -> Vector2:
	return RpgUtil.world_position(self) + Vector2(0.0, -body_height() * (0.25 if crouching else 0.5))

func _size_hit() -> void:
	hit_radius = maxf(2.0, body_height() * (0.22 if crouching else 0.4))

## Where a bullet leaves the gun, in the coordinates the soldier is placed in.
func muzzle() -> Vector2:
	var center := Vector2(0.0, -body_height() * (0.25 if crouching else 0.55))
	return position + center + aim * (body_width() * 0.5 + 2.0)

func grapple() -> RpgGrapple:
	return get_node_or_null("Grapple") as RpgGrapple

## The soldier's end of the rope, relative to its feet.
func hand() -> Vector2:
	return Vector2(0.0, -body_height() * 0.5)

## The grapple button: fires the hook along the aim, or lets go of what it holds.
func press_grapple() -> void:
	_grapple_asked = true

func is_on_rope() -> bool:
	var rope := grapple()
	return rope != null and rope.is_attached()

## Jump lets go of the rope; a soldier that cannot jump only drops through a plank with it.
func press_jump() -> void:
	if is_on_rope():
		release_grapple()
	elif can_jump or (is_on_floor() and move_y > 0.5 and standing_on_one_way()):
		super.press_jump()

## Lets go of the rope: the soldier flies on with the speed of its swing.
func release_grapple() -> void:
	var rope := grapple()
	if rope == null or rope.is_idle():
		return
	var swinging := rope.state == RpgGrapple.State.SWING
	if swinging:
		velocity = rope.swing_velocity()
	rope.release()
	if swinging:
		_carried = true
		_jump_cut = true  # the rise of a swing is not a jump let go early
		_coyote = 0.0
		_buffer = 0.0

func _use_grapple() -> void:
	var rope := grapple()
	if rope == null:
		return
	if rope.is_attached():
		release_grapple()
	elif rope.is_idle() and rope.fire(RpgUtil.world_position(self) + hand(), RpgGrapple.direction(aim, facing)):
		grapple_fired.emit()
		play_sound(grapple_sound)

## One step on the rope instead of the actor's own: the swing or the hoist.
func _step_on_rope(delta: float) -> void:
	var rope := grapple()
	on_ladder = false
	rope.move(self, delta, gravity_px(), clampf(move_x, -1.0, 1.0) if controllable() else 0.0)
	if rope.state == RpgGrapple.State.SWING and absf(rope.omega) > 0.2 and not facing_locked:
		set_facing(1 if rope.omega > 0.0 else -1)
	_animate()

## A grenade at the next step.
func press_grenade() -> void:
	_grenade_asked = true

func step(delta: float) -> void:
	_tile_hazards.tick(delta)
	if not _started:
		_started = true
		_start = position
	if dead:
		_grenade_asked = false
		_grapple_asked = false
		return
	var rope := grapple()
	if rope != null and rope.fly(delta, self, hand(), layers()):
		grapple_hooked.emit(rope.anchor)
		play_sound(grapple_sound)
	var hanging := rope != null and rope.is_attached()
	var stick := Vector2(move_x, move_y)
	var floor_now := is_on_floor()
	var was_crouching := crouching
	crouching = floor_now and stick.y > RpgGunAim.DEAD_ZONE and absf(stick.x) <= RpgGunAim.DEAD_ZONE and not on_ladder and not hanging
	if crouching != was_crouching:
		_size_hit()
	if absf(stick.x) > RpgGunAim.DEAD_ZONE and not facing_locked:
		set_facing(1 if stick.x > 0.0 else -1)
	aim = RpgGunAim.direction(stick, facing, floor_now and not hanging, crouching)
	if _grapple_asked:
		_grapple_asked = false
		_use_grapple()
		hanging = rope != null and rope.is_attached()
	if hanging:
		_step_on_rope(delta)
	else:
		# a crouched soldier and one that holds its aim stay where they are
		var held := move_x
		if crouching or aim_locked:
			move_x = 0.0
		if _carried:
			_wall_lock = maxf(_wall_lock, delta * 2.0)  # the input does not take the speed away
		super.step(delta)
		move_x = held  # what is held stays held: only this step stood still
		if _carried and (is_on_floor() or is_on_wall()):
			_carried = false
			_wall_lock = 0.0
	_keep_on_screen()
	_step_safety(delta)
	var weapon := gun()
	if weapon != null and weapon.advance(delta, shooting, pool(), muzzle(), aim) > 0:
		_flash_left = FLASH_S
		play_sound(shoot_sound)
	_show_flash(delta)
	if _grenade_asked:
		_grenade_asked = false
		throw_grenade()
	_follow_camera()
	if not dead and touching_hazard():
		var feet := RpgUtil.world_position(self)
		var half := body_width() * 0.5 - 1.0
		var points: Array[Vector2] = [feet + Vector2(0.0, -2.0), feet + Vector2(-half, -2.0), feet + Vector2(half, -2.0), body_center()]
		var spec := RpgTileHazards.at(layers(), points, invulnerable_s * 0.5)
		if not is_invulnerable() and _tile_hazards.consume(spec):
			hit(RpgUtil.to_int(spec["damage"]))
			_safe_left = minf(_safe_left, RpgUtil.to_float(spec["cooldown"], invulnerable_s * 0.5))
	if not dead and _below_stage():
		die()

## The scroller of the stage is led by the soldier: the camera follows to the right only.
func _follow_camera() -> void:
	var found := stage()
	if found == null:
		return
	var scroll := found.scroller()
	scroll.follow(position.x - (scroll.origin.x + view.x * LEAD))

func _screen_left() -> float:
	var found := stage()
	if found == null:
		return -INF
	return found.scroller().view_center().x - view.x * 0.5

## The edges of the screen. The right one is a wall (the camera may be held by a trap, or at
## the end of the stage); the left one kills, or is a wall too.
func _keep_on_screen() -> void:
	var edge := _screen_left()
	if edge == -INF:
		return
	var right := edge + view.x - body_width() * 0.5
	if position.x > right:
		position.x = right
		velocity.x = minf(0.0, velocity.x)
	if position.x >= edge + body_width() * 0.5:
		return
	if left_edge_kills and position.x < edge - body_width():
		die()
	elif not left_edge_kills:
		position.x = edge + body_width() * 0.5
		velocity.x = maxf(0.0, velocity.x)

## True when the feet or the middle of the soldier are in a tile that hurts (spikes).
func touching_hazard() -> bool:
	var all := layers()
	if all.is_empty():
		return false
	var feet := RpgUtil.world_position(self)
	var half := body_width() * 0.5 - 1.0
	for point: Vector2 in [feet + Vector2(0.0, -2.0), feet + Vector2(-half, -2.0), feet + Vector2(half, -2.0), body_center()]:
		if RpgSideTiles.has_at(all, point, RpgSideTiles.HAZARD):
			return true
	return false

func _below_stage() -> bool:
	var found := stage()
	if found == null:
		return false
	return position.y > found.scroller().view_center().y + view.y * 0.5 + body_height() * 2.0

func _step_safety(delta: float) -> void:
	if _safe_left <= 0.0:
		return
	_safe_left = maxf(0.0, _safe_left - delta)
	var visual := get_node_or_null("Visual") as CanvasItem
	if visual != null:
		visual.visible = _safe_left <= 0.0 or int(_safe_left / BLINK_S) % 2 == 0

## The muzzle flash says where the shot goes, whatever the sheet can show.
func _show_flash(delta: float) -> void:
	var flash := get_node_or_null("Muzzle") as Node2D
	if flash == null:
		return
	_flash_left = maxf(0.0, _flash_left - delta)
	flash.visible = _flash_left > 0.0
	flash.position = muzzle() - position
	flash.rotation = aim.angle()

## Throws a grenade up and forward. False without one, or without a scene for it.
func throw_grenade() -> bool:
	if grenades <= 0 or grenade_scene == null or get_parent() == null:
		return false
	var thrown := grenade_scene.instantiate() as Node2D
	if thrown == null:
		return false
	grenades -= 1
	thrown.position = muzzle()
	thrown.set(&"velocity", Vector2(THROW.x * facing, THROW.y) * tile_size + Vector2(velocity.x, 0.0))
	get_parent().add_child(thrown)
	grenade_thrown.emit(thrown)
	return true

## One more grenade (a pickup), up to `max_grenades`. True when it was taken.
func add_grenade() -> bool:
	if grenades >= max_grenades:
		return false
	grenades += 1
	return true

## Something hit the soldier. Nothing happens while it blinks; else it costs one health, and the
## last one is a death. True when the hit counted.
func hit(amount: int = 1) -> bool:
	if dead or is_invulnerable():
		return false
	health -= maxi(1, amount)
	was_hit.emit(health)
	if health <= 0:
		die()
	else:
		_safe_left = invulnerable_s * 0.5
	return true

## The soldier dies (the last hit, a fall, the left edge): an explosion, and `destroyed`.
func die() -> void:
	if dead:
		return
	dead = true
	health = 0
	var rope := grapple()
	if rope != null:
		rope.release()
	_carried = false
	velocity = Vector2.ZERO
	if not keep_weapon:
		equip(DEFAULT_WEAPON)
	var visual := get_node_or_null("Visual") as CanvasItem
	if visual != null:
		visual.visible = false
	if explosion_scene != null and get_parent() != null:
		var burst := explosion_scene.instantiate() as Node2D
		if burst != null:
			burst.position = position + Vector2(0.0, -body_height() * 0.5)
			get_parent().add_child(burst)
	destroyed.emit()

## The next life: dropped in from the top of the screen, a little way in from its left edge,
## blinking and safe for a moment, with full health.
func respawn() -> void:
	dead = false
	health = max_health
	velocity = Vector2.ZERO
	var found := stage()
	if found != null:
		var middle := found.scroller().view_center()
		position = Vector2(middle.x - view.x * 0.25, middle.y - view.y * 0.5 + body_height())
	else:
		position = _start
	_safe_left = invulnerable_s
	var visual := get_node_or_null("Visual") as CanvasItem
	if visual != null:
		visual.visible = true
	respawned.emit()

## The sheet's own animation for the aim, when it has one; else the platform actor's.
func _animate() -> void:
	if animation_locked or _driver.sprite == null:
		return
	var rope := grapple()
	if rope != null and not rope.is_idle():
		for base: String in ["grapple", "aim_up"]:
			if _driver.has_side(base):
				_driver.sprite.speed_scale = 1.0
				_driver.play_side(base, facing)
				return
	if crouching and _driver.has_side("crouch"):
		_driver.sprite.speed_scale = 1.0
		_driver.play_side("crouch", facing)
		return
	if shooting and is_on_floor() and absf(velocity.x) <= 1.0:
		var wanted := aim_animation(RpgGunAim.name_of(aim))
		for base in wanted:
			if _driver.has_side(base):
				_driver.sprite.speed_scale = 1.0
				_driver.play_side(base, facing)
				return
	super._animate()

## The animations to try for an aim, the best first.
static func aim_animation(aim_name: String) -> Array[String]:
	match aim_name:
		"up":
			return ["aim_up", "shoot"]
		"up_forward", "down_forward":
			return ["aim_diagonal", "shoot"]
	return ["shoot"]
