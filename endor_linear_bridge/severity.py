"""Endor finding severity -> Linear priority and label vocabulary.

Linear priorities are integers: 0 none, 1 urgent, 2 high, 3 medium, 4 low.
"""

from __future__ import annotations

from typing import Iterable

CRITICAL = "FINDING_LEVEL_CRITICAL"
HIGH = "FINDING_LEVEL_HIGH"
MEDIUM = "FINDING_LEVEL_MEDIUM"
LOW = "FINDING_LEVEL_LOW"

# Higher rank == more severe.
SEVERITY_RANK: dict[str, int] = {LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4}

_PRIORITY = {CRITICAL: 1, HIGH: 2, MEDIUM: 3, LOW: 4}
_LABEL_WORD = {CRITICAL: "critical", HIGH: "high", MEDIUM: "medium", LOW: "low"}

PRIORITY_NONE = 0


def priority_for(severity: str) -> int:
    """Linear priority for a severity; 0 (none) for anything unrecognized."""
    return _PRIORITY.get(severity, PRIORITY_NONE)


def label_word(severity: str) -> str | None:
    """Lowercase severity word for label naming, or None if unrecognized."""
    return _LABEL_WORD.get(severity)


def max_severity(severities: Iterable[str]) -> str:
    """The most severe recognized level, or "" when none are recognized."""
    ranked = [s for s in severities if s in SEVERITY_RANK]
    if not ranked:
        return ""
    return max(ranked, key=lambda s: SEVERITY_RANK[s])


def sort_key(severity: str) -> int:
    """Sort key placing the most severe first and unknown levels last."""
    return -SEVERITY_RANK.get(severity, 0)
