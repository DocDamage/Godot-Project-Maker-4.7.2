@tool
extends "data_tab.gd"
## The Shops tab (1.5.0, T18.02): the shops in res://game/data/shops, one a file. The form: id,
## title, the stock as rows (an item of game/data/items, its price, its quantity), the sell
## ratio, what the shop buys, when it restocks, its gold, its rolled wares (a loot table of the
## project's), buyback and repairs. A row whose item has no file is shown in red with the reason
## the validator gives (VAL-034). JSON export and import. Every change is one undo step.

const SHOPS_DIR := "res://game/data/shops"
const ITEMS_DIR := "res://game/data/items"
const ENEMIES_DIR := "res://game/data/enemies"
## Loot tables saved as files of their own, which a shop's wares can be.
const LOOT_DIR := "res://game/data/loot_tables"
const ROW_BAD := Color(1.0, 0.4, 0.4)

var shop: RpgShopDefinition = null
var shops_dir := SHOPS_DIR  # tests point the tab at their own folders
var items_dir := ITEMS_DIR
var enemies_dir := ENEMIES_DIR
var loot_dir := LOOT_DIR

var _id: LineEdit
var _title: LineEdit
var _rows: VBoxContainer
var _ratio: SpinBox
var _buys: Dictionary = {}  # category -> CheckBox
var _restock_minutes: SpinBox
var _restock_each_day: CheckBox
var _funds: SpinBox
var _wares: OptionButton
var _buyback: CheckBox
var _repairs: CheckBox
var _problems: Label
var _tables: Array = []  # [[label, RpgLootTable or null]], the wares picker's choices

func _init() -> void:
	name = "Shops"
	build_top([["New", new_shop]])
	var scroll := ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	add_child(scroll)
	var form := VBoxContainer.new()
	form.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(form)
	_id = _field(form, "Shop id (open_shop:<id> opens it)", "id")
	_title = _field(form, "Title (a text key)", "title")
	var stock_label := Label.new()
	stock_label.text = "Stock: item, price (-1: the item's value), how many until it restocks (-1: no limit)"
	stock_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	form.add_child(stock_label)
	_rows = VBoxContainer.new()
	form.add_child(_rows)
	button(form, "Add a row", func() -> void: add_row(""))
	_ratio = _spin(form, "Pays for what it buys (a share of the value)", 0.0, 4.0, 0.05, func(value: float) -> void: set_property("sell_ratio", value))
	var buys_label := Label.new()
	buys_label.text = "Buys (none ticked: everything but key and quest items)"
	form.add_child(buys_label)
	var buys_row := HFlowContainer.new()
	for category: String in RpgShopDefinition.CATEGORIES:
		var check := CheckBox.new()
		check.text = category.capitalize()
		check.toggled.connect(func(_on: bool) -> void: set_property("buys", _ticked_buys()))
		buys_row.add_child(check)
		_buys[category] = check
	form.add_child(buys_row)
	_restock_minutes = _spin(form, "Restocks every N minutes of play (0: not by the clock)", 0, 100000, 1, func(value: float) -> void: set_property("restock_minutes", roundi(value)))
	_restock_each_day = CheckBox.new()
	_restock_each_day.text = "Restocks each morning (a game with a calendar)"
	_restock_each_day.toggled.connect(func(on: bool) -> void: set_property("restock_each_day", on))
	form.add_child(_restock_each_day)
	_funds = _spin(form, "The shop's gold (-1: it never runs out)", -1, 1000000, 1, func(value: float) -> void: set_property("funds", roundi(value)))
	_wares = OptionButton.new()
	_wares.item_selected.connect(func(index: int) -> void: set_wares(index))
	row(form, "Rolled wares at each restock", _wares)
	_buyback = CheckBox.new()
	_buyback.text = "What the player sells can be bought back until the shop restocks"
	_buyback.toggled.connect(func(on: bool) -> void: set_property("buyback", on))
	form.add_child(_buyback)
	_repairs = CheckBox.new()
	_repairs.text = "Repairs worn gear for gold"
	_repairs.toggled.connect(func(on: bool) -> void: set_property("repairs", on))
	form.add_child(_repairs)
	_problems = note(form)
	build_status()

