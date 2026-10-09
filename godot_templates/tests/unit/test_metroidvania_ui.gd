extends RefCounted
## T14.08: the metroidvania's HUD, the room map and its fog in the saved game, and save stations.

const Fixtures := preload("../lib/fixtures.gd")
const HudRecipe := preload("res://builder/recipes/metroidvania/hud_recipe.gd")
const Objects := preload("res://builder/recipes/metroidvania/objects_recipe.gd")
const BuildContext := preload("res://builder/lib/build_context.gd")
const CatalogReader := preload("res://builder/lib/catalog_reader.gd")

const CASES := "res://tests/fixtures/room_plan_cases.json"

func _world(case_name: String = "default") -> Dictionary:
	var cases: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CASES))
	return cases[case_name]

func _ctx() -> BuildContext:
	var ctx := BuildContext.new("res://builder")
	ctx.catalog = CatalogReader.new({"assets": [], "tilesets": [], "objects": []})
	ctx.config = {"archetype": "metroidvania"}
	return ctx

# ---------------------------------------------------------------- the HUD

func test_health_is_shown_as_pips_of_four(t) -> void:
	t.eq(RpgMetroidvaniaHud.pip_count(20), 5)
	t.eq(RpgMetroidvaniaHud.pip_count(18), 5, "a part of a pip is a pip")
	t.eq(RpgMetroidvaniaHud.pip_count(4), 1)
	t.eq(RpgMetroidvaniaHud.pip_count(0), 0)
	t.near(RpgMetroidvaniaHud.pip_fill(20, 4), 1.0)
	t.near(RpgMetroidvaniaHud.pip_fill(18, 4), 0.5, 0.001, "two of the last four")
	t.near(RpgMetroidvaniaHud.pip_fill(18, 3), 1.0)
	t.near(RpgMetroidvaniaHud.pip_fill(3, 0), 0.75)
	t.near(RpgMetroidvaniaHud.pip_fill(3, 1), 0.0)

func test_the_hud_reflects_health_abilities_gold_and_the_weapon(t) -> void:
	var sword := Fixtures.item(&"sword")
	sword.category = RpgItemDefinition.Category.WEAPON
	sword.display_name = "Old Sword"
	var state := Fixtures.install_state({&"sword": sword}) as RpgGameState
	var english := Fixtures.install_english()
	var tree := Fixtures.tree()
	await tree.process_frame
	state.player_stats.max_hp = 20
	state.player_stats.hp = 20
	var hud := HudRecipe.build_hud(_ctx(), PackedStringArray(["double_jump", "dash"])) as RpgMetroidvaniaHud
	t.eq(hud.abilities, PackedStringArray(["double_jump", "dash"]))
	t.eq(hud.icons.size(), 2, "an icon slot per ability (empty: a glyph is drawn)")
	tree.root.add_child(hud)
	t.eq(hud.layer, 20)
	t.eq(hud.ability_states(), [["double_jump", false], ["dash", false]])
	var gold := hud.get_node("Canvas/Gold") as Label
	var weapon := hud.get_node("Canvas/Weapon") as Label
	t.eq(gold.text, "Gold: 0")
	t.ok(not weapon.visible, "no weapon worn")
	state.gold = 35
	t.eq(gold.text, "Gold: 35", "the gold follows Events.gold_changed")
	state.grant(&"dash")
	t.eq(hud.ability_states(), [["double_jump", false], ["dash", true]], "an ability lights up when it is granted")
	state.inventory.add(&"sword", 1)
	t.ok(state.equip(state.player_actor_id, &"sword"))
	t.eq(weapon.text, "Old Sword")
	t.ok(weapon.visible)
	t.eq(RpgMetroidvaniaHud.weapon_text(null), "")
	t.ok(not hud.visible, "hidden while no map is shown (the title screen)")
	tree.root.remove_child(hud)
	hud.free()
	Fixtures.uninstall_english(english)
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the room fog

