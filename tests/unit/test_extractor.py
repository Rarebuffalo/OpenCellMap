"""Unit tests for the streaming MCC extractor."""

import gzip
import io
import tempfile
from pathlib import Path

from scripts.extract_mcc import extract_from_local_file, stream_extract_mcc


SAMPLE_MULTI_MCC_CSV = """radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
LTE,404,45,1234,567890,12,77.2090,28.6139,1000,15,1,1609459200,1672531199,-75
LTE,405,861,4321,987654,45,80.2707,13.0827,800,45,1,1612137600,1675209600,-70
GSM,262,1,501,10234,0,13.4050,52.5200,2500,5,1,1577836800,1640995200,-88
UMTS,525,1,501,45890,240,103.8198,1.3521,1800,8,1,1577836800,1640995200,-92
GSM,404,20,501,10234,0,72.8777,19.0760,2500,5,1,1577836800,1640995200,-88
"""


def test_stream_extract_mcc_filtering():
    """Verify that only requested MCCs are kept, non-target MCCs are dropped, and header is preserved."""
    input_bytes = SAMPLE_MULTI_MCC_CSV.encode("utf-8")
    input_stream = io.BytesIO(input_bytes)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "extracted.csv.gz"
        stats = stream_extract_mcc(
            input_stream=input_stream,
            output_path=output_file,
            target_mccs={"404", "405"},
            is_input_gzipped=False,
        )

        assert stats.total_rows_read == 5, "Total data rows in fixture is 5"
        assert stats.mcc_counts["404"] == 2, "Fixture has 2 MCC 404 rows"
        assert stats.mcc_counts["405"] == 1, "Fixture has 1 MCC 405 row"
        assert stats.total_rows_written == 4, "1 header row + 3 matching data rows"
        assert stats.malformed_rows_count == 0

        # Read back gzipped output and verify contents
        with gzip.open(output_file, "rt", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        assert len(lines) == 4
        # Verify header is exact
        assert lines[0].startswith("radio,mcc,net,area,cell")
        # Verify all data lines belong to target MCCs
        for data_line in lines[1:]:
            parts = data_line.split(",")
            assert parts[1] in ["404", "405"]
            assert parts[1] not in ["262", "525"]


def test_extract_from_gzipped_local_file():
    """Verify extraction from a gzipped input file producing a gzipped output file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_gz = Path(tmpdir) / "source.csv.gz"
        target_gz = Path(tmpdir) / "target.csv.gz"

        with gzip.open(source_gz, "wt", encoding="utf-8") as f:
            f.write(SAMPLE_MULTI_MCC_CSV)

        stats = extract_from_local_file(
            input_file=source_gz,
            output_path=target_gz,
            target_mccs={"404", "405"},
        )

        assert stats.total_rows_read == 5
        assert stats.total_rows_written == 4
        assert target_gz.exists()
        assert target_gz.stat().st_size > 0
        assert len(stats.output_sha256) == 64


def test_extract_with_malformed_and_blank_lines():
    """Verify that corrupt lines with missing columns are safely skipped and reported."""
    csv_with_errors = """radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
LTE,404,45,1234,567890,12,77.2090,28.6139,1000,15,1,1609459200,1672531199,-75
invalid_truncated_row
LTE,405,861,4321,987654,45,80.2707,13.0827,800,45,1,1612137600,1675209600,-70
"""
    input_stream = io.BytesIO(csv_with_errors.encode("utf-8"))

    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "out.csv.gz"
        stats = stream_extract_mcc(
            input_stream=input_stream,
            output_path=output_file,
            target_mccs={"404", "405"},
            is_input_gzipped=False,
        )

        assert stats.total_rows_read == 3
        assert stats.malformed_rows_count == 1
        assert stats.mcc_counts["404"] == 1
        assert stats.mcc_counts["405"] == 1


def test_extract_empty_stream():
    """Verify that an empty stream returns zero counts without error."""
    input_stream = io.BytesIO(b"")
    with tempfile.TemporaryDirectory() as tmpdir:
        output_file = Path(tmpdir) / "empty.csv.gz"
        stats = stream_extract_mcc(
            input_stream=input_stream,
            output_path=output_file,
            target_mccs={"404", "405"},
            is_input_gzipped=False,
        )
        assert stats.total_rows_read == 0
        assert stats.total_rows_written == 0
