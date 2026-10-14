extends RefCounted
## T17.24: the cave, combat on a farm. The pure parts of the cave's recipe (the runs its rock is
## drawn in), the weapon (what it adds to a swing, the shop's row, the hotbar's `use`), the
## farmer's health and hurtbox made at run time, the enemies of a cave that come back every
## morning and what one leaves, and being defeated, which ends the day as 2:00 does. A farm that
## does not fight does none of it.

const Fixtures := preload("../lib/fixtures.gd")
const AddedMaps := preload("../../builder/recipes/farm/added_maps_recipe.gd")
const FarmBuild := preload("../../builder/recipes/farm/farm_build.gd")

const SAVE_DIR := "user://test_farm_cave"
const CAVE_THINGS := [
	{"id": "forage_herb", "name": "Herb", "item": "forage_herb", "seasons": ["spring"], "price": 15, "energy": 8},
	{"id": "forage_ore", "name": "Ore", "item": "forage_ore", "seasons": [], "price": 40, "energy": 0, "maps": ["cave"]},
	{"id": "forage_gem", "name": "Gem", "item": "forage_gem", "seasons": [], "price": 60, "energy": 0, "maps": ["cave"]},
]

var _made: Array[Node] = []

## A farm's game with the weapon among its items: {state, mode, calendar, day_end, fight}.
func _game(fights: bool) -> Dictionary:
	var registry := {}
	for id: StringName in [&"potion", &"forage_herb", &"forage_ore", &"forage_gem"]:
		registry[id] = Fixtures.item(id)
	var sword := Fixtures.item(RpgFarmFight.WEAPON, 1)
	sword.category = RpgItemDefinition.Category.KEY
	var mods: Array[Dictionary] = [{"stat": "attack", "add": 4, "mul": 1.0}, {"stat": "defense", "add": 9, "mul": 1.0}]
	sword.modifiers = mods
	registry[RpgFarmFight.WEAPON] = sword
	var state := Fixtures.install_state(registry) as RpgGameState
	state.inventory.registry = state.items
	var save := Fixtures.install("SaveManager", Fixtures.SAVE_MANAGER) as RpgSaveManager
	save.dir = SAVE_DIR
	var mode := RpgFarmMode.new()
	mode.fights = fights
	mode._ready()
	mode.forage.add_lists(CAVE_THINGS, [])
	_made.append(mode)
	return {"state": state, "mode": mode, "calendar": RpgCalendar.current(), "day_end": mode.day_end, "fight": mode.fight}

func _cleanup() -> void:
	var tree := Fixtures.tree()
	tree.paused = false
	for node in _made:
		if is_instance_valid(node):
			node.free()
	_made.clear()
	var save := tree.root.get_node_or_null("SaveManager") as RpgSaveManager
	if save != null:
		for slot in range(RpgSaveManager.AUTOSAVE_SLOT, RpgSaveManager.SLOTS + 1):
			save.delete(slot)
	Fixtures.uninstall("SaveManager")
	Fixtures.uninstall_state()

func test_the_rock_of_a_cave_is_drawn_in_runs_along_its_rows(t) -> void:
	var rock: Array[Vector2i] = [Vector2i(3, 1), Vector2i(1, 1), Vector2i(2, 1), Vector2i(5, 1), Vector2i(4, 2)]
	t.eq(AddedMaps.cell_runs(rock), [Rect2i(1, 1, 3, 1), Rect2i(5, 1, 1, 1), Rect2i(4, 2, 1, 1)], "a run a row, ended where the rock is not")
	t.eq(AddedMaps.cell_runs([]), [])
	t.eq(AddedMaps.CAVE, RpgFarmFight.CAVE, "the recipe's kind is the game's")
	t.eq(FarmBuild.WEAPON, String(RpgFarmFight.WEAPON), "the item the recipe writes is the one the game swings")
	t.eq(FarmBuild.WEAPON_PRICE, RpgFarmFight.WEAPON_PRICE)

