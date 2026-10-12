class_name RpgRace
extends Node
## A race on a track (the child `Race` of the track's scene): a countdown, the start, the
## checkpoints and the laps of every car, who is where, a warning for a player who drives the
## wrong way, the pickups and the weapons, and the finish with its standings.
##
## A lap counts at the start line, and only when every checkpoint of the track was passed in
## its order since the last time. The places come from that: more laps is ahead, then more
## checkpoints, then nearer to the next one. The race is over when the player has driven its
## laps; rivals that are still on their way are placed by how far they got.
##
## `setup` takes the track's entry of the list of stages (`laps`, `start`, `checkpoints`,
## `waypoints`) and the cars; `begin` puts them on the grid and counts down. RpgRacingMode does
## both when the track is entered; a test does them itself and steps with `advance`.

signal counted(left: int)
signal started
signal lap_done(car: RpgCar, lap: int)
signal positions_changed
signal wrong_way_changed(wrong: bool)
signal pickup_taken(car: RpgCar, kind: String)
signal part_taken(kind: String)
signal finished(standings: Array)

enum Phase { IDLE, COUNTDOWN, RUNNING, FINISHED }

## A car that goes against the track for this long is told so.
const WRONG_WAY_S := 1.0
## How far a rival may be ahead of the player (in checkpoints) before the rubber band takes
## pedal away, and how much at most.
const BAND_FROM := 2.0
const BAND_MOST := 0.25

@export var countdown_s: float = 3.0
## Rivals that are far ahead of the player ease off a little (never the other way round).
@export var rubber_band: bool = true
@export var countdown_sound: StringName = &"sfx_countdown"
@export var lap_sound: StringName = &"sfx_lap"
@export var pickup_sound: StringName = &"sfx_pickup"

var phase: int = Phase.IDLE
var laps := 3
var time_s := 0.0
var cars: Array[RpgCar] = []
var player: RpgCar = null
var gates: Array[RpgRaceCheckpoint] = []
var line: RpgRaceCheckpoint = null
var route := PackedVector2Array()
var route_speeds := PackedFloat32Array()
var pickups: Array[RpgRacePickup] = []
var weapons: Array[RpgRaceWeapon] = []
var wrong_way := false
## Turned off by a test that steps the race itself.
var auto_advance := true

var _lap := {}  # per car (instance id): the lap it is on (0 before the start line)
var _next := {}  # the checkpoint it has to pass next (their number: all passed)
var _done := {}  # the time it finished at
var _last := {}  # where it was a step ago
var _grid := {}  # where it stands at the start: [position, heading]
var _order: Array[RpgCar] = []
var _counted := -1
var _wrong_s := 0.0
var _parked := false

func _physics_process(delta: float) -> void:
	if auto_advance:
		advance(delta)

## The track and its cars. `data` is the track's entry of the list of stages.
func setup(data: Dictionary, all_cars: Array[RpgCar]) -> void:
	cars = all_cars.duplicate()
	player = null
	for car in cars:
		if car.is_player and player == null:
			player = car
		_grid[car.get_instance_id()] = [car.position, car.heading]
		if not car.weapon_fired.is_connected(_on_weapon_fired):
			car.weapon_fired.connect(_on_weapon_fired.bind(car))
	laps = maxi(1, RpgUtil.to_int(data.get("laps", 3), 3))
	gates.clear()
	for raw: Variant in RpgUtil.to_array(data.get("checkpoints", [])):
		if raw is Dictionary:
			var entry: Dictionary = raw
			gates.append(RpgRaceCheckpoint.from_data(entry))
	var begin_at := RpgUtil.to_dict(data.get("start", {}))
	var wide := gates[0].width if not gates.is_empty() else 144.0
	line = RpgRaceCheckpoint.from_data({"position": begin_at.get("line", begin_at.get("position", [0, 0])), "heading": begin_at.get("heading", 0.0), "width": wide})
	route = PackedVector2Array()
	route_speeds = PackedFloat32Array()
	for raw: Variant in RpgUtil.to_array(data.get("waypoints", [])):
		if raw is Dictionary:
			var point: Dictionary = raw
			var at := RpgUtil.to_array(point.get("position", []))
			if at.size() >= 2:
				route.append(Vector2(RpgUtil.to_float(at[0]), RpgUtil.to_float(at[1])))
				route_speeds.append(RpgUtil.to_float(point.get("speed", RpgCarPhysics.TOP), RpgCarPhysics.TOP))
	pickups.clear()
	var holder := get_parent().get_node_or_null("Pickups") if get_parent() != null else null
	if holder != null:
		for node in holder.get_children():
			if node is RpgRacePickup:
				pickups.append(node as RpgRacePickup)
	for car in cars:
		var driver := car.get_node_or_null("Input") as RpgRival
		if driver != null:
			driver.set_route(route, route_speeds)

