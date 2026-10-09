extends RefCounted
## Random-encounter zones (T12.53): the table's weighted draw, the zone's shapes, switching a zone
## off by flag, the step counter (teleports, grace steps) and a deterministic encounter after N
## steps with a fixed seed.

const Fixtures := preload("../lib/fixtures.gd")
const TMP_DIR := "user://test_encounters"

class FakeMode extends RpgTurnBasedMode:
	var player: Node2D = null
	var started: Array = []
	func _player_of(_router: RpgSceneRouter) -> Node2D:
		return player
	func start_encounter(data: RpgEncounterData) -> void:
		started.append(data)

func _rng(seed_value: int) -> RpgRng:
	var rng := RpgRng.new()
	rng.seed_value(seed_value)
	return rng

func _enemy(id: StringName) -> String:
	var def := RpgEnemyDefinition.new()
	def.id = id
	DirAccess.make_dir_recursive_absolute(TMP_DIR)
	var path := "%s/%s.tres" % [TMP_DIR, id]
	ResourceSaver.save(def, path)
	return path

func _table(groups: Array) -> RpgEncounterTable:
	var table := RpgEncounterTable.new()
	table.id = &"test"
	table.groups.assign(groups)
	return table

## A zone with a 4x4-tile (64 px) square polygon at the origin of `parent`.
func _square_zone(parent: Node, table: RpgEncounterTable) -> RpgEncounterZone:
	var zone := RpgEncounterZone.new()
	zone.table = table
	var poly := CollisionPolygon2D.new()
	poly.polygon = PackedVector2Array([Vector2(0, 0), Vector2(64, 0), Vector2(64, 64), Vector2(0, 64)])
	zone.add_child(poly)
	parent.add_child(zone)
	return zone

# ---------------------------------------------------------------- the table

func test_the_table_draws_by_weight_and_deterministically(t) -> void:
	var table := _table([{"enemies": ["a"], "weight": 3}, {"enemies": ["b"], "weight": 1}, {"enemies": ["c"], "weight": 0}])
	var counts := [0, 0, 0]
	var rng := _rng(7)
	for i in 400:
		counts[table.pick(rng)] += 1
	t.eq(counts[2], 0, "a weight of 0 is never drawn")
	t.ok(counts[0] > 250 and counts[1] > 60, "about 3 to 1: %s" % str(counts))
	var first: Array = []
	var second: Array = []
	var a := _rng(12345)
	var b := _rng(12345)
	for i in 20:
		first.append(table.pick(a))
		second.append(table.pick(b))
	t.eq(first, second, "the same seed draws the same groups")
	t.eq(_table([]).pick(rng), -1)
	t.eq(_table([{"enemies": ["a"], "weight": 0}]).pick(rng), -1)

func test_the_table_builds_the_encounter_and_reports_problems(t) -> void:
	var slime := _enemy(&"slime")
	var table := _table([{"enemies": [slime, slime], "weight": 1}])
	table.can_escape = false
	var data := table.encounter_for(0)
	t.eq(data.enemies.size(), 2)
	t.eq(data.enemies[0].id, &"slime")
	t.ok(not data.can_escape)
	t.eq(data.entity_id, "", "a random battle defeats nothing on the map")
	t.eq(RpgEncounterTable.problems_of(table.groups), [] as Array[String])
	var found := RpgEncounterTable.problems_of([{"enemies": [], "weight": 1}, {"enemies": ["ghost"], "weight": 0}])
	t.eq(found.size(), 2, str(found))
	t.ok(found[0].contains("no enemies") and found[1].contains("'ghost'"))
	t.eq(RpgEncounterTable.problems_of([]), ["the table has no groups"] as Array[String])
	t.ok(RpgEncounterTable.problems_of([{"enemies": [slime], "weight": 0}]).has("every group has a weight of 0"))

# ---------------------------------------------------------------- the zone

func test_a_zone_is_its_polygon_rectangle_or_circle(t) -> void:
	var map := Node2D.new()
	var zone := _square_zone(map, _table([{"enemies": ["a"]}]))
	zone.position = Vector2(100, 0)
	t.ok(zone.contains(Vector2(132, 32)))
	t.ok(not zone.contains(Vector2(32, 32)), "the zone moved with its node")
	var rect_zone := RpgEncounterZone.new()
	var holder := CollisionShape2D.new()
	var rect := RectangleShape2D.new()
	rect.size = Vector2(32, 16)
	holder.shape = rect
	holder.position = Vector2(-200, 0)
	rect_zone.add_child(holder)
	map.add_child(rect_zone)
	t.ok(rect_zone.contains(Vector2(-215, 7)))
	t.ok(not rect_zone.contains(Vector2(-215, 9)))
	var circle := CircleShape2D.new()
	circle.radius = 10
	holder.shape = circle
	t.ok(rect_zone.contains(Vector2(-200, 9)) and not rect_zone.contains(Vector2(-200, 11)))
	map.free()

func test_a_zone_can_be_the_cells_painted_on_an_encounters_layer(t) -> void:
	var map := Node2D.new()
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(16, 16)
	var source := TileSetAtlasSource.new()
	var image := Image.create(32, 16, false, Image.FORMAT_RGBA8)
	source.texture = ImageTexture.create_from_image(image)
	source.texture_region_size = Vector2i(16, 16)
	source.create_tile(Vector2i(0, 0))
	tiles.add_source(source, 0)
	var layer := TileMapLayer.new()
	layer.name = "Encounters"
	layer.tile_set = tiles
	layer.set_cell(Vector2i(2, 1), 0, Vector2i(0, 0))
	map.add_child(layer)
	var zone := RpgEncounterZone.new()
	zone.table = _table([{"enemies": ["a"]}])
	map.add_child(zone)
	t.eq(zone.cells(), layer, "a zone without a shape uses the map's Encounters layer")
	t.ok(zone.contains(Vector2(40, 20)), "inside the painted cell (2, 1)")
	t.ok(not zone.contains(Vector2(8, 8)))
	if not zone.is_node_ready():  # add_child readies it once the tree runs
		zone._ready()
	t.ok(not layer.visible, "the cells layer is hidden in the game")
	map.free()

