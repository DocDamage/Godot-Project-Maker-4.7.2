from __future__ import annotations

import re
from pathlib import Path

from rpggen.gui.wizard import default_pages

REPO = Path(__file__).resolve().parents[2]


def test_the_guide_headings_match_the_help_anchors(qtbot) -> None:
    """F1 opens the guide at the heading named by a page's help_anchor."""
    text = (REPO / "docs/user_guide.md").read_text(encoding="utf-8")
    headings = set(re.findall(r"^## (.+)$", text, flags=re.M))
    for page in default_pages():
        qtbot.addWidget(page)
        assert not page.help_anchor or page.help_anchor in headings, page.help_anchor
