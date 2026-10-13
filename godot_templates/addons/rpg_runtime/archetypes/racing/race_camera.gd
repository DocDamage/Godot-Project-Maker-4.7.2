class_name RpgRaceCamera
extends Camera2D
## The camera of a race: it follows the car, looks ahead along the way the car moves and zooms
## out a little with its speed. `fixed` keeps it still over the whole track instead (a small
## track fits on the screen).
##
## The camera is where the picture is. On a track seen at an angle (RpgRaceView, T17.15) the
## car is drawn somewhere else than its place in the plan: the camera follows where it is
## drawn and looks ahead the way it moves on the screen, and `fixed` shows the diamond the
## whole track is there. `base_zoom` is the zoom of a car that stands (1 seen from above).

## The car that is followed.
@export var target_path: NodePath = NodePath("")
@export var fixed: bool = false
## The track in the coordinates of the camera's parent: what a fixed camera shows.
@export var track: Rect2 = Rect2()
## The size of the screen in px.
@export var view: Vector2 = Vector2(640, 360)
## How quickly the camera catches up with where it wants to be, a second.
@export var catch_up: float = 5.0
## The zoom of a car that stands: 1 for a track seen from above. An isometric track whose
## diamonds are much larger or smaller than a car has another (the track recipe sets it).
@export var base_zoom: float = 1.0
## Turned off by a test that steps the camera itself.
var auto_advance := true

func _ready() -> void:
	if fixed:
		look_at_track()
	else:
		snap()

func target() -> Node2D:
	return get_node_or_null(target_path) as Node2D

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta)

## The velocity of the car in tiles a second (zero without one).
func _velocity_tiles() -> Vector2:
	var car := target()
	if car == null:
		return Vector2.ZERO
	var velocity: Variant = car.get(&"velocity")
	var tile := RpgUtil.to_float(car.get(&"tile_size"), 16.0)
	if velocity is Vector2 and tile > 0.0:
		var moving: Vector2 = velocity
		return moving / tile
	return Vector2.ZERO

## Where the car is drawn: its position, or what it says of a track seen at an angle.
func target_position() -> Vector2:
	var car := target()
	if car == null:
		return position
	if car.has_method(&"shown_position"):
		var shown: Vector2 = car.call(&"shown_position")
		return shown
	return car.position

## The velocity of the car as it is seen: the same speed, the way it moves on the screen.
func _shown_velocity() -> Vector2:
	var moving := _velocity_tiles()
	var seen := RpgRaceView.of(self)
	if seen == null or moving == Vector2.ZERO:
		return moving
	return seen.screen_vector(moving).normalized() * moving.length()

## Where the camera wants to be: ahead of the car along its velocity. The zoom is taken out
## of the lead of a zoomed camera, so that it is the same part of the screen.
func wanted() -> Vector2:
	if target() == null:
		return position
	var lead := RpgCarPhysics.look_ahead(_shown_velocity(), minf(view.x, view.y))
	return target_position() + (lead / base_zoom if base_zoom != 1.0 and base_zoom > 0.0 else lead)

func wanted_zoom() -> float:
	var zoomed := RpgCarPhysics.zoom_for(_velocity_tiles().length())
	return zoomed * base_zoom if base_zoom != 1.0 else zoomed

## Puts the camera where it wants to be at once (the start of a race).
func snap() -> void:
	if fixed:
		return
	position = wanted()
	zoom = Vector2.ONE * wanted_zoom()

## The whole track on the screen.
func look_at_track() -> void:
	if track.size.x <= 0.0 or track.size.y <= 0.0:
		return
	position = track.get_center()
	# never nearer than a car that stands is seen
	zoom = Vector2.ONE * minf(maxf(1.0, base_zoom), minf(view.x / track.size.x, view.y / track.size.y))

func advance(delta: float) -> void:
	if fixed:
		return
	var part := clampf(catch_up * delta, 0.0, 1.0)
	position = position.lerp(wanted(), part)
	zoom = Vector2.ONE * lerpf(zoom.x, wanted_zoom(), part)
