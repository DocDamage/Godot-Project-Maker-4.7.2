class_name RpgFarmHud
extends CanvasLayer
## The HUD of a farm (T17.04, T17.11). A child of the farm's mode.
##
## * At the bottom: the hotbar with the held slot and the energy as a bar over it.
## * In the top-left corner: the time (in steps of ten minutes, "12:40"), the weekday, the day
##   and the season ("Monday 3, spring"), the weather (a word, or the packs' icon of it when
##   they have one), and the money. The basic HUD's own line of money is hidden while this one
##   is there, so the money is shown once.
## * A toast (Events.notify) for a harvest and, in the morning, for what the shipping bin paid.
## * In a farm that fights (T17.24) the farmer's health as a red bar over the energy
##   (`%HealthBar`, which only the HUD of such a farm has).
##
## The scene (recipes/farm/hud_recipe.gd) has `%EnergyBar` and `%Slots` with a child a slot,
## each with an `Icon` (TextureRect) and a `Qty` (Label), and `%Clock`, `%Date`, `%Weather`,
## `%WeatherIcon` and `%Money`. A scene without the second group (one made before T17.11) shows
## the first alone.

## Under the dialogue box (10) and the menus: the hotbar lies at the bottom, where they open.
const LAYER := 5
const HELD := Color(1.0, 1.0, 1.0, 1.0)
const NOT_HELD := Color(0.6, 0.6, 0.65, 0.85)
## The clock moves in steps of this many minutes.
const CLOCK_STEP := 10

## The packs' icons of the weather: kind ("sun", "rain", "storm", "snow") -> Texture2D. A kind
## without one is shown as its word.
@export var weather_icons: Dictionary = {}

var _mode: RpgFarmMode = null
var _field: RpgField = null

func _ready() -> void:
	layer = LAYER
	_mode = get_parent() as RpgFarmMode
	if _mode != null:  # its parts are made in its `_ready`, which runs after this one
		if _mode.is_node_ready():
			_bind()
		else:
			_mode.ready.connect(_bind)
	var bus := RpgUtil.events()
	if bus != null:
		bus.map_entered.connect(_on_map)
		bus.gold_changed.connect(_on_gold)
		bus.game_loaded.connect(_on_gold)
	var router := RpgUtil.router()
	if router != null:
		router.map_changed.connect(_on_map)
	refresh()

func _bind() -> void:
	_mode.ensure_parts()
	_mode.hotbar.changed.connect(refresh)
	_mode.energy.changed.connect(_on_energy)
	if _mode.weather != null:
		_mode.weather.changed.connect(_on_weather)
	if _mode.day_end != null:
		_mode.day_end.woke.connect(_on_woke)
	if _mode.fight != null:
		_mode.fight.health_changed.connect(_on_health)
	var calendar := RpgCalendar.current()
	if calendar != null:
		calendar.minute_passed.connect(_on_minute)
		calendar.day_began.connect(_on_day)
	watch_field(RpgField.current())
	refresh()

func _on_energy(_value: int, _maximum: int) -> void:
	refresh()

func _on_map(_id: StringName) -> void:
	watch_field(RpgField.current())
	refresh()

func _on_health(_hp: int, _max_hp: int) -> void:
	refresh_health()

## The health bar (T17.24) shows the farmer's hit points; a HUD without one shows nothing.
func refresh_health() -> void:
	var bar := get_node_or_null("%HealthBar") as ProgressBar
	if bar == null:
		return
	var now := RpgFarmFight.hit_points()
	bar.max_value = maxi(1, now[1])
	bar.value = now[0]

func _on_gold(_total: int) -> void:
	refresh_status()

func _on_weather(_kind: String) -> void:
	refresh_status()

func _on_minute(minute: int) -> void:
	if minute % CLOCK_STEP == 0:
		refresh_status()

func _on_day(_day: int) -> void:
	refresh_status()

# ------------------------------------------------------------------ the toasts

## A harvest of `field` is told by a toast from now on (the field of the map that is shown is
## watched by itself).
func watch_field(field: RpgField) -> void:
	if field == _field:
		return
	if _field != null and is_instance_valid(_field) and _field.harvested.is_connected(_on_harvested):
		_field.harvested.disconnect(_on_harvested)
	_field = field
	if _field != null:
		_field.harvested.connect(_on_harvested)

func _on_harvested(_crop_id: String, item_id: StringName, qty: int) -> void:
	RpgUtil.notify(harvest_text(item_id, qty))

