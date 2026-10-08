extends RefCounted
## Seeds the data files of the demo under game/data/ (user_seed: written once, never again):
## hero actor, new-game data, the potion item and the starter NPC's dialogue.

const RECIPE_VERSION := 1

const Paths := preload("../lib/paths.gd")
const SeedUtil := preload("../lib/seed_util.gd")
const TextureUtil := preload("../lib/texture_util.gd")
const JsonUtil := preload("../lib/json_util.gd")
const BuildContext := preload("../lib/build_context.gd")

const HERO_PATH := "res://game/data/actors/hero.tres"
const NEW_GAME_PATH := "res://game/data/new_game.tres"
const POTION_PATH := "res://game/data/items/potion.tres"
const GREETING_PATH := "res://game/data/dialogue/npc_greeting.tres"

const STATS := "res://addons/rpg_runtime/data/stats.gd"
const ACTOR_DEF := "res://addons/rpg_runtime/data/actor_definition.gd"
const NEW_GAME := "res://addons/rpg_runtime/data/new_game_data.gd"
const ITEM_DEF := "res://addons/rpg_runtime/data/item_definition.gd"
const DLG_RES := "res://addons/rpg_runtime/dialogue/dialogue_resource.gd"
const DLG_LINE := "res://addons/rpg_runtime/dialogue/dialogue_line.gd"
const DLG_CHOICE := "res://addons/rpg_runtime/dialogue/dialogue_choice.gd"

## English text of the seeded content keys (the translations recipe adds them to strings.csv).
const SEED_STRINGS := {
	"ITEM_POTION_NAME": "Potion",
	"ITEM_POTION_DESC": "Restores 10 HP.",
}

func outputs(ctx: BuildContext) -> PackedStringArray:
	# Without the demo there is no NPC to greet the player.
	if ctx.demo_removed:
		return SeedUtil.missing([HERO_PATH, NEW_GAME_PATH, POTION_PATH])
	return SeedUtil.missing([HERO_PATH, NEW_GAME_PATH, POTION_PATH, GREETING_PATH])

func input_hash(ctx: BuildContext) -> String:
	return ctx.stable_hash({"v": RECIPE_VERSION, "icon": _icon_asset(ctx).get("id", ""), "player": _player_id(ctx), "demo_removed": ctx.demo_removed})

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

func build(ctx: BuildContext) -> Array:
	var issues: Array = []
	if not FileAccess.file_exists(HERO_PATH):
		_save(ctx, _hero(ctx), HERO_PATH, issues)
	if not FileAccess.file_exists(NEW_GAME_PATH):
		_save(ctx, _new_game(ctx.demo_removed), NEW_GAME_PATH, issues)
	if not FileAccess.file_exists(POTION_PATH):
		_save(ctx, _potion(ctx), POTION_PATH, issues)
	if not ctx.demo_removed and not FileAccess.file_exists(GREETING_PATH):
		_save(ctx, _greeting(), GREETING_PATH, issues)
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

func _new_game(demo_removed: bool = false) -> Resource:
	var ng := SeedUtil.make(NEW_GAME)
	ng.set("start_map", "res://game/maps/starter_map.tscn")
	ng.set("start_spawn", &"default")
	ng.set("gold", 50)
	ng.set("items", SeedUtil.dict_array([] if demo_removed else [{"item_id": "potion", "qty": 2}]))
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
		_line("ask", "Villager", "Is there anything I can help you with?", "", "", [], [["Any tips?", "tips"], ["Bye", "bye"]]),
		_line("tips", "Villager", "Take this potion. Walk into the house to see inside, and open the chest nearby.", "bye", "not flag:starter_npc.talked", ["set_flag:starter_npc.talked=true", "give_item:potion:1"], []),
		_line("tips_again", "Villager", "I have already told you everything I know.", "bye", "flag:starter_npc.talked", [], []),
		_line("bye", "Villager", "Safe travels!", "", "", [], []),
	]
	var res_lines: Array = res.get("lines")
	res_lines.assign(lines)
	return res
