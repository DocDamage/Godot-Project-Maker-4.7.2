extends RefCounted
## T14.06: rooms built from the plans rpggen makes (tests/fixtures/room_plan_cases.json, written
## by tools/make_map_plan_cases.py): what the recipe paints, the exits and where they lead, the
## room's camera, the parallax layers, and the graph and repair of a world of rooms.

const Fixtures := preload("../lib/fixtures.gd")
const PlatformTests := preload("test_platform_actor.gd")
const RoomsRecipe := preload("res://builder/recipes/metroidvania/rooms_recipe.gd")
const SideKit := preload("res://builder/recipes/metroidvania/side_kit.gd")
const Parallax := preload("res://builder/recipes/metroidvania/parallax_recipe.gd")
const Objects := preload("res://builder/recipes/metroidvania/objects_recipe.gd")
const PlayerRecipe := preload("res://builder/recipes/metroidvania/player_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const MapGraph := preload("res://addons/rpg_project_tools/tools/map_graph.gd")
const Repair := preload("res://addons/rpg_project_tools/tools/world_repair.gd")

const CASES := "res://tests/fixtures/room_plan_cases.json"
const TILE := 16

func _plan(case_name: String = "default") -> Dictionary:
	var cases: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CASES))
	var world: Dictionary = cases[case_name]
	return world["rooms"]

func _ctx(assets: Array = []) -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.catalog = CatalogReader.new({"assets": assets, "tilesets": [], "objects": []})
	ctx.config = {"archetype": "metroidvania", "resolution": [640, 360]}
	return ctx

func _kit(tile_set: TileSet) -> Dictionary:
	return SideKit.find(_ctx(), {"sources": [{"asset": "t.a", "source_id": 0}]}, tile_set)

## The room `id` of a plan as a node tree (with a player and a camera, as a built project has).
func _room(plan: Dictionary, id: String, tile_set: TileSet, with_player: bool = true) -> RpgRoom:
	var spec := RoomsRecipe.room_by_id(plan, id)
	var root := RoomsRecipe.new().build_room(_ctx(), plan, spec, tile_set, _kit(tile_set)) as RpgRoom
	if with_player:
		var player := PlayerRecipe.build_player("Player", null, Vector2i(24, 24), Vector2i(12, 23), TILE)
		root.get_node("Entities").add_child(player)
		(player.get_node("Components/PlatformInput") as RpgPlatformInput).enabled = false
		var spawn := root.get_spawn(&"default")
		player.position = spawn.position
		root.add_child(Objects.build_camera(TILE))
	return root

func _char_at(spec: Dictionary, cell: Vector2i) -> String:
	var rows: Array = spec["tiles"]
	return str(rows[cell.y])[cell.x]

# ---------------------------------------------------------------- what the recipe builds

func test_the_kit_finds_every_kind_of_tile(t) -> void:
	var kit := _kit(PlatformTests.tileset())
	t.eq(kit["top"]["coords"], PlatformTests.GROUND, "plain solid ground, not the breakable block")
	t.eq(kit["fill"], kit["top"], "no second row in this sheet")
	t.eq(kit["ladder"]["coords"], PlatformTests.LADDER)
	t.eq(kit["hazard"]["coords"], PlatformTests.HAZARD)
	t.eq(kit["breakable"]["coords"], PlatformTests.BREAKABLE)
	t.eq((kit["one_way"] as Array).size(), 1)
	t.eq(SideKit.plank(kit, true, true)["coords"], PlatformTests.ONE_WAY, "one plank tile serves every part of a run")
	var bare := TileSet.new()
	t.eq(SideKit.find(_ctx(), {"sources": []}, bare)["top"], {}, "a tile set without a solid tile has no floor")

