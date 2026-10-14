class_name RpgProjectile
extends Area2D
## A shot of the real-time combat: it flies straight, hurts the first hurtbox of the other team it touches
## (the damage formula of a melee hit, with the shooter's attack when it was fired), and is gone after
## a hit, at a wall (world layer 1) or after `range_px`. Layers: those of its team's hitbox (player 7
## looking at 10, enemy 8 looking at 9) and the world. Made in code (RpgProjectile.create) and never
## saved; it is drawn in code too (an orb, or an arrow along its flight). A cutscene holds it.
##
## Seen from the side (the metroidvania) a shot flies at the height it was fired and meets the
## hurtboxes themselves. Seen from above or on diamonds (the action RPG: `set_on_ground`) the
## screen's y is depth and height at once, so a shot fired at the middle of a tall body passed over
## a body shorter than half of it: such a shot flies at its shooter's feet, on the ground, and hurts
## the first body whose footprint (RpgHurtbox.ground_rect) its path crosses, short or tall; only
## its picture is drawn `lift` higher, at the height it was fired from, with a shadow where it is.

const GROUP := &"rpg_projectiles"
const RADIUS := 3.0
const ENEMY_COLOR := Color(1.0, 0.55, 0.2)
const PLAYER_COLOR := Color(0.75, 0.9, 1.0)

var team: StringName = &"enemy"
var velocity := Vector2.ZERO
var range_px := 160.0
## The shooter's attack when it was fired (equipment counted).
var attack := 1
var crit_chance := RpgRealtimeMath.DEFAULT_CRIT_CHANCE
var knockback_strength := 120.0
## "orb" or "arrow".
var style := "orb"
## The player's heavy attack fired it: more damage (RpgRealtimeMath.heavy_damage).
var heavy := false
var source: Node = null
var travelled := 0.0
var done := false
## It flies on the ground (set_on_ground): its position is a point on the ground, it meets
## footprints, not hurtboxes.
var on_ground := false
## How far above its point on the ground its picture is drawn (world axes; on the ground only).
var lift := Vector2.ZERO
## Where on its last way (0 to 1) first_on_path met a footprint.
var _met_at := 1.0

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
		shot.crit_chance = RpgUtil.to_float(stats.extra.get("crit_chance", RpgRealtimeMath.DEFAULT_CRIT_CHANCE))
	return shot

## A shot of a top-down or isometric game (`from` given to create() is its shooter's feet): it flies
## on the ground and its picture is drawn `height` above it (the middle of the shooter's body minus
## its feet). It no longer looks at hurtboxes through physics (masks 9 and 10 off): it meets their
## footprints on its way (advance); walls still stop it, at the height of the feet.
func set_on_ground(height: Vector2) -> void:
	on_ground = true
	lift = height
	set_collision_mask_value(9, false)
	set_collision_mask_value(10, false)
	queue_redraw()

## Where its picture is drawn above its point on the ground: `lift` when it is loosed, coming down
## evenly to the ground at the end of its range (an arrow falls as it flies; at a target of any
## height it is drawn between the hand and the ground).
func drawn_lift() -> Vector2:
	return lift * (1.0 - clampf(travelled / maxf(range_px, 1.0), 0.0, 1.0))

static func _stats_of(shooter: Node) -> RpgStats:
	return RpgRealtimeMath.stats_of(shooter)

func _ready() -> void:
	add_to_group(GROUP)
	area_entered.connect(_on_area_entered)
	body_entered.connect(_on_body_entered)

func _physics_process(delta: float) -> void:
	if done or RpgSequenceRunner.running():
		return
	advance(delta)

## Flies on by `delta` seconds; gone once it has flown its range. On the ground it hurts the first
## body of the other team whose footprint its way crosses (and stops there).
func advance(delta: float) -> void:
	var step := velocity * delta
	var before := RpgUtil.world_position(self)
	position += step
	travelled += step.length()
	if on_ground and is_inside_tree():
		queue_redraw()  # its picture comes down as it flies
		var after := RpgUtil.world_position(self)
		var struck := first_on_path(before, after, targets())
		if struck != null:
			global_position = before + (after - before) * _met_at
			hit(struck)
			return
	if travelled >= range_px:
		finish()

## The hurtboxes a shot on the ground can hurt: those of the other team in the tree, on the layer
## its team's hits look at (enemy hurtboxes 10 for the player's shots, 9 for the enemies'), that
## can be hit now (a dead or dodging body's hurtbox is not monitorable).
func targets() -> Array[RpgHurtbox]:
	var out: Array[RpgHurtbox] = []
	if not is_inside_tree():
		return out
	var layer := 10 if team == &"player" else 9
	for node: Node in get_tree().get_nodes_in_group(RpgHurtbox.GROUP):
		var hurtbox := node as RpgHurtbox
		if hurtbox == null or hurtbox.team == team or not hurtbox.monitorable or hurtbox.is_queued_for_deletion():
			continue
		if hurtbox.get_collision_layer_value(layer):
			out.append(hurtbox)
	return out

## The first of `candidates` whose footprint (grown by the shot's radius) the way from `from` to
## `to` (world, on the ground) crosses, or null; the way is walked in steps no longer than the
## radius, so a fast shot does not jump over a narrow body. Ties go to the first candidate.
func first_on_path(from: Vector2, to: Vector2, candidates: Array) -> RpgHurtbox:
	_met_at = 1.0
	var boxes: Array[RpgHurtbox] = []
	var rects: Array[Rect2] = []
	for node: Node in candidates:
		var hurtbox := node as RpgHurtbox
		if hurtbox != null:
			boxes.append(hurtbox)
			rects.append(hurtbox.ground_rect().grow(RADIUS))
	if boxes.is_empty():
		return null
	var steps := maxi(1, ceili(from.distance_to(to) / RADIUS))
	for i in steps + 1:
		var k := float(i) / float(steps)
		var at := from.lerp(to, k)
		for j in rects.size():
			if rects[j].has_point(at):
				_met_at = k
				return boxes[j]
	return null

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
	var rolled := RpgRealtimeMath.roll_damage(attack, hurtbox.defense(), crit_chance, rng)
	info.amount = RpgUtil.to_int(rolled["amount"])
	if heavy:
		info.amount = RpgRealtimeMath.heavy_damage(info.amount)
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
	if on_ground:
		# its shadow on the ground, where it hits; the picture `lift` above, along the flight
		draw_set_transform(Vector2.ZERO, -rotation, Vector2(1.0, 0.5))
		draw_circle(Vector2.ZERO, RADIUS, Color(0.0, 0.0, 0.0, 0.35))
		draw_set_transform(drawn_lift().rotated(-rotation))
	if style == "arrow":
		draw_line(Vector2(-7, 0), Vector2(3, 0), color, 1.5)
		draw_colored_polygon(PackedVector2Array([Vector2(5, 0), Vector2(1, -2.5), Vector2(1, 2.5)]), color)
	else:
		draw_circle(Vector2.ZERO, RADIUS + 1.0, color.darkened(0.5))
		draw_circle(Vector2.ZERO, RADIUS, color)
