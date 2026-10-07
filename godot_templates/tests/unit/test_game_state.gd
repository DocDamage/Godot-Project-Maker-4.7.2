extends RefCounted
## GameState, RpgPersistent and the item registry (T6.04).

const Fixtures := preload("../lib/fixtures.gd")

func test_flags_set_get_and_event(t) -> void:
	var state := Fixtures.install_state()
	var seen := []
	RpgUtil.events().entity_state_changed.connect(func(id: String, key: String, value: Variant) -> void: seen.append([id, key, value]))
	t.ok(state.get_flag("npc", "talked") == null)
	t.eq(state.get_flag("npc", "talked", false), false)
	state.set_flag("npc", "talked", true)
	t.eq(state.get_flag("npc", "talked"), true)
	t.eq(seen, [["npc", "talked", true]])
	t.eq(state.flag_count(), 1)
	Fixtures.uninstall_state()

func test_gold_never_goes_negative_and_emits(t) -> void:
	var state := Fixtures.install_state()
	var seen := []
	RpgUtil.events().gold_changed.connect(func(total: int) -> void: seen.append(total))
	state.gold = 30
	state.gold = -5
	t.eq(state.gold, 0)
	t.eq(seen, [30, 0])
	Fixtures.uninstall_state()

func test_new_game_without_data_files_uses_defaults(t) -> void:
	var state := Fixtures.install_state()
	state.set_flag("x", "y", 1)
	state.new_game()
	t.eq(state.flags.size(), 0)
	t.eq(state.gold, 50)
	t.eq(state.player_stats.hp, state.player_stats.max_hp)
	t.eq(state.playtime_s, 0.0)
	Fixtures.uninstall_state()

func test_to_dict_from_dict_round_trip_through_json(t) -> void:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion", 5)})
	state.new_game()
	state.gold = 77
	state.inventory.add(&"potion", 7)
	state.set_flag("chest_1", "opened", true)
	state.set_flag("npc_1", "count", 3)
	state.quests["q1"] = "started"
	state.current_map = "res://game/maps/starter_map.tscn"
	state.current_spawn = &"door"
	state.player_position = Vector2(12.5, 40.0)
	state.player_facing = "left"
	state.playtime_s = 12.5
	state.player_stats.attack = 9
	state.rng.seed_value(5)
	state.rng.randf()
	var snapshot: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	var expected_next: int = state.rng.randi_range(0, 99999)
	state.new_game()
	state.from_dict(snapshot)
	t.eq(state.gold, 77)
	t.eq(state.inventory.count(&"potion"), 7)
	t.eq(state.get_flag("chest_1", "opened"), true)
	t.eq(state.get_flag("npc_1", "count"), 3)
	t.eq(typeof(state.get_flag("npc_1", "count")), TYPE_INT)
	t.eq(state.quests["q1"], "started")
	t.eq(state.current_map, "res://game/maps/starter_map.tscn")
	t.eq(state.current_spawn, &"door")
	t.eq(state.player_position, Vector2(12.5, 40.0))
	t.eq(state.player_facing, "left")
	t.near(state.playtime_s, 12.5)
	t.eq(state.player_stats.attack, 9)
	t.eq(state.rng.randi_range(0, 99999), expected_next, "rng state is saved")
	Fixtures.uninstall_state()

func test_give_experience_emits_level_ups(t) -> void:
	var state := Fixtures.install_state()
	state.new_game()
	var levels := []
	RpgUtil.events().level_up.connect(func(_id: StringName, level: int) -> void: levels.append(level))
	t.eq(state.give_experience(38), 2)
	t.eq(levels, [2, 3])
	Fixtures.uninstall_state()

func test_load_items_first_duplicate_wins(t) -> void:
	var state := Fixtures.install_state()
	var dir := "user://test_items_%d" % Time.get_ticks_usec()
	DirAccess.make_dir_recursive_absolute(dir)
	var a := Fixtures.item(&"potion")
	a.value = 1
	var b := Fixtures.item(&"potion")
	b.value = 2
	var c := Fixtures.item(&"elixir")
	ResourceSaver.save(a, dir + "/a_potion.tres")
	ResourceSaver.save(b, dir + "/b_potion.tres")
	ResourceSaver.save(c, dir + "/c_elixir.tres")
	state.load_items(dir)
	t.eq(state.items.size(), 2)
	t.eq((state.items[&"potion"] as RpgItemDefinition).value, 1)
	for f in DirAccess.get_files_at(dir):
		DirAccess.remove_absolute(dir + "/" + f)
	DirAccess.remove_absolute(dir)
	Fixtures.uninstall_state()

class FakeEntity extends Node2D:
	var entity_id := "fake_1"
	var opened_applied := false
	func apply_opened_state() -> void:
		opened_applied = true

func test_persistent_frees_a_defeated_entity(t) -> void:
	var state := Fixtures.install_state()
	state.set_flag("fake_1", "defeated", true)
	var entity := FakeEntity.new()
	var p := RpgPersistent.new()
	entity.add_child(p)
	Fixtures.tree().root.add_child(entity)
	p._ready()  # the root is not in the tree yet while --script runs _initialize
	t.ok(entity.is_queued_for_deletion())
	Fixtures.tree().root.remove_child(entity)
	entity.free()
	Fixtures.uninstall_state()

func test_persistent_applies_the_opened_state(t) -> void:
	var state := Fixtures.install_state()
	state.set_flag("fake_1", "opened", true)
	var entity := FakeEntity.new()
	var p := RpgPersistent.new()
	entity.add_child(p)
	Fixtures.tree().root.add_child(entity)
	p._ready()
	t.ok(entity.opened_applied)
	t.ok(not entity.is_queued_for_deletion())
	Fixtures.tree().root.remove_child(entity)
	entity.free()
	Fixtures.uninstall_state()

func test_persistent_leaves_a_fresh_entity_alone(t) -> void:
	var state := Fixtures.install_state()
	var entity := FakeEntity.new()
	entity.add_child(RpgPersistent.new())
	Fixtures.tree().root.add_child(entity)
	t.ok(not entity.opened_applied and not entity.is_queued_for_deletion())
	Fixtures.tree().root.remove_child(entity)
	entity.free()
	t.ok(state != null)
	Fixtures.uninstall_state()
