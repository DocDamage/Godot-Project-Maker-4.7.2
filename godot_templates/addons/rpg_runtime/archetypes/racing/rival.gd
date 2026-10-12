class_name RpgRival
extends Node
## What drives a rival's car (its child `Input`, where the player's car has RpgCarInput): it
## follows the waypoints of the track with the car's own physics, nothing else. It heads for
## the next waypoint, brakes down to the speed the waypoint has in the distance the brake
## needs, and gives no pedal while it is still turning at speed.
##
## `skill` (0 to 1) is how good it is at that: a weaker driver brakes earlier, takes corners
## more slowly, uses less of the pedal and holds the middle of the road less well. `pace`
## (a race's rubber band, 1 when there is none) only takes pedal away from a rival that is far
## ahead; it never makes one faster than its car. A rival that gets stuck (a car that stands
## in its way, a tyre) backs off and passes on the other side of the road for a while.

## How near a waypoint it turns to the next one, in tiles.
const REACH := 4.0
## Steps a car may stand before the driver backs it off what it is stuck on, and for how long.
const STUCK_STEPS := 90
const BACK_STEPS := 40
## After backing off: how long it keeps to one side of the road, and how far from its middle
## (tiles).
const DODGE_STEPS := 150
const DODGE_TILES := 1.5
## Steps it carries a weapon before it uses it.
const FIRE_AFTER := 50

@export var skill: float = 0.7

var route := PackedVector2Array()
var speeds := PackedFloat32Array()
## The waypoint it heads for.
var index := 0
var pace := 1.0

var _stuck := 0
var _back := 0
var _armed := 0
var _dodge := 0
var _dodge_side := 1.0

## The waypoints of the track (px) and the speed each allows (tiles a second).
func set_route(points: PackedVector2Array, limits: PackedFloat32Array, first: int = 0) -> void:
	route = points
	speeds = limits
	index = posmod(first, maxi(1, points.size()))
	_stuck = 0
	_back = 0
	_dodge = 0

## Where it aims near waypoint `i`: beside the middle of the road, the more the weaker it is.
func aim(i: int, tile: float) -> Vector2:
	var at := route[i]
	var next := route[(i + 1) % route.size()]
	var before := route[posmod(i - 1, route.size())]
	var side := (next - before).orthogonal().normalized()
	# the same side every lap: a number of the waypoint, between -1 and 1
	var lean := sin(i * 12.9898 + skill * 78.233) * (1.0 - skill) * 1.2
	if _dodge > 0:  # round what it was stuck on
		lean = _dodge_side * DODGE_TILES
	return at + side * lean * tile

func poll(body: CharacterBody2D) -> void:
	var car := body as RpgCar
	if car == null or route.is_empty() or not car.engine_on:
		return
	var tile := car.tile_size
	var to := aim(index, tile) - car.position
	if to.length() < REACH * tile:
		index = (index + 1) % route.size()
		to = aim(index, tile) - car.position
	var speed := car.speed_tiles()
	if _back > 0:  # backing off what it was stuck on
		_back -= 1
		car.throttle = -1.0
		car.steer = -RpgCarPhysics.steer_toward(car.heading, to.angle())
		return
	_stuck = _stuck + 1 if absf(speed) < 0.6 and not car.is_spinning() else 0
	if _stuck > STUCK_STEPS:
		_stuck = 0
		_back = BACK_STEPS
		_dodge = DODGE_STEPS
		_dodge_side = -_dodge_side  # the other side each time
	_dodge = maxi(0, _dodge - 1)
	var limit := (speeds[index] if index < speeds.size() else RpgCarPhysics.TOP) * (0.7 + 0.3 * skill)
	# a weaker driver does not use all of its car on a straight either
	var cruise := car.top_tiles() * (0.75 + 0.25 * skill)
	var room := (speed * speed - limit * limit) / (2.0 * RpgCarPhysics.BRAKE) + 2.5 + (1.0 - skill) * 2.0
	var slow := speed > limit and to.length() < room * tile
	var off := RpgCarPhysics.angle_difference(car.heading, to.angle())
	var turning := absf(off) > 0.45 and speed > 6.0
	car.steer = RpgCarPhysics.steer_toward(car.heading, to.angle())
	if slow:
		car.throttle = -1.0
	elif turning or speed > cruise:
		car.throttle = 0.0
	else:
		car.throttle = (0.85 + 0.15 * skill) * clampf(pace, 0.5, 1.0)
	if car.weapon != "":
		_armed += 1
		if _armed >= FIRE_AFTER:
			_armed = 0
			car.press_fire()
	else:
		_armed = 0
