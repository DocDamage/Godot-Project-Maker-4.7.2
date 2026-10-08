extends RefCounted
## Equipment (T12.45): the slots, the modifier sums, equip / unequip swaps, the save key, combat
## reading stats through get_stat, and the picker's preview.

const Fixtures := preload("../lib/fixtures.gd")
const ActorBuild := preload("res://builder/lib/actor_build.gd")

func _gear(id: StringName, category: RpgItemDefinition.Category, stat: StringName, add: float, mul: float = 1.0) -> RpgItemDefinition:
	var def := Fixtures.item(id, 1)
	def.category = category
	var mods: Array[Dictionary] = [{"stat": String(stat), "add": add, "mul": mul}]
	def.modifiers = mods
	return def

func _state() -> Node:
	var registry := {
		&"sword": _gear(&"sword", RpgItemDefinition.Category.WEAPON, &"attack", 3.0),
		&"axe": _gear(&"axe", RpgItemDefinition.Category.WEAPON, &"attack", 5.0),
		&"mail": _gear(&"mail", RpgItemDefinition.Category.ARMOR, &"defense", 2.0),
		&"ring": _gear(&"ring", RpgItemDefinition.Category.ACCESSORY, &"attack", 0.0, 2.0),
		&"potion": Fixtures.item(&"potion", 99, &"heal", 10),
	}
	var state := Fixtures.install_state(registry)
	state.new_game()
	state.player_stats.attack = 5
	state.player_stats.defense = 2
	return state

func test_the_modifiers_of_everything_worn_are_summed(t) -> void:
	var state := _state()
	t.eq(state.equipped_modifiers(&"hero").size(), 0)
	t.near(state.stat_of(&"hero", &"attack"), 5.0)
	state.inventory.add(&"sword")
	state.inventory.add(&"ring")
	state.inventory.add(&"mail")
	t.ok(state.equip(&"hero", &"sword"))
	t.near(state.stat_of(&"hero", &"attack"), 8.0)
	t.ok(state.equip(&"hero", &"ring"))  # add first, then multiply: (5 + 3) * 2
	t.near(state.stat_of(&"hero", &"attack"), 16.0)
	t.ok(state.equip(&"hero", &"mail"))
	t.near(state.stat_of(&"hero", &"defense"), 4.0)
	t.eq(state.equipped_modifiers(&"hero").size(), 3)
	Fixtures.uninstall_state()

func test_equipping_moves_the_item_and_a_swap_returns_the_old_one(t) -> void:
	var state := _state()
	state.inventory.add(&"sword")
	state.inventory.add(&"axe")
	t.ok(state.equip(&"hero", &"sword"))
	t.eq(state.inventory.count(&"sword"), 0)
	t.eq(state.equipped_in(&"hero", &"weapon"), &"sword")
	t.ok(state.equip(&"hero", &"axe"))
	t.eq(state.equipped_in(&"hero", &"weapon"), &"axe")
	t.eq(state.inventory.count(&"sword"), 1, "the sword is back in the inventory")
	t.eq(state.inventory.count(&"axe"), 0)
	t.ok(state.unequip(&"hero", &"weapon"))
	t.eq(state.equipped_in(&"hero", &"weapon"), &"")
	t.eq(state.inventory.count(&"axe"), 1)
	t.ok(not state.unequip(&"hero", &"weapon"), "an empty slot has nothing to take off")
	Fixtures.uninstall_state()

func test_what_cannot_be_worn_is_refused(t) -> void:
	var state := _state()
	state.inventory.add(&"potion")
	t.ok(not state.equip(&"hero", &"potion"), "a consumable has no slot")
	t.ok(not state.equip(&"hero", &"sword"), "an item that is not held")
	t.ok(not state.equip(&"nobody", &"potion"))
	state.inventory.add(&"sword")
	t.ok(not state.equip(&"nobody", &"sword"), "an unknown actor")
	t.eq(state.inventory.count(&"sword"), 1)
	Fixtures.uninstall_state()

func test_a_swap_with_a_full_inventory_changes_nothing(t) -> void:
	var state := _state()
	state.inventory.add(&"sword")
	state.equip(&"hero", &"sword")
	state.inventory.add(&"axe")
	state.inventory.capacity = 1  # the axe fills the only stack, and then it leaves it free for the sword
	t.ok(state.equip(&"hero", &"axe"))
	t.eq(state.inventory.count(&"sword"), 1)
	state.inventory.add(&"potion")  # the sword's stack is the only one; a potion has no room
	t.eq(state.inventory.count(&"potion"), 0)
	t.ok(not state.unequip(&"hero", &"weapon"), "no room for the axe")
	t.eq(state.equipped_in(&"hero", &"weapon"), &"axe")
	Fixtures.uninstall_state()