## Puts every car on the grid and counts down to the start.
func begin() -> void:
	phase = Phase.COUNTDOWN
	time_s = 0.0
	_counted = -1
	wrong_way = false
	_wrong_s = 0.0
	for weapon in weapons:
		if is_instance_valid(weapon):
			weapon.queue_free()
	weapons.clear()
	for pickup in pickups:
		pickup.active = true
		pickup.visible = true
	_done.clear()
	for car in cars:
		var id := car.get_instance_id()
		var spot: Array = _grid[id]
		var at: Vector2 = spot[0]
		var way: float = spot[1]
		car.place(at, way)
		car.engine_on = false
		_lap[id] = 0
		_next[id] = gates.size()
		_last[id] = car.position
		var driver := car.get_node_or_null("Input") as RpgRival
		if driver != null:
			driver.set_route(route, route_speeds)
	_order = cars.duplicate()
	_rank()

func is_running() -> bool:
	return phase == Phase.RUNNING

func is_finished() -> bool:
	return phase == Phase.FINISHED

## Seconds until the start (0 once the race runs).
func countdown_left() -> float:
	return maxf(0.0, countdown_s - time_s) if phase == Phase.COUNTDOWN else 0.0

## The lap `car` is on: 0 before it has crossed the start line, then 1, 2, ...
func lap_of(car: RpgCar) -> int:
	return RpgUtil.to_int(_lap.get(car.get_instance_id(), 0))

## How many checkpoints `car` has passed on its lap.
func checkpoints_of(car: RpgCar) -> int:
	var next := RpgUtil.to_int(_next.get(car.get_instance_id(), 0))
	return next if lap_of(car) > 0 else 0

func has_finished(car: RpgCar) -> bool:
	return _done.has(car.get_instance_id())

## How far `car` has got: its laps, its checkpoints, and how near the next one it is.
func progress(car: RpgCar) -> float:
	var id := car.get_instance_id()
	var next := RpgUtil.to_int(_next.get(id, 0))
	var target := gates[next] if next < gates.size() else line
	var near := 1.0 - clampf(car.position.distance_to(target.position) / (maxf(1.0, target.width) * 4.0), 0.0, 1.0)
	return lap_of(car) * (gates.size() + 1.0) + next + near * 0.99

## The cars, the first first.
func order() -> Array[RpgCar]:
	return _order.duplicate()

## The place of `car`, 1 for the first.
func place_of(car: RpgCar) -> int:
	return _order.find(car) + 1

func _rank() -> void:
	var before := _order.duplicate()
	var values := {}
	for car in cars:
		# a car that has finished is ahead of every car that has not, the earlier the further
		values[car.get_instance_id()] = 1000000.0 - RpgUtil.to_float(_done[car.get_instance_id()]) if has_finished(car) else progress(car)
	_order.sort_custom(func(a: RpgCar, b: RpgCar) -> bool:
		return RpgUtil.to_float(values[a.get_instance_id()]) > RpgUtil.to_float(values[b.get_instance_id()]))
	if _order != before:
		positions_changed.emit()

## The standings: for every car its `place`, whether it is the `player`, whether it `finished`
## and its `time_s` (0 for a car that did not).
func standings() -> Array:
	var out: Array = []
	for car in _order:
		out.append({
			"car": car,
			"place": out.size() + 1,
			"player": car == player,
			"finished": has_finished(car),
			"time_s": RpgUtil.to_float(_done.get(car.get_instance_id(), 0.0)),
			"lap": lap_of(car),
		})
	return out

## Takes the rivals off the track (a test of the player's car alone), or puts them back.
func park_rivals(parked: bool) -> void:
	_parked = parked
	for car in cars:
		if car == player:
			continue
		car.visible = not parked
		car.set_collision_layer_value(2, not parked)
		car.set_collision_mask_value(1, not parked)
		car.set_collision_mask_value(2, not parked)
		if parked:
			car.engine_on = false
			car.position = Vector2(-10000.0, -10000.0 - 100.0 * cars.find(car))
		elif phase == Phase.RUNNING:
			car.engine_on = true

func _active(car: RpgCar) -> bool:
	return car == player or not _parked

