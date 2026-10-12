class_name RpgCarPhysics
extends RefCounted
## The arithmetic of a racing game's car: pure functions, the same as rpggen's
## `rpggen/core/car_math.py` (both are tested against one table of cases).
##
## The model is an arcade one. A car has a heading and a speed along it; it speeds up to a top
## speed, brakes, rolls out, and reverses slowly. It turns faster when it is slow than when it
## is fast. What it drives on gives it grip: on grass it is slower and slides, on oil it hardly
## steers. Turning moves the heading; the speed the car had sideways to its new heading fades
## with the grip, and while there is much of it the car drifts. A bump costs speed. Lengths are
## in tiles and angles in radians (0 is to the right, a quarter turn clockwise is down).

## What a surface does: [grip, how much of the top speed it allows].
const SURFACES := {
	"road": [1.0, 1.0],
	"boost": [1.0, 1.0],
	"dirt": [0.7, 0.8],
	"grass": [0.45, 0.55],
	"oil": [0.12, 1.0],
}
const DEFAULT_SURFACE := "road"
## The names the ground of a pack may have (its `surface:<name>` tag or a tile's `footstep`).
const SURFACE_NAMES := {
	"asphalt": "road", "tarmac": "road", "stone": "road", "wood": "road", "metal": "road",
	"sand": "dirt", "gravel": "dirt", "mud": "dirt", "snow": "dirt",
	"water": "oil", "ice": "oil",
}

const TOP := 12.0  # tiles a second
const ACCEL := 9.0  # tiles a second, every second
const BRAKE := 22.0
const DRAG := 5.0  # rolling out with nothing held
const REVERSE := 0.4  # of the top speed
const OVERSPEED := 14.0  # how fast a car that is over its top speed slows
const TURN_SLOW := 3.4  # rad a second, at walking pace
const TURN_FAST := 1.9  # at the top speed
const TURN_FROM := 0.8  # tiles a second: below this a car turns less, and not at all standing
const TRACTION := 16.0  # how fast sideways speed fades at full grip
const DRIFT_FROM := 0.18  # of the top speed, sideways: from here on the car drifts
const BOUNCE := 0.3  # how much of the speed into a barrier comes back out
const SCRAPE := 0.75  # how much of the speed along a barrier is kept
const BOOST_TOP := 1.5
const BOOST_ACCEL := 3.0
const BOOST_S := 1.5
const STEER_FULL := 0.5  # rad off the wanted heading at which absolute steering steers all the way
const LEAD := 0.25  # of the screen: how far the camera looks ahead at the top speed
const ZOOM_FAR := 0.85  # the camera's zoom at the top speed (1 standing)

## The surface of the car's model for the name the ground has.
static func surface(surface_name: String) -> String:
	var key := surface_name.strip_edges().to_lower()
	if SURFACES.has(key):
		return key
	var known: String = SURFACE_NAMES.get(key, DEFAULT_SURFACE)
	return known

static func _facts(surface_name: String) -> Array:
	var facts: Array = SURFACES[surface(surface_name)]
	return facts

static func grip(surface_name: String) -> float:
	var value: float = _facts(surface_name)[0]
	return value

## The speed a car gets to on a surface.
static func top_speed(surface_name: String, boosting: bool = false, top: float = TOP) -> float:
	var part: float = _facts(surface_name)[1]
	return top * part * (BOOST_TOP if boosting else 1.0)

## The speed along the heading after `delta` s. `throttle` is 1 for the pedal, -1 for the brake
## (which reverses a car that stands), 0 for neither; `limit` the top speed where the car is.
static func accelerate(speed: float, throttle: float, limit: float, delta: float, boosting: bool = false, accel: float = ACCEL, brake: float = BRAKE) -> float:
	throttle = clampf(throttle, -1.0, 1.0)
	var push := accel * (BOOST_ACCEL if boosting else 1.0)
	if speed > limit:  # too fast for where it is: it slows whatever is held
		return maxf(limit, speed - maxf(OVERSPEED, brake if throttle < 0.0 else 0.0) * delta)
	if throttle > 0.0:
		if speed < 0.0:
			return minf(0.0, speed + brake * throttle * delta)
		return minf(limit, speed + push * throttle * delta)
	if throttle < 0.0:
		if speed > 0.0:
			return maxf(0.0, speed + brake * throttle * delta)
		return maxf(-limit * REVERSE, speed + accel * throttle * delta)
	return move_toward(speed, 0.0, DRAG * delta)

## How fast the car turns with the wheel all the way over, in rad a second: fast when it is
## slow, slower at speed, not at all when it stands, and the other way round in reverse.
static func turn_rate(speed: float, top: float = TOP) -> float:
	var pace := absf(speed)
	var rate := TURN_SLOW + (TURN_FAST - TURN_SLOW) * minf(1.0, pace / top if top > 0.0 else 0.0)
	rate *= minf(1.0, pace / TURN_FROM)
	return -rate if speed < 0.0 else rate

## The heading after `delta` s with the wheel at `steer` (-1 left to 1 right). On a surface
## with little grip the wheel does less.
static func turn(heading: float, speed: float, steer: float, surface_name: String, delta: float, top: float = TOP) -> float:
	var bite := minf(1.0, 0.25 + grip(surface_name))
	return heading + clampf(steer, -1.0, 1.0) * turn_rate(speed, top) * bite * delta

