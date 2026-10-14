extends RefCounted
## T17.23: the maps added to a farm. The pure parts of their recipe (which cells of the sea keep
## the farmer out, how a drawn ground is laid, what the plan's entries are called), and what the
## game does on a map of a kind: on a beach only the things of a beach lie, and the rod is cast
## into the sea, where the fish of the sea bite.

const AddedMaps := preload("../../builder/recipes/farm/added_maps_recipe.gd")
const FarmBuild := preload("../../builder/recipes/farm/farm_build.gd")
const ForageTest := preload("test_farm_forage.gd")

const FORAGE := [
	{"id": "forage_herb", "name": "Herb", "item": "forage_herb", "seasons": ["spring"], "price": 15, "energy": 8},
	{"id": "forage_leek", "name": "Leek", "item": "forage_leek", "seasons": ["spring", "summer"], "price": 20, "energy": 8},
	{"id": "forage_shell", "name": "Shell", "item": "forage_shell", "seasons": ["spring", "summer", "autumn", "winter"], "price": 15, "energy": 8, "maps": ["beach"]},
	{"id": "forage_weed", "name": "Seaweed", "item": "forage_weed", "seasons": ["summer"], "price": 20, "energy": 8, "maps": ["beach"]},
]
const FISH := [
	{"id": "fish_perch", "name": "Perch", "item": "fish_perch", "seasons": [], "times": [], "water": ["pond"], "price": 30, "energy": 12, "speed": 1.0},
	{"id": "fish_cod", "name": "Cod", "item": "fish_cod", "seasons": [], "times": [], "water": ["sea"], "price": 45, "energy": 12, "speed": 1.0},
]

func test_an_entry_of_the_plan_names_its_map_its_door_and_its_spawn(t) -> void:
	var entry := {"id": "farm_map_2", "map": "game/maps/farm_map_2.tscn", "kind": "beach", "trail": 1.0}
	t.eq(AddedMaps.map_id(entry), "farm_map_2")
	t.eq(AddedMaps.map_path(entry), "res://game/maps/farm_map_2.tscn")
	t.eq(AddedMaps.door_name(entry), "to_farm_map_2", "the farm's door to it")
	t.eq(AddedMaps.spawn_name(entry), "from_farm_map_2", "where the farmer comes back to")
	var trails: Array[Dictionary] = [{"cell": [1, 5]}, {"cell": [38, 9]}]
	t.eq(AddedMaps.trail_of(entry, trails), {"cell": [38, 9]}, "a number of a plan is read as the index it is")
	t.eq(AddedMaps.trail_of({"trail": 2}, trails), {}, "a trail the farm does not have")
	t.eq(AddedMaps.trail_of({}, trails), {}, "an entry without one")
	t.eq(AddedMaps.TRAILS_SCENE, FarmBuild.TRAILS_SCENE)
	t.ok(AddedMaps.TRAILS_SCENE.begins_with("res://generated/"), "the trails are written on every build: not under game/")
	t.eq(AddedMaps.KIND_META, RpgForage.KIND_META, "the recipe writes the metadata the game reads")
	t.eq(AddedMaps.WATER_META, RpgFishing.WATER_META)

func test_only_the_cells_of_the_sea_that_touch_the_land_block(t) -> void:
	# a sea three cells deep along the west side of a map of 6 x 4
	var water: Array[Vector2i] = []
	for y in 4:
		for x in 3:
			water.append(Vector2i(x, y))
	var shore := AddedMaps.shore_cells(water, Vector2i(6, 4))
	t.eq(shore, [Vector2i(2, 0), Vector2i(2, 1), Vector2i(2, 2), Vector2i(2, 3)], "the column beside the land, and nothing behind it")
	# a bay: every cell with land to one of its four sides
	water.erase(Vector2i(2, 1))
	shore = AddedMaps.shore_cells(water, Vector2i(6, 4))
	t.ok(shore.has(Vector2i(1, 1)) and shore.has(Vector2i(2, 0)) and shore.has(Vector2i(2, 2)))
	t.ok(not shore.has(Vector2i(0, 1)), "the cell behind the bay is behind it")
	t.eq(AddedMaps.shore_cells([], Vector2i(6, 4)), [])
	var all: Array[Vector2i] = [Vector2i(0, 0)]
	t.eq(AddedMaps.shore_cells(all, Vector2i(1, 1)), [], "a map that is all sea has no shore")

func test_a_drawn_ground_is_laid_in_runs_along_the_rows_of_the_inside(t) -> void:
	var size := Vector2i(7, 5)
	t.eq(AddedMaps.row_runs(size, []), [Rect2i(1, 1, 5, 1), Rect2i(1, 2, 5, 1), Rect2i(1, 3, 5, 1)], "the inside, not the edge")
	var water: Array[Vector2i] = [Vector2i(1, 1), Vector2i(2, 1), Vector2i(3, 2), Vector2i(5, 3), Vector2i(0, 2)]
	t.eq(AddedMaps.row_runs(size, water), [Rect2i(3, 1, 3, 1), Rect2i(1, 2, 2, 1), Rect2i(4, 2, 2, 1), Rect2i(1, 3, 4, 1)], "a run ends where the sea begins")
	var covered := 0
	for run in AddedMaps.row_runs(size, water):
		covered += run.size.x
	t.eq(covered, 15 - 4, "every cell of the inside that is no sea, once")
	t.eq(AddedMaps.row_runs(Vector2i(2, 2), []), [], "a map without an inside")

