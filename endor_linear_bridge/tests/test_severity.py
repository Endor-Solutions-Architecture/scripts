from endor_linear_bridge.severity import (
    label_word,
    max_severity,
    priority_for,
    sort_key,
)


def test_priority_for_maps_each_known_level():
    assert priority_for("FINDING_LEVEL_CRITICAL") == 1
    assert priority_for("FINDING_LEVEL_HIGH") == 2
    assert priority_for("FINDING_LEVEL_MEDIUM") == 3
    assert priority_for("FINDING_LEVEL_LOW") == 4


def test_priority_for_returns_none_priority_for_unknown():
    assert priority_for("FINDING_LEVEL_UNSPECIFIED") == 0
    assert priority_for("") == 0
    assert priority_for("NONSENSE") == 0


def test_label_word_maps_each_known_level():
    assert label_word("FINDING_LEVEL_CRITICAL") == "critical"
    assert label_word("FINDING_LEVEL_HIGH") == "high"
    assert label_word("FINDING_LEVEL_MEDIUM") == "medium"
    assert label_word("FINDING_LEVEL_LOW") == "low"


def test_label_word_returns_none_for_unknown():
    assert label_word("FINDING_LEVEL_UNSPECIFIED") is None
    assert label_word("") is None


def test_max_severity_picks_the_most_severe():
    assert (
        max_severity(["FINDING_LEVEL_LOW", "FINDING_LEVEL_CRITICAL", "FINDING_LEVEL_MEDIUM"])
        == "FINDING_LEVEL_CRITICAL"
    )


def test_max_severity_ignores_unknown_levels():
    assert (
        max_severity(["NONSENSE", "FINDING_LEVEL_MEDIUM"]) == "FINDING_LEVEL_MEDIUM"
    )


def test_max_severity_of_empty_is_empty_string():
    assert max_severity([]) == ""
    assert max_severity(["NONSENSE"]) == ""


def test_sort_key_orders_critical_before_low():
    levels = ["FINDING_LEVEL_LOW", "FINDING_LEVEL_CRITICAL", "FINDING_LEVEL_HIGH"]
    assert sorted(levels, key=sort_key) == [
        "FINDING_LEVEL_CRITICAL",
        "FINDING_LEVEL_HIGH",
        "FINDING_LEVEL_LOW",
    ]


def test_sort_key_puts_unknown_levels_last():
    levels = ["NONSENSE", "FINDING_LEVEL_LOW"]
    assert sorted(levels, key=sort_key) == ["FINDING_LEVEL_LOW", "NONSENSE"]