func test_a_room_is_painted_as_the_plan_says(t) -> void:
	var tile_set := PlatformTests.tileset()
	var expected := {"#": ["Ground", PlatformTests.GROUND], "B": ["Ground", PlatformTests.BREAKABLE], "=": ["Platforms", PlatformTests.ONE_WAY], "^": ["Hazards", PlatformTests.HAZARD], "H": ["Decoration", PlatformTests.LADDER]}
	var seen := {}
	var specs: Array[Dictionary] = []
	var plan_of := {}
	for case_name: String in ["default", "every_ability"]:
		for spec in RoomsRecipe.rooms(_plan(case_name)):
			specs.append(spec)
			plan_of[spec] = _plan(case_name)
	for spec in specs:
		var plan: Dictionary = plan_of[spec]
		var room := _room(plan, str(spec["id"]), tile_set, false)
		var layer_names: Array = []
		for child in room.get_children():
			if child is TileMapLayer:
				layer_names.append(String(child.name))
		t.eq(layer_names, ["Ground", "Platforms", "Hazards", "Decoration", "Foreground"])
		var rows: Array = spec["tiles"]
		var wrong := 0
		for y in rows.size():
			var row := str(rows[y])
			for x in row.length():
				var cell := Vector2i(x, y)
				var symbol := row[x]
				seen[symbol] = true
				for layer_name: String in layer_names:
					var layer := room.get_node(layer_name) as TileMapLayer
					var coords := layer.get_cell_atlas_coords(cell) if layer.get_cell_source_id(cell) >= 0 else Vector2i(-1, -1)
					var want := Vector2i(-1, -1)
					if expected.has(symbol) and expected[symbol][0] == layer_name:
						want = expected[symbol][1]
					elif symbol == "T" and layer_name == "Decoration":
						want = PlatformTests.LADDER
					elif symbol == "T" and layer_name == "Platforms":
						want = PlatformTests.ONE_WAY
					if coords != want:
						wrong += 1
		t.eq(wrong, 0, "%s: every cell on its layer" % spec["id"])
		t.ok((room.get_node("Ground") as TileMapLayer).collision_enabled and (room.get_node("Platforms") as TileMapLayer).collision_enabled)
		t.eq(room.room_size, Vector2i(40, 23))
		t.eq(String(room.map_id), str(spec["id"]))
		t.ok(room.side_view and room.interior(), "a side-view room, and no day and night in a cave")
		room.free()
	for symbol: String in ["#", ".", "=", "^", "H", "B", "T"]:
		t.ok(seen.has(symbol), "the plans use '%s'" % symbol)

func test_exits_lead_to_their_partner_and_have_a_spawn_point_beside_them(t) -> void:
	var plan := _plan()
	var tile_set := PlatformTests.tileset()
	for spec in RoomsRecipe.rooms(plan):
		var room := _room(plan, str(spec["id"]), tile_set, false)
		var planned: Array = spec["exits"]
		var exits := room.exits()
		t.eq(exits.size(), planned.size(), str(spec["id"]))
		var bounds := Rect2(Vector2.ZERO, Vector2(room.room_size * TILE))
		for i in planned.size():
			var want: Dictionary = planned[i]
			var found := room.exit_named(str(want["id"]))
			t.ok(found != null, str(want["id"]))
			if found == null:
				continue
			t.eq(found.edge, str(want["edge"]))
			t.eq(found.target_room, "res://game/maps/rooms/%s.tscn" % want["to"])
			t.eq(found.target_exit, str(want["to_exit"]))
			t.ok(found.get_collision_layer_value(6) and found.get_collision_mask_value(2), "a trigger that looks for the player")
			var shape := found.get_node("Shape") as CollisionShape2D
			var area := Rect2(found.position + shape.position - (shape.shape as RectangleShape2D).size / 2.0, (shape.shape as RectangleShape2D).size)
			t.ok(not bounds.intersects(area), "%s: the area lies outside the room" % want["id"])
			t.ok(bounds.grow(1.0).intersects(area), "%s: and touches its edge" % want["id"])
			var spawn := room.get_spawn(StringName(str(want["id"])))
			t.ok(spawn != null and spawn.spawn_id == StringName(str(want["id"])), "a spawn point named like the exit")
			t.ok(bounds.grow(-4.0).has_point(spawn.position), "%s: players arrive inside the room" % want["id"])
			t.ok(spawn.side_view)
			if found.is_side():
				t.eq(found.outward().x, 1.0 if found.edge == "E" else -1.0)
				t.eq(spawn.side(), -1 if found.edge == "E" else 1, "they look into the room")
		room.free()
	var start := _room(plan, "room_01", tile_set, false)
	t.ok(start.get_spawn(&"default").spawn_id == &"default", "the start room has the default spawn")
	t.eq(start.get_spawn(&"default").position, RoomsRecipe.feet(Vector2i(3, 19), TILE))
	t.ok(start.get_node("Entities").get_child_count() == 0, "no sign, no player: this tile set has no such scenes")
	start.free()

