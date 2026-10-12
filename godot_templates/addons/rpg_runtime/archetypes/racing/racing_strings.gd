class_name RpgRacingStrings
extends RefCounted
## Translation keys of the racing game with their English text. The translations recipe adds
## them to game/i18n/strings.tsv when the project is a racing game, beside the arcade keys.

const KEYS := {
	"RACE_SPEED": "Speed: %d",
	"RACE_BOOSTS": "Boosts: %d",
	"RACE_LAP": "Lap %d/%d",
	"RACE_PLACE": "Place %d/%d",
	"RACE_WEAPON": "Weapon: %s",
	"RACE_SHIELD": "Shield",
	"RACE_WRONG_WAY": "Wrong way!",
	"RACE_COUNT": "%d",
	"RACE_GO": "Go!",
	"RACE_FINISHED": "Finished: place %d",
	"RACE_ITEM_MISSILE": "Missile",
	"RACE_ITEM_BOMB": "Bomb",
	"RACE_POINTS": "Points: %d",
	"RACE_LAST": "Last place: %d/%d",
	"RACE_RESULTS": "%s: results",
	"RACE_THIS_RACE": "Race",
	"RACE_TABLE": "Championship",
	"RACE_CHAMPION": "Champion: %s",
	"RACE_ELIMINATED": "Last twice: you are out",
	"RACE_PARTS_WON": "Parts won: %s",
	"RACE_PART_SPEED": "Speed",
	"RACE_PART_TYRES": "Tyres",
	"RACE_PART_ACCELERATION": "Acceleration",
	"RACE_DRIVER_YOU": "You",
	"RACE_DRIVER_RIVAL": "Rival %d",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)
