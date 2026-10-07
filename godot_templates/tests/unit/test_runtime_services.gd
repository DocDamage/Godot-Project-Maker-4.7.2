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
		"game_saved", "game_loaded",
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
