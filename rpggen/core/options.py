"""Pure logic of the Options page: feature dependencies, presets, layers, input bindings."""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass
from typing import Any

from rpggen import schema
from rpggen.core import config as config_mod

# feature -> the features it needs. The demo map is painted with the tile set and its villager,
# enemy and save point need their systems; the navigation layer is only read by enemies.
DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "demo": ("tilesets", "dialogue", "combat", "save"),
    "navigation": ("combat",),
}
FEATURE_DEPS = DEPENDENCIES  # the name before 1.1
RESOLUTION_PRESETS = [(320, 180), (384, 216), (480, 270), (640, 360)]
WINDOW_PRESETS = [(960, 540), (1280, 720), (1600, 900), (1920, 1080)]
# editable binding fields of the input table and the type of their entries
BINDING_FIELDS: tuple[tuple[str, type], ...] = (
    ("keys", str),
    ("mouse_buttons", int),
    ("joy_buttons", int),
)

# Every feature of config.FEATURE_KEYS: (group, label, one sentence). A test checks that none is
# missing.
FEATURE_GROUPS = ("World", "Game systems", "Tools")
FEATURE_INFO: dict[str, tuple[str, str, str]] = {
    "tilesets": (
        "World",
        "Tilesets",
        "Cuts your tile sheets into a Godot TileSet you can paint with.",
    ),
    "collision": (
        "World",
        "Collision",
        "Walls, water and tall objects block the player and the enemies.",
    ),
    "terrain": (
        "World",
        "Terrain",
        "Autotiles: terrains that join their edges and corners while you paint.",
    ),
    "animations": (
        "World",
        "Animations",
        "Builds walk, idle and attack animations from your character sheets.",
    ),
    "navigation": (
        "World",
        "Navigation",
        "Adds a navigation layer to the TileSet so enemies can path around walls. Off by "
        "default: enemies walk straight at the player.",
    ),
    "save": ("Game systems", "Save / load", "Three save slots, an autosave and a Load menu."),
    "dialogue": (
        "Game systems",
        "Dialogue",
        "A dialogue box with choices, conditions and events (items, flags).",
    ),
    "combat": (
        "Game systems",
        "Combat",
        "Battles (turn-based) or real-time fighting (action), with enemies and rewards.",
    ),
    "demo": (
        "Game systems",
        "Demo scene",
        "A starter map with a villager, a chest, an enemy, a house and a second area. You can "
        "remove it later.",
    ),
    "editor_tools": (
        "Tools",
        "Editor tools",
        "The Assets dock in the Godot editor: drag buildings, props and enemies into maps.",
    ),
    "debug_tools": (
        "Tools",
        "Debug tools",
        "An overlay with the frame rate and a few shortcuts while you test (debug builds only).",
    ),
}


def features_in_group(group: str) -> list[str]:
    """The feature keys of a group, in the order they are shown."""
    return [k for k, (g, _label, _text) in FEATURE_INFO.items() if g == group]


def feature_label(key: str) -> str:
    return FEATURE_INFO.get(key, ("", key, ""))[1]


LAYER_GROUND_REQUIRED = "The Ground layer is required."
LAYER_EMPTY = "Layer names cannot be empty."
LAYER_DUPLICATE = "Layer names must be unique."


# What a farm (M17) does not show among its features: nothing since T17.24, which gave
# ``combat`` a meaning on a farm (a cave with enemies, a weapon in the shop, health on the HUD).
FARM_HIDDEN: tuple[str, ...] = ()
# What the demo and the navigation layer of a farm do not need: the village is built and its
# people walk whether or not anybody fights.
FARM_NOT_NEEDED = ("combat",)
# The sentences of the features that mean something else on a farm.
FARM_FEATURE_TEXT = {
    "combat": "A cave beside the farm with enemies to fight, a weapon in the shop and health on "
    "the HUD. Being defeated is passing out: you wake at home.",
    "navigation": "Adds a navigation layer to the TileSet so the people of the village walk "
    "round walls to where their day takes them. Off by default: they appear where they are due.",
    "demo": "The village with a villager who keeps the shop, a chest, a house and a second "
    "area. You can remove it later.",
}


