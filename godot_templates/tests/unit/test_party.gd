extends RefCounted
## Party members (T12.47): joining and leaving, the events and the condition, turn order and
## targets with a full party, shared experience, equipment per member, the status menu and the save.

const Fixtures := preload("../lib/fixtures.gd")
const UiRecipes := preload("res://builder/recipes/ui_recipes.gd")
const SceneUtil := preload("res://builder/lib/scene_util.gd")

const MENU_TMP := "user://test_status_menu.tscn"
const INVENTORY_TMP := "user://test_inventory_menu.tscn"
const S := RpgBattleController.State

class FixedRng extends RpgRng:
	func randf_range(_a: float, _b: float) -> float:
		return 1.0
	func randf() -> float:
		return 0.5
	func randi_range(from: int, _to: int) -> int:
		return from
	func pick(items: Array) -> Variant:
		return null if items.is_empty() else items[0]

func _actor(id: StringName, speed: int = 5, attack: int = 8) -> RpgActorDefinition:
	var def := RpgActorDefinition.new()
	def.id = id
	def.display_name = String(id).capitalize()
	var stats := RpgStats.new()
	stats.max_hp = 20
	stats.hp = 20
	stats.attack = attack
	stats.defense = 1
	stats.speed = speed
	def.base_stats = stats
	return def

func _gear(id: StringName, category: RpgItemDefinition.Category, stat: StringName, add: float) -> RpgItemDefinition:
	var def := Fixtures.item(id, 1)
	def.category = category
	var mods: Array[Dictionary] = [{"stat": String(stat), "add": add, "mul": 1.0}]
	def.modifiers = mods
	return def

var _english: Translation = null

## The game state with four actors to recruit, and the English strings (the join and leave notes
## format their text). Pair it with _end().
func _state() -> Node:
	if _english == null:
		_english = Fixtures.install_english()
	var state := Fixtures.install_state({
		&"potion": Fixtures.item(&"potion", 99, &"heal", 10),
		&"sword": _gear(&"sword", RpgItemDefinition.Category.WEAPON, &"attack", 3.0),
	})
	state.new_game()
	state.inventory.slots.clear()
	state.player_stats = RpgStats.new()
	state.player_stats.speed = 6
	state.player_stats.attack = 10
	for id in [&"mira", &"bo", &"cass", &"dre"]:
		state.actor_defs[id] = _actor(id)
	return state

func _end() -> void:
	Fixtures.uninstall_state()
	if _english != null:
		Fixtures.uninstall_english(_english)
		_english = null

func _enemy(enemy_hp: int = 30, xp: int = 20) -> RpgEnemyDefinition:
	var def := RpgEnemyDefinition.new()
	def.id = &"slime"
	def.display_name = "Slime"
	var stats := RpgStats.new()
	stats.max_hp = enemy_hp
	stats.hp = enemy_hp
	stats.attack = 1
	stats.defense = 1
	stats.speed = 1
	def.base_stats = stats
	def.xp_reward = xp
	return def

# ------------------------------------------------------------------ joining and leaving

func test_a_character_joins_and_leaves(t) -> void:
	var state := _state()
	var changes := []
	RpgUtil.events().party_changed.connect(func() -> void: changes.append(state.party.size()))
	t.eq(state.party_ids(), [&"hero"] as Array[StringName])
	t.ok(state.join_party(&"mira"))
	t.eq(state.party_ids(), [&"hero", &"mira"] as Array[StringName])
	t.ok(state.in_party(&"mira"))
	t.eq(state.stats_of(&"mira").hp, 20, "a new member starts at full hit points")
	t.ok(state.stats_of(&"mira") != state.actor_definition(&"mira").base_stats, "the member has a copy of the stats")
	t.ok(state.leave_party(&"mira"))
	t.ok(not state.in_party(&"mira"))
	t.eq(changes, [1, 0])
	_end()

func test_joining_is_refused_when_it_cannot_work(t) -> void:
	var state := _state()
	t.ok(state.join_party(&"mira"))
	t.ok(not state.join_party(&"mira"), "twice")
	t.ok(not state.join_party(&"hero"), "the player is in already")
	t.ok(not state.join_party(&""), "no id")
	t.ok(state.join_party(&"bo"))
	t.ok(state.join_party(&"cass"))
	t.eq(state.party_ids().size(), RpgGameState.MAX_PARTY, "the player and three members make four")
	t.ok(not state.join_party(&"dre"), "the party is full")
	t.ok(not state.leave_party(&"hero"), "the player cannot leave")
	t.ok(not state.leave_party(&"dre"), "dre never joined")
	_end()

