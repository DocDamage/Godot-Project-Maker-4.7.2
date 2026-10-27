class_name RpgSchedule
extends Node
## Where a person is at which time of the day (T17.09). A child `Schedule` of an NPC: the NPC
## finds it with `RpgNpc.schedule()`, and an NPC without one stands where its map put it, as
## every NPC did before. It does nothing in a game without a calendar (`RpgCalendar.current()`
## is null) and nothing while `entries` is empty.
##
## An entry is a Dictionary:
##   hour     from which hour of the day it holds (6 to 23, then 0 and 1 of the night: a day
##            runs from 6:00 to 2:00)
##   days     the days of the week it holds on (0 to 6, `RpgCalendar.weekday()`); none: every day
##   weather  the weather it holds in ("rain"); "": whatever the weather
##   map      the id of the map (`RpgMapRoot.map_id`); "": the map the NPC is on
##   place    the name of a marker of that map (`make_place`), or instead of it
##   cell     a cell of that map, [x, y]
##   facing   optional: where the NPC looks once it is there
##
## `resolve` gives the entry in force: of the entries of the day and the weather, the last whose
## hour has come; an entry that names a weather wins over one that names none. Before the first
## hour of the day the last entry of the day holds (where the person spent the night).
##
## Nobody is simulated off screen. When a map is entered each of its NPCs is put where the
## calendar says it is now, and one whose place is on another map is away: hidden, not in the
## way and not talkable. While a map is shown and an hour passes, an NPC whose place changed
## walks there along the map's navigation (`NavigationServer2D.map_get_path`, which the TileSet's
## navigation layer feeds when `features.navigation` is on); one whose place is now on another
## map walks to the nearest door (RpgDoor) and is away from there, and one that comes back
## appears at the door nearest to its place. On a map without navigation, or when no path leads
## there, the NPC fades out, is moved and fades in again (`fade_s`; 0 moves it at once).
##
## **Making way** (1.5.0, T18.07). While it walks, the NPC looks a short way ahead along its path
## with the shape of its own body (`blocker`): the player or another person standing there
## (collision layers 2 and 4) makes it slow down and step to the side that is free (`SLOW`,
## `free_side`), back onto its way once the way ahead is clear. Where there is no room at either
## side it waits, facing them; after `WAIT_S` it asks for a new way as soon as they move. The
## time it may take to arrive (after which it is put at its place) counts only the time it was
## free to walk, so a player standing in a doorway does not make it jump. It never walks into
## a body: a person's own collision mask has only the world, so the look ahead is what keeps it
## off.
##
## **A day that is not like the others** (T17.25: a festival of a farm) does not change the
## entries: whoever knows of it sets `RpgSchedule.override`, and the entry it gives for a person
## at an hour wins over everything the person's own entries say, whatever the weather. `pick`
## and `resolve` do not ask it: they say what the entries say. `entry_in_force` does.

## The NPC stands at its place again (after a walk or a move).
signal arrived
## The NPC left for another map.
signal left

const NODE_NAME := "Schedule"
## The group of the markers a schedule names (`make_place`).
const PLACE_GROUP := &"rpg_place"
## The group of the schedules at work, for `set_weather`.
const GROUP := &"rpg_schedules"
## The first hour of a day: an hour below it belongs to the night of the day before.
const DAY_FIRST_HOUR := 6
const ARRIVE_PX := 2.0
## How far from a place the end of a path may be and still count as leading there.
const REACH_PX := 12.0
## Making way (T18.07): how far ahead it looks, how far it may step aside in one go, how much it
## slows while it does, how long it waits before it asks for a new way, and whom it makes way
## for (the collision layers of the player and of people).
const LOOK_AHEAD_PX := 10.0
const SIDE_PX := 6.0
const SLOW := 0.5
const WAIT_S := 1.5
## How long it keeps to the side it chose once the way ahead is clear again (it does not dither).
const KEEP_SIDE_S := 0.75
const MAKE_WAY_MASK := 2 | 8

