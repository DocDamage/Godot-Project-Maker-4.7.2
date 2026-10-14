class_name RpgCalendarPage
extends Control
## The calendar of a farm (T17.25): a season as its weeks, the day of today marked, the day of
## its festival and the birthdays in their colours, and under the weeks what each marked day is
## ("12  Egg hunt", "17  Anna's birthday"). *Earlier* and *Later* turn to the other seasons;
## `cancel` or Back closes it, once the key that asked for it is up again (so the press that
## closes the wall calendar is not the farmer's next `interact` with it).
##
## It needs no scene: `build()` makes its controls (once) and `show_season()` fills them from
## the events (`events`, else `RpgFarmEvents.current()`). It is shown in two places:
## `RpgCalendarPage.add_to(menu)` gives a pause menu its Calendar button, which opens the page
## over the menu; and the wall calendar of the farmhouse opens it over the paused game
## (`RpgFarmEvents.open_calendar`).

const BUTTON_NAME := "Calendar"
const PAGE_NAME := "CalendarPage"
const CELL_SIZE := Vector2(30, 18)
const LIST_SIZE := Vector2(230, 78)
const PLAIN := Color(0.16, 0.17, 0.22)
const TODAY := Color(0.95, 0.95, 0.9)
const FESTIVAL := Color(0.85, 0.62, 0.18)
const BIRTHDAY := Color(0.75, 0.38, 0.55)
const DARK_TEXT := Color(0.08, 0.08, 0.1)
const LIGHT_TEXT := Color(0.92, 0.92, 0.95)
## The keys that can close it: it goes when none of them is down any more.
const CLOSE_ACTIONS: Array[StringName] = [&"cancel", &"confirm", &"interact", &"ui_accept"]
## Swallowed while it is shown over the game, so that no menu opens over it.
const HELD_BACK: Array[StringName] = [&"menu"]

## The events the page shows; null: those of the running game.
var events: RpgFarmEvents = null
## The season and the year that are shown.
var season := 0
var year := 1

var _built := false
var _heading: Label = null
var _grid: GridContainer = null
var _list: Label = null
var _earlier: Button = null
var _later: Button = null
var _back: Button = null
var _cells: Dictionary = {}  # day -> ColorRect
var _marks: Dictionary = {}  # day -> "today", "festival", "birthday" or ""
var _closing := false

# ------------------------------------------------------------------ in the pause menu

## Gives a pause menu (RpgPauseMenu, or any menu with a `%Resume` button in a column of
## buttons) a Calendar button after People (else after Journal, else after Status) that opens
## the page over the menu. Returns the button; the one that is there when it was added before;
## null for a menu without the column.
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
	button.text = RpgFarmStrings.t("FARM_CALENDAR")
	box.add_child(button)
	var before: Node = null
	for other: String in [RpgPeoplePage.BUTTON_NAME, "Journal", "Status"]:
		if before == null:
			before = box.get_node_or_null(other)
	if before == null:
		before = resume
	box.move_child(button, before.get_index() + 1)
	button.pressed.connect(open_in.bind(menu))
	RpgMenuUtil.wire_vertical(RpgMenuUtil.focusables(box))
	return button

## Opens the page over a menu, as the menu's submenu when it keeps one (RpgPauseMenu does).
## Null while another submenu is open.
static func open_in(menu: Control) -> RpgCalendarPage:
	var keeps := &"_submenu" in menu
	if keeps and menu.get(&"_submenu") != null:
		return null
	var page := RpgCalendarPage.new()
	page.name = PAGE_NAME
	menu.add_child(page)
	if keeps:
		menu.set(&"_submenu", page)
		if menu.has_method(&"_on_submenu_closed"):
			page.tree_exited.connect(Callable(menu, &"_on_submenu_closed"))
	return page

# ------------------------------------------------------------------ the page

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS  # it is shown over a paused game
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	build()
	show_today()
	focus_first.call_deferred()

## Makes the controls of the page: a dimmed background and a panel with the heading, the weeks,
## what the marked days are, and Earlier, Later and Back. Once.
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
	_heading = Label.new()
	_heading.name = "Heading"
	_heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(_heading)
	_grid = GridContainer.new()
	_grid.name = "Days"
	_grid.columns = RpgCalendar.WEEK_DAYS
	_grid.add_theme_constant_override("h_separation", 2)
	_grid.add_theme_constant_override("v_separation", 2)
	box.add_child(_grid)
	_list = Label.new()
	_list.name = "List"
	_list.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_list.custom_minimum_size = LIST_SIZE
	box.add_child(_list)
	var row := HBoxContainer.new()
	row.name = "Buttons"
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_child(row)
	_earlier = _button(row, "Earlier", "FARM_CALENDAR_EARLIER", turn.bind(-1))
	_back = _button(row, "Back", "FARM_PEOPLE_BACK", ask_to_close)
	_later = _button(row, "Later", "FARM_CALENDAR_LATER", turn.bind(1))
	_earlier.focus_neighbor_right = _earlier.get_path_to(_back)
	_back.focus_neighbor_left = _back.get_path_to(_earlier)
	_back.focus_neighbor_right = _back.get_path_to(_later)
	_later.focus_neighbor_left = _later.get_path_to(_back)

func _button(row: Node, node_name: String, key: String, pressed: Callable) -> Button:
	var button := Button.new()
	button.name = node_name
	button.text = RpgFarmStrings.t(key)
	button.pressed.connect(pressed)
	row.add_child(button)
	return button

