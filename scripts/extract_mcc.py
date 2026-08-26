#!/usr/bin/env python3
"""Streaming MCC Extractor for OpenCelliD Global Exports.

Extracts records matching specific Mobile Country Codes (e.g. 404, 405 for India)
from a local file or HTTP stream directly into a compressed target file with
constant memory usage.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import os
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterator

from rich.console import Console
from rich.table import Table

# Import project settings for safe token access
from location_resolver.config import settings

console = Console()

OPENCELLID_DOWNLOAD_URL_TEMPLATE = (
    "https://download.unwiredlabs.com/ocid/downloads?token={token}&file=cell_towers.csv.gz"
)


@dataclass
class ExtractionStats:
    """Statistics and integrity metrics for the extraction run."""

    source_description: str = ""
    target_path: str = ""
    target_mccs: set[str] = field(default_factory=set)

    total_rows_read: int = 0
    total_rows_written: int = 0
    mcc_counts: dict[str, int] = field(default_factory=dict)
    malformed_rows_count: int = 0

    elapsed_seconds: float = 0.0
    output_bytes: int = 0
    output_sha256: str = ""


class StreamLineReader:
    """Streams decompressed text lines from an underlying binary stream."""

    def __init__(self, binary_stream: BinaryIO, is_gzipped: bool = True, buffer_size: int = 64 * 1024):
        self.binary_stream = binary_stream
        self.is_gzipped = is_gzipped
        self.buffer_size = buffer_size

    def __iter__(self) -> Iterator[str]:
        if self.is_gzipped:
            # Wrap gzip reader in TextIOWrapper with utf-8 decoding and line buffering
            gz_file = gzip.GzipFile(fileobj=self.binary_stream, mode="rb")
            text_stream = io.TextIOWrapper(gz_file, encoding="utf-8", errors="replace")
            for line in text_stream:
                yield line
        else:
            text_stream = io.TextIOWrapper(self.binary_stream, encoding="utf-8", errors="replace")
            for line in text_stream:
                yield line


def stream_extract_mcc(
    input_stream: BinaryIO,
    output_path: Path,
    target_mccs: set[str],
    is_input_gzipped: bool = True,
    mcc_column_name: str = "mcc",
    mcc_column_index_fallback: int = 1,
) -> ExtractionStats:
    """Stream-process input lines, filtering by target MCCs and writing to a gzipped output file."""
    stats = ExtractionStats(
        target_path=str(output_path),
        target_mccs=target_mccs,
        mcc_counts={mcc: 0 for mcc in sorted(target_mccs)},
    )
    start_time = time.time()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()

    line_reader = StreamLineReader(input_stream, is_gzipped=is_input_gzipped)
    line_iter = iter(line_reader)

    # 1. Read and preserve header line
    try:
        header_line = next(line_iter)
    except StopIteration:
        stats.elapsed_seconds = time.time() - start_time
        return stats

    header_fields = [h.strip() for h in header_line.rstrip("\r\n").split(",")]
    
    # Determine MCC column index
    if mcc_column_name in header_fields:
        mcc_idx = header_fields.index(mcc_column_name)
    else:
        # Fallback index if header is absent or custom
        mcc_idx = mcc_column_index_fallback

    # Write output to gzipped file
    with gzip.open(output_path, mode="wt", encoding="utf-8", newline="") as out_gz:
        # Write preserved header
        out_gz.write(header_line.rstrip("\r\n") + "\n")
        stats.total_rows_written += 1

        # Process data rows line-by-line
        for line_str in line_iter:
            raw_line = line_str.rstrip("\r\n")
            if not raw_line.strip():
                continue

            stats.total_rows_read += 1
            fields = raw_line.split(",")

            if len(fields) <= mcc_idx:
                stats.malformed_rows_count += 1
                continue

            row_mcc = fields[mcc_idx].strip()

            if row_mcc in target_mccs:
                out_gz.write(raw_line + "\n")
                stats.total_rows_written += 1
                stats.mcc_counts[row_mcc] = stats.mcc_counts.get(row_mcc, 0) + 1

    stats.elapsed_seconds = round(time.time() - start_time, 2)

    if output_path.exists():
        stats.output_bytes = output_path.stat().st_size
        with open(output_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        stats.output_sha256 = hasher.hexdigest()

    return stats


def extract_from_local_file(
    input_file: Path,
    output_path: Path,
    target_mccs: set[str],
) -> ExtractionStats:
    """Extract matching MCC rows from a local file (.csv or .csv.gz)."""
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    is_gz = input_file.name.endswith(".gz")
    with open(input_file, "rb") as in_f:
        stats = stream_extract_mcc(
            input_stream=in_f,
            output_path=output_path,
            target_mccs=target_mccs,
            is_input_gzipped=is_gz,
        )
        stats.source_description = f"Local File: {input_file.name} ({input_file.stat().st_size:,} bytes)"
        return stats


def extract_from_http_stream(
    url: str,
    output_path: Path,
    target_mccs: set[str],
) -> ExtractionStats:
    """Extract matching MCC rows by streaming directly from HTTP endpoint without saving full world export."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OpenLocationResolver-Ingestion/0.1.0"},
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        content_len = response.headers.get("Content-Length")
        size_desc = f"{int(content_len):,} bytes" if content_len else "unknown size"
        stats = stream_extract_mcc(
            input_stream=response,
            output_path=output_path,
            target_mccs=target_mccs,
            is_input_gzipped=True,
        )
        stats.source_description = f"HTTP Stream: cell_towers.csv.gz ({size_desc})"
        return stats


