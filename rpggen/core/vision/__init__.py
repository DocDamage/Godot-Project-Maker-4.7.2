"""The local vision step (T17.34): for a picture that names and pixels cannot decide, ask a
vision model running on this machine what it shows. Optional and off by default; with the
setting off nothing is started or sent. Answers are cached by the picture's hash, so a pack is
asked once.

The model names the picture in a few words (a list of numbered kinds to choose from was
answered at random by Qwen3.5 9B: a sheep was a weapon); the words are read as a file's name is
(``classifier``), with the words a game asset's name rarely holds but a description does
(``EXTRA_WORDS``: animals, crops, tools, people). How much an answer counts is measured on the
answer key (``tools/answer_key.py``), like any reader: at 16 px the model mistakes a sheep for a
cat, at 64 px and more it names slimes, keys and lamp posts.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpggen import paths
from rpggen.core import cache, classifier
from rpggen.core.vision.llama import LlamaConfig, LlamaServer, picture_png

CACHE_VERSION = 2

QUESTION = (
    "This is a pixel-art picture from a 2D game asset pack, enlarged. Name exactly what it "
    "shows (the animal, plant, object, kind of person, kind of ground or interface piece), in "
    "at most five words."
)

# words of a description that say a role and that file names rarely use (the classifier's own
# table holds the words of names); PERSON is somebody, the player or a villager alike
PERSON = "PERSON"


def _words(text: str) -> list[str]:
    return text.split()


# in order of strength: a description naming a vehicle and its wheels is a vehicle, a house and
# its door a building, a monster and the sword it holds a monster
EXTRA_WORDS: dict[str, str] = {}
ROLE_ORDER: list[str] = []
for _role, _text in (
    ("VEHICLE", "vehicle car truck cart wagon boat ship spaceship spacecraft rocket plane "
                "airplane bus tractor harvester bicycle train tank submarine"),
    ("BUILDING", "house building barn shed hut cabin cottage castle tower church temple shop "
                 "store home tent windmill silo greenhouse roof"),
    ("ENEMY", "monster enemy dragon demon skeleton zombie ghost slime goblin orc troll beast "
              "creature undead vampire"),
    ("ANIMAL", "animal sheep cow pig chicken hen rooster duck goose horse goat rabbit bunny cat "
               "dog puppy kitten bird fish deer fox bear owl frog mouse turtle bee butterfly "
               "crab"),
    ("CROP", "crop crops carrot wheat corn potato tomato pumpkin cabbage turnip seedling sprout "
             "sapling vegetable eggplant strawberry"),
    ("TOOL", "tool hoe pickaxe shovel scythe sickle hammer saw rake pliers wrench"),
    ("WEAPON", "weapon sword bow axe spear dagger staff gun rifle pistol"),
    (PERSON, "person man woman boy girl child kid farmer knight soldier explorer cowboy "
             "villager wizard witch king queen princess adventurer human character people"),
    ("ITEM", "item apple bread cheese egg milk meat mushroom berry fruit heart star bottle "
             "potion coin gem key"),
    ("DECORATION", "lamp lamppost lantern bench table chair bed archway door"),
):  # fmt: skip
    ROLE_ORDER.append(_role)
    EXTRA_WORDS.update({w: _role for w in _words(_text) if w not in EXTRA_WORDS})
# words that say nothing of what is shown
NOISE = frozenset(_words("a an the pixel pixelated art sprite small game with and of on in"))


@dataclass(frozen=True)
class VisionAnswer:
    raw: str  # the model's words
    role: str | None  # the role they say (PERSON for somebody), None when they say none

    @property
    def words(self) -> list[str]:
        return [w for w in re.findall(r"[a-z]+", self.raw.lower()) if w not in NOISE]


def role_of(raw: str) -> str | None:
    """The role a description says: the strongest of its words in ``EXTRA_WORDS`` (by
    ``ROLE_ORDER``), else what the classifier reads in the words as a name."""
    words = [w for w in re.findall(r"[a-z]+", raw.lower()) if w not in NOISE]
    found = []
    for word in words:
        singular = word[:-1] if word.endswith("s") and word[:-1] in EXTRA_WORDS else word
        if singular in EXTRA_WORDS:
            found.append(EXTRA_WORDS[singular])
    if found:
        return min(found, key=ROLE_ORDER.index)
    if not words:
        return None
    role, confidence, _alts = classifier.classify({}, "vision/" + "_".join(words) + ".png", None)
    return role if confidence > 0 and role != "NONE" else None


def parse(raw: str) -> VisionAnswer:
    return VisionAnswer(raw.strip(), role_of(raw))


def _cache_key(sha256: str) -> str:
    return hashlib.sha256(f"vision:{sha256}".encode()).hexdigest()


def cached(sha256: str) -> VisionAnswer | None:
    found = cache.get(_cache_key(sha256), CACHE_VERSION)
    if found is None:
        return None
    return parse(str(found.get("raw", "")))


def config_from_settings(settings: object) -> LlamaConfig | None:
    """The backend the settings name, or None when the step is off."""
    if not getattr(settings, "vision_enabled", False):
        return None
    return LlamaConfig(
        server=Path(getattr(settings, "vision_server", "")),
        model=Path(getattr(settings, "vision_model", "")),
        projector=Path(getattr(settings, "vision_projector", "")),
        port=int(getattr(settings, "vision_port", 8190)),
    )


@contextmanager
def session(config: LlamaConfig) -> Iterator[LlamaServer]:
    """A started server for a batch of questions; stopped (and the GPU freed) at the end."""
    server = LlamaServer(config, paths.cache_dir() / "vision" / "llama-server.log")
    with server:
        yield server


def ask_all(config: LlamaConfig, pictures: Iterable[tuple[str, Path]]) -> dict[str, VisionAnswer]:
    """``{sha256: answer}`` for ``(sha256, file)`` pairs: cached answers first, the server
    started only when a picture has none."""
    out: dict[str, VisionAnswer] = {}
    todo: list[tuple[str, Path]] = []
    for sha, file in pictures:
        found = cached(sha)
        if found is not None:
            out[sha] = found
        elif sha not in {s for s, _ in todo}:
            todo.append((sha, file))
    if not todo:
        return out
    with session(config) as server:
        for sha, file in todo:
            raw = server.ask(picture_png(file), QUESTION)
            cache.put(_cache_key(sha), CACHE_VERSION, {"raw": raw})
            out[sha] = parse(raw)
    return out


# ----------------------------------------------------------------------------- in the analysis

RULES = Path(__file__).resolve().parents[2] / "data" / "vision_rules.json"
RULES_VERSION = 1
MAX_PICTURES = 500  # asked in one analysis at most (about a second each on the owner's GPU)
USAGES = frozenset({"sprite", "object", "iso_tile", "portrait", "ui", "growth_strip"})
VISION_TAG = "vision:"


def allowed_roles() -> dict[str, Any]:
    """The roles the step may give (``RULES``, written by ``tools/answer_key.py vision --write``
    from its measurement on the answer key): those where the model was right more often than
    rpggen on the pictures rpggen was not sure of. Empty when nothing was measured to help."""
    try:
        data = json.loads(RULES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict) or data.get("version") != RULES_VERSION:
        return {}
    roles = data.get("roles")
    return roles if isinstance(roles, dict) else {}


def candidates(assets: Iterable[Any], auto_confidence: float) -> list[Any]:
    """The pictures the step asks about: read by rpggen, not by the user (no override, not
    confirmed, not from a profile or a learned rule), not set aside, of a usage the measurement
    covered, and not sure; the first ``MAX_PICTURES`` by id."""
    from rpggen.core import calibration, catalog

    out = []
    for asset in sorted(assets, key=lambda a: a.id):
        facets = catalog.effective(asset)
        if (
            asset.kind == "image"
            and not asset.overrides
            and asset.status != "CONFIRMED"
            and asset.detected_by not in calibration.USER_READERS
            and facets.get("usage") in USAGES
            and facets.get("role") not in (None, "NONE")
            and asset.confidence < auto_confidence
        ):
            out.append(asset)
    return out[:MAX_PICTURES]


def apply(
    assets: Iterable[Any],
    file_of: Callable[[Any], Path | None],
    config: LlamaConfig,
    auto_confidence: float,
    ask: Callable[..., dict[str, VisionAnswer]] = ask_all,
) -> int:
    """The vision step of an analysis: asks about the ``candidates`` and gives a picture the
    role the model names where that role is one the step may give (``allowed_roles``) and not
    already its own. The picture stays unsure (its confidence is kept), so it is still reviewed;
    its tags say what the model saw. Returns how many pictures changed."""
    allowed = allowed_roles()
    if not allowed:
        return 0
    pictures: list[tuple[Any, str, Path]] = []
    for asset in candidates(assets, auto_confidence):
        file = file_of(asset)
        if file is None or not file.is_file():
            continue
        pictures.append((asset, hashlib.sha256(file.read_bytes()).hexdigest(), file))
    if not pictures:
        return 0
    answers = ask(config, [(sha, file) for _a, sha, file in pictures])
    changed = 0
    for asset, sha, _file in pictures:
        found = answers.get(sha)
        if found is None or found.role not in allowed:
            continue
        if asset.detected.get("role") == found.role:
            continue
        tags = [t for t in asset.detected.get("tags") or [] if not str(t).startswith(VISION_TAG)]
        asset.detected = {**asset.detected, "role": found.role,
                          "tags": sorted({*tags, VISION_TAG + found.raw[:60]})}  # fmt: skip
        asset.detected.pop("roles_alt", None)
        asset.detected_by = "vision"
        changed += 1
    return changed