func _events() -> RpgFarmEvents:
	return events if events != null else RpgFarmEvents.current()

## Shows the season of today.
func show_today() -> void:
	var calendar := RpgCalendar.current()
	if calendar != null:
		show_season(calendar.season, calendar.year)
	else:
		show_season(0, 1)

## Turns `step` seasons on (or back; never before the first spring).
func turn(step: int) -> void:
	var at := maxi(0, (year - 1) * RpgCalendar.SEASONS.size() + season + step)
	@warning_ignore("integer_division")
	show_season(at % RpgCalendar.SEASONS.size(), at / RpgCalendar.SEASONS.size() + 1)

## Fills the page with a season of a year.
func show_season(of_season: int, of_year: int) -> void:
	build()
	season = posmod(of_season, RpgCalendar.SEASONS.size())
	year = maxi(1, of_year)
	var calendar := RpgCalendar.current()
	var length := calendar.days_per_season if calendar != null else RpgCalendar.DAYS_PER_SEASON
	_heading.text = heading_text(season, year)
	for child in _grid.get_children():
		_grid.remove_child(child)
		child.queue_free()
	_cells.clear()
	_marks.clear()
	for weekday in RpgCalendar.WEEK_DAYS:
		var head := Label.new()
		head.name = "Weekday%d" % weekday
		head.text = RpgFarmStrings.weekday(weekday).left(2)
		head.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		head.custom_minimum_size = Vector2(CELL_SIZE.x, 0)
		_grid.add_child(head)
	var found := _events()
	var rows: Array[Dictionary] = []
	if found != null:
		rows = found.season_rows(season, year)
	for day in range(1, length + 1):
		var mark := ""
		for row in rows:
			if RpgUtil.to_int(row["day"]) != day:
				continue
			if RpgUtil.to_str(row["kind"]) != RpgFarmEvents.BIRTHDAY:
				mark = "festival"
			elif mark == "":
				mark = "birthday"
		if calendar != null and calendar.season == season and calendar.year == year and calendar.day == day:
			mark = "today" if mark == "" else mark + "+today"
		_marks[day] = mark
		var cell := _cell(day, mark)
		_grid.add_child(cell)
		_cells[day] = cell
	_list.text = "\n".join(lines(rows))

## One day of the weeks: a box in the colour of what the day is, with a frame when it is today.
func _cell(day: int, mark: String) -> ColorRect:
	var cell := ColorRect.new()
	cell.name = "Day%d" % day
	cell.custom_minimum_size = CELL_SIZE
	var today := mark.ends_with("today")
	cell.color = TODAY if today else PLAIN
	var inner := ColorRect.new()
	inner.name = "Fill"
	inner.color = FESTIVAL if mark.begins_with("festival") else (BIRTHDAY if mark.begins_with("birthday") else PLAIN)
	inner.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side: String in ["left", "top"]:
		inner.set("offset_" + side, 2.0)
	for side: String in ["right", "bottom"]:
		inner.set("offset_" + side, -2.0)
	inner.visible = not today or mark != "today"
	cell.add_child(inner)
	var number := Label.new()
	number.name = "Number"
	number.text = str(day)
	number.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	number.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	number.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	number.add_theme_color_override("font_color", DARK_TEXT if mark != "" else LIGHT_TEXT)
	cell.add_child(number)
	return cell

## "Spring, year 1".
static func heading_text(of_season: int, of_year: int) -> String:
	return RpgFarmStrings.t("FARM_CALENDAR_TITLE", [RpgFarmStrings.season(RpgCalendar.season_name_of(of_season)).capitalize(), of_year])

## The marked days of a season as lines: "12  Egg hunt"; one line saying so when none is.
static func lines(rows: Array[Dictionary]) -> PackedStringArray:
	var out := PackedStringArray()
	for row in rows:
		out.append(RpgFarmStrings.t("FARM_CALENDAR_ROW", [RpgUtil.to_int(row["day"]), RpgUtil.to_str(row["text"])]))
	if out.is_empty():
		out.append(RpgFarmStrings.t("FARM_CALENDAR_NOTHING"))
	return out

## The heading, and what is listed under the weeks.
func heading() -> String:
	return _heading.text if _heading != null else ""

func listed() -> String:
	return _list.text if _list != null else ""

## How many days the weeks show, and what a day is marked as: "", "today", "festival",
## "birthday", "festival+today" or "birthday+today".
func day_count() -> int:
	return _cells.size()

func mark_of(day: int) -> String:
	return RpgUtil.to_str(_marks.get(day, ""))

func focus_first() -> void:
	if _back != null and _back.is_inside_tree():
		_back.grab_focus()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		ask_to_close()

## Over the game (not in a menu) the key of the pause menu does nothing while it is shown, and
## `cancel` is taken here, before that: a key may be both.
func _input(event: InputEvent) -> void:
	if not (get_parent() is CanvasLayer):
		return
	if event.is_action_pressed("cancel"):
		get_viewport().set_input_as_handled()
		ask_to_close()
		return
	for action in HELD_BACK:
		if InputMap.has_action(action) and event.is_action(action):
			get_viewport().set_input_as_handled()

## Closes it when the keys that can close it are up.
func ask_to_close() -> void:
	_closing = true

func _process(_delta: float) -> void:
	if not _closing:
		return
	for action in CLOSE_ACTIONS:
		if InputMap.has_action(action) and Input.is_action_pressed(action):
			return
	close()

## Closes it at once.
func close() -> void:
	queue_free()