@export var entries: Array[Dictionary] = []
## Whose schedule this is: the id of a person. A schedule without entries takes those `source`
## has for this id (for the NPC's `entity_id` when this is empty).
@export var person: String = ""
## The walking speed in px a second.
@export var speed: float = 48.0
## The seconds of the fade out and of the fade in of an NPC that cannot walk to its place.
@export var fade_s: float = 0.25

var actor: RpgActor = null

## Who knows the entries of a schedule that has none of its own: `func(person: String) -> Array`.
## A mode sets it (the farm gives the schedules of game/data/people.json, so they can be edited
## there); nobody else does, and then a schedule without entries does nothing.
static var source: Callable = Callable()
## Who can put a person somewhere else for a day: `func(person: String, hour: int) ->
## Dictionary`, an entry (as above) that is in force at that hour of today whatever the
## person's own entries say, or {} for an hour like any other. Nobody sets it but a mode that
## has such days (the farm's events), and then every schedule goes by its entries alone.
static var override: Callable = Callable()

static var _weather := ""

var _map: RpgMapRoot = null
var _entry: Dictionary = {}  # the entry the NPC was last sent to
var _away := false
var _layer := 0  # the NPC's collision layer, kept while it is away
var _path: PackedVector2Array = PackedVector2Array()
var _path_at := 0
var _target := Vector2.ZERO
var _leaving := false
var _walk_left := 0.0
var _speed_before := -1.0
var _tween: Tween = null
var _blocked_s := 0.0  # how long the way ahead has been taken (T18.07)
var _side := Vector2.ZERO  # the side it is stepping to, or none
var _side_s := 0.0  # how long since it last stepped aside: the side is kept for a while
var _waited_at := Vector2.INF  # where the one it waits for stood when it began to wait

# ------------------------------------------------------------------ the entry in force

## The hour as the day counts it: 6 to 25 (0:00 and 1:00 of the night are 24 and 25).
static func day_hour(hour: int) -> int:
	return hour + 24 if hour < DAY_FIRST_HOUR else hour

## The entry of `list` in force at `hour` (what a clock shows) on `weekday` in `weather_now`,
## or {} when no entry is of that day and weather.
static func pick(list: Array[Dictionary], hour: int, weekday: int, weather_now: String) -> Dictionary:
	var now := day_hour(hour)
	var come: Dictionary = {}
	var come_key := -1
	var latest: Dictionary = {}
	var latest_key := -1
	for entry in list:
		var days := RpgUtil.to_array(entry.get("days", []))
		if not days.is_empty() and not _has_day(days, weekday):
			continue
		var wanted := RpgUtil.to_str(entry.get("weather", ""))
		if wanted != "" and wanted != weather_now:
			continue
		var from := day_hour(RpgUtil.to_int(entry.get("hour", DAY_FIRST_HOUR), DAY_FIRST_HOUR))
		# a weather entry wins over a plain one, then the later hour, then the later entry
		var key := (100 if wanted != "" else 0) + from
		if from <= now:
			if key >= come_key:
				come = entry
				come_key = key
		elif key >= latest_key:
			latest = entry
			latest_key = key
	if not come.is_empty():
		return come
	return latest

static func _has_day(days: Array, weekday: int) -> bool:
	for day: Variant in days:
		if RpgUtil.to_int(day, -1) == weekday:
			return true
	return false

## The entry in force at `hour` on `weekday` in `weather_now`.
func resolve(hour: int, weekday: int, weather_now: String = "") -> Dictionary:
	return pick(entries, hour, weekday, weather_now)

## The entry in force now by the calendar and the weather of the day; {} without a calendar.
func entry_in_force() -> Dictionary:
	var calendar := RpgCalendar.current()
	if calendar == null:
		return {}
	var hour := calendar.clock()[0]
	if override.is_valid():
		var forced := RpgUtil.to_dict(override.call(person_id(), hour))
		if not forced.is_empty():
			return forced
	return resolve(hour, calendar.weekday(), _weather)

