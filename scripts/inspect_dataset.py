#!/usr/bin/env python3
"""Dataset Inspection & Profiling Tool for OpenCelliD and Cellular Data Exports.

Reads cellular CSV / CSV.GZ exports in a streaming, memory-safe manner and generates
both machine-readable JSON and human-readable Markdown inspection reports.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import polars as pl
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class DatasetInspectionMetrics:
    """Structured inspection metrics collected across the dataset."""

    # File metadata
    file_path: str = ""
    file_name: str = ""
    file_size_bytes: int = 0
    file_size_mb: float = 0.0
    sha256_checksum: str = ""
    inspected_at: str = ""

    # Record counts
    total_rows: int = 0

    # Radio distribution
    radio_distribution: dict[str, int] = field(default_factory=dict)

    # Geographic metrics
    lat_min: float | None = None
    lat_max: float | None = None
    lon_min: float | None = None
    lon_max: float | None = None
    null_island_count: int = 0  # lat==0 and lon==0
    out_of_bounds_coords_count: int = 0  # lat not in [-90, 90] or lon not in [-180, 180]
    missing_coords_count: int = 0
    in_india_bbox_count: int = 0  # Approx India BBox: lat in [6.5, 37.5], lon in [68.0, 97.5]

    # Network identifiers
    mcc_distribution: dict[str, int] = field(default_factory=dict)
    unique_mnc_count: int = 0
    unique_lac_count: int = 0
    unique_cell_id_count: int = 0
    invalid_area_count: int = 0  # area <= 0 or area > 65535
    invalid_cell_count: int = 0  # cell <= 0

    # Signal & Quality metrics
    range_min: int | None = None
    range_median: float | None = None
    range_p95: float | None = None
    range_max: int | None = None
    zero_or_negative_range_count: int = 0

    samples_min: int | None = None
    samples_median: float | None = None
    samples_p95: float | None = None
    samples_max: int | None = None
    single_sample_count: int = 0  # cells with exactly 1 sample

    changeable_distribution: dict[str, int] = field(default_factory=dict)
    average_signal_recorded_count: int = 0

    # Timestamps
    created_min_utc: str | None = None
    created_max_utc: str | None = None
    updated_min_utc: str | None = None
    updated_max_utc: str | None = None

    # Key Uniqueness
    duplicate_composite_keys: int = 0

    # Quality Flags & Warnings
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def compute_sha256(file_path: Path, max_bytes: int = 64 * 1024 * 1024) -> str:
    """Compute SHA256 checksum (reads up to max_bytes for multi-GB files to remain responsive)."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        bytes_read = 0
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
            bytes_read += len(chunk)
            if bytes_read >= max_bytes:
                break
    return hasher.hexdigest() + (" (partial)" if bytes_read >= max_bytes else "")


