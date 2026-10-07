class_name RpgBattleStrings
extends RefCounted
## Translation keys of the turn-based battle with their English text. The translations recipe adds
## them to game/i18n/strings.tsv when the project's archetype is turn_based. Sentences take their
## values through %s / %d.

const KEYS := {
	"BATTLE_ATTACK": "Attack",
	"BATTLE_DEFEND": "Defend",
	"BATTLE_ITEM": "Item",
	"BATTLE_RUN": "Run",
	"BATTLE_SKILLS_NONE": "Skills (none)",
	"BATTLE_ATTACK_HIT": "%s attacks %s for %d damage.",
	"BATTLE_ATTACK_CRIT": "Critical hit! %s hits %s for %d damage.",
	"BATTLE_DEFEATED_NAME": "%s is defeated.",
	"BATTLE_DEFENDS": "%s defends.",
	"BATTLE_NO_EFFECT": "It had no effect.",
	"BATTLE_ITEM_HEAL": "%s uses %s on %s: %d HP restored.",
	"BATTLE_NO_ESCAPE": "There is no way to escape!",
	"BATTLE_ESCAPED": "Got away safely!",
	"BATTLE_ESCAPE_FAILED": "Could not get away!",
	"BATTLE_APPEARS": "%s appears!",
	"BATTLE_VICTORY": "Victory!",
	"BATTLE_DEFEATED": "Defeated",
	"BATTLE_REWARDS": "Gained %d XP and %d gold.",
	"BATTLE_FOUND": "Found: %s",
	"BATTLE_LEVEL_UP": "%s reached level %d!",
	"BATTLE_CHOOSE_TARGET": "Choose a target",
	"BATTLE_NO_ITEMS": "No items to use",
}
