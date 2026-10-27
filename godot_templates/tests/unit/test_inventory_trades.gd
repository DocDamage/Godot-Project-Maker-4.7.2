extends RefCounted
## The inventory of 1.5.0: trades all or nothing, slots that carry their own data, what is given
## to a full bag waiting for room, gear that wears and breaks, and sets of gear.

const Fixtures := preload("../lib/fixtures.gd")

var _english: Translation = null

func _gear(id: StringName, category: RpgItemDefinition.Category, durability: int = 0, set_id: StringName = &"", defense: float = 0.0) -> RpgItemDefinition:
	var def := Fixtures.item(id, 1)
	def.display_name = String(id).capitalize()
	def.category = category
	def.durability = durability
	def.set_id = set_id
	if defense != 0.0:
		var mods: Array[Dictionary] = [{"stat": "defense", "add": defense}]
		def.modifiers = mods
	return def

func _state() -> Node:
	if _english == null:
		_english = Fixtures.install_english()
	var potion := Fixtures.item(&"potion", 10)
	potion.display_name = "Potion"
	var state := Fixtures.install_state({
		&"potion": potion,
		&"herb": Fixtures.item(&"herb"),
		&"sword": _gear(&"sword", RpgItemDefinition.Category.WEAPON, 3),
		&"helm": _gear(&"helm", RpgItemDefinition.Category.ARMOR, 0, &"knight", 2.0),
		&"ring": _gear(&"ring", RpgItemDefinition.Category.ACCESSORY, 2, &"knight"),
	})
	state.new_game()
	state.inventory.slots.clear()
	state.equipment.clear()
	state.gold = 0
	return state

func _end() -> void:
	Fixtures.uninstall_state()
	if _english != null:
		Fixtures.uninstall_english(_english)
		_english = null

func _toasts() -> Array:
	var seen := []
	RpgUtil.events().notify.connect(func(text: String) -> void: seen.append(text))
	return seen

# ------------------------------------------------------------------ all or nothing

func test_a_trade_happens_whole_or_not_at_all(t) -> void:
	var state := _state()
	var bag: RpgInventory = state.inventory
	bag.capacity = 2
	bag.add(&"herb", 5)
	t.ok(not bag.transact([{"item_id": "potion", "qty": 1}], [{"item_id": "herb", "qty": 6}]), "six herbs are not held")
	t.eq(bag.count(&"herb"), 5, "nothing taken")
	bag.add(&"sword")
	t.ok(not bag.fits([{"item_id": "potion", "qty": 1}]), "the bag is full")
	t.ok(bag.fits([{"item_id": "potion", "qty": 1}], [{"item_id": "herb", "qty": 5}]), "taking the herbs makes room")
	t.ok(bag.transact([{"item_id": "potion", "qty": 3}], [{"item_id": "herb", "qty": 5}]))
	t.eq([bag.count(&"herb"), bag.count(&"potion")], [0, 3])
	t.ok(not bag.transact([{"item_id": "potion", "qty": 8}, {"item_id": "herb", "qty": 1}]), "the potions fit, the herb does not")
	t.eq([bag.count(&"potion"), bag.count(&"herb")], [3, 0], "so neither is given")
	_end()

func test_a_trial_changes_nothing_and_says_nothing(t) -> void:
	var state := _state()
	var seen := []
	RpgUtil.events().item_added.connect(func(id: StringName, _qty: int) -> void: seen.append(id))
	state.inventory.fits([{"item_id": "potion", "qty": 2}])
	t.eq(state.inventory.slots.size(), 0)
	t.eq(seen, [], "no signal for a trial")
	_end()

# ------------------------------------------------------------------ data

func test_a_slot_that_carries_data_holds_one_and_never_stacks(t) -> void:
	var state := _state()
	var bag: RpgInventory = state.inventory
	t.ok(bag.add_with(&"herb", {"wear": 2}))
	bag.add(&"herb", 3)
	t.eq(bag.slots.size(), 2, "the plain herbs do not join the one with data")
	t.eq(bag.count(&"herb"), 4)
	t.eq(bag.data_at(0), {"wear": 2})
	bag.remove(&"herb", 3)
	t.eq(bag.count(&"herb"), 1, "the plain ones go first")
	t.eq(bag.data_at(0), {"wear": 2})
	var saved: Array = JSON.parse_string(JSON.stringify(bag.to_array()))
	bag.load_array(RpgUtil.restore_numbers(saved))
	t.eq(bag.data_at(0), {"wear": 2}, "kept by a save")
	t.eq(bag.take_one(&"herb"), {"wear": 2})
	t.eq(bag.take_one(&"herb"), null, "none left")
	_end()

# ------------------------------------------------------------------ waiting for room

func test_what_does_not_fit_waits_and_comes_when_there_is_room(t) -> void:
	var state := _state()
	var toasts := _toasts()
	state.inventory.capacity = 1
	state.inventory.add(&"herb")
	var waiting: Array = state.give_items([{"item_id": "potion", "qty": 2}])
	t.eq(waiting, [{"item_id": "potion", "qty": 2}] as Array[Dictionary])
	t.eq(state.pending_items, [{"item_id": "potion", "qty": 2}] as Array[Dictionary])
	t.ok(toasts.has("No room in the bag: Potion x2 will wait for you"), str(toasts))
	state.inventory.remove(&"herb")
	t.eq(state.inventory.count(&"potion"), 2, "they came as soon as there was room")
	t.eq(state.pending_items.size(), 0)
	t.ok(toasts.has("Potion x2 put in your bag"), str(toasts))
	_end()

