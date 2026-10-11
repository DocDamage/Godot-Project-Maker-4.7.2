class_name RpgWeaponPickup
extends Node2D
## A weapon for the soldier. It comes in on a carrier: a capsule that flies across the screen
## from the right, weaving. Shot, the carrier is gone and the weapon falls to the ground, where
## a touch of the soldier takes it. A carrier that is not shot flies off with it.

signal defeated
signal picked(weapon: String)

enum State { FLYING, FALLING, LYING }

const KINDS: Array[String] = ["machine_gun", "spread", "laser", "flame"]
const MARGIN := 48.0
const TINTS := {"machine_gun": Color(1.0, 0.85, 0.3), "spread": Color(1.0, 0.45, 0.3),
	"laser": Color(0.45, 0.8, 1.0), "flame": Color(1.0, 0.6, 0.15)}

@export var weapon: String = "spread"
## Px a second across the screen.
@export var speed: float = 60.0
@export var sway: float = 16.0
@export var gravity: float = 500.0
@export var pick_radius: float = 14.0
@export var hit_radius: float = 8.0
@export var points: int = 0
@export var view: Vector2 = Vector2(640, 360)
## The picture of a weapon (kind -> Texture2D); a kind without one is tinted.
@export var textures: Dictionary = {}
@export_flags_2d_physics var wall_mask: int = 1
@export var sound: StringName = &"sfx_weapon_pickup"

var state: int = State.FLYING
## False for a test that steps it by hand.
var auto_advance := true
var age := 0.0
var _home_y := 0.0
var _fall := 0.0
var _placed := false

func _ready() -> void:
	add_to_group(RpgArcadeBulletPool.TARGET_GROUP)
	var visual := get_node_or_null("Visual") as Sprite2D
	if visual == null:
		return
	var own: Texture2D = textures.get(weapon)
	if own != null:
		visual.texture = own
	else:
		var tint: Color = TINTS.get(weapon, Color.WHITE)
		visual.modulate = tint

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta)

## Called by the spawner: which weapon the wave says it is.
func spawned_in_wave(wave: RpgArcadeWave, _index: int) -> void:
	var wanted := RpgUtil.to_str(wave.data.get("weapon", weapon))
	if KINDS.has(wanted):
		weapon = wanted
		_ready()

## Dropped as it is (a test, a smoke step): it falls from where it is.
func drop() -> void:
	if state != State.FLYING:
		return
	state = State.FALLING
	remove_from_group(RpgArcadeBulletPool.TARGET_GROUP)

## A bullet hits the carrier: the weapon falls.
func take_hit(_damage: int) -> void:
	drop()

func _screen_center() -> Vector2:
	var node := get_parent()
	while node != null:
		if node is RpgArcadeStage:
			return (node as RpgArcadeStage).scroller().view_center()
		node = node.get_parent()
	return Vector2(position.x, view.y * 0.5)

func _soldier() -> Node2D:
	if not is_inside_tree():
		return null
	for node in get_tree().get_nodes_in_group(RpgArcadeBulletPool.SHIP_GROUP):
		if node is Node2D and node.has_method(&"equip") and not RpgUtil.to_bool(node.get(&"dead")):
			return node as Node2D
	return null

func _on_ground() -> bool:
	if wall_mask == 0 or not is_inside_tree():
		return false
	var world := get_world_2d()
	if world == null:
		return false
	var query := PhysicsPointQueryParameters2D.new()
	query.position = global_position + Vector2(0.0, hit_radius)
	query.collision_mask = wall_mask
	query.collide_with_areas = false
	return not world.direct_space_state.intersect_point(query, 1).is_empty()

## One step: the carrier flies, the weapon falls, the soldier takes it.
func advance(delta: float) -> void:
	if not _placed:
		_placed = true
		_home_y = position.y
	age += delta
	var center := _screen_center()
	match state:
		State.FLYING:
			position.x -= speed * delta
			position.y = _home_y + sin(age * 3.0) * sway
			if position.x < center.x - view.x * 0.5 - MARGIN:
				queue_free()  # it flew off with the weapon
		State.FALLING:
			_fall += gravity * delta
			position.y += _fall * delta
			if _on_ground():
				position.y -= _fall * delta  # back out of the ground it fell into
				state = State.LYING
			elif position.y > center.y + view.y * 0.5 + MARGIN:
				queue_free()
		State.LYING:
			if position.x < center.x - view.x * 0.5 - MARGIN:
				queue_free()
	if state != State.FLYING:
		var soldier := _soldier()
		if soldier != null and _reach(soldier) <= pick_radius:
			give(soldier)

func _reach(soldier: Node2D) -> float:
	var at := soldier.global_position
	if soldier.has_method(&"hit_center"):
		var middle: Variant = soldier.call(&"hit_center")
		if middle is Vector2:
			at = middle
	return at.distance_to(global_position)

## Gives the soldier the weapon and takes the pickup away.
func give(soldier: Node2D) -> void:
	soldier.call(&"equip", weapon)
	var router := RpgUtil.router()
	if router != null and router.audio != null:
		router.audio.call(&"play", sound)
	picked.emit(weapon)
	defeated.emit()
	queue_free()
