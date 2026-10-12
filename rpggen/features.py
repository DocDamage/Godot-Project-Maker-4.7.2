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
# The farm and life sim of M17, off until its gate (T17.20). The kind can be generated from the
# command line and a config since T17.04; the wizard does not offer it.
FARM_AVAILABLE = False
# The isometric view of M17, off until its gate (T17.20). A config or `rpggen generate
# --projection isometric` can ask for it since T17.13; the wizard does not offer it. Maps are
# painted in it from T17.14 on.
ISOMETRIC_AVAILABLE = False