func test_exit_layout_of_every_edge(t) -> void:
	var size := Vector2i(40, 23)
	var east := RoomsRecipe.exit_layout("E", Vector2i(39, 19), size, TILE)
	t.eq(east["position"], Vector2(640, 320))
	t.eq(east["area"], Rect2(0, -48, 16, 48), "three tiles high, just outside")
	t.eq(east["arrival"], Vector2(616, 320))
	var west := RoomsRecipe.exit_layout("W", Vector2i(0, 19), size, TILE)
	t.eq(west["position"], Vector2(0, 320))
	t.eq(west["area"], Rect2(-16, -48, 16, 48))
	t.eq(west["arrival"], Vector2(24, 320))
	var north := RoomsRecipe.exit_layout("N", Vector2i(20, 0), size, TILE)
	t.eq(north["position"], Vector2(328, 0))
	t.eq(north["area"], Rect2(-8, -16, 16, 16), "above the ceiling")
	t.ok(north["arrival"].y > 24.0, "a player from above arrives well below the area")
	var south := RoomsRecipe.exit_layout("S", Vector2i(20, 22), size, TILE)
	t.eq(south["position"], Vector2(328, 368))
	t.eq(south["area"], Rect2(-8, 0, 16, 16), "below the floor")
	t.ok(south["arrival"].y < 368.0)

# ---------------------------------------------------------------- arriving

func test_arriving_keeps_the_speed_and_the_facing_and_the_camera_stays_in_the_room(t) -> void:
	var tree := Fixtures.tree()
	await tree.process_frame
	var plan := _plan()
	var room := _room(plan, "room_02", PlatformTests.tileset())
	tree.root.add_child(room)
	var player := room.get_player() as RpgPlatformPlayer
	var camera := room.camera()
	t.ok(camera != null and camera.enabled)
	var cameras := 0
	for node in room.find_children("*", "Camera2D", true, false):
		if (node as Camera2D).enabled:
			cameras += 1
	t.eq(cameras, 1, "exactly one enabled camera: the room's")
	t.eq(camera.limits(), Rect2(0, 0, 640, 368), "the camera's limits are the room's")
	t.ok(room.exits().size() == 2 and not room.just_arrived())
	# the player comes in from the west, running and in the middle of a jump
	var west := room.exit_named("room_02_exit_w")
	var carry := {"velocity": Vector2(110, -90), "facing": 1, "on_ladder": false, "offset": Vector2(-3, -20)}
	room.arrive("room_02_exit_w", carry)
	var spawn := room.get_spawn(&"room_02_exit_w")
	t.eq(player.position, spawn.position + Vector2(0, -20), "at the exit's spawn point, as high above the floor as before")
	t.eq(player.velocity, Vector2(110, -90), "the speed is kept")
	t.eq(player.facing, 1)
	t.ok(room.just_arrived())
	t.ok(not west.use(player), "an exit does not fire in the moment after arriving")
	t.eq(camera.offset, Vector2(-96, 0), "the view slides in from the side the player came from")
	t.ok(camera.limit_left < 0, "and may show past that edge while it does")
	await tree.create_timer(0.4).timeout
	t.eq(camera.offset, Vector2.ZERO)
	t.eq(camera.limits(), Rect2(0, 0, 640, 368), "then the limits are the room's again")
	# what an exit hands over
	player.velocity = Vector2(-80, 12)
	player.set_facing(-1)
	var taken := west.carry_of(player)
	t.eq(taken["velocity"], Vector2(-80, 12))
	t.eq(taken["facing"], -1)
	t.eq(taken["offset"], player.global_position - west.global_position)
	# from the east, looking left
	room.arrive("room_02_exit_e", {"velocity": Vector2(-110, 0), "facing": -1})
	t.eq(player.position, room.get_spawn(&"room_02_exit_e").position)
	t.eq(player.facing, -1)
	t.eq(camera.offset.x, 96.0)
	# the scene router's hook: a loaded position gets the camera at once
	player.position = Vector2(300, 320)
	room.player_placed(player)
	t.eq(camera.global_position, camera.wanted())
	tree.root.remove_child(room)
	room.free()

