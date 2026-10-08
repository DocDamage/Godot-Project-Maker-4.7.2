class_name RpgProjectile
extends Area2D
## A shot of the action RPG: it flies straight, hurts the first hurtbox of the other team it touches
## (the damage formula of a melee hit, with the shooter's attack when it was fired), and is gone after
## a hit, at a wall (world layer 1) or after `range_px`. Layers: those of its team's hitbox (player 7
## looking at 10, enemy 8 looking at 9) and the world. Made in code (RpgProjectile.create) and never
## saved; it is drawn in code too (an orb, or an arrow along its flight). A cutscene holds it.

const GROUP := &"rpg_projectiles"
const RADIUS := 3.0
const ENEMY_COLOR := Color(1.0, 0.55, 0.2)
const PLAYER_COLOR := Color(0.75, 0.9, 1.0)

var team: StringName = &"enemy"
var velocity := Vector2.ZERO
var range_px := 160.0
## The shooter's attack when it was fired (equipment counted).
var attack := 1
var crit_chance := RpgArpgMath.DEFAULT_CRIT_CHANCE
var knockback_strength := 120.0
## "orb" or "arrow".
var style := "orb"
## The player's heavy attack fired it: more damage (RpgArpgMath.heavy_damage).
var heavy := false
var source: Node = null
var travelled := 0.0
var done := false

## A shot from `shooter` (its stats give the attack) at `from` (global) toward `direction`. Not yet in
## the tree: add it to the map, then it flies.
static func create(shooter: Node2D, from: Vector2, direction: Vector2, shot_team: StringName, speed: float, max_range_px: float, shot_style: String = "orb") -> RpgProjectile:
	var shot := RpgProjectile.new()
	shot.name = "Projectile"
	shot.team = shot_team
	shot.source = shooter
	shot.style = shot_style
	shot.velocity = direction.normalized() * speed
	shot.range_px = max_range_px
	shot.rotation = direction.angle()
	shot.position = from
	shot.z_index = 1
	shot.collision_layer = 0
	shot.collision_mask = 0
	shot.set_collision_layer_value(7 if shot_team == &"player" else 8, true)
	shot.set_collision_mask_value(10 if shot_team == &"player" else 9, true)
	shot.set_collision_mask_value(1, true)  # walls
	shot.monitorable = false
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var circle := CircleShape2D.new()
	circle.radius = RADIUS
	shape.shape = circle
	shot.add_child(shape)
	var stats := _stats_of(shooter)
	if stats != null:
		var state := RpgUtil.state()
		shot.attack = roundi(state.effective_stat(stats, &"attack")) if state != null else stats.attack
		shot.crit_chance = RpgUtil.to_float(stats.extra.get("crit_chance", RpgArpgMath.DEFAULT_CRIT_CHANCE))
	return shot

static func _stats_of(shooter: Node) -> RpgStats:
	var actor := shooter as RpgActor
	if actor == null:
		return null
	var comp := actor.component("Stats") as RpgStatsComponent
	return comp.stats if comp != null else null

func _ready() -> void:
	add_to_group(GROUP)
	area_entered.connect(_on_area_entered)
	body_entered.connect(_on_body_entered)

func _physics_process(delta: float) -> void:
	if done or RpgSequenceRunner.running():
		return
	advance(delta)

## Flies on by `delta` seconds; gone once it has flown its range.
func advance(delta: float) -> void:
	var step := velocity * delta
	position += step
	travelled += step.length()
	if travelled >= range_px:
		finish()

## Hits `hurtbox` when it belongs to the other team: true when the damage landed. The shot is gone
## either way (an invulnerable target still stops it).
func hit(hurtbox: RpgHurtbox) -> bool:
	if done or hurtbox == null or hurtbox.team == team:
		return false
	var landed := hurtbox.receive(build_info(hurtbox))
	finish()
	return landed

func build_info(hurtbox: RpgHurtbox) -> RpgDamageInfo:
	var info := RpgDamageInfo.new()
	info.source = source if is_instance_valid(source) else null
	var state := RpgUtil.state()
	var rng: RpgRng = state.rng if state != null else null
	var rolled := RpgArpgMath.roll_damage(attack, hurtbox.defense(), crit_chance, rng)
	info.amount = RpgUtil.to_int(rolled["amount"])
	if heavy:
		info.amount = RpgArpgMath.heavy_damage(info.amount)
	info.crit = RpgUtil.to_bool(rolled["crit"])
	info.knockback = velocity.normalized() * knockback_strength
	return info

func finish() -> void:
	if done:
		return
	done = true
	velocity = Vector2.ZERO
	set_deferred("monitoring", false)
	if is_inside_tree():
		queue_free()

func _on_area_entered(area: Area2D) -> void:
	hit(area as RpgHurtbox)

func _on_body_entered(body: Node) -> void:
	if body != source:
		finish()  # a wall

func _draw() -> void:
	var color := PLAYER_COLOR if team == &"player" else ENEMY_COLOR
	if style == "arrow":
		draw_line(Vector2(-7, 0), Vector2(3, 0), color, 1.5)
		draw_colored_polygon(PackedVector2Array([Vector2(5, 0), Vector2(1, -2.5), Vector2(1, 2.5)]), color)
	else:
		draw_circle(Vector2.ZERO, RADIUS + 1.0, color.darkened(0.5))
		draw_circle(Vector2.ZERO, RADIUS, color)
