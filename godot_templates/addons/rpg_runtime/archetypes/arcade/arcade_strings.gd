class_name RpgArcadeStrings
extends RefCounted
## Translation keys of the arcade kinds (the shoot-em-up, the run and gun, the racing game) with
## their English text. The translations recipe adds them to game/i18n/strings.tsv for those kinds.

const KEYS := {
	"ARC_LIVES": "Lives",
	"ARC_SCORE": "Score",
	"ARC_MULTIPLIER": "x%d",
	"ARC_STAGE": "Stage %d",
	"ARC_STAGE_CLEAR": "Stage clear!",
	"ARC_TIME_BONUS": "Time bonus",
	"ARC_LIFE_BONUS": "Lives bonus",
	"ARC_TOTAL": "Total",
	"ARC_EXTRA_LIFE": "Extra life!",
	"ARC_GAME_OVER": "Game over",
	"ARC_CONTINUE": "Continue",
	"ARC_CONTINUE_IN": "Continue? %d",
	"ARC_QUIT": "Quit to title",
	"ARC_HIGH_SCORES": "High scores",
	"ARC_NEW_HIGH_SCORE": "A new high score! Your name:",
	"ARC_NO_SCORES": "Nobody has a score yet.",
	"ARC_OK": "OK",
	"ARC_WARNING": "Warning!",
	"ARC_SAVED_BETWEEN_STAGES": "Saved between stages",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)