func test_a_ladder_exit_keeps_the_climb(t) -> void:
	var tree := Fixtures.tree()
	await tree.process_frame
	var plan := _plan()
	var shaft := ""
	for spec in RoomsRecipe.rooms(plan):
		if spec["kind"] == "shaft":
			shaft = str(spec["id"])
	t.ok(shaft != "", "the plan has a shaft")
	var up := ""
	var shaft_exits: Array = RoomsRecipe.room_by_id(plan, shaft).get("exits", [])
	for exit_spec: Dictionary in shaft_exits:
		if exit_spec["edge"] == "N":
			up = str(exit_spec["to"])
	var room := _room(plan, up, PlatformTests.tileset())
	tree.root.add_child(room)
	var player := room.get_player() as RpgPlatformPlayer
	var south := "%s_exit_s" % up
	room.arrive(south, {"velocity": Vector2(0, -70), "facing": 1, "on_ladder": true})
	t.ok(player.on_ladder, "still climbing")
	t.eq(player.position, room.get_spawn(StringName(south)).position)
	t.ok(player.ladder_here(), "and on the ladder that comes up through the floor")
	t.eq(room.camera().offset, Vector2(0, 96), "the view slides in from below")
	tree.root.remove_child(room)
	room.free()

# ---------------------------------------------------------------- parallax

func _background(id: String, depth: int) -> Dictionary:
	return {"id": id, "path": "icon.svg", "status": "CONFIRMED", "detected": {"usage": "background", "role": "BACKGROUND", "tags": ["parallax:%d" % depth]}, "overrides": {}}

func test_parallax_layers_scroll_at_their_factors(t) -> void:
	t.near(Parallax.factor(1), 0.15)
	t.near(Parallax.factor(2), 0.4)
	t.near(Parallax.factor(3), 0.7)
	t.ok(Parallax.factor(9) < 1.0, "even the nearest layer lags a little")
	t.eq(Parallax.depth_of({"tags": ["x", "parallax:2"]}), 2)
	t.eq(Parallax.depth_of({"tags": ["title"]}), 0)
	var title := _background("p.title", 1)
	title["detected"]["tags"] = []
	var ctx := _ctx([_background("p.near", 3), _background("p.far", 1), title, _background("p.mid", 2)])
	var found := Parallax.layers(ctx)
	t.eq(found.size(), 3, "a background without a depth is not a layer")
	t.eq([found[0]["asset"], found[1]["asset"], found[2]["asset"]], ["p.far", "p.mid", "p.near"], "the farthest first")
	var holder := Parallax.build(ctx, Vector2(640, 368), Vector2(640, 360))
	t.eq(holder.get_child_count(), 3)
	var texture := load("res://icon.svg") as Texture2D
	for i in 3:
		var layer := holder.get_child(i) as Parallax2D
		t.ok(layer != null, "a Parallax2D")
		t.near(layer.scroll_scale.x, Parallax.factor(i + 1))
		t.near(layer.scroll_scale.y, 1.0, 0.001, "only sideways")
		var sprite := layer.get_node("Sprite") as Sprite2D
		var zoom := sprite.scale.x
		t.ok(zoom == floorf(zoom) and texture.get_height() * zoom >= 360.0, "a whole-number zoom, as tall as the view")
		t.near(layer.repeat_size.x, texture.get_width() * zoom)
		t.near(sprite.position.y + texture.get_height() * zoom, 368.0, 0.01, "it stands on the bottom of the room")
	t.ok(holder.z_index < 0, "behind everything")
	holder.free()
	t.eq(Parallax.build(_ctx(), Vector2(640, 368), Vector2(640, 360)), null, "no layers, no node")
	# a room of a project with backgrounds has the node first, behind its tiles
	var room := RoomsRecipe.new().build_room(ctx, _plan(), RoomsRecipe.room_by_id(_plan(), "room_01"), PlatformTests.tileset(), _kit(PlatformTests.tileset()))
	t.eq(String(room.get_child(0).name), "Background")
	room.free()

