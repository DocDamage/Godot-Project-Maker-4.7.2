extends RefCounted
## The editor dock on diamonds (T17.27): what the dock places in an isometric map stands on the
## middle of the diamond under the mouse, as the builder stands it; an object of several
## diamonds covers the cells the builder says; the world tools and the world repair give what
## they add the shape of a cell. The maps are built as a recipe builds them, from the tile set of
## the isometric fixture pack (tests/fixtures/iso_tiles). A map of squares is placed in as it
## was: test_placement.gd and test_world_repair.gd are unchanged, and the last test here says
## what must not have moved.
##
## What no test of this file can do is press Ctrl+Z in the editor: `Placement.apply` takes the
## editor's own undo manager, which exists only in a running editor. The undo of a placement is
## run there by tests/integration/test_m17_isometric.py; here the validator's Fix, which also
## takes a plain UndoRedo, is undone on diamonds.

const Placement := preload("res://addons/rpg_project_tools/dock/placement.gd")
const Repair := preload("res://addons/rpg_project_tools/tools/world_repair.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")
const ValidatorPanel := preload("res://addons/rpg_project_tools/dock/validator_panel.gd")
const Tool := preload("res://builder/tools/world_repair.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")
const TilesetRecipe := preload("res://builder/recipes/tileset_recipe.gd")
const ObjectRecipe := preload("res://builder/recipes/object_scenes_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")
const IsoTileset := preload("res://builder/lib/iso_tileset.gd")
const MapGeo := preload("res://builder/lib/map_geo.gd")
const MapUtil := preload("res://builder/lib/map_util.gd")
const JsonUtil := preload("res://builder/lib/json_util.gd")

const FIXTURE := "res://tests/fixtures/iso_tiles/catalog.json"
const TS_PATH := "res://generated/tilesets/iso.tres"
const STATE_PATH := "res://rpggen/tileset_apply_state.json"
const HOUSE_PICTURE := "res://tests/fixtures/iso_tiles/house.png"
const OUT := "user://test_placement_iso_object.tscn"
const DIR := "user://placement_iso"
const FOOT := Vector2i(60, 34)
const UNIT := 34  # a step from a diamond of 60 x 34 to the next is 34.48 px
const SIZE := Vector2i(12, 8)
const WALL := "iso_tiles.png.isotile_019_"

var _roots: Array[Node] = []

# ---------------------------------------------------------------- a map as a recipe builds it

## The fixture's catalog with a wall, as the audit would name one (the pack names none).
func _catalog() -> Dictionary:
	var cat := JsonUtil.to_dict(JsonUtil.read(FIXTURE)).duplicate(true)
	for raw: Variant in JsonUtil.to_array(cat["assets"]):
		var asset: Dictionary = raw
		if str(asset["id"]).begins_with(WALL):
			asset["overrides"] = {"role": "WALL"}
	return cat

func _geo() -> MapGeo:
	var ctx := BuildContext.new("res://builder")
	ctx.config = {"projection": "isometric", "features": {"navigation": false}, "seed": 7, "map_layers": MapUtil.DEFAULT_LAYERS.duplicate()}
	ctx.catalog = CatalogReader.new(_catalog(), "isometric")
	TilesetRecipe.new().build(ctx)
	var geo := MapGeo.new(ctx)
	geo.load_tile_set()
	return geo

## A map of SIZE diamonds: ground everywhere, the packs' wall around it when `walled`.
func _map(geo: MapGeo, id: String, walled: bool = false) -> Node2D:
	var root := MapUtil.new_map_root("Map", id)
	var nodes := MapUtil.build_layers(root, MapUtil.DEFAULT_LAYERS, geo.tile_set)
	var ground: TileMapLayer = nodes["Ground"]
	MapUtil.fill(ground, Rect2i(Vector2i.ZERO, SIZE), geo.find_tile("GROUND"))
	if walled:
		geo.paint_walls(root, nodes, SIZE)
	return root

func _cleanup() -> void:
	for root in _roots:
		if is_instance_valid(root):
			root.free()
	_roots.clear()
	for p: String in [TS_PATH, STATE_PATH, OUT]:
		if FileAccess.file_exists(p):
			DirAccess.remove_absolute(p)
	Maps.remove_tree(DIR)

