extends RefCounted
## The people of a farm's village (T17.09), from the stored plan (`rpggen/world_plan.json`, the
## key `people` of the section `farm`, planned by rpggen/core/people_plan.py).
##
## As a recipe of the build's list:
## * generated/data/people.json, the people with their scenes and with the places of their
##   schedules turned into the map and the marker they are for each person, on every build;
## * game/data/people.json, the same, once: it is the user's afterwards (RpgFriendship reads
##   it, and gives the schedules to the NPCs);
## * game/data/dialogue/person_<id>.tres, once: what a person says, and what it says from two
##   hearts on (`friendship:<id>>=2`); in a farm that was planned with festivals (T17.25) also,
##   before either, what it says on a festival (`festival`), on the day before one
##   (`festival_tomorrow`) and on its birthday (`birthday:<id>`).
##
## As the farm's part of the village (starter_map_recipe calls `prepare` before it paints the
## walls and `augment_map` before it saves the map; see MAP_AUGMENTERS there):
## * the village's side of the door pair between the farm and the village: a gap in the wall
##   on the edge opposite the farm's way out, the door `to_farm` and the spawn `from_farm`;
## * the places the schedules name, as markers under `Places` (RpgSchedule.make_place):
##   `home_<n>` beside the door of house n, `square` near the place a visitor arrives at, and
##   `work` beside the villager who keeps the shop. Each has more spots than one
##   (`home_1_2`, `square_2`, ...) and the people take them in turn, so that two who are at
##   the same place do not stand in each other. The village has no water: there is no `pond`;
## * in a farm that was planned with festivals, the markers they name (events_recipe.gd:
##   `festival_table` below the square, `festival_egg_<n>` spread over the village);
## * an NPC for every person, with its `Schedule` (RpgSchedule, `person` its id), where it is
##   at home. All the places of a person are on the village, so each has one NPC.
##
## **The people and the NPCs the starter map places.** The first NPC of the starter map is the
## demo's villager (it greets, gives the errand and opens the shop): it stays. The others the
## options ask for (`starter_map.npcs` above 1) are not placed in a farm's village: the people
## of the plan stand there instead.

const RECIPE_VERSION := 1

const SceneUtil := preload("../../lib/scene_util.gd")
const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const MapUtil := preload("../../lib/map_util.gd")
const MapBuild := preload("../../lib/map_build.gd")
const MapGeo := preload("../../lib/map_geo.gd")
const WorldPlan := preload("../../lib/world_plan.gd")
const ObjectEntries := preload("../../lib/object_entries.gd")
const BuildContext := preload("../../lib/build_context.gd")
const ActorRecipes := preload("../actor_recipes.gd")
const InteriorRecipe := preload("../interior_recipe.gd")
const FarmBuild := preload("farm_build.gd")
const FarmMapRecipe := preload("farm_map_recipe.gd")
const EventsRecipe := preload("events_recipe.gd")

const PLANNED_PATH := "res://generated/data/people.json"
const USER_PATH := "res://game/data/people.json"
const DIALOGUE_DIR := "res://game/data/dialogue/"
const SCHEDULE := "res://addons/rpg_runtime/actors/schedule.gd"
const DLG_RES := "res://addons/rpg_runtime/dialogue/dialogue_resource.gd"
const DLG_LINE := "res://addons/rpg_runtime/dialogue/dialogue_line.gd"
const VILLAGE_ID := "starter_map"
const DOOR_NAME := "to_farm"
## What only the planner needs of a person: not in the files the game reads.
const PLAN_ONLY: Array[String] = ["asset", "pattern"]
## How many of the starter map's own NPCs a farm's village keeps: the demo's villager.
const DEMO_NPCS := 1
## How many spots a place has: the people take them in turn.
const HOME_SPOTS := 4
const SQUARE_SPOTS := 6
## From how many hearts a person has more to say.
const FRIEND_HEARTS := 2
## The version of what the recipe does for a farm with festivals only (T17.25): in the hashes of
## such a farm and of no other.
const EVENTS_VERSION := 1
## What the people say on a festival, in turn.
const FESTIVAL_LINES: Array[String] = [
	"What a day! The whole village is on the square.",
	"I have looked forward to this all season.",
	"No work today. Have you seen what there is to do?",
]
## The cells beside the door of a house where its people stand, the nearest first. Never the
## cell next to the door's: the door of a house of even width lies between two cells.
const HOME_STEPS: Array[Vector2i] = [Vector2i(2, 0), Vector2i(-2, 0), Vector2i(3, 0), Vector2i(-3, 0)]
## Where the village's door to the farm is: on the edge opposite the farm's way out.
const OPPOSITE := {"E": "W", "W": "E", "S": "N", "N": "S"}
const FACING_IN := {"N": "down", "E": "left", "S": "up", "W": "right"}

