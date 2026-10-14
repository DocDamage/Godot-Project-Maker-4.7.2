extends RefCounted
## Real isometric packs in the builder (T17.22), on the fixture of the synthetic pack `iso_kit`
## (in the manner of *Medieval Town* and *Vector Roads*: walls that stand along one side of a
## diamond in four turns, a wall with a door, one with a window, a fence, a roof that is a tile,
## road corners that are round and square): a piece is asked for by its side, the edge of a map
## is laid from segments, a house is put together from pieces on a footprint and sorts as one
## building, a yard is fenced with segments, and the camera's zoom keeps the steps of the grid
## whole.

const TilesetRecipe := preload("res://builder/recipes/tileset_recipe.gd")
const ObjectRecipe := preload("res://builder/recipes/object_scenes_recipe.gd")
const FarmMapRecipe := preload("res://builder/recipes/farm/farm_map_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const IsoTileset := preload("res://builder/lib/iso_tileset.gd")
const IsoHouse := preload("res://builder/lib/iso_house.gd")
const MapGeo := preload("res://builder/lib/map_geo.gd")
const MapUtil := preload("res://builder/lib/map_util.gd")
const ObjectEntries := preload("res://builder/lib/object_entries.gd")
const ObjectIndex := preload("res://builder/lib/object_index.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const FIXTURE := "res://tests/fixtures/iso_kit/catalog.json"
const TS_PATH := "res://generated/tilesets/iso.tres"
const STATE_PATH := "res://rpggen/tileset_apply_state.json"
const OUT := "user://test_iso_kit_house.tscn"
const FOOT := Vector2i(64, 36)
const WALL := "iso_kit.png.stone_wall_01_"
const SHORT := "iso_kit.png.stone_short_wall_01_"
const DOOR := "iso_kit.png.stone_door_01_"
const WINDOW := "iso_kit.png.stone_window_01_"
const FENCE := "iso_kit.png.wood_fence_01_"
const ROOF := "iso_kit.png.roof_point_01_0"
## The side the turn 0, 1, 2, 3 of a wall of the pack stands along: not the turn's number.
const TURN_SIDES: Array[String] = ["e", "s", "w", "n"]
## How far the whole wall rises above its diamond on a far side: the storey of a house.
const STOREY := 23

func _catalog() -> Dictionary:
	return JsonUtil.to_dict(JsonUtil.read(FIXTURE)).duplicate(true)

func _context(cat: Dictionary) -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": "isometric", "features": {"navigation": false}, "seed": 7, "map_layers": MapUtil.DEFAULT_LAYERS.duplicate()}
	ctx.catalog = CatalogReader.new(cat, "isometric")
	return ctx

func _cleanup() -> void:
	for p: String in [TS_PATH, STATE_PATH, OUT]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)

func _asset_at(layer: TileMapLayer, cell: Vector2i) -> String:
	var data := layer.get_cell_tile_data(cell)
	return str(data.get_custom_data("asset_id")) if data != null else ""

# ---------------------------------------------------------------- a piece by its side

func test_a_piece_along_a_side_is_asked_for_by_the_side(t) -> void:
	var iso := IsoTileset.new(CatalogReader.new(_catalog(), "isometric"))
	t.ok(iso.has_tiles())
	t.eq(iso.footprint(), FOOT)
	# the four turns of a wall stand along the four sides, and not in the order of the turns
	for turn in 4:
		t.eq(iso.edge_of(WALL + str(turn)), TURN_SIDES[turn], "turn %d" % turn)
		var piece := iso.edge_piece(WALL + "0", TURN_SIDES[turn])
		t.eq(piece, {"asset_id": WALL + str(turn), "turn": turn}, "the member for %s" % TURN_SIDES[turn])
		# any turn of the set names the set
		t.eq(iso.edge_piece(WALL + "2", TURN_SIDES[turn]), piece)
	t.eq(iso.edge_members(DOOR + "1"), {"e": DOOR + "0", "s": DOOR + "1", "w": DOOR + "2", "n": DOOR + "3"})
	t.eq(iso.first_of(DOOR + "3"), DOOR + "0")
	# by a tag or a role: the first set of it, by id, that has the side
	t.eq(iso.edge_piece("door", "s"), {"asset_id": DOOR + "1", "turn": 1})
	t.eq(iso.edge_piece("fence", "n"), {"asset_id": FENCE + "3", "turn": 3})
	t.eq(iso.edge_piece("WALL", "n"), {"asset_id": DOOR + "3", "turn": 3}, "the first wall by id is the one with a door")
	t.eq(iso.edge_piece("no such thing", "n"), {})
	t.eq(iso.edge_piece(WALL + "0", "up"), {})
	t.eq(iso.edge_piece("iso_kit.png.grass_01_0", "n"), {}, "a ground tile stands along no side")
	t.eq(iso.edge_of("iso_kit.png.grass_01_0"), "")
	t.eq(iso.edge_members("iso_kit.png.grass_01_0"), {})
	# the sets: every one, the plain walls, the fences
	t.eq(iso.edge_sets("WALL"), [DOOR + "0", SHORT + "0", WALL + "0", WINDOW + "0", FENCE + "0"])
	t.eq(iso.edge_sets("WALL", ["door", "window"]), [SHORT + "0", WALL + "0", FENCE + "0"])
	t.eq(iso.wall_sets(false), [SHORT + "0", WALL + "0"])
	t.eq(iso.wall_sets(true), [FENCE + "0"])
	t.eq(iso.edge_rise(WALL + "0", "n"), STOREY)
	t.ok(iso.edge_rise(WALL + "0", "e") < STOREY, "a near side begins lower: less of it shows above the diamond")
	# the edge of a map: the lowest plain wall, a fence first on a farm
	t.eq(iso.border_set(), SHORT + "0")
	t.eq(iso.border_set(true), FENCE + "0")
	# such a piece is no tile a map is filled or bordered with
	t.eq(iso.plain_tiles("WALL"), [] as Array[String])
	t.eq(iso.plain_tile("WALL"), "", "the packs have no whole wall tile")
	t.ok(iso.plain_tile("GROUND") != "")
	# where its picture is: its own canvas in the atlas
	var picture := iso.picture_of(WALL + "0")
	t.eq(str(picture.get("texture", "")), "res://tests/fixtures/iso_kit/iso_kit_0.png")
	var region: Array = picture["region"]
	t.eq([int(region[2]), int(region[3])], [72, 96])
	t.eq(iso.picture_of("nothing"), {})
	# a road's corner says how it turns, and the piece laid on a corner is the first by id
	t.eq(str(iso.facets("iso_kit.png.roades").get("corner", "")), "round")
	t.eq(str(iso.facets("iso_kit.png.streetes").get("corner", "")), "square")
	t.eq(str(iso.piece_for("ROAD", ["e", "s"]).get("asset_id", "")), "iso_kit.png.roades")
	t.ok(not iso.facets("iso_kit.png.roadns").has("corner"), "a straight is no corner")

# ---------------------------------------------------------------- the edge of a map

func test_the_edge_of_a_map_is_laid_from_segments(t) -> void:
	_cleanup()
	var ctx := _context(_catalog())
	t.eq(TilesetRecipe.new().build(ctx), [])
	var geo := MapGeo.new(ctx)
	var tile_set := geo.load_tile_set()
	t.ok(geo.isometric and tile_set != null)
	t.eq(geo.wall_tile(), {}, "no whole wall tile")
	var size := Vector2i(6, 5)
	var gap := Vector2i(5, 2)
	t.eq(MapGeo.outward_sides(Vector2i(3, 0), size), ["n"] as Array[String])
	t.eq(MapGeo.outward_sides(Vector2i(0, 0), size), ["n", "w"] as Array[String])
	t.eq(MapGeo.outward_sides(Vector2i(5, 0), size), ["n", "e"] as Array[String])
	t.eq(MapGeo.outward_sides(Vector2i(0, 4), size), ["w", "s"] as Array[String])
	t.eq(MapGeo.outward_sides(Vector2i(5, 4), size), ["e", "s"] as Array[String])
	t.eq(MapGeo.outward_sides(Vector2i(2, 2), size), [] as Array[String])
	t.eq(MapGeo.edge_places(["n", "w"] as Array[String]), [["n", "Props"], ["w", "GroundDetails"]])
	t.eq(MapGeo.edge_places(["n", "e"] as Array[String]), [["e", "Props"], ["n", "GroundDetails"]])
	t.eq(MapGeo.edge_places(["w", "s"] as Array[String]), [["s", "Props"], ["w", "GroundDetails"]])
	t.eq(MapGeo.edge_places(["e", "s"] as Array[String]), [["e", "Props"], ["s", "Overhead"]])
	var root := MapUtil.new_map_root("Test", "test")
	var nodes := MapUtil.build_layers(root, MapUtil.DEFAULT_LAYERS, tile_set)
	geo.paint_walls(root, nodes, size, [gap])
	var props: TileMapLayer = nodes["Props"]
	var under: TileMapLayer = nodes["GroundDetails"]
	var over: TileMapLayer = nodes["Overhead"]
	var walls: TileMapLayer = nodes["Walls"]
	var ground: TileMapLayer = nodes["Ground"]
	t.eq(props.get_used_cells().size(), 2 * 6 + 2 * 3 - 1, "a piece on every cell of the edge but the gap")
	t.eq(walls.get_used_cells().size(), 0)
	t.eq(ground.get_used_cells().size(), 0, "a segment fills no diamond: the ground under it stays")
	for layer: TileMapLayer in [props, under, over]:
		t.eq(layer.get_cell_source_id(gap), -1, "the way out is open")
	# the member of the lowest wall that stands along the side that looks out of the map
	var by_side := {"n": SHORT + "3", "e": SHORT + "0", "s": SHORT + "1", "w": SHORT + "2"}
	for x in range(1, 5):
		t.eq(_asset_at(props, Vector2i(x, 0)), by_side["n"], "the first row: n")
		t.eq(_asset_at(props, Vector2i(x, 4)), by_side["s"], "the last row: s")
	for y in range(1, 4):
		t.eq(_asset_at(props, Vector2i(0, y)), by_side["w"], "the first column: w")
		if Vector2i(5, y) != gap:
			t.eq(_asset_at(props, Vector2i(5, y)), by_side["e"], "the last column: e")
	# a corner has a piece for each of its two sides, on two layers
	t.eq(_asset_at(props, Vector2i(0, 0)), by_side["n"])
	t.eq(_asset_at(under, Vector2i(0, 0)), by_side["w"])
	t.eq(_asset_at(props, Vector2i(5, 0)), by_side["e"])
	t.eq(_asset_at(under, Vector2i(5, 0)), by_side["n"])
	t.eq(_asset_at(props, Vector2i(0, 4)), by_side["s"])
	t.eq(_asset_at(under, Vector2i(0, 4)), by_side["w"])
	t.eq(_asset_at(props, Vector2i(5, 4)), by_side["e"])
	t.eq(_asset_at(over, Vector2i(5, 4)), by_side["s"])
	t.eq(under.get_used_cells().size(), 3)
	t.eq(over.get_used_cells().size(), 1)
	# the cells are blocked by the tiles' own diamonds, on the layer that is sorted with the actors
	t.ok(props.y_sort_enabled and props.collision_enabled)
	for cell in props.get_used_cells():
		t.eq(props.get_cell_tile_data(cell).get_collision_polygons_count(0), 1, "%s blocks" % cell)
	t.ok(root.get_node_or_null("BorderCollision") == null, "no unseen shape is needed")
	# a near side is drawn after who stands on the cell before it, a far side before who stands
	# on the cell after it: the layer sorts a piece by the middle of its cell
	var east_wall := props.map_to_local(Vector2i(5, 1)).y
	t.ok(props.map_to_local(Vector2i(4, 1)).y < east_wall, "an actor west of the east wall is drawn first")
	var north_wall := props.map_to_local(Vector2i(2, 0)).y
	t.ok(props.map_to_local(Vector2i(2, 1)).y > north_wall, "an actor south of the north wall is drawn after it")
	root.free()
	# a farm is fenced
	var farm_root := MapUtil.new_map_root("Test", "test")
	var farm_nodes := MapUtil.build_layers(farm_root, MapUtil.DEFAULT_LAYERS, tile_set)
	geo.paint_walls(farm_root, farm_nodes, size, [gap], true)
	t.eq(_asset_at(farm_nodes["Props"], Vector2i(2, 0)), FENCE + "3")
	farm_root.free()
	# a map without the layers of a corner's second piece has one piece on it
	var few_root := MapUtil.new_map_root("Test", "test")
	var few := MapUtil.build_layers(few_root, ["Ground", "Walls"], tile_set)
	t.ok(geo.paint_edge_walls(few_root, few, size, [gap]))
	var only: TileMapLayer = few["Walls"]
	t.eq(only.get_used_cells().size(), 17)
	t.eq(_asset_at(only, Vector2i(5, 4)), by_side["e"])
	few_root.free()
	# the hash of a map recipe says that the packs have such pieces
	t.eq(MapGeo.edge_hash(ctx), {"iso_edges": MapGeo.EDGE_VERSION})
	ctx.config.erase("projection")
	t.eq(MapGeo.edge_hash(ctx), {}, "a project seen from above has nothing of it")
	_cleanup()

# ---------------------------------------------------------------- a house of pieces

## What the sort keys say about an actor whose feet are at `at`: for each half of the house the
## actor overlaps, 1 when the actor is drawn after it (in front), -1 before it.
func _drawn(house: Node2D, at: Vector2) -> Array[int]:
	var out: Array[int] = []
	var halves: Array[Node2D] = []
	if at.x <= house.position.x:
		halves.append(house.get_node("Left") as Node2D)
	if at.x >= house.position.x:
		halves.append(house.get_node("Right") as Node2D)
	for half in halves:
		var key := house.position.y + half.position.y
		out.append(1 if at.y > key else (-1 if at.y < key else 0))
	return out

func _sprites(house: Node2D) -> Array[Sprite2D]:
	var out: Array[Sprite2D] = []
	for half_name: String in ["Left", "Right"]:
		for child in house.get_node(half_name).get_children():
			out.append(child as Sprite2D)
	return out

## What a house of `size` cells whose door is before `door_column` must be, whatever built it.
func _check_house(t, house: Node2D, size: Vector2i, door_column: int, what: String) -> void:
	var first := Vector2i(8, 6)
	var cells := Rect2i(first, size)
	house.position = RpgIso.cell_to_screen(first + size - Vector2i.ONE, FOOT)
	var keys := RpgIso.sort_keys(cells, FOOT)
	var left := house.get_node("Left") as Node2D
	var right := house.get_node("Right") as Node2D
	t.ok(house.y_sort_enabled, "%s: its halves are sorted among the actors" % what)
	t.near(house.position.x, keys[0], 0.001, "%s: cut at the corner nearest the camera" % what)
	t.near(house.position.y + left.position.y, keys[1], 0.001, "%s: the left half sorts by the left corner" % what)
	t.near(house.position.y + right.position.y, keys[2], 0.001, "%s: the right half sorts by the right corner" % what)
	# a wall on every side of the rim, one door, a roof over each cell
	var walls := {}
	var doors: Array = []
	var placed := {}
	var roofs := {}
	for sprite in _sprites(house):
		var cell: Vector2i = sprite.get_meta("cell")
		var side := str(sprite.get_meta("side"))
		var kind := str(sprite.get_meta("kind"))
		var asset_id := str(sprite.get_meta("asset_id"))
		var region := (sprite.texture as AtlasTexture).region
		# where the picture lies: in the half it is drawn with, and nowhere across the cut
		var from_x := sprite.offset.x
		var to_x := from_x + region.size.x
		if sprite.get_parent() == left:
			t.ok(to_x <= 0.001, "%s: %s of the left half ends at the cut (%s)" % [what, sprite.name, to_x])
		else:
			t.ok(from_x >= -0.001, "%s: %s of the right half begins at the cut (%s)" % [what, sprite.name, from_x])
		if kind == "roof":
			roofs[cell] = int(roofs.get(cell, 0)) + 1
			t.eq(asset_id, ROOF)
			continue
		# one piece a side; the few px of it that lie across the cut are a sprite of the other half
		t.ok(not placed.has([cell, side, sprite.get_parent().name]), "%s: one piece on the %s side of %s" % [what, side, cell])
		placed[[cell, side, sprite.get_parent().name]] = true
		t.eq(str(walls.get([cell, side], asset_id)), asset_id, "%s: the two halves of one piece" % what)
		walls[[cell, side]] = asset_id
		var iso_side := TURN_SIDES[int(asset_id.right(1))]
		t.eq(iso_side, side, "%s: the piece on the %s side of %s stands along that side" % [what, side, cell])
		if kind == "door":
			if not doors.has([cell, side]):
				doors.append([cell, side])
			t.ok(asset_id.begins_with(DOOR), "%s: the door piece" % what)
		elif kind == "window":
			t.ok(asset_id.begins_with(WINDOW), "%s: a window piece" % what)
		else:
			t.ok(asset_id.begins_with(WALL), "%s: the whole wall, not the short one" % what)
	var rim := 0
	for y in size.y:
		for x in size.x:
			var cell := Vector2i(x, y)
			t.ok(roofs.has(cell), "%s: a roof over %s" % [what, cell])
			for side: String in ["n", "e", "s", "w"]:
				var out := (side == "n" and y == 0) or (side == "w" and x == 0) or (side == "e" and x == size.x - 1) or (side == "s" and y == size.y - 1)
				t.eq(walls.has([cell, side]), out, "%s: the %s side of %s" % [what, side, cell])
				rim += 1 if out else 0
	t.eq(walls.size(), rim)
	t.eq(roofs.size(), size.x * size.y)
	t.eq(doors, [[Vector2i(door_column, size.y - 1), "s"]], "%s: one door, above the plan's door cell" % what)
	# the walk round it: every point of the ground two cells around it, a quarter of a cell apart
	var checked := 0
	var wrong := 0
	for iy in range(-8, size.y * 4 + 9):
		for ix in range(-8, size.x * 4 + 9):
			var g := Vector2(first.x + ix / 4.0, first.y + iy / 4.0)
			var at := Vector2((g.x - g.y + 1) * FOOT.x / 2.0, (g.x + g.y) * FOOT.y / 2.0)
			var truth := RpgIso.in_front(at, cells, FOOT)
			if truth == 0 or (g.x >= first.x and g.x <= first.x + size.x and g.y >= first.y and g.y <= first.y + size.y):
				continue  # beside it, where neither hides the other; or on it, where nobody stands
			checked += 1
			for seen in _drawn(house, at):
				if seen != truth:
					wrong += 1
	t.ok(checked > 150, "%s: %d points were asked" % [what, checked])
	t.eq(wrong, 0, "%s: an actor on the ring round it is drawn on the right side of it" % what)
	t.eq(_drawn(house, RpgIso.cell_to_screen(first + Vector2i(0, -1), FOOT)).max(), -1, "%s: north of it: behind" % what)
	t.eq(_drawn(house, RpgIso.cell_to_screen(first + Vector2i(-1, 0), FOOT)).max(), -1, "%s: west of it: behind" % what)
	t.eq(_drawn(house, RpgIso.cell_to_screen(first + Vector2i(size.x - 1, size.y), FOOT)).min(), 1, "%s: south of it: in front" % what)
	t.eq(_drawn(house, RpgIso.cell_to_screen(first + Vector2i(size.x, size.y - 1), FOOT)).min(), 1, "%s: east of it: in front" % what)

func test_a_house_is_put_together_from_the_packs_pieces(t) -> void:
	_cleanup()
	var ctx := _context(_catalog())
	t.eq(TilesetRecipe.new().build(ctx), [])
	var iso := IsoTileset.new(ctx.catalog)
	var pieces := IsoHouse.kit(iso)
	t.eq(pieces, {"wall": WALL + "0", "door": DOOR + "0", "window": WINDOW + "0", "roof": ROOF, "storey": STOREY})
	# the packs drew no whole house: the entry of the village's is the house of pieces
	var entry := ObjectEntries.starter_building(ctx)
	t.eq(str(entry.get("id", "")), IsoHouse.ENTRY_ID)
	t.ok(IsoHouse.is_kit(entry) and ObjectEntries.is_iso(entry), "an entry of pieces, drawn for the view")
	t.eq(entry["role"], "BUILDING")
	t.eq(entry["stands_on"], [2, 2])
	t.eq(entry["iso"], [FOOT.x, FOOT.y])
	var geo := MapGeo.new(ctx)
	t.eq(geo.building_info(entry), {"size": [2, 2], "door": [0, 2]}, "what the planner is told")
	t.eq(ObjectEntries.entries(ctx).filter(func(e: Dictionary) -> bool: return e["role"] == "BUILDING").size(), 1)
	# the parts are made once for a seed
	t.eq(ObjectEntries.starter_building(ctx)["parts"], entry["parts"])
	var parts: Array = entry["parts"]
	t.eq(parts.size(), 8 + 4, "eight places for a wall and four roofs")
	var roof_part: Dictionary = parts[parts.size() - 1]
	t.eq(roof_part["kind"], "roof")
	t.eq(roof_part["lift"], STOREY, "a roof lies a storey up: as far as the wall rises on a far side")
	t.eq(IsoHouse.part_position(roof_part, Vector2i(2, 2), FOOT), Vector2(0, -STOREY), "the roof of the nearest cell")
	t.eq(IsoHouse.part_position(parts[0], Vector2i(2, 2), FOOT), Vector2(0, -FOOT.y), "the far cell's wall stands on the far cell")
	# its scene: the object recipe builds it as it builds a whole house
	var recipe := ObjectRecipe.new()
	t.eq(recipe.template_for(entry, geo.tile_px), "building")
	t.eq(recipe._build_scene(entry, OUT, geo.tile_px), OK)
	var house := (ResourceLoader.load(OUT, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate() as Node2D
	t.ok(house is StaticBody2D, "it blocks")
	t.ok(house.get_node_or_null("Sprite") == null, "it has no picture of its own")
	t.eq((house.get_node("Footprint") as CollisionPolygon2D).polygon, IsoTileset.outline(Vector2i(2, 2), FOOT), "it blocks the cells of its footprint")
	t.eq(house.get_meta("stands_on"), [2, 2])
	t.eq(house.get_meta("iso"), [FOOT.x, FOOT.y])
	t.eq(house.get_meta("role"), "BUILDING")
	t.eq(JsonUtil.to_dict(house.get_meta("kit"))["wall"], WALL + "0")
	# the door and the spawn before it, where a whole house of the packs has them
	var entrance := house.get_node("Entrance") as Area2D
	var spawn := house.get_node("ExitSpawn") as Node2D
	t.ok(entrance != null and spawn != null, "a door and a spawn")
	t.eq(spawn.get("spawn_id"), ObjectIndex.exit_spawn_id(IsoHouse.ENTRY_ID))
	# the root stands on the cell (1, 1) of the footprint; the plan's door cell is (0, 2)
	t.eq(spawn.position, Vector2(RpgIso.cell_to_screen(Vector2i(0, 2), FOOT) - RpgIso.cell_to_screen(Vector2i(1, 1), FOOT)), "who comes out stands on the plan's door cell")
	var door_side := (RpgIso.cell_to_screen(Vector2i(0, 1), FOOT) + RpgIso.cell_to_screen(Vector2i(0, 2), FOOT)) / 2.0 - RpgIso.cell_to_screen(Vector2i(1, 1), FOOT)
	t.ok(entrance.position.distance_to(door_side) < 3.0, "the trigger lies along the side the door piece stands on")
	_check_house(t, house, Vector2i(2, 2), 0, "the village's house")
	# a roof on the diagonal through the nearest corner is cut in two
	t.ok(house.get_node("Left").get_node_or_null("Roof_1_1") != null and house.get_node("Right").get_node_or_null("Roof_1_1") != null, "the roof of the nearest cell is in both halves")
	t.ok(house.get_node("Left").get_node_or_null("Roof_0_1") != null, "the roof of the cell west of it is in the left half")
	var over := house.get_node("Right").get_node_or_null("Roof_0_1") as Sprite2D
	t.ok(over == null or (over.texture as AtlasTexture).region.size.x <= 4, "... but for the pixel of its eaves that hangs over the cut")
	t.ok(house.get_node("Right").get_node_or_null("Roof_1_0") != null, "the roof of the cell north of it is in the right half")
	house.free()
	# on the footprint of a farm's plan: wider than deep, deeper than wide, the door further east
	var entries := ObjectEntries.entries(ctx)
	for want: Array in [[Vector2i(3, 2), 1], [Vector2i(2, 3), 0], [Vector2i(4, 3), 2], [Vector2i(2, 2), 1]]:
		var size: Vector2i = want[0]
		var column: int = want[1]
		var built := FarmMapRecipe.kit_building(geo, entries, Rect2i(Vector2i(8, 6), size), column)
		t.ok(built != null, "a house of pieces on %s" % size)
		if built == null:
			continue
		var outline := ((built.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points
		t.eq(outline, IsoTileset.outline(size, FOOT), "it is solid over its footprint")
		_check_house(t, built, size, column, "a farm's building on %s" % size)
		built.free()
	t.eq(FarmMapRecipe.building_entry(entries, "house", Vector2i(2, 2), 0, geo.tile_px, "", true), {}, "the farm puts it together itself")
	# a pack with a whole house is placed as it always was: no house of pieces
	var whole := _catalog()
	var tree: Dictionary = {}
	for raw: Variant in JsonUtil.to_array(whole["assets"]):
		var asset: Dictionary = raw
		if str(asset["id"]) == "iso_kit.png.tree_01_0":
			tree = asset
	tree["overrides"] = {"role": "BUILDING"}
	var whole_ctx := _context(whole)
	t.eq(str(ObjectEntries.starter_building(whole_ctx).get("id", "")), "iso_kit.png.tree_01_0")
	t.eq(ObjectEntries.entries(whole_ctx).filter(func(e: Dictionary) -> bool: return IsoHouse.is_kit(e)).size(), 0)
	# and a pack without a wall with a door has no kit
	var doorless := _catalog()
	for raw: Variant in JsonUtil.to_array(doorless["tilesets"]):
		var def: Dictionary = raw
		var tiles: Dictionary = def.get("tiles", {})
		for turn in 4:
			tiles.erase(DOOR + str(turn))
	t.eq(IsoHouse.kit(IsoTileset.new(CatalogReader.new(doorless, "isometric"))), {})
	_cleanup()

func test_a_yard_is_fenced_with_the_packs_segments(t) -> void:
	_cleanup()
	var ctx := _context(_catalog())
	t.eq(TilesetRecipe.new().build(ctx), [])
	var geo := MapGeo.new(ctx)
	geo.load_tile_set()
	var yard := Rect2i(4, 4, 3, 2)
	t.eq(FarmMapRecipe.yard_sides(Vector2i(5, 3), yard), ["s"] as Array[String], "north of the yard: the segment on its south side")
	t.eq(FarmMapRecipe.yard_sides(Vector2i(3, 4), yard), ["e"] as Array[String])
	t.eq(FarmMapRecipe.yard_sides(Vector2i(7, 5), yard), ["w"] as Array[String])
	t.eq(FarmMapRecipe.yard_sides(Vector2i(4, 6), yard), ["n"] as Array[String])
	t.eq(FarmMapRecipe.yard_sides(Vector2i(3, 3), yard), [] as Array[String], "a corner of the fence: the segments beside it meet there")
	var piece := FarmMapRecipe.make_edge_fence(geo.iso, FENCE + "0", ["s"] as Array[String], FOOT)
	t.ok(piece is StaticBody2D and piece.get("blocks_movement") == true)
	t.eq(((piece.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, RpgFarmIso.diamond(FOOT, 1.0), "it closes its diamond")
	var sprite := piece.get_node("Sprite") as Sprite2D
	t.eq(sprite.get_meta("asset_id"), FENCE + "1", "the member that stands along the south side")
	t.eq(sprite.offset, -Vector2(36, 68), "the middle of its diamond on the middle of the cell")
	piece.free()
	var corner := FarmMapRecipe.make_edge_fence(geo.iso, FENCE + "0", [] as Array[String], FOOT)
	t.ok(corner.get_node_or_null("Sprite") == null and corner.get_node_or_null("Shape") != null)
	corner.free()
	_cleanup()