func _entry(entry_name: String = "x", role: String = "", tags: Array = []) -> Dictionary:
	return {"name": entry_name, "role": role, "tags": tags}

## Something the editor dropped at `at` under the scene's root.
func _dropped(root: Node, at: Vector2) -> Node2D:
	var node := Node2D.new()
	root.add_child(node)
	node.position = at
	return node

# ---------------------------------------------------------------- one diamond

func test_a_drop_lands_on_the_diamond_under_the_mouse(t) -> void:
	_cleanup()
	var geo := _geo()
	var root := _map(geo, "m")
	var entities := Maps.entities_of(root)
	var placement := Placement.new()
	placement.snap = 16  # the dock's "Tile" in a project whose tile set is not called overworld
	t.eq(Placement.diamond_of(root), FOOT)
	for cell: Vector2i in [Vector2i(0, 0), Vector2i(7, 3), Vector2i(11, 7), Vector2i(2, 6)]:
		var middle := RpgIso.cell_to_screen(cell, FOOT)
		t.eq(middle, geo.center(cell), "where the builder puts what stands on %s" % cell)
		var corners := RpgIso.diamond(cell, FOOT)
		var points: Array[Vector2] = [middle]
		# the four quadrants of the diamond
		for by: Vector2 in [Vector2(1, 1), Vector2(-1, 1), Vector2(-1, -1), Vector2(1, -1)]:
			points.append(middle + Vector2(by.x * FOOT.x / 8.0, by.y * FOOT.y / 8.0))
		# nearly in its four corners, and nearly on the middle of its four sides
		for i in 4:
			points.append(middle + (corners[i] - middle) * 0.9)
			points.append(middle + ((corners[i] + corners[(i + 1) % 4]) / 2.0 - middle) * 0.9)
		for at in points:
			var dropped := _dropped(root, at)
			var plan := placement.plan(dropped, root, _entry())
			t.eq(plan["position"], middle, "a drop at %s is on the diamond %s" % [at, cell])
			t.eq(plan["cell"], cell)
			t.eq(plan["cells"], [cell] as Array[Vector2i], "it stands on that one cell")
			t.eq(plan["parent"], entities, "among the Y-sorted entities, as on squares")
			t.eq(plan["old_position"], at)
			dropped.free()
		# across a side it is the neighbour's
		for i in 4:
			var beyond := middle + ((corners[i] + corners[(i + 1) % 4]) / 2.0 - middle) * 1.2
			var dropped := _dropped(root, beyond)
			var plan := placement.plan(dropped, root, _entry())
			var by: Vector2i = RpgIso.STEPS[RpgIso.SIDES[i]]
			t.eq(plan["cell"], cell + by, "across side %s of %s" % [RpgIso.SIDES[i], cell])
			t.eq(plan["position"], RpgIso.cell_to_screen(cell + by, FOOT))
			dropped.free()
	root.free()
	_cleanup()

func test_snapping_on_diamonds(t) -> void:
	_cleanup()
	var geo := _geo()
	var root := _map(geo, "m")
	var at := RpgIso.cell_to_screen(Vector2i(4, 2), FOOT) + Vector2(7, -5)
	var placement := Placement.new()
	var dropped := _dropped(root, at)
	# off: where it was dropped, and the plan still says on which diamond that is
	placement.snap = 0
	var free_plan := placement.plan(dropped, root, _entry())
	t.eq(free_plan["position"], at)
	t.eq(free_plan["cell"], Vector2i(4, 2))
	# every other choice of the dock is the middle of the diamond: 8, the tile, 32, a custom step
	for step: int in [8, 16, 32, 5, 200]:
		placement.snap = step
		t.eq(placement.plan(dropped, root, _entry())["position"], RpgIso.cell_to_screen(Vector2i(4, 2), FOOT), "snap %d" % step)
	t.eq(Placement.snap_to_diamond(root, at, 0), at)
	t.eq(Placement.snap_to_diamond(root, at, 16), RpgIso.cell_to_screen(Vector2i(4, 2), FOOT))
	# the map's layer and the entities' node may lie anywhere: the layer is asked for the cell,
	# and the position is the new parent's own
	var ground := root.get_node("Ground") as TileMapLayer
	ground.position = Vector2(10, 6)
	Maps.entities_of(root).position = Vector2(100, 0)
	placement.snap = 16
	var moved := placement.plan(dropped, root, _entry())
	var cell: Vector2i = moved["cell"]
	t.eq(cell, RpgIso.screen_to_cell(at - Vector2(10, 6), FOOT))
	t.eq(moved["position"], RpgIso.cell_to_screen(cell, FOOT) + Vector2(10, 6) - Vector2(100, 0))
	dropped.free()
	# the double click: nothing is in the map yet, the point is the middle of the view
	ground.position = Vector2.ZERO
	Maps.entities_of(root).position = Vector2.ZERO
	var detached := Node2D.new()
	var plan := placement.plan(detached, root, _entry(), null, RpgIso.cell_to_screen(Vector2i(9, 1), FOOT) + Vector2(-11, 4))
	t.eq(plan["position"], RpgIso.cell_to_screen(Vector2i(9, 1), FOOT))
	t.ok(plan["old_parent"] == null)
	detached.free()
	root.free()
	_cleanup()

