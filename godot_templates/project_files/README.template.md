# {project_name}

This is a Godot game project made with rpggen. It is a **{archetype}** RPG starter: a small
map, a player you can walk around with, a talking NPC, a chest, a title screen, a pause menu and
saving and loading. Everything is yours to change.

- Godot version: {godot_version}
- RPG runtime version: {runtime_version}

Asset packs used in this project:

{packs_list}

## 1. Quick start

1. Install Godot {godot_version} (the standard version, not the .NET one).
2. Open the Godot Project Manager, choose **Import**, and pick this folder's `project.godot`.
3. Press **F5** (Run Project). The title screen appears; choose **New Game**.

Move with the arrow keys, WASD or a gamepad. Press the interact key next to the NPC or the chest.
Press the menu key for the pause menu.

## 2. Painting maps

1. Open `game/maps/starter_map.tscn` (double-click it in the FileSystem dock).
2. In the Scene dock, select one of the layers, for example `Ground`, `GroundDetails` or `Walls`.
3. Open the **TileMap** panel at the bottom of the editor and pick a tile from the TileSet.
4. Click or drag in the map to paint. Right-click erases.
5. Terrains (auto-tiling) are on the **Terrains** tab of the TileMap panel. Pick a terrain and paint:
   the edges and corners are chosen for you.
6. To see collision shapes while the game runs, turn on **Debug > Visible Collision Shapes**.

Walls block the player because their tiles have collision shapes. If a painted wall does not
block, check that you painted on the `Walls` layer.

## 3. Placing objects