# ------------------------------------------------------------------ the weather

## The weather of the day every schedule goes by ("" in a game without weather).
static func weather() -> String:
	return _weather

## Tells every schedule the weather of the day (the weather itself is T17.11): the NPCs of the
## map that is shown go where they are in that weather.
static func set_weather(value: String) -> void:
	if value == _weather:
		return
	_weather = value
	var tree := RpgUtil.tree()
	if tree == null:
		return
	for node in tree.get_nodes_in_group(GROUP):
		var schedule := node as RpgSchedule
		if schedule != null:
			schedule.update()

# ------------------------------------------------------------------ places

## A marker a schedule can name: a Marker2D with this name in the group of the places (kept in
## a saved scene). A recipe adds it to a map and sets its position.
static func make_place(place: String) -> Marker2D:
	var marker := Marker2D.new()
	marker.name = place
	marker.set_meta(&"place", place)
	marker.add_to_group(PLACE_GROUP, true)
	return marker

## The marker `place` of a map, or null.
static func find_place(map: Node, place: String) -> Node2D:
	if map == null or place == "":
		return null
	for node in map.find_children("*", "Node2D", true, false):
		if not node.is_in_group(PLACE_GROUP):
			continue
		var named := RpgUtil.to_str(node.get_meta(&"place")) if node.has_meta(&"place") else String(node.name)
		if named == place:
			return node as Node2D
	return null

## The middle of a cell of a map: by its first tile layer, else in tiles of 16 px.
static func cell_position(map: Node2D, cell: Vector2i) -> Vector2:
	for node in map.find_children("*", "TileMapLayer", true, false):
		var layer := node as TileMapLayer
		if layer.tile_set != null:
			return RpgUtil.world_position(layer) + layer.map_to_local(cell)
	return RpgUtil.world_position(map) + (Vector2(cell) + Vector2(0.5, 0.5)) * 16.0

## True when an entry's place is on the map the NPC is on.
func here(entry: Dictionary) -> bool:
	var map_id := RpgUtil.to_str(entry.get("map", ""))
	return map_id == "" or (_map != null and String(_map.map_id) == map_id)

## Where the place of an entry is on this map, or Vector2.INF when the map has no such place.
func place_position(entry: Dictionary) -> Vector2:
	if _map == null:
		return Vector2.INF
	var raw: Variant = entry.get("cell")
	if raw is Vector2i:
		var as_cell: Vector2i = raw
		return cell_position(_map, as_cell)
	var cell := RpgUtil.to_array(raw)
	if cell.size() == 2:
		return cell_position(_map, Vector2i(RpgUtil.to_int(cell[0]), RpgUtil.to_int(cell[1])))
	var marker := find_place(_map, RpgUtil.to_str(entry.get("place", "")))
	return RpgUtil.world_position(marker) if marker != null else Vector2.INF

## The door of the map nearest to `from`, or null on a map without doors.
func nearest_door(from: Vector2) -> RpgDoor:
	var best: RpgDoor = null
	var best_d := INF
	if _map == null:
		return null
	for node in _map.find_children("*", "Area2D", true, false):
		var door := node as RpgDoor
		if door == null:
			continue
		var d := from.distance_squared_to(RpgUtil.world_position(door))
		if d < best_d:
			best_d = d
			best = door
	return best

# ------------------------------------------------------------------ at work

func _ready() -> void:
	setup()

## Finds the NPC, its map and the calendar, and puts the NPC where it is now (`_ready` calls
## it; a test that keeps its nodes out of the tree calls it itself).
func setup() -> void:
	set_physics_process(false)
	actor = get_parent() as RpgActor
	_map = _map_of(actor)
	if entries.is_empty():
		_take_entries()
	if not at_work():
		return
	add_to_group(GROUP)
	var calendar := RpgCalendar.current()
	if not calendar.hour_passed.is_connected(_on_hour):
		calendar.hour_passed.connect(_on_hour)
	var bus := RpgUtil.events()
	if bus != null and not bus.map_entered.is_connected(_on_map_entered):
		bus.map_entered.connect(_on_map_entered)
	place_now()

