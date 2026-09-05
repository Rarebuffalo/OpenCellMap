"""Unit tests for Canonical Cell domain entity model."""

import datetime
import pytest
from location_resolver.domain.cell import Cell, RadioType


def test_valid_canonical_cell_creation():
    """Verify standard canonical cell creation with required fields."""
    cell = Cell(
        radio=RadioType.LTE,
        mcc=404,
        mnc=45,
        lac_tac=1234,
        cell_id=567890,
        unit=12,
        latitude=28.6139,
        longitude=77.2090,
        range_m=1200,
        samples=15,
        changeable=True,
        created_epoch=1609459200,
        updated_epoch=1672531199,
        source="test_source",
        source_dataset="sample.csv",
    )

    assert cell.radio == RadioType.LTE
    assert cell.mcc == 404
    assert cell.mnc == 45
    assert cell.lac_tac == 1234
    assert cell.cell_id == 567890
    assert cell.latitude == 28.6139
    assert cell.longitude == 77.2090
    assert cell.range_m == 1200
    assert cell.samples == 15
    assert cell.changeable is True
    assert cell.composite_key == ("LTE", 404, 45, 1234, 567890)
    assert cell.enodeb_id == 567890 // 256
    assert cell.lte_sector_id == 567890 % 256


def test_radio_type_parsing():
    """Verify radio string parsing and aliases."""
    assert RadioType.from_str("LTE") == RadioType.LTE
    assert RadioType.from_str("gsm") == RadioType.GSM
    assert RadioType.from_str("UMTS") == RadioType.UMTS
    assert RadioType.from_str("NR") == RadioType.NR
    assert RadioType.from_str("5G") == RadioType.NR
    assert RadioType.from_str("CDMA") == RadioType.CDMA

    with pytest.raises(ValueError) as exc:
        RadioType.from_str("WIFI_UNKNOWN")
    assert "Unsupported radio access technology" in str(exc.value)


def test_timestamp_utc_conversion():
    """Verify integer epoch timestamps convert to timezone-aware UTC datetimes."""
    cell = Cell(
        radio=RadioType.GSM,
        mcc=404,
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=19.0760,
        longitude=72.8777,
        created_at=1459669222,
        updated_at=1491232540,
        created_epoch=1459669222,
        updated_epoch=1491232540,
    )

    assert cell.created_at is not None
    assert cell.created_at.tzinfo == datetime.timezone.utc
    assert cell.created_at.year == 2016
    assert cell.created_epoch == 1459669222


def test_missing_signal_representation():
    """Verify signal strength is None when missing or unmeasured."""
    cell = Cell(
        radio=RadioType.GSM,
        mcc=404,
        mnc=10,
        lac_tac=100,
        cell_id=5000,
        latitude=19.0760,
        longitude=72.8777,
        average_signal=None,
    )
    assert cell.average_signal is None