Houses, trees, chests, signs and other objects are placed from the **Assets** dock (see
[10.1](#101-the-assets-dock)): drag one into the map and it lands under `YSorted/Entities`, snapped
and Y-sorted. You can also drag any scene from `generated/scenes/objects/` into the map yourself;
put it under the `YSorted/Entities` node so it sorts correctly in front of and behind the player.

## 4. Adding an NPC with dialogue

1. Open `game/maps/starter_map.tscn`, select the example NPC (`Npc1` under `YSorted/Entities`) and
   use **Duplicate** (Ctrl+D) to make a copy. Give the copy its own `Entity Id` in the Inspector
   (for example `starter_map_npc_002`).
2. Create a dialogue: in the FileSystem dock right-click `game/data/dialogue/`, choose
   **New Resource...**, and pick **RpgDialogueResource**. Save it there.
3. Open the dialogue resource in the Inspector and write its lines (and choices, if you like).
   Conditions such as `not flag:starter_npc.talked` and events such as `give_item:potion:1` are
   explained in `addons/rpg_runtime/README.md`.
4. Select your new NPC, and in the Inspector drag the dialogue file into its **Dialogue** slot.
5. Run the game and talk to it.

The **Dialogue** tab of the Assets dock is an easier way to write the lines: pick a file of
`game/data/dialogue/`, then edit each line's speaker, portrait, text (with a preview of its
formatting), condition, events, choices and the line it jumps to, with undo. A condition or event
the game would not understand is marked as you type. **Test** plays the conversation against a
pretend game state (tick the flags and items it should have) without touching your saves, and
**Export JSON** / **Import JSON** move a dialogue to and from a text file. Press **Save** when you
are done.

## 5. Items

1. In the FileSystem dock open `game/data/items/`.
2. Right-click, **New Resource...**, pick **RpgItemDefinition**, and save it there.
3. Fill in the id, the name, the description and the icon in the Inspector.
4. Items you save in that folder are found automatically. Give one to the player from a dialogue
   line (`give_item:<id>`), from a chest (its **Loot** list), or in the **Items** list of
   `game/data/new_game.tres`.

## 6. Customizing generated scenes

Never edit files inside `generated/` or `addons/rpg_runtime/`. They are generated-owned: rpggen
rewrites them whenever you regenerate, so your edits would be lost or set aside.

To change a generated scene, use **Scene > New Inherited Scene...**, pick the generated scene, and
save the new scene under `game/`. Make your changes there. When rpggen updates the original, your
inherited scene picks up the update and keeps your changes.

## 7. Regenerating safely

You can run rpggen again on this project, for example after changing options or updating an asset
pack. Three promises hold every time:

1. **Your painted maps stay the same.** Tiles you painted are never moved or removed.
2. **Your files are never overwritten.** Nothing in `game/` is touched. If you edited a generated
   file (this README, for instance), your version stays and the new one is written next to it
   with the extra ending `.rpggen-new`. Compare the two and keep what you like.
3. **A failed run changes nothing.** The project is built in a hidden `.rpggen_staging` folder
   first and only copied in after it passes its checks.

Before you regenerate, **close the Godot editor**; an open editor can save an old copy of a scene
over the new one. If something goes wrong, run `rpggen restore` (or press **Restore previous** in
the wizard) to bring back the version from before the last regeneration. The backups live in
`.rpggen_backups/`.

## 8. Folder layout

| Folder | What it is | Who owns it |
| --- | --- | --- |
| `game/` | Your maps, scenes, data (items, dialogue) and scripts | You |
| `generated/` | Scenes, tile sets and animations built from your packs | rpggen (generated) |
| `addons/rpg_runtime/` | The shared game code: saving, dialogue, inventory, menus | rpggen (generated) |
| `addons/rpg_project_tools/` | The editor plugin: asset library dock, content checks | rpggen (generated) |
| `assets/packs/` | A copy of your asset packs, with their licenses | rpggen (generated) |
| `rpggen/` | The generation report, settings, catalog and ownership ledger | rpggen |
| `GENERATION_REPORT.md` | What was generated, and what to review | rpggen (generated) |
| `README.md` | This file | rpggen (generated) |

`addons/rpg_runtime/`, `addons/rpg_project_tools/` and `generated/` are generated-owned. `game/` is yours.

## 9. Licenses

- The RPG runtime in `addons/rpg_runtime/` is released under the MIT-0 license: you can use it
  in any project without credit. See `addons/rpg_runtime/LICENSE`.
- Your asset packs keep their own licenses. Each pack's license files are copied next to it in
  `assets/packs/<pack>/`. Read them before you publish your game; some require credit.
  `GENERATION_REPORT.md` lists every pack, the license files found and the licence rpggen read
  from them.
- **Credits.** *Credits* on the title screen and in the pause menu lists your own lines, every
  asset pack with its author and licence, and the engine. The packs' part is generated
  (`generated/data/credits.tres`), so a regeneration updates it: correct a pack's author, URL or
  licence on rpggen's Audit page (*Packs* tab). Your own lines go in `game/data/credits_extra.tsv`
  (yours, never overwritten): one line per row, a section name, a tab, then the text, for example
  `Made by<TAB>Your name`. Rows that start with `#` are notes. An exported game shows the lines of
  the last build; a run from the editor reads the file directly.

{version_control_note}

## 10. Removing the demo

When you are ready to make your own game, open the **Assets** dock in the Godot editor, go to
its **Project** tab and press **Remove demo content**. It removes the demo NPC, chest and enemy
from the starter map, the demo house interior (when you did not change it) and the starting
items, and regeneration will not bring them back.

By hand: remove the example map, NPC and chest from `game/` (look in `game/maps/` and
`game/data/`), create your own start map and point **Start Map** in `game/data/new_game.tres` at
it. Leave `generated/` and the addons alone.

The title screen, the pause menu and saving keep working with your own maps.

## 10.1 The Assets dock

With the project open in Godot 4.7 the **Assets** dock (right side) lists every object,
building, character and enemy of your packs. Search, filter by category, and drag an item into
the 2D view (or double-click it) to place it: it goes under the map's `YSorted/Entities`, snaps
to the grid and gets an entity id. Select an item to edit its role, tags, collision, origin and
animation speed; **Regenerate affected resources** (Project tab) rebuilds what changed.
**Validate content** (Validate tab) checks entity ids, doors and dialogue; **Fix entity IDs**
repairs the map being edited. Everything the dock does can be undone in the editor, except
regeneration.

## 11. Sound

The sounds of the game are **sound slots**: a fixed list (map, battle and title music; menu
cursor, confirm and cancel; hit, attack, pick-up, chest, door, footstep, save, level-up). rpggen
filled the slots from the audio of your packs by file name; the choice is stored in
`rpggen/generator_config.json` under `sounds`, and `rpggen/sound_bank.json` (rebuilt on every
generation) maps each slot to its file. A slot without a sound stays silent and writes nothing
to the log.

* **Change a slot:** run rpggen again on this folder, open **Mapping → Sound → Edit…**, choose
  another file (▶ plays it) and generate. Nothing you edited is overwritten.
* **Map music** is the **Music Asset Id** property of the map's root node (`StarterMap`). The map
  you already have keeps what is in it; for a new map, set the property to an audio asset id
  (see `rpggen/audio_index.json`). A map without one keeps the music that is playing.
* **Volumes** are the sliders of the Settings menu (Master, Music, SFX, UI).

## 12. How the maps are connected

A new project has three maps: `starter_map.tscn`, the house `interior_1.tscn` and a second
outdoor map, `field_1.tscn`. They are joined by two kinds of door (both are the `RpgDoor` script
on an `Area2D`):

* **The house door** (the `Entrance` node inside the house object) leads to `interior_1`; the
  `Exit` door of the interior leads back to the starter map.
* **The east exit** (`starter_map_east_exit`, under `Triggers` in the starter map) sits in a gap
  in the east wall and leads to the `west_entry` spawn of `field_1`; its `field_1_west_exit`
  door leads back to the `east_entry` spawn of the starter map.

To connect your own maps, put an `RpgDoor` where the player should leave, set its **Target Map**
and **Target Spawn**, and add a spawn point with that name in the target map. The map you paint
over is yours: regenerating never changes it. **Remove demo content** in the Assets dock
removes `field_1.tscn` when you did not change it and clears the door that led to it.

## 13. Saving, autosave and game over

* **Slots.** The pause menu and the title screen offer three save slots. Slot 0 is the
  **autosave**: the game writes it when you enter a map (at most once every few seconds) and
  shows a small notice instead of playing the save sound. You can load it but not save into
  it. Turn it off with **Settings → Autosave**. A save that cannot be read falls back to its
  backup file; a game from a newer runtime is refused with a message, never half-loaded.
* **Game over.** When the player is defeated a screen offers **Continue** (the newest save, the
  autosave included; hidden when there is none), **Try again** (the start of the current map
  with full health) and **Quit to title**. The scene is `generated/scenes/ui/game_over.tscn`;
  the choices are carried out by `RpgDefeatPolicy` in `addons/rpg_runtime/combat/`.

## 14. Cutscenes

A **sequence** is a list of commands played one after another: walk a character a few tiles, turn
it, fade the screen, shake or pan the camera, show a dialogue, give an item, set a flag or a
variable, start a battle, go to another map, and branch with `if` on the same conditions the
dialogues use. While one plays, the player cannot move or open the menu.

1. Open a map and press **Add trigger area (walk in)** or **(interact)** in the Assets dock
   (Project tab). It adds an area at the centre of the view and an empty sequence file in
   `game/data/sequences/` named after it.
2. Open that file and edit **Commands**: each entry is a dictionary such as
   `{{"cmd": "move_actor", "entity": "starter_map_npc_001", "tiles": [2, 0]}}`. The full list is in
   `addons/rpg_runtime/README.md` ("Sequences") and at the top of
   `addons/rpg_runtime/events/sequence.gd`.
3. Play the map and walk in. A trigger fires once per game (untick **Once** to repeat it); a
   dialogue line can start a sequence too with the event `run_sequence:<id>`. Tick **Skippable**
   on the sequence to let the player skip it with cancel.

## 15. Keys, switches and gates

* **Gate**: Assets dock (Project tab) → **Add gate**. Set its **Key Item** (an item of the KEY
  category in `game/data/items/`) and the player opens it for good by pressing interact with the
  key in the bag. Or give it an **Open When** condition, written like the dialogue conditions
  (`flag:<entity>.<key>`, `var:<name>>=N`, `quest_done:<id>` ...): it is open while that holds.
* **Switch**: select a gate and press **Add floor switch** or **Add lever**: the switch opens that
  gate (its Open When becomes `flag:<switch id>.on`). A plate stays down once stepped on unless
  **Hold** is ticked; a lever flips each time unless **Once** is ticked.
* **Locked door**: any door between maps can have a **Key Item** and an **Entity Id** too.

Gates and switches remember their state in the save. A cutscene can open a gate by setting the
flag its condition names.

## 16. Languages

Every text of the menus is a key (`UI_NEW_GAME`) with its English text in
`game/i18n/strings.tsv` (yours, never overwritten): a tab-separated table whose first row is
`keys<TAB>en`. To translate the game, add a column headed by a locale code (`fr`, `pt_BR`) and fill
it in; regenerate, and each column becomes a translation in `generated/i18n/`. *Settings >
Language* then lists *System* (the player's own language when there is a column for it, else the
fallback, English) and every language of the table; the choice is saved with the other settings.
A key a column leaves empty shows its English text.

## 17. Your own build steps

Every `.gd` file in `game/builder_recipes/` runs after rpggen's own build steps, on every build, in
file-name order: make scenes or resources from the catalog of your packs, under `game/` (yours) or
`generated/custom/` (rebuilt each time). `example_recipe.gd` shows the shape; the rpggen
documentation (`docs/recipes.md`) lists what a recipe can use. A recipe that fails stops the build
with BUILD-002, which names its file.

## 18. Equipment and shops

* **Equipment.** An item of the category WEAPON, ARMOR or ACCESSORY can be worn: the inventory's
  **Equip** button (or the status screen) shows the choices with the stat changes in green and
  red before you confirm, and the old piece goes back to the bag. What an item changes is its
  **Modifiers** list in `game/data/items/<id>.tres` (for example `attack` +3). The new game's
  starting gear is in `game/data/new_game.tres`.
* **Shops.** A shop is a file in `game/data/shops/` (**New Resource… → RpgShopDefinition**): its
  **Stock** lists the items with a price (a price below 0 means the item's own **Value**), and
  **Sell Ratio** is what the shop pays for your items (half by default). A dialogue line with the
  event `open_shop:<shop id>` opens it when the conversation ends. The demo villager runs the
  `village_shop` after the first talk.

## 19. Quests

A quest is a file in `game/data/quests/` (**New Resource… → RpgQuestDefinition**): a title, the
**Stages** in order and the **Rewards** (gold, experience, items). Each stage has an `id`, a
`description` and `complete_when`, a condition written like the dialogue conditions
(`flag:<entity>.<key>`, `item:<id>`, ...): when it holds, the quest moves to the next stage by
itself, and after the last one it is complete and the rewards are given. A stage may also name a
`target`, the entity id of an NPC, chest or other object, which the minimap marks. Dialogue starts
and moves quests with the events `quest_start:<id>`, `quest_stage:<id>:<stage>` and
`quest_complete:<id>`, and can ask `quest_active:<id>`, `quest_done:<id>` or
`quest_stage:<id>:<stage>`. The pause menu's **Journal** lists the active and completed quests.
The demo has one, `errand`: talk to the villager, open the chest, report back.

## 20. Light and the time of day

Every map has an ambient light: daylight outdoors, dimmer in interiors (a map whose root has
**Is Interior** ticked, or whose id starts with `interior`). **Ambient Override** on the map's root
sets a colour of your own. Objects with the `light` tag (rpggen suggests it for torches, lamps,
lanterns, candles and campfires; change the tags on rpggen's Audit page or in the Assets dock) get
a light in their scene; a flame flickers, a lamp does not. **Settings → Day and night** (off by
default) lets the outdoor light follow the play time, a day every 24 minutes.

## 21. Minimap and world map

Each map in `game/maps/` gets a minimap, made by the build (`generated/minimaps/`, a pixel per
cell, the average colour of its tile), so repaint a map and regenerate (or use **Regenerate
affected resources**) to update it. In the game it shows in the top-right corner (*Settings >
Minimap* hides it) with the player, doors, unopened chests and quest targets, and the pause menu's
**Map** shows the maps visited, unseen cells covered. A quest stage marks an entity on the
minimap when it has a `target`: the entity id of an NPC, chest or other object.