func test_a_character_without_a_definition_cannot_join(t) -> void:
	var state := _state()
	t.ok(not state.join_party(&"ghost"))
	t.eq(state.party.size(), 0)
	_end()

func test_the_dialogue_events_and_the_condition(t) -> void:
	var state := _state()
	t.ok(not RpgCondition.evaluate("party:mira"))
	t.ok(RpgDialogueRunner.execute_event("join_party:mira"))
	t.ok(RpgCondition.evaluate("party:mira"))
	t.ok(RpgCondition.evaluate("party:hero and not party:bo"))
	t.ok(RpgDialogueRunner.execute_event("leave_party:mira"))
	t.ok(not RpgCondition.evaluate("party:mira"))
	t.ok(not RpgDialogueRunner.execute_event("join_party"), "an id is needed")
	t.ok(not RpgDialogueRunner.execute_event("leave_party:"), "an id is needed")
	_end()

func test_leaving_takes_the_gear_back_to_the_inventory(t) -> void:
	var state := _state()
	state.join_party(&"mira")
	state.inventory.add(&"sword")
	t.ok(state.equip(&"mira", &"sword"))
	t.eq(state.inventory.count(&"sword"), 0)
	state.leave_party(&"mira")
	t.eq(state.inventory.count(&"sword"), 1)
	t.eq(state.equipped_in(&"mira", &"weapon"), &"")
	_end()

func test_each_member_has_their_own_equipment(t) -> void:
	var state := _state()
	state.join_party(&"mira")
	state.inventory.add(&"sword")
	t.ok(state.equip(&"mira", &"sword"))
	t.near(state.stat_of(&"mira", &"attack"), 11.0)
	t.near(state.stat_of(&"hero", &"attack"), 10.0, 0.001, "the player is not wearing it")
	t.eq(state.equipped_in(&"hero", &"weapon"), &"")
	var battler := RpgBattleActor.make(&"mira", "Mira", state.stats_of(&"mira"), true)
	t.eq(battler.stat(&"attack"), 11, "combat reads the member's equipment")
	_end()

# ------------------------------------------------------------------ battle

func _battle(members: Array, enemy_count: int = 1, enemy_hp: int = 30, xp: int = 20) -> Dictionary:
	var state := _state()
	for id: StringName in members:
		state.join_party(id)
	var data := RpgEncounterData.new()
	var defs: Array[RpgEnemyDefinition] = []
	for i in enemy_count:
		defs.append(_enemy(enemy_hp, xp))
	data.enemies = defs
	var c := RpgBattleController.new()
	c.setup(data, FixedRng.new())
	return {"state": state, "c": c}

func _done(b: Dictionary) -> void:
	(b["c"] as Node).free()
	_end()

func test_the_battle_party_is_the_player_and_the_members(t) -> void:
	var b := _battle([&"mira", &"bo"])
	var c: RpgBattleController = b["c"]
	t.eq(c.party.size(), 3)
	t.eq(c.party[1].id, &"mira")
	t.eq(c.party[1].display_name, "Mira")
	t.ok(c.party[1].stats == b["state"].stats_of(&"mira"), "members share their live stats")
	_done(b)

func test_every_member_acts_in_speed_order(t) -> void:
	var b := _battle([&"mira"], 1, 200)
	var c: RpgBattleController = b["c"]
	b["state"].stats_of(&"mira").speed = 9  # faster than the player (6) and the slime (1)
	var acted: Array = []
	c.entries_resolved.connect(func(entries: Array) -> void:
		for e: Dictionary in entries:
			acted.append(String(e["text"]).get_slice(" ", 0)))
	var asked: Array = []
	c.auto_choose = func(actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary:
		asked.append(actor.id)
		return {"command_id": &"attack", "target_index": 0}
	c.round_number = 0
	# One round only: the slime survives, so stop after it by capping the battle with an escape.
	c.can_escape = true
	await _one_round(c)
	t.eq(asked, [&"hero", &"mira"], "everyone on the player side is asked, in party order")
	t.eq(acted.slice(0, 3), ["Mira", "Hero", "Slime"], "mira (9), then the hero (6), then the slime (1)")
	_done(b)

## Runs round one of the controller by hand: ask, choose for the enemies, execute.
func _one_round(c: RpgBattleController) -> void:
	c._choices.clear()
	for a in RpgBattleController.living(c.party):
		c._choices[a] = await c._choose_player(a)
	for a in RpgBattleController.living(c.enemies):
		c._choices[a] = c._choose_enemy(a)
	await c._execute_round()

func test_targets_cover_the_whole_party(t) -> void:
	var b := _battle([&"mira", &"bo"])
	var c: RpgBattleController = b["c"]
	var heal := c.command_by_id(&"item")
	var asked := c.candidates(c.party[0], heal)
	t.eq(asked.size(), 3, "an ally-targeted command can be aimed at each of the three")
	c.party[1].stats.hp = 0
	t.eq(c.candidates(c.party[0], heal).size(), 2, "a fallen member is not offered")
	t.eq(c.candidates(c.party[0], c.command_by_id(&"attack")).size(), 1)
	_done(b)

func test_experience_is_shared_and_level_ups_are_announced(t) -> void:
	var b := _battle([&"mira"], 1, 10, 25)  # level 1 needs 10, level 2 needs 28
	var c: RpgBattleController = b["c"]
	var levels := []
	RpgUtil.events().level_up.connect(func(id: StringName, level: int) -> void: levels.append([id, level]))
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary: return {"command_id": &"attack", "target_index": 0}
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.VICTORY)
	t.eq(b["state"].player_stats.level, 2)
	t.eq(b["state"].stats_of(&"mira").level, 2, "the member gets the same experience")
	t.eq(levels.size(), 2)
	t.eq(c.level_ups.size(), 2)
	_done(b)

