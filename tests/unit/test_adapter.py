"""Unit tests for Source Ingestion Adapter and schema detection."""

import pytest
from location_resolver.domain.cell import RadioType
from location_resolver.ingestion.adapter import (
    CellSourceAdapter,
    RowParseError,
    UnknownSchemaError,
    detect_schema,
)

LEGACY_INDIA_HEADER = "radio,mcc,mnc,lac,cid,changeable_0,long,lat,range,sample,changeable_1,created,updated,avgsignal"
STANDARD_OPENCELLID_HEADER = "radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal"


def test_detect_legacy_india_schema():
    """Verify detection of legacy India country export header."""
    fields = [c.strip() for c in LEGACY_INDIA_HEADER.split(",")]
    schema = detect_schema(fields)
    assert schema.name == "legacy_india_opencellid_csv"
    assert schema.radio_idx == 0
    assert schema.mcc_idx == 1
    assert schema.mnc_idx == 2
    assert schema.lac_tac_idx == 3
    assert schema.cell_id_idx == 4
    assert schema.unit_idx == 5
    assert schema.longitude_idx == 6
    assert schema.latitude_idx == 7


def test_detect_standard_opencellid_schema():
    """Verify detection of standard 14-column OpenCelliD / MLS header."""
    fields = [c.strip() for c in STANDARD_OPENCELLID_HEADER.split(",")]
    schema = detect_schema(fields)
    assert schema.name == "standard_opencellid_mls_csv"
    assert schema.mnc_idx == 2
    assert schema.lac_tac_idx == 3
    assert schema.cell_id_idx == 4
    assert schema.longitude_idx == 6


def test_unknown_schema_rejection():
    """Verify incomplete or corrupted headers raise UnknownSchemaError."""
    corrupt_header = ["radio", "mcc", "net", "something_random"]
    with pytest.raises(UnknownSchemaError) as exc:
        detect_schema(corrupt_header)
    assert "Missing required fields" in str(exc.value)


def test_parse_legacy_404_row():
    """Verify parsing a real 404.csv row."""
    adapter = CellSourceAdapter.from_header_line(LEGACY_INDIA_HEADER, source_name="test_404")
    row_fields = "GSM,404,5,221,2171,0,70.380477,20.913162,1000,1,1,1459669222,1459669222,0".split(",")
    cell = adapter.parse_row(row_fields, source_dataset="404.csv")

    assert cell.radio == RadioType.GSM
    assert cell.mcc == 404
    assert cell.mnc == 5
    assert cell.lac_tac == 221
    assert cell.cell_id == 2171
    assert cell.unit == 0
    assert cell.longitude == pytest.approx(70.380477)
    assert cell.latitude == pytest.approx(20.913162)
    assert cell.range_m == 1000
    assert cell.samples == 1
    assert cell.changeable is True
    assert cell.created_epoch == 1459669222
    assert cell.average_signal is None  # 0 in bulk dump maps to None (unavailable)
    assert cell.source == "test_404"
    assert cell.source_dataset == "404.csv"


def test_parse_legacy_405_row_with_real_signal():
    """Verify parsing a 405.csv row with negative dBm signal value."""
    adapter = CellSourceAdapter.from_header_line(LEGACY_INDIA_HEADER, source_name="test_405")
    row_fields = "LTE,405,874,1,1126180,45,72.83,18.92,500,3,0,1600000000,1600000500,-78".split(",")
    cell = adapter.parse_row(row_fields, source_dataset="405.csv")

    assert cell.radio == RadioType.LTE
    assert cell.mcc == 405
    assert cell.mnc == 874
    assert cell.lac_tac == 1
    assert cell.cell_id == 1126180
    assert cell.unit == 45
    assert cell.changeable is False  # changeable_1 = 0
    assert cell.average_signal == -78


def test_malformed_row_rejection():
    """Verify row with missing columns raises RowParseError."""
    adapter = CellSourceAdapter.from_header_line(LEGACY_INDIA_HEADER)
    short_row = ["GSM", "404", "5", "221"]
    with pytest.raises(RowParseError) as exc:
        adapter.parse_row(short_row)
    assert "columns; expected 14" in str(exc.value)