func test_the_preview_lists_only_the_stats_that_change(t) -> void:
	var state := _state()
	state.inventory.add(&"sword")
	state.inventory.add(&"axe")
	state.equip(&"hero", &"sword")
	var up: Dictionary = state.equip_preview(&"hero", &"weapon", &"axe")
	t.eq(up.keys(), [&"attack"])
	t.near(up[&"attack"], 2.0)
	var down: Dictionary = state.equip_preview(&"hero", &"weapon", &"")  # taking the sword off
	t.near(down[&"attack"], -3.0)
	t.eq(state.equip_preview(&"hero", &"armor", &"").size(), 0)
	Fixtures.uninstall_state()

func test_a_save_without_equipment_loads_empty_and_equipment_survives(t) -> void:
	var state := _state()
	var plain: Dictionary = state.to_dict()
	t.ok(plain.has("equipment"))
	plain.erase("equipment")
	state.inventory.add(&"sword")
	state.equip(&"hero", &"sword")
	state.from_dict(plain)
	t.eq(state.equipped_in(&"hero", &"weapon"), &"", "an old save has empty slots")
	t.eq(state.equipment.size(), 0)
	# a round trip through JSON, as the save file does
	state.inventory.add(&"sword")
	state.inventory.add(&"mail")
	state.equip(&"hero", &"sword")
	state.equip(&"hero", &"mail")
	var json := JSON.stringify(state.to_dict())
	var back: Dictionary = JSON.parse_string(json)
	state.new_game()
	t.eq(state.equipment.size(), 0)
	state.from_dict(back)
	t.eq(state.equipped_in(&"hero", &"weapon"), &"sword")
	t.eq(state.equipped_in(&"hero", &"armor"), &"mail")
	t.eq(state.equipped_in(&"hero", &"accessory"), &"")
	# nonsense in the key is dropped, not trusted
	var odd: Dictionary = state.to_dict()
	odd["equipment"] = {"hero": {"weapon": "sword", "tail": "x"}, "ghost": 5}
	state.from_dict(odd)
	t.eq(state.equipment, {"hero": {"weapon": "sword"}})
	Fixtures.uninstall_state()

func test_combat_reads_attack_and_defense_through_get_stat(t) -> void:
	var state := _state()
	var hero := RpgBattleActor.make(&"hero", "Hero", state.player_stats, true)
	var foe_stats := RpgStats.new()
	foe_stats.attack = 5
	foe_stats.defense = 2
	var foe := RpgBattleActor.make(&"slime", "Slime", foe_stats, false)
	t.eq(hero.stat(&"attack"), 5)
	state.inventory.add(&"sword")
	state.inventory.add(&"mail")
	state.equip(&"hero", &"sword")
	state.equip(&"hero", &"mail")
	t.eq(hero.stat(&"attack"), 8)
	t.eq(hero.stat(&"defense"), 4)
	t.eq(foe.stat(&"attack"), 5, "enemies wear nothing")
	t.eq(state.effective_stat(foe_stats, &"attack"), 5.0)
	t.eq(state.actor_of(foe_stats), &"")
	var hurtbox := RpgHurtbox.new()
	t.eq(hurtbox.defense(), 0, "no health, no defense")
	hurtbox.free()
	Fixtures.uninstall_state()

func test_the_preview_text_is_signed_and_coloured(t) -> void:
	var english := Fixtures.install_english()
	t.eq(RpgEquipPicker.delta_text(&"attack", 3.0), "Attack +3")
	t.eq(RpgEquipPicker.delta_text(&"defense", -1.0), "Defense -1")
	t.eq(RpgEquipPicker.delta_text(&"move_speed", 2.5), "Move speed +2.5")
	var text := RpgEquipPicker.preview_bbcode({&"attack": 3.0, &"defense": -1.0})
	t.ok(text.contains("[color=%s]Attack +3[/color]" % RpgEquipPicker.GAIN_COLOR))
	t.ok(text.contains("[color=%s]Defense -1[/color]" % RpgEquipPicker.LOSS_COLOR))
	t.eq(RpgEquipPicker.preview_bbcode({}), "No change")
	Fixtures.uninstall_english(english)

func test_the_picker_lists_the_candidates_and_equips_on_press(t) -> void:
	var english := Fixtures.install_english()
	var state := _state()
	state.inventory.add(&"sword")
	state.inventory.add(&"axe")
	state.inventory.add(&"mail")
	var picker := RpgEquipPicker.new()
	picker.actor_id = &"hero"
	picker.slot = &"weapon"
	picker.focus_item = &"axe"
	Fixtures.tree().root.add_child(picker)
	if not picker.is_node_ready():
		picker._ready()
	var names: Array[String] = []
	for b in picker.find_children("Choice_*", "Button", true, false):
		names.append(b.name)
	names.sort()
	t.eq(names, ["Choice_axe", "Choice_sword"], "only weapons")
	t.eq(picker.find_children("TakeOff", "Button", true, false).size(), 0, "nothing worn, nothing to take off")
	var preview := picker.find_child("Preview", true, false) as RichTextLabel
	t.ok(preview.text.contains("Attack +5"), "the focused axe is previewed")
	var closed := []
	picker.closed.connect(func(changed: bool) -> void: closed.append(changed))
	(picker.find_child("Choice_sword", true, false) as Button).pressed.emit()
	t.eq(state.equipped_in(&"hero", &"weapon"), &"sword")
	t.eq(closed, [true])
	Fixtures.uninstall_state()
	Fixtures.uninstall_english(english)