func test_what_the_weapon_adds_is_its_attack(t) -> void:
	var def := Fixtures.item(&"blade")
	t.eq(RpgFarmBlade.bonus_of(def), 0, "an item without modifiers")
	var mods: Array[Dictionary] = [{"stat": "attack", "add": 3, "mul": 1.0}, {"stat": "defense", "add": 5, "mul": 1.0}, {"stat": "attack", "add": 1.4, "mul": 1.0}]
	def.modifiers = mods
	t.eq(RpgFarmBlade.bonus_of(def), 4, "the attack's, rounded")
	t.eq(RpgFarmBlade.bonus_of(null), 0)
	var blade := RpgFarmBlade.new()
	blade.reach = Vector2(8, 8)
	blade.center = Vector2(0, -8)
	blade.swing("right", 4)
	t.ok(blade.active, "a swing can hit")
	t.eq([blade.bonus, blade.position], [4, Vector2(8, -8)], "aimed the way the farmer faces")
	blade._physics_process(RpgFarmBlade.SWING_S + 0.01)
	t.ok(not blade.active, "and is over after a moment")
	blade.swing("right", 0, Vector2(30, 17))  # on diamonds: toward the cell faced
	t.eq(blade.position, Vector2(0, -8) + Vector2(30, 17).normalized() * 8.0, "aimed at the faced cell")
	blade.free()

func test_a_farm_that_does_not_fight_has_no_weapon_and_nothing_to_fight(t) -> void:
	var game := _game(false)
	var fight: RpgFarmFight = game["fight"]
	var mode: RpgFarmMode = game["mode"]
	t.ok(fight != null and not fight.enabled, "the part is there and does nothing")
	t.eq(RpgFarmFight.current(), null)
	t.ok(not fight.is_weapon(RpgFarmFight.WEAPON))
	t.ok(not RpgFarmShop.stock_sources.has(fight.stock), "the shop sells no weapon")
	var farmer := Node2D.new()
	_made.append(farmer)
	t.ok(not fight.arm(farmer), "nobody is armed")
	t.eq(farmer.get_child_count(), 0)
	t.ok(mode.tool_for(RpgFarmFight.WEAPON) == null)
	_cleanup()

func test_a_farm_that_fights_sells_the_weapon_and_arms_the_farmer(t) -> void:
	var game := _game(true)
	var fight: RpgFarmFight = game["fight"]
	var state: RpgGameState = game["state"]
	t.ok(fight.is_weapon(RpgFarmFight.WEAPON) and not fight.is_weapon(&"potion"))
	t.ok(RpgFarmShop.stock_sources.has(fight.stock), "a stock source of the shop")
	var shop := RpgFarmShop.new()
	shop.seasonal = false
	t.ok(shop.offered(state.items).has(RpgFarmFight.WEAPON), "the weapon is for sale")
	t.eq(shop.buy_price(RpgFarmFight.WEAPON, state.items), RpgFarmFight.WEAPON_PRICE)
	state.gold = 500
	t.eq(shop.buy(state, RpgFarmFight.WEAPON, 1), RpgShopDefinition.OK)
	t.eq([state.gold, state.inventory.count(RpgFarmFight.WEAPON)], [300, 1])
	t.ok(not shop.offered(state.items).has(RpgFarmFight.WEAPON), "kept like a tool: not offered twice")
	var farmer := Node2D.new()
	_made.append(farmer)
	t.ok(fight.arm(farmer))
	var hurtbox := farmer.get_node_or_null(RpgFarmFight.HURTBOX_NODE) as RpgHurtbox
	var blade := farmer.get_node_or_null(RpgFarmFight.BLADE_NODE) as RpgFarmBlade
	t.ok(farmer.get_node_or_null(RpgFarmFight.HEALTH_NODE) is RpgHealth, "health")
	t.ok(hurtbox != null and hurtbox.get_collision_layer_value(9) and hurtbox.team == &"player", "the player's hurtbox (9), which the enemies' hitboxes look for")
	t.ok(blade != null and blade.get_collision_layer_value(7) and blade.get_collision_mask_value(10), "the player's hitbox (7) looks for the enemies' hurtboxes (10)")
	t.ok(not blade.active, "and hits nothing until a swing")
	var count := farmer.get_child_count()
	t.ok(fight.arm(farmer))
	t.eq(farmer.get_child_count(), count, "once")
	_cleanup()

