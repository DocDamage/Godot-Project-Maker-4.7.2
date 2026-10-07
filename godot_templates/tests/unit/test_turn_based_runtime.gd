extends RefCounted
## The turn-based archetype around the battle: overworld enemies, the combat mode, text, recipes
## helpers (T7.01 to T7.04).

const Fixtures := preload("../lib/fixtures.gd")
const EnemyRecipes := preload("res://builder/recipes/turn_based/enemy_recipes.gd")
const ARCH_DIR := "res://addons/rpg_runtime/archetypes/turn_based"

func _scripts(dir_path: String) -> Array[String]:
	var out: Array[String] = []
	var dir := DirAccess.open(dir_path)
	for f in dir.get_files():
		if f.ends_with(".gd"):
			out.append(dir_path + "/" + f)
	for d in dir.get_directories():
		out.append_array(_scripts(dir_path + "/" + d))
	return out

func test_every_archetype_script_parses(t) -> void:
	var paths := _scripts(ARCH_DIR)
	t.ok(paths.size() >= 17, "found %d scripts" % paths.size())
	for path in paths:
		var script := load(path) as GDScript
		t.ok(script != null and script.can_instantiate(), path)

func test_battle_text_falls_back_to_english_and_formats(t) -> void:
	t.eq(RpgBattleText.t("BATTLE_ATTACK"), "Attack")
	t.eq(RpgBattleText.t("BATTLE_ATTACK_HIT", ["Hero", "Slime", 7]), "Hero attacks Slime for 7 damage.")
	t.eq(RpgBattleText.t("NOT_A_KEY"), "NOT_A_KEY")
	for key in RpgBattleStrings.KEYS.keys():
		t.ok(String(key).begins_with("BATTLE_"), key)
		t.ok(String(RpgBattleStrings.KEYS[key]) != "", key)

func test_item_names(t) -> void:
	var def := Fixtures.item(&"potion")
	def.display_name = "ITEM_POTION_NAME"
	t.eq(RpgBattleText.item_name(def, &"potion"), "Potion", "an untranslated key falls back to the id")
	def.display_name = "Healing Draught"
	t.eq(RpgBattleText.item_name(def, &"potion"), "Healing Draught")
	t.eq(RpgBattleText.item_name(null, &"magic_herb"), "Magic Herb")

func test_standard_commands_load_in_order(t) -> void:
	var commands := RpgBattleController.load_commands()
	var ids: Array = []
	for c in commands:
		ids.append(String(c.id))
	t.eq(ids, ["attack", "defend", "item", "skill", "run"])
	t.eq(commands[1].priority, 10, "defend acts first")
	t.eq(commands[1].targets, RpgBattleCommand.TARGET_SELF)
	t.eq(commands[0].targets, RpgBattleCommand.TARGET_ONE_ENEMY)
	t.eq(commands[2].targets, RpgBattleCommand.TARGET_ONE_ALLY)

func test_overworld_enemy_builds_its_encounter(t) -> void:
	var enemy := RpgOverworldEnemy.new()
	enemy.entity_id = "map_enemy_001"
	var slime := RpgEnemyDefinition.new()
	slime.id = &"slime"
	enemy.definition = slime
	var data := enemy.build_encounter()
	t.eq(data.entity_id, "map_enemy_001")
	t.eq(data.enemies.size(), 1)
	t.ok(data.enemies[0] == slime)
	t.eq(data.can_escape, true)
	var bat := RpgEnemyDefinition.new()
	enemy.group.assign([slime, bat])
	enemy.can_escape = false
	data = enemy.build_encounter()
	t.eq(data.enemies.size(), 2, "the group replaces the single definition")
	t.eq(data.can_escape, false)
	enemy.free()

func test_escape_grace_counts_down(t) -> void:
	var enemy := RpgOverworldEnemy.new()
	t.ok(not enemy.is_in_grace())
	enemy.grant_grace(1.5)
	t.ok(enemy.is_in_grace())
	enemy.grant_grace(0.5)
	t.ok(enemy._grace == 1.5, "a shorter grace never shortens a longer one")
	enemy.free()

func test_combat_mode_without_a_router_refuses_quietly(t) -> void:
	var mode := RpgTurnBasedMode.new()
	t.ok(not mode.is_in_combat())
	t.eq(RpgTurnBasedMode.latest_save_slot(), -1, "no SaveManager, no slot")
	t.ok(RpgTurnBasedMode.find_entity("anything") == null)
	mode.free()

func test_the_mode_is_a_combat_mode(t) -> void:
	var mode := RpgTurnBasedMode.new()
	t.ok(mode is RpgCombatMode)
	t.eq(mode.battle_scene_path, "res://generated/scenes/battle/battle.tscn")
	mode.free()

func test_target_cursor_blinks_only_while_pointing(t) -> void:
	var cursor := RpgTargetCursor.new()
	t.ok(not cursor.is_pointing())
	cursor.point_at(Vector2(10, 20))
	t.ok(cursor.is_pointing() and cursor.visible)
	t.eq(cursor.position, Vector2(10, 20))
	cursor.hide_cursor()
	t.ok(not cursor.is_pointing() and not cursor.visible)
	cursor.free()

# ---------------------------------------------------------------- enemy recipe helpers

func test_enemy_stats_scale_with_the_index(t) -> void:
	t.eq(EnemyRecipes.scaled(0), {"hp": 12, "attack": 4, "defense": 1, "xp": 5, "gold": 3})
	t.eq(EnemyRecipes.scaled(1), {"hp": 16, "attack": 5, "defense": 1, "xp": 7, "gold": 4})
	t.eq(EnemyRecipes.scaled(2), {"hp": 20, "attack": 6, "defense": 2, "xp": 9, "gold": 5})
	t.eq(EnemyRecipes.scaled(5), {"hp": 32, "attack": 9, "defense": 3, "xp": 15, "gold": 8})

func test_enemy_slugs_are_short_unless_they_clash(t) -> void:
	t.eq(EnemyRecipes.slugs_for(["pack.enemies.slime", "pack.enemies.bat"]), ["slime", "bat"])
	t.eq(EnemyRecipes.slugs_for(["a.enemies.slime", "b.enemies.slime", "a.enemies.bat"]), ["a__enemies__slime", "b__enemies__slime", "bat"])
	t.eq(EnemyRecipes.slugs_for(["pack.sheet#c1"]), ["sheet_c1"])

func test_enemy_display_names_drop_animation_words(t) -> void:
	t.eq(EnemyRecipes.display_name("slime_idle"), "Slime")
	t.eq(EnemyRecipes.display_name("fire_bat_sheet"), "Fire Bat")
	t.eq(EnemyRecipes.display_name("idle"), "Idle", "a lone word is kept")