# ------------------------------------------------------------------ max_hp and move_speed

func _boots(id: StringName, stat: StringName, add: float) -> RpgItemDefinition:
	return _gear(id, RpgItemDefinition.Category.ACCESSORY, stat, add)

func test_a_max_hp_modifier_raises_the_cap_and_does_not_heal(t) -> void:
	var state := _state()
	state.items[&"amulet"] = _boots(&"amulet", &"max_hp", 10.0)
	var base: int = state.player_stats.max_hp
	state.player_stats.hp = base - 5
	t.eq(RpgUtil.max_hp(state.player_stats), base)
	state.inventory.add(&"amulet")
	state.equip(&"hero", &"amulet")
	t.eq(RpgUtil.max_hp(state.player_stats), base + 10)
	t.eq(state.player_stats.hp, base - 5, "wearing it does not heal")
	t.eq(RpgBattleActor.make(&"hero", "Hero", state.player_stats, true).max_hp(), base + 10)
	t.eq(RpgBattleActor.make(&"x", "X", RpgStats.new(), false).max_hp(), RpgStats.new().max_hp, "enemies wear nothing")
	# a potion heals up to the new cap
	state.items[&"big"] = Fixtures.item(&"big", 99, &"heal", 100)
	state.inventory.add(&"big")
	t.ok(state.inventory.use(&"big", state.player_stats))
	t.eq(state.player_stats.hp, base + 10)
	t.ok(not state.inventory.use(&"big", state.player_stats), "full at the new cap")
	Fixtures.uninstall_state()

func test_taking_off_a_max_hp_item_pulls_the_hp_down_but_not_to_zero(t) -> void:
	var state := _state()
	state.items[&"amulet"] = _boots(&"amulet", &"max_hp", 10.0)
	var base: int = state.player_stats.max_hp
	state.inventory.add(&"amulet")
	state.equip(&"hero", &"amulet")
	state.player_stats.hp = base + 10
	t.ok(state.unequip(&"hero", &"accessory"))
	t.eq(state.player_stats.hp, base, "clamped to the smaller cap")
	state.player_stats.hp = 3
	state.equip(&"hero", &"amulet")
	state.unequip(&"hero", &"accessory")
	t.eq(state.player_stats.hp, 3, "a lower hp is left alone")
	Fixtures.uninstall_state()

func test_a_level_up_refills_to_the_equipped_cap(t) -> void:
	var state := _state()
	state.items[&"amulet"] = _boots(&"amulet", &"max_hp", 10.0)
	state.inventory.add(&"amulet")
	state.equip(&"hero", &"amulet")
	state.player_stats.hp = 1
	t.ok(state.give_experience(1000) > 0)
	t.eq(state.player_stats.hp, RpgUtil.max_hp(state.player_stats))
	t.eq(state.player_stats.hp, state.player_stats.max_hp + 10)
	Fixtures.uninstall_state()

func test_a_move_speed_modifier_scales_the_players_walk(t) -> void:
	var state := _state()
	state.items[&"boots"] = _boots(&"boots", &"move_speed", 20.0)
	t.near(state.move_speed_factor(state.player_stats), 1.0)
	var player := ActorBuild.build("player", "Hero", null, Vector2i(16, 24), Vector2i(8, 23), 16) as RpgActor
	var movement: RpgMovement = player.component("Movement")
	movement.actor = player
	var walk := movement.speed
	t.near(movement.walk_speed(), walk)
	state.inventory.add(&"boots")
	state.equip(&"hero", &"boots")
	t.near(state.move_speed_factor(state.player_stats), 1.25)  # 80 -> 100
	t.near(movement.walk_speed(), walk * 1.25)
	var npc := ActorBuild.build("base", "Npc", null, Vector2i(16, 24), Vector2i(8, 23), 16) as RpgActor
	var npc_movement: RpgMovement = npc.component("Movement")
	npc_movement.actor = npc
	t.near(npc_movement.walk_speed(), npc_movement.speed, 0.0001)
	t.near(state.move_speed_factor(RpgStats.new()), 1.0, 0.0001)
	player.free()
	npc.free()
	Fixtures.uninstall_state()

func test_equipping_announces_itself_on_the_event_bus(t) -> void:
	var state := _state()
	var seen := []
	RpgUtil.events().equipment_changed.connect(func(actor: StringName, slot: StringName) -> void: seen.append([actor, slot]))
	state.inventory.add(&"sword")
	state.equip(&"hero", &"sword")
	state.unequip(&"hero", &"weapon")
	t.eq(seen, [[&"hero", &"weapon"], [&"hero", &"weapon"]])
	Fixtures.uninstall_state()
