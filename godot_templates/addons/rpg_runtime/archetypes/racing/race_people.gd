class_name RpgRacePeople
extends Node2D
## The people of a race (1.5.0, T18.19), with the racing option *Racers and spectators*: the
## drivers of the cars, standing beside them on the grid until the lights begin; a flag marshal
## at the start line, who waves the start and the last lap; spectators behind the barriers of
## the straights, who cheer (a bob of two steps); and, after the last race of a cup, the podium
## of its first three. Nobody of them blocks the track: their bodies are taken off every layer.
##
## Who drives which car is the build's choice (`generated/data/drivers.json`, by the seed:
## {"drivers": [{id, name, frames, portrait, colour}], "people": [frames, ...]}, the frames the
## SpriteFrames of a person): the packs' people, no one twice while there are enough, else a
## drawn figure in the colour of the car. The names are
## what RpgChampionship.driver_name says and the portraits what the results show beside them;
## a rival drives a little bolder or more careful by its driver (`skill_of`).
##
## The node is the child `People` of a track's scene, made by RpgRacingMode when the track is
## entered; its positions are of the plan, drawn through RpgRaceView on a track seen at an angle.

const NODE_NAME := "People"
const DATA_PATH := "res://generated/data/drivers.json"
const SPECTATORS_MOST := 12
const BOB_S := 0.25
const WAVE_S := 2.0
## How much bolder or more careful a driver is: at most this off the rival's skill.
const SKILL_SPREAD := 0.08
const STAND_IN := Color(0.85, 0.75, 0.6)

static var _data: Dictionary = {}
static var _data_path := ""
## Where the drivers are read from (a test points it at its own file).
static var data_path := DATA_PATH

var race: RpgRace = null
var drivers: Array[Node2D] = []
var marshal: Node2D = null
var spectators: Array[Node2D] = []
var podium: Array[Node2D] = []
var _bob := 0.0
var _up := false
var _wave := 0.0

# ------------------------------------------------------------------ the data

static func data() -> Dictionary:
	if _data_path != data_path:
		_data_path = data_path
		_data = {}
		if FileAccess.file_exists(data_path):
			_data = RpgUtil.to_dict(JSON.parse_string(FileAccess.get_file_as_string(data_path)))
	return _data

## The entry of a driver (`player`, `rival_1`, ...), or {}.
static func driver(id: String) -> Dictionary:
	for raw: Variant in RpgUtil.to_array(data().get("drivers", [])):
		var entry := RpgUtil.to_dict(raw)
		if RpgUtil.to_str(entry.get("id", "")) == id:
			return entry
	return {}

## The name of a driver, or "" when the race has no people (or the driver is the player).
static func name_of(id: String) -> String:
	return RpgUtil.to_str(driver(id).get("name", ""))

## The SpriteFrames of a person (a path of drivers.json), or null.
static func frames_at(path: String) -> SpriteFrames:
	return load(path) as SpriteFrames if path != "" and ResourceLoader.exists(path) else null

## The animation a person stands in: facing down when it has that, else its first.
static func standing(frames: SpriteFrames) -> StringName:
	for anim: StringName in [&"idle_down", &"idle", &"walk_down", &"default"]:
		if frames.has_animation(anim) and frames.get_frame_count(anim) > 0:
			return anim
	var names := frames.get_animation_names()
	return StringName(names[0]) if not names.is_empty() else &""

## The portrait of a driver: the pack's picture of its face when it has one, else the first
## standing frame of its scene, or null.
static func portrait_of(id: String) -> Texture2D:
	var entry := driver(id)
	var face := RpgUtil.to_dict(entry.get("portrait", {}))
	var path := RpgUtil.to_str(face.get("path", ""))
	if path != "" and ResourceLoader.exists(path):
		var sheet := load(path) as Texture2D
		var region := RpgUtil.to_array(face.get("region", []))
		if region.size() == 4:
			var part := AtlasTexture.new()
			part.atlas = sheet
			part.region = Rect2(RpgUtil.to_float(region[0]), RpgUtil.to_float(region[1]), RpgUtil.to_float(region[2]), RpgUtil.to_float(region[3]))
			return part
		return sheet
	var frames := frames_at(RpgUtil.to_str(entry.get("frames", "")))
	if frames == null:
		return null
	var anim := standing(frames)
	return frames.get_frame_texture(anim, 0) if anim != &"" else null

