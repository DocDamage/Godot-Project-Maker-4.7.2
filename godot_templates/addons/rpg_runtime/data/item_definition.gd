class_name RpgItemDefinition
extends Resource

enum Category { CONSUMABLE, WEAPON, ARMOR, ACCESSORY, QUEST, KEY, MATERIAL }

@export var id: StringName
@export var display_name: String  # a tr() key, e.g. "ITEM_POTION_NAME"
@export var description: String  # tr() key
@export var icon: Texture2D
@export var category: Category = Category.CONSUMABLE
@export var max_stack: int = 99
@export var value: int = 10
@export var modifiers: Array[Dictionary] = []  # [{stat, add, mul}] for equipment
## A weapon that shoots (action RPG): the attack fires an arrow instead of a swing.
@export var ranged: bool = false
## "heal" (effect_amount HP), "mp" (effect_amount MP), "cure" (removes `cures`, in battle), "".
@export var use_effect: StringName = &""
@export var effect_amount: int = 0
## The statuses a "cure" item removes (empty = every harmful one).
@export var cures: Array[StringName] = []

@export_group("Battle (turn-based)")
## A weapon's element: its attacks hit with it.
@export var element: StringName = &""
## Worn: {element: rate} like RpgActorDefinition.element_rates (the lowest worn rate counts).
@export var element_rates: Dictionary = {}
## Worn: statuses that never take hold.
@export var status_immune: Array[StringName] = []
## A weapon's status: its attacks inflict it with this chance (0..1).
@export var attack_status: StringName = &""
@export var attack_status_chance: float = 0.0
