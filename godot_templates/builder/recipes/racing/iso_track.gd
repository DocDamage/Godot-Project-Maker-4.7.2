extends RefCounted
## A track of a racing game seen at an angle (T17.15): what the track recipe builds for a
## project with `projection: isometric`. The plan of the track is the one of a track seen from
## above, cell for cell (rpggen/core/track_plan.py); only what is painted and where things are
## drawn differ.
##
## **Two spaces in one scene.** The race is driven on the flat plan: the cars, the barriers and
## the tyres that stop them (`Barriers`), what every cell is made of (`Surfaces`), the pickups
## and the node `Race` have the positions the plan gave them, in px of the plan, exactly as in
## a track seen from above. So the physics of a car, the checkpoints and the rivals never hear
## of the view. What is *seen* is laid out on the diamonds of the isometric tile set: the
## ground (`Ground`), the road, what lies on it (`Marks`), the walls and hedges drawn where
## the barriers are (`Walls`), the scenery and the camera. The node `View` (RpgRaceView) says
## how a point of the plan becomes a point of the screen; the cars, the pickups and the
## weapons ask it where to draw themselves.
##
## **The road and the scale.** With road pieces of the packs (tiles whose `joins` say on which
## sides the road goes on) a cell of the loop is one diamond, and the road is laid from the
## piece for the two sides the loop goes through: a straight, or the corner piece at a corner
## of the plan. Such a piece is a street a car of its pack fills half of, and the road of the
## plan is three cars wide: so the diamonds are enlarged (the layer `Ground` is scaled, a whole
## number of times) until the car is about as long on the road as the plan has it. Without
## road pieces the road, five tiles wide, is drawn on the ground tiles as the track recipe
## draws the road of a pack that has none, and a diamond is as many tiles wide as makes the
## car that long (RaceBuild.scale_for).

