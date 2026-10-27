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

@export_group("Wear and sets (1.5.0)")
## How much wear the item takes before it breaks; 0 (the default): it never wears. A worn weapon
## wears by one with each attack, worn armour or an accessory with each hit taken
## (GameState.wear); what it has taken is the data of its slot ({"wear": n}).
@export var durability: int = 0
## The set the item belongs to (game/data/item_sets/<id>.tres, an RpgItemSet): wearing enough of
## its pieces gives the set's bonuses. &"" for none.
@export var set_id: StringName = &""

## The item as plain data, and back (the dock's JSON export and import, 1.5.0). The icon is its
## file's path, or {atlas, region} for a part of a sheet; enums are written by name.
func to_dict() -> Dictionary:
	var out := {"id": String(id), "display_name": display_name, "description": description, "category": Category.find_key(category), "max_stack": max_stack, "value": value, "modifiers": modifiers.duplicate(true), "ranged": ranged, "use_effect": String(use_effect), "effect_amount": effect_amount, "cures": _names(cures), "element": String(element), "element_rates": element_rates.duplicate(true), "status_immune": _names(status_immune), "attack_status": String(attack_status), "attack_status_chance": attack_status_chance, "durability": durability, "set_id": String(set_id)}
	if icon is AtlasTexture and (icon as AtlasTexture).atlas != null and icon.resource_path == "":
		var part := icon as AtlasTexture
		out["icon"] = {"atlas": part.atlas.resource_path, "region": [part.region.position.x, part.region.position.y, part.region.size.x, part.region.size.y]}
	elif icon != null:
		out["icon"] = icon.resource_path
	return out

static func _names(list: Array[StringName]) -> Array:
	var out: Array = []
	for entry in list:
		out.append(String(entry))
	return out

static func _name_list(raw: Variant) -> Array[StringName]:
	var out: Array[StringName] = []
	for entry: Variant in RpgUtil.to_array(raw):
		out.append(StringName(str(entry)))
	return out

static func from_dict(data: Dictionary) -> RpgItemDefinition:
	var made := RpgItemDefinition.new()
	made.id = StringName(str(data.get("id", "")))
	made.display_name = str(data.get("display_name", ""))
	made.description = str(data.get("description", ""))
	var kind: Variant = Category.get(str(data.get("category", "CONSUMABLE")).to_upper(), Category.CONSUMABLE)
	made.category = RpgUtil.to_int(kind) as Category
	made.max_stack = RpgUtil.to_int(data.get("max_stack", made.max_stack))
	made.value = RpgUtil.to_int(data.get("value", made.value))
	for raw: Variant in RpgUtil.to_array(data.get("modifiers", [])):
		if raw is Dictionary:
			made.modifiers.append(RpgUtil.to_dict(raw).duplicate(true))
	made.ranged = RpgUtil.to_bool(data.get("ranged", false))
	made.use_effect = StringName(str(data.get("use_effect", "")))
	made.effect_amount = RpgUtil.to_int(data.get("effect_amount", 0))
	made.cures = _name_list(data.get("cures", []))
	made.element = StringName(str(data.get("element", "")))
	made.element_rates = RpgUtil.to_dict(data.get("element_rates", {})).duplicate(true)
	made.status_immune = _name_list(data.get("status_immune", []))
	made.attack_status = StringName(str(data.get("attack_status", "")))
	made.attack_status_chance = RpgUtil.to_float(data.get("attack_status_chance", 0.0))
	made.durability = RpgUtil.to_int(data.get("durability", 0))
	made.set_id = StringName(str(data.get("set_id", "")))
	var icon_data: Variant = data.get("icon", "")
	if icon_data is Dictionary:
		var sheet := str(RpgUtil.to_dict(icon_data).get("atlas", ""))
		var region := RpgUtil.to_array(RpgUtil.to_dict(icon_data).get("region", []))
		if ResourceLoader.exists(sheet) and region.size() == 4:
			var part := AtlasTexture.new()
			part.atlas = load(sheet) as Texture2D
			part.region = Rect2(RpgUtil.to_float(region[0]), RpgUtil.to_float(region[1]), RpgUtil.to_float(region[2]), RpgUtil.to_float(region[3]))
			made.icon = part
	elif str(icon_data) != "" and ResourceLoader.exists(str(icon_data)):
		made.icon = load(str(icon_data)) as Texture2D
	return made
