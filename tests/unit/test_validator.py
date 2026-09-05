"""Unit tests for CellValidator and RangeClassification."""

import pytest
from location_resolver.domain.cell import Cell, RadioType
from location_resolver.ingestion.adapter import CellSourceAdapter
from location_resolver.ingestion.validator import CellValidator, RangeClassification


def test_validator_valid_cell():
    """Verify clean valid cell passes validation with zero errors."""
    cell = Cell(
        radio=RadioType.LTE,
        mcc=404,
        mnc=45,
        lac_tac=1234,
        cell_id=567890,
        latitude=28.6139,
        longitude=77.2090,
        range_m=1200,
        samples=15,
        created_epoch=1459669222,
        updated_epoch=1459700000,
    )
    validator = CellValidator(target_mccs={404, 405})
    res = validator.validate(cell)

    assert res.is_valid is True
    assert len(res.errors) == 0
    assert res.range_classification == RangeClassification.VALID


def test_validator_out_of_bounds_coords():
    """Verify invalid latitudes and longitudes are rejected."""
    bad_lat = Cell(
        radio=RadioType.GSM,
        mcc=404,
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=95.0,  # Invalid (> 90)
        longitude=77.0,
    )
    res = CellValidator().validate(bad_lat)
    assert res.is_valid is False
    assert any("Latitude out of bounds" in e for e in res.errors)

    bad_lon = Cell(
        radio=RadioType.GSM,
        mcc=404,
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=20.0,
        longitude=-195.0,  # Invalid (< -180)
    )
    res2 = CellValidator().validate(bad_lon)
    assert res2.is_valid is False
    assert any("Longitude out of bounds" in e for e in res2.errors)


def test_validator_null_island_rejection():
    """Verify (0.0, 0.0) coordinates are rejected as Null Island."""
    null_island_cell = Cell(
        radio=RadioType.GSM,
        mcc=404,
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=0.0,
        longitude=0.0,
    )
    res = CellValidator().validate(null_island_cell)
    assert res.is_valid is False
    assert any("Null Island" in e for e in res.errors)


def test_validator_identifier_checks():
    """Verify negative or zero identifiers trigger errors."""
    bad_mcc = Cell(
        radio=RadioType.GSM,
        mcc=0,  # Invalid
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=20.0,
        longitude=75.0,
    )
    res = CellValidator().validate(bad_mcc)
    assert res.is_valid is False
    assert any("MCC must be positive" in e for e in res.errors)

    bad_lac = Cell(
        radio=RadioType.GSM,
        mcc=404,
        mnc=10,
        lac_tac=0,  # Invalid
        cell_id=5000,
        latitude=20.0,
        longitude=75.0,
    )
    res2 = CellValidator().validate(bad_lac)
    assert res2.is_valid is False
    assert any("Area code" in e for e in res2.errors)


def test_validator_suspicious_and_invalid_range():
    """Verify range classification for normal, suspicious, and invalid ranges."""
    validator = CellValidator(max_valid_range_m=50_000)

    # Suspicious (> 50km)
    huge_cell = Cell(
        radio=RadioType.LTE,
        mcc=404,
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=20.0,
        longitude=75.0,
        range_m=75000,  # 75km
    )
    res = validator.validate(huge_cell)
    assert res.is_valid is True  # Non-fatal
    assert res.range_classification == RangeClassification.SUSPICIOUS
    assert any("exceeds threshold" in w for w in res.warnings)

    # Invalid (<= 0)
    zero_cell = Cell(
        radio=RadioType.LTE,
        mcc=404,
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=20.0,
        longitude=75.0,
        range_m=0,
    )
    res2 = validator.validate(zero_cell)
    assert res2.range_classification == RangeClassification.INVALID


def test_validator_inverted_timestamps_warning():
    """Verify warning when updated timestamp precedes created timestamp."""
    inverted_cell = Cell(
        radio=RadioType.LTE,
        mcc=404,
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=20.0,
        longitude=75.0,
        created_epoch=1600000500,
        updated_epoch=1600000000,  # 500s earlier than created
    )
    res = CellValidator().validate(inverted_cell)
    assert any("precedes created" in w for w in res.warnings)


def test_end_to_end_pipeline_with_legacy_fixture():
    """Verify raw legacy row -> adapter -> cell -> validator flow."""
    header = "radio,mcc,mnc,lac,cid,changeable_0,long,lat,range,sample,changeable_1,created,updated,avgsignal"
    row = "GSM,404,45,25033,53132,0,77.543466,12.903442,1369,14,1,1459703141,1491232540,0"

    adapter = CellSourceAdapter.from_header_line(header, source_name="integration_test")
    cell = adapter.parse_row(row.split(","))
    validator = CellValidator(target_mccs={404, 405})
    res = validator.validate(cell)

    assert res.is_valid is True
    assert cell.mcc == 404
    assert cell.mnc == 45
    assert cell.lac_tac == 25033
    assert cell.cell_id == 53132
    assert cell.samples == 14
    assert cell.range_m == 1369
    assert res.range_classification == RangeClassification.VALID