## The id of the person: `person`, else the `entity_id` of the NPC.
func person_id() -> String:
	if person != "" or actor == null:
		return person
	return RpgUtil.to_str(actor.get(&"entity_id")) if &"entity_id" in actor else ""

func _take_entries() -> void:
	var id := person_id()
	if id == "" or not source.is_valid():
		return
	for raw: Variant in RpgUtil.to_array(source.call(id)):
		if raw is Dictionary:
			entries.append(RpgUtil.to_dict(raw))

## False for a schedule that does nothing: no calendar, no entries or no NPC to move.
func at_work() -> bool:
	return actor != null and not entries.is_empty() and RpgCalendar.current() != null

## True while the NPC is on another map: hidden and not talkable.
func away() -> bool:
	return _away

## True while the NPC walks to its place or to a door.
func walking() -> bool:
	return not _path.is_empty()

static func _map_of(node: Node) -> RpgMapRoot:
	var at := node
	while at != null:
		if at is RpgMapRoot:
			return at as RpgMapRoot
		at = at.get_parent()
	return null

## Puts the NPC where the calendar says it is now, without a walk: at its place, or away. What
## happens when its map is entered.
func place_now() -> void:
	if not at_work():
		return
	_stop()
	_entry = entry_in_force()
	if _entry.is_empty():
		return
	if not here(_entry):
		_set_away(true)
		return
	_set_away(false)
	var at := place_position(_entry)
	if at.is_finite():
		_put(at)
		_face()
	else:
		_no_place()

## Sends the NPC where it is now when that changed since it was last sent: a walk, a way out or
## a way in. What happens when an hour passes or the weather turns while its map is shown.
func update() -> void:
	if not at_work() or not _shown():
		return
	var next := entry_in_force()
	if next.is_empty() or next == _entry:
		return
	_entry = next
	_stop()
	if not here(next):
		if _away:
			return
		var out := nearest_door(RpgUtil.world_position(actor))
		if out == null:
			_move(Vector2.ZERO, true)
		else:
			_go(RpgUtil.world_position(out), true)
		return
	var at := place_position(next)
	if not at.is_finite():
		_no_place()
		return
	if _away:
		_set_away(false)
		var door := nearest_door(at)
		if door == null:
			_put(at)
			_face()
			arrived.emit()
			return
		_put(RpgUtil.world_position(door))
	_go(at, false)

func _on_hour(_hour: int) -> void:
	update()

func _on_map_entered(_map_id: StringName) -> void:
	if _shown():
		place_now()

func _shown() -> bool:
	var router := RpgUtil.router()
	return router == null or router.current_map == null or router.current_map == _map

func _no_place() -> void:
	push_warning("[RPG-WORLD] %s: the map has no place for the schedule entry %s" % [actor.name, _entry])

# ------------------------------------------------------------------ getting there

## The way from the NPC to `target` on the map's navigation; empty when the map has none, the
## NPC cannot walk or the way does not lead there.
func path_to(target: Vector2) -> PackedVector2Array:
	var none := PackedVector2Array()
	if not actor.is_inside_tree() or actor.component("Movement") == null:
		return none
	var world := actor.get_world_2d()
	if world == null:
		return none
	# a map that was never synchronised (no physics frame yet) cannot be asked: it logs an error
	if NavigationServer2D.map_get_iteration_id(world.navigation_map) == 0:
		return none
	var path := NavigationServer2D.map_get_path(world.navigation_map, actor.global_position, target, true)
	if path.is_empty() or path[path.size() - 1].distance_to(target) > REACH_PX:
		return none
	return path

