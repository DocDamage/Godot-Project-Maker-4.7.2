@tool
extends "data_tab.gd"
## The Items tab (1.5.0, T18.03): the items in res://game/data/items, one a file. The form: id, the
## name and description keys (with their English text from game/i18n/strings.tsv beside them),
## icon, category, stack size, value, the equipment's modifiers as rows, ranged, the use effect
## and its amount, what it cures, the battle fields of a turn-based game (shown only in one), and
## *Wear and sets*: durability (0: it never wears) and the set (one of game/data/item_sets, with a
## button that shows it in the Item sets tab). A new item's keys are added to strings.tsv with
## English text. JSON export and import. Every change is one undo step.

const ITEMS_DIR := "res://game/data/items"
const SETS_DIR := "res://game/data/item_sets"
const StringsTsv := preload("../tools/strings_tsv.gd")
const USE_EFFECTS: Array[String] = ["", "heal", "mp", "cure"]

var item: RpgItemDefinition = null
var items_dir := ITEMS_DIR  # tests point the tab at their own folders and file
var sets_dir := SETS_DIR
var strings_path := StringsTsv.PATH
## The battle fields are shown in a turn-based game only (its runtime folder is there).
var turn_based := DirAccess.dir_exists_absolute("res://addons/rpg_runtime/archetypes/turn_based")

var _id: LineEdit
var _name_key: LineEdit
var _name_text: Label
var _desc_key: LineEdit
var _desc_text: Label
var _icon: LineEdit
var _category: OptionButton
var _stack: SpinBox
var _value: SpinBox
var _modifier_rows: VBoxContainer
var _ranged: CheckBox
var _effect: OptionButton
var _amount: SpinBox
var _cures: LineEdit
var _battle: VBoxContainer
var _element: LineEdit
var _rates: LineEdit
var _immune: LineEdit
var _attack_status: LineEdit
var _attack_chance: SpinBox
var _durability: SpinBox
var _set: OptionButton
var _problems: Label

func _init() -> void:
	name = "Items"
	build_top([["New", new_item]])
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(form)
	_id = _field(form, "Item id", "id")
	_name_key = _field(form, "Name (a text key)", "display_name")
	_name_text = _english(form)
	_desc_key = _field(form, "Description (a text key)", "description")
	_desc_text = _english(form)
	_icon = LineEdit.new()
	_icon.placeholder_text = "res://... a texture (empty: none)"
	_icon.text_submitted.connect(func(text: String) -> void: set_icon(text))
	_icon.focus_exited.connect(func() -> void: set_icon(_icon.text))
	row(form, "Icon", _icon)
	_category = OptionButton.new()
	for key: String in RpgItemDefinition.Category.keys():
		_category.add_item(key.capitalize())
	_category.item_selected.connect(func(index: int) -> void: set_property("category", index))
	row(form, "Category", _category)
	_stack = _spin(form, "Stack size", 1, 9999, 1, func(value: float) -> void: set_property("max_stack", roundi(value)))
	_value = _spin(form, "Value (gold)", 0, 1000000, 1, func(value: float) -> void: set_property("value", roundi(value)))
	var mods_label := Label.new()
	mods_label.text = "Modifiers when worn: stat, add, multiply"
	form.add_child(mods_label)
	_modifier_rows = VBoxContainer.new()
	form.add_child(_modifier_rows)
	button(form, "Add a modifier", func() -> void: add_modifier("attack"))
	_ranged = CheckBox.new()
	_ranged.text = "Ranged: the attack shoots (action RPG)"
	_ranged.toggled.connect(func(on: bool) -> void: set_property("ranged", on))
	form.add_child(_ranged)
	_effect = OptionButton.new()
	for effect in USE_EFFECTS:
		_effect.add_item(effect if effect != "" else "(none)")
	_effect.item_selected.connect(func(index: int) -> void: set_property("use_effect", StringName(USE_EFFECTS[index])))
	row(form, "Use", _effect)
	_amount = _spin(form, "Amount (HP or MP)", 0, 99999, 1, func(value: float) -> void: set_property("effect_amount", roundi(value)))
	_cures = _list_field(form, "Cures (statuses, comma separated; empty: every harmful one)", "cures")
	_battle = VBoxContainer.new()
	form.add_child(_battle)
	var battle_label := Label.new()
	battle_label.text = "Battle (turn-based)"
	_battle.add_child(battle_label)
	_element = _field(_battle, "Element of its attacks", "element")
	_rates = LineEdit.new()
	_rates.placeholder_text = "fire: 0.5, ice: 2"
	_rates.text_submitted.connect(func(text: String) -> void: set_property("element_rates", parse_rates(text)))
	_rates.focus_exited.connect(func() -> void: set_property("element_rates", parse_rates(_rates.text)))
	row(_battle, "Element rates when worn", _rates)
	_immune = _list_field(_battle, "Statuses that never take hold when worn", "status_immune")
	_attack_status = _field(_battle, "Status its attacks inflict", "attack_status")
	_attack_chance = _spin(_battle, "Chance of that status (0..1)", 0.0, 1.0, 0.05, func(value: float) -> void: set_property("attack_status_chance", value))
	var wear_label := Label.new()
	wear_label.text = "Wear and sets"
	form.add_child(wear_label)
	_durability = _spin(form, "Durability (0: it never wears)", 0, 99999, 1, func(value: float) -> void: set_property("durability", roundi(value)))
	var set_row := HBoxContainer.new()
	_set = OptionButton.new()
	_set.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_set.item_selected.connect(func(index: int) -> void: set_property("set_id", StringName(_set_ids()[index])))
	set_row.add_child(_set)
	button(set_row, "Show in Item sets", show_set)
	row(form, "Set", set_row)
	_problems = note(form)
	build_status()

