class_name RpgStrings
extends RefCounted
## Every UI string key in one place. The translations recipe writes game/i18n/strings.csv and the
## English Translation resource from this table. Use tr("UI_...") in scripts.

const KEYS := {
	"UI_NEW_GAME": "New Game",
	"UI_CONTINUE": "Continue",
	"UI_LOAD": "Load",
	"UI_SAVE": "Save",
	"UI_SETTINGS": "Settings",
	"UI_QUIT": "Quit",
	"UI_RESUME": "Resume",
	"UI_INVENTORY": "Inventory",
	"UI_STATUS": "Status",
	"UI_TITLE": "Title",
	"UI_BACK": "Back",
	"UI_USE": "Use",
	"UI_GOLD": "Gold",
	"UI_EMPTY": "Empty",
	"UI_SLOT": "Slot",
	"UI_NO_ITEMS": "No items",
	"UI_SELECT_ITEM": "Select an item",
	"UI_HINT_SELECT": "Select",
	"UI_HINT_CONFIRM": "Confirm",
	"UI_HINT_CHOOSE": "Choose",
	"UI_HINT_NEXT": "Next",
	"UI_VOLUME_MASTER": "Master volume",
	"UI_VOLUME_MUSIC": "Music volume",
	"UI_VOLUME_SFX": "Effects volume",
	"UI_VOLUME_UI": "Interface volume",
	"UI_FULLSCREEN": "Fullscreen",
	"UI_TEXT_SPEED": "Text speed",
	"UI_LANGUAGE": "Language",
	"UI_DAY_NIGHT": "Day and night",
	"UI_MINIMAP": "Minimap",
	"UI_QUEST_TRACKER": "Quest tracker",
	"UI_WORLD_MAP": "Map",
	"UI_NO_MAPS_YET": "No map seen yet",
	"UI_LANGUAGE_SYSTEM": "System",
	"UI_UI_SCALE": "Interface size",
	"UI_CONTROLS": "Controls",
	"UI_PRESS_KEY": "Press a key…",
	"UI_SPEED_SLOW": "Slow",
	"UI_SPEED_NORMAL": "Normal",
	"UI_SPEED_FAST": "Fast",
	"UI_SPEED_INSTANT": "Instant",
	"UI_LEVEL": "Level",
	"UI_HP": "HP",
	"UI_MP": "MP",
	"UI_XP": "Experience",
	"UI_ATTACK": "Attack",
	"UI_DEFENSE": "Defense",
	"UI_SPEED": "Speed",
	"UI_MAGIC": "Magic",
	"UI_RESISTANCE": "Resistance",
	"UI_GAME_OVER_TITLE": "You were defeated",
	"UI_GAME_OVER_CONTINUE": "Continue from last save",
	"UI_GAME_OVER_RETRY": "Try again from the start of the map",
	"UI_GAME_OVER_QUIT": "Quit to title",
	"UI_SCREEN_SHAKE": "Screen shake",
	"UI_AUTOSAVED": "Saved",
	"UI_AUTOSAVE": "Autosave",
	"UI_GAME_SAVED": "Game saved",
	"UI_SAVE_FAILED": "Saving failed",
	"UI_LOAD_FAILED": "Loading failed",
	"UI_SAVE_DAMAGED_LOADED_BACKUP": "Save was damaged; loaded backup.",
	"UI_SAVE_FROM_NEWER_VERSION": "Save from newer version",
	"UI_CANNOT_USE_NOW": "Cannot use that now",
	"UI_CHEST_FOUND": "Found %s",
	"UI_CHEST_EMPTY": "The chest is empty",
	"UI_PLAYTIME": "Playtime",
	"UI_ACTION_MOVE_UP": "Move up",
	"UI_ACTION_MOVE_DOWN": "Move down",
	"UI_ACTION_MOVE_LEFT": "Move left",
	"UI_ACTION_MOVE_RIGHT": "Move right",
	"UI_ACTION_INTERACT": "Interact",
	"UI_ACTION_CONFIRM": "Confirm",
	"UI_ACTION_CANCEL": "Cancel",
	"UI_ACTION_MENU": "Menu",
	"UI_ACTION_ATTACK": "Attack",
	"UI_ACTION_DODGE": "Dodge",
	"UI_LV": "Lv",
	"UI_PLAYED": "played",
	"UI_OVERWRITE_SAVE": "Overwrite this save?",
	"UI_YES": "Yes",
	"UI_NO": "No",
	"UI_MONTH_1": "Jan",
	"UI_MONTH_2": "Feb",
	"UI_MONTH_3": "Mar",
	"UI_MONTH_4": "Apr",
	"UI_MONTH_5": "May",
	"UI_MONTH_6": "Jun",
	"UI_MONTH_7": "Jul",
	"UI_MONTH_8": "Aug",
	"UI_MONTH_9": "Sep",
	"UI_MONTH_10": "Oct",
	"UI_MONTH_11": "Nov",
	"UI_MONTH_12": "Dec",
	"UI_EQUIP": "Equip",
	"UI_EQUIPMENT": "Equipment",
	"UI_TAKE_OFF": "Take off",
	"UI_SLOT_WEAPON": "Weapon",
	"UI_SLOT_ARMOR": "Armor",
	"UI_SLOT_ACCESSORY": "Accessory",
	"UI_NO_CHANGE": "No change",
	"UI_NOTHING_TO_EQUIP": "Nothing to wear here",
	"UI_CANNOT_EQUIP": "Cannot equip that",
	"UI_MOVE_SPEED": "Move speed",
	"UI_SHOP": "Shop",
	"UI_BUY": "Buy",
	"UI_SELL": "Sell",
	"UI_GOLD_SHORT": "G",
	"UI_BOUGHT": "Bought %s",
	"UI_SOLD": "Sold %s",
	"UI_NOT_ENOUGH_GOLD": "Not enough gold",
	"UI_NO_ROOM": "No room in the bag",
	"UI_CANNOT_TRADE": "Cannot do that",
	"UI_NOTHING_FOR_SALE": "Nothing for sale",
	"UI_NOTHING_TO_SELL": "Nothing to sell",
	"UI_SHOP_QUANTITY_HINT": "Left / right: how many",
	"UI_SELL_ALL": "Sell all",
	"UI_BUYBACK": "Buy back",
	"UI_NOTHING_TO_BUY_BACK": "Nothing to buy back",
	"UI_SOLD_OUT": "Sold out",
	"UI_SHOP_LEFT": "%d left",
	"UI_SHOP_FUNDS": "Shop's gold",
	"UI_SHOP_CANNOT_PAY": "The shop cannot pay that much",
	"UI_SELL_ALL_CONFIRM": "Sell everything for %d G? Press again",
	"UI_SOLD_ALL": "Sold everything for %d G",
	"UI_JOURNAL": "Journal",
	"UI_QUESTS_ACTIVE": "Active",
	"UI_QUESTS_DONE": "Completed",
	"UI_NO_QUESTS_ACTIVE": "No active quests",
	"UI_NO_QUESTS_DONE": "No completed quests",
	"UI_QUEST_NEW": "New quest: %s",
	"UI_QUEST_UPDATED": "Quest updated: %s",
	"UI_QUEST_DONE": "Quest complete: %s",
	"UI_QUEST_FAILED": "Quest failed: %s",
	"UI_SKILLS": "Skills",
	"UI_SKILL_POINTS": "Points: %d",
	"UI_LEARN": "Learn",
	"UI_UNLEARN": "Unlearn",
	"UI_RESET": "Reset",
	"UI_RESET_COST": "Reset (%d G)",
	"UI_RANK": "rank %d/%d",
	"UI_SKILL_NEEDS": "Needs %s",
	"UI_ROW_LOCKED": "Opens after %d points in the rows above",
	"UI_ROW_LOCKED_SHORT": "That row is not open yet",
	"UI_NO_POINTS": "Not enough points",
	"UI_MAX_RANK": "Fully learned",
	"UI_SKILL_NEEDED": "Another skill needs it",
	"UI_SKILL_NOT_LEARNED": "Not learned",
	"UI_SKILL_LEARNED": "Learned: %s",
	"UI_NO_SKILL_TREES": "No skills to learn",
	"UI_ACHIEVEMENTS": "Achievements",
	"UI_ACHIEVEMENT_UNLOCKED": "Achievement unlocked: %s",
	"UI_ACHIEVEMENTS_TOTAL": "%d of %d unlocked · %d points",
	"UI_SECRET": "???",
	"UI_NO_ACHIEVEMENTS": "No achievements",
	"UI_ITEM_WAITING": "No room in the bag: %s will wait for you",
	"UI_ITEM_DELIVERED": "%s put in your bag",
	"UI_ITEM_BROKE": "%s broke",
	"UI_WEAR": "Wear %d/%d",
	"UI_SET_BONUS": "Set %s: %d worn",
	"UI_QUEST_READY": "Ready to turn in",
	"UI_QUEST_FAILED_MARK": "(failed)",
	"UI_QUEST_TRACKED": "Tracked",
	"UI_CREDITS": "Credits",
	"UI_CREDITS_ASSETS": "Art and sound",
	"UI_CREDITS_ENGINE": "Engine",
	"UI_CREDITS_BY": "%s by %s",
	"UI_USE_ON": "Use on",
	"UI_PARTY_JOINED": "%s joined the party",
	"UI_WORLD_OVERVIEW": "World",
	"UI_PARTY_LEFT": "%s left the party",
	"UI_LOCKED": "It will not open.",
	"UI_LOCKED_NEED": "Locked. It needs: %s",
	"UI_UNLOCKED": "Unlocked with: %s",
	"UI_NEEDS_ABILITY": "You cannot get past this yet.",
	"UI_SAVE_AT_STATION": "Save at a station",
}