func test_the_enemies_of_a_cave_come_back_and_leave_a_thing_of_the_cave(t) -> void:
	var game := _game(true)
	var fight: RpgFarmFight = game["fight"]
	var state: RpgGameState = game["state"]
	t.ok(RpgFarmFight.is_cave_enemy("farm_map_3_enemy_2"))
	t.ok(not RpgFarmFight.is_cave_enemy("starter_map_enemy_001"), "an enemy of another map is none")
	t.ok(not RpgFarmFight.is_cave_enemy("farm_map_3_debris_2"))
	t.eq(fight.cave_things(), [&"forage_ore", &"forage_gem"] as Array[StringName], "the things whose entries name the cave")
	state.set_flag("farm_map_3_enemy_1", "defeated", true)
	state.set_flag("farm_map_3_enemy_2", "defeated", false)
	state.set_flag("starter_map_enemy_001", "defeated", true)
	t.eq(fight.revive_enemies(), 1)
	t.ok(not RpgUtil.to_bool(state.get_flag("farm_map_3_enemy_1", "defeated", false)), "back in the morning")
	t.ok(RpgUtil.to_bool(state.get_flag("starter_map_enemy_001", "defeated", false)), "nobody else")
	var calendar: RpgCalendar = game["calendar"]
	state.set_flag("farm_map_3_enemy_1", "defeated", true)
	calendar.end_day()
	t.ok(not RpgUtil.to_bool(state.get_flag("farm_map_3_enemy_1", "defeated", false)), "the morning brings it back")
	_cleanup()

func test_being_defeated_ends_the_day_as_two_o_clock_does(t) -> void:
	var game := _game(true)
	var state: RpgGameState = game["state"]
	var mode: RpgFarmMode = game["mode"]
	var calendar: RpgCalendar = game["calendar"]
	var day_end: RpgDayEnd = game["day_end"]
	var fight: RpgFarmFight = game["fight"]
	var bed := RpgBed.new()
	bed.position = Vector2(100, 50)
	bed.wake_offset = Vector2(0, 8)
	var farmer := Node2D.new()
	farmer.position = Vector2(400, 300)
	_made.append(bed)
	_made.append(farmer)
	day_end.farmer = farmer
	bed.remember()
	calendar.pass_minutes(8 * 60)  # 14:00
	var day := calendar.day
	state.gold = 200
	mode.energy.value = 90
	state.player_stats.hp = 0
	var downs: Array[bool] = []
	fight.knocked_out.connect(func() -> void: downs.append(true))
	t.ok(fight.begin_down(), "what the health's `died` does first; the day ends a moment later")
	t.ok(not fight.begin_down(), "once")
	t.ok(fight.down and downs.size() == 1, "the farmer lies down")
	t.ok(day_end.pass_out(), "what follows the moment: the day ends")
	t.eq(calendar.day, day + 1, "at 14:00, as at 2:00")
	t.eq(day_end.last_night, RpgDayEnd.PASSED_OUT)
	t.ok(day_end.knocked_out, "and it says why")
	t.eq(mode.energy.value, 50, "half the energy")
	t.eq([state.gold, day_end.money_lost], [180, 20], "a tenth of the money")
	t.eq(farmer.position, Vector2(100, 58), "at the bed")
	t.eq(state.player_stats.hp, RpgUtil.max_hp(state.player_stats), "the morning heals")
	t.ok(not fight.down)
	calendar.pass_minutes(RpgCalendar.DAY_MINUTES)
	t.ok(not day_end.knocked_out, "a night at 2:00 is no defeat")
	_cleanup()