func _field(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: set_property(property, _typed(property, text)))
	edit.focus_exited.connect(func() -> void: set_property(property, _typed(property, edit.text)))
	row(parent, label_text, edit)
	return edit

func _list_field(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: set_property(property, parse_names(text)))
	edit.focus_exited.connect(func() -> void: set_property(property, parse_names(edit.text)))
	row(parent, label_text, edit)
	return edit

func _english(parent: Control) -> Label:
	var label := Label.new()
	label.modulate = Color(1, 1, 1, 0.7)
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(label)
	return label

func _spin(parent: Control, label_text: String, lo: float, hi: float, step: float, action: Callable) -> SpinBox:
	var spin := SpinBox.new()
	spin.min_value = lo
	spin.max_value = hi
	spin.step = step
	spin.value_changed.connect(func(value: float) -> void:
		if not _loading:
			action.call(value))
	row(parent, label_text, spin)
	return spin

static func _typed(property: String, text: String) -> Variant:
	if property in ["id", "element", "attack_status"]:
		return StringName(text.strip_edges())
	return text.strip_edges()

## "poison, sleep" -> [&"poison", &"sleep"].
static func parse_names(text: String) -> Array[StringName]:
	var out: Array[StringName] = []
	for word in text.split(",", false):
		if word.strip_edges() != "":
			out.append(StringName(word.strip_edges()))
	return out

static func names_text(list: Array[StringName]) -> String:
	return ", ".join(PackedStringArray(list.map(func(entry: StringName) -> String: return String(entry))))

## "fire: 0.5, ice: 2" -> {"fire": 0.5, "ice": 2.0}.
static func parse_rates(text: String) -> Dictionary:
	var out := {}
	for pair in text.split(",", false):
		var parts := pair.split(":")
		if parts.size() == 2 and parts[0].strip_edges() != "" and parts[1].strip_edges().is_valid_float():
			out[parts[0].strip_edges()] = parts[1].strip_edges().to_float()
	return out

static func rates_text(rates: Dictionary) -> String:
	var parts: PackedStringArray = []
	for key: Variant in rates:
		parts.append("%s: %s" % [key, rates[key]])
	return ", ".join(parts)

# ---------------------------------------------------------------- files

func folder() -> String:
	return items_dir

func context_object() -> Object:
	return item

func open(path: String) -> bool:
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition
	if res == null:
		say("%s is not an item." % path)
		return false
	item = res
	file_path = path
	dirty = false
	_refresh()
	say("%s." % path.get_file())
	return true

func save() -> bool:
	if item == null or file_path == "":
		return false
	var err := ResourceSaver.save(item, file_path)
	dirty = err != OK
	say("Saved %s." % file_path.get_file() if err == OK else "Could not save (error %d)." % err)
	return err == OK

