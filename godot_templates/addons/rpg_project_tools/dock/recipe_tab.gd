@tool
extends "data_tab.gd"
## The Recipes tab (1.5.0, T18.14): the recipes of crafting in res://game/data/recipes, one a
## file. The form: id, title, the ingredients and the results as rows (an item of game/data/items
## and how many), the station (empty: by hand), the minutes, the category, how it is learned and
## the hint of one not yet known; what is wrong with it (VAL-034 says the same). JSON export and
## import. Every change is one undo step.

const RECIPES_DIR := "res://game/data/recipes"
const ITEMS_DIR := "res://game/data/items"
const ROW_BAD := Color(1.0, 0.4, 0.4)

var recipe: RpgRecipe = null
var recipes_dir := RECIPES_DIR  # tests point the tab at their own folders
var items_dir := ITEMS_DIR

var _id: LineEdit
var _title: LineEdit
var _tables: Dictionary = {}  # "ingredients" / "results" -> VBoxContainer
var _station: LineEdit
var _minutes: SpinBox
var _category: LineEdit
var _learn: OptionButton
var _hint: LineEdit
var _problems: Label

func _init() -> void:
	name = "Recipes"
	build_top([["New", new_recipe]])
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(form)
	_id = _field(form, "Recipe id", "id")
	_title = _field(form, "Title (a text key)", "title")
	for table: String in ["ingredients", "results"]:
		var label := Label.new()
		label.text = "Takes (item, how many)" if table == "ingredients" else "Makes (item, how many)"
		form.add_child(label)
		var rows := VBoxContainer.new()
		rows.name = table.capitalize()
		form.add_child(rows)
		_tables[table] = rows
		button(form, "Add an item", func() -> void: add_item(table, ""))
	_station = _field(form, "Station (empty: by hand)", "station")
	_minutes = SpinBox.new()
	_minutes.max_value = 100000
	_minutes.value_changed.connect(func(value: float) -> void:
		if not _loading:
			set_property("minutes", roundi(value)))
	row(form, "Minutes it takes (0: at once)", _minutes)
	_category = _field(form, "Category", "category")
	_learn = OptionButton.new()
	for way in RpgRecipe.LEARN_WAYS:
		_learn.add_item(way)
	_learn.item_selected.connect(func(index: int) -> void: set_property("learn", RpgRecipe.LEARN_WAYS[index]))
	row(form, "Learned", _learn)
	_hint = _field(form, "Hint while unknown", "hint")
	_problems = note(form)
	build_status()

func _field(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: set_property(property, _typed(property, text)))
	edit.focus_exited.connect(func() -> void: set_property(property, _typed(property, edit.text)))
	row(parent, label_text, edit)
	return edit

static func _typed(property: String, text: String) -> Variant:
	return StringName(text.strip_edges()) if property in ["id", "station"] else text.strip_edges()

# ---------------------------------------------------------------- files

func folder() -> String:
	return recipes_dir

func context_object() -> Object:
	return recipe

func open(path: String) -> bool:
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgRecipe
	if res == null:
		say("%s is not a recipe." % path)
		return false
	recipe = res
	file_path = path
	dirty = false
	_refresh()
	say("%s." % path.get_file())
	return true

func save() -> bool:
	if recipe == null or file_path == "":
		return false
	var err := ResourceSaver.save(recipe, file_path)
	dirty = err != OK
	say("Saved %s." % file_path.get_file() if err == OK else "Could not save (error %d)." % err)
	return err == OK

func new_recipe() -> String:
	var made := RpgRecipe.new()
	DirAccess.make_dir_recursive_absolute(folder())
	var path := free_path("new_recipe")
	made.id = StringName(path.get_file().get_basename())
	made.title = "RECIPE_%s_NAME" % String(made.id).to_upper()
	if ResourceSaver.save(made, path) != OK:
		say("Could not save %s." % path)
		return ""
	file_path = path
	rescan()
	open(path)
	return path

func to_json_text() -> String:
	return JSON.stringify(recipe.to_dict(), "  ", false) + "\n" if recipe != null else ""

func import_json(json_path: String) -> String:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if not (parsed is Dictionary) or not (RpgUtil.to_dict(parsed).get("ingredients") is Dictionary):
		say("%s is not recipe JSON." % json_path.get_file())
		return ""
	var made := RpgRecipe.from_dict(RpgUtil.to_dict(RpgUtil.restore_numbers(parsed)))
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

