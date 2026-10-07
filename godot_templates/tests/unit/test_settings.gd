extends RefCounted
## RpgSettings: values, persistence, input remapping (T6.10).

const Fixtures := preload("../lib/fixtures.gd")
const ACTION := "test_settings_action"

func _new(path: String) -> Node:
	var s := Fixtures.install("RpgSettings", Fixtures.SETTINGS)
	s.path = path
	return s

func _key(code: int) -> InputEventKey:
	var k := InputEventKey.new()
	k.physical_keycode = code as Key
	return k

func _tmp() -> String:
	return "user://test_settings_%d.cfg" % Time.get_ticks_usec()

func _action(events: Array) -> void:
	if InputMap.has_action(ACTION):
		InputMap.erase_action(ACTION)
	InputMap.add_action(ACTION)
	for ev in events:
		InputMap.action_add_event(ACTION, ev)

func test_defaults_and_text_speed(t) -> void:
	var s := _new(_tmp())
	t.near(s.volumes["master"], 0.8)
	t.eq(s.text_speed, "normal")
	t.near(s.text_cps(), 40.0)
	s.set_text_speed("slow")
	t.near(s.text_cps(), 20.0)
	s.set_text_speed("fast")
	t.near(s.text_cps(), 80.0)
	s.set_text_speed("instant")
	t.near(s.text_cps(), 0.0)
	s.set_text_speed("ludicrous")
	t.eq(s.text_speed, "instant", "unknown speeds are ignored")
	Fixtures.uninstall("RpgSettings")

func test_volumes_are_clamped_and_unknown_buses_ignored(t) -> void:
	var s := _new(_tmp())
	s.set_volume("music", 3.0)
	t.near(s.volumes["music"], 1.0)
	s.set_volume("sfx", -1.0)
	t.near(s.volumes["sfx"], 0.0)
	s.set_volume("nothing", 0.5)
	t.ok(not s.volumes.has("nothing"))
	s.set_ui_scale(1.25)
	t.near(s.ui_scale, 1.25)
	s.set_ui_scale(7.0)
	t.near(s.ui_scale, 1.0)
	Fixtures.uninstall("RpgSettings")

func test_values_persist_in_the_config_file(t) -> void:
	var path := _tmp()
	var s := _new(path)
	s.set_volume("master", 0.3)
	s.set_text_speed("fast")
	s.set_ui_scale(1.5)
	s.fullscreen = true
	t.ok(s.save_settings())
	var again := _new(path)
	again.load_settings()
	t.near(again.volumes["master"], 0.3)
	t.eq(again.text_speed, "fast")
	t.near(again.ui_scale, 1.5)
	t.eq(again.fullscreen, true)
	DirAccess.remove_absolute(path)
	Fixtures.uninstall("RpgSettings")

func test_event_serialization_round_trip(t) -> void:
	var key := _key(KEY_E)
	var d: Dictionary = RpgSettings_serialize(key)
	t.eq(d, {"type": "key", "physical": KEY_E})
	var back := deserialize(d)
	t.ok(back is InputEventKey and (back as InputEventKey).physical_keycode == KEY_E)
	var jb := InputEventJoypadButton.new()
	jb.button_index = JOY_BUTTON_X
	t.eq(RpgSettings_serialize(jb), {"type": "joy_button", "index": JOY_BUTTON_X})
	var jb2 := deserialize({"type": "joy_button", "index": 3}) as InputEventJoypadButton
	t.eq(jb2.button_index, 3 as JoyButton)
	var mb := deserialize({"type": "mouse_button", "index": 2}) as InputEventMouseButton
	t.eq(mb.button_index, 2 as MouseButton)
	var jm := deserialize({"type": "joy_axis", "axis": 1, "value": -1.0}) as InputEventJoypadMotion
	t.eq(jm.axis, 1 as JoyAxis)
	t.ok(deserialize({"type": "banana"}) == null)
	t.ok(deserialize("nonsense") == null)
	t.eq(RpgSettings_serialize(InputEventMouseMotion.new()), {})

# The settings script has no class_name (it is an autoload); reach its static helpers by script.
func RpgSettings_serialize(ev: InputEvent) -> Dictionary:
	return (load(Fixtures.SETTINGS) as GDScript).serialize_event(ev)

func deserialize(d: Variant) -> InputEvent:
	return (load(Fixtures.SETTINGS) as GDScript).deserialize_event(d)

func test_rebind_replaces_the_old_event_and_is_stored(t) -> void:
	_action([_key(KEY_A)])
	var path := _tmp()
	var s := _new(path)
	s.load_settings()  # captures the defaults, including the test action
	t.ok(s.remappable_actions().has(ACTION))
	t.ok(s.rebind(ACTION, _key(KEY_A), _key(KEY_B)))
	var events := InputMap.action_get_events(ACTION)
	t.eq(events.size(), 1)
	t.eq((events[0] as InputEventKey).physical_keycode, KEY_B as Key)
	# A fresh settings object reads the stored binding and it replaces the default.
	_action([_key(KEY_A)])
	var again := _new(path)
	again.load_settings()
	var loaded := InputMap.action_get_events(ACTION)
	t.eq(loaded.size(), 1)
	t.eq((loaded[0] as InputEventKey).physical_keycode, KEY_B as Key)
	again.reset_bindings()
	t.eq((InputMap.action_get_events(ACTION)[0] as InputEventKey).physical_keycode, KEY_A as Key)
	DirAccess.remove_absolute(path)
	InputMap.erase_action(ACTION)
	Fixtures.uninstall("RpgSettings")

func test_rebind_rejects_unknown_actions_and_null_events(t) -> void:
	var s := _new(_tmp())
	t.ok(not s.rebind("no_such_action", null, _key(KEY_Q)))
	_action([_key(KEY_A)])
	t.ok(not s.rebind(ACTION, null, null))
	InputMap.erase_action(ACTION)
	Fixtures.uninstall("RpgSettings")

func test_event_text_is_not_empty(t) -> void:
	var s := _new(_tmp())
	t.ok(s.event_text(_key(KEY_E)) != "")
	var jb := InputEventJoypadButton.new()
	t.ok(s.event_text(jb) != "")
	Fixtures.uninstall("RpgSettings")
