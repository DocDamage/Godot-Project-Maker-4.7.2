extends RefCounted
## The pure parts of the farm's map recipe (T17.06) and of the people's recipe (T17.09): how a
## plan is read, which building and which pictures of the packs stand for what it names, where
## the farmer starts, where the village's door to the farm and the people's places lie, and
## what people.json holds of a person.

const FarmMap := preload("../../builder/recipes/farm/farm_map_recipe.gd")
const People := preload("../../builder/recipes/farm/people_recipes.gd")
const MapBuild := preload("../../builder/lib/map_build.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")

const HOUSE := {"id": "farm_house", "kind": "house", "rect": [4, 3, 6, 4], "door": [6, 7],
	"interior": {"id": "farm_house", "size": [8, 7], "door": [3, 6], "arrive": [3, 5], "bed": {"cell": [1, 1], "size": [1, 2]}, "start": [2, 2]}}
const COOP := {"id": "farm_coop", "kind": "coop", "rect": [20, 4, 4, 3], "door": [21, 7],
	"interior": {"id": "farm_coop", "size": [8, 6], "door": [2, 5], "arrive": [2, 4], "trough": [1, 1], "stalls": [[3, 1], [4, 1]]},
	"yard": {"rect": [19, 7, 6, 3], "fence": [[18, 7]], "gate": [20, 10], "side": "S"}}

func _farm() -> Dictionary:
	return {
		"size": [40, 30], "house": HOUSE, "animal_houses": [COOP],
		"bin": {"cell": [10, 6], "front": [10, 7]},
		"paths": [[6, 7], [6, 8], [7, 8]],
		"start": {"map": "farm_house", "cell": [2, 2], "facing": "down"},
		"exit": {"edge": "E", "cell": [39, 20], "spawn": [38, 20], "facing": "left", "to": "starter_map"},
	}

func _entry(id: String, role: String, size: Vector2i, tags: Array = [], door: Array = []) -> Dictionary:
	return {"id": id, "name": id.get_slice(".", 1), "role": role, "tags": tags, "texture_path": "res://none.png",
		"region": [0, 0, size.x, size.y], "origin": [size.x / 2, size.y - 1], "door": door}

func test_a_plan_is_read_as_cells_and_rectangles(t) -> void:
	t.eq(FarmMap.cell_of([3.0, 4.0]), Vector2i(3, 4))
	t.eq(FarmMap.cell_of(null), Vector2i.ZERO)
	t.eq(FarmMap.rect_of([4, 3, 6, 4]), Rect2i(4, 3, 6, 4))
	t.eq(FarmMap.rect_of([4, 3]), Rect2i())
	t.eq(FarmMap.cells_of([[1, 2], [3, 4]]), [Vector2i(1, 2), Vector2i(3, 4)])
	var farm := _farm()
	t.eq(FarmMap.buildings_of(farm).size(), 2)
	t.eq(FarmMap.map_paths(farm), ["res://game/maps/farm.tscn", "res://game/maps/farm_house.tscn", "res://game/maps/farm_coop.tscn"])
	t.eq(FarmMap.map_paths({}), [], "no plan, no map")
	t.eq(FarmMap.room_path(COOP), "res://game/maps/farm_coop.tscn")
	t.eq(FarmMap.door_spawn("farm_house"), "farm_house_door")
	t.eq(FarmMap.start_of(farm), {"map": "res://game/maps/farm_house.tscn", "spawn": "start"})
	t.eq(FarmMap.start_of({}), {})

func test_the_farmer_starts_on_the_plans_cell_or_east_of_a_wider_bed(t) -> void:
	var room := Vector2i(8, 7)
	t.eq(FarmMap.start_cell(Vector2i(2, 2), Vector2i(1, 1), Vector2i(1, 2), room), Vector2i(2, 2))
	t.eq(FarmMap.start_cell(Vector2i(2, 2), Vector2i(1, 1), Vector2i(2, 2), room), Vector2i(3, 2), "a bed two cells wide lies on the plan's cell")
	t.eq(FarmMap.start_cell(Vector2i(2, 2), Vector2i(1, 1), Vector2i(3, 1), room), Vector2i(2, 2), "a short one leaves the plan's cell free")
	t.eq(FarmMap.start_cell(Vector2i(2, 2), Vector2i(1, 1), Vector2i(9, 2), room), Vector2i(6, 2), "never in the wall")