func test_a_fallen_member_gets_no_experience_and_stands_up_after_the_battle(t) -> void:
	var b := _battle([&"mira"], 1, 10, 6)
	var c: RpgBattleController = b["c"]
	b["state"].stats_of(&"mira").hp = 0
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary: return {"command_id": &"attack", "target_index": 0}
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.VICTORY)
	t.eq(b["state"].stats_of(&"mira").experience, 0)
	t.eq(b["state"].player_stats.experience, 6)
	t.eq(b["state"].stats_of(&"mira").hp, 1, "back on their feet with 1 HP")
	_done(b)

func test_losing_with_the_whole_party_is_a_defeat(t) -> void:
	var b := _battle([&"mira"], 1, 500)
	var c: RpgBattleController = b["c"]
	(c.enemies[0].stats as RpgStats).attack = 500
	c.auto_choose = func(_actor: RpgBattleActor, _battle_ref: Variant) -> Dictionary: return {"command_id": &"defend"}
	var result := await c.run()
	t.eq(result.outcome, RpgEncounterResult.Outcome.DEFEAT)
	t.eq(b["state"].stats_of(&"mira").hp, 0, "the defeat policy decides what happens next")
	_done(b)

func test_experience_from_a_quest_reward_is_shared_too(t) -> void:
	var state := _state()
	state.join_party(&"mira")
	state.give_experience(10)
	t.eq(state.player_stats.level, 2)
	t.eq(state.stats_of(&"mira").level, 2)
	t.eq(state.give_experience_to(&"nobody", 5), 0)
	_end()

# ------------------------------------------------------------------ save

func test_the_party_and_its_equipment_survive_a_save_round_trip(t) -> void:
	var state := _state()
	state.join_party(&"mira")
	state.join_party(&"bo")
	state.inventory.add(&"sword")
	state.equip(&"bo", &"sword")
	state.stats_of(&"mira").hp = 7
	state.stats_of(&"mira").level = 3
	var back: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	state.new_game()
	t.eq(state.party.size(), 0)
	state.from_dict(back)
	t.eq(state.party_ids(), [&"hero", &"mira", &"bo"] as Array[StringName])
	t.eq(state.stats_of(&"mira").hp, 7)
	t.eq(state.stats_of(&"mira").level, 3)
	t.eq(state.equipped_in(&"bo", &"weapon"), &"sword")
	t.near(state.stat_of(&"bo", &"attack"), 11.0)
	_end()

func test_a_save_without_a_party_loads_with_none(t) -> void:
	var state := _state()
	state.join_party(&"mira")
	var old: Dictionary = JSON.parse_string(JSON.stringify(state.to_dict()))
	old.erase("party")
	state.from_dict(old)
	t.eq(state.party.size(), 0)
	_end()

# ------------------------------------------------------------------ the status menu

func _menu() -> RpgStatusMenu:
	var root: Node = UiRecipes.new().call("_build_status_menu")
	SceneUtil.save_scene(root, MENU_TMP)
	var menu := (load(MENU_TMP) as PackedScene).instantiate() as RpgStatusMenu
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	return menu

