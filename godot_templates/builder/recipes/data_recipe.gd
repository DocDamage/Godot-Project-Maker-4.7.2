extends RefCounted
## Seeds the data files of the demo under game/data/ (user_seed: written once, never again):
## hero actor, new-game data, the potion item and the starter NPC's dialogue.

const RECIPE_VERSION := 8

const Paths := preload("../lib/paths.gd")
const SeedUtil := preload("../lib/seed_util.gd")
const TextureUtil := preload("../lib/texture_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")
const MapBuild := preload("../lib/map_build.gd")
const ObjectEntries := preload("../lib/object_entries.gd")

const HERO_PATH := "res://game/data/actors/hero.tres"
const STARTER_MAP_PATH := "res://game/maps/starter_map.tscn"
const WORLD_PLAN_PATH := "res://rpggen/world_plan.json"
const COMPANION_ID := "companion"
const COMPANION_PATH := "res://game/data/actors/companion.tres"
const NEW_GAME_PATH := "res://game/data/new_game.tres"
const POTION_PATH := "res://game/data/items/potion.tres"
const ANTIDOTE_PATH := "res://game/data/items/antidote.tres"
const ETHER_PATH := "res://game/data/items/ether.tres"
const GREETING_PATH := "res://game/data/dialogue/npc_greeting.tres"
const QUEST_ID := "errand"
const QUEST_PATH := "res://game/data/quests/errand.tres"
const SHOP_ID := "village_shop"
const SHOP_PATH := "res://game/data/shops/village_shop.tres"

const STATS := "res://addons/rpg_runtime/data/stats.gd"
const ACTOR_DEF := "res://addons/rpg_runtime/data/actor_definition.gd"
const NEW_GAME := "res://addons/rpg_runtime/data/new_game_data.gd"
const ITEM_DEF := "res://addons/rpg_runtime/data/item_definition.gd"
const DLG_RES := "res://addons/rpg_runtime/dialogue/dialogue_resource.gd"
const DLG_LINE := "res://addons/rpg_runtime/dialogue/dialogue_line.gd"
const DLG_CHOICE := "res://addons/rpg_runtime/dialogue/dialogue_choice.gd"
const SHOP_DEF := "res://addons/rpg_runtime/data/shop_definition.gd"
const QUEST_DEF := "res://addons/rpg_runtime/data/quest_definition.gd"

## English text of the seeded content keys (the translations recipe adds them to strings.csv).
const SEED_STRINGS := {
	"ITEM_POTION_NAME": "Potion",
	"ITEM_POTION_DESC": "Restores 10 HP.",
	"ITEM_ANTIDOTE_NAME": "Antidote",
	"ITEM_ANTIDOTE_DESC": "Cures poison in battle.",
	"ITEM_ETHER_NAME": "Ether",
	"ITEM_ETHER_DESC": "Restores 10 MP.",
	"QUEST_ERRAND_TITLE": "The villager's errand",
	"QUEST_ERRAND_TALK": "Talk to the villager",
	"QUEST_ERRAND_CHEST": "Open the chest",
	"QUEST_ERRAND_RETURN": "Tell the villager about it",
	"ITEM_SWORD_NAME": "Sword",
	"ITEM_SWORD_DESC": "A plain blade. Attack +2.",
	"ITEM_AXE_NAME": "Axe",
	"ITEM_AXE_DESC": "A woodsman's axe. Attack +2.",
	"ITEM_BOW_NAME": "Bow",
	"ITEM_BOW_DESC": "A short bow. Attack +2. In an action RPG it shoots arrows.",
	"ITEM_ARMOR_NAME": "Armor",
	"ITEM_ARMOR_DESC": "Sturdy armor. Defense +2.",
	"ITEM_SHIELD_NAME": "Shield",
	"ITEM_SHIELD_DESC": "A wooden shield. Defense +2.",
	"ITEM_HELMET_NAME": "Helmet",
	"ITEM_HELMET_DESC": "A plain helmet. Defense +2.",
}

## The starter equipment: the first ITEM asset whose name contains one of the words becomes the
## starter weapon (sword, axe, bow) and the starter armor (armor, shield, helmet). Each gives +2 to
## one stat. The item id is the word.
const WEAPON_WORDS: Array[String] = ["sword", "axe", "bow"]
const ARMOR_WORDS: Array[String] = ["armor", "shield", "helmet"]
const GEAR_BONUS := 2

