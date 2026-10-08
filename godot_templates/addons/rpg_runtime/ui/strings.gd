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
	"UI_VOLUME_MASTER": "Master volume",
	"UI_VOLUME_MUSIC": "Music volume",
	"UI_VOLUME_SFX": "Effects volume",
	"UI_VOLUME_UI": "Interface volume",
	"UI_FULLSCREEN": "Fullscreen",
	"UI_TEXT_SPEED": "Text speed",
	"UI_UI_SCALE": "Interface size",
	"UI_CONTROLS": "Controls",
	"UI_PRESS_KEY": "Press a key…",
	"UI_SPEED_SLOW": "Slow",
	"UI_SPEED_NORMAL": "Normal",
	"UI_SPEED_FAST": "Fast",
	"UI_SPEED_INSTANT": "Instant",
	"UI_LEVEL": "Level",
	"UI_HP": "HP",
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
}

## English text of a key (the key itself when unknown).
static func english(key: String) -> String:
	return KEYS.get(key, key)

## The translation key of an input action ("UI_ACTION_<NAME>") when it has one, else the action name.
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