func test_quest_rewards_chests_and_the_dialogue_never_lose_an_item(t) -> void:
	var state := _state()
	state.inventory.capacity = 1
	state.inventory.add(&"herb")
	var quest := RpgQuestDefinition.new()
	quest.id = &"q"
	var stages: Array[Dictionary] = [{"id": "a", "complete_when": ""}]
	quest.stages = stages
	quest.rewards = {"items": [{"item_id": "potion", "qty": 1}]}
	state.quest_defs[&"q"] = quest
	state.quest_start(&"q")
	state.quest_complete(&"q")
	RpgDialogueRunner.execute_event("give_item:potion:2")
	var chest := RpgChest.new()
	var loot: Array[Dictionary] = [{"item_id": "potion", "qty": 1}]
	chest.loot = loot
	chest.interact()
	chest.free()
	t.eq(state.pending_items, [{"item_id": "potion", "qty": 4}] as Array[Dictionary], "all four wait")
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	state.new_game()
	t.eq(state.pending_items.size(), 0)
	state.from_dict(back)
	t.eq(state.pending_items, [{"item_id": "potion", "qty": 4}] as Array[Dictionary], "kept by a save")
	state.inventory.capacity = 2
	state.deliver_pending()
	t.eq(state.inventory.count(&"potion"), 4)
	t.ok(not state.to_dict().has("pending_items"), "nothing waits, nothing saved")
	_end()

# ------------------------------------------------------------------ wear

func test_gear_wears_and_breaks(t) -> void:
	var state := _state()
	var toasts := _toasts()
	state.inventory.add(&"sword")
	t.ok(state.equip(&"hero", &"sword"))
	t.eq(state.wear_of(&"hero", &"weapon"), [0, 3] as Array[int])
	t.ok(not state.wear_stats(state.player_stats, &"weapon"))
	t.eq(state.wear_of(&"hero", &"weapon"), [1, 3] as Array[int])
	t.ok(state.unequip(&"hero", &"weapon"))
	t.eq(state.inventory.data_at(0), {"wear": 1}, "its wear goes with it into the bag")
	t.ok(state.equip(&"hero", &"sword"))
	t.eq(state.wear_of(&"hero", &"weapon"), [1, 3] as Array[int], "and back")
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	t.eq(RpgUtil.restore_numbers(back["worn_data"]), {"hero": {"weapon": {"wear": 1}}}, "saved")
	t.ok(not state.wear(&"hero", &"weapon", 1))
	t.ok(state.wear(&"hero", &"weapon", 1), "the third blow breaks it")
	t.eq(state.equipped_in(&"hero", &"weapon"), &"")
	t.eq(state.inventory.count(&"sword"), 0, "gone")
	t.ok(toasts.has("Sword broke"), str(toasts))
	state.from_dict(back)
	t.eq(state.wear_of(&"hero", &"weapon"), [1, 3] as Array[int], "loaded")
	_end()

func test_gear_without_durability_never_wears(t) -> void:
	var state := _state()
	state.inventory.add(&"helm")
	state.equip(&"hero", &"helm")
	state.inventory.add(&"ring")
	state.equip(&"hero", &"ring")
	state.wear_from_hit(state.player_stats)
	t.eq(state.wear_of(&"hero", &"armor"), [0, 0] as Array[int])
	t.eq(state.wear_of(&"hero", &"accessory"), [1, 2] as Array[int], "a hit wears the ring")
	t.ok(not state.to_dict()["worn_data"].has("armor") if state.to_dict().has("worn_data") else true)
	_end()

# ------------------------------------------------------------------ sets

func test_a_set_gives_its_bonus_when_enough_is_worn(t) -> void:
	var state := _state()
	var knight := RpgItemSet.new()
	knight.id = &"knight"
	knight.title = "Knight"
	var bonuses: Array[Dictionary] = [{"pieces": 2, "modifiers": [{"stat": "defense", "add": 5}]}]
	knight.bonuses = bonuses
	state.item_sets[&"knight"] = knight
	var base: float = state.stat_of(&"hero", &"defense")
	state.inventory.add(&"helm")
	state.equip(&"hero", &"helm")
	t.eq(state.stat_of(&"hero", &"defense"), base + 2.0, "one piece: the helm alone")
	t.eq(state.equip_preview(&"hero", &"accessory", &"ring"), {&"defense": 5.0}, "the preview counts the set")
	state.inventory.add(&"ring")
	state.equip(&"hero", &"ring")
	t.eq(state.stat_of(&"hero", &"defense"), base + 7.0, "two pieces: the set's bonus")
	t.eq(state.worn_sets(&"hero"), [{"set_id": &"knight", "worn": 2, "bonus_at": 2}] as Array[Dictionary])
	t.eq(knight.modifiers_for(1), [])
	t.eq(knight.first_bonus_at(), 2)
	_end()