## How a rival drives with this driver: its skill a little up or down by the driver's name.
static func skill_of(base: float, id: String) -> float:
	var who := name_of(id)
	if who == "":
		return base
	var step := float(posmod(who.hash(), 17) - 8) / 8.0
	return clampf(base + step * SKILL_SPREAD, 0.3, 1.0)

# ------------------------------------------------------------------ on a track

## Makes the people of `the_race`, whose track is `track` (its entry of the list of stages):
## the drivers beside their cars, the marshal, the spectators. Nothing without the data (a race
## without the option).
func setup(the_race: RpgRace, track: Dictionary) -> void:
	race = the_race
	if data().is_empty() or race == null:
		return
	var tile := 16.0
	for car in race.cars:
		tile = car.tile_size
		var id := RpgChampionship.driver_of(car)
		var person := _person(RpgUtil.to_str(driver(id).get("frames", "")), _colour(id))
		person.name = "Driver_%s" % id
		var side := Vector2.from_angle(car.heading + PI * 0.5) * tile * 0.9
		_place(person, car.position + side)
		person.set_meta(&"driver", id)
		drivers.append(person)
		var rival := car.get_node_or_null("Input") as RpgRival
		if rival != null:
			rival.skill = skill_of(rival.skill, id)
	if race.line != null:
		marshal = _person(_pick_person(0), Color(0.95, 0.95, 0.95))
		marshal.name = "Marshal"
		_place(marshal, beside_line(tile, 0.0))
	var placed := 0
	for spot in spectator_spots(track, tile):
		if placed >= SPECTATORS_MOST:
			break
		var fan := _person(_pick_person(placed + 1), Color.from_hsv(float(placed) / SPECTATORS_MOST, 0.5, 0.9))
		fan.name = "Spectator%d" % (placed + 1)
		_place(fan, spot)
		spectators.append(fan)
		placed += 1
	if not race.counted.is_connected(_on_counted):
		race.counted.connect(_on_counted)
		race.started.connect(func() -> void: wave())
		race.lap_done.connect(_on_lap)

## A point beside the start line, past the end of it (`along`: tiles along the race's way).
func beside_line(tile: float, along: float) -> Vector2:
	var across := Vector2.from_angle(race.line.heading + PI * 0.5)
	return race.line.position + across * (race.line.width * 0.5 + tile) + Vector2.from_angle(race.line.heading) * along * tile

## The colour of a driver (its car's).
static func _colour(id: String) -> Color:
	var raw := RpgUtil.to_array(driver(id).get("colour", []))
	return Color(RpgUtil.to_float(raw[0]), RpgUtil.to_float(raw[1]), RpgUtil.to_float(raw[2])) if raw.size() >= 3 else STAND_IN

## Where spectators stand: on the cells of the long thin barriers of `track` (the walls along
## the straights), a few cells apart.
static func spectator_spots(track: Dictionary, tile: float) -> Array[Vector2]:
	var out: Array[Vector2] = []
	for raw: Variant in RpgUtil.to_array(track.get("barriers", [])):
		var rect := RpgUtil.to_array(raw)
		if rect.size() != 4:
			continue
		var x := RpgUtil.to_int(rect[0])
		var y := RpgUtil.to_int(rect[1])
		var w := RpgUtil.to_int(rect[2])
		var h := RpgUtil.to_int(rect[3])
		if maxi(w, h) < 6 or mini(w, h) > 1:
			continue  # a straight is a long thin barrier
		for i in range(2, maxi(w, h) - 2, 4):
			var cell := Vector2(x + (i if w >= h else 0), y + (i if h > w else 0))
			out.append((cell + Vector2(0.5, 0.5)) * tile)
	return out

