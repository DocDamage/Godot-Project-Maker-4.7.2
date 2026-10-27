class_name RpgFarmShop
extends RpgShopDefinition
## The shop of a farm (T17.08): the shop of T12.46 with the quantities of T13.11, which also
## sells **the seeds of the season** and keeps **opening hours** by the calendar. It is the
## village shop (`game/data/shops/village_shop.tres`) of a farm: `recipes/farm/shop_recipe.gd`
## makes it, the keeper's `open_shop:<id>` opens it, and selling at its counter pays at once.
##
## What it offers: its `stock` (what a shop of any kind lists: the potion, the gear, the tools a
## new game does not start with), then the seed of every crop of the game that grows in the
## season of the day, at the seed's own `value` (the crop's `seed_price`), then what the stock
## sources add. A tool the farmer has already is not offered again.
##
## **More stock** (feed, animals, tool upgrades: the cards after this one) is added without
## touching this file: `RpgFarmShop.add_stock_source(callable)`, where the callable takes the
## name of the season ("spring") and returns rows `{item_id, price}` (a price below 0, or none,
## is the item's own `value`).
##
## **A row that is no thing for the bag** (an animal, T17.07) also names `deliver`, a callable
## `func(item_id: StringName, qty: int) -> String`: buying the row pays its price and calls it
## instead of putting the item into the inventory; it returns "" or why not (the codes of
## RpgShopDefinition), and a row that was refused costs nothing.

## Every farm shop asks these for more rows; see the top of the file.
static var stock_sources: Array[Callable] = []
## Who can close every farm shop for a whole day (T17.25: a festival): `func() -> String`, what
## the keeper says on such a day, or "" on a day like any other. Nobody else sets it, and then
## the shop keeps its hours.
static var day_off: Callable = Callable()

## The hours it is open, on a clock of 24: from `opens` up to, not including, `closes`.
@export var opens: int = 9
@export var closes: int = 17
## The day of the week it stays closed (RpgCalendar.weekday(): 0 is the first day of a year),
## or -1 for a shop that is open every day. The last day of the week: the day the people plan
## gives the shopkeeper off (`rpggen/core/people_plan.py`, SHOP_CLOSED_DAY: the one place the
## day is decided; a test holds this default and the recipe's number to it).
@export var closed_weekday: int = 6
## False: the seeds of the season are not added (a shop that sells only its `stock`).
@export var seasonal: bool = true

## The crops whose seeds it sells; the game's (the mode's) when none are given (a test gives them).
var crops: RpgCropData = null

## The hours and the seasonal seeds are part of the shop's plain data (the dock's JSON).
func to_dict() -> Dictionary:
	return super().merged({"opens": opens, "closes": closes, "closed_weekday": closed_weekday, "seasonal": seasonal})

func apply_dict(data: Dictionary) -> void:
	super(data)
	opens = RpgUtil.to_int(data.get("opens", opens))
	closes = RpgUtil.to_int(data.get("closes", closes))
	closed_weekday = RpgUtil.to_int(data.get("closed_weekday", closed_weekday))
	seasonal = RpgUtil.to_bool(data.get("seasonal", seasonal), seasonal)

static func add_stock_source(source: Callable) -> void:
	if not stock_sources.has(source):
		stock_sources.append(source)

static func remove_stock_source(source: Callable) -> void:
	stock_sources.erase(source)

# ------------------------------------------------------------------ the hours

## True when a shop with these hours is open at `minute` of the day (RpgCalendar.minute: 9:00
## is 540) on the day of the week `weekday`.
static func open_at(minute: int, weekday: int, from_hour: int, to_hour: int, closed_day: int) -> bool:
	if closed_day >= 0 and weekday == closed_day:
		return false
	return minute >= from_hour * 60 and minute < to_hour * 60

