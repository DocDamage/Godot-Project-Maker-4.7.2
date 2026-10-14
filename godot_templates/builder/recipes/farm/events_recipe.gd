extends RefCounted
## The festivals of a farm's year (T17.25), from the stored plan (`rpggen/world_plan.json`, the
## key `events` of the section `farm`, planned by rpggen/core/event_plan.py).
##
## As a recipe of the build's list, in a farm with `starter_map.festivals` on:
## * generated/data/events.json, the festivals with the map their markers are on (the village),
##   on every build;
## * game/data/events.json, the same, once: it is the user's afterwards, and the game takes
##   from the generated file only the events the user's does not list (RpgFarmEvents).
## A farm with the option off has neither, and the recipe writes nothing.
##
## For the other recipes of a farm:
## * `village_spots` gives the people's recipe the markers the festivals name (`festival_table`
##   by the square, `festival_egg_<n>` spread over the village), which it adds to the places of
##   a village that is being built;
## * `add_wall_calendar` hangs the calendar (RpgWallCalendar) on the wall of the farmhouse room
##   that is being built. A room and a village that exist are never built again: a farm from
##   before the card has the calendar in its pause menu, and its festivals take place round the
##   square (RpgFarmEvents.marker_position).

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const BuildContext := preload("../../lib/build_context.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const FarmBuild := preload("farm_build.gd")

const PLANNED_PATH := "res://generated/data/events.json"
const USER_PATH := "res://game/data/events.json"
const WALL_CALENDAR := FarmBuild.DIR + "wall_calendar.gd"
const VILLAGE_ID := "starter_map"
const CALENDAR_NAME := "WallCalendar"
const TABLE := "festival_table"
const EGG := "festival_egg_%d"
const PAPER := Color(0.95, 0.94, 0.88)
const HEAD := Color(0.78, 0.22, 0.2)
const INK := Color(0.3, 0.3, 0.36)
const BOARD := Color(0.5, 0.33, 0.18)

# ---------------------------------------------------------------- the recipe

func outputs(ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray()
	if not FarmBuild.festivals(ctx):
		return out
	out.append(PLANNED_PATH)
	out.append_array(SeedUtil.missing([USER_PATH]))
	return out

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "on": FarmBuild.festivals(ctx), "events": FarmBuild.events()})

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if not FarmBuild.festivals(ctx):
		return issues
	var data := {"events": entries()}
	for path: String in [PLANNED_PATH] + Array(SeedUtil.missing([USER_PATH])):
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		var err := JsonUtil.write(path, data)
		if err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	return issues

## What events.json holds (event_plan.events_file): each festival of the plan with the map its
## markers are on.
static func entries() -> Array:
	var out: Array = []
	for event in FarmBuild.events():
		var entry := JsonUtil.to_dict(_whole(event))
		entry["map"] = VILLAGE_ID
		out.append(entry)
	return out

## A number of the plan as the whole number it is (JSON gives floats back), in lists and tables
## too.
static func _whole(value: Variant) -> Variant:
	if value is float:
		var number: float = value
		return int(number) if is_equal_approx(number, roundf(number)) else value
	if value is Array:
		var list: Array = value
		var out: Array = []
		for item: Variant in list:
			out.append(_whole(item))
		return out
	if value is Dictionary:
		var table: Dictionary = value
		var out := {}
		for key: Variant in table.keys():
			out[key] = _whole(table[key])
		return out
	return value

# ---------------------------------------------------------------- the village

## The markers the planned festivals name, in the order they are made: the table of every
## festival that has one, then the spots of every egg hunt.
static func markers() -> Array[String]:
	var out: Array[String] = []
	for event in FarmBuild.events():
		var table := JsonUtil.to_str(event.get("table", ""))
		if table != "" and not out.has(table):
			out.append(table)
	for event in FarmBuild.events():
		for raw: Variant in JsonUtil.to_array(event.get("spots", [])):
			if JsonUtil.to_str(raw) != "" and not out.has(JsonUtil.to_str(raw)):
				out.append(JsonUtil.to_str(raw))
	return out

