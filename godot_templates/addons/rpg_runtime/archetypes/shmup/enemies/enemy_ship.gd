class_name RpgShmupEnemy
extends Node2D
## What every enemy of a shoot-em-up is: health, points, a place among the things the player's
## bullets hit, a death with an explosion and perhaps a power-up left behind, and a touch that
## destroys the ship. The four behaviours extend it and say how it moves (_fly) and what it
## fires (_act): RpgShmupPopcorn, RpgShmupTurret, RpgShmupAsteroid, RpgShmupCarrier.
##
## An enemy flies either with the screen (its place is kept relative to the middle of the
## screen, like the ship's) or in the stage (it scrolls past with the background); `in_stage`
## says which. It comes from where the ship looks and travels the other way.

## The framework's sign of a kill (RpgArcadeSpawner, RpgArcadeStage.adopt).
signal defeated

## How far outside the screen an enemy may be before it is taken away, in px.
const MARGIN := 48.0

@export var health: int = 1
@export var points: int = 100
## The radius of what bullets and the ship hit, in px.
@export var hit_radius: float = 8.0
## Px a second along the way it travels.
@export var speed: float = 50.0
@export var orientation: String = "vertical"
## The size of the screen in px.
@export var view: Vector2 = Vector2(320, 180)
## Scrolls past with the background (a turret, an asteroid) instead of flying with the screen.
@export var in_stage: bool = false
@export var explosion_scene: PackedScene = null
@export var powerup_scene: PackedScene = null
## The power-up it leaves when it is shot ("" leaves none); see RpgShmupPowerup.KINDS.
@export var drop: String = ""
@export var bullet_speed: float = 90.0

## False for a test that steps the enemy by hand.
var auto_advance := true
## The middle of the screen when the enemy is not in a stage (a test).
var area_center := Vector2.ZERO
var pool_override: RpgShmupBulletPool = null
## Seconds since it appeared.
var age := 0.0
## Its place in its formation, relative to the formation's middle, turned to the way it travels.
var formation_offset := Vector2.ZERO
var formation := "line"

var _rel := Vector2.ZERO
var _placed := false
var _was_inside := false
var _dead := false

func _ready() -> void:
	add_to_group(RpgShmupBulletPool.TARGET_GROUP)

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta)

## The way the enemy travels: against the way the ship looks.
func travel() -> Vector2:
	return -RpgShmupMath.forward_of(orientation)

## Across the way of the game (to the enemy's left as it travels).
func across() -> Vector2:
	var way := travel()
	return Vector2(-way.y, way.x)

func stage() -> RpgArcadeStage:
	var node := get_parent()
	while node != null:
		if node is RpgArcadeStage:
			return node as RpgArcadeStage
		node = node.get_parent()
	return null

## The middle of the screen, in the coordinates the enemy is placed in.
func center() -> Vector2:
	var found := stage()
	return found.scroller().view_center() if found != null else area_center

func pool() -> RpgShmupBulletPool:
	if pool_override != null:
		return pool_override
	var found := stage()
	return found.get_node_or_null("Bullets") as RpgShmupBulletPool if found != null else null

## The player's ship, or null (none, or destroyed).
func ship() -> Node2D:
	if not is_inside_tree():
		return null
	for node in get_tree().get_nodes_in_group(RpgShmupBulletPool.SHIP_GROUP):
		if node is Node2D and node.has_method(&"hit") and not RpgUtil.to_bool(node.get(&"dead")):
			return node as Node2D
	return null

## Where the enemy is, relative to the middle of the screen.
func on_screen() -> Vector2:
	return position - center()

func is_inside_screen() -> bool:
	return Rect2(-view * 0.5, view).has_point(on_screen())