## A new item with its keys (ITEM_<ID>_NAME, _DESC), which are added to strings.tsv in English.
func new_item() -> String:
	var made := RpgItemDefinition.new()
	DirAccess.make_dir_recursive_absolute(folder())
	var path := free_path("new_item")
	made.id = StringName(path.get_file().get_basename())
	var upper := String(made.id).to_upper()
	made.display_name = "ITEM_%s_NAME" % upper
	made.description = "ITEM_%s_DESC" % upper
	if ResourceSaver.save(made, path) != OK:
		say("Could not save %s." % path)
		return ""
	StringsTsv.add({made.display_name: String(made.id).capitalize(), made.description: ""}, strings_path)
	file_path = path
	rescan()
	open(path)
	return path

func to_json_text() -> String:
	return JSON.stringify(item.to_dict(), "  ", false) + "\n" if item != null else ""

func import_json(json_path: String) -> String:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if not (parsed is Dictionary) or not RpgUtil.to_dict(parsed).has("max_stack"):
		say("%s is not item JSON." % json_path.get_file())
		return ""
	var made := RpgItemDefinition.from_dict(RpgUtil.to_dict(RpgUtil.restore_numbers(parsed)))
	DirAccess.make_dir_recursive_absolute(folder())
	var target := folder().path_join(json_path.get_file().get_basename() + ".tres")
	if ResourceSaver.save(made, target) != OK:
		say("Could not save %s." % target)
		return ""
	StringsTsv.add({made.display_name: String(made.id).capitalize(), made.description: ""}, strings_path)
	file_path = target
	rescan()
	open(target)
	return target

# ---------------------------------------------------------------- the sets

## "" (none) and the ids of game/data/item_sets, sorted; the item's own when it has no file.
func _set_ids() -> Array[String]:
	var out: Array[String] = []
	for path in tres_files(sets_dir):
		out.append(path.get_file().get_basename())
	out.sort()
	if item != null and item.set_id != &"" and not out.has(String(item.set_id)):
		out.append(String(item.set_id))
	out.push_front("")
	return out

## Shows the item's set in the dock's Item sets tab.
func show_set() -> void:
	if item == null or item.set_id == &"":
		return
	var tabs := get_parent() as TabContainer
	var sets_tab: Node = tabs.get_node_or_null("Item sets") if tabs != null else null
	if sets_tab == null:
		return
	tabs.current_tab = sets_tab.get_index()
	var path := "%s/%s.tres" % [sets_dir, item.set_id]
	if FileAccess.file_exists(path):
		sets_tab.call("open", path)

# ---------------------------------------------------------------- showing

func problems() -> Array[String]:
	var out: Array[String] = []
	if item == null:
		return out
	if item.id == &"":
		out.append("the item has no id")
	if item.set_id != &"" and not FileAccess.file_exists("%s/%s.tres" % [sets_dir, item.set_id]):
		out.append("the item belongs to the set '%s', which has no file in %s" % [item.set_id, sets_dir])
	for key: String in [item.display_name, item.description]:
		if key != "" and not RpgUtil.to_dict(StringsTsv.read(strings_path)["rows"]).has(key):
			out.append("the key %s has no row in %s" % [key, strings_path.get_file()])
	return out

func _refresh() -> void:
	if item == null:
		return
	_loading = true
	var texts := RpgUtil.to_dict(StringsTsv.read(strings_path)["rows"])
	_id.text = String(item.id)
	_name_key.text = item.display_name
	_name_text.text = _text_of(texts, item.display_name)
	_desc_key.text = item.description
	_desc_text.text = _text_of(texts, item.description)
	_icon.text = item.icon.resource_path if item.icon != null and item.icon.resource_path != "" else ("(a part of %s)" % (item.icon as AtlasTexture).atlas.resource_path if item.icon is AtlasTexture and (item.icon as AtlasTexture).atlas != null else "")
	_category.select(item.category)
	_stack.value = item.max_stack
	_value.value = item.value
	_ranged.set_pressed_no_signal(item.ranged)
	_effect.select(maxi(0, USE_EFFECTS.find(String(item.use_effect))))
	_amount.value = item.effect_amount
	_cures.text = names_text(item.cures)
	_battle.visible = turn_based
	_element.text = String(item.element)
	_rates.text = rates_text(item.element_rates)
	_immune.text = names_text(item.status_immune)
	_attack_status.text = String(item.attack_status)
	_attack_chance.value = item.attack_status_chance
	_durability.value = item.durability
	var ids := _set_ids()
	_set.clear()
	for set_id in ids:
		_set.add_item(set_id if set_id != "" else "(none)")
	_set.select(ids.find(String(item.set_id)))
	_build_modifier_rows()
	_loading = false
	_problems.text = "\n".join(PackedStringArray(problems()))

