extends RefCounted
## MapBuild.plan (T11.25): the same plans as the Python planner (rpggen/core/map_preview.py), checked
## against the shared fixture map_plan_cases.json, plus the rules that must hold for any options.

const MapBuild := preload("../../builder/lib/map_build.gd")
const JsonUtil := preload("../../builder/lib/json_util.gd")
const FIXTURE := "res://tests/fixtures/map_plan_cases.json"

func test_plans_match_the_python_planner(t) -> void:
	var cases: Variant = JsonUtil.read(FIXTURE)
	t.ok(cases is Array and cases.size() == 20, "fixture loads with 20 cases")
	var n := 0
	for c in cases:
		n += 1
		var plan := MapBuild.plan(c["options"], int(c["seed"]), c["building"], String(c["archetype"]))
		var got := JSON.stringify(MapBuild.to_json(plan), "", true)
		var want := JSON.stringify(RpgUtil.restore_numbers(c["plan"]), "", true)
		t.eq(got, want, "case %d (%s, seed %d)" % [n, c["archetype"], int(c["seed"])])

func test_the_default_options_are_the_old_constants(t) -> void:
	var building := {"size": [5, 4], "door": [2, 4]}
	var plan := MapBuild.plan({}, 12345, building, "turn_based")
	t.ok(plan["is_default"])
	t.eq(plan["size"], Vector2i(40, 24))
	t.eq(plan["buildings"], [Vector2i(8, 6)])
	t.eq(plan["spawn"], Vector2i(12, 12))
	t.eq(plan["npcs"], [Vector2i(16, 12)])
	t.eq(plan["chests"], [Vector2i(18, 8)])
	t.eq(plan["enemies"], [Vector2i(28, 12)])
	t.eq(plan["decorations"].size(), 8)
	var arpg := MapBuild.plan({}, 12345, building, "arpg")
	t.eq(arpg["enemies"], [Vector2i(28, 12), Vector2i(32, 12)])

func test_the_ground_option_alone_keeps_the_default_layout(t) -> void:
	var plan := MapBuild.plan({"ground": "pack.tiles.sand"}, 1, {"size": [5, 4], "door": [2, 4]}, "turn_based")
	t.ok(plan["is_default"])

func test_path_cells_run_along_the_row_then_up_the_column(t) -> void:
	var cells := MapBuild.path_cells(Vector2i(12, 12), Vector2i(10, 10))
	t.eq(cells[0], Vector2i(12, 12))
	t.ok(cells.has(Vector2i(10, 12)) and cells.has(Vector2i(10, 10)) and cells.has(Vector2i(10, 11)))

func test_random_option_sets_stay_valid(t) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 2024
	var building := {"size": [5, 4], "door": [2, 4]}
	for i in 60:
		var options := {
			"size": [rng.randi_range(24, 96), rng.randi_range(24, 96)],
			"buildings": rng.randi_range(0, 4), "npcs": rng.randi_range(0, 6),
			"enemies": rng.randi_range(0, 8), "chests": rng.randi_range(0, 4),
			"decorations": rng.randi_range(0, 40), "ground_patches": rng.randi_range(0, 20),
		}
		var plan := MapBuild.plan(options, rng.randi_range(0, 99999), building, "turn_based")
		var size: Vector2i = plan["size"]
		var used := {}
		for key in ["npcs", "chests", "enemies", "decorations"]:
			for tile in plan[key]:
				t.ok(tile.x >= 1 and tile.x <= size.x - 2 and tile.y >= 1 and tile.y <= size.y - 2, "inside the map (case %d)" % i)
				t.ok(not used.has(tile), "one entity per tile (case %d)" % i)
				used[tile] = true
		t.ok(plan["buildings"].size() <= int(options["buildings"]), "no more buildings than asked (case %d)" % i)

# ------------------------------------------------------------------ one interior per house (T13.12)

const InteriorRecipe := preload("res://builder/recipes/interior_recipe.gd")
const ObjectIndex := preload("../../builder/lib/object_index.gd")

func test_the_plan_gives_each_building_its_interior_and_door_column(t) -> void:
	var house := {"size": [5, 4], "door": [2, 4]}
	var plan := MapBuild.plan({}, 12345, house, "turn_based")
	t.eq(plan["interiors"], [{"id": "interior_1", "size": [10, 8], "door": 2}])
	var several := MapBuild.plan({"size": [64, 40], "buildings": 4}, 7, house, "turn_based")
	var count: int = several["buildings"].size()
	t.ok(count >= 2, "several houses")
	t.eq(several["interiors"].size(), count)
	t.eq(several["interiors"][count - 1]["id"], "interior_%d" % count)
	var wide := MapBuild.interiors_for(2, {"size": [14, 6], "door": [9, 6]})
	t.eq(wide[1], {"id": "interior_2", "size": [14, 8], "door": 9})
	t.eq(MapBuild.interiors_for(1, {"size": [3, 3], "door": [0, 3]})[0]["door"], 1, "never in a corner")
	t.eq(MapBuild.interiors_for(1, {"size": [12, 3], "door": [11, 3]})[0]["door"], 10)
	t.eq(MapBuild.interiors_for(3, {}).size(), 0)

func test_each_house_has_its_own_map_and_spawn_to_return_to(t) -> void:
	t.eq(InteriorRecipe.interior_path(1), "res://game/maps/interior_1.tscn")
	t.eq(InteriorRecipe.interior_path(3), "res://game/maps/interior_3.tscn")
	t.eq(InteriorRecipe.interior_id(2), "interior_2")
	# the first house keeps the spawn id every project has had; the others get their number
	var first := InteriorRecipe.exit_spawn_for("pack.objects.town.house", 1)
	t.eq(first, ObjectIndex.exit_spawn_id("pack.objects.town.house"))
	t.eq(InteriorRecipe.exit_spawn_for("pack.objects.town.house", 2), StringName(String(first) + "_2"))
	var entries := [
		{"id": "p.house", "name": "house", "role": "BUILDING", "tags": []},
		{"id": "p.bedroll", "name": "Bedroll", "role": "DECORATION", "tags": []},
		{"id": "p.desk", "name": "desk", "role": "DECORATION", "tags": ["table"]},
	]
	t.eq(InteriorRecipe.furniture_entry(entries, "bed")["id"], "p.bedroll")
	t.eq(InteriorRecipe.furniture_entry(entries, "table")["id"], "p.desk")
	t.eq(InteriorRecipe.furniture_entry(entries, "throne"), {})