func advance(delta: float) -> void:
	if phase == Phase.IDLE or phase == Phase.FINISHED:
		return
	time_s += delta
	if phase == Phase.COUNTDOWN:
		var left := ceili(countdown_left())
		if left != _counted:
			_counted = left
			counted.emit(left)
			_play(countdown_sound)
		if time_s < countdown_s:
			return
		phase = Phase.RUNNING
		time_s = 0.0
		for car in cars:
			car.engine_on = _active(car)
			_last[car.get_instance_id()] = car.position
		started.emit()
		return
	for car in cars:
		if _active(car):
			_follow(car)
	_take_pickups(delta)
	_move_weapons(delta)
	_band()
	_rank()
	_check_wrong_way(delta)
	if player != null and has_finished(player):
		_finish()

## The checkpoints and the start line `car` went over since the last step.
func _follow(car: RpgCar) -> void:
	var id := car.get_instance_id()
	var from: Vector2 = _last[id]
	var to := car.position
	_last[id] = to
	if has_finished(car):
		return
	var next := RpgUtil.to_int(_next[id])
	if next < gates.size():
		if gates[next].crossed(from, to):
			_next[id] = next + 1
		return
	if line.crossed(from, to):  # every checkpoint was passed: the line counts
		var lap := RpgUtil.to_int(_lap[id]) + 1
		_lap[id] = lap
		_next[id] = 0
		if lap > 1:
			lap_done.emit(car, lap - 1)
			if car == player:
				_play(lap_sound)
		if lap > laps:
			_done[id] = time_s  # a rival that has finished drives on: it does not stand in the way

func _take_pickups(delta: float) -> void:
	for pickup in pickups:
		pickup.advance(delta)
		if not pickup.active:
			continue
		for car in cars:
			if not _active(car) or not pickup.reaches(car.position):
				continue
			if pickup.is_part() and car != player:
				continue
			if not give(car, pickup.kind):
				continue
			pickup.take()
			pickup_taken.emit(car, pickup.kind)
			if car == player:
				_play(pickup_sound)
			break

## Gives `car` what a pickup of `kind` holds. False when the car cannot take it now (it has
## all the boosts it can carry).
func give(car: RpgCar, kind: String) -> bool:
	match kind:
		"boost":
			return car.add_boost()
		"missile", "bomb":
			car.weapon = kind
		"shield":
			car.shielded = true
		_:
			if not RpgRacePickup.PARTS.has(kind):
				return false
			part_taken.emit(kind)
	return true

func _on_weapon_fired(kind: String, car: RpgCar) -> void:
	var made := RpgRaceWeapon.fired(car, kind, car.tile_size)
	weapons.append(made)
	var holder := get_parent()
	if holder != null:
		holder.add_child(made)

func _move_weapons(delta: float) -> void:
	var targets: Array = []
	for car in cars:
		if _active(car):
			targets.append(car)
	for weapon in weapons:
		if is_instance_valid(weapon):
			weapon.advance(delta, targets)
			if weapon.done:
				weapon.queue_free()
	weapons = weapons.filter(func(w: RpgRaceWeapon) -> bool: return is_instance_valid(w) and not w.done)

## A rival far ahead of the player gives a little less pedal.
func _band() -> void:
	if player == null:
		return
	var mine := progress(player)
	for car in cars:
		var driver := car.get_node_or_null("Input") as RpgRival
		if driver == null:
			continue
		var lead := progress(car) - mine
		driver.pace = 1.0 - clampf((lead - BAND_FROM) / 6.0, 0.0, 1.0) * BAND_MOST if rubber_band else 1.0

## The way the track goes where `point` is: along its waypoints.
func way_at(point: Vector2) -> Vector2:
	if route.size() < 3:
		return Vector2.ZERO
	var nearest := 0
	var best := INF
	for i in route.size():
		var d := route[i].distance_squared_to(point)
		if d < best:
			best = d
			nearest = i
	return (route[(nearest + 1) % route.size()] - route[posmod(nearest - 1, route.size())]).normalized()

func _check_wrong_way(delta: float) -> void:
	if player == null:
		return
	var moving := player.velocity
	var against := moving.length() > player.tile_size * 2.0 and moving.normalized().dot(way_at(player.position)) < -0.5
	_wrong_s = _wrong_s + delta if against else 0.0
	var wrong := _wrong_s >= WRONG_WAY_S
	if wrong != wrong_way:
		wrong_way = wrong
		wrong_way_changed.emit(wrong)

func _finish() -> void:
	phase = Phase.FINISHED
	_rank()
	for car in cars:
		car.engine_on = false
	if wrong_way:
		wrong_way = false
		wrong_way_changed.emit(false)
	finished.emit(standings())

func _play(slot: StringName) -> void:
	var router := RpgUtil.router()
	var audio: Node = router.audio if router != null else null
	if audio != null and audio.has_method("play"):
		audio.call("play", slot)
