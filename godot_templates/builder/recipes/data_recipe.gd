extends RefCounted
## Seeds the data files of the demo under game/data/ (user_seed: written once, never again):
## hero actor, new-game data, the potion item and the starter NPC's dialogue.

const RECIPE_VERSION := 3

const Paths := preload("../lib/paths.gd")
const SeedUtil := preload("../lib/seed_util.gd")
const TextureUtil := preload("../lib/texture_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const HERO_PATH := "res://game/data/actors/hero.tres"
const NEW_GAME_PATH := "res://game/data/new_game.tres"
const POTION_PATH := "res://game/data/items/potion.tres"
const GREETING_PATH := "res://game/data/dialogue/npc_greeting.tres"
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

## English text of the seeded content keys (the translations recipe adds them to strings.csv).
const SEED_STRINGS := {
	"ITEM_POTION_NAME": "Potion",
	"ITEM_POTION_DESC": "Restores 10 HP.",
	"ITEM_SWORD_NAME": "Sword",
	"ITEM_SWORD_DESC": "A plain blade. Attack +2.",
	"ITEM_AXE_NAME": "Axe",
	"ITEM_AXE_DESC": "A woodsman's axe. Attack +2.",
	"ITEM_BOW_NAME": "Bow",
	"ITEM_BOW_DESC": "A short bow. Attack +2.",
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
	if not ctx.demo_removed:
		wanted.append(GREETING_PATH)
		wanted.append(SHOP_PATH)
	return SeedUtil.missing(wanted)

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "icon": _icon_asset(ctx).get("id", ""), "player": _player_id(ctx), "demo_removed": ctx.demo_removed, "gear": _gear(ctx)})

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
		_save(ctx, _hero(ctx), HERO_PATH, issues)
	if not FileAccess.file_exists(NEW_GAME_PATH):
		_save(ctx, _new_game(ctx.demo_removed, gear.keys()), NEW_GAME_PATH, issues)
	if not FileAccess.file_exists(POTION_PATH):
		_save(ctx, _potion(ctx), POTION_PATH, issues)
	if not ctx.demo_removed and not FileAccess.file_exists(GREETING_PATH):
		_save(ctx, _greeting(), GREETING_PATH, issues)
	if not ctx.demo_removed and not FileAccess.file_exists(SHOP_PATH):
		_save(ctx, _shop(gear.keys()), SHOP_PATH, issues)
	return issues

func _save(ctx: BuildContext, res: Resource, path: String, issues: Array) -> void:
	var err := SeedUtil.save(res, path)
	if err != OK:
		issues.append(ctx.make_issue("BUILD-004", {"file": path, "err": err}, path))

func _hero(ctx: BuildContext) -> Resource:
	var def := SeedUtil.make(ACTOR_DEF)
	def.set("id", &"hero")
	def.set("display_name", "Hero")
	var stats := SeedUtil.make(STATS)
	def.set("base_stats", stats)
	var pid := _player_id(ctx)
	if pid != "":
		var frames_path: String = Paths.SPRITE_FRAMES_DIR + "%s.tres" % pid
		if ResourceLoader.exists(frames_path):
			def.set("sprite_frames", load(frames_path))
	return def

func _new_game(demo_removed: bool = false, gear_words: Array = []) -> Resource:
	var ng := SeedUtil.make(NEW_GAME)
	ng.set("start_map", "res://game/maps/starter_map.tscn")
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

## The village shop: potions and the starter gear, at their item values.
func _shop(gear_words: Array) -> Resource:
	var shop := SeedUtil.make(SHOP_DEF)
	shop.set("id", StringName(SHOP_ID))
	shop.set("title", "UI_SHOP")
	var stock: Array = [{"item_id": "potion", "price": -1}]
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
func _greeting() -> Resource:
	var res := SeedUtil.make(DLG_RES)
	var lines: Array = [
		_line("greet", "Villager", "Hello, traveler! Welcome to our village.", "", "", [], []),
		_line("ask", "Villager", "Is there anything I can help you with?", "", "", [], [["Any tips?", "tips"], ["Show me your wares", "shop", "flag:starter_npc.talked"], ["Bye", "bye"]]),
		_line("tips", "Villager", "Take this potion. Walk into the house to see inside, and open the chest nearby.", "bye", "not flag:starter_npc.talked", ["set_flag:starter_npc.talked=true", "give_item:potion:1"], []),
		_line("tips_again", "Villager", "I have already told you everything I know.", "bye", "flag:starter_npc.talked", [], []),
		_line("shop", "Villager", "Take a look at what I have.", "bye", "", ["open_shop:" + SHOP_ID], []),
		_line("bye", "Villager", "Safe travels!", "", "", [], []),
	]
	var res_lines: Array = res.get("lines")
	res_lines.assign(lines)
	return res
