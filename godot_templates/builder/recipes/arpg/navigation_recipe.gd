extends RefCounted
## Navigation helpers of the action-RPG recipes (T9.06). Not a recipe of its own: the TileSet's
## navigation layer is built by tileset_recipe.gd when `features.navigation` is on, and this file
## tells the enemy recipe how enemies move then.
##
## Tile-based navigation is the simple default. For large maps bake a NavigationRegion2D instead
## and keep nav_mode = "agent" (the generated README says so).

## True when the project wants agent navigation.
static func enabled(ctx) -> bool:
	return bool(ctx.config.get("features", {}).get("navigation", false))

## "agent" with navigation, else "direct" (the enemy's behavior key nav_mode).
static func nav_mode(ctx) -> String:
	return "agent" if enabled(ctx) else "direct"
