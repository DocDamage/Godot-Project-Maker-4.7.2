@tool
extends VBoxContainer
## The "Asset" panel of the library (T8.05): role, tags, collision profile, origin, footprint and
## (for characters) the FPS of each animation. "Save overrides" writes them into the catalog.

const CatalogEdit := preload("../tools/catalog_edit.gd")
const JsonIo := preload("../tools/json_io.gd")

signal saved(entry_id: String)

const ROLES: Array[String] = ["GROUND", "WALL", "CLIFF", "WATER", "ROAD", "AUTOTILE", "DECORATION", "BUILDING", "INTERIOR", "PLAYER", "NPC", "ENEMY", "BOSS", "WEAPON", "ITEM", "EFFECT", "PROJECTILE", "UI", "PORTRAIT", "BACKGROUND", "NONE"]
const PROFILES: Array[String] = ["NONE", "FULL", "BOTTOM_HALF", "BOTTOM_EDGE", "TOP_EDGE", "LEFT_EDGE", "RIGHT_EDGE", "ALPHA_POLYGON", "CUSTOM"]

var entry: Dictionary = {}
var _catalog: Dictionary = {}
var _title: Label
var _role: OptionButton
var _tags: LineEdit
var _profile: OptionButton
var _origin: Array[SpinBox] = []
var _footprint: Array[SpinBox] = []
var _fps_box: VBoxContainer
var _fps: Dictionary = {}  # animation name -> SpinBox
var _status: Label
var _save: Button

func _init() -> void:
	name = "AssetInspector"
	_title = Label.new()
	_title.text = "Select an item to edit its catalog entry."
	_title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_title)
	_role = OptionButton.new()
	for r in ROLES:
		_role.add_item(r)
	add_child(_row("Role", _role))
	_tags = LineEdit.new()
	_tags.placeholder_text = "comma separated, e.g. chest, door"
	add_child(_row("Tags", _tags))
	_profile = OptionButton.new()
	for p in PROFILES:
		_profile.add_item(p)
	add_child(_row("Collision", _profile))
	add_child(_spin_row("Origin x, y", 2, _origin))
	add_child(_spin_row("Footprint x, y, w, h", 4, _footprint))
	_fps_box = VBoxContainer.new()
	add_child(_fps_box)
	_save = Button.new()
	_save.text = "Save overrides"
	_save.pressed.connect(_on_save)
	add_child(_save)
	_status = Label.new()
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	_set_enabled(false)

func _row(label: String, control: Control) -> HBoxContainer:
	var row := HBoxContainer.new()
	var l := Label.new()
	l.text = label
	l.custom_minimum_size.x = 110
	row.add_child(l)
	control.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(control)
	return row

func _spin_row(label: String, count: int, into: Array[SpinBox]) -> HBoxContainer:
	var row := HBoxContainer.new()
	var l := Label.new()
	l.text = label
	l.custom_minimum_size.x = 110
	row.add_child(l)
	for i in count:
		var box := SpinBox.new()
		box.min_value = -4096
		box.max_value = 4096
		box.step = 1
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(box)
		into.append(box)
	return row

func _set_enabled(on: bool) -> void:
	_role.disabled = not on
	_tags.editable = on
	_profile.disabled = not on
	_save.disabled = not on
	for box in _origin + _footprint:
		box.editable = on

static func _select(button: OptionButton, text: String) -> void:
	for i in button.item_count:
		if button.get_item_text(i) == text:
			button.select(i)
			return
	button.select(0)

## The record the panel edits: the sheet object of the entry, else the asset's effective facets.
func _facets() -> Dictionary:
	var id := JsonIo.to_str(entry.get("asset_id", ""))
	var index := CatalogEdit.object_index(_catalog, id)
	if index >= 0:
		return _catalog["objects"][index]
	var asset := CatalogEdit.find_asset(_catalog, id)
	return CatalogEdit.effective(asset) if not asset.is_empty() else {}

func _is_object() -> bool:
	return CatalogEdit.object_index(_catalog, JsonIo.to_str(entry.get("asset_id", ""))) >= 0

