class_name RpgCar
extends CharacterBody2D
## A car of a racing game, seen from above. It drives by RpgCarPhysics: it speeds up to a top
## speed, brakes and reverses, turns more slowly the faster it goes, is slower and slides on
## grass, hardly steers on oil, drifts when it turns hard at speed, and loses speed when it
## bumps into a barrier or another car. A boost (`press_boost` while it has one, or a boost
## arrow of the track) makes it faster for a moment.
##
## The car is told what to want: `throttle` (1 the pedal, -1 the brake and reverse), `steer`
## (-1 left to 1 right) and press_boost(). With `absolute_steering` the `stick` points where the
## car is to head. RpgCarInput tells the player's car from the input actions, RpgRival a
## rival's from the waypoints of the track; a test tells it directly. Its children: `Visual`
## (RpgHeadingSprite), `Body` and `Input` (what drives it).
##
## In a race (RpgRace) a car stands still until the start (`engine_on`), may carry one weapon
## (`weapon`: a missile or a bomb, used with press_fire), may have a shield that takes one hit,
## and spins out of control for a moment when it is hit (`hit`). The parts a player has won
## make it better: `top_mul`, `accel_mul`, `grip_mul`.
##
## The car drives on the flat plan of its track: its position, its heading and its velocity
## are the plan's, whatever the view. On a track that is seen at an angle (RpgRaceView, T17.15)
## only its picture is somewhere else: `shown_position()` and `shown_heading()` say where it is
## drawn and which way it points on the screen, and the stick of *absolute* steering is a
## direction of the screen.

signal bumped(lost_tiles: float)
signal boosted
signal drift_started
signal surface_changed(surface: String)
signal weapon_fired(kind: String)
signal spun_out
signal shield_broken

## How long a car that was hit spins, and how fast it turns while it does.
const SPIN_S := 1.2
const SPIN_RAD_S := 11.0

@export var is_player: bool = true
## The size of a tile of the track in px: the model's lengths are tiles.
@export var tile_size: float = 16.0
## The stick is the heading (easier for newcomers); else left and right turn the car.
@export var absolute_steering: bool = false
## The boosts the car has.
@export var boosts: int = 3
@export var max_boosts: int = 9
@export var bump_sound: StringName = &"sfx_bump"
@export var skid_sound: StringName = &"sfx_skid"

## Where the car points: rad, 0 is to the right, a quarter turn clockwise is down.
@export var heading: float = -PI * 0.5
var throttle := 0.0
var steer := 0.0
var stick := Vector2.ZERO
var drifting := false
## Seconds of boost left.
var boost_left := 0.0
## What the car drives on now (a surface of RpgCarPhysics).
var surface := "road"
## What it drives on when the track says nothing (a test).
var surface_override := ""
## Reads the input every step; a test or a smoke step turns it off and tells the car itself.
var input_node_enabled := true

## The car drives (a race keeps it off until the start, and after the finish).
var engine_on := true
## The weapon the car carries: "", "missile" or "bomb".
var weapon := ""
## A shield takes the next hit.
var shielded := false
## Seconds the car still spins after a hit.
var spin_left := 0.0
## What the car's parts make of it: its top speed, its acceleration and its grip, times these.
var top_mul := 1.0
var accel_mul := 1.0
var grip_mul := 1.0

var _boost_asked := false
var _fire_asked := false
var _surfaces: RpgTrackSurfaces = null
var _surfaces_known := false
var _view: RpgRaceView = null
var _view_known := false

func _ready() -> void:
	motion_mode = CharacterBody2D.MOTION_MODE_FLOATING
	_show()

func _physics_process(delta: float) -> void:
	poll_input()
	step(delta)

func poll_input() -> void:
	var input := get_node_or_null("Input")
	if input_node_enabled and input != null and input.has_method(&"poll"):
		input.call(&"poll", self)

## A boost at the next step, if the car has one.
func press_boost() -> void:
	_boost_asked = true

