"""Unit tests for the extensible dataset extractor and provenance manifest generator."""

import gzip
import io
import json
import tempfile
from pathlib import Path

import pytest

from scripts.extract_dataset import (
    FilterPipeline,
    HeaderValidationError,
    MCCFilter,
    RadioFilter,
    extract_from_file,
    stream_extract_dataset,
    validate_header,
)

SAMPLE_MULTI_MCC_CSV = """radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
LTE,404,45,1234,567890,12,77.2090,28.6139,1000,15,1,1609459200,1672531199,-75
LTE,405,861,4321,987654,45,80.2707,13.0827,800,45,1,1612137600,1675209600,-70
GSM,262,1,501,10234,0,13.4050,52.5200,2500,5,1,1577836800,1640995200,-88
UMTS,525,1,501,45890,240,103.8198,1.3521,1800,8,1,1577836800,1640995200,-92
GSM,404,20,501,10234,0,72.8777,19.0760,2500,5,1,1577836800,1640995200,-88
"""


def test_header_validation_success():
    """Verify official 14-column header passes strict validation."""
    valid_header = "radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal\n"
    fields, header_map = validate_header(valid_header, strict=True)
    assert len(fields) == 14
    assert header_map["radio"] == 0
    assert header_map["mcc"] == 1
    assert header_map["cell"] == 4


def test_header_validation_failure():
    """Verify corrupted header missing columns raises HeaderValidationError."""
    corrupt_header = "radio,mcc,net,area,cell,lon,lat\n"
    with pytest.raises(HeaderValidationError) as exc_info:
        validate_header(corrupt_header, strict=True)
    assert "Missing expected columns" in str(exc_info.value)


def test_stream_extract_with_manifest():
    """Verify extraction generates valid gzipped dataset and complete manifest JSON."""
    input_stream = io.BytesIO(SAMPLE_MULTI_MCC_CSV.encode("utf-8"))

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "india_cell_towers.csv.gz"
        manifest_file = Path(tmpdir) / "india_cell_towers.manifest.json"
        report_file = Path(tmpdir) / "report.json"

        pipeline = FilterPipeline([MCCFilter(["404", "405"])])

        result = stream_extract_dataset(
            input_stream=input_stream,
            output_path=output_file,
            manifest_path=manifest_file,
            report_path=report_file,
            filter_pipeline=pipeline,
            dataset_name="india_test_dataset",
            source_name="fixture_stream",
            is_input_gzipped=False,
        )

        assert result.manifest.rows_processed == 5
        assert result.manifest.rows_written == 3
        assert result.manifest.malformed_rows == 0
        assert result.mcc_breakdown["404"] == 2
        assert result.mcc_breakdown["405"] == 1

        # Verify Manifest File on Disk
        assert manifest_file.exists()
        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        assert manifest_data["dataset_name"] == "india_test_dataset"
        assert manifest_data["source_dataset"] == "fixture_stream"
        assert manifest_data["rows_processed"] == 5
        assert manifest_data["rows_written"] == 3
        assert manifest_data["filters_applied"] == [{"type": "mcc_filter", "target_mccs": ["404", "405"]}]
        assert len(manifest_data["output_checksum"]) == 64
        assert manifest_data["output_size_bytes"] > 0
        assert manifest_data["output_file"] == "india_cell_towers.csv.gz"

        # Verify Report File on Disk
        assert report_file.exists()
        with open(report_file, "r", encoding="utf-8") as f:
            report_data = json.load(f)
        assert "performance" in report_data
        assert "mcc_breakdown" in report_data

        # Verify Output Gzip Content
        with gzip.open(output_file, "rt", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]

        assert len(lines) == 4  # 1 header + 3 matched data rows
        assert lines[0].startswith("radio,mcc,net,area,cell")


def test_filter_extensibility_combined_mcc_and_radio():
    """Verify combining MCCFilter and RadioFilter in pipeline."""
    input_stream = io.BytesIO(SAMPLE_MULTI_MCC_CSV.encode("utf-8"))

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "india_lte.csv.gz"
        manifest_file = Path(tmpdir) / "india_lte.manifest.json"

        # Keep only LTE rows with MCC 404 or 405
        pipeline = FilterPipeline([
            MCCFilter(["404", "405"]),
            RadioFilter(["LTE"]),
        ])

        result = stream_extract_dataset(
            input_stream=input_stream,
            output_path=output_file,
            manifest_path=manifest_file,
            report_path=None,
            filter_pipeline=pipeline,
            dataset_name="india_lte_only",
            is_input_gzipped=False,
        )

        assert result.manifest.rows_processed == 5
        assert result.manifest.rows_written == 2  # Only the 2 LTE rows in 404 and 405
        assert result.mcc_breakdown["404"] == 1
        assert result.mcc_breakdown["405"] == 1


def test_extract_from_gzipped_file_integration():
    """Verify extract_from_file end-to-end with local .csv.gz file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_gz = Path(tmpdir) / "world_sample.csv.gz"
        output_gz = Path(tmpdir) / "india.csv.gz"
        manifest_json = Path(tmpdir) / "india.manifest.json"
        report_json = Path(tmpdir) / "india_report.json"

        with gzip.open(source_gz, "wt", encoding="utf-8") as f:
            f.write(SAMPLE_MULTI_MCC_CSV)

        pipeline = FilterPipeline([MCCFilter(["404", "405"])])

        result = extract_from_file(
            input_file=source_gz,
            output_file=output_gz,
            manifest_file=manifest_json,
            report_file=report_json,
            filter_pipeline=pipeline,
            dataset_name="india_cells",
        )

        assert result.manifest.rows_processed == 5
        assert result.manifest.rows_written == 3
        assert result.manifest.source_dataset == "world_sample.csv.gz"
        assert len(result.manifest.source_checksum) == 64
        assert output_gz.exists()
        assert manifest_json.exists()
        assert report_json.exists()
