class_name RpgPeoplePage
extends Control
## The People page of the pause menu (T17.09): who was met, their hearts, and what is known of
## their taste (an item is known once it was given). Then the farm's animals (T18.13), each by
## its name, its kind and its hearts. One button a person; the person in focus
## is described under the list. `cancel` or Back closes it.
##
## It needs no scene: `build()` makes its controls (once) and `refresh()` fills them from the
## friendships (`friendship`, else `RpgFriendship.current()`). `RpgPeoplePage.add_to(menu)`
## gives a pause menu its People button, which opens the page over the menu.

const BUTTON_NAME := "People"
const PAGE_NAME := "PeoplePage"
const LIST_SIZE := Vector2(240, 96)
const DETAIL_SIZE := Vector2(240, 56)

## The friendships the page shows; null: those of the running game.
var friendship: RpgFriendship = null

var _built := false
var _list: VBoxContainer = null
var _detail: Label = null
var _back: Button = null
var _rows: Array[Button] = []
var _row_people: Dictionary = {}  # Button -> person id

# ------------------------------------------------------------------ in the pause menu

## Gives a pause menu (RpgPauseMenu, or any menu with a `%Resume` button in a column of
## buttons) a People button after Journal (else after Status) that opens the page over the
## menu. Returns the button; the one that is there when it was added before; null for a menu
## without the column.
static func add_to(menu: Control) -> Button:
	if menu == null:
		return null
	var resume := menu.get_node_or_null("%Resume") as Button
	if resume == null:
		return null
	var box := resume.get_parent()
	var there := box.get_node_or_null(BUTTON_NAME) as Button
	if there != null:
		return there
	var button := Button.new()
	button.name = BUTTON_NAME
	button.text = RpgFarmStrings.t("FARM_PEOPLE")
	box.add_child(button)
	var before := box.get_node_or_null("Journal")
	if before == null:
		before = box.get_node_or_null("Status")
	if before == null:
		before = resume
	box.move_child(button, before.get_index() + 1)
	button.pressed.connect(open_in.bind(menu))
	RpgMenuUtil.wire_vertical(RpgMenuUtil.focusables(box))
	return button

## Opens the page over a menu, as the menu's submenu when it keeps one (RpgPauseMenu does: it
## does not close on `cancel` while the page is open, and takes the focus back afterwards).
## Null while another submenu is open.
static func open_in(menu: Control) -> RpgPeoplePage:
	var keeps := &"_submenu" in menu
	if keeps and menu.get(&"_submenu") != null:
		return null
	var page := RpgPeoplePage.new()
	page.name = PAGE_NAME
	menu.add_child(page)
	if keeps:
		menu.set(&"_submenu", page)
		if menu.has_method(&"_on_submenu_closed"):
			page.tree_exited.connect(Callable(menu, &"_on_submenu_closed"))
	return page

# ------------------------------------------------------------------ the page

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS  # the pause menu pauses the tree
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	build()
	refresh()
	focus_first.call_deferred()

## Makes the controls of the page: a dimmed background and a panel with the heading, the list
## of the people, the description of the one in focus and Back. Once.
func build() -> void:
	if _built:
		return
	_built = true
	var dim := ColorRect.new()
	dim.name = "Dim"
	dim.color = Color(0, 0, 0, 0.85)
	dim.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(dim)
	var center := CenterContainer.new()
	center.name = "Center"
	center.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(center)
	var panel := PanelContainer.new()
	panel.name = "Panel"
	center.add_child(panel)
	var margin := MarginContainer.new()
	margin.name = "Margin"
	for side: String in ["left", "top", "right", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 8)
	panel.add_child(margin)
	var box := VBoxContainer.new()
	box.name = "Box"
	margin.add_child(box)
	var heading := Label.new()
	heading.name = "Heading"
	heading.text = RpgFarmStrings.t("FARM_PEOPLE")
	heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(heading)
	var scroll := ScrollContainer.new()
	scroll.name = "Scroll"
	scroll.custom_minimum_size = LIST_SIZE
	scroll.follow_focus = true
	box.add_child(scroll)
	_list = VBoxContainer.new()
	_list.name = "List"
	_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(_list)
	_detail = Label.new()
	_detail.name = "Detail"
	_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.custom_minimum_size = DETAIL_SIZE
	box.add_child(_detail)
	_back = Button.new()
	_back.name = "Back"
	_back.text = RpgFarmStrings.t("FARM_PEOPLE_BACK")
	_back.pressed.connect(close)
	box.add_child(_back)

## Fills the list from the friendships: a button for everybody who was met, in the order they
## were met.
func refresh() -> void:
	build()
	for row in _rows:
		_list.remove_child(row)
		row.queue_free()
	_rows.clear()
	_row_people.clear()
	var friends := _friends()
	if friends != null:
		for id in friends.met:
			var row := Button.new()
			row.name = "Person_%s" % id
			row.alignment = HORIZONTAL_ALIGNMENT_LEFT
			row.text = row_text(friends, id)
			row.focus_entered.connect(describe.bind(id))
			row.pressed.connect(describe.bind(id))
			_list.add_child(row)
			_rows.append(row)
			_row_people[row] = id
	_add_family()
	_add_animals()
	_detail.text = RpgFarmStrings.t("FARM_PEOPLE_NONE") if _rows.is_empty() else detail_text(friends, person_of(_rows[0]))
	var ring: Array = []
	ring.append_array(_rows)
	ring.append(_back)
	RpgMenuUtil.wire_vertical(ring)