## One more boost (a pickup), up to `max_boosts`. True when it was taken.
func add_boost() -> bool:
	if boosts >= max_boosts:
		return false
	boosts += 1
	return true

## Uses the weapon the car carries, at the next step.
func press_fire() -> void:
	_fire_asked = true

## Something hit the car (a missile, a bomb): a shield takes it, else the car spins. True when
## the car spins.
func hit() -> bool:
	if shielded:
		shielded = false
		shield_broken.emit()
		return false
	spin_left = SPIN_S
	boost_left = 0.0
	spun_out.emit()
	play_sound(skid_sound)
	return true

func is_spinning() -> bool:
	return spin_left > 0.0

## The top speed of this car on the road, tiles a second.
func top_tiles() -> float:
	return RpgCarPhysics.TOP * top_mul

## Starts a boost now (a boost arrow of the track; press_boost spends one of the car's own).
func start_boost() -> void:
	boost_left = RpgCarPhysics.BOOST_S
	boosted.emit()

func is_boosting() -> bool:
	return boost_left > 0.0

## The way the car points, a unit vector.
func forward() -> Vector2:
	return Vector2.from_angle(heading)

## The speed along the heading, tiles a second (negative in reverse).
func speed_tiles() -> float:
	return RpgCarPhysics.split(velocity, heading).x / tile_size if tile_size > 0.0 else 0.0

## The speed sideways to the heading, tiles a second.
func lateral_tiles() -> float:
	return RpgCarPhysics.split(velocity, heading).y / tile_size if tile_size > 0.0 else 0.0

## Puts the car somewhere, standing, pointing along `rad`.
func place(at: Vector2, rad: float) -> void:
	position = at
	heading = rad
	velocity = Vector2.ZERO
	boost_left = 0.0
	spin_left = 0.0
	drifting = false
	_show()

## How the track is seen: null from above, where the picture is where the car is.
func view() -> RpgRaceView:
	if not _view_known or (_view != null and not is_instance_valid(_view)):
		_view_known = is_inside_tree()
		_view = RpgRaceView.of(get_parent())
	return _view

## Where the car is drawn, in the coordinates it is in: its place in the plan seen from above.
func shown_position() -> Vector2:
	var seen := view()
	return seen.to_screen(position) if seen != null else position

## The way the car points on the screen: its heading seen from above.
func shown_heading() -> float:
	var seen := view()
	return seen.screen_heading(heading) if seen != null else heading

## The way the car points on the screen, a unit vector.
func shown_forward() -> Vector2:
	return Vector2.from_angle(shown_heading())

func _map_root() -> Node:
	var node := get_parent()
	var top := node
	while node != null:
		if node is RpgMapRoot:
			return node
		top = node
		node = node.get_parent()
	return top

## What the car drives on: what the track says of the cell under it, else what the tile under
## it says, else road.
func surface_here() -> String:
	if surface_override != "":
		return RpgCarPhysics.surface(surface_override)
	if not _surfaces_known or (_surfaces != null and not is_instance_valid(_surfaces)):
		_surfaces_known = true
		_surfaces = null
		var root := _map_root()
		if root != null:
			for node in root.find_children("*", "Node2D", true, false):
				if node is RpgTrackSurfaces:
					_surfaces = node as RpgTrackSurfaces
					break
	if _surfaces != null:
		return _surfaces.at(RpgUtil.world_position(self))
	return RpgCarPhysics.surface(_tile_surface())

func _tile_surface() -> String:
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	var root := _map_root()
	if audio == null or root == null or not audio.get(&"bank") is RpgSoundBank:
		return ""
	var bank: RpgSoundBank = audio.get(&"bank")
	var layers: Array[TileMapLayer] = []
	for node in root.find_children("*", "TileMapLayer", true, false):
		layers.append(node as TileMapLayer)
	return RpgMovement.surface_at(layers, RpgUtil.world_position(self), bank)

