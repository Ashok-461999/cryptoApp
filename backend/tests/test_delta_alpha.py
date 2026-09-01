"""Tests for Delta × Binance Alpha engine."""

from app.signals.delta_alpha import (
    Confluence100,
    grade_cap_reason,
    grade_from_score,
    max_leverage_for_grade,
)


def test_grade_from_score():
    assert grade_from_score(92) == "A+"
    assert grade_from_score(80) == "A"
    assert grade_from_score(72) == "B"
    assert grade_from_score(65) == "NO"


def test_grade_cap_reason():
    assert grade_cap_reason("A+", {"A+": 3, "A": 0, "B": 0}) is not None
    assert grade_cap_reason("A+", {"A+": 2, "A": 0, "B": 0}) is None


def test_max_leverage_for_grade():
    assert max_leverage_for_grade("A+") == 7
    assert max_leverage_for_grade("B") == 3