# ---------------------------------------------------------------- the plan

## The people of the stored plan, in its order.
static func people() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw: Variant in JsonUtil.to_array(FarmBuild.plan().get("people", [])):
		out.append(JsonUtil.to_dict(raw))
	return out

static func dialogue_path(person_id: String) -> String:
	return "%sperson_%s.tres" % [DIALOGUE_DIR, person_id]

## The name of spot `index` of a place: `square`, `square_2`, `square_3`, ...
static func spot_name(place: String, index: int) -> String:
	return place if index <= 0 else "%s_%d" % [place, index + 1]

## Where the places of a schedule are for the `index`-th person of the plan, as
## people_plan.people_file takes them: `home` an entry a house, `square` and `work` one each.
static func places_for(index: int, houses: int) -> Dictionary:
	var homes: Array = []
	for n in maxi(1, houses):
		homes.append({"map": VILLAGE_ID, "place": spot_name("home_%d" % (n + 1), index % HOME_SPOTS)})
	return {
		"home": homes,
		"square": {"map": VILLAGE_ID, "place": spot_name("square", index % SQUARE_SPOTS)},
		"work": {"map": VILLAGE_ID, "place": "work"},
	}

## A number of the plan as the whole number it is (JSON gives floats back), in lists and
## tables too.
static func whole(value: Variant) -> Variant:
	if value is float:
		var number: float = value
		return int(number) if is_equal_approx(number, roundf(number)) else value
	if value is Array:
		var list: Array = value
		var out: Array = []
		for item: Variant in list:
			out.append(whole(item))
		return out
	if value is Dictionary:
		var table: Dictionary = value
		var out := {}
		for key: Variant in table.keys():
			out[key] = whole(table[key])
		return out
	return value

## One entry of a schedule with its place turned into the map and the marker it is for this
## person (people_plan._placed): a place `places` does not name keeps its name.
static func placed(entry: Dictionary, home: int, places: Dictionary) -> Dictionary:
	var place := JsonUtil.to_str(entry.get("place", ""))
	var spot: Variant = places.get(place)
	if place == "home" and spot is Array:
		var homes: Array = spot
		spot = homes[home - 1] if home > 0 and home <= homes.size() else null
	if not (spot is Dictionary):
		return JsonUtil.to_dict(whole(entry))
	var out := {}
	for key: Variant in entry.keys():
		if JsonUtil.to_str(key) != "place":
			out[key] = whole(entry[key])
	var where: Dictionary = spot
	for key: Variant in where.keys():
		out[key] = where[key]
	return out

## What people.json holds of one person (people_plan.people_file): the plan's entry without
## what only the planner needs, with its scene and its placed schedule.
static func person_entry(person: Dictionary, places: Dictionary, scene: String) -> Dictionary:
	var out := {}
	for key: Variant in person.keys():
		if not PLAN_ONLY.has(JsonUtil.to_str(key)):
			out[key] = whole(person[key])
	out["scene"] = scene
	var schedule: Array = []
	for raw: Variant in JsonUtil.to_array(person.get("schedule", [])):
		schedule.append(placed(JsonUtil.to_dict(raw), JsonUtil.to_int(person.get("home", 1), 1), places))
	out["schedule"] = schedule
	return out

# ---------------------------------------------------------------- the packs