def dependencies(archetype: str = "") -> dict[str, tuple[str, ...]]:
    """``DEPENDENCIES`` as they are for a kind of game: a farm's do not name ``combat``."""
    if archetype == "farm":
        return {
            key: tuple(dep for dep in deps if dep not in FARM_NOT_NEEDED)
            for key, deps in DEPENDENCIES.items()
        }
    return DEPENDENCIES


def hidden_features(archetype: str) -> tuple[str, ...]:
    """The features the Options page does not show for a kind (their values stay)."""
    if archetype in config_mod.ARCADE_KINDS:
        return ARCADE_HIDDEN
    if archetype == "metroidvania":
        return ("navigation",)
    return FARM_HIDDEN if archetype == "farm" else ()


def feature_text(key: str, archetype: str = "") -> str:
    """The sentence of a feature, as it is true for the kind."""
    if archetype == "farm" and key in FARM_FEATURE_TEXT:
        return FARM_FEATURE_TEXT[key]
    return FEATURE_INFO[key][2]


def missing_deps(features: dict[str, bool], key: str, archetype: str = "") -> list[str]:
    """Features ``key`` needs that are currently switched off."""
    return [dep for dep in dependencies(archetype).get(key, ()) if not features.get(dep, False)]


def stages_text(archetype: str, starter_map: dict[str, Any]) -> str:
    """What an arcade kind's options make: "1 stage, scrolling up"."""
    if archetype == "shmup":
        from rpggen.core import wave_plan

        try:
            return wave_plan.describe(starter_map)
        except wave_plan.WavePlanError:
            return ""
    if archetype == "run_and_gun":
        from rpggen.core import stage_plan

        try:
            return stage_plan.describe(starter_map)
        except stage_plan.StagePlanError:
            return ""
    if archetype == "racing":
        from rpggen.core import track_plan

        try:
            return track_plan.describe(starter_map)
        except track_plan.TrackPlanError:
            return ""
    return "stages"


ARCADE_NAMES = {"shmup": "Shoot 'em up", "run_and_gun": "Run and gun", "racing": "Racing"}
# The features an arcade kind has no use for: its stages are not a demo scene one can leave
# out, and nothing in them looks for a path. The Options page does not show them and leaves
# their values as the config has them.
ARCADE_HIDDEN = ("demo", "navigation")


def _count(number: int, noun: str) -> str:
    if noun == "life":
        return f"{number} {'life' if number == 1 else 'lives'}"
    if noun == "enemy":
        return f"{number} {'enemy' if number == 1 else 'enemies'}"
    return f"{number} {noun}{'' if number == 1 else 's'}"


def arcade_numbers(archetype: str, starter_map: dict[str, Any]) -> list[str]:
    """What the summary says of an arcade kind beside its name (T16.16): "vertical", "3 stages",
    "3 lives". Nothing when the options do not fit together."""
    from rpggen.core import stage_plan, track_plan, wave_plan

    try:
        if archetype == "shmup":
            opts = wave_plan.normalized(starter_map)
            stages = opts["stages"] + len(opts["added_stages"])
            return [opts["orientation"], _count(stages, "stage"), _count(opts["lives"], "life")]
        if archetype == "run_and_gun":
            opts = stage_plan.normalized(starter_map)
            stages = opts["stages"] + len(opts["added_stages"])
            out = [_count(stages, "stage"), _count(opts["lives"], "life")]
            if opts["grapple"]:
                out.append("grapple" if opts["jump"] else "grapple, no jump")
            return out
        if archetype == "racing":
            opts = track_plan.normalized(starter_map)
            tracks = opts["tracks"] + len(opts["added_tracks"])
            return [
                _count(tracks, "track"),
                _count(opts["laps"], "lap"),
                _count(opts["rivals"], "rival"),
            ]
    except ValueError:  # the three plan errors are ValueErrors
        return []
    return []


def plan_text(archetype: str, stages: dict[str, Any], starter_map: dict[str, Any]) -> str:
    """A planned run in words, for a dry run (T16.16): "3 stages, 24 waves, 3 bosses" or
    "4 tracks of 3 laps, 3 rivals"."""
    every = stages["list"]
    if archetype == "racing":
        from rpggen.core import track_plan

        laps = int(stages.get("laps", every[0].get("laps", 3) if every else 3))
        rivals = track_plan.normalized(starter_map)["rivals"]
        return f"{_count(len(every), 'track')} of {_count(laps, 'lap')}, {_count(rivals, 'rival')}"
    waves = sum(1 for s in every for w in s.get("waves", []) if w.get("enemy") != "pickup")
    bosses = sum(1 for s in every if s.get("boss"))
    return (
        f"{_count(len(every), 'stage')}, {_count(waves, 'wave')}, "
        f"{bosses} boss{'' if bosses == 1 else 'es'}"
    )


