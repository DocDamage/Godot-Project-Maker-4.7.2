class_name RpgShmupShip
extends CharacterBody2D
## The player's ship of a shoot-em-up. It flies in eight directions inside the play area, which
## moves with the camera; `focus` halves its speed for precise dodging. What can be hit is one
## point at its middle, much smaller than its picture. A hit destroys it; it comes back blinking
## and cannot be hit for three seconds.
##
## The ship is moved by what it is told to want (`move`, `shooting`, `focusing`, press_shoot,
## press_bomb): RpgShmupShipInput tells it from the input actions, a test tells it directly.
## Its children: `Visual` (the picture), `Weapon`, `Bomb` and `Input`.

signal destroyed
signal respawned

const BLINK_S := 0.1

## Px a second.
@export var speed: float = 120.0
@export var focus_factor: float = 0.5
## The radius of what can be hit, in px.
@export var hit_radius: float = 1.0
@export var invulnerable_s: float = 3.0
## "vertical" (the ship looks up) or "horizontal" (it looks right).
@export var orientation: String = "vertical"
## Where the ship may be, relative to the middle of the screen.
@export var play_area: Rect2 = Rect2(-160, -90, 320, 180)
## Half the size of its picture: that much of the play area is kept free at every edge.
@export var half_size: Vector2 = Vector2(8, 8)
@export var explosion_scene: PackedScene = null

## What the ship wants: a direction (each part -1..1), to fire, to fly slowly.
var move := Vector2.ZERO
var shooting := false
var focusing := false
var dead := false
## False for a test that steps the ship by hand.
var auto_advance := true
## The middle of the screen when the ship is not in a stage (a test).
var area_center := Vector2.ZERO
## The pool the ship fires into when it is not in a stage (a test).
var pool_override: RpgShmupBulletPool = null

var _offset := Vector2.ZERO
var _start_offset := Vector2.ZERO
var _placed := false
var _safe_left := 0.0
var _shot_asked := false
var _bomb_asked := false

func _ready() -> void:
	add_to_group(RpgShmupBulletPool.SHIP_GROUP)

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta)

## The way the ship looks: up, or right.
func forward() -> Vector2:
	return RpgShmupMath.forward_of(orientation)

func weapon() -> RpgShmupWeapon:
	return get_node_or_null("Weapon") as RpgShmupWeapon

func bomb() -> RpgShmupBomb:
	return get_node_or_null("Bomb") as RpgShmupBomb

func _stage() -> RpgArcadeStage:
	var node := get_parent()
	while node != null:
		if node is RpgArcadeStage:
			return node as RpgArcadeStage
		node = node.get_parent()
	return null

## The middle of the screen, in the coordinates the ship is placed in.
func center() -> Vector2:
	var stage := _stage()
	return stage.scroller().view_center() if stage != null else area_center

func pool() -> RpgShmupBulletPool:
	if pool_override != null:
		return pool_override
	var stage := _stage()
	return stage.get_node_or_null("Bullets") as RpgShmupBulletPool if stage != null else null

func is_invulnerable() -> bool:
	return _safe_left > 0.0

## Where the ship is, relative to the middle of the screen.
func offset() -> Vector2:
	return _offset

## One shot at the next step (the input without auto-fire).
func press_shoot() -> void:
	_shot_asked = true

## A bomb at the next step.
func press_bomb() -> void:
	_bomb_asked = true

## One step: the ship flies, stays inside the play area, fires and drops its bomb.
func advance(delta: float) -> void:
	var input := get_node_or_null("Input")
	if input != null and input.has_method(&"poll"):
		input.call(&"poll", self)
	var middle := center()
	if not _placed:
		_placed = true
		_offset = position - middle
		_start_offset = _offset
	if dead:
		_shot_asked = false
		_bomb_asked = false
		return
	var pace := speed * (focus_factor if focusing else 1.0)
	_offset += move.limit_length(1.0) * pace * delta
	var room := play_area.grow_individual(-half_size.x, -half_size.y, -half_size.x, -half_size.y)
	_offset = _offset.clamp(room.position, room.end)
	position = middle + _offset
	_step_safety(delta)
	_show_bank()
	var gun := weapon()
	var bullets := pool()
	if gun != null:
		gun.advance(delta, shooting or _shot_asked, bullets, position + forward() * half_size.y, forward())
	_shot_asked = false
	if _bomb_asked:
		_bomb_asked = false
		var blast := bomb()
		if blast != null:
			blast.use(bullets, Rect2(middle + play_area.position, play_area.size))

func _step_safety(delta: float) -> void:
	var visual := get_node_or_null("Visual") as CanvasItem
	if _safe_left <= 0.0:
		return
	_safe_left = maxf(0.0, _safe_left - delta)
	if visual != null:
		visual.visible = _safe_left <= 0.0 or int(_safe_left / BLINK_S) % 2 == 0

## The picture leans with the flight when its sheet has frames for it: the ship's left and right
## are the sheet's left and right (the up and down of a ship that looks right).
func _show_bank() -> void:
	var visual := get_node_or_null("Visual") as AnimatedSprite2D
	if visual == null or visual.sprite_frames == null:
		return
	var lean := move.x if orientation != "horizontal" else move.y
	var wanted := bank_animation(visual.sprite_frames, lean, orientation)
	if wanted != &"" and visual.animation != wanted:
		visual.play(wanted)

## The animation of `frames` for a lean of -1 (left, or up), 0 or 1: the first that exists.
static func bank_animation(frames: SpriteFrames, lean: float, ship_orientation: String) -> StringName:
	var sides: Array[String] = ["left", "right"]
	if ship_orientation == "horizontal":
		sides = ["up", "down"]
	var names: Array[String] = []
	if absf(lean) > 0.1:
		var side := sides[0] if lean < 0.0 else sides[1]
		names.append_array(["bank_" + side, "walk_" + side, "idle_" + side])
	names.append_array(["idle", "idle_up", "idle_right", "idle_down", "default"])
	for candidate in names:
		if frames.has_animation(candidate):
			return StringName(candidate)
	return &""

## Something hit the ship. Nothing happens while it blinks; else it is destroyed (an explosion,
## the weapon back at its first level, `destroyed`). True when it was destroyed.
func hit() -> bool:
	if dead or is_invulnerable():
		return false
	dead = true
	var visual := get_node_or_null("Visual") as CanvasItem
	if visual != null:
		visual.visible = false
	if explosion_scene != null and get_parent() != null:
		var burst := explosion_scene.instantiate() as Node2D
		if burst != null:
			burst.position = position
			get_parent().add_child(burst)
	var gun := weapon()
	if gun != null:
		gun.reset()
	destroyed.emit()
	return true

## The next life: where the stage began, blinking, with the starting bombs.
func respawn() -> void:
	dead = false
	_offset = _start_offset
	position = center() + _offset
	_safe_left = invulnerable_s
	var blast := bomb()
	if blast != null:
		blast.refill()
	var visual := get_node_or_null("Visual") as CanvasItem
	if visual != null:
		visual.visible = true
	respawned.emit()
