class_name RpgRunAndGunStrings
extends RefCounted
## Translation keys of the run and gun with their English text. The translations recipe adds
## them to game/i18n/strings.tsv when the project is a run and gun, beside the arcade keys.

const KEYS := {
	"RNG_GRENADES": "Grenades: %d",
	"RNG_HEALTH": "Health: %d",
	"RNG_WEAPON_MACHINE_GUN": "Machine gun",
	"RNG_WEAPON_SPREAD": "Spread",
	"RNG_WEAPON_LASER": "Laser",
	"RNG_WEAPON_FLAME": "Flame",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)

## The name of a weapon.
static func weapon_name(weapon: String) -> String:
	return t("RNG_WEAPON_" + weapon.to_upper())
