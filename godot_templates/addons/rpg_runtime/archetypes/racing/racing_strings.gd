class_name RpgRacingStrings
extends RefCounted
## Translation keys of the racing game with their English text. The translations recipe adds
## them to game/i18n/strings.tsv when the project is a racing game, beside the arcade keys.

const KEYS := {
	"RACE_SPEED": "Speed: %d",
	"RACE_BOOSTS": "Boosts: %d",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)