## The scene of a person: the character of its NPC asset, else the NPC the demo's villager is
## (any NPC of the packs, else the stand-in made of the player's sprite). "" when none exists.
static func scene_for(ctx: BuildContext, person: Dictionary) -> String:
	var asset_id := JsonUtil.to_str(person.get("asset", ""))
	if asset_id != "" and ResourceLoader.exists(ActorRecipes.character_scene_path(asset_id)):
		return ActorRecipes.character_scene_path(asset_id)
	for asset in ctx.catalog.assets_by_role("NPC"):
		var path := ActorRecipes.character_scene_path(JsonUtil.to_str(asset["id"]))
		if ResourceLoader.exists(path):
			return path
	return ActorRecipes.FALLBACK_NPC_PATH if ResourceLoader.exists(ActorRecipes.FALLBACK_NPC_PATH) else ""

## How many houses the village's own plan has (the planner of the starter map, as the
## interiors count them).
static func houses(ctx: BuildContext) -> int:
	var building := ObjectEntries.starter_building(ctx)
	var overworld: Dictionary = ctx.catalog.tileset_def("overworld")
	var tile_px := 16 if overworld.is_empty() else JsonUtil.to_int(overworld["tile_size"][0])
	# an isometric village's houses stand on the cells their pictures say (T17.14), as the
	# starter map recipe plans them
	var house := MapGeo.new(ctx).building_info(building) if MapGeo.is_isometric(ctx) else InteriorRecipe.building_info(building, tile_px)
	var layout := MapBuild.plan(ctx.section("starter_map"), JsonUtil.to_int(ctx.config.get("seed", 12345)), house, JsonUtil.to_str(ctx.config.get("archetype", "farm")))
	var built: Array = layout["buildings"]
	return built.size()

# ---------------------------------------------------------------- the recipe

func outputs(_ctx: BuildContext) -> PackedStringArray:
	var out := PackedStringArray([PLANNED_PATH])
	var seeded: Array = [USER_PATH]
	for person in people():
		seeded.append(dialogue_path(JsonUtil.to_str(person["id"])))
	out.append_array(SeedUtil.missing(seeded))
	return out

func input_hash(ctx: BuildContext) -> String:
	var scenes := {}
	for person in people():
		scenes[person["id"]] = scene_for(ctx, person)
	var hashed := {"v": RECIPE_VERSION, "people": people(), "scenes": scenes, "houses": houses(ctx), "spots": [HOME_SPOTS, SQUARE_SPOTS]}
	if festive():  # only a farm with festivals has the key (T17.25)
		hashed["events_v"] = EVENTS_VERSION
	return ctx.stable_hash(hashed)

## True in a farm that was planned with festivals: its people say so, and its village has the
## markers they name.
static func festive() -> bool:
	return not FarmBuild.events().is_empty()

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var entries: Array = []
	var list := people()
	var count := houses(ctx)
	for i in list.size():
		var person := list[i]
		entries.append(person_entry(person, places_for(i, count), scene_for(ctx, person)))
		var path := dialogue_path(JsonUtil.to_str(person["id"]))
		if not FileAccess.file_exists(path):
			var err := SeedUtil.save(_dialogue(person, i), path)
			if err != OK:
				issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))
	var data := {"people": entries}
	for path: String in [PLANNED_PATH] + Array(SeedUtil.missing([USER_PATH])):
		DirAccess.make_dir_recursive_absolute(path.get_base_dir())
		var write_err := JsonUtil.write(path, data)
		if write_err != OK:
			issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": write_err}, path))
	return issues

