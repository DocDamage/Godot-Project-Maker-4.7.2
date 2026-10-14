class_name RpgFarmCaveStrings
extends RefCounted
## Translation keys of a farm that fights (T17.24) with their English text. The translations
## recipe adds them to game/i18n/strings.tsv for a farm that fights only, so that the strings of
## a farm that does not are what they were; the English text is the fallback everywhere else.

const KEYS := {
	"ITEM_FARM_SWORD_NAME": "Sword",
	"ITEM_FARM_SWORD_DESC": "Hold it and press Use to swing it. For the cave.",
	"FARM_KNOCKED_OUT": "You were knocked out and woke up at home.",
	"FARM_KNOCKED_OUT_LOST": "You were knocked out and woke up at home. %d %s is gone.",
	"FARM_CAVE_LEFT": "The %s left %s.",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)
