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
import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

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


EXTRA_WORDS: dict[str, str] = {}
for _role, _text in (
    ("ANIMAL", "sheep cow pig chicken hen rooster duck goose horse goat rabbit bunny cat dog "
               "puppy kitten bird fish deer fox bear owl frog mouse turtle bee butterfly crab"),
    ("CROP", "crop crops carrot carrots wheat corn potato potatoes tomato tomatoes pumpkin "
             "cabbage turnip seedling sprout sapling vegetable vegetables eggplant strawberry"),
    ("TOOL", "hoe pickaxe shovel watering can scythe sickle hammer saw rake fishing rod"),
    (PERSON, "person man woman boy girl child kid farmer knight soldier explorer cowboy "
             "villager wizard witch king queen princess adventurer human character people"),
    ("VEHICLE", "car truck cart wagon boat ship bus tractor bicycle"),
    ("ITEM", "apple bread cheese egg milk meat mushroom berry berries fruit chest heart star "
             "bottle"),
    ("DECORATION", "lamp lamppost lantern bench table chair bed archway door"),
    ("BUILDING", "roof"),
):  # fmt: skip
    EXTRA_WORDS.update(dict.fromkeys(_words(_text), _role))
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
    """The role a description says: a word of ``EXTRA_WORDS`` (the last one, the noun of
    "blue slime" or "golden key"), else what the classifier reads in the words as a name."""
    words = [w for w in re.findall(r"[a-z]+", raw.lower()) if w not in NOISE]
    for word in reversed(words):
        singular = word[:-1] if word.endswith("s") and word[:-1] in EXTRA_WORDS else word
        if singular in EXTRA_WORDS:
            return EXTRA_WORDS[singular]
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
