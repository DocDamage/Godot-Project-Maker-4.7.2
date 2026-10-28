# M18 — Finishing what is left (release 1.5.0)

**Goal:** everything the status page still lists as left out, faulty or never built, finished in
rpggen's own code; and French taken out of the project. Asked for by the owner on 2026-10-27
("all this needs to be finished"; "i dont need french, we can completely remove it from the
project").

This file follows the format of M01–M17. It was written against the branch `gridwright` at
`c1a9b83` (PR #10, which brings the quests, shops, bag, skill trees and achievements of the
Godot kits' designs, waiting for a green CI to be merged into `main`). Like Part F of M17, these
cards are part of release 1.5.0: the gate T17.20 is closed after them.

**Not in this milestone:** T17.34 (confidence close to 100 % on real packs) waits for the
owner's review of the answer key (`F:\rpggen_scratch\answer_key`, one pack of 25 marked); its
fit, its vision rules and its measurement are done when the marks are in, as that card says.

## The ground rules (as in M13–M17)

* **Older projects regenerate unchanged.** A 1.0–1.4 project, and a 1.5 project made before a
  card, regenerates without a prompt, with nothing under `game/` changed and byte-identical
  TileSets and sprite frames. New behaviour is gated by a config key older configs lack (as
  `features.progression` is), and a recipe's hash gains a key only when what it adds applies.
  A file under `game/` is seeded only when it is missing (`SeedUtil.missing`). A map, a room or
  a farmhouse that exists is never rebuilt.
* **A runtime change that older games see** (the runtime addon is copied on every
  regeneration) is named in the runtime's CHANGELOG, as the minimap was.
* **Strict GDScript** (warnings are errors); a parse error in a base class crashes the test
  run, so the GDScript suite runs after every runtime edit.
* **Rpggen's own code.** The Godot kits are ideas only: their designs may be written again in
  rpggen's style, nothing is copied.
* **Nothing a pack draws is set aside** but copies; what a card needs to show a pack's art
  (stacking, animation, overlays) is built.
* **How the work is run:** during a card, lint, format, types, the unit and GDScript suites and
  the integration tests of what it touches; the full suites and CI once per batch (the parts
  below). Nothing on C:; scratch under `F:\rpggen_scratch\`. Each card is done when its *Done
  when* holds and what it shows was looked at in a rendered picture.

## The cards

| Card | What | Size | Depends on | Status |
|------|------|:----:|------------|--------|
| T18.01 | French out: the wizard's translation, its tooling and every mention | M | — | open |
| T18.02 | The dock's Shops tab | M | — | open |
| T18.03 | The dock's Items tab | M | — | open |
| T18.04 | Starters that show stock, restock, the shop's gold, buyback, wear and repair | M | T18.02, T18.03 | open |
| T18.05 | A farm's animal houses follow the animals the packs have | S | — | open |
| T18.06 | The *Day and night* setting is obeyed in a game with a calendar | S | — | open |
| T18.07 | Walking villagers make way for the player | M | — | open |
| T18.08 | A dialogue with many choices scrolls | S | — | open |
| T18.09 | A crop whose kind was removed can still be cleared | S | — | open |
| T18.10 | The farmer's tool strips of a pack are played | M | — | open |
| T18.11 | Working at zero energy ends the day | S | — | open |
| T18.12 | A pail for milk | S | — | open |
| T18.13 | A name for each animal | S | — | open |
| T18.14 | Crafting: recipes, stations and the crafting window (shared runtime) | L | T18.03 | open |
| T18.15 | Crafting on a farm: a workbench and what it makes | M | T18.14 | open |
| T18.16 | Cooking: a kitchen, dishes and recipes to learn | M | T18.14 | open |
| T18.17 | Children | L | — | open |
| T18.18 | Dropping onto diamonds with the mouse | M | — | open |
| T18.19 | An isometric race: a drawn car on diamonds, racers and people along the track, the Options picture | L | — | open |
| T18.20 | Height on diamonds: stacks that block and can be walked, terrains on a diamond's sides | XL | T18.18 | open |
| T18.21 | Documentation, screenshots and changelogs | M | all | open |

Order of work: Part A (T18.01), Part B (T18.02–T18.04), Part C (T18.05–T18.09), Part D
(T18.10–T18.17), Part E (T18.18–T18.20), then T18.21. Each part is one batch for the full suites
and CI.

---

# Part A — French out

## T18.01 — French out: the wizard's translation, its tooling and every mention

**Depends on:** nothing
**Files:** `rpggen/gui/i18n/` (`rpggen_fr.ts`, `rpggen_fr.qm`), `rpggen/gui/translations.py`,
`rpggen/gui/app.py`, the settings dialog (its *Language* choice), `rpggen/core/app_settings.py`,
`tools/update_translations.py`, `tools/package.py`, `packaging/rpggen.spec`,
`tests/gui/test_translations.py`, `CONTRIBUTING.md`, `docs/user_guide.md`, `docs/status.md`,
`docs/spec/00_START_HERE.md`, the CHANGELOG, `godot_templates/tests/unit/test_languages.gd`

French is the only translation the wizard has, so with it the machinery goes too.

**Spec**
* **The wizard.** `rpggen_fr.ts` and `rpggen_fr.qm` are deleted, and so is the folder. So are
  `translations.py` (`install`, `choose`, `display_name`), its call in `app.py`, the *Language*
  choice of the settings dialog, `tools/update_translations.py` and its tests, the `.qm` step
  of `tools/package.py` and the `I18N` data of `rpggen.spec`.
* **The setting.** `app_settings.language` is dropped from what is written. A settings file
  that still has it loads without error or warning (the key is ignored), so a user's settings
  survive the update.
* **`tr()` stays.** The wizard's texts keep their `self.tr(...)` wrappers: without a translator
  Qt returns the text as written, and taking them out would touch every page for nothing.
* **Mentions.** Every French line of the docs goes: the CONTRIBUTING section on translations,
  the user guide's wizard language setting, *The French file has the new wizard texts of M16/M17
  unfinished*, the T12.56 manual row (a native speaker's review), and the known fault about the
  Options page texts passed to `tr()` as constants (it was only about extraction for French).
* **The games.** A generated game's languages (T12.56: tables in `generated/i18n`, the
  *Language* choice of the game's settings) are not French and stay: they are how a user
  translates their own game. The runtime's test fixture that happens to be French
  (`test_languages.gd`, `_french()`) becomes a test locale with made-up texts, so no French is
  left in the repository. (The owner's word of 2026-10-27: the games' languages stay.)

**Done when**
* `git grep -i -E "french|rpggen_fr|\"fr\"|'fr'|fran.ais"` finds nothing outside third-party
  files and the history (the CHANGELOG says French was removed).
* The wizard starts and runs a generation with an old settings file that has `language: "fr"`.
* The frozen build has no `i18n` folder; the unit, GUI and GDScript suites pass.

---

# Part B — Shops and items in the dock

## T18.02 — The dock's Shops tab

**Depends on:** nothing
**Files:** `godot_templates/addons/rpg_project_tools/dock/shop_tab.gd` (new), the dock's tab
list, `addons/rpg_runtime/data/shop_definition.gd` (`to_dict`, `from_dict`),
`godot_templates/tests/unit/test_progression_tools.gd` (or a new `test_shop_tab.gd`)

Shops gained stock, restock, their own gold, rolled wares and buyback in 427b2c4; today these
are set only in Godot's inspector.

**Spec**
* A tab like the Skills, Achievements and Item sets tabs (`data_tab.gd`'s file row, status line,
  one undo step a change, Export and Import JSON), over `game/data/shops/*.tres`.
* Fields: the title key; the stock as rows (an item picked from `game/data/items`, its price,
  its quantity, empty for no limit); the sell ratio; what the shop buys (categories); restock
  every N game minutes or each day; the shop's gold (−1 for none); the rolled wares (a loot
  table picked from the project's); buyback on or off.
* A row whose item does not exist is shown in red with the reason, as VAL-034 reports it.

**Done when**
* A GDScript test opens the starter shop in the tab, changes a quantity, the restock and the
  gold, saves, and reads the same values back from the file; undo restores the old ones.

## T18.03 — The dock's Items tab

**Depends on:** nothing
**Files:** `dock/item_tab.gd` (new), `addons/rpg_runtime/data/item_definition.gd` (`to_dict`,
`from_dict`), tests

**Spec**
* Over `game/data/items/*.tres`, with the same file row and undo: id, name and description keys
  (with the text of `strings.tsv` shown beside them), icon, category, stack size, value, the
  equipment's modifiers as rows, ranged, the use effect and its amount, what it cures, the
  battle fields of a turn-based game (shown only in one), and the group *Wear and sets*:
  durability (0 for an item that never wears) and the set (picked from `game/data/item_sets`,
  with a link to the Item sets tab).
* A new item gets its keys added to `strings.tsv` with its English text.

**Done when**
* A test gives the starter sword a durability and the traveler's set from the tab, saves, and the
  game's bag reports both (`Inventory` slot data and `ItemSet` bonus).

## T18.04 — Starters that show stock, restock, the shop's gold, buyback, wear and repair

**Depends on:** T18.02, T18.03
**Files:** `godot_templates/builder/recipes/data_recipe.gd` (the starter shop and items),
`addons/rpg_runtime/data/shop_definition.gd`, `ui/shop_menu.gd`, `ui/strings.gd`, the smoke steps
of `smoke_steps_m6.gd`, tests

A new project's shop uses none of the new fields, so nobody sees them.

**Spec**
* **Behind `features.progression`** (on for a new project; older configs lack it, so their
  shop is unchanged): the starter shop is seeded with a limited quantity of potions that
  restock each day, gold of its own, and buyback on; the starter sword has a durability.
  Seeded only when the file is missing; the hash key `starter_shop: 2` only when it applies.
* **Repair (new; kept at the owner's word of 2026-10-27):** a shop with `repairs: true` lists
  worn gear and mends it for gold (a share of the value by the wear). Without it, gear that wears
  out would only ever break. The starter smith repairs.
* Smoke step `shop_stock_and_repair`: buy the last potion, see *Sold out*, sleep or wait a day,
  see it again; wear the sword, repair it.

**Done when**
* The step passes on the sample in each kind that has a shop (turn-based, action RPG, farm), and
  a 1.4 project regenerated has a byte-identical `game/data/shops/` folder.

---

# Part C — The faults that were left

## T18.05 — A farm's animal houses follow the animals the packs have

**Depends on:** nothing
**Files:** `rpggen/core/farm_plan.py` (`ANIMALS`, the default of `animals`),
`rpggen/core/animal_plan.py`, the Options page's farm section, `tests/unit/test_animal_plan.py`,
`tests/unit/test_farm_plan.py`

Today the option is *none*, *coop* or *coop and barn*. On a pack that has only cows the coop is
built and stays empty, and with *coop* the cows are never used.

**Spec**
* A new value `auto`, the default of a **new** farm: the houses are the ones whose animals the
  packs have (a hen, a chicken or a duck for the coop; a cow, a sheep, a goat or a pig for the
  barn), the coop first. `barn` is added as a choice of its own.
* With a choice whose house no animal of the packs lives in, the Options page says so under the
  choice (*The packs have no animal for the coop*) and offers `auto`; the generation still does
  what was chosen, and its note stays.
* A farm that has a stored plan keeps its houses (`for_project` already never plans again).
  An older config with `coop_and_barn` means what it meant.

**Done when**
* A cows-only synthetic pack makes a farm with a barn and no coop by default; the unit tests
  cover the four choices on a hens-only, a cows-only, a mixed and an animal-less pack.

## T18.06 — The *Day and night* setting is obeyed in a game with a calendar

**Depends on:** nothing
**Files:** `addons/rpg_runtime/core/settings.gd`, `world/day_night.gd`, `world/calendar.gd`,
`ui/settings_menu.gd`, `godot_templates/tests/unit/test_day_night.gd`

Today `RpgCalendar.drives_light` makes the outdoor light follow the calendar whatever the
player's *Day and night* setting says.

**Spec**
* The setting has a default per game: on in a game with a calendar (a farm), off elsewhere, as
  before. `settings.cfg` stores it only once the player changes it; until then the game's
  default applies (`RpgSettings.day_night_on()`).
* With it off in a farm, the outdoor light stays full day while the calendar's time, its night
  warnings, closing times and the passing out at 2:00 go on as before; weather tints still apply.
* The settings menu shows the toggle in a farm too, pressed by default there.

**Done when**
* GDScript tests: a farm with no stored setting dims at night; after turning it off, noon and
  midnight have the same light; a top-down RPG is unchanged.

## T18.07 — Walking villagers make way for the player

**Depends on:** nothing
**Files:** `addons/rpg_runtime/actors/schedule.gd`, `actors/npc.gd`, the player's scene recipe
(an avoidance obstacle), tests

Today a villager walking its schedule pushes into the player and stands there until its walk
times out, then jumps to its place.

**Spec**
* While walking, the villager looks a short way ahead along its path (a shape cast the size of
  its body). When the player is there it slows, then steps aside: with navigation on, through
  the navigation's avoidance (the player is an obstacle of the map, `NavigationObstacle2D`); without
  it, a step to the free side of the path and back onto it.
* If the way is still blocked after `WAIT_S` (1.5 s), it waits facing the player, and asks for a
  new path once the player moves. Its walk timeout counts only time it was free to walk, so a
  villager is not teleported because the player stood in a doorway.
* Villagers do the same for each other.

**Done when**
* A GDScript test puts the player in a corridor a villager has to walk: the villager goes round
  where there is room, waits where there is none, and arrives once the player steps away;
  never overlaps the player's body.

## T18.08 — A dialogue with many choices scrolls

**Depends on:** nothing
**Files:** `addons/rpg_runtime/ui/dialogue_box.gd`, tests

**Spec**
* The box grows upward to at most `MAX_SHARE` (0.7) of the screen's height. When the choices
  need more, they scroll: the container `%Choices` sits in a `ScrollContainer` with
  `follow_focus`, so the keyboard and the gamepad bring the focused choice into view, and the mouse
  wheel scrolls.
* Done by the runtime when the box opens, not by the scene recipe, so an older game's scene
  (which has no scroll container) gets it too and no scene file changes.

**Done when**
* A test opens a line with 20 choices on a 640 x 360 window: the box is no taller than the share,
  choice 20 can be reached with the down key and is visible when focused.

## T18.09 — A crop whose kind was removed can still be cleared

**Depends on:** nothing
**Files:** `addons/rpg_runtime/archetypes/farm/field.gd`, `crop.gd`, `crop_data.gd`, tests

Today a crop standing in a saved game whose kind was taken out of `crops.json` stays and cannot
be picked or cleared.

**Spec**
* When a field loads a cell whose crop is not in the crop data, it shows the crop's last saved
  picture, withered (greyed), and the cell is clearable by hand, the hoe or the scythe, giving
  nothing. The first one the player meets says *This crop is no longer grown here.*
* The night's growth skips it, as now; nothing is lost from the save until it is cleared.

**Done when**
* A test saves a field with berries, removes `berry`, loads, clears the cell and plants
  something else in it.

---

# Part D — The farm

## T18.10 — The farmer's tool strips of a pack are played

**Depends on:** nothing
**Files:** `rpggen/core/catalog.py` (`_farm_use_strips`), the sprite frames recipe,
`godot_templates/builder/recipes/farm/farmer_recipe.gd`, `addons/rpg_runtime/archetypes/farm/farmer.gd`,
`tools.gd`, tests with the `ranch` synthetic pack

Today a strip like `farmer_hoe_down_16x16_3frames` is read, tagged `use_anim:hoe` and `of:<the
farmer>`, and set aside. The farmer then shows the tool's icon over its hands.

**Spec**
* The build adds such strips to the owner's `SpriteFrames` as `<tool>_<direction>`
  (`hoe_down`, `water_left`, ...), which the farm's tools already look for
  (`RpgFarmTool.animation`). The words map onto the farm's tools: hoe; water and watering can for
  the can; axe; pickaxe; sickle and scythe for the scythe; rod for fishing; any other word is
  added under its own name, for a tool a user adds.
* A strip of the player of another kind (a turn-based hero swinging) is added the same way as
  its `attack_<direction>` when the player has no attack.
* The strips stay out of the people of the village and the dock's list of characters, as now;
  their tag says *played as the farmer's hoe*.
* Older farms: the player's sprite frames gain animations, so this is behind a hash key that
  exists only when the pack has such strips; a pack without them builds byte-identical frames.

**Done when**
* On the `ranch` pack the farm's smoke sequence hoes, waters and chops with the strips' frames
  (checked in the step: the animation played is `hoe_down`, not the icon), looked at in pictures.

## T18.11 — Working at zero energy ends the day

**Depends on:** nothing
**Files:** `archetypes/farm/energy.gd`, `farmer.gd`, `day_end.gd`, `farm_strings.gd`, tests

**Spec**
* At zero energy the farmer is slow and tools do nothing (as now). Trying to use a tool at zero
  energy a second time says *You are exhausted* and offers to go home; a third time, or once
  `EXHAUST_MINUTES` (60) of game time have passed at zero, the farmer passes out and the day ends
  as at 2:00 (woken at the bed, a small share of gold lost, next morning's energy reduced).
* An option of the farm, *Exhaustion ends the day*, on for a new farm; older configs lack it and
  keep today's behaviour.

**Done when**
* A GDScript test drains the energy, uses the hoe until the day ends, and checks the morning.

## T18.12 — A pail for milk

**Depends on:** nothing
**Files:** `archetypes/farm/tools/` (a new tool), `animal_product.gd`, `animal_plan.py`
(`collect: BY_HAND`), the farm's shop recipe, the drawn kit (`farm_kit.py`), tests

**Spec**
* A cow's or goat's milk is collected with a pail (sheep with shears, the same tool family) from
  an animal that is ready; by hand it does nothing and says *You need a pail*. The pail is sold at
  the farm's shop and is in the farmer's bag at the start of a farm with a barn.
* Its icon is the pack's when one is named pail, bucket or milk can; else drawn in the kit.
* Behind the farm option that has the barn: a farm without milk animals has no pail.

**Done when**
* The farm's smoke sequence on a pack with cows milks one with the pail and ships the milk.

## T18.13 — A name for each animal

**Depends on:** nothing
**Files:** `archetypes/farm/animal.gd`, `animal_house.gd`, `archetypes/farm/ui/` (a naming
dialog), `farm_strings.gd`, tests

**Spec**
* A newborn or bought animal opens a small dialog with the name the plan's list gives
  (`animal_plan.NAMES`, in the seed's order), editable with the keyboard, or with an on-screen
  keyboard on a gamepad; *OK* keeps it. The name is saved with the animal, shown when it is
  talked to and in the animals' list of the pause menu.
* Older saves: an animal without a name keeps its plan name, never asked again.

**Done when**
* A test buys a hen, names it, saves, loads, and finds the name.

## T18.14 — Crafting: recipes, stations and the crafting window (shared runtime)

**Depends on:** T18.03
**Files:** `addons/rpg_runtime/data/recipe.gd` (new, `RpgRecipe`), `data/recipe_book.gd`
(new), `core/crafting.gd` (new), `world/station.gd` (new), `ui/crafting_menu.gd` (new), the
UI recipes, `game_state.gd` (save), `dock/recipe_tab.gd` (new), the config key
`features.crafting`, the validator (ids), tests

Designed after the owner's crafting kit (ideas only): written in rpggen's style, on rpggen's
inventory.

**Spec**
* **A recipe** (`game/data/recipes/*.tres`): id, name key, ingredients `{item: qty}`, results
  `{item: qty}`, a station id or none (by hand), a time in game minutes (0: at once), a category,
  how it is learned (known, taught, or found when every ingredient has been held once) and a
  hint for one not yet known.
* **Crafting** is one `Inventory.transact` (427b2c4): the ingredients are taken and the results
  given together or nothing changes; a full bag is *Not enough room* before anything is taken.
* **A station** (a workbench, a stove, a forge...) is a map object with a queue: each queued
  craft takes its time (game minutes with a calendar, seconds without), results wait in its tray
  when the bag is full, and cancelling gives back the ingredients of what is not finished. The
  queues and the trays are saved.
* **The window**: a tab by hand and one for the station in use; the recipes as a grid with the
  known ones, unknown ones as silhouettes with their hint; *Craftable now*; the ingredients had
  and lacking; an amount; Craft or Queue; the queue with progress; Collect all. Keyboard, mouse
  and gamepad, as the other menus. Pause → Crafting when crafting by hand is possible.
* **The dock's Recipes tab**, as the other data tabs, with item pickers.
* **Validator** (VAL-034's checks): every item a recipe names exists; every station a recipe
  names is on a map or in the farm plan.
* **Behind `features.crafting`**, on for a new project of a kind that has a bag (turn-based,
  action RPG, farm); a starter recipe seeded for each (a potion by hand from two herbs).
* Achievements and quests can count crafts (`crafted:<item>` atoms beside the existing ones).

**Done when**
* GDScript tests cover all-or-nothing, the tray, cancelling, discovery and saving; the smoke
  step `craft_by_hand` makes the starter recipe in each kind.

## T18.15 — Crafting on a farm: a workbench and what it makes

**Depends on:** T18.14
**Files:** the farm's map recipe (the workbench beside the farmhouse), `crops.json`-like
`game/data/recipes/` seeds, `archetypes/farm/` (sprinkler, chest, scarecrow), the drawn kit,
`farm_plan.py`, tests

**Spec**
* A new farm has a workbench beside the farmhouse (the pack's when one is named workbench,
  bench or table; else drawn). Wood and stone come from clearing stumps, branches and rocks
  (each gives its material, where it gives nothing today).
* Seeded recipes: a fence piece, a chest (storage of its own, saved), a sprinkler (waters the
  four cells round it each morning), a scarecrow (keeps crows off a radius, if crows are on), a
  path stone, a preserves jar (a crop into a jar worth more, after a day).
* Placing a crafted thing is the farmer's *use* on the tile ahead with the thing held.

**Done when**
* The farm's smoke sequence clears a stump, crafts and places a sprinkler, and finds its cells
  watered the next morning.

## T18.16 — Cooking: a kitchen, dishes and recipes to learn

**Depends on:** T18.14
**Files:** the farmhouse's room recipe, `archetypes/farm/` (food), the recipes seeds, tests

**Spec**
* **A kitchen** is a station: the pack's stove or oven when named, else drawn. It is put in a
  **new** farmhouse's room (the room is planned with it); a farmhouse that exists gets it only
  where the room has a free cell by the wall, else a stove is sold at the shop to place.
* **Dishes** are items made of crops, fish, eggs, milk and forage: each restores more energy than
  its parts eaten raw and sells for more. Seeded: about ten, from what the farm's plans grow and
  catch (only dishes whose ingredients the farm can get are seeded).
* **Recipes are learned** from people (a gift of a heart level), a festival, and one known at the
  start; the window shows the unknown ones as silhouettes.
* Behind a farm option *Cooking*, on for a new farm.

**Done when**
* The smoke sequence cooks the known dish at the stove, eats it, and checks the energy.

## T18.17 — Children

**Depends on:** nothing (Marriage, T17.26, is in)
**Files:** `archetypes/farm/marriage.gd`, a new `archetypes/farm/child.gd`, the farmhouse's
room recipe (a crib), `people_plan.py`, `iso_kit.py` and the farm kit (a child stand-in), the
farm's strings, tests

**Spec**
* **Behind a farm option *Children***, on for a new farm with marriage. Some days after the
  wedding (at a heart level with the spouse), the spouse asks; a yes, and a child is born
  `CHILD_DAYS` (14) later.
* **The crib**: a new farmhouse's room is planned with room for it; an existing one gets it on a
  free cell by the wall, else the child sleeps in the spouse's bed space.
* **Growing**: a baby in the crib (it can be held and talked to), then after `TODDLER_DAYS` a
  child who walks the farmhouse, then the yard by day. At most two.
* **The picture**: a child of the pack (an NPC named child, kid, boy, girl, baby) else a drawn
  stand-in in the pack's style and size (a smaller villager), on squares and diamonds. Not set
  aside: the pack's own art first.
* Saved, and shown in the pause menu's family list.

**Done when**
* The smoke sequence, given the hearts as the marriage step is, has a child born and finds it in
  the crib, then walking indoors.

---

# Part E — Isometric

## T18.18 — Dropping onto diamonds with the mouse

**Depends on:** nothing
**Files:** `addons/rpg_project_tools/plugin.gd` (`_handles`, `_forward_canvas_draw_over_viewport`),
`dock/asset_dock.gd`, `dock/placement.gd`, a windowed editor test
(`tests/integration/level_probe/` or a new `editor_drop_probe`)

The placement on diamonds is built and tested (T17.27), but only through the dock's own call;
the mouse path (the editor instances the dragged scene, the dock moves it) has never run.

**Spec**
* **While a dock item is dragged over an isometric map**, the 2D editor shows the diamond (or
  every cell of a larger footprint) it will stand on, and on a raised cell the height it will
  stand at, drawn over the viewport.
* **The drop** goes through `_fix_dropped` as on squares: the instance stands on the middle of
  the diamond, sorted, and is one undo step with the editor's own instancing (one *Ctrl+Z*
  removes it).
* **A test in a windowed editor** (Windows locally; Ubuntu under `xvfb-run` in CI) sends a real
  drag and drop of an item from the dock to the 2D viewport (`Input.parse_input_event` on the
  viewport) and checks where the instance stands.

**Done when**
* The windowed test passes on squares and on diamonds, and the owner's manual row (drop five
  things into an isometric map with the mouse) is added to the gate.

## T18.19 — An isometric race: a drawn car on diamonds, racers and people along the track, the Options picture

**Depends on:** nothing
**Files:** `rpggen/core/iso_kit.py` (a car in headings, people), `rpggen/core/arcade_kit.py`,
`godot_templates/builder/recipes/racing/` (`car_recipe.gd`, `iso_track.gd`, a new people recipe),
the Options page's preview, tests

Today a pack without an isometric car gets the kit's car drawn from above, which looks flat on
diamonds, and no race has any people.

**Spec**
* **A drawn isometric car**: a body drawn from integer arithmetic in sixteen headings as seen at
  the view's angle (a box with a cabin, wheels and shading, in the pack's diamond size), used
  when the packs have no car of eight or more headings. The rivals are its colours.
* **People along the track** (both views; the owner's word of 2026-10-27: spectators, a marshal
  and a podium, and also the racers): spectators behind the barriers of the straights, a flag
  marshal at the start line who waves the start and the last lap, three on the podium at the end
  of a cup. They stand, cheer (a two-frame bob) and never block the track.
* **The racers are people.** Each car of the race, the player's and every rival's, has a driver:
  a person with a name and a face. Before the start the drivers stand beside their cars on the
  grid and get in when the lights begin. The race's standings and the cup's table show each
  driver's name and portrait beside the car. The podium's three are the drivers who finished
  first, second and third, the player among them when they did. The championship
  (`championship.gd`) keeps its drivers from race to race, and a rival's driving (`rival.gd`) can
  differ a little by driver (bolder or more careful), seeded.
* **Where the people come from:** the pack's people when it has any (NPCs and players, on
  diamonds or seen from above to match the view), a driver chosen for each car by the seed with
  no person used twice while there are enough; else the kit's villager stand-ins in the colours
  of their car. Portraits are the pack's when it has them, else the person's first standing
  frame, enlarged.
* **The Options page's picture** of a race with the *View* set to isometric is drawn on diamonds,
  not from above.
* Older races: the people and the drivers are behind a racing option *Racers and spectators*, on
  for a new race; a race without it is as before.

**Done when**
* The racing smoke sequence on the synthetic isometric pack (no car) drives the drawn car; the
  drivers stand at their cars before the start, the standings name them, and the podium shows
  the first three of the race.
* Pictures show the grid with its drivers, people along the track and the podium, in both views.

## T18.20 — Height on diamonds: stacks that block and can be walked, terrains on a diamond's sides

**Depends on:** T18.18
**Files:** `addons/rpg_runtime/world/iso.gd` (`RpgIso`), `actors/actor.gd`, the player and
enemies of the top-down kinds, `godot_templates/builder/lib/iso_tileset.gd`, the height layers
(`addons/rpg_project_tools/tools/height_layers.gd`), the tile set's physics layers, the navigation,
`rpggen/core/terrain/iso.py`, the level probe, tests

Today blocks, ramps and storeys are drawn on height layers (Gridwright), but an actor walks
through them as if the ground were flat; a raised ground does not block; a cliff's side is not a
terrain.

**Spec**
* **Levels.** Each height layer is a level (its `rpg_height` px). An actor has a level (0 on the
  ground). Its picture is drawn `level height` px up and sorts with the cell it stands on, as a
  placed thing on a raised cell already does.
* **Blocking.** The side of a block one level or more above the actor blocks it (a collision
  shape per raised cell, on a physics layer of that level). The edge of a raised area blocks an
  actor standing on it from walking off, except where a ramp or stairs lead down.
* **Ramps and stairs** (tile data `ramp: [from, to, direction]`, set by the reader from the kits'
  ramp pieces and by the dock's *World tools*): walking up one changes the actor's level as it
  crosses, with its picture rising smoothly.
* **Navigation per level**, so villagers, animals and enemies walk up ramps and around blocks;
  an enemy chases only on its own level or by a ramp.
* **Shots and swings** of the action RPG hit what is on the same level (or one below, falling);
  a turn-based encounter starts only on the same level.
* **Terrains on a diamond's sides**: the reader takes the side pieces of the kits and packs
  (cliff faces, block sides, in their turns) as a terrain of sides, and the builder and the Terrain
  tool paint a raised area's visible sides with them, so a hill has its faces instead of a hard
  edge.
* **Older isometric projects**: maps without height layers are unchanged; a map with layers made
  by Gridwright gets the collision and the navigation when regenerated (the runtime CHANGELOG
  says so), since walking through them was the fault.

**Done when**
* The level probe's hill and house of three storeys are walked in a test: the player walks up the
  ramp onto the hill, cannot walk off its edge or through the house, is drawn in front of and
  behind it right; a villager walks up the ramp; an arrow shot from below does not hit an
  enemy on the hill. Looked at in pictures.

---

# Part F — Documentation and the gate

## T18.21 — Documentation, screenshots and changelogs

**Depends on:** all
**Files:** `docs/user_guide.md`, `docs/status.md`, both CHANGELOGs, the runtime's README, the
generated READMEs' templates, `docs/dev/implementation_notes.md`, the screenshots

**Spec**
* The user guide: the Shops and Items tabs, repair, crafting and cooking, children, the
  animals' houses and names, the pail, exhaustion, height on diamonds and the mouse drop, the
  race's people; French gone.
* `docs/status.md`: the lists *Not built* and *Faults that are known and left* empty but for
  what a card here says it could not do; the gate T17.20 gains the manual rows of these cards
  (crafting and cooking by hand, a child born, a mouse drop on diamonds, a hill walked, a race
  with people).
* The notes: each card's deviations, as for M17.

**Done when**
* The docs say nothing that is no longer true, and the screenshots of the new screens and tabs
  were made again.

---

## Decisions of 2026-10-27

1. **The games' own languages stay** (T18.01): only the wizard's French and every mention of
   French go.
2. **People for a race** (T18.19) are spectators, a flag marshal, a podium, and the racers
   themselves as people.
3. **Repair is kept** (T18.04).
4. **The cards are a plan only**: no card is started until the owner says so.
