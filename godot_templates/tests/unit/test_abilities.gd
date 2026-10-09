extends RefCounted
## T14.05: abilities in the saved game, the pickup, what each ability lets the player do, broken
## blocks that stay broken, the `ability:` condition and a gate that asks for an ability.

const Fixtures := preload("../lib/fixtures.gd")
const PlatformTests := preload("test_platform_actor.gd")

const TILE := 16
const FLOOR_Y := 10

func _room(floor_to: int = 30, x: float = 3.0) -> PlatformTests.Room:
	return await PlatformTests.new()._room(floor_to, x)

# ---------------------------------------------------------------- the saved game

func test_grant_and_the_save_round_trip(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	var granted: Array = []
	RpgUtil.events().ability_granted.connect(func(id: StringName) -> void: granted.append(id))
	t.ok(not state.has_ability(&"dash"))
	t.ok(state.grant(&"dash"))
	t.ok(not state.grant(&"dash"), "an ability is granted once")
	t.ok(not state.grant(&""), "an empty id is nothing")
	state.grant(&"double_jump")
	t.eq(granted, [&"dash", &"double_jump"], "Events.ability_granted for each new one")
	state.remember_broken_cell("room_03", Vector2i(4, 9))
	state.remember_broken_cell("room_03", Vector2i(4, 9))
	state.remember_broken_cell("room_03", Vector2i(5, 9))
	var saved := state.to_dict()
	t.eq(saved["abilities"], ["dash", "double_jump"])
	t.eq(saved["broken_cells"], {"room_03": [[4, 9], [5, 9]]})
	var text := JSON.stringify(saved)
	state.new_game()
	t.eq(state.abilities, [] as Array[String], "a new game starts without abilities")
	t.eq(state.broken_cells, {})
	state.from_dict(JSON.parse_string(text))
	t.ok(state.has_ability(&"dash") and state.has_ability(&"double_jump"))
	t.eq(state.broken_cells_of("room_03"), [Vector2i(4, 9), Vector2i(5, 9)] as Array[Vector2i])
	t.eq(state.broken_cells_of("room_01"), [] as Array[Vector2i])
	Fixtures.uninstall_state()

func test_a_save_without_the_keys_loads_empty_and_a_top_down_save_has_no_new_key(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	var plain := state.to_dict()
	t.ok(not plain.has("abilities") and not plain.has("broken_cells"), "a game without abilities writes neither key")
	state.grant(&"dash")
	state.remember_broken_cell("a", Vector2i(1, 1))
	# a save written by 1.0 or 1.1: it has never heard of abilities
	state.from_dict(plain)
	t.eq(state.abilities, [] as Array[String])
	t.eq(state.broken_cells, {})
	# and a damaged one is read as far as it makes sense
	var odd := plain.duplicate(true)
	odd["abilities"] = ["dash", 7, "", "dash", "wall_jump"]
	odd["broken_cells"] = {"a": [[1, 2], "x", [3]], "b": "nope", "c": [[5.0, 6.0]]}
	state.from_dict(odd)
	t.eq(state.abilities, ["dash", "wall_jump"] as Array[String])
	t.eq(state.broken_cells, {"a": [[1, 2]], "c": [[5, 6]]})
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the table and the pickup

func test_the_table_names_every_ability(t) -> void:
	t.eq(RpgAbilities.ORDER.size(), 5)
	for id in RpgAbilities.ORDER:
		t.ok(RpgAbilities.is_known(id), String(id))
		t.ok(RpgMetroidvaniaStrings.KEYS.has(RpgAbilities.name_key(id)), RpgAbilities.name_key(id))
		t.ok(RpgMetroidvaniaStrings.KEYS.has(RpgAbilities.description_key(id)))
		t.ok(RpgMetroidvaniaStrings.KEYS.has(RpgAbilities.hint_key(id)))
		t.ok(RpgAbilities.glyph_texture(id).get_width() == 12)
	t.eq(RpgAbilities.display_name(&"double_jump"), "Double Jump")
	t.eq(RpgAbilities.hint(&"high_jump"), "Your jumps go higher", "no key to press")
	var hint := RpgAbilities.hint(&"double_jump")
	t.ok(hint.begins_with("Press ") and hint.ends_with(" twice") and not hint.contains("%s"), hint)
	t.ok(RpgAbilities.toast(&"dash").begins_with("You found Dash!"), RpgAbilities.toast(&"dash"))
	t.ok(not RpgAbilities.is_known(&"fly"))
	t.eq(RpgAbilities.display_name(&"fly"), "Fly", "an ability of your own is shown by its id")

func _pickup(ability: StringName, id: String) -> RpgAbilityPickup:
	var pickup := RpgAbilityPickup.new()
	pickup.ability = ability
	pickup.entity_id = id
	var sprite := Sprite2D.new()
	sprite.name = "Sprite"
	pickup.add_child(sprite)
	return pickup

func test_a_pickup_grants_once_and_is_gone_after_a_reload(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	var tree := Fixtures.tree()
	await tree.process_frame
	var toasts: Array = []
	RpgUtil.events().notify.connect(func(text: String) -> void: toasts.append(text))
	var pickup := _pickup(&"dash", "room_02_ability_001")
	tree.root.add_child(pickup)
	t.ok((pickup.get_node("Sprite") as Sprite2D).texture != null, "a generated glyph without art")
	t.ok(pickup.collect())
	t.ok(not pickup.collect(), "once")
	t.ok(state.has_ability(&"dash"))
	t.eq(state.get_flag("room_02_ability_001", "collected"), true)
	t.eq(toasts.size(), 1)
	t.ok(str(toasts[0]).contains("Dash") and str(toasts[0]).contains("Press"), str(toasts[0]))
	await tree.process_frame
	t.ok(not is_instance_valid(pickup), "it removed itself")
	# the room is loaded again (a reload, a save): the pickup of an ability the player has is gone
	var saved := state.to_dict()
	state.new_game()
	state.from_dict(saved)
	var again := _pickup(&"dash", "room_02_ability_001")
	tree.root.add_child(again)
	await tree.process_frame
	await tree.process_frame
	t.ok(not is_instance_valid(again), "gone after the reload")
	var other := _pickup(&"wall_jump", "room_04_ability_001")
	tree.root.add_child(other)
	await tree.process_frame
	t.ok(is_instance_valid(other), "another ability is still there")
	other.interact(null)
	t.ok(state.has_ability(&"wall_jump"), "interacting takes it too")
	await tree.process_frame
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- what the abilities do

func test_a_double_jump_granted_in_the_air_works_at_once(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	state.player_stats.max_hp = 10
	state.player_stats.hp = 10
	var room: PlatformTests.Room = await _room()
	room.player.press_jump()
	await room.frames(10)
	room.player.press_jump()
	await room.frames(2)
	t.eq(room.jumps, 1, "no double jump yet")
	state.grant(&"double_jump")  # a cutscene grants it while the player is in the air
	room.player.press_jump()
	await room.frames(2)
	t.eq(room.jumps, 2, "the player reads the saved game every step")
	room.player.press_jump()
	await room.frames(2)
	t.eq(room.jumps, 2, "once per airtime")
	room.close()
	Fixtures.uninstall_state()

func test_the_dash_distance_cooldown_and_once_per_airtime(t) -> void:
	var room: PlatformTests.Room = await _room(60, 3.0)
	var start := room.player.position.x
	room.player.press_dash()
	await room.frames(20)
	t.near(room.player.position.x, start, 0.5, "no dash without the ability")
	room.player.abilities_override = ["dash"]
	var dashes: Array = []
	room.player.dashed.connect(func() -> void: dashes.append(1))
	room.player.press_dash()
	await room.frames(1)
	t.ok(room.player.is_dashing())
	t.ok(room.player.hurtbox.is_invulnerable(), "invulnerable while it lasts")
	await room.frames(16)
	var distance := room.player.position.x - start
	t.near(distance, 110.0 * 3.0 * 0.18, 7.0, "0.18 s at 3x the run speed: %.1f px" % distance)
	t.ok(not room.player.is_dashing())
	room.player.press_dash()
	await room.frames(3)
	t.eq(dashes.size(), 1, "0.6 s cooldown")
	t.ok(room.player.dash_cooldown_left() > 0.1)
	await room.frames(36)
	room.player.press_dash()
	await room.frames(2)
	t.eq(dashes.size(), 2, "ready again")
	await room.frames(50)
	# in the air: one dash until the player lands
	room.player.press_jump()
	await room.frames(6)
	room.player.press_dash()
	await room.frames(2)
	t.eq(dashes.size(), 3)
	var height := room.player.position.y
	await room.frames(6)
	t.near(room.player.position.y, height, 1.0, "a dash does not fall")
	room.player.set("_dash_cooldown", 0.0)
	await room.frames(8)
	room.player.press_dash()
	await room.frames(2)
	t.eq(dashes.size(), 3, "one per airtime, even with the cooldown over")
	room.player.set_facing(-1)
	await room.settle()
	room.player.set("_dash_cooldown", 0.0)
	var from := room.player.position.x
	room.player.press_dash()
	await room.frames(14)
	t.ok(room.player.position.x < from - 40.0, "it goes where the player looks")
	room.close()

func test_the_wall_jump_needs_its_ability(t) -> void:
	var room: PlatformTests.Room = await _room(30, 3.0)
	room.fill(PlatformTests.GROUND, Vector2i(8, FLOOR_Y - 9), Vector2i(8, FLOOR_Y - 1))  # a wall
	room.stand_at(7.0)
	await room.settle()
	room.player.move_x = 1.0
	room.player.press_jump()
	await room.frames(18)
	t.ok(room.player.is_on_wall_only(), "in the air against the wall")
	room.player.press_jump()
	await room.frames(2)
	t.eq(room.jumps, 1, "no wall jump without the ability")
	t.ok(not room.player.is_wall_sliding())
	await room.settle()
	room.player.abilities_override = ["wall_jump"]
	room.player.press_jump()
	await room.frames(30)
	t.ok(room.player.is_on_wall_only() and room.player.velocity.y > 0.0, "falling along the wall")
	t.ok(room.player.is_wall_sliding())
	await room.frames(10)
	t.ok(room.player.velocity.y <= 360.0 * 0.3 + 1.0, "the slide is 0.3 of the fastest fall: %.0f" % room.player.velocity.y)
	room.player.press_jump()
	await room.frames(2)
	t.eq(room.jumps, 3, "a jump off the wall")
	t.ok(room.player.velocity.x < 0.0 and room.player.velocity.y < 0.0, "away from it and up")
	t.eq(room.player.facing, -1)
	room.player.move_x = 0.0
	room.close()

func test_a_broken_block_stays_broken_after_a_reload(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	state.player_stats.max_hp = 10
	state.player_stats.hp = 10
	var room: PlatformTests.Room = await _room()
	room.root.set_script(load("res://addons/rpg_runtime/world/map_root.gd"))
	room.root.set("map_id", &"room_03")
	room.fill(PlatformTests.BREAKABLE, Vector2i(5, FLOOR_Y - 1), Vector2i(5, FLOOR_Y - 1))
	room.stand_at(3.6)
	await room.settle()
	state.grant(&"break_blocks")
	room.player.refresh_layers()
	t.eq(room.player.room_id(), "room_03")
	room.player.press_attack()
	await room.frames(24)
	t.eq(room.layer.get_cell_source_id(Vector2i(5, FLOOR_Y - 1)), -1, "broken")
	t.eq(state.broken_cells_of("room_03"), [Vector2i(5, FLOOR_Y - 1)] as Array[Vector2i])
	var saved := state.to_dict()
	room.close()
	# the room's scene is loaded fresh: the block is back until the saved game takes it out again
	state.new_game()
	state.from_dict(saved)
	var fresh := Node2D.new()
	var layer := TileMapLayer.new()
	layer.tile_set = PlatformTests.tileset()
	fresh.add_child(layer)
	layer.set_cell(Vector2i(5, FLOOR_Y - 1), 0, PlatformTests.BREAKABLE)
	layer.set_cell(Vector2i(6, FLOOR_Y - 1), 0, PlatformTests.BREAKABLE)
	layer.set_cell(Vector2i(5, FLOOR_Y), 0, PlatformTests.GROUND)
	t.eq(RpgAbilities.apply_broken_cells(fresh, "room_03"), 1)
	t.eq(layer.get_cell_source_id(Vector2i(5, FLOOR_Y - 1)), -1, "still broken")
	t.eq(layer.get_cell_source_id(Vector2i(6, FLOOR_Y - 1)), 0, "the block beside it stands")
	t.eq(RpgAbilities.apply_broken_cells(fresh, "room_09"), 0, "another room has none")
	fresh.free()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- conditions and gates

func test_the_ability_condition(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	t.ok(not RpgCondition.evaluate("ability:dash"))
	t.ok(RpgCondition.evaluate("not ability:dash"))
	state.grant(&"dash")
	t.ok(RpgCondition.evaluate("ability:dash"))
	t.ok(not RpgCondition.evaluate("ability:dash and ability:wall_jump"))
	t.eq(RpgCondition.problems("ability:dash"), PackedStringArray())
	t.eq(RpgCondition.problems("ability:").size(), 1, "an id is needed")
	t.ok(RpgCondition.ATOMS.has("ability:"), "the dock's completion knows it")
	Fixtures.uninstall_state()

func test_a_gate_opens_for_an_ability(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	var english := Fixtures.install_english()
	var tree := Fixtures.tree()
	await tree.process_frame
	var toasts: Array = []
	RpgUtil.events().notify.connect(func(text: String) -> void: toasts.append(text))
	var gate := RpgGate.new()
	gate.entity_id = "room_05_gate_001"
	gate.required_ability = &"wall_jump"
	tree.root.add_child(gate)
	t.ok(not gate.open and gate.get_collision_layer_value(5), "closed, and the player can try it")
	gate.interact(null)
	t.eq(toasts, ["You cannot get past this yet."])
	state.grant(&"dash")
	t.ok(not gate.open, "another ability does not open it")
	state.grant(&"wall_jump")
	t.ok(gate.open, "it opens the moment the ability is granted")
	var plain := RpgGate.new()
	tree.root.add_child(plain)
	t.ok(not plain.open and not plain.has_required_ability(), "a gate that asks for nothing is as before")
	gate.queue_free()
	plain.queue_free()
	await tree.process_frame
	Fixtures.uninstall_english(english)
	Fixtures.uninstall_state()