## "Harvested Turnip." or "Harvested Turnip x2."
static func harvest_text(item_id: StringName, qty: int) -> String:
	var item_name := RpgFarmStrings.item_name(item_id)
	return RpgFarmStrings.t("FARM_HARVESTED", [item_name if qty <= 1 else "%s x%d" % [item_name, qty]])

## The morning is done (the summary, if there was one, is closed): what the bin paid.
func _on_woke(_how: String) -> void:
	var total := RpgUtil.to_int(_mode.day_end.last_sale.get("total", 0)) if _mode != null and _mode.day_end != null else 0
	if total > 0:
		RpgUtil.notify(sale_text(total))

static func sale_text(total: int) -> String:
	return RpgFarmStrings.t("FARM_SOLD", [total, RpgRealtimeText.t("UI_GOLD_SHORT", [], RpgStrings.KEYS)])

# ------------------------------------------------------------------ the calendar and the money

## What the clock shows at a minute of the day, in steps of CLOCK_STEP: "12:40".
static func clock_text(minute: int) -> String:
	var shown := RpgCalendar.clock_of(minute - posmod(minute, CLOCK_STEP))
	return "%d:%02d" % [shown[0], shown[1]]

## "Monday 3, spring"
static func date_text(calendar: RpgCalendar) -> String:
	return RpgFarmStrings.t("FARM_HUD_DATE", [RpgFarmStrings.weekday(calendar.weekday()), calendar.day, RpgFarmStrings.season(calendar.season_name())])

static func money_text(gold: int) -> String:
	return "%s: %d" % [RpgRealtimeText.t("UI_GOLD", [], RpgStrings.KEYS), gold]

## Shows the time, the date, the weather and the money as they are now.
func refresh_status() -> void:
	var calendar := RpgCalendar.current()
	var clock := get_node_or_null("%Clock") as Label
	var date := get_node_or_null("%Date") as Label
	if calendar != null:
		if clock != null:
			clock.text = clock_text(calendar.minute)
		if date != null:
			date.text = date_text(calendar)
	var kind := _mode.weather.today if _mode != null and _mode.weather != null else RpgFarmWeather.SUN
	var picture: Texture2D = weather_icons.get(kind)
	var icon := get_node_or_null("%WeatherIcon") as TextureRect
	if icon != null:
		icon.texture = picture
		icon.visible = picture != null
	var word := get_node_or_null("%Weather") as Label
	if word != null:
		word.text = RpgFarmWeather.text(kind)
		word.visible = picture == null or icon == null
	var state := RpgUtil.state()
	var money := get_node_or_null("%Money") as Label
	if money != null and state != null:
		money.text = money_text(state.gold)
		_hide_basic_money()
	var ground := get_node_or_null("Status") as Control
	if ground != null:
		ground.reset_size()  # no wider than its lines, when a line got shorter

## The basic HUD shows the money too: its line is hidden while this HUD has one.
func _hide_basic_money() -> void:
	var router := RpgUtil.router()
	if router == null:
		return
	for child in router.get_children():
		if child is RpgHudBasic:
			var line := child.get_node_or_null("%Gold") as Control
			if line != null:
				line.visible = false

## Shows everything as it is now. Hidden while no map is shown.
func refresh() -> void:
	var router := RpgUtil.router()
	visible = router != null and router.get("current_map") != null
	refresh_status()
	if _mode == null or _mode.energy == null or _mode.hotbar == null:
		return
	var bar := get_node_or_null("%EnergyBar") as ProgressBar
	if bar != null:
		bar.max_value = _mode.energy.max_energy
		bar.value = _mode.energy.value
	refresh_health()
	var slots := get_node_or_null("%Slots")
	if slots == null:
		return
	var state := RpgUtil.state()
	for i in slots.get_child_count():
		var slot := slots.get_child(i) as Control
		if slot == null:
			continue
		var item := _mode.hotbar.item_at(i)
		var def: RpgItemDefinition = state.items.get(item) if state != null else null
		var icon := slot.get_node_or_null("Icon") as TextureRect
		if icon != null:
			icon.texture = def.icon if def != null else null
		var qty := slot.get_node_or_null("Qty") as Label
		if qty != null:
			var count := _mode.hotbar.qty_at(i)
			qty.text = str(count) if count > 1 else ""
		slot.modulate = HELD if i == _mode.hotbar.held else NOT_HELD
