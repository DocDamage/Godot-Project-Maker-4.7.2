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
| `assets/packs/` | A copy of your asset packs, with their licenses | rpggen (generated) |
| `rpggen/` | The generation report, settings, catalog and ownership ledger | rpggen |
| `GENERATION_REPORT.md` | What was generated, and what to review | rpggen (generated) |
| `README.md` | This file | rpggen (generated) |

`addons/rpg_runtime/` and `generated/` are generated-owned. `game/` is yours.

## 9. Licenses

- The RPG runtime in `addons/rpg_runtime/` is released under the MIT-0 license: you can use it
  in any project without credit. See `addons/rpg_runtime/LICENSE`.
- Your asset packs keep their own licenses. Each pack's license files are copied next to it in
  `assets/packs/<pack>/`. Read them before you publish your game; some require credit.
  `GENERATION_REPORT.md` lists every pack and the license files found.

## 10. Removing the demo

When you are ready to make your own game, you can delete the demo content:

1. Remove the example map, NPC and chest from `game/` (look in `game/maps/` and `game/data/`).
2. Create your own start map and point **Start Map** in `game/data/new_game.tres` at it.
3. Leave `generated/` and `addons/rpg_runtime/` alone.

The title screen, the pause menu and saving keep working with your own maps.