## What a person says: a greeting, and another line once the farmer has two hearts with it. The
## first line whose condition holds is said; the other is passed over. In a farm with festivals
## (T17.25) three lines come before them, each said on its day and passed over on every other:
## on a festival, on the day before one, and on the person's birthday (a line by an atom of
## RpgCondition: marriage, T17.26, adds its own the same way).
func _dialogue(person: Dictionary, index: int = 0) -> Resource:
	var id := JsonUtil.to_str(person["id"])
	var speaker := JsonUtil.to_str(person.get("name", id.capitalize()))
	var friends := "friendship:%s>=%d" % [id, FRIEND_HEARTS]
	var greeting := "Hello! I am %s. I keep the shop of the village." if JsonUtil.to_str(person.get("job", "")) != "" else "Hello! I am %s. You have taken over the old farm, have you not?"
	var res := SeedUtil.make(DLG_RES)
	var lines: Array = [
		_line("friend", speaker, "It is good to see you! Come by whenever you like.", friends),
		_line("hello", speaker, greeting % speaker, "not " + friends),
	]
	if festive():
		var special: Array = [
			_line("festival", speaker, FESTIVAL_LINES[index % FESTIVAL_LINES.size()], "festival"),
			_line("festival_tomorrow", speaker, "Tomorrow is the festival on the square. The shop will be closed, so buy what you need today.", "festival_tomorrow"),
		]
		if not JsonUtil.to_dict(person.get("birthday", {})).is_empty():
			special.append(_line("birthday", speaker, "It is my birthday today! You remembered?", "birthday:%s" % id))
		lines = special + lines
	var res_lines: Array = res.get("lines")
	res_lines.assign(lines)
	return res

func _line(line_id: String, speaker: String, text: String, condition: String) -> Resource:
	var line := SeedUtil.make(DLG_LINE)
	line.set("id", StringName(line_id))
	line.set("speaker", speaker)
	line.set("text", text)
	line.set("condition", condition)
	return line

# ---------------------------------------------------------------- the village

## What the starter map's hash holds of the farm's part of the village.
static func map_hash() -> Dictionary:
	var hashed := {"v": RECIPE_VERSION, "people": people(), "exit": JsonUtil.to_dict(FarmMapRecipe.plan().get("exit", {})), "spots": [HOME_SPOTS, SQUARE_SPOTS, DEMO_NPCS]}
	if festive():  # only a farm with festivals has the keys (T17.25)
		hashed["festival"] = EventsRecipe.markers()
		hashed["events_v"] = EVENTS_VERSION
	return hashed

## The cells of a village something stands or lies on: its houses, what the planner placed, its
## roads, where the player appears (with the cells round it), and `kept` (doors and the like).
static func occupied(layout: Dictionary, house: Vector2i, kept: Array[Vector2i]) -> Dictionary:
	var taken := {}
	var built: Array[Vector2i] = layout["buildings"]
	for at in built:
		for dx in maxi(1, house.x):
			for dy in maxi(1, house.y):
				taken[at + Vector2i(dx, dy)] = true
	for key: String in ["decorations", "npcs", "chests", "enemies", "path", "exit_path", "doors"]:
		if not layout.has(key):
			continue
		var raw: Array = layout[key]
		var cells: Array[Vector2i] = []
		cells.assign(raw)
		for cell in cells:
			taken[cell] = true
	var spawn: Vector2i = layout["spawn"]
	for dx in range(-1, 2):
		for dy in range(-1, 2):
			taken[spawn + Vector2i(dx, dy)] = true
	for cell in kept:
		taken[cell] = true
	return taken

## The village's side of the way to the farm: {cell (the gap in the wall), spawn (the floor
## before it), edge, facing}, on the edge opposite the farm's way out, a third of the way
## along it or as near to that as the village has free ground (the middle of a wall is where a
## visitor first walks against it), and away from the gaps the map has (`skip`). {} for a plan
## without a way out.
static func farm_door(layout: Dictionary, house: Vector2i, skip: Array[Vector2i], farm: Dictionary) -> Dictionary:
	var way_out := JsonUtil.to_dict(farm.get("exit", {}))
	if way_out.is_empty():
		return {}
	var edge := JsonUtil.to_str(OPPOSITE.get(JsonUtil.to_str(way_out.get("edge", "E")), "W"))
	var size: Vector2i = layout["size"]
	var blocked := occupied(layout, house, skip)
	var built: Array[Vector2i] = layout["buildings"]
	for at in built:  # not against a house either
		for dx in range(-1, maxi(1, house.x) + 1):
			for dy in range(-1, maxi(1, house.y) + 2):
				blocked[at + Vector2i(dx, dy)] = true
	var gaps: Array[Vector2i] = skip.duplicate()
	gaps.append(layout["exit_gap"])
	for gap in gaps:  # two gaps are never side by side
		for dx in range(-2, 3):
			for dy in range(-2, 3):
				blocked[gap + Vector2i(dx, dy)] = true
	@warning_ignore("integer_division")
	var wanted := Vector2i(size.x / 3, size.y / 3)
	match edge:
		"N":
			wanted.y = 0
		"S":
			wanted.y = size.y - 1
		"E":
			wanted.x = size.x - 1
		_:
			wanted.x = 0
	var cell := WorldPlan.free_edge_cell(wanted, edge, size, blocked)
	return {"cell": cell, "spawn": WorldPlan.inside(edge, cell), "edge": edge, "facing": JsonUtil.to_str(FACING_IN.get(edge, "down"))}

