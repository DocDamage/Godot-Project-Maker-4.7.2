@tool
extends "data_tab.gd"
## The Item sets tab (1.5.0): the sets of gear in res://game/data/item_sets. The form: id, title
## and the bonuses ("2: defense +5, attack +1", one line for each number of pieces); the items of
## game/data/items that belong to the set, with Add and Remove (each saves the item's `set_id`)
## and the durability of the item picked (0: it never wears); what is wrong with the set; JSON
## export and import. Every change is one undo step.

const SETS_DIR := "res://game/data/item_sets"
const ITEMS_DIR := "res://game/data/items"
const SkillTreeTab := preload("skill_tree_tab.gd")

var item_set: RpgItemSet = null
var sets_dir := SETS_DIR  # tests point the tab at their own folders
var items_dir := ITEMS_DIR

var _id: LineEdit
var _title: LineEdit
var _bonuses: TextEdit
var _members: ItemList
var _all_items: OptionButton
var _durability: SpinBox
var _problems: Label

func _init() -> void:
	name = "Item sets"
	build_top([["New", new_set]])
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(form)
	_id = _field(form, "Set id", "id")
	_title = _field(form, "Title (a text key)", "title")
	_bonuses = TextEdit.new()
	_bonuses.custom_minimum_size = Vector2(0, 60)
	_bonuses.placeholder_text = "one line for each number of pieces worn: 2: defense +5, attack +1"
	_bonuses.focus_exited.connect(func() -> void: set_property("bonuses", parse_bonuses(_bonuses.text)))
	row(form, "Bonuses", _bonuses)
	var members_label := Label.new()
	members_label.text = "Items of the set"
	form.add_child(members_label)
	_members = ItemList.new()
	_members.custom_minimum_size = Vector2(0, 80)
	_members.item_selected.connect(func(_index: int) -> void: _show_durability())
	form.add_child(_members)
	var add_row := HBoxContainer.new()
	_all_items = OptionButton.new()
	_all_items.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_row.add_child(_all_items)
	button(add_row, "Add", func() -> void:
		if _all_items.selected >= 0:
			add_member(_all_items.get_item_text(_all_items.selected)))
	button(add_row, "Remove", func() -> void:
		var picked := _members.get_selected_items()
		if not picked.is_empty():
			remove_member(_members.get_item_text(picked[0])))
	form.add_child(add_row)
	_durability = SpinBox.new()
	_durability.max_value = 9999
	_durability.rounded = true
	_durability.value_changed.connect(func(value: float) -> void:
		var picked := _members.get_selected_items()
		if not _loading and not picked.is_empty():
			set_durability(_members.get_item_text(picked[0]), roundi(value)))
	row(form, "Durability of the item picked (0: never wears)", _durability)
	_problems = note(form)
	build_status()

func _field(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: set_property(property, _typed(property, text)))
	edit.focus_exited.connect(func() -> void: set_property(property, _typed(property, edit.text)))
	row(parent, label_text, edit)
	return edit

static func _typed(property: String, text: String) -> Variant:
	return StringName(text.strip_edges()) if property == "id" else text.strip_edges()

# ---------------------------------------------------------------- files

func folder() -> String:
	return sets_dir

func context_object() -> Object:
	return item_set

func open(path: String) -> bool:
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemSet
	if res == null:
		say("%s is not an item set." % path)
		return false
	item_set = res
	file_path = path
	dirty = false
	_refresh()
	say("%s: %d items." % [path.get_file(), members().size()])
	return true

func save() -> bool:
	if item_set == null or file_path == "":
		return false
	var err := ResourceSaver.save(item_set, file_path)
	dirty = err != OK
	say("Saved %s." % file_path.get_file() if err == OK else "Could not save (error %d)." % err)
	return err == OK

func new_set() -> String:
	var made := RpgItemSet.new()
	DirAccess.make_dir_recursive_absolute(folder())
	var path := free_path("new_set")
	made.id = StringName(path.get_file().get_basename())
	made.title = "ITEM_SET_%s_NAME" % String(made.id).to_upper()
	var bonuses: Array[Dictionary] = [{"pieces": 2, "modifiers": [{"stat": "defense", "add": 2}]}]
	made.bonuses = bonuses
	if ResourceSaver.save(made, path) != OK:
		say("Could not save %s." % path)
		return ""
	file_path = path
	rescan()
	open(path)
	return path

func to_json_text() -> String:
	return JSON.stringify(item_set.to_dict(), "  ", false) + "\n" if item_set != null else ""

func import_json(json_path: String) -> String:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if not (parsed is Dictionary) or not (RpgUtil.to_dict(parsed).get("bonuses") is Array):
		say("%s is not item set JSON." % json_path.get_file())
		return ""
	var made := RpgItemSet.from_dict(RpgUtil.to_dict(RpgUtil.restore_numbers(parsed)))
	DirAccess.make_dir_recursive_absolute(folder())
	var target := folder().path_join(json_path.get_file().get_basename() + ".tres")
	if ResourceSaver.save(made, target) != OK:
		say("Could not save %s." % target)
		return ""
	file_path = target
	rescan()
	open(target)
	return target

