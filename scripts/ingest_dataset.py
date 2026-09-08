#!/usr/bin/env python3
"""CLI Ingestion Tool for Streaming Bulk Loading into PostgreSQL + PostGIS.

Streams cellular dataset archives directly into PostGIS via PostgreSQL COPY,
recording telemetry, validation stats, and execution provenance.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from rich.console import Console
from rich.table import Table

from location_resolver.db.loader import CellBulkLoader, IngestionStats, load_operator_networks
from location_resolver.db.migrator import apply_migrations
from location_resolver.ingestion.validator import CellValidator

console = Console()


def run_ingestion(
    data_dir: Path,
    batch_size: int = 50000,
    load_metadata: bool = True,
    source_name: str = "opencellid_legacy",
    report_output: Path | None = None,
) -> dict:
    """Execute streaming bulk ingestion across all dataset files in data_dir."""
    console.print(f"[bold green]Starting OpenCellMap PostGIS Bulk Ingestion[/bold green]")
    console.print(f"Source Directory: [cyan]{data_dir}[/cyan]")
    console.print(f"Batch Size: [cyan]{batch_size:,} records[/cyan]\n")

    # 1. Ensure migrations are up-to-date
    applied = apply_migrations()
    if applied:
        console.print(f"[dim]Applied migrations: {applied}[/dim]")

    results: dict = {
        "ingestion_started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_directory": str(data_dir),
        "operator_metadata_rows": 0,
        "cellular_files": [],
        "total_records_ingested": 0,
        "total_invalid_records": 0,
        "total_suspicious_range_records": 0,
        "total_elapsed_seconds": 0.0,
    }

    start_total_time = time.time()
    loader = CellBulkLoader()
    validator = CellValidator(target_mccs={404, 405}, max_valid_range_m=50000)

    # 2. Ingest Operator Metadata
    if load_metadata:
        op_csv = data_dir / "MCC-MNC India.csv"
        if op_csv.exists():
            console.print(f"[bold blue]Loading Operator Networks Metadata:[/bold blue] {op_csv.name}")
            op_count = load_operator_networks(op_csv)
            results["operator_metadata_rows"] = op_count
            console.print(f"  [green]Successfully loaded {op_count} operator circle mappings[/green]\n")
        else:
            console.print(f"[yellow]Operator metadata file not found at {op_csv}[/yellow]\n")

    # 3. Discover and Ingest Cellular Archives
    target_files = [
        data_dir / "404.csv.zip",
        data_dir / "405.csv.zip",
    ]

    for file_path in target_files:
        if not file_path.exists():
            # Check for uncompressed fallback
            alt_path = data_dir / file_path.stem
            if alt_path.exists():
                file_path = alt_path
            else:
                console.print(f"[yellow]Target file not found: {file_path}[/yellow]")
                continue

        dataset_name = file_path.stem
        console.print(f"[bold blue]Ingesting Cellular Archive:[/bold blue] {file_path.name}")

        def _on_progress(stats: IngestionStats) -> None:
            console.print(
                f"  Batch {stats.batch_count:,} | "
                f"Processed: {stats.total_rows_read:,} | "
                f"Valid: {stats.total_valid_rows:,} | "
                f"Speed: {stats.throughput_rows_per_sec:,.0f} rows/s",
                end="\r",
            )

        file_stats = loader.ingest_archive(
            file_path=file_path,
            dataset_name=dataset_name,
            source_name=source_name,
            batch_size=batch_size,
            validator=validator,
            progress_callback=_on_progress,
        )

        console.print(f"\n  [green]Completed {file_path.name}:[/green] "
                      f"{file_stats.total_valid_rows:,} rows inserted in {file_stats.elapsed_seconds:.2f}s "
                      f"({file_stats.throughput_rows_per_sec:,.0f} rows/s)\n")

        results["cellular_files"].append(asdict(file_stats))
        results["total_records_ingested"] += file_stats.total_valid_rows
        results["total_invalid_records"] += file_stats.total_invalid_rows
        results["total_suspicious_range_records"] += file_stats.suspicious_range_rows

    results["total_elapsed_seconds"] = time.time() - start_total_time
    results["ingestion_completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # 4. Display Summary Table
    table = Table(title="Bulk Ingestion Summary", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Operator Metadata Mappings", f"{results['operator_metadata_rows']:,}")
    table.add_row("Total Cellular Rows Ingested", f"{results['total_records_ingested']:,}")
    table.add_row("Invalid / Corrupt Rows Quarantined", f"{results['total_invalid_records']:,}")
    table.add_row("Suspicious Range Records (>50km)", f"{results['total_suspicious_range_records']:,}")
    table.add_row("Total Ingestion Time", f"{results['total_elapsed_seconds']:.2f}s")
    if results['total_elapsed_seconds'] > 0:
        overall_throughput = results['total_records_ingested'] / results['total_elapsed_seconds']
        table.add_row("Average Ingestion Throughput", f"{overall_throughput:,.0f} rows/s")

    console.print(table)

    # 5. Write Report JSON if requested
    if report_output:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        console.print(f"\nSaved ingestion audit report to [cyan]{report_output}[/cyan]")

    return results


def main() -> int:
    """CLI entry point for ingest_dataset.py."""
    parser = argparse.ArgumentParser(description="Stream cellular datasets directly into PostGIS via COPY.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("/home/Krishna-Singh/Downloads/dataset-opencellmap"),
        help="Path to directory containing 404.csv.zip, 405.csv.zip, and MCC-MNC India.csv",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50000,
        help="Batch size for COPY streaming (default: 50,000)",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Skip loading operator metadata CSV",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=Path("reports/ingestion/india_cellular_summary.json"),
        help="Path to write ingestion JSON report",
    )

    args = parser.parse_args()
    run_ingestion(
        data_dir=args.data_dir,
        batch_size=args.batch_size,
        load_metadata=not args.no_metadata,
        report_output=args.report_output,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