def effective_features(wanted: dict[str, bool], archetype: str = "") -> dict[str, bool]:
    """``wanted`` with every feature whose dependencies are off forced off."""
    out = dict(wanted)
    for key in DEPENDENCIES:
        if missing_deps(out, key, archetype):
            out[key] = False
    return out


# ------------------------------------------------------------------------- a farm (T17.16)

FARM_NAME = "Farm"


def farm_crop_count(catalog: Any, projection: str = config_mod.PROJECTION_TOP_DOWN) -> int:
    """How many crops a farm of these packs will have: the ones of the packs that can grow,
    and the three drawn ones when there are fewer than two (``farm_kit.lacking``)."""
    from rpggen.core import farm_kit

    own = farm_kit.growing(catalog, projection) if catalog is not None else 0
    return own + (len(farm_kit.CROP_STAND_INS) if own < farm_kit.MIN_CROPS else 0)


def plan_farm(cfg: config_mod.GeneratorConfig, catalog: Any, project: Any = None) -> dict[str, Any]:
    """What a generation would plan for a farm, without building anything: ``map`` (the farm's
    own map, ``farm_plan``: the stored one when ``project`` has its farm, with the added maps
    it does not have yet), ``crops`` and ``people`` (how many), ``stored`` and ``notes``. Raises
    a ``ValueError`` (the planners' errors) when the options make no farm."""
    from rpggen.core import event_plan, farm_plan, orchestrator, people_plan, world_plan

    chosen = cfg.starter_map_options()
    facts = orchestrator.farm_facts(cfg, catalog) if catalog is not None else farm_plan.facts_of()
    stored = bool(project) and farm_plan.exists(project)
    # the cave of Combat is among the added maps (T17.24)
    try:
        rows = orchestrator.farm_map_options(cfg, project if stored else None)
    except ValueError as exc:
        raise farm_plan.FarmPlanError(str(exc)) from None
    section, notes = farm_plan.for_project(project if stored else None, rows, cfg.seed, facts)
    kept = ((world_plan.load(project) or {}).get("farm") or {}) if stored else {}
    crops = len(kept.get("crops") or []) or farm_crop_count(catalog, cfg.projection)
    if kept.get("people"):
        people = len(kept["people"])
    elif catalog is not None:
        who = people_plan.plan(chosen, cfg.seed, orchestrator.people_facts(cfg, catalog, {}))
        people = len(who["people"])
    else:
        people = people_plan.DRAWN_PEOPLE
    # festivals (T17.25): the stored ones, else the four a year has, none with the option off
    festivals = 0
    if chosen.get("festivals", True):
        festivals = len((kept.get("events") or {}).get("festivals") or []) or len(
            event_plan.SEASONS
        )
    return {
        "map": section,
        "crops": crops,
        "people": people,
        "festivals": festivals,
        "stored": stored,
        "notes": notes,
    }


def farm_numbers(starter_map: dict[str, Any], crops: int | None = None) -> list[str]:
    """What the summary says of a farm beside its name: "28 days a season", "a coop", "6
    crops" (the crops when somebody counted them). Nothing when the options do not fit."""
    from rpggen.core import farm_plan

    try:
        opts = farm_plan.normalized(starter_map)
    except farm_plan.FarmPlanError:
        return []
    days = starter_map.get("days_per_season", config_mod.FARM_DAYS_PER_SEASON)
    houses = farm_plan.ANIMALS[opts["animals"]]
    out = [f"{days} days a season"]
    out.append(" and ".join(f"a {house}" for house in houses) if houses else "no animals")
    if crops is not None:
        out.append(_count(crops, "crop"))
    return out


def farm_text(plans: dict[str, Any]) -> str:
    """A planned farm in words, for a dry run: "a farm of 40 x 30 with a plot of 96 cells, a
    pond, 6 crops, 5 people, 4 festivals" (``plans`` is ``plan_farm``'s; the festivals are
    left out of a farm that has none)."""
    from rpggen.core import farm_plan

    people = plans["people"]
    festivals = int(plans.get("festivals", 0) or 0)
    return (
        f"{farm_plan.summary(plans['map'])}, {_count(plans['crops'], 'crop')}, "
        f"{people} {'person' if people == 1 else 'people'}"
        + (f", {_count(festivals, 'festival')}" if festivals else "")
    )


