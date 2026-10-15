extends RefCounted
## The maps added to a farm (T17.23): a forest and a beach, each a map of its own, built from
## the stored plan (`rpggen/world_plan.json`, the list `farm.map.added`, planned by
## rpggen/core/added_map_plan.py), and the farm's side of the doors to them.
##
## * game/maps/<id>.tscn for every entry of the plan (`farm_map_1`, `farm_map_2`, ...), **once**
##   (user_seed ownership): a map that exists is never built again, and a row that is added
##   later builds one more map and touches no other. On it, whatever its kind: the layers of a
##   top-down map with the `Soil` layer and the `Field` (so the tools work there: the axe and the
##   sickle clear what the plan lays down, and the rod is cast at cells whose tile says `water`),
##   the edge with the one gap that is the way back to the farm (the door `to_farm`, the spawn
##   `from_farm`), trees, scenery and things to clear as the farm has them
##   (farm_map_recipe.gd's own: the packs' pictures by their words, else drawn), and the places
##   where things to forage lie (`Forage/Spot1` ...). Its root says what it is with the metadata
##   `farm_kind` (RpgForage.KIND_META: a beach has things of its own), and the map is no
##   interior: the weather, the seasons and the light of the day are the farm's.
##   - a **forest** (`kind`): the ground of the farm under a shade (`Shade`), a path to its
##     clearing;
##   - a **beach**: sand (the packs' ground tile the plan names, else drawn: `Sand`), the sea
##     along one side (the packs' water tile, else the drawn water of the `Soil` layer; its
##     cells carry the `water` data, and the root says `farm_water`: `sea`, RpgFishing.WATER_META,
##     so the fish of the sea bite there), `Markers/FishFrom` where the rod is cast from.
## * generated/scenes/farm/trails.tscn, **on every build**: the farm's side of every door pair.
##   The farm's map instances this scene once, when it is built (`Trails`, farm_map_recipe.gd),
##   and is never written again; what the scene holds grows with the plan: for every added map
##   the door `to_<id>` on the cell of the trail the plan gave it (`farm.map.trails`: beside the
##   edge of the farm, set aside when the farm was planned), the spawn `from_<id>` one cell
##   further in, and a worn patch of ground with an arrow (`Mark_<id>`) so that the door can be
##   seen. A farm without added maps has the scene with nothing in it.
##
## **Squares or diamonds.** Everything goes through the seam of the map recipes
## (builder/lib/map_geo.gd), as the farm's map does: the same plan is painted with square tiles
## or with the project's diamonds.
##
## `build_map` is one function for every kind; what a kind has of its own is in `_add_ground`
## (the `match` on the kind) and, for a cave, `_add_enemies` after `_add_common`.
##   - a **cave** (T17.24, a farm that fights): the farm's ground in the gloom (`Gloom`), the
##     rock the plan names (`walls`) and the edge drawn over it (`Rock`; the edge blocks as
##     every edge does, the rock where it meets the floor: the body `RockWall`), no path and no
##     wall tile, boulders, the places where the things of a cave lie, and the
##     action RPG's enemies (recipes/arpg/enemy_recipes.gd, which a farm that fights has: the
##     packs' ENEMY, else the drawn slime of the farm kit) at the cells the plan names, each
##     remembered as `<id>_enemy_<n>` (RpgFarmFight brings them back every morning). Its root
##     is an interior (`is_interior`): no rain falls there, and its light is a cave's
##     (`ambient_override`, darker than a room's). The packs' own rock lies over the drawn one
##     where they have it (cave_rock.gd: a cell of a picture of rock seen from above, a tile of
##     rock on diamonds, else their boulders), and an enemy drawn much smaller than the farmer
##     is scaled to stand ENEMY_HEIGHT of the farmer's height (`scale_to_farmer`).
## * The ground of every map but a beach with sand of its own is the farm's plain ground tile
##   where rpggen found one (`farm.ground`, builder/lib/plain_ground.gd).

const RECIPE_VERSION := 2
## The version of what the recipe does for an isometric project only: in the hash of such a
## project and of no other.
const ISO_VERSION := 1

