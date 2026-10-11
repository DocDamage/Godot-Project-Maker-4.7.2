class_name RpgRunAndGunStrings
extends RefCounted
## Translation keys of the run and gun with their English text. The translations recipe adds
## them to game/i18n/strings.tsv when the project is a run and gun, beside the arcade keys.

const KEYS := {
	"RNG_GRENADES": "Grenades: %d",
	"RNG_HEALTH": "Health: %d",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)
