extends RefCounted
## T17.09: schedules. The entry in force for an hour, a day and a weather; an NPC that is put at
## its place when its map is entered, is away when its place is on another map, and goes where
## it is when the hour changes; and NPCs without a schedule, which are what they were.

const Fixtures := preload("../lib/fixtures.gd")
const ActorBuild := preload("res://builder/lib/actor_build.gd")

const TILE := 16
const HOME := Vector2(24, 24)
const SQUARE := Vector2(104, 88)
const POND := Vector2(200, 120)
const SHOP := Vector2(168, 24)
const DOOR := Vector2(104, 152)
const START := Vector2(56, 56)

## A day of somebody who works in the village: at home early and late, on the square by day, at
## the pond on two afternoons, at home when it rains, and in the inn (another map) at night.
const DAY: Array[Dictionary] = [
	{"hour": 6, "map": "village", "place": "home"},
	{"hour": 9, "map": "village", "place": "square", "facing": "left"},
	{"hour": 14, "days": [2, 5], "map": "village", "place": "pond"},
	{"hour": 18, "map": "village", "place": "home"},
	{"hour": 22, "map": "inn", "place": "bar"},
	{"hour": 9, "weather": "rain", "map": "village", "place": "home"},
]

var _made: Array[Node] = []

## A village with the markers a schedule names and one door.
func _village(map_id: StringName = &"village") -> RpgMapRoot:
	var map := RpgMapRoot.new()
	map.name = "Village"
	map.map_id = map_id
	var places := Node2D.new()
	places.name = "Places"
	map.add_child(places)
	var spots := {"home": HOME, "square": SQUARE, "pond": POND, "shop": SHOP}
	for place: String in spots:
		var marker := RpgSchedule.make_place(place)
		var at: Vector2 = spots[place]
		marker.position = at
		places.add_child(marker)
	var door := RpgDoor.new()
	door.name = "Door"
	door.position = DOOR
	map.add_child(door)
	var entities := Node2D.new()
	entities.name = "Entities"
	map.add_child(entities)
	_made.append(map)
	return map

## An NPC on a map where its map put it (START), with a schedule of `entries` when there are any.
func _npc(map: RpgMapRoot, entries: Array[Dictionary], with_schedule: bool = true) -> RpgNpc:
	var npc := ActorBuild.build("npc", "Villager", null, Vector2i(16, 24), Vector2i(8, 23), TILE) as RpgNpc
	npc.entity_id = "anna"
	npc.position = START
	map.get_node("Entities").add_child(npc)
	if with_schedule:
		var schedule := RpgSchedule.new()
		schedule.name = RpgSchedule.NODE_NAME
		schedule.entries = entries.duplicate(true)
		schedule.fade_s = 0.0
		npc.add_child(schedule)
		schedule.setup()  # what `_ready` does in a tree
	return npc

func _calendar(hour: int = 6) -> RpgCalendar:
	Fixtures.install_state()
	var calendar := RpgCalendar.ensure()
	calendar.minute = hour * 60
	return calendar

func _clear() -> void:
	for node in _made:
		if is_instance_valid(node):
			if node.is_inside_tree():
				node.get_parent().remove_child(node)
			node.free()
	_made.clear()
	RpgSchedule.set_weather("")
	RpgSchedule.source = Callable()
	Fixtures.uninstall_state()

static func _place(entry: Dictionary) -> String:
	return "%s/%s" % [entry.get("map", ""), entry.get("place", "")]

# ---------------------------------------------------------------- the entry in force

