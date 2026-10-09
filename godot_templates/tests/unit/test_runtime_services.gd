extends RefCounted
## Events, util, router, audio, UI helpers, strings, debug overlay, combat contract
## (T6.01, T6.08, T6.10-T6.14).

const Fixtures := preload("../lib/fixtures.gd")

func test_events_bus_declares_every_documented_signal(t) -> void:
	var events := Fixtures.install("Events", Fixtures.EVENTS)
	var expected := [
		"map_entered", "entity_state_changed", "interaction_started", "interaction_finished",
		"dialogue_started", "dialogue_finished", "dialogue_event", "item_added", "item_removed",
		"gold_changed", "player_damaged", "player_healed", "experience_gained", "level_up",
		"entity_defeated", "encounter_requested", "encounter_finished", "notify", "game_paused",
		"game_saved", "game_loaded", "chest_opened", "door_used", "attack_started",
	]
	for name in expected:
		t.ok(events.has_signal(name), name)
	Fixtures.uninstall("Events")

func test_util_emit_and_lookup(t) -> void:
	t.ok(RpgUtil.events() == null)
	RpgUtil.emit(&"notify", ["nobody listens"])  # no bus: silently nothing
	Fixtures.install("Events", Fixtures.EVENTS)
	var got := []
	RpgUtil.events().notify.connect(func(text: String) -> void: got.append(text))
	RpgUtil.notify("hello")
	RpgUtil.emit(&"gold_changed", [5])
	RpgUtil.emit(&"not_a_signal", [])
	t.eq(got, ["hello"])
	t.ok(RpgUtil.autoload(&"Events") == RpgUtil.events())
	t.ok(RpgUtil.state() == null and RpgUtil.router() == null and RpgUtil.settings() == null)
	t.ok(RpgUtil.service(&"no_such_group") == null)
	Fixtures.uninstall("Events")

func test_scene_router_starts_idle(t) -> void:
	var router := Fixtures.install("SceneRouter", "res://addons/rpg_runtime/world/scene_router.gd")
	t.ok(not router.is_busy())
	t.eq(router.stack_depth(), 0)
	t.ok(router.current_map == null)
	t.ok(router.combat == null and router.audio == null)
	Fixtures.uninstall("SceneRouter")

func test_combat_mode_contract(t) -> void:
	var mode := RpgCombatMode.new()
	t.ok(not mode.is_in_combat())
	mode.free()

func test_audio_pool_and_index(t) -> void:
	var audio := RpgAudio.new()
	Fixtures.tree().root.add_child(audio)
	if not audio.is_node_ready():
		audio._ready()
	t.eq(audio.get_child_count(), 2 + RpgAudio.SFX_POOL + 1)
	t.ok(audio.stream_for("no.such.asset") == null)
	t.eq(audio.sfx_busy_count(), 0)
	audio.play_sfx(null)
	audio.play_ui(null)
	audio.play_music(null, 0.0)  # fading out with nothing playing is fine
	t.eq(audio.current_music_id, "")
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = 22050
	var pcm := PackedByteArray()
	pcm.resize(2000)
	wav.data = pcm
	audio.play_sfx(wav)
	audio.play_music(wav, 0.0)
	Fixtures.tree().root.remove_child(audio)
	audio.free()

func test_menu_util_wires_a_wrapping_list(t) -> void:
	var box := VBoxContainer.new()
	var buttons: Array = []
	for i in 3:
		var b := Button.new()
		b.name = "B%d" % i
		box.add_child(b)
		buttons.append(b)
	RpgMenuUtil.wire_vertical(buttons)
	t.eq(String(buttons[0].focus_neighbor_bottom), "../B1")
	t.eq(String(buttons[0].focus_neighbor_top), "../B2", "wraps to the last")
	t.eq(String(buttons[2].focus_neighbor_bottom), "../B0", "wraps to the first")
	box.free()

func test_menu_util_wires_a_grid(t) -> void:
	var box := GridContainer.new()
	var buttons: Array = []
	for i in 5:  # 3 columns: a full row and a short row
		var b := Button.new()
		b.name = "G%d" % i
		box.add_child(b)
		buttons.append(b)
	RpgMenuUtil.wire_grid(buttons, 3)
	t.eq(String(buttons[0].focus_neighbor_right), "../G1")
	t.eq(String(buttons[0].focus_neighbor_left), "../G2", "wraps within the row")
	t.eq(String(buttons[3].focus_neighbor_right), "../G4")
	t.eq(String(buttons[4].focus_neighbor_right), "../G3", "the short row wraps to its own start")
	t.eq(String(buttons[0].focus_neighbor_bottom), "../G3")
	t.eq(String(buttons[3].focus_neighbor_bottom), "../G0")
	t.eq(String(buttons[2].focus_neighbor_bottom), ".", "no cell below: wraps to the top of its own column")
	RpgMenuUtil.wire_grid([], 3)
	box.free()