## Somebody of the packs for the n-th place along the track, by turn ("" when none).
static func _pick_person(n: int) -> String:
	var people := RpgUtil.to_array(data().get("people", []))
	return RpgUtil.to_str(people[n % people.size()]) if not people.is_empty() else ""

## A person: an AnimatedSprite2D of `frames_path` standing, else a drawn figure in `colour`.
## Neither has a body: nothing bumps into them.
func _person(frames_path: String, colour: Color) -> Node2D:
	var node: Node2D = null
	var frames := frames_at(frames_path)
	if frames != null and standing(frames) != &"":
		var sprite := AnimatedSprite2D.new()
		sprite.sprite_frames = frames
		sprite.animation = standing(frames)
		var first := frames.get_frame_texture(sprite.animation, 0)
		sprite.offset = Vector2(0, -first.get_height() * 0.5) if first != null else Vector2.ZERO
		node = sprite
	else:
		node = Node2D.new()
		var body := Polygon2D.new()
		body.polygon = PackedVector2Array([Vector2(-3, 0), Vector2(3, 0), Vector2(3, -8), Vector2(-3, -8)])
		body.color = colour
		node.add_child(body)
		var head := Polygon2D.new()
		head.polygon = PackedVector2Array([Vector2(-2, -8), Vector2(2, -8), Vector2(2, -12), Vector2(-2, -12)])
		head.color = Color(0.95, 0.8, 0.65)
		node.add_child(head)
	add_child(node)
	return node

## Puts a person at a point of the plan, drawn where the view draws it.
func _place(person: Node2D, plan_point: Vector2) -> void:
	var seen := RpgRaceView.of(race) if race != null else null
	person.position = seen.to_screen(plan_point) if seen != null else plan_point
	person.set_meta(&"base", person.position)

# ------------------------------------------------------------------ what they do

## The count of the lights: the drivers stand at their cars at its first and get in when the
## lights begin (the next), every time the race counts down.
func _on_counted(left: int) -> void:
	for person in drivers:
		person.visible = left > 2

## The marshal waves (the start, the last lap).
func wave() -> void:
	_wave = WAVE_S

func _on_lap(car: RpgCar, lap: int) -> void:
	if car == race.player and lap == race.laps - 1:
		wave()

## True while the drivers stand beside their cars.
func drivers_standing() -> bool:
	return not drivers.is_empty() and drivers.all(func(person: Node2D) -> bool: return person.visible)

func _process(delta: float) -> void:
	_bob -= delta
	_wave = maxf(0.0, _wave - delta)
	if _bob > 0.0:
		return
	_bob = BOB_S * (0.5 if _wave > 0.0 else 1.0)
	_up = not _up
	for person: Node2D in spectators + podium:
		_step(person, 1.0)
	if marshal != null and _wave > 0.0:
		_step(marshal, 2.0)

func _step(person: Node2D, height: float) -> void:
	if not is_instance_valid(person):
		return
	var base: Vector2 = person.get_meta(&"base", person.position)
	person.position = base + (Vector2(0, -height) if _up else Vector2.ZERO)

## The podium after the last race of a cup: the three who finished first, second and third
## (driver ids, the first first), beside the start line, the first highest.
func show_podium(top: Array[String]) -> Array[Node2D]:
	for person in podium:
		person.queue_free()
	podium.clear()
	if race == null or race.line == null or data().is_empty():
		return podium
	var tile := race.player.tile_size if race.player != null else 16.0
	var heights: Array[float] = [tile * 0.6, tile * 0.3, 0.0]
	var steps: Array[float] = [0.0, -1.2, 1.2]
	for i in mini(3, top.size()):
		var person := _person(RpgUtil.to_str(driver(top[i]).get("frames", "")), _colour(top[i]))
		person.name = "Podium%d" % (i + 1)
		person.set_meta(&"driver", top[i])
		_place(person, beside_line(tile * 1.5, steps[i]))
		person.position.y -= heights[i]
		person.set_meta(&"base", person.position)
		podium.append(person)
	return podium
