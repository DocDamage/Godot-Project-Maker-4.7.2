class_name RpgShmupStrings
extends RefCounted
## Translation keys of the shoot-em-up with their English text. The translations recipe adds
## them to game/i18n/strings.tsv when the project is a shoot-em-up, beside the arcade keys.

const KEYS := {
	"SHM_BOMBS": "Bombs: %d",
	"SHM_WEAPON": "%s Lv %d",
	"SHM_WEAPON_STRAIGHT": "Shot",
	"SHM_WEAPON_SPREAD": "Spread",
	"SHM_WEAPON_LASER": "Laser",
	"SHM_WEAPON_HOMING": "Homing",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)

## The name of a weapon kind.
static func weapon_name(kind: String) -> String:
	return t("SHM_WEAPON_" + kind.to_upper())
