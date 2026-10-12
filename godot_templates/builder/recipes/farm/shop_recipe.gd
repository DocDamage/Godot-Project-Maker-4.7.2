extends RefCounted
## The shop of a farm (T17.08). A farm has the shop the top-down village has
## (`game/data/shops/village_shop.tres`, which the keeper's `open_shop:village_shop` opens,
## seeded once by data_recipe while the demo is there); this makes it an RpgFarmShop: the same
## id, title and stock, with opening hours, the two tools a new game does not start with, and
## the seeds of the season, which the shop adds itself from the crops of the game.
##
## It is not a recipe of the build's list: data_recipe, which owns the file, calls `for_farm`
## for a farm (and `shop_hash` for its own hash), as it calls farm_build for what a new game
## starts with.
##
## **More stock** (feed, animals, the tools' upgrades: T17.07 and after). A thing that is
## always for sale is a row of `EXTRA_STOCK`; a thing that depends on the day or on the game
## is added while the game runs, with `RpgFarmShop.add_stock_source`.

const VERSION := 2

const SeedUtil := preload("../../lib/seed_util.gd")
const JsonUtil := preload("../../lib/json_util.gd")
const FarmBuild := preload("farm_build.gd")

## Open from 9:00 to 17:00, and closed on the last day of the week: the day the people plan
## gives the shopkeeper off. `rpggen/core/people_plan.py` (SHOP_CLOSED_DAY) is the one place the
## day is decided; `tests/unit/test_farm_config.py` holds this number and the default of
## RpgFarmShop to it.
const OPENS := 9
const CLOSES := 17
const CLOSED_WEEKDAY := 6
## Selling at the counter pays what the bin pays overnight: the item's price.
const SELL_RATIO := 1.0
## What the tools cost that a new game does not start with (FarmBuild.START_TOOLS).
const TOOL_PRICES := {"sickle": 50, "farm_axe": 120}
## Rows `{item_id, price}` that are always for sale beside the above: none yet.
const EXTRA_STOCK: Array[Dictionary] = []
## The fishing rod (T17.10): for sale where the farm has a pond and the option
## `starter_map.fishing` is on (FarmBuild.fishing(), the stored plan's `farm.forage.fishing`).
## It is not a row of EXTRA_STOCK because a farm with a well does not sell it.
const ROD_STOCK: Array[Dictionary] = [{"item_id": "fishing_rod", "price": 150}]

## What data_recipe's hash holds of the farm's shop.
static func shop_hash() -> Dictionary:
	return {"v": VERSION, "opens": OPENS, "closes": CLOSES, "closed": CLOSED_WEEKDAY, "ratio": SELL_RATIO, "tools": TOOL_PRICES, "extra": EXTRA_STOCK, "rod": rod_stock()}

## The rod's row where it is sold, else nothing.
static func rod_stock() -> Array:
	var rows: Array = []
	if FarmBuild.fishing():
		rows.append_array(ROD_STOCK)
	return rows

## The rows a farm's shop lists beside what the village shop of every kind lists.
static func farm_stock() -> Array:
	var rows: Array = []
	for tool_id in FarmBuild.TOOL_ORDER:
		if not FarmBuild.START_TOOLS.has(tool_id) and TOOL_PRICES.has(tool_id):
			rows.append({"item_id": tool_id, "price": JsonUtil.to_int(TOOL_PRICES[tool_id])})
	rows.append_array(EXTRA_STOCK)
	rows.append_array(rod_stock())
	return rows

## The farm's shop made of the village shop `shop` (an RpgShopDefinition).
static func for_farm(shop: Resource) -> Resource:
	var out := SeedUtil.make(FarmBuild.SHOP)
	out.set("id", shop.get("id"))
	out.set("title", shop.get("title"))
	out.set("buys", shop.get("buys"))
	var stock: Array = []
	var listed: Array = shop.get("stock")
	stock.append_array(listed)
	stock.append_array(farm_stock())
	out.set("stock", SeedUtil.dict_array(stock))
	out.set("sell_ratio", SELL_RATIO)
	out.set("opens", OPENS)
	out.set("closes", CLOSES)
	out.set("closed_weekday", CLOSED_WEEKDAY)
	return out
