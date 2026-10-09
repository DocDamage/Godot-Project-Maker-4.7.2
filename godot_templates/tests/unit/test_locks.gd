extends RefCounted
## Keys, switches and gates (T12.70): a gate opened by its key (once, remembered), by a condition
## (switches, variables), closing again; plates and levers; locked map doors; the dock's plan; the
## content check.

const Fixtures := preload("../lib/fixtures.gd")
const Placement := preload("res://addons/rpg_project_tools/dock/placement.gd")
const ContentChecks := preload("res://addons/rpg_project_tools/tools/content_checks.gd")
const Maps := preload("res://tests/lib/map_fixtures.gd")

func _key() -> RpgItemDefinition:
	var key := Fixtures.item(&"cellar_key", 1)
	key.category = RpgItemDefinition.Category.KEY
	key.display_name = "Cellar key"
	return key

var _english: Translation = null

## The game state with the key, and the English strings (the lock notes format their text).
## Pair it with _end().
func _state() -> Node:
	if _english == null:
		_english = Fixtures.install_english()
	var state := Fixtures.install_state({&"cellar_key": _key()})
	state.new_game()
	state.inventory.slots.clear()
	return state

func _end() -> void:
	Fixtures.uninstall_state()
	if _english != null:
		Fixtures.uninstall_english(_english)
		_english = null

func _gate(id: String, key: StringName = &"", open_when: String = "") -> RpgGate:
	var gate := RpgGate.new()
	gate.entity_id = id
	gate.key_item = key
	gate.open_when = open_when
	gate._ready()
	return gate

func _shape_disabled(gate: Node) -> bool:
	var shape := gate.get_node("Shape") as CollisionShape2D
	return shape.disabled

func test_a_gate_opens_for_good_with_its_key(t) -> void:
	var state := _state()
	var notes: Array = []
	RpgUtil.events().notify.connect(func(text: String) -> void: notes.append(text))
	var gate := _gate("cellar_gate_001", &"cellar_key")
	t.ok(not gate.open and gate.visible)
	t.ok(gate.get_collision_layer_value(1) and gate.get_collision_layer_value(5), "it blocks, and the interaction finds it")
	gate.interact()
	t.ok(not gate.open, "no key, no entry")
	t.eq(notes, ["Locked. It needs: Cellar key"], "the note names the key")
	state.inventory.add(&"cellar_key")
	gate.interact()
	t.ok(gate.open)
	t.ok(not gate.visible)
	t.eq(state.inventory.count(&"cellar_key"), 0, "the key is used up")
	t.eq(state.get_flag("cellar_gate_001", "unlocked"), true)
	var again := _gate("cellar_gate_001", &"cellar_key")
	t.ok(again.open, "a gate built again (a map load) remembers it was unlocked")
	gate.free()
	again.free()
	_end()

func test_a_gate_follows_its_condition_both_ways(t) -> void:
	var state := _state()
	var gate := _gate("hall_gate_001", &"", "flag:hall_switch_001.on and var:torches>=2")
	var events: Array = []
	gate.changed.connect(func(open: bool) -> void: events.append(open))
	t.ok(not gate.open)
	state.set_flag("hall_switch_001", "on", true)
	t.ok(not gate.open, "both parts must hold")
	state.set_var("torches", 2)
	t.ok(gate.open, "it opens as soon as the condition holds")
	state.set_flag("hall_switch_001", "on", false)
	t.ok(not gate.open, "and closes when it no longer does")
	t.eq(events, [true, false])
	gate.interact()
	t.ok(not gate.open, "a gate without a key does not open by hand")
	gate.free()
	_end()

func test_plates_and_levers_set_their_flag(t) -> void:
	var state := _state()
	var plate := RpgSwitch.new()
	plate.entity_id = "hall_switch_001"
	plate._ready()
	t.ok(plate.get_collision_mask_value(2) and not plate.monitorable, "a plate watches the player")
	var player := Node2D.new()
	player.add_to_group("player")
	plate._on_body_entered(player)
	t.ok(plate.is_on())
	plate._on_body_exited(player)
	t.ok(plate.is_on(), "a plate stays down")
	plate.hold = true
	plate._on_body_exited(player)
	t.ok(not plate.is_on(), "unless it is held down")
	var lever := RpgSwitch.new()
	lever.entity_id = "hall_switch_002"
	lever.kind = RpgSwitch.Kind.LEVER
	lever._ready()
	t.ok(lever.get_collision_layer_value(5), "a lever is an interactable")
	lever.interact()
	t.eq(state.get_flag("hall_switch_002", "on"), true)
	lever.interact()
	t.eq(state.get_flag("hall_switch_002", "on"), false, "a lever flips")
	lever.once = true
	lever.interact()
	lever.interact()
	t.ok(lever.is_on(), "a once-lever stays on")
	for node: Node in [plate, lever, player]:
		node.free()
	_end()