const SceneUtil := preload("../../lib/scene_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const IsoTileset := preload("../../lib/iso_tileset.gd")
const StageRecipes := preload("../arcade/stage_recipes.gd")
const RaceBuild := preload("racing_build.gd")

## Bumped when what this file builds changes (part of the track recipe's hash for an isometric
## project only, so the hash of a project seen from above never moves with it).
const VERSION := 1

const WALL := Color(0.78, 0.16, 0.16)
const HEDGE := Color(0.15, 0.33, 0.17)
const ROAD := Color(0.27, 0.27, 0.31)
const LINE := Color(0.94, 0.94, 0.94)
const TYRE := Color(0.14, 0.14, 0.16)
const OVERLAYS := {"d": Color(0.59, 0.44, 0.27, 0.9), "o": Color(0.09, 0.09, 0.12, 0.92), "b": Color(0.35, 0.86, 1.0, 0.9)}
## The side of a diamond a step of the loop leaves a cell by.
const SIDE_OF := {Vector2i(0, -1): "n", Vector2i(1, 0): "e", Vector2i(0, 1): "s", Vector2i(-1, 0): "w"}
## What stands up (a car, a tree) is drawn by its row of diamonds from this `z_index` on: over
## everything that lies flat. A car's own `z_index` is this, so the two sort together.
const STANDING_Z := 5
## How far a run of drawn road reaches over the edge of its cells, in px of the plan.
const SEAM := 1.0

## The node that says how the plan of a track is seen: a diamond of `geo`, enlarged `scale`
## times, is `tiles` tiles of `tile` px wide, the first cell behind the wall round the field.
static func view_node(geo: MapGeo, tile: int, tiles: int, scale: int = 1) -> RpgRaceView:
	var node := Node.new()
	node.name = RpgRaceView.NODE
	SceneUtil.attach_script(node, RaceBuild.VIEW_SCRIPT)
	node.set("footprint", geo.footprint * maxi(1, scale))
	node.set("cell_px", float(tiles * tile))
	node.set("origin", Vector2(RaceBuild.BORDER * tile, RaceBuild.BORDER * tile))
	return node as RpgRaceView  # by its script: the node was a plain Node when it was made

## A flat shape of one colour over a rectangle of the plan, as it is seen.
static func _flat(seen: RpgRaceView, node_name: String, area: Rect2, color: Color) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.name = node_name
	shape.color = color
	shape.polygon = seen.screen_corners(area)
	return shape

static func _keep(root: Node2D, layer: Node2D, layer_name: String, z: int) -> void:
	if layer.get_child_count() == 0:
		layer.free()
		return
	layer.z_index = z
	SceneUtil.add(root, layer, root, layer_name)
	SceneUtil.set_owner_recursive(layer, root)

static func _points(raw: Variant) -> Array[Vector2]:
	var out: Array[Vector2] = []
	for entry: Variant in JsonUtil.to_array(raw):
		var pair := JsonUtil.to_array(entry)
		if entry is Dictionary:
			pair = JsonUtil.to_array(JsonUtil.to_dict(entry).get("position", []))
		if pair.size() >= 2:
			out.append(Vector2(JsonUtil.to_float(pair[0]), JsonUtil.to_float(pair[1])))
	return out

## The cells of the map a field of the plan of `field` px lies on, with one more ring round
## them, so that the wall at the edge of the field does not stand at the edge of the world.
static func ground_cells(seen: RpgRaceView, field: Rect2) -> Rect2i:
	var from := seen.grid_point(field.position)
	var to := seen.grid_point(field.end)
	var first := Vector2i(floori(from.x), floori(from.y)) - Vector2i.ONE
	var last := Vector2i(ceili(to.x), ceili(to.y)) + Vector2i.ONE
	return Rect2i(first, last - first)

## The tile the field of a track is laid with: the plain ground of the packs that is grass (by
## its `surface` or its name) when they have one, else their first plain ground.
static func field_tile(geo: MapGeo) -> Dictionary:
	for asset_id in geo.iso.plain_tiles("GROUND"):
		var tags := JsonUtil.to_array(geo.iso.facets(asset_id).get("tags", []))
		if tags.has(IsoTileset.SURFACE_TAG + "grass") or asset_id.to_lower().contains("grass"):
			return geo.tile_of_asset(asset_id)
	return geo.find_tile("GROUND")

## The sides every cell of a loop joins on: cell -> [side, side], in the order of the loop.
static func loop_sides(loop: Array) -> Dictionary:
	var cells: Array[Vector2i] = []
	for raw: Variant in loop:
		var pair := JsonUtil.to_array(raw)
		if pair.size() >= 2:
			cells.append(Vector2i(JsonUtil.to_int(pair[0]), JsonUtil.to_int(pair[1])))
	var out := {}
	for i in cells.size():
		var sides: Array[String] = []
		for other: Vector2i in [cells[posmod(i - 1, cells.size())], cells[(i + 1) % cells.size()]]:
			var side: String = SIDE_OF.get(other - cells[i], "")
			if side != "" and not sides.has(side):
				sides.append(side)
		out[cells[i]] = sides
	return out

## The scene of a track seen at an angle. The arguments are those of the track recipe's
## `build_track` for a track seen from above, all in the px of the plan, with `geo` (the
## geometry of the project's isometric maps, its tile set loaded) in the place of the tile set
## and the road tile. `look` has, beside what it has there: `loop` (the cells of the loop),
## the scale of the track (RaceBuild.scale_for: `pieces`, `tiles`, `scale`, `zoom`), and
## `decoration_origins` (for each of `decoration_textures` the point of the picture that
## stands on the middle of a diamond, for a picture drawn for these diamonds, which is
## enlarged with them; or null: the middle of its lower edge, as large as it is).
static func build_track(index: int, stage: Dictionary, view: Vector2i, tile: int, rows: PackedStringArray, barriers: Array[Rect2i],
		start: Vector2, geo: MapGeo, car_scene: PackedScene, fixed_camera: bool = false, look: Dictionary = {}) -> Node2D:
	var root := StageRecipes.build_stage(index, stage, view, start)
	var cells := Vector2i(rows[0].length() if not rows.is_empty() else 0, rows.size())
	var field := Rect2(Vector2.ZERO, Vector2(cells) * tile)
	var loop := JsonUtil.to_array(look.get("loop", []))
	var pieces := JsonUtil.to_bool(look.get("pieces", false)) and not loop.is_empty()
	var enlarged := maxi(1, JsonUtil.to_int(look.get("scale", 1), 1)) if pieces else 1
	var seen := view_node(geo, tile, RaceBuild.BLOCK if pieces else maxi(1, JsonUtil.to_int(look.get("tiles", RaceBuild.DRAWN_TILES), RaceBuild.DRAWN_TILES)), enlarged)
	# the ground: the plain ground tile of the packs under the whole field
	var ground := TileMapLayer.new()
	ground.tile_set = geo.tile_set
	ground.collision_enabled = false
	ground.z_index = -10
	if enlarged > 1:
		ground.scale = Vector2(enlarged, enlarged)
	SceneUtil.add(root, ground, root, "Ground")
	root.move_child(ground, 0)
	var covered := ground_cells(seen, field)
	var plain := field_tile(geo)
	if not plain.is_empty():
		MapUtil.fill(ground, covered, plain)
	# the road: the pieces of the packs along the loop, or drawn
	var drawn := Node2D.new()
	var marks := Node2D.new()  # what lies on the road: over the tiles, under the cars
	if pieces:
		geo.paint_sides(ground, loop_sides(loop), "ROAD", plain)
	for y in cells.y:
		var from := -1
		var mark_from := -1
		var mark := ""
		for x in cells.x + 1:
			var letter := rows[y][x] if x < cells.x else "g"
			var is_road := letter != "g" and letter != "."
			if is_road and not pieces and from < 0:
				from = x
			elif not is_road and from >= 0:
				# a hair larger than its cells: no seam shows between two rows at a zoom that is not whole
				drawn.add_child(_flat(seen, "Road_%d_%d" % [from, y], Rect2(Vector2(from, y) * tile, Vector2((x - from) * tile, tile)).grow(SEAM), ROAD))
				from = -1
			var shown := letter if OVERLAYS.has(letter) or letter == "s" else ""
			if shown != mark:
				if mark != "":
					var color: Color = LINE if mark == "s" else OVERLAYS[mark]
					marks.add_child(_flat(seen, "Mark_%s_%d_%d" % [mark, mark_from, y], Rect2(Vector2(mark_from, y) * tile, Vector2((x - mark_from) * tile, tile)), color))
				mark = shown
				mark_from = x
	_keep(root, drawn, "Road", -6)
	_keep(root, marks, "Marks", -4)
	SceneUtil.add(root, seen, root, RpgRaceView.NODE)
	var surfaces := Node2D.new()
	SceneUtil.attach_script(surfaces, RaceBuild.SURFACES_SCRIPT)
	surfaces.set("cell", float(tile))
	surfaces.set("rows", rows)
	SceneUtil.add(root, surfaces, root, "Surfaces")
	# what stops a car, in the plan; and where it is, drawn on the diamonds
	var walls := StaticBody2D.new()
	walls.collision_layer = 1 << (RaceBuild.WORLD_LAYER - 1)
	walls.collision_mask = 0
	SceneUtil.add(root, walls, root, "Barriers")
	var shown_walls := Node2D.new()
	var standing := Node2D.new()  # what stands up: sorted with the cars by its row of diamonds
	for i in barriers.size():
		var area := Rect2(Vector2(barriers[i].position) * tile, Vector2(barriers[i].size) * tile)
		var shape := CollisionShape2D.new()
		var box := RectangleShape2D.new()
		box.size = area.size
		shape.shape = box
		shape.position = area.get_center()
		SceneUtil.add(walls, shape, root, "Shape%d" % i)
		var edge := barriers[i].size.x == 1 or barriers[i].size.y == 1
		shown_walls.add_child(_flat(seen, "Wall%d" % i, area, WALL if edge else HEDGE))
	var tyre_texture: Texture2D = null
	if look.get("tyre_texture") is Texture2D:
		tyre_texture = look.get("tyre_texture")
	var tyres := _points(look.get("tyres", []))
	for i in tyres.size():
		var shape := CollisionShape2D.new()
		var circle := CircleShape2D.new()
		circle.radius = tile * 0.4
		shape.shape = circle
		shape.position = tyres[i]
		SceneUtil.add(walls, shape, root, "Tyre%d" % i)
		if tyre_texture != null:
			var picture := Sprite2D.new()
			picture.name = "TyrePicture%d" % i
			picture.texture = tyre_texture
			picture.position = seen.to_screen(tyres[i])
			picture.z_index = STANDING_Z + seen.depth(tyres[i])
			standing.add_child(picture)
		else:
			var disc := Polygon2D.new()
			disc.name = "TyrePicture%d" % i
			disc.color = TYRE
			var ring := PackedVector2Array()
			for k in 8:  # a circle of the plan, as it is seen
				ring.append(seen.to_screen(tyres[i] + Vector2.from_angle(TAU * k / 8.0) * tile * 0.4))
			disc.polygon = ring
			shown_walls.add_child(disc)
	_keep(root, shown_walls, "Walls", -3)
	# the scenery of the packs on the hedges: one thing a diamond, on its middle
	var scenery_textures: Array = JsonUtil.to_array(look.get("decoration_textures", []))
	var origins: Array = JsonUtil.to_array(look.get("decoration_origins", []))
	var taken := {}
	var placed := 0
	if not scenery_textures.is_empty():
		for place in _points(look.get("decoration", [])):
			var g := seen.grid_point(place)
			var cell := Vector2i(floori(g.x), floori(g.y))
			if taken.has(cell):
				continue
			taken[cell] = true
			var which := placed % scenery_textures.size()
			var texture: Texture2D = scenery_textures[which]
			var at := RpgIso.cell_to_screen(cell, seen.footprint)
			var picture := Sprite2D.new()
			picture.name = "Scenery%d" % placed
			picture.texture = texture
			picture.centered = false
			var origin: Variant = origins[which] if which < origins.size() else null
			if origin is Vector2:
				var foot: Vector2 = origin
				picture.offset = -foot
			else:
				picture.offset = Vector2(-texture.get_width() / 2.0, -texture.get_height())
			picture.position = at
			if enlarged > 1 and origin is Vector2:  # drawn for these diamonds: as large as they are
				picture.scale = Vector2(enlarged, enlarged)
			picture.z_index = STANDING_Z + cell.x + cell.y + 1
			standing.add_child(picture)
			placed += 1
	_keep(root, standing, "Scenery", 0)
	# where pickups lie, in the plan (a pickup draws itself where it is seen)
	var pickups := JsonUtil.to_array(look.get("pickups", []))
	if not pickups.is_empty():
		var holder := Node2D.new()
		SceneUtil.add(root, holder, root, "Pickups")
		var at := _points(pickups)
		var pickup_scene: PackedScene = null
		if look.get("pickup_scene") is PackedScene:
			pickup_scene = look.get("pickup_scene")
		for i in at.size():
			var what := JsonUtil.to_str(JsonUtil.to_dict(pickups[i]).get("kind", "boost"))
			var lying := pickup_scene.instantiate() as Node2D if pickup_scene != null else null
			if lying != null:
				lying.position = at[i]
				lying.set("kind", what)
				SceneUtil.add(holder, lying, root, "Pickup%d" % (i + 1))
				continue
			var marker := Marker2D.new()
			marker.position = at[i]
			marker.set_meta("kind", what)
			SceneUtil.add(holder, marker, root, "Pickup%d" % (i + 1))
	# the camera is where the picture is: over the diamond of the field, or on the car as seen
	var heading := JsonUtil.to_float(look.get("heading", -PI * 0.5))
	var rivals := JsonUtil.to_array(look.get("rival_scenes", []))
	var car_at := RaceBuild.grid_slot(start, heading, rivals.size(), tile) if not rivals.is_empty() else start
	var camera := root.get_node("Camera") as Camera2D
	SceneUtil.attach_script(camera, RaceBuild.CAMERA_SCRIPT)
	camera.set("target_path", NodePath("../Car"))
	camera.set("view", Vector2(view))
	# what a fixed camera shows: the diamond of the field and a little of the ground round it
	var shown := seen.screen_rect(field).grow(seen.footprint.y * 0.5)
	camera.set("track", shown)
	camera.set("fixed", fixed_camera)
	camera.set("base_zoom", JsonUtil.to_float(look.get("zoom", 1.0), 1.0))
	camera.position = shown.get_center() if fixed_camera else seen.to_screen(car_at)
	root.get_node("Scroller").set("camera_path", NodePath(""))
	for i in rivals.size():
		if not (rivals[i] is PackedScene):
			continue
		var scene: PackedScene = rivals[i]
		var rival := scene.instantiate() as Node2D
		if rival != null:
			rival.position = RaceBuild.grid_slot(start, heading, i, tile)
			rival.set("heading", heading)
			SceneUtil.add(root, rival, root, "Rival%d" % (i + 1))
	if car_scene != null:
		var car := car_scene.instantiate() as Node2D
		if car != null:
			car.position = car_at
			car.set("heading", heading)
			SceneUtil.add(root, car, root, "Car")
		var race := Node.new()
		SceneUtil.attach_script(race, RaceBuild.RACE_SCRIPT)
		race.set("rubber_band", JsonUtil.to_bool(look.get("rubber_band", true)))
		SceneUtil.add(root, race, root, "Race")
	return root