## English text of a key (the key itself when unknown).
static func english(key: String) -> String:
	return KEYS.get(key, key)

## The translation key of an input action ("UI_ACTION_<NAME>") when it has one, else the action name.
## The translated text of `key` formatted with `arg`; the English text when no translation has
## the key (the editor, a test). A translation without "%s" is shown as it is.
static func format(key: String, arg: Variant) -> String:
	var text := String(TranslationServer.translate(key))
	if text == key:
		text = english(key)
	return text % [arg] if text.contains("%") else text

static func action_label(action: String) -> String:
	var key := "UI_ACTION_" + action.to_upper()
	return key if KEYS.has(key) else action

const TRANSLATIONS_DIR := "res://generated/i18n"

## Adds the generated Translation resources to the TranslationServer. Called once by boot.
## (Registering .tres translations in the project settings fails at engine start-up, so the
## runtime does it.)
static func register_translations() -> int:
	var dir := DirAccess.open(TRANSLATIONS_DIR)
	if dir == null:
		return 0
	var files := dir.get_files()
	files.sort()
	var added := 0
	for f in files:
		var name := f.trim_suffix(".remap")
		if not name.ends_with(".tres"):
			continue
		var t := load(TRANSLATIONS_DIR + "/" + name) as Translation
		if t != null:
			TranslationServer.add_translation(t)
			added += 1
	_add_missing_defaults()
	return added

## The locales the project has a translation for (the columns of game/i18n/strings.tsv),
## sorted. The settings menu offers them, plus "System".
static func locales(folder: String = TRANSLATIONS_DIR) -> PackedStringArray:
	var found: PackedStringArray = []
	var dir := DirAccess.open(folder)
	if dir == null:
		return found
	for f in dir.get_files():
		var file_name := f.trim_suffix(".remap")
		if not file_name.ends_with(".tres"):
			continue
		var t := load(folder + "/" + file_name) as Translation
		if t != null and t.locale != "" and not found.has(t.locale):
			found.append(t.locale)
	found.sort()
	return found

## A project made before a key existed has no row for it in game/i18n/strings.tsv (the file is the
## user's and is never rewritten). Keys that no registered translation knows get their English
## text from KEYS, so new screens are not shown as raw keys.
static func _add_missing_defaults() -> void:
	var fallback := Translation.new()
	fallback.locale = "en"
	var any := false
	for key: String in KEYS.keys():
		if str(TranslationServer.translate(RpgUtil.to_name(key))) == key:
			fallback.add_message(RpgUtil.to_name(key), RpgUtil.to_name(KEYS[key]))
			any = true
	if any:
		TranslationServer.add_translation(fallback)