func outputs(ctx: BuildContext) -> PackedStringArray:
	# Without the demo there is no NPC to greet the player.
	var wanted: Array = [HERO_PATH, NEW_GAME_PATH, POTION_PATH]
	for word: String in _gear(ctx):
		wanted.append(_gear_path(word))
	if not ctx.demo_removed and not _no_village(ctx):
		wanted.append(GREETING_PATH)
		wanted.append(SHOP_PATH)
		wanted.append(QUEST_PATH)
		if _has_party_demo(ctx):
			wanted.append(COMPANION_PATH)
		if _turn_based(ctx):
			wanted.append(ANTIDOTE_PATH)
			wanted.append(ETHER_PATH)
	return SeedUtil.missing(wanted)

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "icon": _icon_asset(ctx).get("id", ""), "player": _player_id(ctx), "demo_removed": ctx.demo_removed, "gear": _gear(ctx), "chest": _has_chest(ctx), "party": _has_party_demo(ctx), "turn_based": _turn_based(ctx)}.merged({"start_map": _start_map(ctx)} if _no_village(ctx) else {}))

func _player_id(ctx: BuildContext) -> String:
	var players: Array = ctx.catalog.assets_by_role("PLAYER")
	return JsonUtil.to_str(players[0]["id"]) if not players.is_empty() else ""

## The ITEM asset that serves as the potion icon: one named potion, else the first ITEM sprite.
func _icon_asset(ctx: BuildContext) -> Dictionary:
	var first: Dictionary = {}
	for a in ctx.catalog.assets_by_role("ITEM"):
		var eff: Dictionary = ctx.catalog.effective(a)
		if a.get("status", "") in ["UNUSED", "MISSING"] or not ["sprite", "object"].has(eff.get("usage", "")):
			continue
		if JsonUtil.to_str(a["id"]).contains("potion"):
			return a
		if first.is_empty():
			first = a
	return first

func _gear_path(word: String) -> String:
	return "res://game/data/items/%s.tres" % word

## {word: asset} of the starter weapon and armor that the project's ITEM assets suggest.
func _gear(ctx: BuildContext) -> Dictionary:
	var out: Dictionary = {}
	for group: Array in [WEAPON_WORDS, ARMOR_WORDS]:
		for word: String in group:
			var found := _asset_named(ctx, word)
			if not found.is_empty():
				out[word] = found
				break
	return out

func _asset_named(ctx: BuildContext, word: String) -> Dictionary:
	for a in ctx.catalog.assets_by_role("ITEM"):
		var eff: Dictionary = ctx.catalog.effective(a)
		if a.get("status", "") in ["UNUSED", "MISSING"] or not ["sprite", "object"].has(eff.get("usage", "")):
			continue
		if (JsonUtil.to_str(a["id"]) + " " + JsonUtil.to_str(a.get("path", ""))).to_lower().contains(word):
			return a
	return {}

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	var gear := _gear(ctx)
	for word: String in gear:
		var asset: Dictionary = gear[word]
		if not FileAccess.file_exists(_gear_path(word)):
			_save(ctx, _gear_item(ctx, word, asset), _gear_path(word), issues)
	if not FileAccess.file_exists(HERO_PATH):
		_save(ctx, _hero(ctx, _turn_based(ctx)), HERO_PATH, issues)
	if not FileAccess.file_exists(NEW_GAME_PATH):
		_save(ctx, _new_game(ctx.demo_removed, gear.keys(), _start_map(ctx)), NEW_GAME_PATH, issues)
	if not FileAccess.file_exists(POTION_PATH):
		_save(ctx, _potion(ctx), POTION_PATH, issues)
	if _no_village(ctx):
		return issues  # no village: the rooms recipe seeds the sign and the hermit of the last room
	if not ctx.demo_removed and not FileAccess.file_exists(GREETING_PATH):
		_save(ctx, _greeting(_has_party_demo(ctx)), GREETING_PATH, issues)
	if _has_party_demo(ctx) and not FileAccess.file_exists(COMPANION_PATH):
		_save(ctx, _companion(ctx), COMPANION_PATH, issues)
	if not ctx.demo_removed and not FileAccess.file_exists(QUEST_PATH):
		_save(ctx, _quest(_has_chest(ctx)), QUEST_PATH, issues)
	if not ctx.demo_removed and not FileAccess.file_exists(SHOP_PATH):
		_save(ctx, _shop(gear.keys(), _turn_based(ctx)), SHOP_PATH, issues)
	if not ctx.demo_removed and _turn_based(ctx):
		for path: String in [ANTIDOTE_PATH, ETHER_PATH]:
			if not FileAccess.file_exists(path):
				_save(ctx, _battle_item(path == ANTIDOTE_PATH), path, issues)
	return issues