# ---------------------------------------------------------------- the graph and its repair

## The rooms of a plan as {path: root}, and the callable the graph reads them through.
func _world(plan: Dictionary) -> Dictionary:
	var roots := {}
	var tile_set := PlatformTests.tileset()
	for spec in RoomsRecipe.rooms(plan):
		roots[RoomsRecipe.room_path(spec)] = _room(plan, str(spec["id"]), tile_set, false)
	return roots

func _free_world(roots: Dictionary) -> void:
	for path: String in roots:
		(roots[path] as Node).free()

func _paths(roots: Dictionary) -> Array[String]:
	var out: Array[String] = []
	for path: String in roots:
		out.append(path)
	out.sort()
	return out

func test_the_graph_of_a_planned_world_has_no_finding(t) -> void:
	var plan := _plan("every_ability")
	var roots := _world(plan)
	var instance_of := func(path: String) -> Node: return roots.get(path)
	var graph := MapGraph.read(_paths(roots), instance_of)
	var start := MapGraph.start_for({"rooms": plan})
	t.eq(start, "res://game/maps/rooms/room_01.tscn")
	t.eq(MapGraph.start_for({}), MapGraph.START, "a top-down world starts in the starter map")
	t.eq(MapGraph.reachable(graph, start).size(), 9, "every room through its exits")
	t.eq(MapGraph.unreachable(graph, start), [] as Array[String])
	t.eq(MapGraph.dangling(graph, func(path: String) -> bool: return roots.has(path)), [] as Array[Dictionary])
	var first: Dictionary = graph[start]
	t.eq((first["doors"] as Array).size(), 1)
	t.ok(first["doors"][0]["exit"] and first["doors"][0]["edge"] == "E" and first["doors"][0]["id"] == "room_01_exit_e")
	t.eq(Repair.plan_repairs(_paths(roots), {"rooms": plan, "grid": {}}, instance_of, start), [] as Array[Dictionary])
	_free_world(roots)

func _grid(plan: Dictionary) -> Dictionary:
	var grid := {}
	for spec in RoomsRecipe.rooms(plan):
		grid[spec["id"]] = spec["cell"]
	return grid

