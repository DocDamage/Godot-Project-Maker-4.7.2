class_name RpgMetroidvaniaStrings
extends RefCounted
## Translation keys of the metroidvania archetype with their English text. The translations recipe
## adds them to game/i18n/strings.tsv when the project's archetype is metroidvania.

const KEYS := {
	"MV_ITEM_GAINED": "Picked up %s x%d",
	"MV_GOLD_GAINED": "+%d gold",
	"MV_LEVEL_UP": "Level %d!",
	"MV_ABILITY_GAINED": "You found %s!",
	"MV_ABILITY_DOUBLE_JUMP_NAME": "Double Jump",
	"MV_ABILITY_DOUBLE_JUMP_DESC": "Jump a second time in the air.",
	"MV_ABILITY_DOUBLE_JUMP_HINT": "Press %s twice",
	"MV_ABILITY_DASH_NAME": "Dash",
	"MV_ABILITY_DASH_DESC": "A short burst that crosses wide gaps. Nothing hurts you while it lasts.",
	"MV_ABILITY_DASH_HINT": "Press %s",
	"MV_ABILITY_WALL_JUMP_NAME": "Wall Jump",
	"MV_ABILITY_WALL_JUMP_DESC": "Slide down a wall and jump off it.",
	"MV_ABILITY_WALL_JUMP_HINT": "Press %s against a wall",
	"MV_ABILITY_HIGH_JUMP_NAME": "High Jump",
	"MV_ABILITY_HIGH_JUMP_DESC": "Every jump goes higher.",
	"MV_ABILITY_HIGH_JUMP_HINT": "Your jumps go higher",
	"MV_ABILITY_BREAK_BLOCKS_NAME": "Breaker",
	"MV_ABILITY_BREAK_BLOCKS_DESC": "Your attack breaks cracked blocks.",
	"MV_ABILITY_BREAK_BLOCKS_HINT": "Press %s at a cracked block",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)
