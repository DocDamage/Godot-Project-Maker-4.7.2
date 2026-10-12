class_name RpgFarmStrings
extends RefCounted
## Translation keys of the farm with their English text. The translations recipe adds them to
## game/i18n/strings.tsv when the project is a farm.

const KEYS := {
	"FARM_ENERGY": "Energy",
	"FARM_TIRED": "Too tired. Eat something or sleep.",
	"FARM_FULL": "The bag is full.",
	"FARM_CAN_EMPTY": "The can is empty. Fill it at water.",
	"FARM_WRONG_SEASON": "%s does not grow in %s.",
	"FARM_ATE": "Ate %s.",
	"SEASON_SPRING": "spring",
	"SEASON_SUMMER": "summer",
	"SEASON_AUTUMN": "autumn",
	"SEASON_WINTER": "winter",
	"ITEM_HOE_NAME": "Hoe",
	"ITEM_HOE_DESC": "Tills ground into soil.",
	"ITEM_WATERING_CAN_NAME": "Watering can",
	"ITEM_WATERING_CAN_DESC": "Waters tilled soil. Fill it at water.",
	"ITEM_SICKLE_NAME": "Sickle",
	"ITEM_SICKLE_DESC": "Cuts a ripe crop, a withered one and grass.",
	"ITEM_FARM_AXE_NAME": "Axe",
	"ITEM_FARM_AXE_DESC": "Clears stumps and branches.",
	# money (T17.08)
	"FARM_BIN_PUT": "Put %s into the shipping bin.",
	"FARM_BIN_TOOK": "Took %s back out of the bin.",
	"FARM_BIN_EMPTY": "The bin is empty. Hold what you want to sell.",
	"FARM_SUMMARY_TITLE": "Sold overnight",
	"FARM_SUMMARY_TOTAL": "Total: %d %s",
	"FARM_PASSED_OUT": "You stayed up too late and passed out.",
	"FARM_PASSED_OUT_LOST": "You stayed up too late and passed out. %d %s is gone.",
	"FARM_SHOP_CLOSED": "The shop is closed. It is open from %d:00 to %d:00.",
	"FARM_SHOP_CLOSED_DAY": "The shop is closed. It is open from %d:00 to %d:00, every day but %s.",
	"FARM_WEEKDAY_0": "Monday",
	"FARM_WEEKDAY_1": "Tuesday",
	"FARM_WEEKDAY_2": "Wednesday",
	"FARM_WEEKDAY_3": "Thursday",
	"FARM_WEEKDAY_4": "Friday",
	"FARM_WEEKDAY_5": "Saturday",
	"FARM_WEEKDAY_6": "Sunday",
	# people (T17.09)
	"FARM_PEOPLE": "People",
	"FARM_PEOPLE_NONE": "You have met nobody yet.",
	"FARM_PEOPLE_HEARTS": "%d of %d hearts",
	"FARM_PEOPLE_LOVES": "Loves: %s",
	"FARM_PEOPLE_LIKES": "Likes: %s",
	"FARM_PEOPLE_DISLIKES": "Dislikes: %s",
	"FARM_PEOPLE_UNKNOWN": "Nothing is known of their taste yet.",
	"FARM_PEOPLE_BACK": "Back",
	"FARM_GIFT_LOVES": "%s loves it!",
	"FARM_GIFT_LIKES": "%s likes it.",
	"FARM_GIFT_NEUTRAL": "%s thanks you.",
	"FARM_GIFT_DISLIKES": "%s does not like it.",
	"FARM_GIFT_ENOUGH": "%s has had enough gifts this week.",
}

## The text of `key` (its translation, else the English above) with `args` filled in.
static func t(key: String, args: Array = []) -> String:
	return RpgRealtimeText.t(key, args, KEYS)

## The name of a season of the calendar ("spring").
static func season(season_name: String) -> String:
	return t("SEASON_" + season_name.to_upper())

## The name of a day of the week (RpgCalendar.weekday(): 0 is the first day of a year, "Monday").
static func weekday(day: int) -> String:
	return t("FARM_WEEKDAY_%d" % posmod(day, RpgCalendar.WEEK_DAYS))

## The name of an item as a sentence shows it.
static func item_name(item_id: StringName) -> String:
	var state := RpgUtil.state()
	var def: RpgItemDefinition = state.items.get(item_id) if state != null else null
	return RpgRealtimeText.item_name(def, item_id)