## The family (T18.17): the spouse and the children, a row each.
func _add_family() -> void:
	var old := _list.get_node_or_null("Family")
	if old != null:
		_list.remove_child(old)
		old.queue_free()
	var marriage := RpgMarriage.current()
	var spouse := marriage.spouse() if marriage != null else ""
	var family := RpgFarmChildren.kids()
	if spouse == "" and family.is_empty():
		return
	var heading := Label.new()
	heading.name = "Family"
	heading.text = RpgFarmStrings.t("FARM_FAMILY")
	_list.add_child(heading)
	var lines: Array[String] = []
	if spouse != "":
		var friends := _friends()
		lines.append(RpgFarmStrings.t("FARM_FAMILY_SPOUSE", [friends.display_name(spouse) if friends != null else spouse]))
	for kid in family:
		lines.append(RpgFarmStrings.t("FARM_FAMILY_CHILD", [str(kid["name"]), RpgFarmChildren.age_of(kid)]))
	for i in lines.size():
		var b := Button.new()
		b.name = "Family_%d" % i
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		b.text = lines[i]
		var said := lines[i]
		b.focus_entered.connect(func() -> void: _detail.text = said)
		_list.add_child(b)
		_rows.append(b)

## A row for each animal of the farm (T18.13): "Dot the Hen   3 of 10 hearts".
func _add_animals() -> void:
	var old := _list.get_node_or_null("Animals")
	if old != null:
		_list.remove_child(old)
		old.queue_free()
	var herd := RpgAnimalHouse.herd()
	if herd.is_empty():
		return
	var heading := Label.new()
	heading.name = "Animals"
	heading.text = RpgFarmStrings.t("FARM_ANIMALS")
	_list.add_child(heading)
	var house := RpgAnimalHouse.current()
	for row in herd:
		var b := Button.new()
		b.name = "Animal_%d" % RpgUtil.to_int(row["id"])
		b.alignment = HORIZONTAL_ALIGNMENT_LEFT
		var kind_id := RpgUtil.to_str(row["kind"])
		var kind_name := RpgUtil.to_str(house.data.kind(kind_id).get("name", kind_id)) if house != null and house.data != null else kind_id.capitalize()
		b.text = RpgFarmStrings.t("FARM_ANIMAL_ROW", [RpgUtil.to_str(row["name"]), kind_name, RpgAnimalHouse.hearts_of(RpgUtil.to_int(row["friendship"])), RpgAnimalHouse.HEARTS])
		var said := b.text
		b.focus_entered.connect(func() -> void: _detail.text = said)
		_list.add_child(b)
		_rows.append(b)

## The buttons of the people, in order.
func rows() -> Array[Button]:
	return _rows

func person_of(row: Button) -> String:
	return RpgUtil.to_str(_row_people.get(row, ""))

## What the page says under the list.
func detail() -> String:
	return _detail.text if _detail != null else ""

## Shows what is known of a person under the list.
func describe(id: String) -> void:
	_detail.text = detail_text(_friends(), id)

func focus_first() -> void:
	var first: Button = _rows[0] if not _rows.is_empty() else _back
	if first != null and first.is_inside_tree():
		first.grab_focus()

func _friends() -> RpgFriendship:
	return friendship if friendship != null else RpgFriendship.current()

## "Anna   3 of 10 hearts".
static func row_text(friends: RpgFriendship, id: String) -> String:
	return "%s   %s" % [friends.display_name(id), RpgFarmStrings.t("FARM_PEOPLE_HEARTS", [friends.hearts(id), RpgFriendship.HEARTS])]

## The name and the hearts of a person, its birthday in a farm that has them (T17.25:
## "Birthday: spring 12") and, a line a taste, the items that were given to it: "Loves: Corn",
## "Likes: ...", "Dislikes: ...". Nothing is said of an item nobody gave.
static func detail_text(friends: RpgFriendship, id: String) -> String:
	if friends == null or id == "":
		return ""
	var lines: PackedStringArray = [row_text(friends, id)]
	var events := RpgFarmEvents.current()
	var born := events.birthday_text(id) if events != null else ""
	var tastes := 1
	if born != "":
		lines.append(born)
		tastes = 2
	var keys := {RpgFriendship.LOVES: "FARM_PEOPLE_LOVES", RpgFriendship.LIKES: "FARM_PEOPLE_LIKES", RpgFriendship.DISLIKES: "FARM_PEOPLE_DISLIKES"}
	for taste in RpgFriendship.TASTES:
		var names: PackedStringArray = []
		for item in friends.known_of(id, taste):
			names.append(RpgFarmStrings.item_name(StringName(item)))
		if not names.is_empty():
			lines.append(RpgFarmStrings.t(RpgUtil.to_str(keys[taste]), [", ".join(names)]))
	if lines.size() == tastes:
		lines.append(RpgFarmStrings.t("FARM_PEOPLE_UNKNOWN"))
	return "\n".join(lines)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		close()

func close() -> void:
	queue_free()
