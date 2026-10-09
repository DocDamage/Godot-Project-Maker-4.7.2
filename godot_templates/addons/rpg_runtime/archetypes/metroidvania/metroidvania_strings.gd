class_name RpgMetroidvaniaStrings
extends RefCounted
## Translation keys of the metroidvania archetype with their English text. The translations recipe
## adds them to game/i18n/strings.tsv when the project's archetype is metroidvania.

const KEYS := {
	"MV_ITEM_GAINED": "Picked up %s x%d",
	"MV_GOLD_GAINED": "+%d gold",
	"MV_LEVEL_UP": "Level %d!",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)