func _go(target: Vector2, leaving: bool) -> void:
	var path := path_to(target)
	if path.is_empty():
		_move(target, leaving)
		return
	_path = path
	_path_at = 0
	_target = target
	_leaving = leaving
	var length := 0.0
	for i in range(1, path.size()):
		length += path[i - 1].distance_to(path[i])
	# twice the time the way takes: an NPC that is held up is put there in the end
	_walk_left = length / maxf(speed, 1.0) * 2.0 + 2.0
	var movement := actor.component("Movement") as RpgMovement
	_speed_before = movement.speed
	movement.speed = speed
	set_physics_process(true)

func _physics_process(delta: float) -> void:
	if _path.is_empty():
		set_physics_process(false)
		return
	var calendar := RpgCalendar.current()
	if calendar != null and calendar.stands_still():
		actor.move_dir(Vector2.ZERO)  # somebody talks to it, or a cutscene plays
		return
	var to := _path[_path_at] - actor.global_position
	while to.length() <= ARRIVE_PX and _path_at < _path.size() - 1:
		_path_at += 1
		to = _path[_path_at] - actor.global_position
	if to.length() <= ARRIVE_PX or _walk_left <= 0.0:
		var target := _target
		var leaving := _leaving
		_stop()
		_land(target, leaving)
		return
	var dir := to.normalized()
	var ahead := blocker(dir, minf(LOOK_AHEAD_PX, to.length()))
	if ahead == null:
		_walk_left -= delta  # only the time it was free to walk counts
		_blocked_s = 0.0
		_side_s += delta
		if _side_s >= KEEP_SIDE_S:
			_side = Vector2.ZERO
		_waited_at = Vector2.INF
		_set_pace(1.0)
		actor.move_dir(dir)
		return
	_make_way(dir, ahead, delta)

## The player or the person whose body is `ahead` px along `dir` (with the shape of this NPC's
## body, on the layers of MAKE_WAY_MASK; `ignore` is not counted), or null when the way is free.
func blocker(dir: Vector2, ahead: float = LOOK_AHEAD_PX, ignore: Node2D = null) -> Node2D:
	var body := _body_shape()
	if body == null or not actor.is_inside_tree() or body.shape == null:
		return null
	var query := PhysicsShapeQueryParameters2D.new()
	query.shape = body.shape
	query.transform = body.global_transform.translated(dir * ahead)
	query.collision_mask = MAKE_WAY_MASK
	query.exclude = [actor.get_rid()] if ignore == null or not (ignore is CollisionObject2D) else [actor.get_rid(), (ignore as CollisionObject2D).get_rid()]
	for hit: Dictionary in actor.get_world_2d().direct_space_state.intersect_shape(query, 8):
		var found: Object = hit.get("collider")
		var other := found as Node2D
		if other != null and other != actor and other.visible:
			return other
	return null

func _body_shape() -> CollisionShape2D:
	for child in actor.get_children():
		if child is CollisionShape2D and not (child as CollisionShape2D).disabled:
			return child as CollisionShape2D
	return null

## The side (a unit vector across `dir`) it can step to round `other`: no other body there and
## no wall in the way; the side away from `other` first. Zero when there is no room on either.
func free_side(dir: Vector2, other: Node2D) -> Vector2:
	var across := dir.orthogonal()
	if across.dot(actor.global_position - other.global_position) < 0.0:
		across = -across
	for side: Vector2 in [across, -across]:
		if blocker(side, SIDE_PX, other) == null and not actor.test_move(actor.global_transform, side * SIDE_PX):
			return side
	return Vector2.ZERO