func _field(parent: Control, label_text: String, property: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.text_submitted.connect(func(text: String) -> void: set_property(property, _typed(property, text)))
	edit.focus_exited.connect(func() -> void: set_property(property, _typed(property, edit.text)))
	row(parent, label_text, edit)
	return edit

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
	return StringName(text.strip_edges()) if property == "id" else text.strip_edges()

func _check(category: String) -> CheckBox:
	var check: CheckBox = _buys[category]
	return check

func _ticked_buys() -> Array[String]:
	var out: Array[String] = []
	for category: String in RpgShopDefinition.CATEGORIES:
		if _check(category).button_pressed:
			out.append(category)
	return out

# ---------------------------------------------------------------- files

func folder() -> String:
	return shops_dir

func context_object() -> Object:
	return shop

func open(path: String) -> bool:
	var res := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgShopDefinition
	if res == null:
		say("%s is not a shop." % path)
		return false
	shop = res
	file_path = path
	dirty = false
	_refresh()
	say("%s: %d rows of stock." % [path.get_file(), shop.stock.size()])
	return true

func save() -> bool:
	if shop == null or file_path == "":
		return false
	var err := ResourceSaver.save(shop, file_path)
	dirty = err != OK
	say("Saved %s." % file_path.get_file() if err == OK else "Could not save (error %d)." % err)
	return err == OK

func new_shop() -> String:
	var made := RpgShopDefinition.new()
	DirAccess.make_dir_recursive_absolute(folder())
	var path := free_path("new_shop")
	made.id = StringName(path.get_file().get_basename())
	if ResourceSaver.save(made, path) != OK:
		say("Could not save %s." % path)
		return ""
	file_path = path
	rescan()
	open(path)
	return path

func to_json_text() -> String:
	return JSON.stringify(shop.to_dict(), "  ", false) + "\n" if shop != null else ""

func import_json(json_path: String) -> String:
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if not (parsed is Dictionary) or not (RpgUtil.to_dict(parsed).get("stock") is Array):
		say("%s is not shop JSON." % json_path.get_file())
		return ""
	var data := RpgUtil.to_dict(RpgUtil.restore_numbers(parsed))
	var target := folder().path_join(json_path.get_file().get_basename() + ".tres")
	# a shop of a farm (RpgFarmShop) stays one: the file it replaces says which kind it is
	var made: RpgShopDefinition = null
	var old := ResourceLoader.load(target, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgShopDefinition if ResourceLoader.exists(target) else null
	if old != null:
		var kind: GDScript = old.get_script()
		made = kind.new()
		made.apply_dict(data)
	else:
		made = RpgShopDefinition.from_dict(data)
	DirAccess.make_dir_recursive_absolute(folder())
	if ResourceSaver.save(made, target) != OK:
		say("Could not save %s." % target)
		return ""
	file_path = target
	rescan()
	open(target)
	return target

# ---------------------------------------------------------------- the project's items and tables

## The item ids of game/data/items, sorted.
func item_ids() -> Array[String]:
	var out: Array[String] = []
	for path in tres_files(items_dir):
		var item := ResourceLoader.load(path, "", ResourceLoader.CACHE_MODE_REPLACE) as RpgItemDefinition
		if item != null:
			out.append(String(item.id) if item.id != &"" else path.get_file().get_basename())
	out.sort()
	return out

## The loot tables a shop's wares can be: [label, table]: none, the files of `loot_dir`, the
## loot of each enemy (copied into the shop when picked), and the shop's own when it is none of
## those.
func loot_choices() -> Array:
	var out: Array = [["(none)", null]]
	for path in tres_files(loot_dir):
		var table := ResourceLoader.load(path) as RpgLootTable
		if table != null:
			out.append([path.get_file().get_basename(), table])
	for path in tres_files(enemies_dir):
		var enemy := ResourceLoader.load(path) as RpgEnemyDefinition
		if enemy != null and enemy.loot != null:
			out.append(["what %s drops" % path.get_file().get_basename(), enemy.loot])
	if shop != null and shop.wares != null and _table_index(out, shop.wares) < 0:
		out.append(["the shop's own", shop.wares])
	return out

static func _table_index(choices: Array, table: RpgLootTable) -> int:
	for i in choices.size():
		var other: RpgLootTable = choices[i][1]
		if other == table or (other != null and table != null and other.entries == table.entries):
			return i
	return -1

# ---------------------------------------------------------------- showing

func problems() -> Array[String]:
	return shop.stock_problems(item_ids()) if shop != null else [] as Array[String]

func _refresh() -> void:
	if shop == null:
		return
	_loading = true
	_id.text = String(shop.id)
	_title.text = shop.title
	_ratio.value = shop.sell_ratio
	for category: String in RpgShopDefinition.CATEGORIES:
		_check(category).set_pressed_no_signal(shop.buys.has(category))
	_restock_minutes.value = shop.restock_minutes
	_restock_each_day.set_pressed_no_signal(shop.restock_each_day)
	_funds.value = shop.funds
	_buyback.set_pressed_no_signal(shop.buyback)
	_repairs.set_pressed_no_signal(shop.repairs)
	_tables = loot_choices()
	_wares.clear()
	for choice: Array in _tables:
		_wares.add_item(str(choice[0]))
	_wares.select(maxi(0, _table_index(_tables, shop.wares)))
	_build_rows()
	_loading = false
	_problems.text = "\n".join(PackedStringArray(problems()))

func _build_rows() -> void:
	for child in _rows.get_children():
		_rows.remove_child(child)
		child.queue_free()
	var ids := item_ids()
	for i in shop.stock.size():
		var entry := shop.stock[i]
		var line := HBoxContainer.new()
		line.name = "Row%d" % i
		var picker := OptionButton.new()
		picker.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var item_id := str(entry.get("item_id", ""))
		var choices := ids.duplicate()
		if not choices.has(item_id):
			choices.push_front(item_id)  # kept, so the row says what it names
		for choice: String in choices:
			picker.add_item(choice)
		picker.select(choices.find(item_id))
		picker.item_selected.connect(func(index: int) -> void: set_row(i, "item_id", picker.get_item_text(index)))
		line.add_child(picker)
		var price := SpinBox.new()
		price.min_value = -1
		price.max_value = 1000000
		price.value = RpgUtil.to_int(entry.get("price", -1))
		price.tooltip_text = "Price (-1: the item's value)"
		price.value_changed.connect(func(value: float) -> void:
			if not _loading:
				set_row(i, "price", roundi(value)))
		line.add_child(price)
		var qty := SpinBox.new()
		qty.min_value = -1
		qty.max_value = 9999
		qty.value = RpgUtil.to_int(entry["qty"]) if entry.has("qty") else -1
		qty.tooltip_text = "How many until it restocks (-1: no limit)"
		qty.value_changed.connect(func(value: float) -> void:
			if not _loading:
				set_row(i, "qty", roundi(value)))
		line.add_child(qty)
		button(line, "Remove", func() -> void: remove_row(i))
		var problem := shop.row_problem(i, ids)
		if problem != "":
			picker.add_theme_color_override("font_color", ROW_BAD)
			picker.tooltip_text = problem
		_rows.add_child(line)

## The problem shown on stock row `index` ("" when it is fine): what the red row says.
func row_note(index: int) -> String:
	return shop.row_problem(index, item_ids()) if shop != null else ""

# ---------------------------------------------------------------- edits (one undo step each)

func _apply(value: Array) -> void:
	shop.set(str(value[0]), value[1])
	dirty = true
	_refresh()

func set_property(property: String, value: Variant) -> void:
	if _loading or shop == null or not (property in shop):
		return
	var old: Variant = shop.get(property)
	if typeof(old) == typeof(value) and old == value:
		return
	record("Edit shop", &"_apply", [property, value], [property, old])

## The stock as a new array (one undo step changes the whole list).
func _stock_copy() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for entry in shop.stock:
		out.append(entry.duplicate(true))
	return out

func _set_stock(rows: Array[Dictionary]) -> void:
	record("Edit the shop's stock", &"_apply", ["stock", rows], ["stock", _stock_copy()])

## Sets `key` of stock row `index`: item_id, price (-1: the item's value) or qty (-1: no limit,
## the key is then left out).
func set_row(index: int, key: String, value: Variant) -> void:
	if _loading or shop == null or index < 0 or index >= shop.stock.size():
		return
	var rows := _stock_copy()
	if key == "qty" and RpgUtil.to_int(value) < 0:
		if not rows[index].has("qty"):
			return
		rows[index].erase("qty")
	elif rows[index].get(key) == value:
		return
	else:
		rows[index][key] = value
	_set_stock(rows)

func add_row(item_id: String) -> void:
	if shop == null:
		return
	var rows := _stock_copy()
	var ids := item_ids()
	rows.append({"item_id": item_id if item_id != "" else (ids[0] if not ids.is_empty() else ""), "price": -1})
	_set_stock(rows)

func remove_row(index: int) -> void:
	if shop == null or index < 0 or index >= shop.stock.size():
		return
	var rows := _stock_copy()
	rows.remove_at(index)
	_set_stock(rows)

## Picks choice `index` of loot_choices() as the shop's wares (an enemy's table is copied).
func set_wares(index: int) -> void:
	if _loading or shop == null or index < 0 or index >= _tables.size():
		return
	var table: RpgLootTable = _tables[index][1]
	if table == shop.wares:
		return
	var picked: RpgLootTable = null
	if table != null:
		picked = table if table.resource_path.begins_with(loot_dir) else table.duplicate(true) as RpgLootTable
	record("Set the shop's wares", &"_apply", ["wares", picked], ["wares", shop.wares])