def added_maps_text(farm_map: dict[str, Any]) -> list[str]:
    """The maps added to a farm in words, a line each, for a dry run and the wizard (T17.23):
    "Old woods: a forest of 28 x 22 with 8 places to forage", "North shore: a beach of 30 x 20
    with 6 places to forage and the sea to fish in". A name that is no map (a farm from before
    added maps were built) says so."""
    from rpggen.core import farm_plan

    out = []
    for entry in farm_map.get("added", []):
        cols, rows = entry["size"]
        text = (
            f"{entry['name']}: a {entry['kind']} of {cols} x {rows} with "
            f"{_count(len(entry.get('spots', [])), 'place')} to forage"
        )
        if entry.get("enemies"):
            text += f" and {_count(len(entry['enemies']), 'enemy')} to fight"
        out.append(text + (" and the sea to fish in" if entry.get("water") else ""))
    out += [f"{name}: a name only (the farm was made before added maps were built)"
            for name in farm_plan.names_only(farm_map)]  # fmt: skip
    return out


def default_projection(catalog: Any, archetype: str) -> str:
    """The view a new project of these packs starts with (T17.16): isometric when the kind
    has the view, the packs have isometric ground and no ground that is seen from above; from
    above otherwise."""
    from rpggen.core import iso_atlas, mapping

    top_down = config_mod.PROJECTION_TOP_DOWN
    if archetype not in config_mod.ISOMETRIC_KINDS or catalog is None:
        return top_down
    if iso_atlas.ground_problem(catalog):
        return top_down
    if mapping.assets_with_role(catalog, "GROUND", top_down):
        return top_down
    return config_mod.PROJECTION_ISOMETRIC


def isometric_problem(catalog: Any) -> str:
    """Why a project of these packs cannot be isometric ("" when it can): what the run would
    say (``iso_atlas.check_ground``)."""
    from rpggen.core import iso_atlas

    return iso_atlas.ground_problem(catalog)


def has_isometric_art(catalog: Any) -> bool:
    """True when a pack of the catalog is one of isometric tiles, or one of its pictures is
    drawn for the isometric view, whatever its role or status: there is something a *View*
    choice could be about. False for the packs of squares most projects are made of."""
    from rpggen.core import catalog as catalog_mod

    if catalog is None:
        return False
    if any(catalog_mod.pack_view(pack) == "isometric" for pack in catalog.packs):
        return True
    return any(
        a.kind == "image"
        and catalog_mod.effective(a).get("projection") == catalog_mod.PROJECTION_ISOMETRIC
        for a in catalog.assets
    )


def pack_footprint(catalog: Any) -> tuple[int, int] | None:
    """The diamond of the first isometric pack of a catalog (``catalog.isometric_footprint``),
    or None when no pack is isometric."""
    from rpggen.core import catalog as catalog_mod

    for pack in catalog.packs if catalog is not None else []:
        found = catalog_mod.isometric_footprint(pack)
        if found is not None:
            return found[0], found[1]
    return None


FLAT_VEHICLE_NOTE = "drawn from above: it will look flat on an isometric track"


def flat_vehicle(catalog: Any, ident: str | None, archetype: str, projection: str) -> bool:
    """True for the car of an isometric race that is a rotation sheet drawn from above (the
    sixteen headings of T16.02): it is driven all the same, and looks flat (T17.15)."""
    from rpggen.core import catalog as catalog_mod

    if archetype != "racing" or projection != config_mod.PROJECTION_ISOMETRIC:
        return False
    asset = catalog.asset(ident) if catalog is not None and ident else None
    if asset is None:
        return False
    facets = catalog_mod.effective(asset)
    headings = facets.get("headings")
    turned = isinstance(headings, int) and not isinstance(headings, bool) and headings > 0
    return turned and facets.get("projection") != catalog_mod.PROJECTION_ISOMETRIC


def _tiles(value: float) -> str:
    """40, 22.5 and 11.25 as they are; an unending fraction (13.333...) to one decimal."""
    exact = round(value, 2)
    return f"{exact:g}" if abs(value - exact) < 1e-9 else f"{round(value, 1):g}"