func _save(ctx: BuildContext, res: Resource, path: String, issues: Array) -> void:
	var err := SeedUtil.save(res, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

## With `skills` (turn-based) the hero has 6 MP, magic 1 and knows fire.
func _hero(ctx: BuildContext, skills: bool = false) -> Resource:
	var def := SeedUtil.make(ACTOR_DEF)
	def.set("id", &"hero")
	def.set("display_name", "Hero")
	var stats := SeedUtil.make(STATS)
	if skills:
		stats.set("magic", 1)
		stats.set("max_mp", 6)
		stats.set("mp", 6)
		def.set("skills", {"fire": 1})
	def.set("base_stats", stats)
	var pid := _player_id(ctx)
	if pid != "":
		var frames_path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % pid
		if ResourceLoader.exists(frames_path):
			def.set("sprite_frames", load(frames_path))
	return def

## A second character for the party (looks like the hero until the sprite is replaced). The
## villager's "join me" choice adds them with the event join_party:companion.
func _companion(ctx: BuildContext) -> Resource:
	var def := _hero(ctx)
	def.set("id", StringName(COMPANION_ID))
	def.set("display_name", "Mira")
	var stats := SeedUtil.make(STATS)
	stats.set("max_hp", 18)
	stats.set("hp", 18)
	stats.set("attack", 4)
	stats.set("defense", 2)
	stats.set("speed", 6)
	stats.set("magic", 3)
	stats.set("max_mp", 12)
	stats.set("mp", 12)
	def.set("base_stats", stats)
	def.set("skills", {"cure": 1, "sleep": 1, "fire": 3})
	return def

## A metroidvania (T14.06) has rooms instead of the village: none of the village's demo data
## (the villager's greeting, the shop, the errand, the companion) is seeded for it.
func _metroidvania(ctx: BuildContext) -> bool:
	return JsonUtil.to_str(ctx.config.get("archetype", "turn_based")) == "metroidvania"

## The arcade kinds (M16): a run through stages, the first of which is where a new game starts.
const ARCADE_KINDS: Array[String] = ["shmup", "run_and_gun", "racing"]
const FIRST_STAGE_PATH := "res://generated/scenes/stages/stage_01.tscn"

func _arcade(ctx: BuildContext) -> bool:
	return ARCADE_KINDS.has(JsonUtil.to_str(ctx.config.get("archetype", "turn_based")))

## True for a kind without the village: none of its demo data is seeded.
func _no_village(ctx: BuildContext) -> bool:
	return _metroidvania(ctx) or _arcade(ctx)

## Where a new game starts: the starter map, the start room of a metroidvania's stored plan, or
## the first stage of an arcade game.
func _start_map(ctx: BuildContext) -> String:
	if _arcade(ctx):
		return FIRST_STAGE_PATH
	if _metroidvania(ctx):
		var plan := JsonUtil.to_dict(JsonUtil.to_dict(JsonUtil.read(WORLD_PLAN_PATH) if FileAccess.file_exists(WORLD_PLAN_PATH) else {}).get("rooms", {}))
		for raw: Variant in JsonUtil.to_array(plan.get("list", [])):
			var room := JsonUtil.to_dict(raw)
			if JsonUtil.to_str(room.get("id", "")) == JsonUtil.to_str(plan.get("start", "")):
				return "res://" + JsonUtil.to_str(room.get("map", ""))
	return STARTER_MAP_PATH

func _new_game(demo_removed: bool = false, gear_words: Array = [], start_map: String = STARTER_MAP_PATH) -> Resource:
	var ng := SeedUtil.make(NEW_GAME)
	ng.set("start_map", start_map)
	ng.set("start_spawn", &"default")
	ng.set("gold", 50)
	var starting: Array = [] if demo_removed else [{"item_id": "potion", "qty": 2}]
	for word: String in gear_words:
		starting.append({"item_id": word, "qty": 1})
	ng.set("items", SeedUtil.dict_array(starting))
	return ng

func _potion(ctx: BuildContext) -> Resource:
	var item := SeedUtil.make(ITEM_DEF)
	item.set("id", &"potion")
	item.set("display_name", "ITEM_POTION_NAME")
	item.set("description", "ITEM_POTION_DESC")
	item.set("max_stack", 99)
	item.set("value", 10)
	item.set("use_effect", &"heal")
	item.set("effect_amount", 10)
	var icon := _icon_asset(ctx)
	if not icon.is_empty():
		var eff: Dictionary = ctx.catalog.effective(icon)
		var size: Array = eff.get("frame", eff.get("size", [16, 16]))
		item.set("icon", TextureUtil.region_texture("res://" + JsonUtil.to_str(icon["path"]), Rect2i(0, 0, JsonUtil.to_int(size[0]), JsonUtil.to_int(size[1]))))
	return item

## Skills, MP and the battle items are for the turn-based archetype.
func _turn_based(ctx: BuildContext) -> bool:
	return JsonUtil.to_str(ctx.config.get("archetype", "turn_based")) == "turn_based"

## The antidote (cures poison) or the ether (10 MP), sold in the village shop.
func _battle_item(antidote: bool) -> Resource:
	var item := SeedUtil.make(ITEM_DEF)
	var word := "antidote" if antidote else "ether"
	item.set("id", StringName(word))
	item.set("display_name", "ITEM_%s_NAME" % word.to_upper())
	item.set("description", "ITEM_%s_DESC" % word.to_upper())
	item.set("max_stack", 99)
	item.set("value", 8 if antidote else 20)
	if antidote:
		item.set("use_effect", &"cure")
		var cures: Array[StringName] = [&"poison"]
		item.set("cures", cures)
	else:
		item.set("use_effect", &"mp")
		item.set("effect_amount", 10)
	return item

## The party demo: a companion the villager can bring along. In a turn-based game she fights in
## the battles; in the action RPG she follows and helps on the map (T13.15).
func _has_party_demo(ctx: BuildContext) -> bool:
	return not ctx.demo_removed

## Whether the starter map gets a chest: the options allow one and the packs have something to use.
func _has_chest(ctx: BuildContext) -> bool:
	var options := MapBuild.merged_options(ctx.section("starter_map"), JsonUtil.to_str(ctx.config.get("archetype", "turn_based")))
	return JsonUtil.to_int(options["chests"]) >= 1 and not ObjectEntries.chest_entry(ctx).is_empty()

## Talk to the villager -> open the chest -> tell the villager (the chest stage only when the
## starter map has a chest). Each stage finishes by itself when
## its condition holds; the dialogue starts the quest and sets the last flag. A stage's "target"
## is the entity the minimap marks (T12.64).
func _quest(has_chest: bool = true) -> Resource:
	var quest := SeedUtil.make(QUEST_DEF)
	quest.set("id", StringName(QUEST_ID))
	quest.set("title", "QUEST_ERRAND_TITLE")
	var stages: Array = [{"id": "talk", "description": "QUEST_ERRAND_TALK", "complete_when": "flag:starter_npc.talked", "target": "starter_npc"}]
	if has_chest:  # a map without a chest would leave the quest stuck here
		stages.append({"id": "chest", "description": "QUEST_ERRAND_CHEST", "complete_when": "flag:starter_map_chest_001.opened", "target": "starter_map_chest_001"})
	stages.append({"id": "return", "description": "QUEST_ERRAND_RETURN", "complete_when": "flag:starter_npc.reported", "target": "starter_npc"})
	quest.set("stages", SeedUtil.dict_array(stages))
	quest.set("rewards", {"gold": 25, "experience": 5})
	return quest

## The village shop: potions (antidotes and ethers in a turn-based game) and the starter gear, at
## their item values.
func _shop(gear_words: Array, battle_items: bool = false) -> Resource:
	var shop := SeedUtil.make(SHOP_DEF)
	shop.set("id", StringName(SHOP_ID))
	shop.set("title", "UI_SHOP")
	var stock: Array = [{"item_id": "potion", "price": -1}]
	if battle_items:
		stock.append({"item_id": "antidote", "price": -1})
		stock.append({"item_id": "ether", "price": -1})
	for word: String in gear_words:
		stock.append({"item_id": word, "price": -1})
	shop.set("stock", SeedUtil.dict_array(stock))
	shop.set("sell_ratio", 0.5)
	return shop

func _gear_item(ctx: BuildContext, word: String, asset: Dictionary) -> Resource:
	var item := SeedUtil.make(ITEM_DEF)
	var is_weapon := WEAPON_WORDS.has(word)
	item.set("id", StringName(word))
	item.set("display_name", "ITEM_%s_NAME" % word.to_upper())
	item.set("description", "ITEM_%s_DESC" % word.to_upper())
	item.set("category", 1 if is_weapon else 2)  # RpgItemDefinition.Category.WEAPON / ARMOR
	item.set("max_stack", 1)
	item.set("value", 25)
	var mods: Array[Dictionary] = []
	mods.append({"stat": "attack" if is_weapon else "defense", "add": GEAR_BONUS, "mul": 1.0})
	item.set("modifiers", mods)
	item.set("ranged", word == "bow")
	var eff: Dictionary = ctx.catalog.effective(asset)
	var size: Array = eff.get("frame", eff.get("size", [16, 16]))
	item.set("icon", TextureUtil.region_texture("res://" + JsonUtil.to_str(asset["path"]), Rect2i(0, 0, JsonUtil.to_int(size[0]), JsonUtil.to_int(size[1]))))
	return item

func _line(line_id: String, speaker: String, text: String, next: String, condition: String, events: Array, choices: Array) -> Resource:
	var line := SeedUtil.make(DLG_LINE)
	line.set("id", StringName(line_id))
	line.set("speaker", speaker)
	line.set("text", text)
	line.set("next", StringName(next))
	line.set("condition", condition)
	line.set("events", PackedStringArray(events))
	var typed: Array = []
	for c: Array in choices:
		var choice := SeedUtil.make(DLG_CHOICE)
		choice.set("text", c[0])
		choice.set("next", JsonUtil.to_name(c[1]))
		if c.size() > 2:
			choice.set("condition", c[2])
		typed.append(choice)
	if not typed.is_empty():
		var line_choices: Array = line.get("choices")
		line_choices.assign(typed)
	return line

## A greeting, a choice ("Any tips?" / "Bye") and a branch that gives a potion the first time only.
## With `party_demo` the villager can also bring the companion along, and send them home again.
func _greeting(party_demo: bool = false) -> Resource:
	var res := SeedUtil.make(DLG_RES)
	var party_choices: Array = []
	var party_lines: Array = []
	if party_demo:
		var join_condition := "not party:" + COMPANION_ID
		party_choices = [["Would you like to travel with me?", "join", join_condition], ["You can stay here now.", "leave", "party:" + COMPANION_ID]]
		party_lines = [
			_line("join", "Villager", "Mira has been looking for an adventure. Take good care of her!", "bye", "", ["join_party:" + COMPANION_ID], []),
			_line("leave", "Villager", "Mira is welcome back at the village any time.", "bye", "", ["leave_party:" + COMPANION_ID], []),
		]
	var ask_choices: Array = [["Any tips?", "tips"], ["I opened the chest.", "report", "quest_stage:errand:return"], ["Show me your wares", "shop", "flag:starter_npc.talked"]]
	ask_choices.append_array(party_choices)
	ask_choices.append(["Bye", "bye"])
	var lines: Array = [
		_line("greet", "Villager", "Hello, traveler! Welcome to our village.", "", "", ["quest_start:" + QUEST_ID], []),
		_line("ask", "Villager", "Is there anything I can help you with?", "", "", [], ask_choices),
		_line("tips", "Villager", "Take this potion. Walk into the house to see inside, and open the chest nearby.", "bye", "not flag:starter_npc.talked", ["set_flag:starter_npc.talked=true", "give_item:potion:1"], []),
		_line("tips_again", "Villager", "I have already told you everything I know.", "bye", "flag:starter_npc.talked", [], []),
		_line("report", "Villager", "Wonderful! Take this for your trouble.", "bye", "", ["set_flag:starter_npc.reported=true"], []),
		_line("shop", "Villager", "Take a look at what I have.", "bye", "", ["open_shop:" + SHOP_ID], []),
	]
	lines.append_array(party_lines)  # before "bye": it has to stay the last line, or it would run on
	lines.append(_line("bye", "Villager", "Safe travels!", "", "", [], []))
	var res_lines: Array = res.get("lines")
	res_lines.assign(lines)
	return res