func test_menu_util_focusables_skip_hidden_and_disabled(t) -> void:
	var box := VBoxContainer.new()
	var ok_button := Button.new()
	var off := Button.new()
	off.disabled = true
	var hidden := Button.new()
	hidden.visible = false
	var slider := HSlider.new()
	for c in [ok_button, off, hidden, slider]:
		box.add_child(c)
	t.eq(RpgMenuUtil.focusables(box), [ok_button, slider])
	box.free()
	t.eq(RpgMenuUtil.scene_path("pause_menu"), "res://generated/scenes/ui/pause_menu.tscn")
	t.ok(RpgMenuUtil.open_submenu(Control.new(), "no_such_menu") == null)

func test_strings_table(t) -> void:
	t.ok(RpgStrings.KEYS.size() > 30)
	t.eq(RpgStrings.english("UI_NEW_GAME"), "New Game")
	t.eq(RpgStrings.english("UNKNOWN"), "UNKNOWN")
	t.eq(RpgStrings.action_label("interact"), "UI_ACTION_INTERACT")
	t.eq(RpgStrings.action_label("my_custom_action"), "my_custom_action")
	for key in RpgStrings.KEYS.keys():
		t.ok(String(key).begins_with("UI_"), key)
		t.ok(String(RpgStrings.KEYS[key]) != "", key)
	t.eq(RpgStrings.register_translations(), 0, "no generated translations in the template project")

func test_a_dropped_toast_expiring_later_is_harmless(t) -> void:
	var root := Control.new()
	var stack := VBoxContainer.new()
	stack.name = "Stack"
	root.add_child(stack)
	root.set_script(load("res://addons/rpg_runtime/ui/notification.gd"))
	Fixtures.tree().root.add_child(root)
	stack.owner = root
	stack.unique_name_in_owner = true
	var gone := Control.new()
	gone.free()
	root._expire(gone)  # a freed toast: no error, nothing to do
	root.show_toast("kept")
	root._expire(stack.get_child(0))
	t.eq(root.toast_count(), 0, "a live toast is removed")
	Fixtures.tree().root.remove_child(root)
	root.free()

func test_notification_stack_is_capped_at_three(t) -> void:
	var root := Control.new()
	var stack := VBoxContainer.new()
	stack.name = "Stack"
	root.add_child(stack)
	root.set_script(load("res://addons/rpg_runtime/ui/notification.gd"))
	Fixtures.tree().root.add_child(root)
	stack.owner = root
	stack.unique_name_in_owner = true
	for i in 5:
		root.show_toast("toast %d" % i)
	t.eq(root.toast_count(), 3)
	t.eq(((stack.get_child(0) as Container).get_child(0) as Label).text, "toast 2", "the oldest were dropped")
	Fixtures.tree().root.remove_child(root)
	root.free()

func test_debug_overlay_commands(t) -> void:
	var state := Fixtures.install_state({&"potion": Fixtures.item(&"potion")})
	state.new_game()
	var overlay := RpgDebugOverlay.new()
	t.eq(overlay.run_command(""), "")
	t.ok(overlay.run_command("help").contains("tp <spawn_id>"))
	t.eq(overlay.run_command("gold 77"), "gold = 77")
	t.eq(state.gold, 77)
	t.ok(overlay.run_command("gold").begins_with("usage"))
	t.eq(overlay.run_command("give potion 3"), "gave 3 x potion")
	t.eq(state.inventory.count(&"potion"), 3)
	t.eq(overlay.run_command("flag npc.talked=true"), "ok")
	t.eq(state.get_flag("npc", "talked"), true)
	t.ok(overlay.run_command("flag broken").begins_with("usage"))
	state.player_stats.hp = 1
	overlay.run_command("heal")
	t.eq(state.player_stats.hp, state.player_stats.max_hp)
	t.ok(overlay.run_command("tp somewhere").begins_with("usage"), "needs a map")
	t.eq(overlay.run_command("encounter"), "no combat mode in this game")
	t.eq(overlay.run_command("dance"), "unknown command (help)")
	overlay.free()
	Fixtures.uninstall_state()

# ---------------------------------------------------------------- sound slots (T11.20)

func _bank_with(paths: Dictionary) -> RpgSoundBank:
	var bank := RpgSoundBank.new()
	bank.set_paths(paths)
	return bank