func test_a_zone_is_switched_off_by_its_flag_or_without_a_table(t) -> void:
	var state := Fixtures.install_state()
	var map := Node2D.new()
	var zone := _square_zone(map, _table([{"enemies": ["a"]}]))
	zone.disabled_flag = "bridge.repaired"
	t.ok(zone.is_enabled())
	t.eq(RpgEncounterZone.zone_at(map, Vector2(10, 10)), zone)
	state.set_flag("bridge", "repaired", true)
	t.ok(not zone.is_enabled())
	t.ok(RpgEncounterZone.zone_at(map, Vector2(10, 10)) == null, "a switched-off zone brings nothing")
	state.set_flag("bridge", "repaired", false)
	zone.table = null
	t.ok(not zone.is_enabled(), "no table, no battles")
	map.free()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- steps

func test_steps_are_whole_tiles_walked_and_teleports_do_not_count(t) -> void:
	var steps := RpgEncounterSteps.new()
	steps.tile_px = 16.0
	t.eq(steps.walk(Vector2(0, 0)), 0, "the first position only starts the count")
	t.eq(steps.walk(Vector2(10, 0)), 0)
	t.eq(steps.walk(Vector2(20, 0)), 1, "20 px walked: one step, 4 px carried")
	t.eq(steps.walk(Vector2(20, 28)), 2, "4 + 28 = 32 px: two steps")
	t.eq(steps.walk(Vector2(200, 28)), 0, "a jump of 180 px is a door, not walking")
	t.eq(steps.walk(Vector2(216, 28)), 1)
	steps.reset()
	t.eq(steps.walk(Vector2(0, 0)), 0, "after a reset the count starts afresh")
	t.eq(steps.steps_taken, 4)

func test_an_encounter_comes_after_the_same_number_of_steps_with_the_same_seed(t) -> void:
	var map := Node2D.new()
	var zone := _square_zone(map, _table([{"enemies": ["a"]}]))
	zone.steps_per_encounter = 8.0
	var first_battle: Array = []
	for attempt in 2:
		var steps := RpgEncounterSteps.new()
		var rng := _rng(12345)
		var n := 0
		while n < 500:
			n += 1
			if steps.step(map, Vector2(32, 32), rng) != null:
				break
		first_battle.append(n)
	t.eq(first_battle[0], first_battle[1], "seed 12345 brings the first battle at the same step")
	t.ok(first_battle[0] < 500)
	var outside := RpgEncounterSteps.new()
	var rng := _rng(12345)
	for i in 200:
		t.ok(outside.step(map, Vector2(500, 500), rng) == null, "no battles outside the zone")
	map.free()

func test_grace_steps_bring_no_battle(t) -> void:
	var map := Node2D.new()
	var zone := _square_zone(map, _table([{"enemies": ["a"]}]))
	zone.steps_per_encounter = 1.0  # every step brings a battle once the grace is over
	var steps := RpgEncounterSteps.new()
	steps.grace_steps = RpgEncounterSteps.GRACE_STEPS
	var rng := _rng(1)
	for i in RpgEncounterSteps.GRACE_STEPS:
		t.ok(steps.step(map, Vector2(10, 10), rng) == null, "grace step %d" % (i + 1))
	t.eq(steps.step(map, Vector2(10, 10), rng), zone, "the first step after the grace")
	map.free()

func test_the_turn_based_mode_starts_a_random_battle_and_grants_grace(t) -> void:
	var state := Fixtures.install_state()
	state.rng.seed_value(99)
	var router := Fixtures.install("SceneRouter", "res://addons/rpg_runtime/world/scene_router.gd") as RpgSceneRouter
	var map := RpgMapRoot.new()
	var player := Node2D.new()
	map.add_child(player)
	router.current_map = map
	var zone := _square_zone(map, _table([{"enemies": [_enemy(&"bat")], "weight": 1}]))
	zone.steps_per_encounter = 1.0
	var mode := FakeMode.new()
	mode.player = player
	mode.count_steps()  # the first position
	for i in 4:
		player.position.x += 4.0
		mode.count_steps()
	t.eq(mode.started.size(), 1, "one tile walked in an every-step zone")
	var data: RpgEncounterData = mode.started[0]
	t.eq(data.enemies[0].id, &"bat")
	mode._in_combat = true
	mode._on_pop_finished(null)
	t.eq(mode.steps.grace_steps, RpgEncounterSteps.GRACE_STEPS, "a battle grants the grace steps")
	mode.count_steps()
	for i in 4 * RpgEncounterSteps.GRACE_STEPS:
		player.position.x += 4.0 if i % 8 < 4 else -4.0
		mode.count_steps()
	t.eq(mode.started.size(), 1, "no battle during the grace steps")
	player.position.x += 4.0
	mode.count_steps()
	for i in 3:
		player.position.x += 4.0
		mode.count_steps()
	t.eq(mode.started.size(), 2, "the next step after the grace brings one")
	mode.free()
	router.current_map = null
	map.free()
	Fixtures.uninstall("SceneRouter")
	Fixtures.uninstall_state()