func test_a_locked_door_needs_its_key_once(t) -> void:
	var state := _state()
	var door := RpgDoor.new()
	door.target_map = "res://does/not/matter.tscn"
	door.key_item = &"cellar_key"
	door.entity_id = "town_door_001"
	t.ok(door.is_locked())
	t.ok(not door.try_unlock())
	state.inventory.add(&"cellar_key")
	t.ok(door.try_unlock())
	t.ok(not door.is_locked())
	t.eq(state.inventory.count(&"cellar_key"), 0)
	t.ok(door.try_unlock(), "an unlocked door stays unlocked")
	var plain := RpgDoor.new()
	t.ok(not plain.is_locked() and plain.try_unlock(), "a door without a key item is never locked")
	door.free()
	plain.free()
	_end()

func test_the_dock_plans_gates_and_switches_that_open_them(t) -> void:
	var root := Maps.map("crypt")
	var gate_plan := Placement.plan_lock(root, Vector2(40, 40), 16, "gate")
	t.eq(gate_plan["entity_id"], "crypt_gate_001")
	t.eq(gate_plan["parent"], Maps.entities_of(root))
	t.eq(gate_plan["position"], Vector2(48, 48))
	var gate := Placement.build_lock(gate_plan)
	t.ok(gate is RpgGate)
	Maps.entities_of(root).add_child(gate)
	var lever_plan := Placement.plan_lock(root, Vector2(80, 40), 16, "lever", gate)
	t.eq(lever_plan["entity_id"], "crypt_switch_001")
	t.eq(lever_plan["gate"], gate, "a switch added with a gate selected opens it")
	var lever := Placement.build_lock(lever_plan)
	t.ok(lever is RpgSwitch and (lever as RpgSwitch).kind == RpgSwitch.Kind.LEVER)
	t.eq(Placement.switch_condition("crypt_switch_001"), "flag:crypt_switch_001.on")
	t.ok(Placement.plan_lock(root, Vector2.ZERO, 16, "plate", lever)["gate"] == null, "only a gate is linked")
	lever.free()
	root.free()

func test_the_lock_check_val_025(t) -> void:
	var dir := "user://test_locks"
	Maps.remove_tree(dir)
	DirAccess.make_dir_recursive_absolute(dir + "/maps")
	DirAccess.make_dir_recursive_absolute(dir + "/items")
	ResourceSaver.save(_key(), dir + "/items/cellar_key.tres")
	var a := Maps.map("a")
	var specs: Array = [
		["Good", RpgGate.new(), {"entity_id": "a_gate_001", "key_item": &"cellar_key"}],
		["Ghost", RpgGate.new(), {"entity_id": "a_gate_002", "key_item": &"ghost_key"}],
		["Never", RpgGate.new(), {"entity_id": "a_gate_003"}],
		["NoId", RpgSwitch.new(), {}],
		["Door", RpgDoor.new(), {"key_item": &"cellar_key"}],
	]
	for spec: Array in specs:
		var node: Node = spec[1]
		node.name = spec[0]
		var props: Dictionary = spec[2]
		for key: String in props:
			node.set(key, props[key])
		a.add_child(node)
	Maps.save(a, dir + "/maps/a.tscn")
	var found: Array = []
	for f in ContentChecks.run({"maps": dir + "/maps", "items": dir + "/items", "dialogue": dir + "/none", "resources": [dir + "/none"], "placeholders": dir + "/none/"}):
		if f["code"] == "VAL-025":
			found.append("%s: %s" % [f["node"], f["detail"]["problem"]])
	found.sort()
	t.eq(found.size(), 4, str(found))
	t.ok(found[0].begins_with("Door:") and found[0].contains("no entity_id"))
	t.ok(found[1].begins_with("Ghost:") and found[1].contains("'ghost_key'"))
	t.ok(found[2].begins_with("Never:") and found[2].contains("never opens"))
	t.ok(found[3].begins_with("NoId:") and found[3].contains("no entity_id"))
	Maps.remove_tree(dir)