func test_sound_bank_unset_slots_are_silent(t) -> void:
	var bank := _bank_with({})
	t.ok(bank.stream(&"sfx_hit") == null, "an unset slot has no stream")
	t.ok(not bank.has_slot(&"sfx_hit"))
	var missing := _bank_with({"sfx_hit": "res://does_not_exist.wav"})
	t.ok(missing.has_slot(&"sfx_hit"))
	t.ok(missing.stream(&"sfx_hit") == null, "a file that does not load is silent, not an error")

func test_audio_play_on_an_unset_slot_does_nothing(t) -> void:
	var audio := RpgAudio.new()
	audio.play(&"sfx_hit")
	audio.play_ui_slot(&"sfx_ui_move")
	audio.play_music_slot(&"music_map")
	t.eq(audio.sfx_busy_count(), 0)
	audio.free()

class FakeBus extends Node:
	signal item_added(item_id: StringName, qty: int)
	signal player_damaged(amount: int)
	signal level_up(actor_id: StringName, new_level: int)
	signal game_saved(slot: int)
	signal chest_opened(entity_id: String)
	signal door_used(entity_id: String)
	signal attack_started(actor: Node)

class RecordingAudio extends RpgAudio:
	var played: Array = []
	func play(slot: StringName, _volume_db: float = 0.0, _pitch_scale: float = 1.0) -> void:
		played.append(slot)

func test_events_play_their_slots(t) -> void:
	var bus := FakeBus.new()
	var audio := RecordingAudio.new()
	audio.connect_events(bus)
	bus.player_damaged.emit(3)
	bus.level_up.emit(&"hero", 2)
	bus.game_saved.emit(1)
	bus.chest_opened.emit("c1")
	bus.door_used.emit("d1")
	bus.attack_started.emit(null)
	t.eq(audio.played, [&"sfx_hit", &"sfx_levelup", &"sfx_save", &"sfx_chest", &"sfx_door", &"sfx_attack"])
	bus.free()
	audio.free()

func test_every_event_slot_is_a_sound_slot_name(t) -> void:
	for signal_name in RpgAudio.EVENT_SLOTS.keys():
		t.ok(str(RpgAudio.EVENT_SLOTS[signal_name]).begins_with("sfx_"), str(signal_name))

# ---------------------------------------------------------------- game over (T11.21)

func test_defeat_policy_without_a_save_manager(t) -> void:
	t.eq(RpgDefeatPolicy.latest_save_slot(), -1, "no SaveManager, no slot")
	t.ok(RpgDefeatPolicy.Choice.CONTINUE != RpgDefeatPolicy.Choice.RETRY)
	RpgDefeatPolicy.force_screen = true
	t.ok(not RpgDefeatPolicy.is_automatic(), "a test can force the screen")
	RpgDefeatPolicy.force_screen = false

func test_game_over_strings_exist_with_defaults(t) -> void:
	for key in ["UI_GAME_OVER_TITLE", "UI_GAME_OVER_CONTINUE", "UI_GAME_OVER_RETRY", "UI_GAME_OVER_QUIT"]:
		t.ok(RpgStrings.KEYS.has(key), key)
		t.ok(RpgStrings.english(key) != key, key)

func test_game_over_screen_emits_one_choice(t) -> void:
	var screen := RpgGameOver.new()
	var seen := []
	screen.chosen.connect(func(choice: int) -> void: seen.append(choice))
	screen._choose(RpgDefeatPolicy.Choice.RETRY)
	screen._choose(RpgDefeatPolicy.Choice.QUIT)
	t.eq(seen, [RpgDefeatPolicy.Choice.RETRY], "a second press is ignored")
	screen.free()

# ---------------------------------------------------------------- small polish (T11.24)

func test_prompt_text_picks_the_device(t) -> void:
	var key := InputEventKey.new()
	key.physical_keycode = KEY_E
	var pad := InputEventJoypadButton.new()
	pad.button_index = JOY_BUTTON_A
	t.eq(RpgInteraction.key_text([key, pad], false), "E")
	t.ok(RpgInteraction.key_text([key, pad], true) != "E", "a controller shows its own button")
	t.eq(RpgInteraction.key_text([key], true), "E", "no pad binding: the key")
	t.eq(RpgInteraction.key_text([], false), "?")

func test_pause_menu_progress_text(t) -> void:
	t.eq(RpgPauseMenu.progress_text("res://game/maps/starter_map.tscn", 750.0), "Starter Map  ·  12 min")
	t.eq(RpgPauseMenu.progress_text("", 59.0), "0 min")