func test_the_can_is_filled_at_the_water_beside_the_place(t) -> void:
	var pond: Array[Vector2i] = [Vector2i(5, 5), Vector2i(6, 5), Vector2i(5, 6), Vector2i(6, 6)]
	t.eq(FarmMap.water_beside(Vector2i(6, 7), pond), Vector2i(6, 6), "north of the place")
	t.eq(FarmMap.water_beside(Vector2i(7, 5), pond), Vector2i(6, 5), "west of it")
	t.eq(FarmMap.water_beside(Vector2i(9, 9), pond), Vector2i(6, 6), "else the nearest")

func test_a_building_of_the_packs_stands_for_one_of_the_plan_when_it_fits(t) -> void:
	var entries: Array[Dictionary] = [
		_entry("p.barn", "BUILDING", Vector2i(96, 64), ["barn"], [40, 63]),
		_entry("p.coop", "BUILDING", Vector2i(64, 48), ["coop"], [24, 47]),
		_entry("p.house", "BUILDING", Vector2i(96, 64), [], [40, 63]),
		_entry("p.shed", "BUILDING", Vector2i(80, 64), [], [40, 63]),
		_entry("p.tree", "DECORATION", Vector2i(96, 64)),
	]
	t.eq(FarmMap.building_entry(entries, "house", Vector2i(6, 4), 2, 16).get("id"), "p.house", "not the barn of the same size")
	t.eq(FarmMap.building_entry(entries, "house", Vector2i(5, 4), 2, 16).get("id"), "p.shed")
	t.eq(FarmMap.building_entry(entries, "house", Vector2i(6, 4), 2, 16, "p.barn").get("id"), "p.barn", "the chosen starter building first")
	t.eq(FarmMap.building_entry(entries, "house", Vector2i(6, 4), 3, 16), {}, "another door column: drawn")
	t.eq(FarmMap.building_entry(entries, "house", Vector2i(7, 4), 2, 16), {}, "another footprint: drawn")
	t.eq(FarmMap.building_entry(entries, "coop", Vector2i(4, 3), 1, 16).get("id"), "p.coop")
	t.eq(FarmMap.building_entry(entries, "barn", Vector2i(6, 4), 2, 16).get("id"), "p.barn")
	t.eq(FarmMap.building_entry(entries, "coop", Vector2i(6, 4), 2, 16), {}, "a house is no coop")
	var only_barn: Array[Dictionary] = [entries[0]]
	t.eq(FarmMap.building_entry(only_barn, "house", Vector2i(6, 4), 2, 16).get("id"), "p.barn", "a pack with nothing else")

func test_the_pictures_of_the_packs_are_found_by_their_words(t) -> void:
	t.eq(Array(FarmMap.name_words("Oak-Tree_02")), ["oak", "tree", "02"])
	var entries: Array[Dictionary] = [
		_entry("p.big_rock", "DECORATION", Vector2i(64, 64)),
		_entry("p.oak_tree", "DECORATION", Vector2i(32, 48)),
		_entry("p.rock_small", "DECORATION", Vector2i(16, 16)),
		_entry("p.street", "DECORATION", Vector2i(16, 16)),
		_entry("p.thing", "DECORATION", Vector2i(16, 16), ["stump"]),
		_entry("p.tree_house", "BUILDING", Vector2i(32, 48)),
	]
	var ids := func(found: Array[Dictionary]) -> Array:
		var out: Array = []
		for entry in found:
			out.append(entry["id"])
		return out
	t.eq(ids.call(FarmMap.thing_entries(entries, "tree", 16)), ["p.oak_tree"], "a decoration, by a whole word")
	t.eq(ids.call(FarmMap.thing_entries(entries, "rock", 16)), ["p.rock_small"], "not one of four cells a side")
	t.eq(ids.call(FarmMap.thing_entries(entries, "stump", 16)), ["p.thing"], "or by a tag")
	t.eq(ids.call(FarmMap.thing_entries(entries, "grass", 16)), [])
	var none: Array[Dictionary] = []
	t.eq(FarmMap.thing_texture(none, 3), null, "nothing of the packs: drawn")