func test_the_room_fog_survives_a_save_and_a_top_down_save_is_unchanged(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	var plain := state.to_dict()
	t.ok(not plain.has("room_fog"), "a game that never entered a room writes no key")
	t.ok(state.visit_room("room_01"))
	t.ok(not state.visit_room("room_01"), "a room is new once")
	t.ok(not state.visit_room(""))
	state.visit_room("room_03")
	t.ok(state.room_visited("room_03") and not state.room_visited("room_02"))
	state.fog_mark("game__maps__starter_map", Vector2i(8, 8), Vector2i(2, 2), 1)
	var saved := state.to_dict()
	t.eq(saved["room_fog"], {"room_01": true, "room_03": true})
	t.ok(saved.has("map_fog"), "the top-down fog keeps its own key")
	var text := JSON.stringify(saved)
	state.new_game()
	t.eq(state.room_fog, {})
	state.from_dict(JSON.parse_string(text))
	t.eq(state.room_fog, {"room_01": true, "room_03": true})
	t.ok(state.fog_seen("game__maps__starter_map", Vector2i(2, 2)), "and its meaning")
	# a save of 1.0 or 1.1 has no such key; a damaged one is read as far as it makes sense
	state.from_dict(plain)
	t.eq(state.room_fog, {})
	var odd := plain.duplicate(true)
	odd["room_fog"] = {"room_02": true, "room_04": false, "": true, "room_05": 1}
	state.from_dict(odd)
	t.eq(state.room_fog, {"room_02": true, "room_05": true})
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- the room map

func test_the_room_map_shows_the_rooms_visited_on_the_worlds_grid(t) -> void:
	var world := _world()
	var rooms := RpgMinimapData.room_list(world)
	t.eq(rooms.size(), 6)
	t.eq(RpgMinimapData.room_list({}).size(), 0, "a world of areas has no rooms")
	var boxes := RpgMinimapData.room_boxes(world)
	t.eq(boxes.size(), 6)
	var first: Rect2i = boxes["room_01"]
	var second: Rect2i = boxes["room_02"]
	t.eq(first.size, RpgMinimapData.ROOM_BOX)
	t.eq(second.position, first.position + Vector2i(16, 0), "the room to the east, one box and a gap further")
	var pickup_room := ""
	for room in rooms:
		if room.has("pickup"):
			pickup_room = str(room["id"])
	var picture := RpgMinimapData.room_map(world, {"room_01": true, "room_02": true, pickup_room: true}, "room_02", [])
	t.eq(picture.get_pixelv(first.position).to_html(), RpgMinimapData.ROOM_EDGE.to_html(), "a visited room has an edge")
	t.eq(picture.get_pixelv(first.position + Vector2i(1, 1)).to_html(), RpgMinimapData.ROOM_SEEN.to_html(), "and is filled")
	t.eq(picture.get_pixelv(second.position).to_html(), RpgMinimapData.ROOM_HERE.to_html(), "the current room is outlined in white")
	t.eq(picture.get_pixelv(first.position + Vector2i(3, 5)).to_html(), RpgMinimapData.ROOM_STATION.to_html(), "the save station of the start room")
	t.eq(picture.get_pixelv(Vector2i(first.end.x, first.position.y + 4)).to_html(), RpgMinimapData.ROOM_EDGE.to_html(), "a notch where the exit east is")
	t.eq(picture.get_pixelv(Vector2i(first.position.x - 1, first.position.y + 4)).to_html(), RpgMinimapData.ROOM_BACK.to_html(), "none where there is no exit")
	var third: Rect2i = boxes["room_03"]
	if pickup_room != "room_03":
		t.eq(picture.get_pixelv(third.position + Vector2i(2, 2)).to_html(), RpgMinimapData.ROOM_BACK.to_html(), "a room not visited yet is not drawn")
	var with_pickup: Rect2i = boxes[pickup_room]
	t.eq(picture.get_pixelv(with_pickup.position + Vector2i(9, 5)).to_html(), RpgMinimapData.ROOM_PICKUP.to_html(), "an ability that still lies there")
	var taken := RpgMinimapData.room_map(world, {pickup_room: true}, pickup_room, ["dash"])
	t.eq(taken.get_pixelv(with_pickup.position + Vector2i(9, 5)).to_html(), RpgMinimapData.ROOM_SEEN.to_html(), "no mark once the player has it")
	# the world map: the same picture, four times as large
	var state := Fixtures.install_state() as RpgGameState
	state.visit_room("room_01")
	state.current_map = "res://game/maps/rooms/room_01.tscn"
	var large := RpgWorldMapMenu.room_overview(world, state)
	t.eq(large.get_size(), picture.get_size() * 4)
	t.eq(large.get_pixelv(first.position * 4).to_html(), RpgMinimapData.ROOM_HERE.to_html())
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- save stations

func test_a_station_restores_health_brings_enemies_back_and_is_the_place_to_return_to(t) -> void:
	var state := Fixtures.install_state() as RpgGameState
	var english := Fixtures.install_english()
	var tree := Fixtures.tree()
	await tree.process_frame
	state.player_stats.max_hp = 20
	state.player_stats.hp = 3
	state.set_flag("room_03_enemy_001", "defeated", true)
	state.set_flag("room_04_enemy_002", "defeated", true)
	state.set_flag("room_02_guardian", "defeated", true)
	state.set_flag("room_03_chest_001", "opened", true)
	t.eq(RpgSaveStation.respawn_point(state), {}, "no station used yet")
	t.eq(RpgSaveStation.respawn_point(null), {})
	var room := Node2D.new()
	room.set_script(load("res://addons/rpg_runtime/world/map_root.gd"))
	room.set("map_id", &"room_01")
	room.scene_file_path = "res://game/maps/rooms/room_01.tscn"
	var station := Objects.build_station(_ctx(), 16) as RpgSaveStation
	t.ok(station != null and station.get_collision_layer_value(5), "an interactable")
	t.ok(station.get_node_or_null("Sprite") != null, "a drawn bench without art")
	station.position = Vector2(140, 320)
	room.add_child(station)
	tree.root.add_child(room)
	var rests: Array = []
	station.rested.connect(func() -> void: rests.append(1))
	t.eq(station.rest(), 2, "two ordinary enemies come back")
	t.eq(rests.size(), 1)
	t.eq(state.player_stats.hp, 20, "health is restored")
	t.eq(state.get_flag("room_03_enemy_001", "defeated"), false)
	t.eq(state.get_flag("room_04_enemy_002", "defeated"), false)
	t.eq(state.get_flag("room_02_guardian", "defeated"), true, "the guardian stays defeated")
	t.eq(state.get_flag("room_03_chest_001", "opened"), true, "an opened chest stays open")
	var point := RpgSaveStation.respawn_point(state)
	t.eq(point["position"], Vector2(140, 320))
	t.eq(point["map"], room.scene_file_path)
	# the place to return to is part of the saved game
	var saved := state.to_dict()
	state.new_game()
	state.from_dict(saved)
	t.eq(RpgSaveStation.respawn_point(state).get("position"), Vector2(140, 320))
	tree.root.remove_child(room)
	room.free()
	Fixtures.uninstall_english(english)
	Fixtures.uninstall_state()

func test_the_mode_says_how_the_archetype_saves_and_continues(t) -> void:
	var mode := RpgMetroidvaniaMode.new()
	t.ok(mode.save_at_stations, "the pause menu's Save is off")
	t.ok(mode.autosave_on_every_map, "every room change saves")
	t.ok(not mode.is_in_combat())
	t.ok(mode.has_method(&"respawn_after_defeat"), "Continue after a defeat is the mode's")
	mode.free()
	t.ok(not RpgDefeatPolicy.can_continue(), "without a save and without such a mode there is nothing to continue")
	var other := RpgCombatMode.new()
	t.eq(other.get("save_at_stations"), null, "the other archetypes save as before")
	other.free()
