# Orchard crops and individual hazards

This implements the owner's saved answer-key choices: **Use orchard crops (CROP)** and
**I want to define hazards for my game**. Those answers did not specify growth durations or
damage numbers. Growth timing below is an editable game default; hazards require an explicit
per-tile setting.

## Orchards

The current Farm RPG sheets provide eight canonical orchard crops. Each uses the unshadowed
sheet, with source hashes and inspected frame selections in `rpggen/data/orchard_layouts.json`.
The shadowed and older sheets remain available as CROP art; they do not add duplicate trees to
the crop plan. Stumps, snow, autumn foliage and white silhouette masks are excluded from the
growth strips. Coconut's seeds and sprouts come from its second row.

| Crop | Harvest season | Normal difficulty: first harvest / regrowth |
| --- | --- | --- |
| Apple | Autumn | 5 / 2 nights |
| Apricot | Spring | 5 / 2 nights |
| Cherry | Spring | 5 / 1 nights |
| Banana | Summer | 4 / 2 nights |
| Coconut | Summer | 5 / 2 nights |
| Mango | Summer | 5 / 2 nights |
| Orange | Summer | 5 / 2 nights |
| Peach | Summer | 5 / 2 nights |

Trees may be planted in any season. Juvenile trees grow without watering, including outside
their harvest season. Mature trees remain standing through winter and after harvest. Fruit
develops only during the harvest season; unpicked fruit is cleared when that season ends.
The first harvest takes the listed number of nights when growth starts in the harvest season;
a tree planted outside it waits at maturity until fruit can develop. Harvesting with a full
inventory leaves both tree and fruit intact. The established-tree flag survives saving.

The generated plan supplies `orchard: true`, `mature_stage` (the zero-based fruitless tree
frame), `days`, `regrow` and `seasons`. Edit those gameplay values in the generated game's
`game/data/crops.json`. That file is written once and existing entries take precedence over
the generated defaults. Existing world plans keep their crops and append newly discovered
orchards. Ordinary field crops retain their watering and withering rules, and the planner
keeps annual crop coverage for all four seasons.

## Individual tile hazards

In the asset detail panel, select a tile picture and set **Damages the player**, **Damage per
hit**, and **Time between hits**. For a sheet, select its zero-based tile column and row first.
An isometric tile picture has just one local tile, `0,0`; its settings follow it into the
packed atlas. Each tile is edited independently, even when the asset browser folds variants
into one card. Edits use the normal project overrides and undo history.

For example, this asset override enables one tile and leaves its neighbors alone:

```json
{
  "tile_overrides": {
    "0,0": {
      "custom": {
        "hazard": true,
        "hazard_damage": 7,
        "hazard_cooldown": 2.5
      }
    }
  }
}
```

Checking the box initially supplies 1 damage per hit with a 1-second repeat interval. These
are control defaults, not saved owner answers. The mixed elemental floor palette remains
harmless until configured. Unchecking the box or undoing the override clears its hazard on
the next build. Other tile custom data and neighboring settings are preserved.

Top-down players take the configured damage at their feet. Side-view players use their
existing body probes and damage/death behavior; the metroidvania also retains its return to
safe ground. A shared timer per player prevents stacked hits from overlapping layers or from
crossing tile boundaries. When layers overlap, the highest damage wins, with layer order
breaking equal-damage ties. Disabled map layers cannot hurt players. Existing side-view
hazards without individual settings retain their previous timing defaults.

Private validation artifacts and source-pixel comparisons are under
`D:/rpggen_orchard_hazards_20261028`; no pack artwork is included in the repository.