func test_the_status_menu_pages_through_the_members(t) -> void:
	var state := _state()
	var alone := _menu()
	t.ok(alone.get_node_or_null("%Stats/Member") == null, "no pager for one character")
	t.eq(alone.shown_actor(), &"hero")
	alone.free()
	state.join_party(&"mira")
	state.stats_of(&"mira").attack = 12
	var menu := _menu()
	t.ok(menu.get_node_or_null("%Stats/Member") != null)
	t.eq(menu.shown_actor(), &"hero")
	menu.page(1)
	await Fixtures.tree().process_frame
	t.eq(menu.shown_actor(), &"mira")
	var texts := []
	for child in (menu.get_node("%Stats") as VBoxContainer).get_children():
		if child is Label and not child.is_queued_for_deletion():
			texts.append((child as Label).text)
	t.ok(texts.has("Attack: 12"), "the stats of the member on show: %s" % str(texts))
	menu.page(1)
	await Fixtures.tree().process_frame
	t.eq(menu.shown_actor(), &"hero", "wraps around")
	menu.free()
	_end()

func test_the_picker_of_the_status_menu_equips_the_member_on_show(t) -> void:
	var state := _state()
	state.join_party(&"mira")
	state.inventory.add(&"sword")
	var menu := _menu()
	menu.page(1)
	await Fixtures.tree().process_frame
	menu._open_picker(&"weapon")
	var picker: RpgEquipPicker = null
	for child in menu.get_children():
		if child is RpgEquipPicker:
			picker = child
	t.ok(picker != null)
	t.eq(picker.actor_id, &"mira")
	picker.free()
	menu.free()
	_end()

# ------------------------------------------------------------------ the demo

func test_the_demo_villager_offers_the_companion_only_when_asked_to(t) -> void:
	var recipe: Object = load("res://builder/recipes/data_recipe.gd").new()
	var plain: RpgDialogueResource = recipe._greeting()
	for line in plain.lines:
		t.ok(not line.events.has("join_party:companion"))
	var res: RpgDialogueResource = recipe._greeting(true)
	var join: RpgDialogueLine = null
	var ask: RpgDialogueLine = null
	for line in res.lines:
		if line.id == &"join":
			join = line
		if line.id == &"ask":
			ask = line
	t.ok(join != null and join.events.has("join_party:companion"))
	t.eq(res.lines[res.lines.size() - 1].id, &"bye", "bye stays last, or the dialogue would run on into join")
	var conditions := []
	for choice in ask.choices:
		conditions.append(choice.condition)
	t.ok(conditions.has("not party:companion") and conditions.has("party:companion"))
	var state := _state()
	state.actor_defs[&"companion"] = _actor(&"companion")
	var runner := RpgDialogueRunner.new()
	runner.start(res)
	runner.advance()  # greet -> ask
	var wanted := -1
	var visible := runner.visible_choices()
	for i in visible.size():
		if visible[i].next == &"join":
			wanted = i
	t.ok(wanted >= 0, "the join choice is offered before the companion has joined")
	runner.choose(wanted)
	t.ok(state.in_party(&"companion"))
	_end()

# ------------------------------------------------------------------ items on members

func _inventory_menu() -> RpgInventoryMenu:
	var root: Node = UiRecipes.new().call("_build_inventory_menu")
	SceneUtil.save_scene(root, INVENTORY_TMP)
	var menu := (load(INVENTORY_TMP) as PackedScene).instantiate() as RpgInventoryMenu
	Fixtures.tree().root.add_child(menu)
	if not menu.is_node_ready():
		menu._ready()
	return menu

func test_an_item_from_the_inventory_menu_can_heal_a_member(t) -> void:
	var state := _state()
	state.join_party(&"mira")
	state.stats_of(&"mira").hp = 5
	state.inventory.add(&"potion", 2)
	var menu := _inventory_menu()
	menu._selected = &"potion"
	menu.use_on(&"mira")
	t.eq(state.stats_of(&"mira").hp, 15)
	t.eq(state.inventory.count(&"potion"), 1)
	menu.use_on(&"hero")  # the hero is at full health: refused, the potion is kept
	t.eq(state.inventory.count(&"potion"), 1)
	menu.free()
	_end()

func test_the_member_picker_lists_everyone_and_reports_the_choice(t) -> void:
	var state := _state()
	state.join_party(&"mira")
	var picker := RpgMemberPicker.new()
	Fixtures.tree().root.add_child(picker)
	if not picker.is_node_ready():
		picker._ready()
	var picked := []
	picker.chosen.connect(func(id: StringName) -> void: picked.append(id))
	t.ok(picker.find_child("Member_hero", true, false) != null)
	var mira := picker.find_child("Member_mira", true, false) as Button
	t.ok(mira != null)
	mira.pressed.emit()
	t.eq(picked, [&"mira"])
	picker.free()
	_end()