def tiles_hint(resolution: tuple[int, int], tile: int) -> str:
    return f"≈ {_tiles(resolution[0] / tile)} × {_tiles(resolution[1] / tile)} tiles on screen"


IMPORT_OVERHEAD = 1.8  # project bytes / pack bytes, measured on sample_pack: 3,378,223 / 1,860,386
# (the copied art, Godot's import cache and the runtime, tests and scripts every project carries)


@dataclass(frozen=True)
class Summary:
    """What the Options page's summary card shows (plain data, no widgets)."""

    archetype: str
    maps: list[str]  # "Starter map", "Second area", "3 interiors"
    systems: list[str]  # the labels of the features that are on
    tile_size: int
    tiles: str  # "≈ 40 × 22.5 tiles on screen"
    world: str = ""  # a metroidvania's starter world: "6 rooms, 2 abilities, a guardian"
    # an arcade kind's numbers, said beside its name: ("vertical", "3 stages", "3 lives")
    numbers: tuple[str, ...] = ()


def summarize(
    archetype: str,
    features: dict[str, bool],
    starter_map: dict[str, Any],
    tile_size: int,
    resolution: tuple[int, int],
    imported_maps: dict[str, Any] | None = None,
    crops: int | None = None,
) -> Summary:
    """The summary of the current (unsaved) options. The demo feature makes the starter map and
    its second area; each building of the starter map has an interior. An imported map chosen as
    the starter map replaces the starter map and its second area (T12.49). A farm (T17.16) has
    its village as the maps, its own map in words as ``world`` and its numbers (``crops``: how
    many crops its packs make, when the caller counted them)."""
    if archetype in config_mod.ARCADE_KINDS:
        # a run through stages (M16): no starter map, no imported maps
        on = {**effective_features(features), **dict.fromkeys(ARCADE_HIDDEN, False)}
        systems = [FEATURE_INFO[key][1] for key in FEATURE_INFO if on.get(key)]
        hint = tiles_hint(resolution, tile_size)
        return Summary(
            archetype,
            [],
            systems,
            tile_size,
            hint,
            stages_text(archetype, starter_map),
            tuple(arcade_numbers(archetype, starter_map)),
        )
    if archetype == "metroidvania":
        # a world of rooms (T14.06): no starter map, no imported maps, no pathfinding
        from rpggen.core import room_plan

        try:
            world = room_plan.describe(starter_map)
        except room_plan.RoomPlanError:
            world = ""
        on = effective_features({**features, "navigation": False})
        systems = [FEATURE_INFO[key][1] for key in FEATURE_INFO if on.get(key)]
        return Summary(archetype, [], systems, tile_size, tiles_hint(resolution, tile_size), world)
    maps: list[str] = []
    imported = imported_maps or {}
    extra = [m for m in imported.get("include", []) if m != imported.get("starter", "")]
    if imported.get("starter"):
        maps.append("Starter map (imported)")
    elif features.get("demo", False):
        maps.append("Starter map")
        maps.append("Second area")
        buildings = int(starter_map.get("buildings", 0) or 0)
        if buildings:
            maps.append(f"{buildings} interior" + ("s" if buildings != 1 else ""))
    if extra:
        maps.append(f"{len(extra)} imported map" + ("s" if len(extra) != 1 else ""))
    hidden = hidden_features(archetype)
    on = effective_features(features, archetype)
    systems = [FEATURE_INFO[key][1] for key in FEATURE_INFO if on.get(key) and key not in hidden]
    hint = tiles_hint(resolution, tile_size)
    if archetype == "farm":
        from rpggen.core import farm_plan

        try:
            farm = farm_plan.describe(starter_map)
        except farm_plan.FarmPlanError:
            farm = ""
        numbers = tuple(farm_numbers(starter_map, crops))
        return Summary(archetype, maps, systems, tile_size, hint, farm, numbers)
    return Summary(archetype, maps, systems, tile_size, hint)


def imported_map_label(imported_map: dict[str, Any]) -> str:
    """How the Options page names an imported map: ``maps/town · tiled_map · 40 × 24 tiles``."""
    stem = (
        str(imported_map["id"]).removeprefix(str(imported_map["pack_id"]) + ".").replace(".", "/")
    )
    width, height = imported_map["size"]
    return f"{stem} · {imported_map['pack_id']} · {width} × {height} tiles"