func test_things_are_solid_when_they_stand_in_the_way(t) -> void:
	var stump := FarmMap.make_thing("stump", null, 16, true)
	t.ok(stump is StaticBody2D and (stump as StaticBody2D).get_collision_layer_value(1))
	t.ok(stump.get_node("Shape") != null and stump.get_node("Sprite").get_child_count() == 2, "drawn of two boxes")
	t.eq(stump.get("blocks_movement"), true)
	var grass := FarmMap.make_thing("grass", null, 16, false)
	t.ok(not (grass is StaticBody2D) and grass.get_node_or_null("Shape") == null, "grass is walked over")
	t.eq(grass.get("entity_id"), "", "an id is given to what can be cleared")
	var fence := FarmMap.make_thing("fence", null, 16, true)
	var whole := (fence.get_node("Shape") as CollisionShape2D).shape as RectangleShape2D
	t.eq(whole.size, Vector2(16, 16), "a fence fills its cell")
	var house := FarmMap.drawn_building("house", Vector2i(6, 4), 2, 16)
	var walls := (house.get_node("Shape") as CollisionShape2D).shape as RectangleShape2D
	t.eq(walls.size, Vector2(96, 64))
	t.eq((house.get_node("Door") as Node2D).position, Vector2(-8, 0), "the door in its column")
	for node: Node in [stump, grass, fence, house]:
		node.free()

func test_the_sign_stands_beside_the_door_where_no_path_runs(t) -> void:
	var farm := _farm()
	t.eq(FarmMap.sign_cell(farm), Vector2i(7, 7), "east of the cell before the door")
	farm["paths"] = [[6, 7], [7, 7]]
	t.eq(FarmMap.sign_cell(farm), Vector2i(5, 7), "west when the path turns east")
	farm["paths"] = [[5, 7], [6, 7], [7, 7]]
	t.eq(FarmMap.sign_cell(farm), Vector2i(-1, -1))

# ---------------------------------------------------------------- the people

func test_what_people_json_holds_of_a_person(t) -> void:
	t.eq(People.spot_name("square", 0), "square")
	t.eq(People.spot_name("home_1", 2), "home_1_3")
	var places := People.places_for(5, 2)
	t.eq(places["home"], [{"map": "starter_map", "place": "home_1_2"}, {"map": "starter_map", "place": "home_2_2"}])
	t.eq(places["square"], {"map": "starter_map", "place": "square_6"})
	t.eq(People.places_for(0, 0)["home"], [{"map": "starter_map", "place": "home_1"}], "a village without a house has one home")
	var person := {
		"id": "anna", "name": "Anna", "asset": "pack.npc", "home": 2.0, "job": "", "pattern": "villager",
		"schedule": [{"hour": 6.0, "place": "home"}, {"hour": 9.0, "days": [0.0, 3.0], "place": "square"}, {"hour": 14.0, "place": "pond"}],
		"loves": ["crop_corn"], "likes": [], "dislikes": [],
	}
	var entry := People.person_entry(person, places, "res://npc.tscn")
	t.ok(not entry.has("asset") and not entry.has("pattern"), "what only the planner needs is left out")
	t.eq(entry["scene"], "res://npc.tscn")
	t.eq(typeof(entry["home"]), TYPE_INT, "whole numbers, not the floats JSON gave back")
	t.eq(entry["schedule"][0], {"hour": 6, "map": "starter_map", "place": "home_2_2"}, "the home of its house")
	t.eq(entry["schedule"][1], {"hour": 9, "days": [0, 3], "map": "starter_map", "place": "square_6"})
	t.eq(entry["schedule"][2], {"hour": 14, "place": "pond"}, "a place nobody placed keeps its name")
	person["home"] = 7
	t.eq(People.person_entry(person, places, "")["schedule"][0], {"hour": 6, "place": "home"}, "a house the village does not have")