func test_the_entry_in_force_is_the_last_whose_hour_has_come(t) -> void:
	var schedule := RpgSchedule.new()
	schedule.entries = DAY.duplicate(true)
	t.eq(_place(schedule.resolve(6, 0)), "village/home")
	t.eq(_place(schedule.resolve(8, 0)), "village/home", "8:00")
	t.eq(_place(schedule.resolve(9, 0)), "village/square", "the hour itself counts")
	t.eq(_place(schedule.resolve(12, 0)), "village/square", "12:00")
	t.eq(_place(schedule.resolve(20, 0)), "village/home", "20:00")
	t.eq(_place(schedule.resolve(23, 0)), "inn/bar")
	t.eq(_place(schedule.resolve(1, 0)), "inn/bar", "1:00 of the night is the same day")
	t.eq(RpgSchedule.day_hour(1), 25)
	t.eq(RpgSchedule.day_hour(6), 6)
	# the days of the week
	t.eq(_place(schedule.resolve(15, 0)), "village/square")
	t.eq(_place(schedule.resolve(15, 2)), "village/pond", "an afternoon at the pond")
	t.eq(_place(schedule.resolve(15, 5)), "village/pond")
	t.eq(_place(schedule.resolve(13, 2)), "village/square", "not before its hour")
	t.eq(_place(schedule.resolve(19, 2)), "village/home", "a later entry of every day takes over")
	# the weather: an entry that names it wins over the plain ones once its hour has come
	t.eq(_place(schedule.resolve(8, 0, "rain")), "village/home")
	t.eq(_place(schedule.resolve(12, 0, "rain")), "village/home", "indoors when it rains")
	t.eq(_place(schedule.resolve(15, 2, "rain")), "village/home", "no pond in the rain")
	t.eq(_place(schedule.resolve(23, 0, "rain")), "village/home", "it holds for the rest of the day")
	t.eq(_place(schedule.resolve(12, 0, "snow")), "village/square", "another weather is none of its")
	t.eq(schedule.resolve(12, 0, "rain"), RpgSchedule.pick(schedule.entries, 12, 0, "rain"))
	# before the first hour of the day: where the day ends
	var late: Array[Dictionary] = [{"hour": 10, "place": "square"}, {"hour": 20, "place": "home"}]
	t.eq(RpgSchedule.pick(late, 7, 0, "").get("place"), "home")
	# of two entries of one hour the later one
	var twice: Array[Dictionary] = [{"hour": 8, "place": "a"}, {"hour": 8, "place": "b"}]
	t.eq(RpgSchedule.pick(twice, 9, 0, "").get("place"), "b")
	# no entry of the day: nothing
	var monday: Array[Dictionary] = [{"hour": 8, "days": [1], "place": "a"}]
	t.eq(RpgSchedule.pick(monday, 9, 0, ""), {})
	t.eq(RpgSchedule.pick([] as Array[Dictionary], 9, 0, ""), {})
	schedule.free()

# ---------------------------------------------------------------- entering a map

func test_an_npc_is_at_its_place_at_8_12_and_20_and_on_a_rainy_day(t) -> void:
	var calendar := _calendar(8)
	var cases := [[8, "", HOME], [12, "", SQUARE], [20, "", HOME], [12, "rain", HOME], [8, "rain", HOME]]
	for case: Array in cases:
		var hour: int = case[0]
		var weather: String = case[1]
		var at: Vector2 = case[2]
		calendar.minute = hour * 60
		RpgSchedule.set_weather(weather)
		var npc := _npc(_village(), DAY)
		t.eq(npc.position, at, "%d:00 %s" % [hour, weather])
		t.ok(npc.visible and not npc.schedule().away())
		t.eq(npc.collision_layer, 8, "it is talkable: on the layer of the NPCs")
	# the weekday counts: the third day of a week is a pond day
	RpgSchedule.set_weather("")
	calendar.day = 3
	calendar.minute = 15 * 60
	t.eq(calendar.weekday(), 2)
	t.eq(_npc(_village(), DAY).position, POND)
	# an entry may look somewhere
	calendar.minute = 12 * 60
	t.eq(_npc(_village(), DAY).facing, "left")
	# a cell instead of a marker, and an entry without a map: the map the NPC is on
	var cells: Array[Dictionary] = [{"hour": 6, "cell": [5, 2]}]
	t.eq(_npc(_village(&"anywhere"), cells).position, Vector2(88, 40), "the middle of the cell (5, 2)")
	_clear()

func test_one_whose_place_is_on_another_map_is_not_on_this_one(t) -> void:
	var calendar := _calendar(23)
	var npc := _npc(_village(), DAY)
	var schedule := npc.schedule()
	t.ok(schedule.away(), "at 23:00 it is in the inn")
	t.ok(not npc.visible, "hidden")
	t.eq(npc.collision_layer, 0, "not in the way and not found by the player's interaction")
	var player := Node2D.new()
	player.position = START + Vector2(0, -40)
	npc.interact(player)
	t.eq(npc.facing, "down", "not talkable: it does not even turn")
	player.free()
	# the same person in the inn is there
	var inn := _village(&"inn")
	inn.get_node("Places").add_child(RpgSchedule.make_place("bar"))
	(inn.get_node("Places/bar") as Node2D).position = Vector2(40, 72)
	var there := _npc(inn, DAY)
	t.ok(there.visible and not there.schedule().away())
	t.eq(there.position, Vector2(40, 72))
	# and in the morning the one of the inn is away and the one of the village at home
	calendar.minute = 8 * 60
	there.schedule().place_now()
	schedule.place_now()
	t.ok(there.schedule().away() and not there.visible)
	t.ok(npc.visible and not schedule.away())
	t.eq(npc.collision_layer, 8, "its layer is back")
	t.eq(npc.position, HOME)
	_clear()