## The way ahead is taken by `other`: slow down and step aside, or wait facing them, and after
## WAIT_S ask for a new way once they have moved.
func _make_way(dir: Vector2, other: Node2D, delta: float) -> void:
	_blocked_s += delta
	_side_s = 0.0
	# a point of the way that the other stands on is passed by: the next one is aimed at
	var body := _body_shape()
	var reach := (body.shape.get_rect().size.length() if body != null and body.shape != null else 12.0) + ARRIVE_PX
	while _path_at < _path.size() - 1 and _path[_path_at].distance_to(other.global_position) < reach:
		_path_at += 1
	if _side != Vector2.ZERO and absf(_side.dot(dir)) > 0.5:
		_side = Vector2.ZERO  # the way turned: choose again
	if _side == Vector2.ZERO or blocker(_side, SIDE_PX, other) != null or actor.test_move(actor.global_transform, _side * 2.0):
		var kept := _side
		_side = free_side(dir, other)
		if kept != Vector2.ZERO and _side != Vector2.ZERO and _side.dot(kept) < 0.0 and blocker(kept, SIDE_PX, other) == null and not actor.test_move(actor.global_transform, kept * 2.0):
			_side = kept
	if _side != Vector2.ZERO:
		_set_pace(SLOW)
		actor.move_dir(_side)
		return
	actor.move_dir(Vector2.ZERO)
	actor.set_facing(RpgAnimationDriver.dir_to_facing(other.global_position - actor.global_position))
	if _blocked_s < WAIT_S:
		return
	if _waited_at == Vector2.INF:
		_waited_at = other.global_position
	elif other.global_position.distance_to(_waited_at) > ARRIVE_PX * 2.0:
		var again := path_to(_target)  # they moved: a new way, from here
		if not again.is_empty():
			_path = again
			_path_at = 0
		_blocked_s = 0.0
		_waited_at = Vector2.INF

func _set_pace(share: float) -> void:
	var movement := actor.component("Movement") as RpgMovement
	if movement != null:
		movement.speed = speed * share

## True while the way ahead is taken and it is waiting (not stepping aside).
func waiting() -> bool:
	return not _path.is_empty() and _blocked_s > 0.0 and _side == Vector2.ZERO

## Ends a walk or a fade where it is.
func _stop() -> void:
	if _tween != null:
		_tween.kill()
		_tween = null
		actor.modulate.a = 1.0
	if _path.is_empty():
		return
	_path = PackedVector2Array()
	_blocked_s = 0.0
	_side = Vector2.ZERO
	_side_s = 0.0
	_waited_at = Vector2.INF
	actor.move_dir(Vector2.ZERO)
	var movement := actor.component("Movement") as RpgMovement
	if movement != null and _speed_before >= 0.0:
		movement.speed = _speed_before
	_speed_before = -1.0
	set_physics_process(false)

## Without a way to walk: fades the NPC out, moves it (or lets it be away) and fades it in.
func _move(target: Vector2, leaving: bool) -> void:
	if fade_s <= 0.0 or not actor.is_inside_tree():
		_land(target, leaving)
		return
	_tween = actor.create_tween()
	_tween.tween_property(actor, "modulate:a", 0.0, fade_s)
	_tween.tween_callback(_land.bind(target, leaving))
	_tween.tween_property(actor, "modulate:a", 1.0, fade_s)

func _land(target: Vector2, leaving: bool) -> void:
	if leaving:
		_set_away(true)
		left.emit()
		return
	_put(target)
	_face()
	arrived.emit()

func _put(at: Vector2) -> void:
	if actor.is_inside_tree():
		actor.global_position = at
		return
	var parent := actor.get_parent() as Node2D
	actor.position = at - (RpgUtil.world_position(parent) if parent != null else Vector2.ZERO)

func _face() -> void:
	var facing := RpgUtil.to_str(_entry.get("facing", ""))
	if facing != "":
		actor.set_facing(facing)

func _set_away(on: bool) -> void:
	if on == _away:
		return
	_away = on
	if on:
		_layer = actor.collision_layer
		actor.collision_layer = 0
		actor.visible = false
		actor.move_dir(Vector2.ZERO)
	else:
		actor.collision_layer = _layer
		actor.visible = true