def intgrid_rows(maps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every IntGrid value of the imported maps, for the "Solid values" list: ``map`` (id),
    ``layer``, ``value``, ``name``, ``solid`` and a ``label``."""
    rows: list[dict[str, Any]] = []
    for imported_map in maps:
        for layer in imported_map["layers"]:
            for v in layer.get("values", []) if layer["kind"] == "intgrid" else []:
                shown = f"{v['value']} ({v['name']})" if v["name"] else str(v["value"])
                rows.append(
                    {
                        "map": imported_map["id"],
                        "layer": layer["name"],
                        "value": v["value"],
                        "name": v["name"],
                        "solid": v["solid"],
                        "label": f"{imported_map_label(imported_map)} · {layer['name']} · {shown}",
                    }
                )
    return rows


def set_solid(maps: list[dict[str, Any]], choices: dict[tuple[str, str, int], bool]) -> int:
    """Applies ``(map id, layer, value) -> solid`` to the catalog's maps; returns how many
    values changed. The choice is kept when the catalog is built again."""
    changed = 0
    for imported_map in maps:
        for layer in imported_map["layers"]:
            for v in layer.get("values", []) if layer["kind"] == "intgrid" else []:
                key = (imported_map["id"], layer["name"], int(v["value"]))
                if key in choices and bool(v["solid"]) != choices[key]:
                    v["solid"] = choices[key]
                    changed += 1
    return changed


def normalize_imported_maps(selection: dict[str, Any], known: list[str]) -> dict[str, Any]:
    """``selection`` without maps the catalog no longer has, the starter among the included maps,
    and without the keys that hold their default (an empty selection is ``{}``)."""
    starter = str(selection.get("starter", ""))
    starter = starter if starter in known else ""
    include = sorted(
        ({str(i) for i in selection.get("include", [])} | ({starter} if starter else set()))
        & set(known)
    )
    return {k: v for k, v in (("include", include), ("starter", starter)) if v}


def estimate_generation_seconds(
    timings: dict[str, float], saved_assets: int, assets: int
) -> float | None:
    """The saved phase timings scaled by the ratio of asset counts; None without history (no
    timings, or no count of the assets they were measured on)."""
    total = sum(v for v in timings.values() if v > 0)
    if total <= 0 or saved_assets <= 0 or assets <= 0:
        return None
    return total * assets / saved_assets


def estimate_kind_seconds(
    kind_timings: dict[str, list[float]], archetype: str, assets: int
) -> float | None:
    """The time the last run of this kind of game took, scaled by the ratio of asset counts;
    None while no run of the kind was timed (the estimate then falls back to the last run of
    any kind)."""
    saved = kind_timings.get(archetype)
    if not saved or saved[0] <= 0 or saved[1] <= 0 or assets <= 0:
        return None
    return saved[1] * assets / saved[0]


def estimate_project_bytes(pack_bytes: int) -> int:
    """The size of the generated project: the packs' bytes times ``IMPORT_OVERHEAD``."""
    return round(max(0, pack_bytes) * IMPORT_OVERHEAD)


TILES_ACROSS = 20  # about this many tiles across is a comfortable view for a 2D RPG


def suggested_preset(presets: list[tuple[int, int]], tile: int) -> tuple[int, int] | None:
    """The preset that shows about ``TILES_ACROSS`` tiles across (the larger one on a tie)."""
    if not presets or tile <= 0:
        return None
    return min(presets, key=lambda p: (abs(p[0] / tile - TILES_ACROSS), -p[0]))


def preset_index(presets: list[tuple[int, int]], value: tuple[int, int]) -> int:
    """Index of ``value`` in ``presets``, or ``len(presets)`` (Custom)."""
    return presets.index(value) if value in presets else len(presets)


def layer_issues(layers: list[str]) -> list[str]:
    out: list[str] = []
    if "Ground" not in layers:
        out.append(LAYER_GROUND_REQUIRED)
    if any(not name.strip() for name in layers):
        out.append(LAYER_EMPTY)
    if len(set(layers)) != len(layers):
        out.append(LAYER_DUPLICATE)
    return out


def add_layer(layers: list[str], name: str) -> list[str]:
    name = name.strip()
    return layers if not name or name in layers else [*layers, name]


def remove_layer(layers: list[str], name: str) -> list[str]:
    return layers if name == "Ground" else [n for n in layers if n != name]


def parse_list(text: str, kind: type) -> list[Any]:
    """``"A, B"`` -> ``["A", "B"]`` (or ints); raises ValueError on a bad integer."""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    return [kind(p) for p in parts]


def format_list(values: list[Any]) -> str:
    return ", ".join(str(v) for v in values)


def apply_binding_text(bindings: dict[str, Any], field: str, text: str) -> dict[str, Any]:
    """A copy of one action's ``bindings`` with ``field`` set from ``text`` (empty removes it).

    Fields the table does not edit (``joy_axes``) are kept."""
    kind = dict(BINDING_FIELDS)[field]
    out = copy.deepcopy(bindings)
    values = parse_list(text, kind)
    if values:
        out[field] = values
    else:
        out.pop(field, None)
    return out


# ---------------------------------------------------------------------------------- presets

PRESET_KEYS = (
    "features",
    "resolution",
    "window_size",
    "map_layers",
    "input",
    "validation",
    "starter_map",
)
STARTER_SIZE_PRESETS = [(32, 20), (40, 24), (64, 40)]
STARTER_COUNT_KEYS = ("buildings", "npcs", "enemies", "chests", "decorations", "ground_patches")


def to_preset(cfg: config_mod.GeneratorConfig) -> dict[str, Any]:
    """The option part of a config: never the packs, the name, the seed or the starter picks."""
    return {
        "features": dict(cfg.features),
        "resolution": list(cfg.resolution),
        "window_size": list(cfg.window_size),
        "map_layers": list(cfg.map_layers),
        "input": copy.deepcopy(cfg.input),
        "validation": dict(cfg.validation),
        "starter_map": cfg.starter_map_options(),
    }


def default_preset(archetype: str = "turn_based") -> dict[str, Any]:
    return to_preset(config_mod.default_for("x", [], archetype=archetype))


# The presets every installation has (T13.06): key -> (label, the features that are on; None for
# the defaults). They cannot be renamed or deleted; saving one under a name makes a copy.
BUILTIN_PRESETS: dict[str, tuple[str, tuple[str, ...] | None]] = {
    "everything": ("Everything", None),
    "minimal": ("Minimal", ("tilesets", "collision", "animations", "save", "dialogue")),
    "tilesets": ("Just the tilesets", ("tilesets", "collision", "terrain")),
}


# The presets of the arcade kinds (T16.16): key -> (label, the kinds it is offered for, what it
# sets among the kind's own options). Everything else on the page stays as it is.
KIND_PRESETS: dict[str, tuple[str, tuple[str, ...], dict[str, Any]]] = {
    "arcade_classic": (
        "Arcade classic",
        ("shmup", "run_and_gun"),
        {"lives": 3, "difficulty": "hard"},
    ),
    "bionic": ("Bionic", ("run_and_gun",), {"grapple": True, "jump": False}),
    "sunday_drive": (
        "Sunday drive",
        ("racing",),
        {"steering": "absolute", "rivals": 2, "rubber_band": True},
    ),
    # a farm's (T17.16): days of 20 minutes, no money lost at 2:00 and five times the money
    "cosy": (
        "Cosy",
        ("farm",),
        {"day_length": "long", "pass_out_loss": False, "starting_money": 500},
    ),
    # a season of a week: a year is 28 days
    "short_year": ("Short year", ("farm",), {"days_per_season": 7}),
}


def kind_preset_keys(archetype: str) -> list[str]:
    """The keys of ``KIND_PRESETS`` that are offered for ``archetype``, in their order."""
    return [key for key, (_label, kinds, _set) in KIND_PRESETS.items() if archetype in kinds]


def kind_preset(key: str, archetype: str, current: dict[str, Any]) -> dict[str, Any] | None:
    """A preset of an arcade kind as ``apply_preset`` takes it: the kind's options as they are
    (``current``) with the preset's values. None for an unknown key or another kind."""
    if key not in KIND_PRESETS or archetype not in KIND_PRESETS[key][1]:
        return None
    return {"starter_map": {**copy.deepcopy(current), **KIND_PRESETS[key][2]}}


def builtin_label(key: str) -> str:
    return BUILTIN_PRESETS[key][0] if key in BUILTIN_PRESETS else KIND_PRESETS[key][0]


def builtin_labels() -> list[str]:
    return [label for label, _on in BUILTIN_PRESETS.values()] + [
        label for label, _kinds, _set in KIND_PRESETS.values()
    ]


def builtin_preset(key: str, archetype: str = "turn_based") -> dict[str, Any] | None:
    """The options of a built-in preset: the defaults, with only the preset's features on and,
    for the two small ones, only the Windows export. None for an unknown key."""
    if key not in BUILTIN_PRESETS:
        return None
    preset = default_preset(archetype)
    wanted = BUILTIN_PRESETS[key][1]
    if wanted is not None:
        preset["features"] = {name: name in wanted for name in preset["features"]}
        preset["export_targets"] = list(config_mod.EXPORT_TARGET_DEFAULT)
    return preset


def input_fits(archetype: str, bindings: dict[str, Any]) -> bool:
    """True when ``bindings`` are the actions of ``archetype`` (the other archetype's differ)."""
    return set(bindings) == set(config_mod.default_input(archetype))


def apply_preset(
    cfg: config_mod.GeneratorConfig, preset: dict[str, Any]
) -> config_mod.GeneratorConfig:
    """A copy of ``cfg`` with the preset's options. Unknown keys are ignored; bindings of the
    other archetype are not taken over. Raises ValueError when the result is not valid."""
    changes: dict[str, Any] = {}
    if isinstance(preset.get("features"), dict):
        merged = dict(cfg.features)
        merged.update({k: bool(v) for k, v in preset["features"].items() if k in merged})
        changes["features"] = effective_features(merged, cfg.archetype)
    for key in ("resolution", "window_size"):
        value = preset.get(key)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            changes[key] = (int(value[0]), int(value[1]))
    if isinstance(preset.get("map_layers"), list):
        changes["map_layers"] = [str(n) for n in preset["map_layers"]]
    if isinstance(preset.get("input"), dict) and input_fits(cfg.archetype, preset["input"]):
        changes["input"] = copy.deepcopy(preset["input"])
    if isinstance(preset.get("validation"), dict):
        merged_validation = dict(cfg.validation)
        merged_validation.update(
            {
                k: bool(v)
                for k, v in preset["validation"].items()
                if k in ("smoke_test", "export_check")
            }
        )
        changes["validation"] = merged_validation
    if isinstance(preset.get("export_targets"), list):  # only the built-in presets carry it
        chosen = [t for t in config_mod.EXPORT_TARGETS if t in preset["export_targets"]]
        changes["export_targets"] = chosen or list(config_mod.EXPORT_TARGET_DEFAULT)
    if isinstance(preset.get("starter_map"), dict):
        known = config_mod.starter_map_defaults(cfg.archetype)
        changes["starter_map"] = {
            k: copy.deepcopy(v) for k, v in preset["starter_map"].items() if k in known
        }
    if cfg.archetype == "metroidvania":
        # rooms have no pathfinding and their layers are fixed: a preset does not change that
        changes.pop("map_layers", None)
        if "features" in changes:
            changes["features"] = {**changes["features"], "navigation": False}
    result = dataclasses.replace(cfg, **changes)
    problems = [message for message in config_errors(result) if not message.startswith("/packs")]
    if problems:
        raise ValueError("; ".join(problems))
    return result


# ------------------------------------------------------------------------- key capture

_KEY_NAMES = {
    "Return": "Enter",
    "Esc": "Escape",
    "Del": "Delete",
    "Ins": "Insert",
    "PgUp": "PageUp",
    "PgDown": "PageDown",
}


def key_name(qt_text: str) -> str | None:
    """The name the config (and Godot) uses for a key, from Qt's text for it (``QKeySequence``
    ``toString``); None for a bare modifier or nothing."""
    text = qt_text.strip()
    if not text or text in ("Ctrl", "Alt", "Meta"):
        return None
    return _KEY_NAMES.get(text, text)


def config_errors(cfg: config_mod.GeneratorConfig) -> list[str]:
    """Schema violations of the option values. The pack list is the project page's concern and
    the layers have friendlier messages in ``layer_issues``."""
    return [
        f"{path}: {message}"
        for path, message in schema.errors("config", cfg.to_json())
        if not path.startswith(("/packs", "/map_layers"))
    ]