# ---------------------------------------------------------------- the hour changes

func test_the_hour_changing_moves_it(t) -> void:
	var calendar := _calendar(8)
	var npc := _npc(_village(), DAY)
	var schedule := npc.schedule()
	var log: Array[String] = []
	schedule.arrived.connect(func() -> void: log.append("arrived"))
	schedule.left.connect(func() -> void: log.append("left"))
	t.eq(npc.position, HOME)
	calendar.pass_minutes(59)
	t.eq(npc.position, HOME, "a minute before 9:00")
	calendar.pass_minutes(1)
	t.eq(npc.position, SQUARE, "9:00")
	t.eq(log, ["arrived"] as Array[String])
	calendar.pass_minutes(60 * 8)
	t.eq(npc.position, SQUARE, "an hour that changes nothing moves nobody")
	t.eq(log.size(), 1)
	calendar.pass_minutes(60)
	t.eq(npc.position, HOME, "18:00")
	# its place is on another map now: it leaves
	calendar.pass_minutes(60 * 4)
	t.ok(schedule.away() and not npc.visible, "22:00: gone to the inn")
	t.eq(log, ["arrived", "arrived", "left"] as Array[String])
	# the weather turning is a change too
	calendar.minute = 12 * 60
	schedule.place_now()
	t.eq(npc.position, SQUARE)
	RpgSchedule.set_weather("rain")
	schedule.update()  # what set_weather does for the schedules of a tree
	t.eq(npc.position, HOME, "it began to rain")
	# one that comes back from another map
	RpgSchedule.set_weather("")
	calendar.minute = 23 * 60
	schedule.place_now()
	t.ok(schedule.away())
	calendar.end_day()  # the morning: 6:00, no hour passed
	schedule.update()
	t.ok(not schedule.away() and npc.visible)
	t.eq(npc.position, HOME, "it came in by the door and went home")
	t.eq(schedule.nearest_door(HOME).position, DOOR)
	_clear()

