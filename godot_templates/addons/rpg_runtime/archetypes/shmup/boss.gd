class_name RpgShmupBoss
extends RpgArcadeBoss
## The boss of a shoot-em-up's stage: the arcade boss (health, phases, a warning before every
## attack, an intro and a defeat) with what the kind adds: it is a target of the player's
## bullets, a touch of it destroys the ship, and its attacks are volleys into the bullet pool.
##
## Attacks: `ring` (all around), `fan` (at the ship), `spiral` (a ring that turns from volley to
## volley), `aimed` (a tight burst at the ship) and `sweep` (a fan that swings from side to
## side). A phase's entry in the stage file says how many bullets (`count`) and how fast
## (`fast`, a factor of `bullet_speed`).

const FAN_DEG := 70.0
const AIMED_DEG := 18.0
const SWEEP_DEG := 40.0
## How far a sweeping fan swings to each side, in degrees.
const SWING_DEG := 50.0
## A burst is this many times the phase's count.
const BURST := 3

## The radius of what bullets and the ship hit, in px.
@export var hit_radius: float = 20.0
@export var orientation: String = "vertical"
@export var bullet_speed: float = 88.0
@export var explosion_scene: PackedScene = null

var pool_override: RpgShmupBulletPool = null
## How many volleys it has fired (a spiral and a sweep turn with it).
var volleys := 0
var _extras: Array[Dictionary] = []

func _ready() -> void:
	add_to_group(RpgShmupBulletPool.TARGET_GROUP)
	exploded.connect(_on_exploded)
	defeated.connect(_on_defeated)
	finished.connect(queue_free)

func setup(data: Dictionary) -> void:
	super.setup(data)
	# what the kind added to each phase, in the order the phases are fought
	var raw: Array[Dictionary] = []
	for entry: Variant in RpgUtil.to_array(data.get("phases", [])):
		if entry is Dictionary:
			var d: Dictionary = entry
			raw.append(d)
	raw.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return RpgUtil.to_float(a.get("until", 0.0)) > RpgUtil.to_float(b.get("until", 0.0)))
	_extras = raw

## The way the boss faces: against the way the ship looks.
func travel() -> Vector2:
	return -RpgShmupMath.forward_of(orientation)

func across() -> Vector2:
	var way := travel()
	return Vector2(-way.y, way.x)

func pool() -> RpgShmupBulletPool:
	if pool_override != null:
		return pool_override
	var node := get_parent()
	while node != null:
		if node is RpgArcadeStage:
			return node.get_node_or_null("Bullets") as RpgShmupBulletPool
		node = node.get_parent()
	return null

func ship() -> Node2D:
	if not is_inside_tree():
		return null
	for node in get_tree().get_nodes_in_group(RpgShmupBulletPool.SHIP_GROUP):
		if node is Node2D and node.has_method(&"hit") and not RpgUtil.to_bool(node.get(&"dead")):
			return node as Node2D
	return null

## A bullet (or a bomb) hits for `damage`.
func take_hit(damage: int) -> void:
	take(damage)

func advance(delta: float) -> void:
	super.advance(delta)
	if state != State.FIGHT:
		return
	var target := ship()
	if target == null:
		return
	var reach := hit_radius + RpgUtil.to_float(target.get(&"hit_radius"), 1.0)
	if target.position.distance_squared_to(position) <= reach * reach:
		target.call(&"hit")

## What the stage file says of the phase that is fought: {count, fast}.
func phase_extra() -> Dictionary:
	var index := phase_index()
	return _extras[index] if index >= 0 and index < _extras.size() else {}

## The bullets of one volley of `attack`, as velocities.
func volley(attack: String) -> PackedVector2Array:
	var extra := phase_extra()
	var count := maxi(1, RpgUtil.to_int(extra.get("count", 6), 6))
	var speed := bullet_speed * RpgUtil.to_float(extra.get("fast", 1.0), 1.0)
	var target := ship()
	var toward := travel()
	if target != null and target.position != position:
		toward = (target.position - position).normalized()
	match attack:
		"ring":
			return RpgShmupEnemyBullet.ring(count, speed, volleys * 0.2)
		"spiral":
			return RpgShmupEnemyBullet.spiral(volleys, count, speed)
		"aimed":
			return RpgShmupEnemyBullet.fan(toward, count * BURST, AIMED_DEG, speed)
		"sweep":
			var swing := deg_to_rad(sin(volleys * 0.7) * SWING_DEG)
			return RpgShmupEnemyBullet.fan(travel().rotated(swing), count * BURST, SWEEP_DEG, speed)
	return RpgShmupEnemyBullet.fan(toward, count, FAN_DEG, speed)

func _perform(attack: String) -> void:
	RpgShmupEnemyBullet.fire(pool(), position, volley(attack))
	volleys += 1

func _move(pattern: String, _delta: float, time_s: float) -> void:
	if pattern == "sweep":
		position = _home + across() * sin(time_s * phase().speed) * sweep_px

func _on_exploded(at: Vector2) -> void:
	if explosion_scene == null or get_parent() == null:
		return
	var burst := explosion_scene.instantiate() as Node2D
	if burst != null:
		burst.position = position + (at - global_position)
		get_parent().add_child(burst)

## Beaten: nothing of it can be hit any more, and what it fired is gone.
func _on_defeated() -> void:
	remove_from_group(RpgShmupBulletPool.TARGET_GROUP)
	var bullets := pool()
	if bullets != null:
		bullets.clear(RpgShmupBulletPool.Team.ENEMY)