const JsonUtil := preload("../../lib/json_util.gd")
const SceneUtil := preload("../../lib/scene_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const MapBuild := preload("../../lib/map_build.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const ObjectEntries := preload("../../lib/object_entries.gd")
const BuildContext := preload("../../lib/build_context.gd")
const FarmBuild := preload("farm_build.gd")
const FieldRecipe := preload("field_recipe.gd")
const FarmMapRecipe := preload("farm_map_recipe.gd")
const CaveRock := preload("cave_rock.gd")
const PlainGround := preload("../../lib/plain_ground.gd")

const TRAILS_SCENE := FarmBuild.TRAILS_SCENE
const TRAILS_NODE := FarmBuild.TRAILS_NODE
const FARM_PATH := "res://game/maps/farm.tscn"
const PLAYER_SCENE := "res://generated/scenes/actors/player.tscn"
## The door pair of an added map: its way back is the door `to_farm` and leads to the farm's
## spawn `from_<id>`; the farm's door `to_<id>` leads to its spawn `from_farm`.
const BACK_DOOR := "to_farm"
const FROM_FARM := "from_farm"
const KIND_META := &"farm_kind"
const WATER_META := &"farm_water"
const FOREST := "forest"
const BEACH := "beach"
const CAVE := "cave"
## The action RPG's enemies (a farm that fights has the folder: staging.OPTIONAL_FOLDERS).
const ENEMY_RECIPES := "../arpg/enemy_recipes.gd"
const GLOOM := Color(0.04, 0.03, 0.06, 0.55)
const ROCK := Color(0.2, 0.18, 0.19)
## The light of a cave (RpgMapRoot.ambient_override): darker and bluer than the light of a room.
const CAVE_LIGHT := Color(0.5, 0.48, 0.6)
## How tall an enemy of a cave stands beside the farmer (`_scale_to_farmer`).
const ENEMY_HEIGHT := 0.7

const SAND := Color(0.89, 0.82, 0.59)
const SAND_DARK := Color(0.86, 0.79, 0.56)
const SHADE := Color(0.05, 0.2, 0.08, 0.3)
const TRAIL := Color(0.62, 0.5, 0.33)
const TRAIL_ARROW := Color(0.93, 0.87, 0.7)

# ---------------------------------------------------------------- the plan

## The added maps of the stored plan (`farm.map.added`), in its order.
static func entries() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(FarmMapRecipe.plan().get("added", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

## The trails of the stored plan (`farm.map.trails`), in its order.
static func trails() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(FarmMapRecipe.plan().get("trails", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

static func map_id(entry: Dictionary) -> String:
	return JsonUtil.to_str(entry.get("id", ""))

static func map_path(entry: Dictionary) -> String:
	return "res://" + JsonUtil.to_str(entry.get("map", ""))

## The door of the farm that leads to an added map, and the spawn the farmer comes back to.
static func door_name(entry: Dictionary) -> String:
	return "to_" + map_id(entry)

static func spawn_name(entry: Dictionary) -> String:
	return "from_" + map_id(entry)

## The trail of the farm an added map uses, or {} when the plan gave it none.
static func trail_of(entry: Dictionary, found: Array[Dictionary]) -> Dictionary:
	var at := JsonUtil.to_int(entry.get("trail", -1), -1)
	return found[at] if at >= 0 and at < found.size() else {}

## The cells of the sea of an entry that touch the land (to the four sides): what keeps the
## farmer out of the water. The rest of the sea is behind them.
static func shore_cells(water: Array[Vector2i], size: Vector2i) -> Array[Vector2i]:
	var wet := {}
	for cell in water:
		wet[cell] = true
	var out: Array[Vector2i] = []
	for cell in water:
		for step: Vector2i in [Vector2i.UP, Vector2i.LEFT, Vector2i.RIGHT, Vector2i.DOWN]:
			var beside := cell + step
			var inside := beside.x >= 0 and beside.y >= 0 and beside.x < size.x and beside.y < size.y
			if inside and not wet.has(beside):
				out.append(cell)
				break
	return out

## The cells of the inside of a map of `size` cells that are not in `without`, as runs along a
## row: [Rect2i] one row high, row by row. What a drawn ground is laid as.
static func row_runs(size: Vector2i, without: Array[Vector2i]) -> Array[Rect2i]:
	var skip := {}
	for cell in without:
		skip[cell] = true
	var out: Array[Rect2i] = []
	for y in range(1, size.y - 1):
		var start := -1
		for x in range(1, size.x):
			var open := x < size.x - 1 and not skip.has(Vector2i(x, y))
			if open and start < 0:
				start = x
			elif not open and start >= 0:
				out.append(Rect2i(start, y, x - start, 1))
				start = -1
	return out

# ---------------------------------------------------------------- the recipe

## The trails' scene on every build, and only the maps that do not exist yet.
func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([TRAILS_SCENE])
	for entry in entries():
		if not FileAccess.file_exists(map_path(entry)):
			out.append(map_path(entry))
	return out

func input_hash(ctx: BuildContext) -> String:
	var hashed := {
		"v": RECIPE_VERSION,
		"added": entries(),
		"trails": trails(),
		"overworld": ctx.catalog.tileset_def("overworld"),
		"layers": ctx.config.get("map_layers", []),
		"ground": JsonUtil.to_str(ctx.section("starter_map").get("ground", "")),
		"music": JsonUtil.to_str(ctx.section("sounds").get("music_map", "")),
		"entries": ObjectEntries.entries(ctx),
		"field": FieldRecipe.RECIPE_VERSION,
		"plain": PlainGround.stored(),
		"rock": CaveRock.VERSION,
	}
	if MapGeo.is_isometric(ctx):
		hashed["iso"] = MapGeo.new(ctx).def
		hashed["iso_v"] = ISO_VERSION
	return ctx.stable_hash(hashed)

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var geo := MapGeo.new(ctx)
	var err := SceneUtil.save_scene(trails_root(geo), TRAILS_SCENE)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": TRAILS_SCENE, "err": err}, TRAILS_SCENE))
	for entry in entries():
		var path := map_path(entry)
		if FileAccess.file_exists(path):
			continue
		var root := build_map(ctx, entry, issues)
		if root == null:
			continue
		err = SceneUtil.save_scene(root, path)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	return issues

# ---------------------------------------------------------------- the farm's side

## The scene the farm's map instances: for every added map of the plan its door, the spawn the
## farmer comes back to, and the mark on the ground. Not yet saved.
static func trails_root(geo: MapGeo) -> Node2D:
	var root := Node2D.new()
	root.name = TRAILS_NODE
	var found := trails()
	for entry in entries():
		var trail := trail_of(entry, found)
		if trail.is_empty():
			continue
		var cell := FarmMapRecipe.cell_of(trail.get("cell"))
		var arrive := FarmMapRecipe.cell_of(trail.get("spawn"))
		var mark := trail_mark(geo, cell - arrive)
		mark.position = geo.center(cell)
		SceneUtil.add(root, mark, root, "Mark_" + map_id(entry))
		geo.add_exit_door(root, root, door_name(entry), cell, map_path(entry), StringName(FROM_FARM))
		MapUtil.add_marker(root, root, spawn_name(entry), geo.center(arrive), true, JsonUtil.to_str(trail.get("facing", "down")))
	return root

## The mark of a trail, the middle of its cell at the origin: a worn patch of the shape of the
## cell, and an arrow that points the way out (`outward`: one step in cells). It lies flat on
## the ground, under whoever walks over it.
static func trail_mark(geo: MapGeo, outward: Vector2i) -> Node2D:
	var mark := Node2D.new()
	var patch := Polygon2D.new()
	patch.name = "Patch"
	patch.color = TRAIL
	var corners := geo.cells_outline(Rect2i(0, 0, 1, 1))
	var middle := geo.center(Vector2i.ZERO)
	var shape := PackedVector2Array()
	for corner in corners:
		shape.append((corner - middle) * 0.9)
	patch.polygon = shape
	mark.add_child(patch)
	var ahead := geo.step(Vector2(outward))
	var across := geo.step(Vector2(-outward.y, outward.x))
	var arrow := Polygon2D.new()
	arrow.name = "Arrow"
	arrow.color = TRAIL_ARROW
	arrow.polygon = PackedVector2Array([ahead * 0.34, ahead * -0.12 + across * 0.26, ahead * -0.12 - across * 0.26])
	mark.add_child(arrow)
	return mark

# ---------------------------------------------------------------- an added map

## One added map of the plan as the nodes of its scene, not yet saved; null, with an issue, when
## the project lacks what it is built from.
func build_map(ctx: BuildContext, entry: Dictionary, issues: Array) -> Node2D:
	var path := map_path(entry)
	var geo := MapGeo.new(ctx)
	if geo.def.is_empty():
		issues.append(ctx.make_issue("TILE-001", {"tileset": "overworld"}, path))
		return null
	var tile_set := geo.load_tile_set()
	if tile_set == null:
		issues.append(ctx.make_issue("VAL-002", {"file": geo.tileset_path()}, geo.tileset_path()))
		return null
	if not ResourceLoader.exists(PLAYER_SCENE):
		issues.append(ctx.make_issue("VAL-002", {"file": PLAYER_SCENE}, PLAYER_SCENE))
		return null
	var id := map_id(entry)
	var kind := JsonUtil.to_str(entry.get("kind", FOREST))
	var size := FarmMapRecipe.cell_of(entry.get("size"))
	var root := MapUtil.new_map_root(id.capitalize().replace(" ", ""), id)
	root.set("display_name", JsonUtil.to_str(entry.get("name", id)))
	root.set("music_asset_id", JsonUtil.to_str(ctx.section("sounds").get("music_map", "")))
	root.set_meta(KIND_META, kind)
	var layer_names: Array = ctx.config.get("map_layers", MapUtil.DEFAULT_LAYERS)
	var nodes := MapUtil.build_layers(root, layer_names, tile_set)
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var door := JsonUtil.to_dict(entry.get("door", {}))
	var gap := FarmMapRecipe.cell_of(door.get("cell"))
	var arrive := FarmMapRecipe.cell_of(door.get("spawn"))
	var water := FarmMapRecipe.cells_of(JsonUtil.to_dict(entry.get("water", {})).get("cells"))

	var water_tile := _add_ground(ctx, entry, kind, root, nodes, geo, water)
	# the edge, open at the way in and where the sea is
	var skip: Array[Vector2i] = [gap]
	skip.append_array(water)
	if kind == CAVE:
		geo.border_collision(root, size, skip)  # the edge of a cave is its rock (`_add_ground`)
	else:
		geo.paint_walls(root, nodes, size, skip)
	for note in geo.take_notes():
		print("[rpggen] INFO added_maps (%s): %s" % [id, note])

	# the field: nothing can be tilled here, and the cells of the sea say `water`
	var soil := FieldRecipe.add_field(root, nodes)
	if soil == null:
		issues.append(ctx.make_issue("VAL-002", {"file": FarmBuild.SOIL_TILESET}, FarmBuild.SOIL_TILESET))
		root.free()
		return null
	# a sea without a water tile of the packs is drawn; the packs' own shows through
	var water_mark := FieldRecipe.WATER_MARK if not water_tile.is_empty() else FieldRecipe.WATER_TILE
	for cell in water:
		soil.set_cell(cell, FieldRecipe.SOURCE_ID, water_mark)
	_add_common(ctx, entry, id, root, nodes, geo, water, size)
	if kind == CAVE:
		_add_enemies(ctx, entry, id, root, entities, geo)

	MapUtil.add_marker(spawns, root, FROM_FARM, geo.center(arrive), true, JsonUtil.to_str(door.get("facing", "down")))
	MapUtil.add_marker(spawns, root, "default", geo.center(arrive), true, JsonUtil.to_str(door.get("facing", "down")))
	geo.add_exit_door(triggers, root, BACK_DOOR, gap, FARM_PATH, StringName(spawn_name(entry)))
	MapUtil.place(PLAYER_SCENE, entities, root, geo.center(arrive))
	return root

## The ground of a kind, the path on it and the water. Returns the packs' water tile the sea
## was painted with, or {} (no sea, or a sea that the `Soil` layer draws).
func _add_ground(ctx: BuildContext, entry: Dictionary, kind: String, root: Node2D, nodes: Dictionary, geo: MapGeo, water: Array[Vector2i]) -> Dictionary:
	var size := FarmMapRecipe.cell_of(entry.get("size"))
	var ground: TileMapLayer = nodes["Ground"]
	var base := _farm_ground(ctx, geo)
	var own := geo.tile_of_asset(JsonUtil.to_str(entry.get("ground", ""))) if JsonUtil.to_str(entry.get("ground", "")) != "" else {}
	MapBuild.fill_ground(ground, size, own if not own.is_empty() else base)
	var details := geo.road_layer(nodes)
	if details != null and kind != CAVE:  # the tunnels of a cave are its floor, not roads
		geo.paint_joined(details, FarmMapRecipe.cells_of(entry.get("paths")), "ROAD", geo.find_tile("ROAD"))
	var water_tile := {}
	match kind:
		BEACH:
			root.set_meta(WATER_META, "sea")
			water_tile = geo.find_tile("WATER")
			if not water_tile.is_empty():
				geo.paint_joined(ground, water, "WATER", water_tile)
			if own.is_empty():
				# no sand of the packs: drawn over the ground, row by row, wherever the sea is not
				_add_cover(root, ground, geo, "Sand", row_runs(size, water), SAND, SAND_DARK)
		FOREST:
			if own.is_empty():
				# the floor of a wood is the farm's ground in the shade of its trees
				_add_cover(root, ground, geo, "Shade", row_runs(size, []), SHADE, SHADE)
		CAVE:
			# the floor of a cave is the ground in the gloom; the rock is drawn over it, and it
			# blocks where it meets the floor. Underground: no rain and a dim light.
			root.set("is_interior", true)
			# a cave is darker than a room of a house: the light of a cave, whatever the hour
			root.set("ambient_override", CAVE_LIGHT)
			var rock := FarmMapRecipe.cells_of(entry.get("walls"))
			if own.is_empty():
				_add_cover(root, ground, geo, "Gloom", row_runs(size, rock), GLOOM, GLOOM)
			# the rock, the edge's among it (no wall tile of the packs stands round a cave):
			# drawn, and the packs' own rock laid over it where they have it (cave_rock.gd)
			var drawn: Array[Vector2i] = []
			drawn.append_array(rock)
			drawn.append_array(MapGeo.border_cells(size, [FarmMapRecipe.cell_of(JsonUtil.to_dict(entry.get("door", {})).get("cell"))]))
			_add_cover(root, ground, geo, "Rock", cell_runs(drawn), ROCK, ROCK)
			_add_rock(ctx, entry, root, nodes, geo, drawn)
			var body := StaticBody2D.new()
			body.collision_layer = 0
			body.collision_mask = 0
			body.set_collision_layer_value(1, true)  # world
			SceneUtil.add(root, body, root, "RockWall")
			var shape_of_cell := geo.cell_shape()
			for cell in shore_cells(rock, size):
				var shape := CollisionShape2D.new()
				shape.name = "Cell_%d_%d" % [cell.x, cell.y]
				shape.shape = shape_of_cell
				shape.position = geo.center(cell)
				body.add_child(shape)
	return water_tile

## The packs' own rock of a cave over the drawn one (cave_rock.gd): a cell of a picture of rock
## on every cell of rock and of the edge seen from above, the isometric tile of rock on the
## ground of every cell on diamonds; else the packs' boulders (the farm's `rock` things), one on
## every cell of rock, which block nothing (the body `RockWall` does). Says in the log which.
func _add_rock(ctx: BuildContext, entry: Dictionary, root: Node2D, nodes: Dictionary, geo: MapGeo, cells: Array[Vector2i]) -> void:
	var holder: Node2D = root.get_node("Rock")
	var ground: TileMapLayer = nodes["Ground"]
	var used := CaveRock.lay(ctx, geo, holder, ground, cells)
	if used != "":
		print("[rpggen] INFO added_maps (%s): the cave's rock is %s" % [map_id(entry), used])
		return
	var boulders := FarmMapRecipe.thing_entries(ObjectEntries.entries(ctx), "rock", geo.tile_px)
	var fitting: Array[Dictionary] = []
	for found in boulders:
		if MapGeo.is_iso_entry(found) == geo.isometric:
			fitting.append(found)
	if fitting.is_empty():
		print("[rpggen] INFO added_maps (%s): the packs have no rock: the cave's rock is drawn" % map_id(entry))
		return
	var parent: Node2D = nodes["Entities"] if geo.isometric else holder
	var interior := {}
	for cell in FarmMapRecipe.cells_of(entry.get("walls")):
		interior[cell] = true
	var i := 0
	for cell in cells:
		if not interior.has(cell):
			continue  # the edge stays drawn: boulders round the map would hide its doorway
		var picture: Node2D = null
		if geo.isometric:
			picture = FarmMapRecipe.iso_picture("rock", fitting[i % fitting.size()], geo.footprint, geo.tile_px)
			picture.position = geo.center(cell)
		else:
			picture = FarmMapRecipe.picture("rock", FarmMapRecipe.thing_texture(fitting, i), geo.tile_px)
			picture.position += FarmMapRecipe._spot(cell, geo)
		picture.name = "Boulder_%d_%d" % [cell.x, cell.y]
		parent.add_child(picture)
		i += 1
	print("[rpggen] INFO added_maps (%s): the cave's rock is the packs' boulders (%s)" % [map_id(entry), JsonUtil.to_str(fitting[0]["id"])])

## `cells` as runs along a row (Rect2i one row high), row by row: what a drawn cover of some
## cells of a map is laid as.
static func cell_runs(cells: Array[Vector2i]) -> Array[Rect2i]:
	var by_row := {}
	for cell in cells:
		if not by_row.has(cell.y):
			by_row[cell.y] = []
		var row: Array = by_row[cell.y]
		row.append(cell.x)
	var rows: Array = by_row.keys()
	rows.sort()
	var out: Array[Rect2i] = []
	for y: int in rows:
		var xs: Array = by_row[y]
		xs.sort()
		var start: int = xs[0]
		var last: int = xs[0]
		for i in range(1, xs.size() + 1):
			var x: int = xs[i] if i < xs.size() else -2
			if x == last + 1:
				last = x
				continue
			out.append(Rect2i(start, y, last - start + 1, 1))
			start = x
			last = x
	return out

## The enemies of a cave (T17.24) at the cells of its plan: the action RPG's enemy scenes in
## turn (enemy_recipes.starter_scene_at), each remembered as `<id>_enemy_<n>`. None, with a
## line in the log, when the project has no enemy scene (a farm that does not fight).
func _add_enemies(ctx: BuildContext, entry: Dictionary, id: String, root: Node2D, entities: Node2D, geo: MapGeo) -> void:
	var here: Script = get_script()
	var path := here.resource_path.get_base_dir().path_join(ENEMY_RECIPES)
	var script: GDScript = null
	if ResourceLoader.exists(path):
		script = load(path) as GDScript
	if script == null:
		print("[rpggen] INFO added_maps (%s): the project has no enemies to put into the cave" % id)
		return
	var recipe: RefCounted = script.new()
	var cells: Array = JsonUtil.to_array(entry.get("enemies", []))
	var farmer := painted_height(PLAYER_SCENE)
	for i in cells.size():
		var scene := JsonUtil.to_str(recipe.call("starter_scene_at", ctx, i))
		if scene == "":
			print("[rpggen] INFO added_maps (%s): no enemy scene was built" % id)
			return
		var cell := FarmMapRecipe.cell_of(JsonUtil.to_dict(cells[i]).get("cell"))
		var enemy := MapUtil.place(scene, entities, root, geo.center(cell), "Enemy%d" % (i + 1))
		if enemy != null:
			enemy.set("entity_id", "%s_enemy_%d" % [id, i + 1])
			enemy.set("facing", "down")
			var size := scale_to_farmer(farmer, painted_height(scene))
			if size != 1.0:
				(enemy as Node2D).scale = Vector2(size, size)
				if i == 0:
					print("[rpggen] INFO added_maps (%s): the enemies are drawn %.2f times as large, %d%% of the farmer's height" % [id, size, roundi(ENEMY_HEIGHT * 100.0)])

## How many px high the first picture of the `Visual` of a scene of an actor is painted (its
## frame without the see-through rows above and below), or 0 when it has none.
static func painted_height(scene_path: String) -> int:
	if not ResourceLoader.exists(scene_path):
		return 0
	var packed := load(scene_path) as PackedScene
	if packed == null:
		return 0
	var node := packed.instantiate()
	var height := 0
	var visual := node.get_node_or_null("Visual") as AnimatedSprite2D
	if visual != null and visual.sprite_frames != null:
		var frames := visual.sprite_frames
		var names := frames.get_animation_names()
		var animation := ""
		if frames.has_animation("idle_down"):
			animation = "idle_down"
		elif not names.is_empty():
			animation = names[0]
		if animation != "" and frames.get_frame_count(animation) > 0:
			var texture := frames.get_frame_texture(animation, 0)
			var image: Image = null
			if texture != null:
				image = texture.get_image()
			if image != null:
				if image.is_compressed():
					image.decompress()
				height = image.get_used_rect().size.y
	node.free()
	return height

## The scale of an enemy that is painted `enemy` px high beside a farmer painted `farmer` px
## high: what makes it ENEMY_HEIGHT of the farmer, in quarters, never smaller than it is drawn
## and at most three times as large; 1 when it is that already, or either is not known (the kit's
## slime was a tile large: half the farmer's height from above).
static func scale_to_farmer(farmer: int, enemy: int) -> float:
	if farmer <= 0 or enemy <= 0:
		return 1.0
	var wanted := ENEMY_HEIGHT * farmer / float(enemy)
	var stepped := clampf(roundf(wanted * 4.0) / 4.0, 1.0, 3.0)
	return stepped

## The ground tile of the farm (farm_map_recipe.gd chooses the same).
func _farm_ground(ctx: BuildContext, geo: MapGeo) -> Dictionary:
	var plain := PlainGround.tile(geo)  # the plain tile rpggen found (farm.ground)
	if not plain.is_empty():
		return plain
	var wanted := JsonUtil.to_str(ctx.section("starter_map").get("ground", ""))
	if wanted == "":
		wanted = JsonUtil.to_str(ctx.section("starter").get("ground", ""))
	if wanted != "":
		var tile := geo.tile_of_asset(wanted)
		if not tile.is_empty():
			return tile
	return geo.find_tile("GROUND")

## A drawn ground over the tiles of the ground and under everything else: one polygon a run of
## cells (`runs`, a row high each), every second row in the second colour so that it does not
## lie there as one flat sheet.
static func _add_cover(root: Node2D, ground: TileMapLayer, geo: MapGeo, node_name: String, runs: Array[Rect2i], first: Color, second: Color) -> void:
	var cover := Node2D.new()
	cover.name = node_name
	root.add_child(cover)
	root.move_child(cover, ground.get_index() + 1)
	for i in runs.size():
		var run := runs[i]
		var strip := Polygon2D.new()
		strip.name = "Row_%d_%d" % [run.position.y, run.position.x]
		strip.polygon = geo.cells_outline(run)
		strip.color = first if run.position.y % 2 == 0 else second
		cover.add_child(strip)

## What every kind has: what blocks the way into the sea, the trees, the scenery and the things
## to clear, the places to forage, the markers.
func _add_common(ctx: BuildContext, entry: Dictionary, id: String, root: Node2D, nodes: Dictionary, geo: MapGeo, water: Array[Vector2i], size: Vector2i) -> void:
	var entities: Node2D = nodes["Entities"]
	if not water.is_empty():
		var sea := StaticBody2D.new()
		sea.collision_layer = 0
		sea.collision_mask = 0
		sea.set_collision_layer_value(1, true)  # world
		SceneUtil.add(root, sea, root, "Sea")
		var shape_of_cell := geo.cell_shape()  # one shape for every cell
		for cell in shore_cells(water, size):
			var shape := CollisionShape2D.new()
			shape.name = "Cell_%d_%d" % [cell.x, cell.y]
			shape.shape = shape_of_cell
			shape.position = geo.center(cell)
			sea.add_child(shape)
	FarmMapRecipe.new().add_things(entry, root, entities, geo, ObjectEntries.entries(ctx), id)
	var spots := FarmMapRecipe.cells_of(entry.get("spots"))
	if not spots.is_empty():
		var holder := Node2D.new()
		SceneUtil.add(root, holder, root, "Forage")
		for i in spots.size():
			MapUtil.add_marker(holder, root, "Spot%d" % (i + 1), geo.center(spots[i]))
	var markers := Node2D.new()
	SceneUtil.add(root, markers, root, "Markers")
	var fish := JsonUtil.to_dict(entry.get("fish", {}))
	if not fish.is_empty():
		MapUtil.add_marker(markers, root, "FishFrom", geo.center(FarmMapRecipe.cell_of(fish.get("from"))))
		MapUtil.add_marker(markers, root, "FishAt", geo.center(FarmMapRecipe.cell_of(fish.get("at"))))
	var clearing := FarmMapRecipe.rect_of(entry.get("clearing"))
	if clearing.size != Vector2i.ZERO:
		var middle := clearing.position + clearing.size / 2
		MapUtil.add_marker(markers, root, "Clearing", geo.center(middle))
