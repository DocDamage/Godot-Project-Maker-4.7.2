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

Houses, trees, chests, signs and other objects are placed from the **Asset Library** dock (it
arrives with a later rpggen update). Until then you can drag any scene from
`generated/scenes/objects/` into the map. Place objects under the `YSorted/Entities` node so they
sort correctly in front of and behind the player.

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
  `GENERATION_REPORT.md` lists every pack and the license files found.

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