## Open now by the calendar of the game. A game without a calendar has a shop without hours.
func is_open() -> bool:
	var calendar := RpgCalendar.current()
	if calendar == null:
		return true
	return day_off_reason() == "" and open_at(calendar.minute, calendar.weekday(), opens, closes, closed_weekday)

## Why no farm shop opens at all today (`day_off`: a festival), or "".
static func day_off_reason() -> String:
	return RpgUtil.to_str(day_off.call()) if day_off.is_valid() else ""

## True on a day the shop does not open at any hour: its closed day of the week, or a day off.
func closed_all_day() -> bool:
	var calendar := RpgCalendar.current()
	if calendar == null:
		return false
	return (closed_weekday >= 0 and calendar.weekday() == closed_weekday) or day_off_reason() != ""

## What the keeper says instead of showing the wares ("" while the shop is open): why it has a
## day off, else its hours.
func closed_reason() -> String:
	if is_open():
		return ""
	var why := day_off_reason()
	return why if why != "" else hours_text()

## "The shop is closed. It is open from 9:00 to 17:00, every day but Sunday."
func hours_text() -> String:
	if closed_weekday < 0:
		return RpgFarmStrings.t("FARM_SHOP_CLOSED", [opens, closes])
	return RpgFarmStrings.t("FARM_SHOP_CLOSED_DAY", [opens, closes, RpgFarmStrings.weekday(closed_weekday)])

# ------------------------------------------------------------------ the stock

func _crops() -> RpgCropData:
	if crops != null:
		return crops
	var mode := RpgFarmMode.current()
	return mode.crops if mode != null else null

## The rows of the day beside `stock`: the seeds of `season_name`, then the stock sources'.
func seasonal_stock(season_name: String) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var data := _crops()
	if seasonal and data != null:
		for crop_id in data.of_season(season_name):
			var seed_id := RpgUtil.to_str(data.crop(crop_id).get("seed", ""))
			if seed_id != "":
				out.append({"item_id": seed_id, "price": -1})
	for source in stock_sources:
		if not source.is_valid():
			continue
		for raw: Variant in RpgUtil.to_array(source.call(season_name)):
			var row := RpgUtil.to_dict(raw)
			if RpgUtil.to_str(row.get("item_id", "")) != "":
				out.append(row)
	return out

## Everything on offer today, `stock` first.
func stock_today() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	out.append_array(stock)
	out.append_array(seasonal_stock(RpgField.season_now()))
	return out

func _entry(item_id: StringName) -> Dictionary:
	for entry in stock_today():
		if StringName(str(entry.get("item_id", ""))) == item_id:
			return entry
	return {}

## Buys `qty` of an item. A row with a `deliver` (see the top of the file) is paid for and
## delivered; every other row is bought as in any shop.
func buy(game: RpgGameState, item_id: StringName, qty: int = 1) -> String:
	var handler: Variant = _entry(item_id).get("deliver")
	if not (handler is Callable):
		return super.buy(game, item_id, qty)
	var deliver: Callable = handler
	if qty <= 0 or not deliver.is_valid() or not game.items.has(item_id):
		return NOT_FOR_SALE
	var cost := buy_price(item_id, game.items) * qty
	if game.gold < cost:
		return NOT_ENOUGH_GOLD
	var refused := RpgUtil.to_str(deliver.call(item_id, qty))
	if refused != OK:
		return refused
	game.gold -= cost
	return OK

## The item ids on offer that GameState knows, in the order of `stock_today()`, without the
## tools the farmer has (a thing of which one is held and that is never sold back).
func offered(items: Dictionary) -> Array[StringName]:
	var out: Array[StringName] = []
	var state := RpgUtil.state()
	for entry in stock_today():
		var item_id := StringName(str(entry.get("item_id", "")))
		if not items.has(item_id) or out.has(item_id):
			continue
		var def: RpgItemDefinition = items.get(item_id)
		if def != null and def.category == RpgItemDefinition.Category.KEY and state != null and state.inventory.has(item_id):
			continue
		out.append(item_id)
	return out
