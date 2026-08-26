"""Unit tests for the dataset inspection and profiling tool."""

from pathlib import Path
from scripts.inspect_dataset import inspect_opencellid_dataset, generate_markdown_report


def test_inspect_sample_opencellid_fixture():
    fixture_path = Path("tests/fixtures/sample_opencellid.csv")
    assert fixture_path.exists(), "Sample fixture must exist"

    metrics = inspect_opencellid_dataset(fixture_path, compute_hash=False)

    # 1. Row count
    assert metrics.total_rows == 8

    # 2. Radio technology distribution
    assert "LTE" in metrics.radio_distribution
    assert metrics.radio_distribution["LTE"] == 5
    assert metrics.radio_distribution["GSM"] == 2
    assert metrics.radio_distribution["UMTS"] == 1

    # 3. Geographic anomalies detected in fixture
    assert metrics.null_island_count == 1, "Should catch the (0.0, 0.0) record"
    assert metrics.out_of_bounds_coords_count == 1, "Should catch (195.0, 95.0)"
    assert len(metrics.errors) >= 1, "Errors list should capture out of bounds coords"

    # 4. MCC distribution
    assert "404" in metrics.mcc_distribution
    assert "405" in metrics.mcc_distribution

    # 5. Composite duplicate check
    assert metrics.duplicate_composite_keys == 1, "Should detect duplicate (LTE, 404, 45, 1234, 567890, 12)"

    # 6. Report generation check
    md_report = generate_markdown_report(metrics)
    assert "# Dataset Inspection Report" in md_report
    assert "Radio Technology Breakdown" in md_report
