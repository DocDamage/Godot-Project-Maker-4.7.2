extends RefCounted
## VAL-033: the room check (tools/room_check.gd) on rooms built from the plans rpggen makes, and on
## those rooms painted wrong by hand: rock over an exit, a ladder taken away, a platform under a
## ceiling, a save station inside rock or in the air.

const RoomTests := preload("test_rooms.gd")
const PlatformTests := preload("test_platform_actor.gd")
const RoomCheck := preload("res://addons/rpg_project_tools/tools/room_check.gd")
const RoomsRecipe := preload("res://builder/recipes/metroidvania/rooms_recipe.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")

const TILE := 16

func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree

func _kinds(issues: Array) -> Array:
	var out: Array = []
	for issue: Dictionary in issues:
		out.append(issue["kind"])
	out.sort()
	return out

func _check(room: Node) -> Array:
	return RoomCheck.new().check_room(room, _tree().root)

## The first room of the default plan with an exit on `edge`, and that exit.
func _room_with(edge: String, tile_set: TileSet) -> Array:
	var rooms := RoomTests.new()
	var plan := rooms._plan("default")
	for spec in RoomsRecipe.rooms(plan):
		var room := rooms._room(plan, str(spec["id"]), tile_set, false)
		for exit in room.exits():
			if exit.edge == edge:
				return [room, exit]
		room.free()
	return []

func test_every_planned_room_gets_through_the_check(t) -> void:
	var tile_set := PlatformTests.tileset()
	var rooms := RoomTests.new()
	var count := 0
	for case_name: String in ["default", "every_ability"]:
		var plan := rooms._plan(case_name)
		for spec in RoomsRecipe.rooms(plan):
			for with_player: bool in [false, true]:
				var room := rooms._room(plan, str(spec["id"]), tile_set, with_player)
				var issues := _check(room)
				t.eq(issues, [], "%s/%s (player: %s)" % [case_name, spec["id"], with_player])
				room.free()
				count += 1
	t.ok(count >= 10, "every room of both plans")
	t.ok(_tree().root.get_node_or_null("RpgRoomCheckSpace") == null, "the physics copy is gone after")

func test_rock_over_an_exit_is_reported_and_a_wall_of_blocks_is_not(t) -> void:
	var tile_set := PlatformTests.tileset()
	var found := _room_with("E", tile_set)
	var room: RpgRoom = found[0]
	var exit: RpgRoomExit = found[1]
	var ground := room.get_node("Ground") as TileMapLayer
	var column := room.room_size.x - 1
	var floor_row := int(exit.position.y / TILE)
	for y in range(floor_row - 3, floor_row):
		ground.set_cell(Vector2i(column, y), 0, PlatformTests.BREAKABLE)
	t.eq(_check(room), [], "a player with every ability breaks the blocks")
	for y in range(0, floor_row):
		ground.set_cell(Vector2i(column, y), 0, PlatformTests.GROUND)
	var issues := _check(room)
	t.eq(_kinds(issues), ["passage"])
	t.eq(issues[0]["node"], String(room.get_path_to(exit)))
	room.free()

func test_an_exit_up_without_its_ladder_is_out_of_reach(t) -> void:
	var tile_set := PlatformTests.tileset()
	var found := _room_with("N", tile_set)
	var room: RpgRoom = found[0]
	var exit: RpgRoomExit = found[1]
	var ladders := room.get_node("Decoration") as TileMapLayer
	var column := int(exit.position.x / TILE)
	for cell in ladders.get_used_cells():
		if cell.x == column:
			ladders.erase_cell(cell)
	var issues := _check(room)
	t.ok(_kinds(issues).has("climb"), "nothing reaches the hole in the ceiling: %s" % [issues])
	room.free()

func test_a_station_inside_rock_or_in_the_air_and_a_plank_under_a_ceiling(t) -> void:
	var tile_set := PlatformTests.tileset()
	var found := _room_with("E", tile_set)
	var room: RpgRoom = found[0]
	var station := RpgSaveStation.new()
	station.name = "Bench"
	room.get_node("Entities").add_child(station)
	var ground := room.get_node("Ground") as TileMapLayer
	var floor_row := 0
	while ground.get_cell_source_id(Vector2i(4, floor_row)) == -1:
		floor_row += 1
	station.position = Vector2(4.5 * TILE, (floor_row + 2) * TILE)
	t.eq(_kinds(_check(room)), ["buried"])
	station.position = Vector2(4.5 * TILE, (floor_row - 5) * TILE)
	t.eq(_kinds(_check(room)), ["floating"])
	station.position = Vector2(4.5 * TILE, floor_row * TILE)
	t.eq(_check(room), [], "on the floor")
	# a plank with one tile of air under a solid ceiling, the player 1.5 tiles tall
	var platforms := room.get_node("Platforms") as TileMapLayer
	for x in range(8, 12):
		platforms.set_cell(Vector2i(x, floor_row - 4), 0, PlatformTests.ONE_WAY)
		ground.set_cell(Vector2i(x, floor_row - 6), 0, PlatformTests.GROUND)
	var issues := _check(room)
	t.eq(_kinds(issues), ["headroom"], "one finding for the whole plank")
	room.free()

func test_the_content_checks_report_a_room_painted_wrong(t) -> void:
	var dir := "res://tests/tmp_room_check"
	DirAccess.make_dir_recursive_absolute(dir)
	var tile_set := PlatformTests.tileset()
	var found := _room_with("E", tile_set)
	var room: RpgRoom = found[0]
	var ground := room.get_node("Ground") as TileMapLayer
	for y in room.room_size.y:
		ground.set_cell(Vector2i(room.room_size.x - 1, y), 0, PlatformTests.GROUND)
	for node in room.find_children("*", "", true, false):
		node.owner = room  # as the recipe does when it saves a room
	var packed := PackedScene.new()
	t.eq(packed.pack(room), OK)
	t.eq(ResourceSaver.save(packed, dir + "/room.tscn"), OK)
	room.free()
	var findings := ContentChecks.run({"maps": dir, "world_plan": dir + "/none.json", "dialogue": dir, "items": dir, "sequences": dir, "enemies": dir, "skills": dir, "actors": dir, "shops": dir, "quests": dir, "placeholders": dir, "resources": []})
	var ours: Array = []
	for f: Dictionary in findings:
		if f["code"] == "VAL-033":
			ours.append(f)
	t.eq(ours.size(), 1, "%s" % [findings])
	if ours.size() == 1:
		t.eq(ours[0]["file"], dir + "/room.tscn")
		t.ok(str(ours[0]["detail"]["problem"]).contains("rock closes its opening"))
	DirAccess.remove_absolute(dir + "/room.tscn")
	DirAccess.remove_absolute(dir)