func test_it_walks_there_on_the_maps_navigation(t) -> void:
	await Fixtures.tree().process_frame
	var calendar := _calendar(8)
	var map := _village()
	# ground of 16 by 12 cells, every tile with a navigation polygon (features.navigation)
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(TILE, TILE)
	tiles.add_navigation_layer()
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(Image.create_empty(TILE, TILE, false, Image.FORMAT_RGBA8))
	source.texture_region_size = Vector2i(TILE, TILE)
	tiles.add_source(source, 0)
	source.create_tile(Vector2i(0, 0))
	var polygon := NavigationPolygon.new()
	var half := TILE / 2.0
	polygon.vertices = PackedVector2Array([Vector2(-half, -half), Vector2(half, -half), Vector2(half, half), Vector2(-half, half)])
	polygon.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	source.get_tile_data(Vector2i(0, 0), 0).set_navigation_polygon(0, polygon)
	var ground := TileMapLayer.new()
	ground.name = "Ground"
	ground.tile_set = tiles
	for y in 12:
		for x in 16:
			ground.set_cell(Vector2i(x, y), 0, Vector2i(0, 0))
	map.add_child(ground)
	map.move_child(ground, 0)
	var npc := ActorBuild.build("npc", "Villager", null, Vector2i(16, 24), Vector2i(8, 23), TILE) as RpgNpc
	npc.position = START
	var schedule := RpgSchedule.new()
	schedule.name = RpgSchedule.NODE_NAME
	schedule.entries = DAY.duplicate(true)
	schedule.speed = 240.0
	npc.add_child(schedule)
	map.get_node("Entities").add_child(npc)
	Fixtures.tree().root.add_child(map)
	t.eq(npc.global_position, HOME, "entering the tree put it at home")
	t.ok(schedule.path_to(SQUARE).is_empty(), "before the navigation map is made there is no way (and no error)")
	for i in 8:  # the navigation map is made in a physics frame
		await Fixtures.tree().physics_frame
	t.ok(not schedule.path_to(SQUARE).is_empty(), "the map's navigation leads to the square")
	var done := [false]
	schedule.arrived.connect(func() -> void: done[0] = true)
	calendar.pass_minutes(60)
	t.ok(schedule.walking(), "9:00: it walks")
	t.ok(npc.global_position.distance_to(HOME) < 1.0, "and is not there at once")
	var between := false
	for i in 180:
		await Fixtures.tree().physics_frame
		var gone := npc.global_position.distance_to(HOME)
		var left := npc.global_position.distance_to(SQUARE)
		if gone > 16.0 and left > 16.0:
			between = true
		if done[0]:
			break
	t.ok(between, "it was seen on the way")
	t.ok(done[0] and not schedule.walking(), "it arrived")
	t.ok(npc.global_position.distance_to(SQUARE) <= 4.0, "at the square: %s" % npc.global_position)
	t.eq(npc.facing, "left", "and looks where the entry says")
	t.near((npc.component("Movement") as RpgMovement).speed, 80.0, 0.001, "its own speed is back")
	# to another map: it walks to the door and is gone
	var out := [false]
	schedule.left.connect(func() -> void: out[0] = true)
	calendar.minute = 21 * 60 + 59
	calendar.pass_minutes(1)
	t.ok(schedule.walking() and not schedule.away(), "22:00: on its way out")
	for i in 180:
		await Fixtures.tree().physics_frame
		if out[0]:
			break
	t.ok(out[0] and schedule.away() and not npc.visible, "gone through the door")
	t.ok(npc.global_position.distance_to(DOOR) <= 4.0)
	_clear()

func test_on_a_map_without_navigation_it_fades_and_is_moved(t) -> void:
	await Fixtures.tree().process_frame
	var calendar := _calendar(8)
	var map := _village()
	var npc := ActorBuild.build("npc", "Villager", null, Vector2i(16, 24), Vector2i(8, 23), TILE) as RpgNpc
	npc.position = START
	var schedule := RpgSchedule.new()
	schedule.name = RpgSchedule.NODE_NAME
	schedule.entries = DAY.duplicate(true)
	schedule.fade_s = 0.1
	npc.add_child(schedule)
	map.get_node("Entities").add_child(npc)
	Fixtures.tree().root.add_child(map)
	for i in 8:
		await Fixtures.tree().physics_frame
	t.eq(npc.global_position, HOME)
	t.ok(schedule.path_to(SQUARE).is_empty(), "this map has no navigation")
	calendar.pass_minutes(60)
	t.ok(not schedule.walking(), "9:00: no walk")
	t.eq(npc.global_position, HOME, "it fades out where it stands")
	var faded := false
	for i in 40:
		await Fixtures.tree().process_frame
		if npc.modulate.a < 0.9:
			faded = true
		if npc.global_position == SQUARE and npc.modulate.a >= 1.0:
			break
	t.ok(faded, "it was seen fading")
	t.eq(npc.global_position, SQUARE, "and is at the square")
	t.near(npc.modulate.a, 1.0, 0.001, "faded in again")
	# an hour that changes its place again while it fades: it is where it is now, not half gone
	calendar.minute = 17 * 60 + 59
	calendar.pass_minutes(1)
	await Fixtures.tree().process_frame
	calendar.minute = 21 * 60 + 59
	calendar.pass_minutes(1)
	for i in 40:
		await Fixtures.tree().process_frame
		if schedule.away():
			break
	t.ok(schedule.away() and not npc.visible, "22:00: gone, by the door it has no way to")
	for i in 15:
		await Fixtures.tree().process_frame
	t.near(npc.modulate.a, 1.0, 0.2, "and not left transparent")
	_clear()

# ---------------------------------------------------------------- nothing changes without one