func test_the_places_of_a_village_are_free_cells_and_no_two_are_one(t) -> void:
	var building := {"size": [5, 4], "door": [2, 4]}
	var layout := MapBuild.plan({}, 12345, building, "farm")
	var none: Array[Vector2i] = []
	var spots := People.village_spots(layout, Vector2i(5, 4), none)
	var taken := People.occupied(layout, Vector2i(5, 4), none)
	var door: Vector2i = layout["doors"][0]
	t.eq(spots["home_1"], door + Vector2i(2, 0), "beside the door, never next to it")
	t.eq(spots["home"], spots["home_1"])
	t.eq(spots["work"], Vector2i(17, 12), "beside the villager who keeps the shop")
	for wanted: String in ["home_1_2", "home_1_3", "home_1_4", "square", "square_2", "square_6"]:
		t.ok(spots.has(wanted), wanted)
	var seen := {}
	for place: String in spots.keys():
		var cell: Vector2i = spots[place]
		t.ok(not taken.has(cell), "%s lies on something" % place)
		t.ok(place == "home" or not seen.has(cell), "%s shares its cell" % place)
		seen[cell] = true
	t.eq(spots, People.village_spots(layout, Vector2i(5, 4), none), "the same every time")
	# a village without a house has a home all the same
	var bare := MapBuild.plan({"buildings": 0}, 7, {}, "farm")
	t.ok(People.village_spots(bare, Vector2i.ZERO, none).has("home_1"))

func test_the_villages_door_to_the_farm_is_opposite_the_farms_way_out(t) -> void:
	var layout := MapBuild.plan({}, 12345, {"size": [5, 4], "door": [2, 4]}, "farm")
	var size: Vector2i = layout["size"]
	var none: Array[Vector2i] = []
	var edges := {"E": "W", "W": "E", "S": "N"}
	for edge: String in edges.keys():
		var door := People.farm_door(layout, Vector2i(5, 4), none, {"exit": {"edge": edge}})
		var cell: Vector2i = door["cell"]
		t.eq(door["edge"], edges[edge])
		t.ok(cell.x == 0 or cell.y == 0 or cell.x == size.x - 1 or cell.y == size.y - 1, "in the wall")
		var gap: Vector2i = layout["exit_gap"]
		t.ok(absi(cell.x - gap.x) + absi(cell.y - gap.y) > 2, "not beside the gap of the east exit")
		var arrive: Vector2i = door["spawn"]
		t.ok(not People.occupied(layout, Vector2i(5, 4), none).has(arrive), "on free ground")
	t.eq(People.farm_door(layout, Vector2i(5, 4), none, {}), {}, "a plan without a way out")
	var west := People.farm_door(layout, Vector2i(5, 4), none, {"exit": {"edge": "E"}})
	t.eq(west["cell"], Vector2i(0, 8))
	t.eq(west["spawn"], Vector2i(1, 8))
	t.eq(west["facing"], "right")

func test_spots_are_picked_nearest_first_and_marked_as_taken(t) -> void:
	var taken := {Vector2i(10, 10): true}
	var preferred: Array[Vector2i] = [Vector2i(10, 10), Vector2i(12, 10)]
	var found := People.pick_spots(Vector2i(10, 10), 3, Vector2i(30, 20), taken, preferred)
	t.eq(found[0], Vector2i(12, 10), "the preferred cell that is free")
	t.eq(found.size(), 3)
	for cell in found:
		t.ok(taken.has(cell) and cell != Vector2i(10, 10))
	t.ok(found[1] != found[2])
	var full := {}
	for x in 10:
		for y in 10:
			full[Vector2i(x, y)] = true
	t.eq(People.pick_spots(Vector2i(5, 5), 2, Vector2i(10, 10), full), [Vector2i(5, 5), Vector2i(5, 5)], "a village with no room")

# ---------------------------------------------------------------- the checks

func test_the_farms_map_is_a_map_of_the_world_for_the_door_check(t) -> void:
	var path := "user://test_farm_world_plan.json"
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify({"areas": [{"id": "woods", "map": "game/maps/woods.tscn"}], "farm": {"map": {"map": "game/maps/farm.tscn"}}}))
	file.close()
	t.eq(ContentChecks.world_maps(path), ["res://game/maps/woods.tscn", "res://game/maps/farm.tscn"])
	file = FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify({"areas": [], "farm": {"crops": []}}))
	file.close()
	t.eq(ContentChecks.world_maps(path), [], "a farm from before it had a map of its own")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
