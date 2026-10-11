class_name RpgGunBoss
extends RpgArcadeBoss
## The boss of a run and gun's stage: the arcade boss (health, phases, a warning before every
## attack, an intro and a defeat) as a target of the soldier's bullets and grenades. There are
## three of them, chosen per stage (`kind`):
##
##   wall    the genre's gate with cannons: it stands at the right of the arena and fires
##   walker  walks back and forth across the arena
##   flyer   hovers above it, sweeping from side to side
##
## Attacks: `aimed` (one shot at the soldier per count), `fan` (a fan at the soldier), `burst`
## (a tight burst of three times the count), `rain` (straight down, spread under it) and
## `ring` (all around). A phase's entry in the stage file says how many bullets (`count`) and
## how fast (`fast`, a factor of `bullet_speed`).

const KINDS: Array[String] = ["wall", "walker", "flyer"]
const FAN_DEG := 50.0
const BURST_DEG := 14.0
const RAIN_DEG := 60.0
const BURST := 3

@export var kind: String = "wall"
## The radius of what bullets hit, in px.
@export var hit_radius: float = 20.0
## Px a second.
@export var bullet_speed: float = 110.0
@export var explosion_scene: PackedScene = null
## How far a walker walks to each side of where it stands, in px.
@export var walk_px: float = 80.0

var pool_override: RpgArcadeBulletPool = null
var volleys := 0
var _extras: Array[Dictionary] = []

func _ready() -> void:
	add_to_group(RpgArcadeBulletPool.TARGET_GROUP)
	exploded.connect(_on_exploded)
	defeated.connect(_on_defeated)
	finished.connect(queue_free)

func setup(data: Dictionary) -> void:
	super.setup(data)
	var named := RpgUtil.to_str(data.get("kind", kind))
	if KINDS.has(named):
		kind = named
	var raw: Array[Dictionary] = []
	for entry: Variant in RpgUtil.to_array(data.get("phases", [])):
		if entry is Dictionary:
			var d: Dictionary = entry
			raw.append(d)
	raw.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return RpgUtil.to_float(a.get("until", 0.0)) > RpgUtil.to_float(b.get("until", 0.0)))
	_extras = raw

func pool() -> RpgArcadeBulletPool:
	if pool_override != null:
		return pool_override
	var node := get_parent()
	while node != null:
		if node is RpgArcadeStage:
			return node.get_node_or_null("Bullets") as RpgArcadeBulletPool
		node = node.get_parent()
	return null

func soldier() -> Node2D:
	if not is_inside_tree():
		return null
	for node in get_tree().get_nodes_in_group(RpgArcadeBulletPool.SHIP_GROUP):
		if node is Node2D and node.has_method(&"hit") and not RpgUtil.to_bool(node.get(&"dead")):
			return node as Node2D
	return null

## The middle of what bullets hit, as a global point: above its feet for the two that stand.
func hit_center() -> Vector2:
	return global_position + (Vector2.ZERO if kind == "flyer" else Vector2(0.0, -hit_radius))

static func _middle_of(body: Node2D) -> Vector2:
	if body.has_method(&"hit_center"):
		var at: Variant = body.call(&"hit_center")
		if at is Vector2:
			return at
	return body.global_position

## A bullet or a blast hits for `damage`.
func take_hit(damage: int) -> void:
	take(damage)

func advance(delta: float) -> void:
	super.advance(delta)
	if state != State.FIGHT:
		return
	var target := soldier()
	if target == null:
		return
	var reach := hit_radius + RpgUtil.to_float(target.get(&"hit_radius"), 4.0)
	if hit_center().distance_squared_to(_middle_of(target)) <= reach * reach:
		target.call(&"hit")

func phase_extra() -> Dictionary:
	var index := phase_index()
	return _extras[index] if index >= 0 and index < _extras.size() else {}

## The bullets of one volley of `attack`, as velocities.
func volley(attack: String) -> PackedVector2Array:
	var extra := phase_extra()
	var count := maxi(1, RpgUtil.to_int(extra.get("count", 3), 3))
	var speed := bullet_speed * RpgUtil.to_float(extra.get("fast", 1.0), 1.0)
	var target := soldier()
	var toward := Vector2.LEFT
	if target != null and _middle_of(target) != hit_center():
		toward = (_middle_of(target) - hit_center()).normalized()
	match attack:
		"fan":
			return _fan(toward, count, FAN_DEG, speed)
		"burst":
			return _fan(toward, count * BURST, BURST_DEG, speed)
		"rain":
			return _fan(Vector2.DOWN, count, RAIN_DEG, speed)
		"ring":
			var out := PackedVector2Array()
			for i in count:
				out.append(Vector2.from_angle(volleys * 0.3 + TAU * i / count) * speed)
			return out
	return _fan(toward, count, 6.0 * (count - 1), speed)  # aimed: one after another, nearly together

static func _fan(toward: Vector2, count: int, spread_deg: float, speed: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n := maxi(1, count)
	var half := deg_to_rad(spread_deg) * 0.5
	for i in n:
		var lean := 0.0 if n == 1 else lerpf(-half, half, i / float(n - 1))
		out.append(toward.rotated(lean) * speed)
	return out

func _perform(attack: String) -> void:
	var bullets := pool()
	if bullets != null:
		var from := bullets.to_local(hit_center())
		for velocity in volley(attack):
			bullets.fire(RpgArcadeBulletPool.Team.ENEMY, from, velocity, 1, 2.0, "enemy")
	volleys += 1

func _move(pattern: String, _delta: float, time_s: float) -> void:
	match pattern:
		"sweep":
			position = _home + Vector2(sin(time_s * phase().speed) * sweep_px, sin(time_s * 2.3) * 6.0)
		"walk":
			# out to the left and back at a steady pace: a triangle, not a sine
			var period := 4.0 / maxf(0.1, phase().speed)
			var part := fposmod(time_s, period) / period
			position = _home + Vector2(-(1.0 - absf(part * 2.0 - 1.0)) * walk_px, 0.0)

func _on_exploded(at: Vector2) -> void:
	if explosion_scene == null or get_parent() == null:
		return
	var burst := explosion_scene.instantiate() as Node2D
	if burst != null:
		burst.position = position + (at - global_position) + (Vector2.ZERO if kind == "flyer" else Vector2(0.0, -hit_radius))
		get_parent().add_child(burst)

func _on_defeated() -> void:
	remove_from_group(RpgArcadeBulletPool.TARGET_GROUP)
	var bullets := pool()
	if bullets != null:
		bullets.clear(RpgArcadeBulletPool.Team.ENEMY)