## Shows the catalog record of a library entry.
func show_entry(p_entry: Dictionary, catalog: Dictionary = {}) -> void:
	entry = p_entry
	_catalog = catalog if not catalog.is_empty() else CatalogEdit.load_catalog()
	var facets := _facets()
	for child in _fps_box.get_children():
		child.queue_free()
	_fps.clear()
	if facets.is_empty():
		_title.text = "%s: no catalog entry (nothing to edit)." % p_entry.get("name", "")
		_set_enabled(false)
		_status.text = ""
		return
	_set_enabled(true)
	_title.text = "%s  (%s)" % [p_entry.get("name", ""), p_entry.get("asset_id", "")]
	_select(_role, JsonIo.to_str(facets.get("role", "NONE")))
	var tag_list: Array = facets.get("tags", [])
	_tags.text = ", ".join(PackedStringArray(tag_list))
	var facet_collision: Dictionary = facets.get("collision", {})
	_select(_profile, JsonIo.to_str(facet_collision.get("profile", "NONE")))
	var origin: Array = facets.get("origin", [0, 0])
	_origin[0].value = JsonIo.to_float(origin[0])
	_origin[1].value = JsonIo.to_float(origin[1])
	var footprint: Array = facets.get("footprint", [0, 0, 0, 0])
	if footprint.size() == 4:
		for i in 4:
			_footprint[i].value = JsonIo.to_float(footprint[i])
	var animations: Dictionary = facets.get("animations", {}) if not _is_object() else {}
	var names: Array = animations.keys()
	names.sort()
	for anim: String in names:
		var box := SpinBox.new()
		box.min_value = 0.5
		box.max_value = 60
		box.step = 0.5
		var anim_spec: Dictionary = animations[anim]
		box.value = JsonIo.to_float(anim_spec.get("fps", 8.0))
		_fps_box.add_child(_row("fps %s" % anim, box))
		_fps[anim] = box
	_status.text = "Status: %s" % _status_text()

func _status_text() -> String:
	var asset := CatalogEdit.find_asset(_catalog, JsonIo.to_str(entry.get("asset_id", "")))
	if not asset.is_empty():
		return JsonIo.to_str(asset.get("status", ""))
	var index := CatalogEdit.object_index(_catalog, JsonIo.to_str(entry.get("asset_id", "")))
	if index < 0:
		return ""
	var objects: Array = _catalog["objects"]
	var obj: Dictionary = objects[index]
	return JsonIo.to_str(obj.get("status", ""))

func _parse_tags() -> Array:
	var tags: Array = []
	for t in _tags.text.split(",", false):
		var tag := t.strip_edges()
		if tag != "" and not tags.has(tag):
			tags.append(tag)
	return tags

## The facet changes the panel's fields make against what the record has now (only differences).
func collect_changes() -> Dictionary:
	var current := _facets()
	var changes := {}
	var role: String = _role.get_item_text(_role.selected)
	if role != JsonIo.to_str(current.get("role", "NONE")):
		changes["role"] = role
	var tags := _parse_tags()
	if tags != current.get("tags", []):
		changes["tags"] = tags
	var profile: String = _profile.get_item_text(_profile.selected)
	var collision: Dictionary = current.get("collision", {"profile": "NONE"})
	if profile != JsonIo.to_str(collision.get("profile", "NONE")):
		var new_collision := collision.duplicate(true)
		new_collision["profile"] = profile
		changes["collision"] = new_collision
	var origin := [int(_origin[0].value), int(_origin[1].value)]
	var old_origin: Array = current.get("origin", [0, 0])
	if origin != [JsonIo.to_int(old_origin[0]), JsonIo.to_int(old_origin[1])] and (current.has("origin") or origin != [0, 0]):
		changes["origin"] = origin
	var footprint := [int(_footprint[0].value), int(_footprint[1].value), int(_footprint[2].value), int(_footprint[3].value)]
	var old_footprint: Array = current.get("footprint", [0, 0, 0, 0])
	if old_footprint.size() == 4 and footprint != [JsonIo.to_int(old_footprint[0]), JsonIo.to_int(old_footprint[1]), JsonIo.to_int(old_footprint[2]), JsonIo.to_int(old_footprint[3])]:
		changes["footprint"] = footprint
	elif old_footprint.size() != 4 and footprint != [0, 0, 0, 0]:
		changes["footprint"] = footprint
	for anim: String in _fps.keys():
		var spin: SpinBox = _fps[anim]
		var old_animations: Dictionary = current.get("animations", {})
		var old_anim: Dictionary = old_animations.get(anim, {})
		var old_fps := JsonIo.to_float(old_anim.get("fps", 8.0))
		if not is_equal_approx(old_fps, spin.value):
			if not changes.has("animations"):
				changes["animations"] = {}
			changes["animations"][anim] = {"fps": spin.value}
	return changes

func _on_save() -> void:
	var changes := collect_changes()
	if changes.is_empty():
		_status.text = "Nothing changed."
		return
	var id := JsonIo.to_str(entry.get("asset_id", ""))
	var catalog := CatalogEdit.load_catalog()
	var ok := false
	if CatalogEdit.object_index(catalog, id) >= 0:
		ok = CatalogEdit.apply_object_changes(catalog, id, changes)
	else:
		ok = CatalogEdit.apply_overrides(catalog, id, changes) != ""
	if not ok or CatalogEdit.save_catalog(catalog) != OK:
		_status.text = "Could not save the catalog."
		return
	_catalog = catalog
	_status.text = "Saved. Use Regenerate to rebuild the affected resources."
	saved.emit(id)
