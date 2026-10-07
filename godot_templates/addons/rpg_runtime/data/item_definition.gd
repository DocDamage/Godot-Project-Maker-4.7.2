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
@export var use_effect: StringName = &""  # "heal", "", future: "cure", ...
@export var effect_amount: int = 0