func test_on_a_map_of_a_kind_the_things_of_the_kind_lie_and_elsewhere_the_others(t) -> void:
	var plain := RpgForage.things_for(FORAGE, "")
	t.eq(plain.size(), 2, "the things that name no kind")
	t.eq(RpgForage.things_for(FORAGE, "forest"), plain, "a kind without things of its own has what the farm has")
	var beach := RpgForage.things_for(FORAGE, "beach")
	t.eq(beach.size(), 2)
	t.eq(str(beach[0]["id"]), "forage_shell")
	t.eq(RpgForage.things_for([FORAGE[0]], "beach").size(), 1, "a table without things of a beach: what there is")
	t.eq(RpgForage.things_for([], "beach"), [])
	var map := Node2D.new()
	t.eq(RpgForage.map_kind(map), "", "a map that says nothing")
	t.eq(RpgForage.map_kind(null), "")
	map.set_meta(RpgForage.KIND_META, "beach")
	t.eq(RpgForage.map_kind(map), "beach")
	map.free()

func test_what_lies_on_a_beach_this_morning_is_a_thing_of_the_beach(t) -> void:
	var helper: RefCounted = ForageTest.new()
	var game: Dictionary = helper.call("_game", 7)
	var forage: RpgForage = game["forage"]
	forage.things.clear()
	forage.fish.clear()
	forage.add_lists(FORAGE, FISH)
	var farm: Dictionary = helper.call("_map")
	var root: Node2D = farm["root"]
	forage.refresh(root)
	var on_farm := forage.lying(forage.places_on(root).size())
	t.ok(not on_farm.is_empty(), "something lies on the farm in spring")
	for item: StringName in on_farm.values():
		t.ok([&"forage_herb", &"forage_leek"].has(item), "%s is a thing of the farm" % item)
	# the same map says it is a beach: other things, and only a beach's
	root.set_meta(RpgForage.KIND_META, "beach")
	root.set("name", "FarmMap2")
	forage.refresh(root)
	var on_beach := forage.lying(forage.places_on(root).size())
	t.ok(not on_beach.is_empty(), "something lies on the beach")
	for item: StringName in on_beach.values():
		t.eq(item, &"forage_shell", "seaweed is summer's, a herb is the farm's")
	# what is picked up there is remembered under the map, beside the farm's own
	var spot: int = on_beach.keys()[0]
	t.ok(forage.pick(spot))
	t.ok(forage.picked_today().has(spot))
	var kept := RpgUtil.to_dict(RpgUtil.to_dict(RpgUtil.state().get_flag(RpgForage.FLAG_ENTITY, RpgForage.PICKED_KEY, {})).get("spots", {}))
	t.ok(kept.has("FarmMap2"), "the flag names the map: %s" % [kept.keys()])
	helper.call("_cleanup")

func test_the_rod_is_cast_into_the_sea_and_a_fish_of_the_sea_bites(t) -> void:
	var helper: RefCounted = ForageTest.new()
	var game: Dictionary = helper.call("_game", 9)
	var forage: RpgForage = game["forage"]
	forage.things.clear()
	forage.fish.clear()
	forage.add_lists(FORAGE, FISH)
	var map: Dictionary = helper.call("_map")
	var root: Node2D = map["root"]
	var field: RpgField = map["field"]
	var water_cell := Vector2i(7, 2)
	# a beach has no body that fills the can: its root says what the water is
	(map["water"] as RpgWaterSource).free()
	t.eq(RpgFishing.water_kind(field, water_cell), RpgFishing.POND, "water tiles and nothing else: a pond")
	root.set_meta(RpgFishing.WATER_META, "sea")
	t.eq(RpgFishing.water_kind(field, water_cell), "sea")
	t.eq(RpgFishing.fish_of(FISH, "spring", "morning", "sea"), ["fish_cod"])
	t.eq(RpgFishing.fish_of(FISH, "spring", "morning", RpgFishing.POND), ["fish_perch"])
	var farmer: RpgFarmer = helper.call("_farmer", game, map)
	var fishing: RpgFishing = game["fishing"]
	t.ok(helper.call("_cast", farmer), "the sea takes a cast")
	t.eq(fishing.state, RpgFishing.WAITING)
	t.eq(fishing.fish_id, "fish_cod", "and what is on the line is a fish of the sea")
	fishing.cancel()
	# a body that says it is a well still has no fish, whatever the map says
	var well := RpgWaterSource.new()
	well.kind = RpgFishing.WELL
	(map["entities"] as Node2D).add_child(well)
	t.eq(RpgFishing.water_kind(field, water_cell), RpgFishing.WELL)
	t.ok(not helper.call("_cast", farmer))
	helper.call("_cleanup")