## `count` free cells for the spots of a place, marked as taken: the `preferred` ones that are
## free first, then the free cells nearest to `centre` (every second one, so that the people
## who stand there leave room to walk between them).
static func pick_spots(centre: Vector2i, count: int, size: Vector2i, taken: Dictionary, preferred: Array[Vector2i] = []) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	for cell in preferred:
		if out.size() < count and _free(cell, size, taken):
			out.append(cell)
			taken[cell] = true
	for distance in size.x + size.y:
		if out.size() >= count:
			break
		for dy in range(-distance, distance + 1):
			for side: int in [-1, 1]:
				var dx := (distance - absi(dy)) * side
				var cell := centre + Vector2i(dx, dy)
				if out.size() < count and posmod(dx + dy, 2) == 0 and _free(cell, size, taken):
					out.append(cell)
					taken[cell] = true
				if dx == 0:
					break
	while out.size() < count:  # a village with no free cell left: everybody on one
		out.append(Vector2i(clampi(centre.x, 1, size.x - 2), clampi(centre.y, 1, size.y - 2)))
	return out

static func _free(cell: Vector2i, size: Vector2i, taken: Dictionary) -> bool:
	return cell.x >= 2 and cell.y >= 2 and cell.x <= size.x - 3 and cell.y <= size.y - 3 and not taken.has(cell)

## The places of a village: marker name -> cell, in the order they are made. `home_<n>` and its
## spots beside the door of house n (one home near the arrival when the village has no house),
## `home` (the first spot of house 1, for a schedule that names no house), `square` and its
## spots, and `work` beside the first NPC of the starter map (the villager who keeps the shop).
## With `festival` (the markers the planned festivals name, events_recipe.gd: none in a farm
## without them) those come last: the first below the square, the others spread over the map
## and never among the people who stand on the square (two cells from every spot of it).
static func village_spots(layout: Dictionary, house: Vector2i, kept: Array[Vector2i], festival: Array[String] = []) -> Dictionary:
	var size: Vector2i = layout["size"]
	var spawn: Vector2i = layout["spawn"]
	var taken := occupied(layout, house, kept)
	var out := {}
	var doors: Array[Vector2i] = layout["doors"]
	for n in maxi(1, doors.size()):
		var centre := spawn + Vector2i(-4, -2)
		var beside: Array[Vector2i] = []
		if n < doors.size():
			centre = doors[n]
			for step in HOME_STEPS:
				beside.append(doors[n] + step)
		var cells := pick_spots(centre, HOME_SPOTS, size, taken, beside)
		for k in cells.size():
			out[spot_name("home_%d" % (n + 1), k)] = cells[k]
	out["home"] = out["home_1"]
	var square := pick_spots(spawn + Vector2i(-4, 3), SQUARE_SPOTS, size, taken)
	for k in square.size():
		out[spot_name("square", k)] = square[k]
	var keepers: Array[Vector2i] = layout["npcs"]
	var counter: Array[Vector2i] = []
	var at := spawn + Vector2i(4, -2)
	if not keepers.is_empty():
		at = keepers[0]
		counter = [at + Vector2i(1, 0), at + Vector2i(-1, 0)]
	out["work"] = pick_spots(at, 1, size, taken, counter)[0]
	var apart := taken.duplicate()
	for spot in square:
		for dx in range(-2, 3):
			for dy in range(-2, 3):
				apart[spot + Vector2i(dx, dy)] = true
	for i in festival.size():
		var centre := EventsRecipe.centre_for(i, festival.size(), size, square[0])
		var cell := pick_spots(centre, 1, size, taken if i == 0 else apart)[0]
		taken[cell] = true
		apart[cell] = true
		out[festival[i]] = cell
	return out