func test_an_npc_without_a_schedule_behaves_as_before(t) -> void:
	var calendar := _calendar(8)
	var map := _village()
	var plain := _npc(map, [], false)
	t.ok(plain.schedule() == null)
	calendar.pass_minutes(60 * 6)
	t.eq(plain.position, START, "it stands where its map put it")
	t.ok(plain.visible)
	t.eq(plain.collision_layer, 8)
	var player := Node2D.new()
	player.position = START + Vector2(0, -40)
	plain.interact(player)
	t.eq(plain.facing, "up", "and turns to who talks to it")
	player.free()
	# a schedule without entries does nothing
	var empty := _npc(map, [])
	t.ok(not empty.schedule().at_work())
	calendar.pass_minutes(60)
	t.eq(empty.position, START)
	t.ok(not empty.schedule().is_in_group(RpgSchedule.GROUP))
	_clear()
	# and in a game without a calendar a schedule with entries does nothing either
	Fixtures.install_state()
	t.ok(RpgCalendar.current() == null)
	var npc := _npc(_village(), DAY)
	var schedule := npc.schedule()
	t.ok(not schedule.at_work())
	t.eq(npc.position, START)
	t.ok(npc.visible and not schedule.away())
	t.eq(schedule.entry_in_force(), {})
	schedule.place_now()
	schedule.update()
	t.eq(npc.position, START)
	t.ok(not schedule.is_physics_processing())
	_clear()

func test_a_schedule_without_entries_takes_those_of_its_person(t) -> void:
	_calendar(12)
	var asked: Array[String] = []
	RpgSchedule.source = func(person: String) -> Array:
		asked.append(person)
		return DAY if person == "anna" else []
	var npc := _npc(_village(), [])
	t.eq(asked, ["anna"] as Array[String], "by the NPC's entity id")
	t.eq(npc.schedule().entries.size(), DAY.size())
	t.eq(npc.position, SQUARE)
	var other := ActorBuild.build("npc", "Other", null, Vector2i(16, 24), Vector2i(8, 23), TILE) as RpgNpc
	other.entity_id = "village_npc_007"
	other.position = START
	(_made[0] as Node).get_node("Entities").add_child(other)
	var schedule := RpgSchedule.new()
	schedule.name = RpgSchedule.NODE_NAME
	schedule.person = "bert"
	other.add_child(schedule)
	schedule.setup()
	t.eq(asked, ["anna", "bert"] as Array[String], "or by the person the schedule names")
	t.ok(not schedule.at_work())
	t.eq(other.position, START, "nobody knows bert: he stays")
	_clear()

# ---------------------------------------------------------------- making way (T18.07)

## Ground with a navigation polygon on every cell of `cells`, walls (StaticBody2D, layer 1) as
## rectangles of `walls`, a villager walking from cell (1, 3) to cell (13, 3) at 9:00 and the
## player standing on its way at cell (7, 3).
func _way(t, cells: Array[Vector2i], walls: Array[Rect2]) -> Array:
	await Fixtures.tree().process_frame
	var calendar := _calendar(8)
	var map := _village()
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(TILE, TILE)
	tiles.add_navigation_layer()
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(Image.create_empty(TILE, TILE, false, Image.FORMAT_RGBA8))
	source.texture_region_size = Vector2i(TILE, TILE)
	tiles.add_source(source, 0)
	source.create_tile(Vector2i(0, 0))
	var polygon := NavigationPolygon.new()
	var half := TILE / 2.0
	polygon.vertices = PackedVector2Array([Vector2(-half, -half), Vector2(half, -half), Vector2(half, half), Vector2(-half, half)])
	polygon.add_polygon(PackedInt32Array([0, 1, 2, 3]))
	source.get_tile_data(Vector2i(0, 0), 0).set_navigation_polygon(0, polygon)
	var ground := TileMapLayer.new()
	ground.name = "Ground"
	ground.tile_set = tiles
	for cell in cells:
		ground.set_cell(cell, 0, Vector2i(0, 0))
	map.add_child(ground)
	map.move_child(ground, 0)
	for rect in walls:
		var wall := StaticBody2D.new()
		var shape := CollisionShape2D.new()
		var box := RectangleShape2D.new()
		box.size = rect.size
		shape.shape = box
		shape.position = rect.get_center()
		wall.add_child(shape)
		map.add_child(wall)
	var npc := ActorBuild.build("npc", "Villager", null, Vector2i(16, 24), Vector2i(8, 23), TILE) as RpgNpc
	var schedule := RpgSchedule.new()
	schedule.name = RpgSchedule.NODE_NAME
	var day: Array[Dictionary] = [{"hour": 6, "map": "village", "cell": [1, 3]}, {"hour": 9, "map": "village", "cell": [13, 3]}]
	schedule.entries = day
	schedule.speed = 60.0
	npc.add_child(schedule)
	map.get_node("Entities").add_child(npc)
	var player := ActorBuild.build("player", "Player", null, Vector2i(16, 24), Vector2i(8, 23), TILE) as RpgActor
	player.position = RpgSchedule.cell_position(map, Vector2i(7, 3))
	player.set_physics_process(false)
	var reads_input := player.find_child("PlayerInput", true, false)
	if reads_input != null:  # a test has no move actions: the player stands still
		reads_input.get_parent().remove_child(reads_input)
		reads_input.free()
	map.get_node("Entities").add_child(player)
	Fixtures.tree().root.add_child(map)
	for i in 8:
		await Fixtures.tree().physics_frame
	var done := [false]
	schedule.arrived.connect(func() -> void: done[0] = true)
	calendar.pass_minutes(60)
	t.ok(schedule.walking(), "9:00: it walks")
	return [schedule, npc, player, done]

