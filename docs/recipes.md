# Custom recipes

A *recipe* is one step of rpggen's build: the tile sets, the characters, the menus, the starter
map... You can add your own. Every `.gd` file in your project's `game/builder_recipes/` folder
runs after rpggen's recipes, on every build (a generation, a regeneration, or *Rebuild* in the
editor's RPG Project Tools dock), one after the other in file-name order. Start the names with a
number (`10_npcs.gd`, `20_signs.gd`) to fix the order.

A new project has `game/builder_recipes/example_recipe.gd`, which does nothing until you
uncomment its lines.

## The shape of a recipe

```gdscript
extends RefCounted

const RecipeContext := preload("res://generated/builder/lib/recipe_context.gd")

func build(ctx: RecipeContext) -> void:
	for npc in ctx.assets_with_role("NPC"):
		var marker := Marker2D.new()
		marker.name = String(npc["id"]).replace(".", "_")
		ctx.save_scene(marker, "res://generated/custom/markers/%s.tscn" % marker.name)
```

* It extends `RefCounted` and has `func build(ctx) -> void`.
* It writes only under `res://game/` (your files: rpggen never rewrites them) or
  `res://generated/custom/` (rpggen's: written again on every build, so build them from your
  inputs each time, and remove them from the folder when the recipe stops making them).

## What `ctx` offers

The API below is stable for rpggen 1.x. `ctx.api_version` is `RECIPE_API_VERSION` (1); it changes
only when something here changes in a way that breaks a recipe.

| Member | What it is |
|--------|------------|
| `api_version` | `1` |
| `recipe_name` | this file's name without `.gd` |
| `config` | a copy of `rpggen/generator_config.json` (`project_name`, `archetype`, `base_tile_size`, `features`, `starter_map`, ...) |
| `rng_seed` | the project's seed: use it for random choices so that a rebuild makes the same result |
| `project_name()`, `tile_size()` | from the config |
| `assets()` | every asset of the catalog: `{id, path, kind, status, facets}`; `facets` are the effective ones (`role`, `usage`, `grid`, `frame`, `animations`, `collision`, ...) |
| `asset(id)`, `assets_with_role(role)` | one asset, or the assets with a role (`"NPC"`, `"DECORATION"`, ...) |
| `asset_file(id)` | the asset's file in the project (`res://assets/packs/...`) |
| `save_scene(root, path)` | saves `root` and its children as a scene (`root` is freed); false when it failed |
| `save_resource(resource, path)` | saves a `.tres` |
| `write_text(path, text)` | writes a text file |
| `say(message)` | a line in the build log (`rpggen/logs/godot_build.log`) |
| `fail(reason)` | stops the build after this recipe with `BUILD-002`; return from `build()` after it |

## When a recipe fails

A recipe that does not load, has no `build(ctx)`, raises a script error, writes outside the two
folders or calls `ctx.fail()` fails the build with **BUILD-002**, which names the file:
*Recipe game/builder_recipes/20_signs.gd failed: script error: ...*. Nothing is delivered (the
project stays as it was), and the log has the details. Fix the recipe, or move it out of the
folder, and generate again.

## Notes

* The recipes run headless, inside the builder: there is no scene tree to add nodes to, and no
  autoloads. Build nodes, save them, and free what you do not save.
* Your recipes are yours: they are under `game/`, so regenerating never changes them.
* The builder's other scripts (`res://generated/builder/`) are internal and may change in any
  release; use only `ctx`.