func test_an_exit_without_its_partner_is_mended_beside_the_wall(t) -> void:
	var plan := _plan()
	var roots := _world(plan)
	var instance_of := func(path: String) -> Node: return roots.get(path)
	var start := "res://game/maps/rooms/room_01.tscn"
	var second := "res://game/maps/rooms/room_02.tscn"
	var room := roots[second] as RpgRoom
	# somebody deleted the west exit of room 2 and the spawn point beside it
	var gone := room.exit_named("room_02_exit_w")
	gone.get_parent().remove_child(gone)
	gone.free()
	var marker := room.get_spawn(&"room_02_exit_w")
	marker.get_parent().remove_child(marker)
	marker.free()
	var graph := MapGraph.read(_paths(roots), instance_of)
	var broken := MapGraph.dangling(graph, func(path: String) -> bool: return roots.has(path))
	t.eq(broken.size(), 1)
	t.eq([broken[0]["map"], broken[0]["missing"], broken[0]["spawn"]], [start, "spawn", "room_02_exit_w"])
	var world := {"rooms": plan, "grid": _grid(plan)}
	var actions := Repair.plan_repairs(_paths(roots), world, instance_of, start)
	var kinds: Array = []
	for action in actions:
		kinds.append([action["kind"], action["map"]])
	t.eq(kinds, [["spawn", second], ["exit", second]], "a spawn point and the exit back, both in room 2")
	var tiles_before := (room.get_node("Ground") as TileMapLayer).get_used_cells().size()
	for action in actions:
		Repair.apply(action, room)
	t.eq((room.get_node("Ground") as TileMapLayer).get_used_cells().size(), tiles_before, "nothing of the room is dug away")
	var mended := room.exit_named("room_02_exit_w")
	t.ok(mended != null and mended.owner == room, "the exit is part of the scene")
	t.eq(mended.target_room, start)
	t.eq(mended.target_exit, "room_01_exit_e")
	t.eq(mended.edge, "W")
	t.eq(mended.position, Vector2(16, 320), "on the floor beside the west wall")
	var arrival := room.get_spawn(&"room_02_exit_w")
	t.eq(arrival.position, Vector2(56, 320), "two and a half tiles further in")
	t.ok(arrival.side_view and arrival.side() == 1)
	t.eq(Repair.plan_repairs(_paths(roots), world, instance_of, start), [] as Array[Dictionary], "nothing more to do")
	_free_world(roots)

func test_a_room_nobody_can_reach_gets_an_exit_pair_with_its_neighbour(t) -> void:
	var plan := _plan()
	var roots := _world(plan)
	var instance_of := func(path: String) -> Node: return roots.get(path)
	var start := "res://game/maps/rooms/room_01.tscn"
	var second := "res://game/maps/rooms/room_02.tscn"
	# both ends of the pair between room 1 and room 2 are gone
	for pair: Array in [[start, "room_01_exit_e"], [second, "room_02_exit_w"]]:
		var room := roots[pair[0]] as RpgRoom
		var exit_node := room.exit_named(pair[1])
		exit_node.get_parent().remove_child(exit_node)
		exit_node.free()
		var marker := room.get_spawn(StringName(str(pair[1])))
		marker.get_parent().remove_child(marker)
		marker.free()
	var graph := MapGraph.read(_paths(roots), instance_of)
	t.eq(MapGraph.unreachable(graph, start).size(), 5, "the whole chain behind room 1 is cut off")
	var world := {"rooms": plan, "grid": _grid(plan)}
	var actions := Repair.plan_repairs(_paths(roots), world, instance_of, start)
	var kinds: Array = []
	for action in actions:
		kinds.append([action["kind"], str(action["map"]).get_file().get_basename()])
	t.eq(kinds, [["spawn", "room_02"], ["exit", "room_02"], ["spawn", "room_01"], ["exit", "room_01"]])
	for action in actions:
		Repair.apply(action, roots[action["map"]])
	t.eq(MapGraph.unreachable(MapGraph.read(_paths(roots), instance_of), start), [] as Array[String])
	t.eq(Repair.plan_repairs(_paths(roots), world, instance_of, start), [] as Array[Dictionary])
	var east := (roots[start] as RpgRoom).exit_named("room_01_exit_e")
	t.eq([east.edge, east.target_room, east.target_exit], ["E", second, "room_02_exit_w"])
	t.eq(east.position, Vector2(624, 320), "on the floor beside the east wall")
	# a room with no neighbour in the plan cannot be joined
	var lonely := {"rooms": plan, "grid": {}}
	var again := _world(plan)
	var instance_again := func(path: String) -> Node: return again.get(path)
	var first := again[start] as RpgRoom
	var only := first.exit_named("room_01_exit_e")
	only.get_parent().remove_child(only)
	only.free()
	var unfixable := Repair.plan_repairs(_paths(again), lonely, instance_again, start)
	t.ok(unfixable.size() >= 1 and unfixable[0]["kind"] == "unfixable", "without the grid nobody knows who is beside whom")
	_free_world(again)
	_free_world(roots)
