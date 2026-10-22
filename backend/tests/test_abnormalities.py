"""Unit tests for the HunterPie abnormality id value object and its catalog."""
import json
from pathlib import Path

import pytest

from app.abnormalities import (
    ABNORMALITY_NAMES,
    EXCLUDED_SHORT_IDS,
    EXCLUDED_STORED_IDS,
    UNKNOWN_GROUP,
    AbnormalityId,
)

FIXTURE_PATH = (Path(__file__).parent / "fixtures"
                / "hunterpie_wilds_abnormalities.json")


@pytest.mark.parametrize("raw, group, short", [
    ("Consumables_Consumables.30", "Consumables", "Consumables.30"),
    ("Debuffs_Debuffs.5.Cleared", "Debuffs", "Debuffs.5.Cleared"),
    ("Skills_Skills.159-1", "Skills", "Skills.159-1"),
])
def test_parse_splits_group_and_short_id(raw, group, short):
    """{Group}_{Id} splits on the first underscore only."""
    # Arrange
    expected_group, expected_short = group, short

    # Act
    parsed = AbnormalityId.parse(raw)

    # Assert
    assert parsed.raw == raw
    assert parsed.group == expected_group
    assert parsed.short == expected_short


def test_parse_without_separator_uses_unknown_group():
    """An id with no '_' keeps its raw value and is grouped as unknown."""
    # Arrange
    raw = "SomeFutureId"

    # Act
    parsed = AbnormalityId.parse(raw)

    # Assert
    assert parsed.group == UNKNOWN_GROUP
    assert parsed.short == raw


def test_display_name_uses_catalog():
    """A catalogued id resolves to its HunterPie name."""
    # Arrange
    parsed = AbnormalityId.parse("Debuffs_Debuffs.2")

    # Act
    name = parsed.display_name

    # Assert
    assert name == "Blastblight"


def test_display_name_falls_back_to_unknown_label():
    """An uncatalogued id still gets a stable, readable label."""
    # Arrange
    parsed = AbnormalityId.parse("Songs_Songs.0")

    # Act
    name = parsed.display_name

    # Assert
    assert name == "Unknown (Songs.0)"


@pytest.mark.parametrize("raw, displayable", [
    ("Debuffs_Debuffs.3.BuildUp", False),
    ("Debuffs_Debuffs.3", True),
    ("Debuffs_Debuffs.5.Cleared", True),
])
def test_is_displayable_excludes_only_buildup_meters(raw, displayable):
    """Buildup gauges are hidden; base debuffs and named variants are not."""
    # Arrange
    parsed = AbnormalityId.parse(raw)

    # Act
    result = parsed.is_displayable

    # Assert
    assert result is displayable


def test_excluded_stored_ids_round_trip():
    """Every stored spelling of an excluded id parses back to an excluded short."""
    # Arrange
    stored_ids = EXCLUDED_STORED_IDS

    # Act
    parsed_shorts = {AbnormalityId.parse(raw).short for raw in stored_ids}

    # Assert
    assert parsed_shorts == set(EXCLUDED_SHORT_IDS)
    assert all(not AbnormalityId.parse(raw).is_displayable for raw in stored_ids)


def test_catalog_matches_hunterpie_fixture():
    """Drift guard: every named fixture id is catalogued or intentionally
    excluded, and no catalog key is stale (catches HunterPie renaming or
    removing an id)."""
    # Arrange
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    named = set(fixture["named"])

    # Act
    uncatalogued = named - set(ABNORMALITY_NAMES) - set(EXCLUDED_SHORT_IDS)
    stale = set(ABNORMALITY_NAMES) - named

    # Assert
    assert uncatalogued == set(), (
        f"fixture ids missing from catalog: {sorted(uncatalogued)}")
    assert stale == set(), (
        f"catalog ids absent from fixture: {sorted(stale)}")
    assert set(EXCLUDED_SHORT_IDS) <= named, (
        "excluded ids no longer exist upstream; revisit the exclusion set")