## Asked by the starter map recipe before it paints the walls: {npcs: how many of the planner's
## own NPCs are placed, gaps: cells of the wall to leave open, door: the way to the farm}.
static func prepare(layout: Dictionary, house: Vector2i, skip: Array[Vector2i]) -> Dictionary:
	var out := {"npcs": DEMO_NPCS, "gaps": []}
	var door := farm_door(layout, house, skip, FarmMapRecipe.plan())
	if not door.is_empty():
		out["door"] = door
		out["gaps"] = [door["cell"]]
	return out

## Adds the farm's part to a village that is being built: the door to the farm, the places and
## the people. `nodes` are the map's nodes by name, `layout` is MapBuild.plan's, `house` the
## size of the starter building in cells ((0, 0) for none), `kept_free` cells nothing may lie
## on (doors), `prepared` what `prepare` answered.
static func augment_map(ctx: BuildContext, root: Node2D, nodes: Dictionary, layout: Dictionary, house: Vector2i, kept_free: Array[Vector2i], prepared: Dictionary) -> void:
	var entities: Node2D = nodes["Entities"]
	var spawns: Node2D = nodes["SpawnPoints"]
	var triggers: Node2D = nodes["Triggers"]
	var ground: TileMapLayer = nodes["Ground"]
	var tile_px := ground.tile_set.tile_size.x if ground.tile_set != null else 16
	# the seam between the village's cells and its px (T17.14): on squares it is the tile of the
	# ground and the arithmetic this always was, on diamonds the project's
	var geo := MapGeo.new(ctx)
	if not geo.isometric:
		geo.tile_px = tile_px
	var kept: Array[Vector2i] = kept_free.duplicate()
	var door := JsonUtil.to_dict(prepared.get("door", {}))
	if not door.is_empty():
		var gap: Vector2i = door["cell"]
		var arrive: Vector2i = door["spawn"]
		MapUtil.add_marker(spawns, root, FarmMapRecipe.FROM_FARM, geo.center(arrive), true, JsonUtil.to_str(door["facing"]))
		geo.add_exit_door(triggers, root, DOOR_NAME, gap, FarmMapRecipe.FARM_PATH, StringName(FarmMapRecipe.FROM_VILLAGE))
		kept.append(gap)
		kept.append(arrive)
		kept.append(WorldPlan.inside(JsonUtil.to_str(door["edge"]), arrive))
	var spots := village_spots(layout, house, kept, EventsRecipe.markers())
	var places := Node2D.new()
	SceneUtil.add(root, places, root, "Places")
	for place: String in spots.keys():
		var cell: Vector2i = spots[place]
		var marker := RpgSchedule.make_place(place)
		marker.position = geo.center(cell)
		places.add_child(marker)
		marker.owner = root
	var list := people()
	var built: Array = layout["buildings"]
	for i in list.size():
		var person := list[i]
		var id := JsonUtil.to_str(person["id"])
		var scene := scene_for(ctx, person)
		if scene == "":
			continue
		var homes: Array = places_for(i, built.size())["home"]
		var home: Dictionary = homes[clampi(JsonUtil.to_int(person.get("home", 1), 1), 1, homes.size()) - 1]
		var at: Vector2i = spots.get(JsonUtil.to_str(home["place"]), spots["home"])
		var npc := MapUtil.place(scene, entities, root, geo.center(at), "Person_%s" % id)
		if npc == null:
			continue
		npc.set("entity_id", "person_%s" % id)
		npc.set("facing", "down")
		if ResourceLoader.exists(dialogue_path(id)):
			npc.set("dialogue", load(dialogue_path(id)))
		var schedule := Node.new()
		SceneUtil.attach_script(schedule, SCHEDULE)
		schedule.set("person", id)
		SceneUtil.add(npc, schedule, root, RpgSchedule.NODE_NAME)