func item_ids() -> Array[String]:
	var out: Array[String] = []
	for path in tres_files(items_dir):
		var item := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition
		if item != null:
			out.append(String(item.id) if item.id != &"" else path.get_file().get_basename())
	out.sort()
	return out

## What is wrong with the recipe: its own problems and the items it names that have no file.
func problems() -> Array[String]:
	var out: Array[String] = recipe.problems() if recipe != null else [] as Array[String]
	if recipe != null:
		var ids := item_ids()
		for item_id in recipe.items():
			if not ids.has(item_id):
				out.append("'%s' has no file in %s" % [item_id, RpgGameState.ITEMS_DIR])
	return out

func _refresh() -> void:
	if recipe == null:
		return
	_loading = true
	_id.text = String(recipe.id)
	_title.text = recipe.title
	_station.text = String(recipe.station)
	_minutes.value = recipe.minutes
	_category.text = recipe.category
	_learn.select(maxi(0, RpgRecipe.LEARN_WAYS.find(recipe.learn)))
	_hint.text = recipe.hint
	var ids := item_ids()
	for table: String in ["ingredients", "results"]:
		_build_rows(table, ids)
	_loading = false
	_problems.text = "\n".join(PackedStringArray(problems()))

func _build_rows(table: String, ids: Array[String]) -> void:
	var holder: VBoxContainer = _tables[table]
	for child in holder.get_children():
		holder.remove_child(child)
		child.queue_free()
	var given: Dictionary = recipe.get(table)
	var keys := given.keys()
	keys.sort()
	for item_id: Variant in keys:
		var line := HBoxContainer.new()
		line.name = "Row_%s" % item_id
		var picker := OptionButton.new()
		picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var choices := ids.duplicate()
		if not choices.has(str(item_id)):
			choices.push_front(str(item_id))
			picker.add_theme_color_override("font_color", ROW_BAD)
			picker.tooltip_text = "'%s' has no file in %s" % [item_id, RpgGameState.ITEMS_DIR]
		for choice: String in choices:
			picker.add_item(choice)
		picker.select(choices.find(str(item_id)))
		var old := str(item_id)
		picker.item_selected.connect(func(index: int) -> void: rename_item(table, old, picker.get_item_text(index)))
		line.add_child(picker)
		var qty := SpinBox.new()
		qty.min_value = 1
		qty.max_value = 999
		qty.value = RpgUtil.to_int(given[item_id], 1)
		qty.value_changed.connect(func(value: float) -> void:
			if not _loading:
				set_qty(table, old, roundi(value)))
		line.add_child(qty)
		button(line, "Remove", func() -> void: remove_item(table, old))
		holder.add_child(line)

# ---------------------------------------------------------------- edits (one undo step each)

func _apply(value: Array) -> void:
	recipe.set(str(value[0]), value[1])
	dirty = true
	_refresh()

func set_property(property: String, value: Variant) -> void:
	if _loading or recipe == null:
		return
	var old: Variant = recipe.get(property)
	if typeof(old) == typeof(value) and old == value:
		return
	record("Edit recipe", &"_apply", [property, value], [property, old])

func _table_copy(table: String) -> Dictionary:
	var given: Dictionary = recipe.get(table)
	return given.duplicate()

func _set_table(table: String, changed: Dictionary) -> void:
	record("Edit the recipe's %s" % table, &"_apply", [table, changed], [table, _table_copy(table)])

func add_item(table: String, item_id: String) -> void:
	if recipe == null:
		return
	var changed := _table_copy(table)
	var ids := item_ids()
	var chosen := item_id if item_id != "" else (ids[0] if not ids.is_empty() else "item")
	changed[chosen] = RpgUtil.to_int(changed.get(chosen, 0)) + 1
	_set_table(table, changed)

func set_qty(table: String, item_id: String, qty: int) -> void:
	if _loading or recipe == null:
		return
	var changed := _table_copy(table)
	if not changed.has(item_id) or RpgUtil.to_int(changed[item_id]) == qty:
		return
	changed[item_id] = maxi(1, qty)
	_set_table(table, changed)

func rename_item(table: String, old: String, new_id: String) -> void:
	if _loading or recipe == null or old == new_id:
		return
	var changed := _table_copy(table)
	var qty := RpgUtil.to_int(changed.get(old, 1), 1)
	changed.erase(old)
	changed[new_id] = qty
	_set_table(table, changed)

func remove_item(table: String, item_id: String) -> void:
	if recipe == null:
		return
	var changed := _table_copy(table)
	if not changed.has(item_id):
		return
	changed.erase(item_id)
	_set_table(table, changed)
