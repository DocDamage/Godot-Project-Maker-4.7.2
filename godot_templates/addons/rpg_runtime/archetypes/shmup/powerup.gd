class_name RpgShmupPowerup
extends Node2D
## A capsule the ship picks up by touching it. It drifts toward the ship's side of the screen
## and is gone when it leaves it. What it gives is its `kind`:
##
##   weapon_up (a level, up to the third; points when the weapon is there already),
##   weapon:<kind> (another weapon: straight, spread, laser, homing), bomb, life,
##   shield (takes one hit) and points.

signal picked(kind: String)

const KINDS: Array[String] = ["weapon_up", "weapon:spread", "weapon:laser", "weapon:homing", "weapon:straight", "bomb", "life", "shield", "points"]
const POINTS := 500
const MARGIN := 24.0
## A tint for a capsule without a picture of its own kind.
const TINTS := {"weapon_up": Color(1.0, 0.5, 0.3), "bomb": Color(1.0, 0.85, 0.2), "life": Color(0.4, 1.0, 0.5),
	"shield": Color(0.5, 0.8, 1.0), "points": Color(1.0, 1.0, 1.0)}

@export var kind: String = "weapon_up"
@export var speed: float = 30.0
## How near the middle of the ship has to come, in px.
@export var pick_radius: float = 14.0
@export var orientation: String = "vertical"
@export var view: Vector2 = Vector2(320, 180)
## The picture of a kind (kind -> Texture2D); a kind without one keeps the scene's and is tinted.
@export var textures: Dictionary = {}
@export var sound: StringName = &"sfx_powerup"

## False for a test that steps it by hand.
var auto_advance := true
var area_center := Vector2.ZERO
var _taken := false

func _ready() -> void:
	var visual := get_node_or_null("Visual") as Sprite2D
	if visual == null:
		return
	var own: Texture2D = textures.get(kind)
	if own != null:
		visual.texture = own
	else:
		visual.modulate = tint_of(kind)

static func tint_of(powerup_kind: String) -> Color:
	var plain := powerup_kind.get_slice(":", 0)
	var found: Color = TINTS.get(powerup_kind, TINTS.get(plain, Color(0.9, 0.5, 1.0)))
	return found

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta)

func _center() -> Vector2:
	var node := get_parent()
	while node != null:
		if node is RpgArcadeStage:
			return (node as RpgArcadeStage).scroller().view_center()
		node = node.get_parent()
	return area_center

func _ship() -> Node2D:
	if not is_inside_tree():
		return null
	for node in get_tree().get_nodes_in_group(RpgArcadeBulletPool.SHIP_GROUP):
		if node is Node2D and node.has_method(&"hit") and not RpgUtil.to_bool(node.get(&"dead")):
			return node as Node2D
	return null

## One step: it drifts toward the ship's side, is picked up by a touch, and leaves the screen.
func advance(delta: float) -> void:
	if _taken:
		return
	position += -RpgShmupMath.forward_of(orientation) * speed * delta
	var ship := _ship()
	if ship != null and ship.position.distance_to(position) <= pick_radius:
		give(ship)
		return
	if not Rect2(-view * 0.5, view).grow(MARGIN).has_point(position - _center()):
		queue_free()

## Gives `ship` what the capsule holds and takes the capsule away.
func give(ship: Node2D) -> void:
	if _taken:
		return
	_taken = true
	apply(kind, ship, RpgArcadeMode.current())
	var router := RpgUtil.router()
	if router != null and router.audio != null:
		router.audio.call(&"play", sound)
	picked.emit(kind)
	queue_free()

## What a capsule of `powerup_kind` does for `ship` in the run of `mode` (either may be null).
static func apply(powerup_kind: String, ship: Node2D, mode: RpgArcadeMode) -> void:
	var weapon := ship.get_node_or_null("Weapon") as RpgShmupWeapon if ship != null else null
	var bomb := ship.get_node_or_null("Bomb") as RpgShmupBomb if ship != null else null
	if powerup_kind.begins_with("weapon:"):
		if weapon != null:
			weapon.set_kind(powerup_kind.trim_prefix("weapon:"))
		return
	match powerup_kind:
		"weapon_up":
			if weapon == null or not weapon.level_up():
				_points(mode)  # the weapon is at its third level: points
		"bomb":
			if bomb == null or not bomb.add():
				_points(mode)
		"life":
			if mode == null or not mode.lives.gain():
				_points(mode)
		"shield":
			if ship != null and ship.has_method(&"set_shield"):
				ship.call(&"set_shield", true)
		_:
			_points(mode)

static func _points(mode: RpgArcadeMode) -> void:
	if mode != null:
		mode.pickup(POINTS)