## One physics step: the wheel, the pedals, the grip of the ground, the move, a bump.
func step(delta: float) -> void:
	if not engine_on:
		velocity = Vector2.ZERO
		_boost_asked = false
		_fire_asked = false
		_show()
		return
	if _fire_asked:
		_fire_asked = false
		if weapon != "" and not is_spinning():
			var fired := weapon
			weapon = ""
			weapon_fired.emit(fired)
	if is_spinning():
		# out of control: it turns round and round and loses its speed
		spin_left = maxf(0.0, spin_left - delta)
		heading = wrapf(heading + SPIN_RAD_S * delta, -PI, PI)
		velocity = velocity.move_toward(Vector2.ZERO, RpgCarPhysics.BRAKE * 0.5 * tile_size * delta)
		var met := move_and_collide(velocity * delta)
		if met != null:
			velocity = RpgCarPhysics.bump(velocity, met.get_normal())
		_boost_asked = false
		_show()
		return
	var here := surface_here()
	if here != surface:
		surface = here
		surface_changed.emit(surface)
		if surface == "boost":
			start_boost()
	if _boost_asked:
		_boost_asked = false
		if boosts > 0 and not is_boosting():
			boosts -= 1
			start_boost()
	var wheel := clampf(steer, -1.0, 1.0)
	if absolute_steering:
		# the stick is a direction of the screen: on a track seen at an angle that is another
		# heading of the plan
		var seen := view()
		var wanted := seen.plan_vector(stick).angle() if seen != null else stick.angle()
		wheel = RpgCarPhysics.steer_toward(heading, wanted) if stick.length() > 0.35 else 0.0
	var state := RpgCarPhysics.step({
		"x": 0.0, "y": 0.0, "heading": heading,
		"vx": velocity.x / tile_size, "vy": velocity.y / tile_size, "boost": boost_left,
	}, throttle, wheel, surface, delta, top_tiles(), RpgCarPhysics.ACCEL * accel_mul, grip_mul)
	heading = wrapf(RpgUtil.to_float(state["heading"]), -PI, PI)
	boost_left = RpgUtil.to_float(state["boost"])
	velocity = Vector2(RpgUtil.to_float(state["vx"]), RpgUtil.to_float(state["vy"])) * tile_size
	var slides := RpgCarPhysics.is_drifting(RpgUtil.to_float(state["lateral"]), top_tiles())
	if slides and not drifting:
		drift_started.emit()
		play_sound(skid_sound)
	drifting = slides
	var hit := move_and_collide(velocity * delta)
	if hit != null:
		var before := velocity.length()
		velocity = RpgCarPhysics.bump(velocity, hit.get_normal())
		# the rest of the step goes along what was hit
		move_and_collide(hit.get_remainder().slide(hit.get_normal()))
		var lost := (before - velocity.length()) / tile_size
		if lost > 0.5:
			bumped.emit(lost)
			play_sound(bump_sound)
	_show()

func _show() -> void:
	var seen := view()
	if seen != null:
		_show_on(seen)
		return
	var visual := get_node_or_null("Visual") as RpgHeadingSprite
	if visual != null:
		visual.show_heading(heading)

## The picture on a track seen at an angle: where the plan's place is on the screen, pointing
## the way the heading looks there, and in front of what stands behind it.
func _show_on(seen: RpgRaceView) -> void:
	var picture := get_node_or_null("Visual") as Node2D
	if picture == null:
		return
	picture.position = seen.to_screen(position) - position
	picture.z_index = seen.depth(position)
	if picture is RpgHeadingSprite:
		(picture as RpgHeadingSprite).show_heading(seen.screen_heading(heading))
	else:
		picture.rotation = seen.screen_heading(heading) + PI * 0.5

## Plays a sound slot through the game audio service (silent when the slot is unset).
func play_sound(slot: StringName) -> void:
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	if audio != null and audio.has_method("play"):
		audio.call("play", slot)