## Frames until it arrived (or `frames` ran out); false when its body ever overlapped the player's.
func _walk(schedule: RpgSchedule, done: Array, frames: int) -> bool:
	var apart := true
	for i in frames:
		await Fixtures.tree().physics_frame
		if schedule.blocker(Vector2.RIGHT, 0.0) != null:
			apart = false
		if done[0]:
			break
	return apart

func test_a_villager_goes_round_the_player_where_there_is_room(t) -> void:
	var cells: Array[Vector2i] = []
	for y in 8:
		for x in 16:
			cells.append(Vector2i(x, y))
	var made: Array = await _way(t, cells, [] as Array[Rect2])
	var schedule: RpgSchedule = made[0]
	var npc: RpgNpc = made[1]
	var done: Array = made[3]
	var apart: bool = await _walk(schedule, done, 600)
	t.ok(done[0], "it arrived")
	t.ok(apart, "and never overlapped the player's body")
	t.ok(npc.global_position.distance_to(RpgSchedule.cell_position(npc.map_node(), Vector2i(13, 3))) <= 4.0, "at its place, walked: %s" % npc.global_position)
	_clear()

func test_a_villager_waits_where_there_is_no_room_and_arrives_once_the_player_steps_away(t) -> void:
	var cells: Array[Vector2i] = []
	for x in 16:
		cells.append(Vector2i(x, 3))
	# walls tight above and below the feet of whoever walks along row 3 (its middle is y = 56)
	var walls: Array[Rect2] = [Rect2(0, 0, 256, 49), Rect2(0, 58, 256, 60)]
	var made: Array = await _way(t, cells, walls)
	var schedule: RpgSchedule = made[0]
	var npc: RpgNpc = made[1]
	var player: RpgActor = made[2]
	var done: Array = made[3]
	# twice what the walk would take: its time runs only while it is free to walk
	var apart: bool = await _walk(schedule, done, 480)
	t.ok(not done[0], "it was not put at its place while the player stood in the way")
	t.ok(schedule.waiting(), "it waits")
	t.ok(apart, "without walking into the player")
	t.eq(npc.facing, "right", "facing the player")
	t.ok(npc.global_position.x < player.global_position.x, "on its side of the player")
	player.global_position = Vector2(300, 300)  # the player steps away
	apart = await _walk(schedule, done, 600)
	t.ok(done[0], "and it arrives once the player stepped away")
	t.ok(npc.global_position.distance_to(RpgSchedule.cell_position(npc.map_node(), Vector2i(13, 3))) <= 4.0, "at its place: %s" % npc.global_position)
	_clear()

func test_villagers_make_way_for_each_other(t) -> void:
	var cells: Array[Vector2i] = []
	for y in 8:
		for x in 16:
			cells.append(Vector2i(x, y))
	var made: Array = await _way(t, cells, [] as Array[Rect2])
	var schedule: RpgSchedule = made[0]
	var player: RpgActor = made[2]
	var done: Array = made[3]
	# another villager stands in the way instead of the player
	var other := ActorBuild.build("npc", "Other", null, Vector2i(16, 24), Vector2i(8, 23), TILE) as RpgNpc
	other.global_position = player.global_position
	player.global_position = Vector2(300, 300)
	player.get_parent().add_child(other)
	var apart: bool = await _walk(schedule, done, 600)
	t.ok(done[0] and apart, "it went round the other villager")
	_clear()