static func _text_of(texts: Dictionary, key: String) -> String:
	var row_cells: Array = texts.get(key, [])
	if key == "":
		return ""
	return "\"%s\"" % str(row_cells[0]) if not row_cells.is_empty() else "(no row in strings.tsv)"

func _build_modifier_rows() -> void:
	for child in _modifier_rows.get_children():
		_modifier_rows.remove_child(child)
		child.queue_free()
	for i in item.modifiers.size():
		var entry := item.modifiers[i]
		var line := HBoxContainer.new()
		line.name = "Modifier%d" % i
		var stat := LineEdit.new()
		stat.text = str(entry.get("stat", ""))
		stat.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		stat.text_submitted.connect(func(text: String) -> void: set_modifier(i, "stat", text.strip_edges()))
		stat.focus_exited.connect(func() -> void: set_modifier(i, "stat", stat.text.strip_edges()))
		line.add_child(stat)
		var add := SpinBox.new()
		add.min_value = -9999
		add.max_value = 9999
		add.value = RpgUtil.to_float(entry.get("add", 0))
		add.value_changed.connect(func(value: float) -> void:
			if not _loading:
				set_modifier(i, "add", roundi(value)))
		line.add_child(add)
		var mul := SpinBox.new()
		mul.max_value = 10
		mul.step = 0.05
		mul.value = RpgUtil.to_float(entry.get("mul", 1.0))
		mul.value_changed.connect(func(value: float) -> void:
			if not _loading:
				set_modifier(i, "mul", value))
		line.add_child(mul)
		button(line, "Remove", func() -> void: remove_modifier(i))
		_modifier_rows.add_child(line)

# ---------------------------------------------------------------- edits (one undo step each)

func _apply(value: Array) -> void:
	item.set(str(value[0]), value[1])
	dirty = true
	_refresh()

func set_property(property: String, value: Variant) -> void:
	if _loading or item == null:
		return
	var old: Variant = item.get(property)
	if typeof(old) == typeof(value) and old == value:
		return
	record("Edit item", &"_apply", [property, value], [property, old])

## The icon: a texture's path, or empty for none.
func set_icon(path: String) -> void:
	if _loading or item == null:
		return
	var clean := path.strip_edges()
	if clean.begins_with("(a part of"):
		return  # the part of a sheet it has: shown, not a path
	var texture: Texture2D = load(clean) as Texture2D if clean != "" and ResourceLoader.exists(clean) else null
	if clean != "" and texture == null:
		say("%s is not a texture." % clean)
		return
	if texture != item.icon:
		record("Set the item's icon", &"_apply", ["icon", texture], ["icon", item.icon])

func _modifiers_copy() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for entry in item.modifiers:
		out.append(entry.duplicate(true))
	return out

func _set_modifiers(rows: Array[Dictionary]) -> void:
	record("Edit the item's modifiers", &"_apply", ["modifiers", rows], ["modifiers", _modifiers_copy()])

func set_modifier(index: int, key: String, value: Variant) -> void:
	if _loading or item == null or index < 0 or index >= item.modifiers.size():
		return
	var rows := _modifiers_copy()
	if rows[index].get(key) == value:
		return
	rows[index][key] = value
	_set_modifiers(rows)

func add_modifier(stat: String) -> void:
	if item == null:
		return
	var rows := _modifiers_copy()
	rows.append({"stat": stat, "add": 1, "mul": 1.0})
	_set_modifiers(rows)

func remove_modifier(index: int) -> void:
	if item == null or index < 0 or index >= item.modifiers.size():
		return
	var rows := _modifiers_copy()
	rows.remove_at(index)
	_set_modifiers(rows)
