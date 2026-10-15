# {project_name}

This is a Godot project made with rpggen. {opening}

- Godot version: {godot_version}
- RPG runtime version: {runtime_version}

Asset packs used in this project:

{packs_list}

## 1. Open it

1. Install Godot {godot_version} (the standard version, not the .NET one).
2. Open the Godot Project Manager, choose **Import**, and pick this folder's `project.godot`.
3. The **RPG Project Tools** dock opens beside the editor: it lists the scenes of your packs.

## 2. A level

1. **Scene > New Scene**, choose **2D Scene**, and save it where you keep your levels (for example
   `game/levels/level_1.tscn`).
2. Add a **TileMapLayer** child and call it `Ground`. In the Inspector, set its **Tile Set** to one
   of the files in `generated/tilesets/` (drag it from the FileSystem dock).
3. Open the **TileMap** panel at the bottom of the editor and its **Terrains** tab. Pick a terrain
   (its name says its surface and the sheet it comes from, for example `dirt · Tileset Grass`)
   and paint: the edges, corners and inner corners are chosen for you, and a plain middle is
   sprinkled with the sheet's variants now and then. **Connect** mode paints areas, **Path** mode
   paints paths.
4. Paint what lies on the ground (paths, water, soil) on a second **TileMapLayer** above the first
   (for example `GroundDetails`) with the same tile set, so the ground stays under it.
5. Single tiles that are no terrain (a sign on a post, a flower) are on the **Tiles** tab.

## 3. Furnishing it

1. Add a **Node2D** called `YSorted` with **Y Sort Enabled** on, and a **Node2D** called
   `Entities` inside it, also with **Y Sort Enabled**. Things placed from the dock go there, so
   whoever stands lower on the screen is drawn in front.
2. In the **RPG Project Tools** dock, pick a building, a prop, a person, an animal or an enemy and
   click in the level to place it. It comes at the pack's own scale, with its collision, its
   animation and what it does.

## 4. What the tiles and scenes carry

- **Collision**: solid ground, walls, cliffs and water stop the player; what is walked on does not.
- **Side view**: one-way platforms (jumped through from below), ladders (the custom data
  `ladder`), hazards (`hazard`) and slopes (a sloped collision) are set on the tiles.
- **Custom data** of every tile: `asset_id` (where it comes from), `footstep` (the sound of a step).
- **Scenes** in `generated/scenes/`: buildings and props (`objects/`), people (`actors/`), enemies
  (`enemies/`). They use the scripts of `addons/rpg_runtime/`, so keep that folder.

Do not edit files under `generated/`: rpggen writes them again. Make a copy (or an inherited
scene) of what you want to change.

## 5. When the packs change

Run rpggen again into this folder with the same packs (or press **Regenerate** in the dock): the
tile sets and scenes are written again. Your levels are yours and are never touched.

## 6. Version control

{version_control_note}