# ---------------------------------------------------------------- the items

## {item id: path} of the item files.
func item_files() -> Dictionary:
	var out := {}
	for path in tres_files(items_dir):
		var item := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition
		if item != null:
			out[String(item.id) if item.id != &"" else path.get_file().get_basename()] = path
	return out

## The ids of the items that name this set, sorted.
func members() -> Array[String]:
	var out: Array[String] = []
	if item_set == null:
		return out
	var files := item_files()
	for item_id: Variant in files:
		var item := load(str(files[item_id])) as RpgItemDefinition
		if item != null and item.set_id == item_set.id:
			out.append(str(item_id))
	out.sort()
	return out

func _apply_item(value: Array) -> void:
	var path := str(item_files().get(str(value[0]), ""))
	var item := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition if path != "" else null
	if item == null:
		return
	item.set(str(value[1]), value[2])
	ResourceSaver.save(item, path)
	_refresh()

func _item(item_id: String) -> RpgItemDefinition:
	var path := str(item_files().get(item_id, ""))
	return load(path) as RpgItemDefinition if path != "" else null

## Puts the item in this set (its file is saved). One undo step.
func add_member(item_id: String) -> void:
	var item := _item(item_id)
	if item == null or item_set == null or item.set_id == item_set.id:
		return
	record("Add the item to the set", &"_apply_item", [item_id, "set_id", item_set.id], [item_id, "set_id", item.set_id])

func remove_member(item_id: String) -> void:
	var item := _item(item_id)
	if item == null or item_set == null or item.set_id != item_set.id:
		return
	record("Take the item out of the set", &"_apply_item", [item_id, "set_id", &""], [item_id, "set_id", item.set_id])

func set_durability(item_id: String, durability: int) -> void:
	var item := _item(item_id)
	if item == null or item.durability == durability:
		return
	record("Set the durability", &"_apply_item", [item_id, "durability", maxi(0, durability)], [item_id, "durability", item.durability])

# ---------------------------------------------------------------- showing

func problems() -> Array[String]:
	var out: Array[String] = item_set.problems() if item_set != null else [] as Array[String]
	if item_set != null and item_set.first_bonus_at() > 0 and members().size() < item_set.first_bonus_at():
		out.append("fewer items name the set than its first bonus needs (%d)" % item_set.first_bonus_at())
	return out

func _refresh() -> void:
	if item_set == null:
		return
	_loading = true
	_id.text = String(item_set.id)
	_title.text = item_set.title
	_bonuses.text = bonuses_text(item_set.bonuses)
	_members.clear()
	for item_id in members():
		_members.add_item(item_id)
	_all_items.clear()
	var ids: Array = item_files().keys()
	ids.sort()
	for item_id: Variant in ids:
		_all_items.add_item(str(item_id))
	_loading = false
	_show_durability()
	_problems.text = "\n".join(PackedStringArray(problems()))

func _show_durability() -> void:
	var picked := _members.get_selected_items()
	var item := _item(_members.get_item_text(picked[0])) if not picked.is_empty() else null
	_loading = true
	_durability.editable = item != null
	_durability.value = item.durability if item != null else 0
	_loading = false

# ---------------------------------------------------------------- edits (one undo step each)

func _apply(value: Array) -> void:
	item_set.set(str(value[0]), value[1])
	dirty = true
	_refresh()

func set_property(property: String, value: Variant) -> void:
	if _loading or item_set == null:
		return
	var old: Variant = item_set.get(property)
	if typeof(old) == typeof(value) and old == value:
		return
	record("Edit item set", &"_apply", [property, value], [property, old])

## "2: defense +5, attack +1" lines -> [{pieces, modifiers}] (the modifiers as the Skills tab
## reads bonuses).
static func parse_bonuses(text: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for raw in text.split("\n", false):
		var line := raw.strip_edges()
		var colon := line.find(":")
		if colon <= 0 or not line.substr(0, colon).strip_edges().is_valid_int():
			continue
		out.append({"pieces": line.substr(0, colon).strip_edges().to_int(), "modifiers": SkillTreeTab.parse_bonuses(line.substr(colon + 1))})
	return out

static func bonuses_text(bonuses: Array[Dictionary]) -> String:
	var lines: PackedStringArray = []
	for bonus in bonuses:
		lines.append("%d: %s" % [RpgUtil.to_int(bonus.get("pieces", 0)), SkillTreeTab.bonuses_text(RpgUtil.to_array(bonus.get("modifiers", []))).replace("\n", ", ")])
	return "\n".join(lines)
