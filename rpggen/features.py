"""Switches for features that are not finished yet."""

from __future__ import annotations

ARPG_AVAILABLE = True  # the action RPG archetype (M9)
# The metroidvania archetype (M14), on since the gate of 1.2 (T14.13). When it is False the
# wizard's third card is disabled and the welcome view offers only the top-down sample.
METROIDVANIA_AVAILABLE = True
# The three arcade kinds of M16, on since the gate of 1.4 (T16.20). When one is False its card is
# disabled, its sample is not offered, and the wizard cannot choose it.
SHMUP_AVAILABLE = True
RUN_AND_GUN_AVAILABLE = True
RACING_AVAILABLE = True