# ---------------------------------------------------------------- several diamonds

func _house(stands_on: Array) -> Dictionary:
	return {
		"id": "pack.house", "name": "house", "role": "DECORATION", "tags": [],
		"texture_path": HOUSE_PICTURE, "region": [0, 0, 60, 64], "origin": [30, 39],
		"footprint": [], "collision": {"profile": "FULL"}, "door": [], "sha256": "", "open_region": [],
		"iso": [60, 34], "stands_on": stands_on,
	}

## The library scene the builder makes of an isometric object entry.
func _built(entry: Dictionary) -> Node2D:
	var err: int = ObjectRecipe.new()._build_scene(entry, OUT, UNIT)
	if err != OK:
		return null
	return (ResourceLoader.load(OUT, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate() as Node2D

func test_an_object_of_several_diamonds_covers_the_cells_the_builder_says(t) -> void:
	_cleanup()
	var geo := _geo()
	var root := _map(geo, "m")
	var placement := Placement.new()
	placement.snap = 16
	var cell := Vector2i(7, 4)
	for size: Vector2i in [Vector2i(1, 1), Vector2i(2, 1), Vector2i(2, 2), Vector2i(1, 2), Vector2i(3, 2)]:
		var entry := _house([size.x, size.y])
		var house := _built(entry)
		t.ok(house != null, "the scene of a %s object is built" % size)
		if house == null:
			continue
		t.eq(Placement.stands_on(house), size, "the scene says what it stands on")
		root.add_child(house)
		house.position = RpgIso.cell_to_screen(cell, FOOT) + Vector2(9, 5)  # the mouse, on the cell
		var plan := placement.plan(house, root, _entry("house", "DECORATION"))
		var cells: Array[Vector2i] = plan["cells"]
		t.eq(cells, IsoTileset.cells_under(cell, entry), "%s: the cells IsoTileset.cells_under says" % size)
		t.eq(cells.size(), size.x * size.y)
		t.eq(plan["cell"], cell, "the diamond under the mouse is the one nearest the camera")
		# the builder puts such an object by its first cell: the same place
		var first := cell - size + Vector2i.ONE
		t.eq(plan["position"], geo.building_position(entry, first), "%s: where the builder stands it" % size)
		var at: Vector2 = plan["position"]
		house.position = at
		# what blocks is the outline of exactly those cells
		var outline := PackedVector2Array()
		for corner in (house.get_node("Footprint") as CollisionPolygon2D).polygon:
			outline.append(corner + house.position)
		t.eq(outline, geo.cells_outline(Rect2i(first, size)), "%s: its footprint lies on its cells" % size)
		for under in cells:
			t.ok(Geometry2D.is_point_in_polygon(RpgIso.cell_to_screen(under, FOOT), outline), "%s is under it" % under)
		for beside: Vector2i in [first - Vector2i(1, 0), first - Vector2i(0, 1), cell + Vector2i(1, 0), cell + Vector2i(0, 1)]:
			t.ok(not cells.has(beside) and not Geometry2D.is_point_in_polygon(RpgIso.cell_to_screen(beside, FOOT), outline), "%s is not" % beside)
		# sorted with what is there: its halves sort by the corners of what it stands on, among
		# the entities of the map (RpgIso.sort_keys: [split x, left key, right key])
		var keys := RpgIso.sort_keys(Rect2i(first, size), FOOT)
		t.eq(house.position.x, keys[0], "%s: cut at its nearest corner" % size)
		var left := house.get_node("Sprite") as Sprite2D
		var right := house.get_node_or_null("SpriteRight") as Sprite2D
		if size == Vector2i.ONE:
			t.eq(house.position.y, RpgIso.depth(cell, FOOT), "one diamond sorts by its middle")
		else:
			t.ok(house.y_sort_enabled, "its halves sort among the map's entities")
			t.eq(house.position.y + left.position.y, keys[1], "%s: the left half" % size)
			if right != null:
				t.eq(house.position.y + right.position.y, keys[2], "%s: the right half" % size)
			else:
				t.eq(keys[1], keys[2], "a square of cells is one picture")
		t.eq(plan["parent"], Maps.entities_of(root))
		t.ok((plan["parent"] as Node2D).y_sort_enabled)
		root.remove_child(house)
		house.free()
	for size: Vector2i in [Vector2i(1, 1), Vector2i(2, 1), Vector2i(1, 2), Vector2i(2, 2), Vector2i(4, 3)]:
		t.eq(Placement.cells_under(Vector2i(10, 7), size), IsoTileset.cells_under(Vector2i(10, 7), {"stands_on": [size.x, size.y]}), "%s cells, as the builder counts them" % size)
	t.eq(Placement.stands_on(root), Vector2i.ONE, "anything else stands on one cell")
	root.free()
	_cleanup()

# ---------------------------------------------------------------- actors and markers

func test_actors_and_markers_snap_the_same_way_and_keep_their_ids(t) -> void:
	_cleanup()
	var geo := _geo()
	var root := _map(geo, "isle")
	var entities := Maps.entities_of(root)
	Maps.entity(entities, "Npc1", "isle_npc_002", true, geo.center(Vector2i(2, 2)))
	var placement := Placement.new()
	placement.snap = 16
	var cell := Vector2i(6, 5)
	var villager := Maps.entity(root, "Villager", "", true, geo.center(cell) + Vector2(-8, 3))
	var plan := placement.plan(villager, root, _entry("Villager", "NPC"))
	t.eq(plan["position"], geo.foot(cell), "an actor's feet are on the middle of its diamond")
	t.eq(plan["entity_id"], "isle_npc_003", "the id a placement on squares gives")
	t.eq([plan["kind"], plan["map_id"], plan["number"]], ["npc", "isle", 3])
	t.eq(plan["old_parent"], root)
	t.eq(plan["parent"], entities)
	var chest := Maps.entity(root, "Chest", "", true, geo.center(Vector2i(3, 1)) + Vector2(5, 5))
	var chest_plan := placement.plan(chest, root, _entry("Chest", "DECORATION", ["chest"]))
	t.eq(chest_plan["position"], geo.center(Vector2i(3, 1)))
	t.eq(chest_plan["entity_id"], "isle_chest_001")
	var marker := Maps.spawn(root, "from_town", "from_town")
	marker.position = geo.center(Vector2i(1, 6)) + Vector2(4, -6)
	var marker_plan := placement.plan(marker, root, _entry("from_town"))
	t.eq(marker_plan["position"], geo.center(Vector2i(1, 6)), "a spawn point is where the builder's is")
	t.eq(marker_plan["entity_id"], "")
	# the flip is what it is on squares
	var sprite := Sprite2D.new()
	villager.add_child(sprite)
	placement.flip_h = true
	t.eq(placement.plan(villager, root, _entry("Villager", "NPC"))["flip_node"], sprite)
	root.free()
	_cleanup()

# ---------------------------------------------------------------- the world tools

func test_the_world_tools_add_diamonds(t) -> void:
	_cleanup()
	var geo := _geo()
	var root := _map(geo, "isle")
	var cell := Vector2i(5, 3)
	var at := geo.center(cell) + Vector2(6, -4)
	var want := IsoTileset.diamond(FOOT)
	t.eq(RpgIso.cell_shape(FOOT).points, want, "RpgIso's shape of a cell is the builder's")
	t.eq(RpgIso.cell_shape(FOOT).points, (geo.cell_shape() as ConvexPolygonShape2D).points)
	for footprint: Vector2i in [Vector2i(180, 104), Vector2i(120, 74), Vector2i(40, 22), Vector2i(33, 17)]:
		t.eq(RpgIso.cell_shape(footprint).points, IsoTileset.diamond(footprint), "of %s too" % footprint)
	# a trigger area: the diamond of its cell
	var plan := Placement.plan_trigger(root, at, UNIT, UNIT, false, "user://seq_test")
	t.eq(plan["position"], geo.center(cell))
	t.eq(plan["entity_id"], "isle_trigger_001")
	t.eq(plan["parent"], root.get_node("Triggers"))
	var area := Placement.build_trigger(plan)
	t.ok(area is RpgTriggerArea)
	t.eq(((area.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, want)
	t.eq(area.position, geo.center(cell))
	area.free()
	# a gate closes its diamond, as the builder's does; a switch keeps the square it makes
	var gate_plan := Placement.plan_lock(root, at, UNIT, "gate")
	t.eq(gate_plan["position"], geo.gate_position(cell), "where the builder puts a gate")
	t.eq(gate_plan["size"], Vector2(UNIT, UNIT))
	t.eq(gate_plan["parent"], Maps.entities_of(root))
	var gate := Placement.build_lock(gate_plan)
	t.ok(gate is RpgGate)
	t.eq(((gate.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, want)
	gate.free()
	var plate_plan := Placement.plan_lock(root, at, UNIT, "plate")
	t.eq(plate_plan["position"], geo.center(cell))
	var plate := Placement.build_lock(plate_plan)
	t.eq(plate.get_child_count(), 0)
	t.eq(plate.get("size"), Vector2(UNIT, UNIT) * 0.75)
	plate.free()
	# an encounter zone with nothing selected: 6 x 6 diamonds around the cell under the point
	var zone := Placement.plan_zone(root, [], at, UNIT, "user://none", "user://none")
	var polygon: PackedVector2Array = zone["polygon"]
	var outline := geo.cells_outline(Rect2i(cell - Vector2i(3, 3), Vector2i(6, 6)))
	t.eq(polygon.size(), 4)
	for i in 4:
		t.eq(polygon[i], outline[i].snapped(Vector2(1, 1)), "corner %d of the zone" % i)
	t.eq(Placement.cells_outline(root, Rect2i(2, 1, 3, 2)), geo.cells_outline(Rect2i(2, 1, 3, 2)))
	root.free()
	_cleanup()

# ---------------------------------------------------------------- the world repair

func _path(id: String) -> String:
	return DIR + "/maps/%s.tscn" % id

func _instance(path: String) -> Node:
	var root := (ResourceLoader.load(path, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene).instantiate(PackedScene.GEN_EDIT_STATE_MAIN)
	_roots.append(root)
	return root

func _plan(ids: Array) -> Array[Dictionary]:
	var paths: Array[String] = []
	for id: String in ids:
		paths.append(_path(id))
	var cache := {}
	return Repair.plan_repairs(paths, {}, func(path: String) -> Node:
		if not cache.has(path):
			cache[path] = _instance(path)
		return cache[path], _path("a"))

func _codes() -> Array:
	var out: Array = []
	for finding: Dictionary in ContentChecks.run({"maps": DIR + "/maps", "start": _path("a"), "world_plan": DIR + "/none.json", "dialogue": DIR + "/x", "items": DIR + "/x", "resources": [DIR + "/x"], "placeholders": DIR + "/x/"}):
		out.append(finding["code"])
	return out

func test_the_repair_counts_diamonds_and_its_door_is_one(t) -> void:
	_cleanup()
	DirAccess.make_dir_recursive_absolute(DIR + "/maps")
	var geo := _geo()
	var a := _map(geo, "a", true)
	var info := Repair.survey(a)
	t.eq(info["iso"], FOOT)
	t.eq(info["tile"], UNIT, "a tile is one step")
	t.eq(info["rect"], Rect2i(Vector2i.ZERO, SIZE))
	t.ok(Repair.walkable(info, Vector2i(1, 1)) and not Repair.walkable(info, Vector2i(0, 1)) and not Repair.walkable(info, Vector2i(11, 4)), "the far and the near walls are solid")
	t.eq(Repair.cell_of(info, geo.center(Vector2i(4, 6)) + Vector2(9, 3)), Vector2i(4, 6))
	t.eq(Repair.center_of(info, Vector2i(4, 6)), geo.center(Vector2i(4, 6)))
	t.eq(Repair.place_on_edge(info, "W"), {"door": Vector2i(1, 4), "spawn": Vector2i(2, 4)}, "edges are the grid's, whatever the view")
	# a door of a that arrives nowhere in b
	var door := Maps.door(a.get_node("Triggers"), "ToB", _path("b"), "from_a")
	door.position = geo.center(Vector2i(10, 3))
	Maps.save(a, _path("a"))
	Maps.save(_map(geo, "b", true), _path("b"))
	t.eq(_codes(), ["VAL-017"])
	var actions := _plan(["a", "b"])
	var kinds: Array = []
	for action in actions:
		kinds.append("%s:%s" % [action["kind"], str(action["map"]).get_file().get_basename()])
	t.eq(kinds, ["spawn:b", "spawn:a", "door:b"], "what it does on squares")
	t.eq(actions[0]["position"], geo.center(Vector2i(2, 3)), "the opposite edge, the same offset, one cell in from the door")
	t.eq(actions[0]["facing"], "right")
	t.eq(actions[1]["position"], geo.center(Vector2i(9, 3)))
	t.eq(actions[2]["position"], geo.center(Vector2i(1, 3)), "the door stands on the middle of its diamond")
	t.eq(actions[2]["iso"], FOOT)
	t.eq(actions[2]["tile"], UNIT)
	# the door the repair builds is the door the builder builds on that cell
	var built := Repair.build(actions[2])
	var holder := Node2D.new()
	var owner_root := Node2D.new()
	owner_root.add_child(holder)
	var builders := geo.add_exit_door(holder, owner_root, "builders", Vector2i(1, 3), _path("a"), &"from_b")
	var shape := (built.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D
	t.ok(shape != null, "a diamond, not a rectangle")
	if shape != null:
		t.eq(shape.points, ((builders.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points)
		t.eq(shape.points, IsoTileset.diamond(FOOT))
	t.eq(built.position, builders.position)
	t.eq([built.collision_layer, built.collision_mask], [builders.collision_layer, builders.collision_mask])
	t.eq([built.get("target_map"), built.get("target_spawn")], [builders.get("target_map"), builders.get("target_spawn")])
	t.eq((built.get_node("Shape") as Node2D).position, (builders.get_node("Shape") as Node2D).position)
	built.free()
	owner_root.free()
	# the headless tool writes it; the validator finds nothing more; a second run does nothing
	var result := Tool.run(DIR + "/maps", {}, false, false, [] as Array[String], _path("a"))
	t.eq(result["repairs"].size(), 3)
	t.eq(result["unfixable"], [])
	t.eq(_codes(), [], "mended")
	t.eq(_plan(["a", "b"]), [] as Array[Dictionary])
	var again := _instance(_path("b")) as Node2D
	var saved := again.get_node("Triggers/b_door_a") as Area2D
	t.eq(saved.position, geo.center(Vector2i(1, 3)))
	t.eq(((saved.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, IsoTileset.diamond(FOOT), "saved with the scene")
	t.eq((again.get_node("SpawnPoints/from_a") as Node2D).position, geo.center(Vector2i(2, 3)))
	t.eq(Repair.cell_of(Repair.survey(again), saved.position), Vector2i(1, 3))
	_cleanup()

func test_a_map_of_diamonds_that_cannot_be_reached_gets_a_door_pair(t) -> void:
	_cleanup()
	DirAccess.make_dir_recursive_absolute(DIR + "/maps")
	var geo := _geo()
	Maps.save(_map(geo, "a", true), _path("a"))
	Maps.save(_map(geo, "c", true), _path("c"))
	t.eq(_codes(), ["VAL-027"])
	var actions := _plan(["a", "c"])
	t.eq(actions.size(), 4)
	for action in actions:
		var at: Vector2 = action["position"]
		var cell := RpgIso.screen_to_cell(at, FOOT)
		t.eq(at, geo.center(cell), "%s is on the middle of the diamond %s" % [action["node"], cell])
		t.ok(cell.x > 0 and cell.y > 0 and cell.x < SIZE.x - 1 and cell.y < SIZE.y - 1, "inside the walls")
		t.eq(action["iso"], FOOT)
	var result := Tool.run(DIR + "/maps", {}, false, false, [] as Array[String], _path("a"))
	t.eq(result["repairs"].size(), 4)
	t.eq(_codes(), [])
	_cleanup()

func test_the_validators_fix_on_diamonds_is_one_undo_step(t) -> void:
	_cleanup()
	var geo := _geo()
	var a := _map(geo, "a", true)
	var triggers := a.get_node("Triggers")
	var undo := UndoRedo.new()
	var action := {"kind": "door", "map": "a", "node": "Triggers/a_door_c", "name": "a_door_c", "position": geo.center(Vector2i(1, 4)), "target_map": "c", "target_spawn": "from_a", "what": "w", "tile": UNIT, "iso": FOOT}
	ValidatorPanel.do_fix(action, a, undo)
	t.eq(triggers.get_child_count(), 1)
	var door := triggers.get_child(0) as Area2D
	t.eq(door.position, geo.center(Vector2i(1, 4)))
	t.eq(((door.get_node("Shape") as CollisionShape2D).shape as ConvexPolygonShape2D).points, IsoTileset.diamond(FOOT))
	t.eq(door.owner, a)
	t.eq(door.get_node("Shape").owner, a, "the diamond is saved with the scene")
	t.ok(undo.undo())
	t.eq(triggers.get_child_count(), 0, "Ctrl+Z takes the door away again")
	t.ok(undo.redo())
	t.eq(triggers.get_child_count(), 1)
	t.eq((triggers.get_child(0) as Node2D).position, geo.center(Vector2i(1, 4)))
	undo.free()
	a.free()
	_cleanup()

# ---------------------------------------------------------------- squares

func test_a_map_of_squares_is_not_asked_about_diamonds(t) -> void:
	var root := Maps.map("m")
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	var layer := TileMapLayer.new()
	layer.name = "Ground"
	layer.tile_set = ts
	root.add_child(layer)
	t.eq(Placement.diamond_of(root), Vector2i.ZERO)
	var bare := Maps.map("bare")
	t.eq(Placement.diamond_of(bare), Vector2i.ZERO, "nor a map without tiles")
	var placement := Placement.new()
	placement.snap = 16
	for map: Node2D in [root, bare]:
		var dropped := _dropped(map, Vector2(21, 13))
		var plan := placement.plan(dropped, map, _entry())
		t.eq(plan["position"], Vector2(16, 16), "the grid of px it always was")
		var keys := plan.keys()
		keys.sort()
		t.eq(keys, ["entity_id", "flip", "flip_node", "kind", "map_id", "number", "old_entity_id", "old_flip", "old_parent", "old_position", "parent", "position"], "the plan it always was")
	var trigger := Placement.plan_trigger(root, Vector2(37, 21), 16, 16, true, "user://seq_test")
	t.ok(not trigger.has("diamond"))
	var area := Placement.build_trigger(trigger)
	t.eq(((area.get_node("Shape") as CollisionShape2D).shape as RectangleShape2D).size, Vector2(16, 16))
	area.free()
	var lock := Placement.plan_lock(root, Vector2(37, 21), 16, "gate")
	t.ok(not lock.has("diamond"))
	t.eq(lock["position"], Vector2(32, 16))
	var gate := Placement.build_lock(lock)
	t.eq(gate.get_child_count(), 0, "a gate on squares makes its own rectangle")
	gate.free()
	var zone := Placement.plan_zone(root, [], Vector2(100, 100), 16, "user://none", "user://none")
	t.eq(zone["polygon"], PackedVector2Array([Vector2(52, 52), Vector2(148, 52), Vector2(148, 148), Vector2(52, 148)]))
	var door := Repair.build({"kind": "door", "name": "d", "position": Vector2(24, 24), "target_map": "x", "target_spawn": "y", "tile": 16})
	t.eq(((door.get_node("Shape") as CollisionShape2D).shape as RectangleShape2D).size, Vector2(16, 16))
	door.free()
	bare.free()
	root.free()
