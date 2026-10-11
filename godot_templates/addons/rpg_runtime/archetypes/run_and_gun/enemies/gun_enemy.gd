class_name RpgGunEnemy
extends RpgPlatformActor
## What every enemy of a run and gun is: a platform actor (it stands on floors and falls) that
## the soldier's bullets and grenades hit, with health, points, a death with an explosion, a
## touch that hurts the soldier, and shots into the stage's bullet pool. The behaviours extend
## it and say what it does in think(): RpgRunnerEnemy, RpgSniperEnemy, RpgGunTurret,
## RpgJumperEnemy and RpgWallCannon.
##
## An enemy that is left behind (the camera never goes back) is taken away without points.

## The framework's sign of a kill (RpgArcadeSpawner, RpgArcadeStage.adopt).
signal defeated

const BEHIND := 64.0

@export var health: int = 1
@export var points: int = 100
## Px a second, at 16 px tiles.
@export var bullet_speed: float = 110.0
## The size of the screen in px.
@export var view: Vector2 = Vector2(640, 360)
@export var explosion_scene: PackedScene = null
## Part of the scenery: it does not move or fall.
@export var fixed: bool = false

## The radius of what bullets hit, in px.
var hit_radius := 8.0
var dead := false
var age := 0.0
var pool_override: RpgArcadeBulletPool = null
## Bullets it has fired (tests and smoke steps look at it).
var shots := 0

func _ready() -> void:
	super._ready()
	add_to_group(RpgArcadeBulletPool.TARGET_GROUP)
	hit_radius = maxf(3.0, minf(body_height(), body_width() * 2.0) * 0.5)

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

## The soldier, or null (none, or dead).
func soldier() -> Node2D:
	if not is_inside_tree():
		return null
	for node in get_tree().get_nodes_in_group(RpgArcadeBulletPool.SHIP_GROUP):
		if node is Node2D and node.has_method(&"hit") and not RpgUtil.to_bool(node.get(&"dead")):
			return node as Node2D
	return null

## The middle of the body, as a global point: what bullets hit, and where its shots start.
func hit_center() -> Vector2:
	return body_center()

## The middle of `body` (its hit_center when it has one).
static func middle_of(body: Node2D) -> Vector2:
	if body.has_method(&"hit_center"):
		var at: Variant = body.call(&"hit_center")
		if at is Vector2:
			return at
	return body.global_position

## Which side the soldier is on: -1 (left), 1 (right) or 0 (none).
func side_of_soldier() -> int:
	var target := soldier()
	if target == null:
		return 0
	var dx := target.global_position.x - global_position.x
	return 0 if absf(dx) < 1.0 else (1 if dx > 0.0 else -1)

func tiles_to_soldier() -> float:
	var target := soldier()
	if target == null:
		return INF
	return hit_center().distance_to(middle_of(target)) / maxf(1.0, tile_size)

## Called by the spawner: what the entry of the wave says (`fast`, `tough`, and a behaviour's own).
func spawned_in_wave(wave: RpgArcadeWave, index: int) -> void:
	bullet_speed *= RpgUtil.to_float(wave.data.get("fast", 1.0), 1.0)
	health = maxi(1, roundi(health * RpgUtil.to_float(wave.data.get("tough", 1.0), 1.0)))
	_read_wave(wave.data, index)

func _read_wave(_data: Dictionary, _index: int) -> void:
	pass

func step(delta: float) -> void:
	if dead:
		return
	age += delta
	think(delta)
	if not fixed:
		super.step(delta)
	_touch_soldier()
	if _left_behind():
		queue_free()

## What the enemy wants to do this step: set move_x, press_jump(), fire. The base enemy stands.
func think(_delta: float) -> void:
	move_x = 0.0

func _touch_soldier() -> void:
	var target := soldier()
	if target == null:
		return
	var reach := hit_radius + RpgUtil.to_float(target.get(&"hit_radius"), 4.0)
	if hit_center().distance_squared_to(middle_of(target)) <= reach * reach:
		target.call(&"hit")

func _left_behind() -> bool:
	var found := stage()
	if found == null:
		return false
	var middle := found.scroller().view_center()
	return position.x < middle.x - view.x * 0.5 - BEHIND or position.y > middle.y + view.y * 0.5 + BEHIND

## Fires `velocities` (px a second) from the middle of the body. Returns how many left.
func fire(velocities: PackedVector2Array) -> int:
	var bullets := pool()
	if bullets == null:
		return 0
	var from := bullets.to_local(hit_center())
	var sent := 0
	for velocity in velocities:
		if bullets.fire(RpgArcadeBulletPool.Team.ENEMY, from, velocity, 1, 2.0, "enemy") >= 0:
			sent += 1
	shots += sent
	return sent

## One bullet at the soldier (along the facing when there is none).
func fire_at_soldier() -> int:
	var target := soldier()
	var way := Vector2(facing, 0.0)
	if target != null and middle_of(target) != hit_center():
		way = (middle_of(target) - hit_center()).normalized()
	return fire(PackedVector2Array([way * px(bullet_speed)]))

## A fan of `count` bullets over `spread_deg` degrees toward the soldier.
func fan_at_soldier(count: int, spread_deg: float) -> int:
	var target := soldier()
	var way := Vector2(facing, 0.0)
	if target != null and middle_of(target) != hit_center():
		way = (middle_of(target) - hit_center()).normalized()
	var out := PackedVector2Array()
	var n := maxi(1, count)
	var half := deg_to_rad(spread_deg) * 0.5
	for i in n:
		var lean := 0.0 if n == 1 else lerpf(-half, half, i / float(n - 1))
		out.append(way.rotated(lean) * px(bullet_speed))
	return fire(out)

## Whether it can be hurt now (a wall cannon is closed most of the time).
func vulnerable() -> bool:
	return true

## A bullet or a blast hits for `damage`.
func take_hit(damage: int) -> void:
	if dead or damage <= 0 or not vulnerable():
		return
	health -= damage
	if health <= 0:
		die()

func die() -> void:
	if dead:
		return
	dead = true
	remove_from_group(RpgArcadeBulletPool.TARGET_GROUP)
	if explosion_scene != null and get_parent() != null:
		var burst := explosion_scene.instantiate() as Node2D
		if burst != null:
			burst.position = position + Vector2(0.0, -body_height() * 0.5)
			get_parent().add_child(burst)
	defeated.emit()
	queue_free()