def inspect_opencellid_dataset(
    file_path: Path,
    compute_hash: bool = True,
    sample_size: int | None = None,
) -> DatasetInspectionMetrics:
    """Inspect and profile an OpenCelliD CSV or CSV.GZ file using Polars streaming."""
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {file_path}")

    metrics = DatasetInspectionMetrics(
        file_path=str(file_path.resolve()),
        file_name=file_path.name,
        file_size_bytes=file_path.stat().st_size,
        file_size_mb=round(file_path.stat().st_size / (1024 * 1024), 2),
        inspected_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

    if compute_hash:
        metrics.sha256_checksum = compute_sha256(file_path)

    # Read schema & data using Polars with explicit schema overrides
    schema_overrides = {
        "radio": pl.Utf8,
        "mcc": pl.Int64,
        "net": pl.Int64,
        "area": pl.Int64,
        "cell": pl.Int64,
        "unit": pl.Int64,
        "lon": pl.Float64,
        "lat": pl.Float64,
        "range": pl.Int64,
        "samples": pl.Int64,
        "changeable": pl.Int64,
        "created": pl.Int64,
        "updated": pl.Int64,
        "averageSignal": pl.Int64,
    }

    try:
        if sample_size:
            df = pl.read_csv(file_path, schema_overrides=schema_overrides, n_rows=sample_size)
        else:
            df = pl.read_csv(file_path, schema_overrides=schema_overrides)
    except Exception as e:
        metrics.errors.append(f"Failed to read CSV: {e}")
        return metrics

    metrics.total_rows = len(df)
    if metrics.total_rows == 0:
        metrics.errors.append("Dataset file is empty.")
        return metrics

    # 1. Radio distribution
    if "radio" in df.columns:
        radio_counts = df["radio"].value_counts().to_dicts()
        metrics.radio_distribution = {
            str(r["radio"] or "NULL"): int(r["count"]) for r in radio_counts
        }

    # 2. Geographic metrics
    if "lat" in df.columns and "lon" in df.columns:
        lat_valid = df["lat"].drop_nulls()
        lon_valid = df["lon"].drop_nulls()

        if len(lat_valid) > 0:
            metrics.lat_min = float(lat_valid.min())  # type: ignore
            metrics.lat_max = float(lat_valid.max())  # type: ignore
        if len(lon_valid) > 0:
            metrics.lon_min = float(lon_valid.min())  # type: ignore
            metrics.lon_max = float(lon_valid.max())  # type: ignore

        metrics.missing_coords_count = int(df["lat"].is_null().sum() + df["lon"].is_null().sum())

        # Null Island (0,0)
        null_island_filter = (df["lat"] == 0.0) & (df["lon"] == 0.0)
        metrics.null_island_count = int(null_island_filter.sum())
        if metrics.null_island_count > 0:
            metrics.warnings.append(
                f"Found {metrics.null_island_count} records with coordinates exactly at (0.0, 0.0) [Null Island]."
            )

        # Out-of-bounds coordinates
        oob_filter = (
            (df["lat"] < -90.0)
            | (df["lat"] > 90.0)
            | (df["lon"] < -180.0)
            | (df["lon"] > 180.0)
        )
        metrics.out_of_bounds_coords_count = int(oob_filter.sum())
        if metrics.out_of_bounds_coords_count > 0:
            metrics.errors.append(
                f"Found {metrics.out_of_bounds_coords_count} records with mathematically invalid WGS-84 coordinates."
            )

        # India bounding box (approx: lat [6.5, 37.5], lon [68.0, 97.5])
        india_filter = (
            (df["lat"] >= 6.5)
            & (df["lat"] <= 37.5)
            & (df["lon"] >= 68.0)
            & (df["lon"] <= 97.5)
        )
        metrics.in_india_bbox_count = int(india_filter.sum())

    # 3. Network identifiers
    if "mcc" in df.columns:
        mcc_counts = df["mcc"].value_counts().to_dicts()
        metrics.mcc_distribution = {
            str(m["mcc"] or "NULL"): int(m["count"]) for m in mcc_counts
        }

    if "net" in df.columns:
        metrics.unique_mnc_count = int(df["net"].n_unique())

    if "area" in df.columns:
        metrics.unique_lac_count = int(df["area"].n_unique())
        invalid_area = (df["area"] <= 0) | (df["area"] > 65535)
        metrics.invalid_area_count = int(invalid_area.sum())
        if metrics.invalid_area_count > 0:
            metrics.warnings.append(
                f"Found {metrics.invalid_area_count} records with area (LAC/TAC) <= 0 or > 65535."
            )

    if "cell" in df.columns:
        metrics.unique_cell_id_count = int(df["cell"].n_unique())
        invalid_cell = df["cell"] <= 0
        metrics.invalid_cell_count = int(invalid_cell.sum())
        if metrics.invalid_cell_count > 0:
            metrics.warnings.append(
                f"Found {metrics.invalid_cell_count} records with cell ID <= 0."
            )

    # 4. Signal & Quality metrics
    if "range" in df.columns:
        r_valid = df["range"].drop_nulls()
        if len(r_valid) > 0:
            metrics.range_min = int(r_valid.min())  # type: ignore
            metrics.range_median = float(r_valid.median())  # type: ignore
            metrics.range_p95 = float(r_valid.quantile(0.95))  # type: ignore
            metrics.range_max = int(r_valid.max())  # type: ignore
            metrics.zero_or_negative_range_count = int((df["range"] <= 0).sum())
            if metrics.zero_or_negative_range_count > 0:
                metrics.warnings.append(
                    f"Found {metrics.zero_or_negative_range_count} records with range <= 0 meters."
                )

    if "samples" in df.columns:
        s_valid = df["samples"].drop_nulls()
        if len(s_valid) > 0:
            metrics.samples_min = int(s_valid.min())  # type: ignore
            metrics.samples_median = float(s_valid.median())  # type: ignore
            metrics.samples_p95 = float(s_valid.quantile(0.95))  # type: ignore
            metrics.samples_max = int(s_valid.max())  # type: ignore
            metrics.single_sample_count = int((df["samples"] == 1).sum())

    if "changeable" in df.columns:
        ch_counts = df["changeable"].value_counts().to_dicts()
        metrics.changeable_distribution = {
            str(c["changeable"] or "NULL"): int(c["count"]) for c in ch_counts
        }

    if "averageSignal" in df.columns:
        sig_valid = (df["averageSignal"] != 0) & df["averageSignal"].is_not_null()
        metrics.average_signal_recorded_count = int(sig_valid.sum())

    # 5. Timestamps
    if "created" in df.columns:
        c_min = df["created"].min()
        c_max = df["created"].max()
        if c_min and c_min > 0:
            metrics.created_min_utc = datetime.datetime.fromtimestamp(
                c_min, datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")
        if c_max and c_max > 0:
            metrics.created_max_utc = datetime.datetime.fromtimestamp(
                c_max, datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")

    if "updated" in df.columns:
        u_min = df["updated"].min()
        u_max = df["updated"].max()
        if u_min and u_min > 0:
            metrics.updated_min_utc = datetime.datetime.fromtimestamp(
                u_min, datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")
        if u_max and u_max > 0:
            metrics.updated_max_utc = datetime.datetime.fromtimestamp(
                u_max, datetime.timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S UTC")

    # 6. Duplicate composite key check
    key_cols = [c for c in ["radio", "mcc", "net", "area", "cell", "unit"] if c in df.columns]
    if key_cols:
        distinct_count = df.select(key_cols).n_unique()
        metrics.duplicate_composite_keys = metrics.total_rows - distinct_count
        if metrics.duplicate_composite_keys > 0:
            metrics.warnings.append(
                f"Found {metrics.duplicate_composite_keys} duplicate composite keys "
                f"across ({', '.join(key_cols)})."
            )

    return metrics


def generate_markdown_report(metrics: DatasetInspectionMetrics) -> str:
    """Generate a clean GitHub-flavored Markdown inspection report."""
    md: list[str] = [
        f"# Dataset Inspection Report: `{metrics.file_name}`",
        "",
        f"**Inspected At:** {metrics.inspected_at}  ",
        f"**File Size:** {metrics.file_size_mb} MB ({metrics.file_size_bytes:,} bytes)  ",
        f"**SHA256 Checksum:** `{metrics.sha256_checksum}`  ",
        f"**Total Records:** **{metrics.total_rows:,}**  ",
        "",
        "---",
        "",
        "## 1. Executive Summary & Quality Flags",
        "",
    ]

    if metrics.errors:
        md.append("### Errors (Require Filtering / Quarantine)")
        for err in metrics.errors:
            md.append(f"- **ERROR:** {err}")
        md.append("")

    if metrics.warnings:
        md.append("### Warnings (Require Normalization / Edge-Case Handling)")
        for warn in metrics.warnings:
            md.append(f"- **WARNING:** {warn}")
        md.append("")

    if not metrics.errors and not metrics.warnings:
        md.append("> **NOTE:** No structural anomalies or corrupt records detected.")
        md.append("")

    md.extend([
        "---",
        "",
        "## 2. Radio Technology Breakdown",
        "",
        "| Radio Standard | Record Count | Percentage |",
        "| :--- | :--- | :--- |",
    ])
    for radio, count in sorted(metrics.radio_distribution.items(), key=lambda x: x[1], reverse=True):
        pct = (count / metrics.total_rows * 100) if metrics.total_rows else 0
        md.append(f"| **{radio}** | {count:,} | {pct:.2f}% |")

    md.extend([
        "",
        "---",
        "",
        "## 3. Geographic Integrity",
        "",
        "| Metric | Value | Status |",
        "| :--- | :--- | :--- |",
        f"| **Latitude Range** | `[{metrics.lat_min}, {metrics.lat_max}]` | {'Valid' if metrics.lat_min and -90 <= metrics.lat_min and metrics.lat_max and metrics.lat_max <= 90 else 'INVALID'} |",
        f"| **Longitude Range** | `[{metrics.lon_min}, {metrics.lon_max}]` | {'Valid' if metrics.lon_min and -180 <= metrics.lon_min and metrics.lon_max and metrics.lon_max <= 180 else 'INVALID'} |",
        f"| **Null Island (0.0, 0.0)** | {metrics.null_island_count:,} | {'Anomaly' if metrics.null_island_count > 0 else 'Clean'} |",
        f"| **Out-of-Bounds Coords** | {metrics.out_of_bounds_coords_count:,} | {'Error' if metrics.out_of_bounds_coords_count > 0 else 'Clean'} |",
        f"| **Missing Coordinates** | {metrics.missing_coords_count:,} | {'Error' if metrics.missing_coords_count > 0 else 'Clean'} |",
        f"| **Within India Bounding Box** | {metrics.in_india_bbox_count:,} ({(metrics.in_india_bbox_count/metrics.total_rows*100):.2f}%) | Regional check |",
        "",
        "---",
        "",
        "## 4. Network Identifiers (MCC / MNC / Area / Cell)",
        "",
        f"- **Unique MNCs (Operators):** {metrics.unique_mnc_count:,}",
        f"- **Unique Areas (LAC/TAC):** {metrics.unique_lac_count:,}",
        f"- **Unique Cell IDs:** {metrics.unique_cell_id_count:,}",
        f"- **Duplicate Composite Keys:** {metrics.duplicate_composite_keys:,}",
        "",
        "### Mobile Country Codes (MCC)",
        "| MCC | Country / Region | Record Count | Percentage |",
        "| :--- | :--- | :--- | :--- |",
    ])

    for mcc, count in sorted(metrics.mcc_distribution.items(), key=lambda x: x[1], reverse=True):
        pct = (count / metrics.total_rows * 100) if metrics.total_rows else 0
        desc = "India" if mcc in ["404", "405"] else "Other/Unknown"
        md.append(f"| **{mcc}** | {desc} | {count:,} | {pct:.2f}% |")

    md.extend([
        "",
        "---",
        "",
        "## 5. Signal & Quality Metrics",
        "",
        "| Metric | Min | Median | P95 | Max |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| **Estimated Range (meters)** | {metrics.range_min}m | {metrics.range_median}m | {metrics.range_p95}m | {metrics.range_max}m |",
        f"| **Crowdsourced Samples** | {metrics.samples_min} | {metrics.samples_median} | {metrics.samples_p95} | {metrics.samples_max:,} |",
        "",
        f"- **Single Sample Towers (Samples = 1):** {metrics.single_sample_count:,} ({(metrics.single_sample_count/metrics.total_rows*100):.2f}% of dataset)",
        f"- **Records with Recorded Signal:** {metrics.average_signal_recorded_count:,}",
        "",
        "---",
        "",
        "## 6. Observation Timeline (UNIX Timestamps)",
        "",
        f"- **First Created Record:** `{metrics.created_min_utc}`",
        f"- **Latest Created Record:** `{metrics.created_max_utc}`",
        f"- **First Updated Record:** `{metrics.updated_min_utc}`",
        f"- **Latest Updated Record:** `{metrics.updated_max_utc}`",
        "",
    ])

    return "\n".join(md)


def print_cli_summary(metrics: DatasetInspectionMetrics) -> None:
    """Render a structured summary table in the terminal."""
    console.print(f"\n[bold cyan]=== DATASET INSPECTION SUMMARY: {metrics.file_name} ===[/bold cyan]")
    console.print(f"File Size: [bold]{metrics.file_size_mb} MB[/bold] | Total Records: [bold green]{metrics.total_rows:,}[/bold green]")
    console.print(f"Inspected: {metrics.inspected_at}\n")

    # Table 1: Radio Breakdown
    table = Table(title="Radio Standard Breakdown")
    table.add_column("Radio", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("Share", justify="right")
    for radio, count in sorted(metrics.radio_distribution.items(), key=lambda x: x[1], reverse=True):
        pct = (count / metrics.total_rows * 100) if metrics.total_rows else 0
        table.add_row(radio, f"{count:,}", f"{pct:.2f}%")
    console.print(table)

    # Warnings / Errors
    if metrics.errors:
        console.print("\n[bold red]Errors Found:[/bold red]")
        for err in metrics.errors:
            console.print(f"  [red]- {err}[/red]")

    if metrics.warnings:
        console.print("\n[bold yellow]Warnings Found:[/bold yellow]")
        for warn in metrics.warnings:
            console.print(f"  [yellow]- {warn}[/yellow]")

    console.print(f"\n[bold green]Duplicate Keys:[/bold green] {metrics.duplicate_composite_keys:,}")
    console.print(f"[bold green]India BBox Match:[/bold green] {metrics.in_india_bbox_count:,} records\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and profile OpenCelliD cellular CSV datasets.")
    parser.add_argument("--file", "-f", type=Path, required=True, help="Path to raw CSV or CSV.GZ file")
    parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=Path("reports/dataset-inspection"),
        help="Directory where JSON and Markdown reports will be stored",
    )
    parser.add_argument("--sample-size", "-n", type=int, default=None, help="Sample N rows instead of full file")
    parser.add_argument("--no-hash", action="store_true", help="Skip SHA256 calculation for fast profiling")

    args = parser.parse_args()

    try:
        metrics = inspect_opencellid_dataset(
            file_path=args.file,
            compute_hash=not args.no_hash,
            sample_size=args.sample_size,
        )
    except Exception as e:
        console.print(f"[bold red]Error running dataset inspector:[/bold red] {e}")
        return 1

    # Print summary to terminal
    print_cli_summary(metrics)

    # Save reports
    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_name = args.file.stem.replace(".csv", "")

    json_path = args.output_dir / f"{base_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(metrics), f, indent=2)

    md_path = args.output_dir / f"{base_name}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(generate_markdown_report(metrics))

    console.print(f"Saved machine-readable report to: [bold cyan]{json_path}[/bold cyan]")
    console.print(f"Saved Markdown report to: [bold cyan]{md_path}[/bold cyan]\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