## Where the `index`-th of `count` things of a village of `size` cells is looked for a free
## cell: the first two cells below the square, the others on a ring round the middle of the
## map, so that the eggs of a hunt lie apart.
static func centre_for(index: int, count: int, size: Vector2i, square: Vector2i) -> Vector2i:
	if index == 0:
		return square + Vector2i(0, 2)
	@warning_ignore("integer_division")
	var middle := Vector2i(size.x / 2, size.y / 2)
	var angle := TAU * float(index) / float(maxi(2, count))
	return middle + Vector2i(roundi(cos(angle) * size.x * 0.3), roundi(sin(angle) * size.y * 0.3))

# ---------------------------------------------------------------- the farmhouse

## The cell of a room of `size` cells the calendar hangs over: of the cells along the top wall
## the one farthest from the head of the bed (the nearest to the right of two as far).
static func calendar_cell(size: Vector2i, bed_head: Vector2i) -> Vector2i:
	var best := Vector2i(1, 1)
	var far := -1
	for x in range(1, maxi(2, size.x - 1)):
		var distance := absi(x - bed_head.x)
		if distance >= far:
			far = distance
			best = Vector2i(x, 1)
	return best

## The calendar (RpgWallCalendar), not yet in a room: a sheet with a red head and rows of days.
## On squares its origin is the upper edge of the cell it hangs over: it is drawn on the wall
## above that cell, `interact` finds it from the cell, and whoever stands in the room is drawn
## over it. On diamonds its origin is the middle of the cell, and it is a board on a post that
## stands there (the walls of an isometric room are no place to hang a thing on).
static func wall_calendar(tile_px: int, diamond: Vector2i = Vector2i.ZERO) -> Area2D:
	var root := Area2D.new()
	root.name = CALENDAR_NAME
	SceneUtil.attach_script(root, WALL_CALENDAR)
	root.collision_layer = 0
	root.collision_mask = 0
	root.set_collision_layer_value(5, true)
	root.monitoring = false
	root.monitorable = true
	var shape := CollisionShape2D.new()
	shape.name = "Shape"
	var unit := float(tile_px)
	var foot := Vector2(0.0, -unit * 0.1)  # the lower edge of the sheet, on the wall above
	if diamond != Vector2i.ZERO:
		shape.shape = RpgFarmIso.diamond_shape(diamond)
		root.add_child(_box("Post", Rect2(-1.0, -unit * 0.5, 2.0, unit * 0.5), BOARD))
		foot = Vector2(0.0, -unit * 0.5)
	else:
		var rect := RectangleShape2D.new()
		rect.size = Vector2(unit * 0.8, unit * 1.2)
		shape.shape = rect
		shape.position = Vector2(0.0, -unit * 0.1)
	root.add_child(shape)
	var picture := Node2D.new()
	picture.name = "Picture"
	picture.position = foot
	root.add_child(picture)
	var wide := unit * 0.7
	var high := unit * 0.75
	picture.add_child(_box("Sheet", Rect2(-wide * 0.5, -high, wide, high), PAPER))
	picture.add_child(_box("Head", Rect2(-wide * 0.5, -high, wide, high * 0.28), HEAD))
	for row in 3:
		picture.add_child(_box("Row%d" % (row + 1), Rect2(-wide * 0.36, -high * (0.6 - row * 0.2), wide * 0.72, maxf(1.0, unit * 0.06)), INK))
	return root

static func _box(node_name: String, rect: Rect2, colour: Color) -> Polygon2D:
	var shape := Polygon2D.new()
	shape.name = node_name
	shape.polygon = PackedVector2Array([rect.position, Vector2(rect.end.x, rect.position.y), rect.end, Vector2(rect.position.x, rect.end.y)])
	shape.color = colour
	return shape

## Hangs the calendar in a farmhouse room that is being built, when the farm has festivals:
## among the entities of the room, at `calendar_cell`. Returns the cell, or (-1, -1) for a farm
## without festivals.
static func add_wall_calendar(root: Node2D, entities: Node2D, size: Vector2i, bed_head: Vector2i, geo: MapGeo) -> Vector2i:
	if FarmBuild.events().is_empty():
		return Vector2i(-1, -1)
	var cell := calendar_cell(size, bed_head)
	var calendar := wall_calendar(geo.tile_px, geo.footprint if geo.isometric else Vector2i.ZERO)
	calendar.position = geo.center(cell)
	if not geo.isometric:
		calendar.position.y -= geo.tile_px * 0.5
	SceneUtil.add(entities, calendar, root, CALENDAR_NAME)
	SceneUtil.set_owner_recursive(calendar, root)
	return cell