## The speed sideways to the heading after `delta` s: it fades with the grip (better tyres,
## `grip_mul` over 1, take it away faster).
static func slide(lateral: float, surface_name: String, delta: float, grip_mul: float = 1.0) -> float:
	return move_toward(lateral, 0.0, TRACTION * grip(surface_name) * grip_mul * delta)

## What a level of a part adds to what it makes better.
const PART_STEP := {"speed": 0.04, "acceleration": 0.08, "tyres": 0.08}
const PART_LEVELS := 3

## What a car's top speed, acceleration or grip is multiplied by with `level` of the part
## (`speed`, `acceleration`, `tyres`): 1 without it, more for each of three.
static func part_factor(part: String, level: int) -> float:
	var step_up: float = PART_STEP.get(part, 0.0)
	return 1.0 + step_up * clampi(level, 0, PART_LEVELS)

static func is_drifting(lateral: float, top: float = TOP) -> bool:
	return absf(lateral) > DRIFT_FROM * top

## A velocity as Vector2(speed along the heading, speed to its right).
static func split(velocity: Vector2, heading: float) -> Vector2:
	var c := cos(heading)
	var s := sin(heading)
	return Vector2(velocity.x * c + velocity.y * s, -velocity.x * s + velocity.y * c)

## The velocity of a speed along the heading and one to its right.
static func join(forward: float, lateral: float, heading: float) -> Vector2:
	var c := cos(heading)
	var s := sin(heading)
	return Vector2(forward * c - lateral * s, forward * s + lateral * c)

## The velocity after hitting something whose surface faces `normal`: what went into it comes
## back weaker, what went along it is slowed.
static func bump(velocity: Vector2, normal: Vector2) -> Vector2:
	var into := velocity.dot(normal)
	if into >= 0.0:
		return velocity
	var along := velocity - normal * into
	return along * SCRAPE - normal * into * BOUNCE

## One step of a car that meets nothing. `state` is x, y, heading, vx, vy and boost (the
## seconds of boost left); the result is the same a step later, with `lateral`. `top`, `accel`
## and `grip_mul` are the car's own (its parts).
static func step(state: Dictionary, throttle: float, steer: float, surface_name: String, delta: float,
		top: float = TOP, accel: float = ACCEL, grip_mul: float = 1.0) -> Dictionary:
	var boost := RpgUtil.to_float(state.get("boost", 0.0))
	var boosting := boost > 0.0
	var velocity := Vector2(RpgUtil.to_float(state.get("vx", 0.0)), RpgUtil.to_float(state.get("vy", 0.0)))
	var heading := RpgUtil.to_float(state.get("heading", 0.0))
	heading = turn(heading, split(velocity, heading).x, steer, surface_name, delta, top)
	var parts := split(velocity, heading)
	var forward := accelerate(parts.x, throttle, top_speed(surface_name, boosting, top), delta, boosting, accel)
	var lateral := slide(parts.y, surface_name, delta, grip_mul)
	velocity = join(forward, lateral, heading)
	return {
		"x": RpgUtil.to_float(state.get("x", 0.0)) + velocity.x * delta,
		"y": RpgUtil.to_float(state.get("y", 0.0)) + velocity.y * delta,
		"heading": heading,
		"vx": velocity.x,
		"vy": velocity.y,
		"boost": maxf(0.0, boost - delta),
		"lateral": lateral,
	}

## The frame of a sheet of `count` headings for a heading: the first frame points up, each
## next one a step clockwise (`heading_order: up_cw`).
static func heading_frame(heading: float, count: int) -> int:
	if count <= 1:
		return 0
	return posmod(floori((heading + PI * 0.5) / (TAU / count) + 0.5), count)

## The shortest way from angle `a` to `b`, from -PI to PI.
static func angle_difference(a: float, b: float) -> float:
	return fposmod(b - a + PI, TAU) - PI

## The wheel for *absolute* steering: toward the heading the stick points to.
static func steer_toward(heading: float, wanted: float) -> float:
	return clampf(angle_difference(heading, wanted) / STEER_FULL, -1.0, 1.0)

## How far from the car the camera looks, along the car's velocity (tiles a second): `LEAD` of
## the screen (`view` px) at the top speed.
static func look_ahead(velocity: Vector2, view: float, top: float = TOP) -> Vector2:
	var pace := velocity.length()
	if pace <= 0.0 or top <= 0.0:
		return Vector2.ZERO
	return velocity / pace * view * LEAD * minf(1.0, pace / top)

## The camera's zoom at a speed: 1 standing, `ZOOM_FAR` at the top speed and beyond.
static func zoom_for(pace: float, top: float = TOP) -> float:
	var part := minf(1.0, absf(pace) / top) if top > 0.0 else 0.0
	return 1.0 + (ZOOM_FAR - 1.0) * part

## The speed (tiles a second) at which a curve of `radius` tiles can be taken without sliding.
static func curve_speed(radius: float, surface_name: String = "road") -> float:
	if radius <= 0.0:
		return 0.0
	return minf(top_speed(surface_name), sqrt(TRACTION * grip(surface_name) * radius))