## Called by the spawner: the enemy's place in the formation of `wave`, and what the entry of
## the wave says about it (`path`, `drop`, `shoots`, and how hard the plan made it: `fast`, a
## factor of the speed of its bullets, and `tough`, a factor of its health).
func spawned_in_wave(wave: RpgArcadeWave, index: int) -> void:
	var places := RpgArcadeWave.offsets(wave.formation, wave.count, wave.gap)
	var plain := places[index] if index < places.size() else Vector2.ZERO
	# formations are laid out for a game that scrolls up; turned for one that scrolls right
	var turned := plain.rotated(Vector2.DOWN.angle_to(travel()))
	position += turned - plain
	formation_offset = turned
	formation = wave.formation
	if wave.data.has("drop") and (index == wave.count - 1 or wave.count == 1):
		drop = RpgUtil.to_str(wave.data["drop"])  # the last of a formation carries it
	bullet_speed *= RpgUtil.to_float(wave.data.get("fast", 1.0), 1.0)
	health = maxi(1, roundi(health * RpgUtil.to_float(wave.data.get("tough", 1.0), 1.0)))
	_read_wave(wave.data, index)

## What a behaviour reads from the entry of its wave.
func _read_wave(_data: Dictionary, _index: int) -> void:
	pass

## One step: the enemy moves, acts, touches the ship, and is gone when it has left the screen.
func advance(delta: float) -> void:
	if _dead:
		return
	var middle := center()
	if not _placed:
		_placed = true
		_rel = position - middle
		_start()
	age += delta
	if in_stage:
		position += _drift() * delta
	else:
		_rel = _fly(_rel, delta)
		position = middle + _rel
	_act(delta)
	_touch_ship()
	if is_inside_screen():
		_was_inside = true
	elif _gone():
		queue_free()

## Called once, at the first step.
func _start() -> void:
	pass

## Where an enemy that flies with the screen is after this step (relative to its middle).
func _fly(rel: Vector2, delta: float) -> Vector2:
	return rel + travel() * speed * delta

## How an enemy that sits in the stage moves by itself, in px a second.
func _drift() -> Vector2:
	return Vector2.ZERO

## What the enemy does beside moving (shooting, releasing others).
func _act(_delta: float) -> void:
	pass

## True when the enemy has left the screen for good: it was on it, or it is behind it.
func _gone() -> bool:
	var rel := on_screen()
	var behind := rel.dot(travel())
	var limit := (absf(travel().x) * view.x + absf(travel().y) * view.y) * 0.5 + MARGIN
	if behind > limit:
		return true
	return _was_inside and not Rect2(-view * 0.5, view).grow(MARGIN).has_point(rel)

func _touch_ship() -> void:
	var target := ship()
	if target == null:
		return
	var reach := hit_radius + RpgUtil.to_float(target.get(&"hit_radius"), 1.0)
	if target.position.distance_squared_to(position) <= reach * reach:
		target.call(&"hit")

## A bullet (or a bomb) hits for `damage`.
func take_hit(damage: int) -> void:
	if _dead or damage <= 0:
		return
	health -= damage
	if health <= 0:
		die()

## Shot down: an explosion, the power-up it carries, and `defeated`.
func die() -> void:
	if _dead:
		return
	_dead = true
	remove_from_group(RpgShmupBulletPool.TARGET_GROUP)
	var parent := get_parent()
	if explosion_scene != null and parent != null:
		var burst := explosion_scene.instantiate() as Node2D
		if burst != null:
			burst.position = position
			parent.add_child(burst)
	if drop != "" and powerup_scene != null and parent != null:
		var left := powerup_scene.instantiate() as Node2D
		if left != null:
			left.set(&"kind", drop)
			left.position = position
			parent.add_child.call_deferred(left)
	_on_death()
	defeated.emit()
	queue_free()

## What a behaviour does when it is shot (an asteroid breaks in two).
func _on_death() -> void:
	pass

## Fires `velocities` from where the enemy is. Returns how many bullets left.
func fire(velocities: PackedVector2Array) -> int:
	return RpgShmupEnemyBullet.fire(pool(), position, velocities)