def print_extraction_summary(stats: ExtractionStats) -> None:
    """Render a structured extraction summary table in the terminal."""
    console.print("\n[bold cyan]=== STREAMING MCC EXTRACTION SUMMARY ===[/bold cyan]")
    console.print(f"Source: [bold]{stats.source_description}[/bold]")
    console.print(f"Target File: [bold cyan]{stats.target_path}[/bold cyan] ({stats.output_bytes:,} bytes)")
    console.print(f"SHA256: `{stats.output_sha256}`")
    console.print(f"Elapsed Time: [bold green]{stats.elapsed_seconds}s[/bold green]\n")

    table = Table(title="Extraction Breakdown")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="green")

    table.add_row("Total Data Rows Processed", f"{stats.total_rows_read:,}")
    for mcc in sorted(stats.target_mccs):
        count = stats.mcc_counts.get(mcc, 0)
        table.add_row(f"Matching MCC {mcc}", f"{count:,}")

    # Written rows include data rows + 1 header line
    data_rows_written = max(0, stats.total_rows_written - 1)
    table.add_row("Total Matching Data Rows Written", f"{data_rows_written:,}")
    table.add_row("Malformed / Skipped Rows", f"{stats.malformed_rows_count:,}")

    console.print(table)
    console.print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract target MCC cellular records from OpenCelliD exports.")
    parser.add_argument("--source", "-s", type=Path, help="Path to local .csv or .csv.gz file")
    parser.add_argument(
        "--from-opencellid",
        action="store_true",
        help="Stream directly from OpenCelliD World Export using OPENCELLID_API_KEY from environment/.env",
    )
    parser.add_argument(
        "--mcc",
        "-m",
        nargs="+",
        default=["404", "405"],
        help="Target MCC values to extract (default: 404 405 for India)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/raw/india_cell_towers.csv.gz"),
        help="Output target file path (must end in .csv.gz)",
    )

    args = parser.parse_args()
    target_mccs = {str(m).strip() for m in args.mcc}

    if not args.source and not args.from_opencellid:
        console.print("[bold red]Error:[/bold red] Specify either `--source <file>` or `--from-opencellid`.")
        return 1

    try:
        if args.from_opencellid:
            token = settings.OPENCELLID_API_KEY.strip()
            if not token:
                console.print(
                    "[bold red]Error:[/bold red] OPENCELLID_API_KEY is not set in environment or .env file.\n"
                    "Configure it in your local .env file before streaming from OpenCelliD."
                )
                return 1

            url = OPENCELLID_DOWNLOAD_URL_TEMPLATE.format(token=token)
            console.print("[bold blue]Starting streaming download and extraction from OpenCelliD...[/bold blue]")
            stats = extract_from_http_stream(url, output_path=args.output, target_mccs=target_mccs)
        else:
            assert args.source is not None
            console.print(f"[bold blue]Starting streaming extraction from local file: {args.source}...[/bold blue]")
            stats = extract_from_local_file(args.source, output_path=args.output, target_mccs=target_mccs)

        print_extraction_summary(stats)
        return 0

    except Exception as e:
        console.print(f"[bold red]Extraction failed:[/bold red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