func test_screen_feedback_respects_the_setting(t) -> void:
	t.ok(RpgScreenFeedback.enabled(), "on without a settings autoload")
	var settings := Fixtures.install("RpgSettings", Fixtures.SETTINGS)
	settings.screen_shake = false
	t.ok(not RpgScreenFeedback.enabled())
	RpgScreenFeedback.shake(null)  # no camera: nothing happens
	settings.screen_shake = true
	t.ok(RpgScreenFeedback.enabled())
	Fixtures.uninstall("RpgSettings")

# ---------------------------------------------------------------- custom slots and surfaces (T13.16)

## A layer with one tile at (2, 1) whose custom data name its asset and, maybe, its footstep.
func _ground_layer(asset_id: String, footstep: String = "") -> TileMapLayer:
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	for layer_name: String in ["asset_id", "footstep"]:
		ts.add_custom_data_layer()
		var index := ts.get_custom_data_layers_count() - 1
		ts.set_custom_data_layer_name(index, layer_name)
		ts.set_custom_data_layer_type(index, TYPE_STRING)
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(Image.create(16, 16, false, Image.FORMAT_RGBA8))
	source.texture_region_size = Vector2i(16, 16)
	ts.add_source(source, 0)
	source.create_tile(Vector2i.ZERO)
	var data := source.get_tile_data(Vector2i.ZERO, 0)
	data.set_custom_data("asset_id", asset_id)
	data.set_custom_data("footstep", footstep)
	var layer := TileMapLayer.new()
	layer.tile_set = ts
	layer.set_cell(Vector2i(2, 1), 0, Vector2i.ZERO)
	return layer

func test_the_step_on_stone_ground_is_the_stone_step(t) -> void:
	var bank := _bank_with({"sfx_step": "res://step.wav", "sfx_step_stone": "res://stone.wav", "sfx_magic": "res://magic.wav"})
	bank.set_surfaces({"pack.tiles.floor": "stone", "pack.tiles.lawn": "grass"})
	t.ok(bank.has_slot(&"sfx_magic"), "a custom slot is a slot like the others")
	t.ok(bank.has_step_surfaces())
	t.eq(bank.surface_of("pack.tiles.floor"), "stone")
	t.eq(bank.surface_of("pack.tiles.unknown"), "")
	t.eq(bank.step_slot("stone"), &"sfx_step_stone")
	t.eq(bank.step_slot("grass"), &"sfx_step", "no grass step in the bank: the plain one")
	t.eq(bank.step_slot(""), &"sfx_step")
	t.ok(not _bank_with({"sfx_step": "res://step.wav"}).has_step_surfaces())
	# the actor's cell: the asset under its feet says what the ground is
	var floor_layer := _ground_layer("pack.tiles.floor")
	var layers: Array[TileMapLayer] = [floor_layer]
	var on_tile := Vector2(2 * 16 + 8, 1 * 16 + 8)
	t.eq(RpgMovement.surface_at(layers, on_tile, bank), "stone")
	t.eq(bank.step_slot(RpgMovement.surface_at(layers, on_tile, bank)), &"sfx_step_stone")
	t.eq(RpgMovement.surface_at(layers, Vector2(200, 200), bank), "", "no tile there")
	# a layer above wins, and a tile's own `footstep` wins over its asset's surface
	var lawn := _ground_layer("pack.tiles.lawn")
	layers.append(lawn)
	t.eq(RpgMovement.surface_at(layers, on_tile, bank), "grass")
	var planks := _ground_layer("pack.tiles.floor", "wood")
	layers.append(planks)
	t.eq(RpgMovement.surface_at(layers, on_tile, bank), "wood")
	# an asset without a surface lets the layer below speak
	var plain := _ground_layer("pack.tiles.unknown")
	var under: Array[TileMapLayer] = [floor_layer, plain]
	t.eq(RpgMovement.surface_at(under, on_tile, bank), "stone")
	for layer: TileMapLayer in [floor_layer, lawn, planks, plain]:
		layer.free()

func test_the_dialogue_event_play_sound_names_a_slot(t) -> void:
	Fixtures.install_state()
	t.ok(RpgDialogueRunner.EVENTS.has("play_sound"))
	t.eq(RpgDialogueRunner.event_problem("play_sound:sfx_magic"), "")
	t.ok(RpgDialogueRunner.event_problem("play_sound") != "", "it needs a slot")
	t.ok(RpgDialogueRunner.execute_event("play_sound:sfx_magic"), "without an audio service it is silent, not an error")
	t.ok(not RpgDialogueRunner.execute_event("play_sound"))
	Fixtures.uninstall_state()
