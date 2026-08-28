#!/usr/bin/env python3
"""Extensible Streaming Dataset Extractor and Manifest Generator for OpenCelliD.

Processes raw cellular exports in a memory-safe stream, applies configurable filters,
validates schema headers, computes cryptographic hashes on-the-fly, ensures atomic
file generation on success, and produces both the filtered compressed dataset and its
accompanying provenance manifest.
"""

from __future__ import annotations

import abc
import argparse
import datetime
import gzip
import hashlib
import io
import json
import os
import sys
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from rich.console import Console
from rich.table import Table

from location_resolver.config import settings

console = Console()

EXTRACTOR_VERSION = "0.2.0"
OPENCELLID_WORLD_URL_TEMPLATE = (
    "https://download.unwiredlabs.com/ocid/downloads?token={token}&file=cell_towers.csv.gz"
)

# Standard official OpenCelliD CSV 14-column header definition
OFFICIAL_OPENCELLID_COLUMNS = [
    "radio",
    "mcc",
    "net",
    "area",
    "cell",
    "unit",
    "lon",
    "lat",
    "range",
    "samples",
    "changeable",
    "created",
    "updated",
    "averageSignal",
]


class HeaderValidationError(ValueError):
    """Raised when an input dataset header fails schema validation."""
    pass


class RowFilter(abc.ABC):
    """Abstract base filter for streaming dataset extraction."""

    @property
    @abc.abstractmethod
    def filter_type(self) -> str:
        """Name of the filter type."""
        pass

    @abc.abstractmethod
    def matches(self, fields: list[str], header_map: dict[str, int]) -> bool:
        """Evaluate whether a parsed CSV row satisfies the filter condition."""
        pass

    @abc.abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize filter parameters for provenance manifests."""
        pass


class MCCFilter(RowFilter):
    """Filters records by one or more Mobile Country Codes (MCC)."""

    def __init__(self, target_mccs: set[str] | list[str]):
        self.target_mccs = {m.strip() for m in target_mccs}

    @property
    def filter_type(self) -> str:
        return "mcc_filter"

    def matches(self, fields: list[str], header_map: dict[str, int]) -> bool:
        mcc_idx = header_map.get("mcc", 1)
        if len(fields) <= mcc_idx:
            return False
        return fields[mcc_idx].strip() in self.target_mccs

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.filter_type,
            "target_mccs": sorted(list(self.target_mccs)),
        }


class RadioFilter(RowFilter):
    """Filters records by radio access technology (e.g. LTE, GSM, UMTS, NR)."""

    def __init__(self, target_radios: set[str] | list[str]):
        self.target_radios = {r.strip().upper() for r in target_radios}

    @property
    def filter_type(self) -> str:
        return "radio_filter"

    def matches(self, fields: list[str], header_map: dict[str, int]) -> bool:
        radio_idx = header_map.get("radio", 0)
        if len(fields) <= radio_idx:
            return False
        return fields[radio_idx].strip().upper() in self.target_radios

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.filter_type,
            "target_radios": sorted(list(self.target_radios)),
        }


class FilterPipeline:
    """Composite pipeline executing a sequence of RowFilters with short-circuit evaluation."""

    def __init__(self, filters: list[RowFilter] | None = None):
        self.filters: list[RowFilter] = filters or []

    def add_filter(self, row_filter: RowFilter) -> None:
        self.filters.append(row_filter)

    def matches(self, fields: list[str], header_map: dict[str, int]) -> bool:
        if not self.filters:
            return True
        for f in self.filters:
            if not f.matches(fields, header_map):
                return False
        return True

    def to_list(self) -> list[dict[str, Any]]:
        return [f.to_dict() for f in self.filters]


@dataclass
class DatasetManifest:
    """Dataset provenance manifest generated alongside extracted files."""

    dataset_name: str
    source_dataset: str
    source_checksum: str
    source_version_date: str
    extraction_timestamp: str
    extractor_version: str
    filters_applied: list[dict[str, Any]]
    rows_processed: int
    rows_written: int
    malformed_rows: int
    output_checksum: str
    output_size_bytes: int
    output_file: str

    def save_atomic(self, final_path: Path) -> None:
        """Write the manifest formatted as JSON atomically via a temp file."""
        final_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = final_path.parent / f".tmp.{os.getpid()}.{time.time_ns()}.{final_path.name}"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, indent=2)
            os.replace(tmp_path, final_path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass


@dataclass
class ExtractionResult:
    """Summary of an extraction run."""

    manifest: DatasetManifest
    elapsed_seconds: float
    throughput_rows_per_sec: float
    mcc_breakdown: dict[str, int] = field(default_factory=dict)


class HashingBinaryReader(io.RawIOBase, BinaryIO):  # type: ignore[misc]
    """Transparent stream wrapper that computes a SHA256 checksum on-the-fly as bytes are read."""

    def __init__(self, raw_stream: BinaryIO):
        self.raw_stream = raw_stream
        self.hasher = hashlib.sha256()
        self.total_bytes_read = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        chunk = self.raw_stream.read(size)
        if chunk:
            self.hasher.update(chunk)
            self.total_bytes_read += len(chunk)
        return chunk

    def readinto(self, buffer: Any, /) -> int:
        n = self.raw_stream.readinto(buffer)  # type: ignore
        if n and n > 0:
            self.hasher.update(buffer[:n])
            self.total_bytes_read += n
        return n or 0

    @property
    def sha256_hexdigest(self) -> str:
        return self.hasher.hexdigest()


class HashingBinaryWriter(io.RawIOBase, BinaryIO):  # type: ignore[misc]
    """Transparent stream wrapper that computes a SHA256 checksum on-the-fly as bytes are written."""

    def __init__(self, raw_stream: BinaryIO):
        self.raw_stream = raw_stream
        self.hasher = hashlib.sha256()
        self.total_bytes_written = 0

    def writable(self) -> bool:
        return True

    def write(self, b: Any, /) -> int:
        self.hasher.update(b)
        n = self.raw_stream.write(b)
        self.total_bytes_written += len(b)
        return n

    def flush(self) -> None:
        if hasattr(self.raw_stream, "closed") and not self.raw_stream.closed:
            self.raw_stream.flush()

    def close(self) -> None:
        if hasattr(self.raw_stream, "closed") and not self.raw_stream.closed:
            self.flush()
            self.raw_stream.close()
        super().close()

    @property
    def sha256_hexdigest(self) -> str:
        return self.hasher.hexdigest()


class StreamLineReader:
    """Decompresses and yields text lines from a binary stream in chunks."""

    def __init__(self, binary_stream: BinaryIO, is_gzipped: bool = True):
        self.binary_stream = binary_stream
        self.is_gzipped = is_gzipped

    def __iter__(self) -> Iterator[str]:
        if self.is_gzipped:
            gz_file = gzip.GzipFile(fileobj=self.binary_stream, mode="rb")
            text_stream = io.TextIOWrapper(gz_file, encoding="utf-8", errors="replace")
            for line in text_stream:
                yield line
        else:
            text_stream = io.TextIOWrapper(self.binary_stream, encoding="utf-8", errors="replace")
            for line in text_stream:
                yield line


def validate_header(header_line: str, strict: bool = True) -> tuple[list[str], dict[str, int]]:
    """Validate header against official OpenCelliD specification.

    Returns:
        tuple of (header_fields, header_index_map)
    Raises:
        HeaderValidationError if required fields are missing or unexpected.
    """
    raw_fields = [f.strip() for f in header_line.rstrip("\r\n").split(",")]
    header_map = {name: idx for idx, name in enumerate(raw_fields)}

    if strict:
        missing_fields = [col for col in OFFICIAL_OPENCELLID_COLUMNS if col not in header_map]
        if missing_fields:
            raise HeaderValidationError(
                f"Input header fails OpenCelliD schema validation. Missing expected columns: {missing_fields}. "
                f"Observed header: {raw_fields}"
            )

    return raw_fields, header_map


def stream_extract_dataset(
    input_stream: BinaryIO,
    output_path: Path,
    manifest_path: Path,
    report_path: Path | None,
    filter_pipeline: FilterPipeline,
    dataset_name: str = "extracted_cellular_data",
    source_name: str = "opencellid_world_export",
    source_version_date: str = "latest",
    is_input_gzipped: bool = True,
    strict_header_check: bool = True,
    progress_interval_rows: int = 1_000_000,
) -> ExtractionResult:
    """Execute streaming extraction, validate headers, write gzip output atomically, and generate manifest."""
    start_time = time.time()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    # Temporary staging paths for atomic safety
    tmp_output_path = output_path.parent / f".tmp.{os.getpid()}.{time.time_ns()}.{output_path.name}"
    tmp_report_path = (
        (report_path.parent / f".tmp.{os.getpid()}.{time.time_ns()}.{report_path.name}")
        if report_path
        else None
    )

    # Wrap input in on-the-fly hashing stream
    hashing_input = HashingBinaryReader(input_stream)
    line_reader = StreamLineReader(hashing_input, is_gzipped=is_input_gzipped)
    line_iter = iter(line_reader)

    # 1. Validate Header
    try:
        header_line = next(line_iter)
    except StopIteration:
        raise ValueError("Input stream is empty; no header found.")

    header_fields, header_map = validate_header(header_line, strict=strict_header_check)
    mcc_idx = header_map.get("mcc", 1)

    rows_processed = 0
    rows_written = 0
    malformed_rows = 0
    mcc_breakdown: dict[str, int] = {}
    last_log_time = start_time

    try:
        # 2. Stream, Filter, and Hash Output On-the-Fly
        with open(tmp_output_path, "wb") as raw_out_f:
            hashing_writer = HashingBinaryWriter(raw_out_f)
            with gzip.GzipFile(fileobj=hashing_writer, mode="wb", mtime=0.0) as gz_out:
                text_out = io.TextIOWrapper(gz_out, encoding="utf-8", newline="")

                # Preserve original header
                text_out.write(header_line.rstrip("\r\n") + "\n")

                for line_str in line_iter:
                    raw_line = line_str.rstrip("\r\n")
                    if not raw_line.strip():
                        continue

                    rows_processed += 1
                    fields = raw_line.split(",")

                    if len(fields) != len(header_fields):
                        malformed_rows += 1
                        continue

                    if filter_pipeline.matches(fields, header_map):
                        text_out.write(raw_line + "\n")
                        rows_written += 1

                        # Track MCC breakdown
                        row_mcc = fields[mcc_idx].strip()
                        mcc_breakdown[row_mcc] = mcc_breakdown.get(row_mcc, 0) + 1

                    # Progress logging
                    if rows_processed % progress_interval_rows == 0:
                        now = time.time()
                        elapsed = now - start_time
                        segment_rate = progress_interval_rows / max(0.001, now - last_log_time)
                        console.print(
                            f"Progress: [cyan]{rows_processed:,}[/cyan] rows processed | "
                            f"[green]{rows_written:,}[/green] matched | "
                            f"Elapsed: {elapsed:.1f}s | Throughput: {segment_rate:,.0f} rows/s"
                        )
                        last_log_time = now

                text_out.flush()

        # If any trailing unread bytes remain in the stream, drain them to finalize source hash
        while hashing_input.read(64 * 1024):
            pass

        elapsed_seconds = max(0.001, time.time() - start_time)
        throughput = rows_processed / elapsed_seconds

        source_sha256 = hashing_input.sha256_hexdigest
        output_sha256 = hashing_writer.sha256_hexdigest
        output_size_bytes = tmp_output_path.stat().st_size

        # 3. Atomically replace target data file
        os.replace(tmp_output_path, output_path)

        # 4. Generate & Atomically Write Manifest
        manifest = DatasetManifest(
            dataset_name=dataset_name,
            source_dataset=source_name,
            source_checksum=source_sha256,
            source_version_date=source_version_date,
            extraction_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            extractor_version=EXTRACTOR_VERSION,
            filters_applied=filter_pipeline.to_list(),
            rows_processed=rows_processed,
            rows_written=rows_written,
            malformed_rows=malformed_rows,
            output_checksum=output_sha256,
            output_size_bytes=output_size_bytes,
            output_file=output_path.name,
        )
        manifest.save_atomic(manifest_path)

        # 5. Save report atomically if requested
        if report_path and tmp_report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_payload = {
                "manifest": asdict(manifest),
                "performance": {
                    "elapsed_seconds": round(elapsed_seconds, 2),
                    "throughput_rows_per_sec": round(throughput, 1),
                },
                "mcc_breakdown": mcc_breakdown,
            }
            with open(tmp_report_path, "w", encoding="utf-8") as f:
                json.dump(report_payload, f, indent=2)
            os.replace(tmp_report_path, report_path)

        return ExtractionResult(
            manifest=manifest,
            elapsed_seconds=round(elapsed_seconds, 2),
            throughput_rows_per_sec=round(throughput, 1),
            mcc_breakdown=mcc_breakdown,
        )

    except Exception:
        # Cleanup temporary files on failure
        if tmp_output_path.exists():
            try:
                tmp_output_path.unlink()
            except OSError:
                pass
        if tmp_report_path and tmp_report_path.exists():
            try:
                tmp_report_path.unlink()
            except OSError:
                pass
        raise


def extract_from_file(
    input_file: Path,
    output_file: Path,
    manifest_file: Path,
    report_file: Path | None,
    filter_pipeline: FilterPipeline,
    dataset_name: str = "india_cellular_dataset",
    source_version_date: str = "latest",
    strict_header: bool = True,
    progress_interval: int = 1_000_000,
) -> ExtractionResult:
    """Run extraction from a local file (.csv or .csv.gz) with on-the-fly single-pass hashing."""
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    is_gz = input_file.name.endswith(".gz")
    with open(input_file, "rb") as in_stream:
        return stream_extract_dataset(
            input_stream=in_stream,
            output_path=output_file,
            manifest_path=manifest_file,
            report_path=report_file,
            filter_pipeline=filter_pipeline,
            dataset_name=dataset_name,
            source_name=input_file.name,
            source_version_date=source_version_date,
            is_input_gzipped=is_gz,
            strict_header_check=strict_header,
            progress_interval_rows=progress_interval,
        )


def extract_from_http(
    url: str,
    output_file: Path,
    manifest_file: Path,
    report_file: Path | None,
    filter_pipeline: FilterPipeline,
    dataset_name: str = "india_cellular_dataset",
    source_version_date: str = "latest",
    strict_header: bool = True,
    progress_interval: int = 1_000_000,
) -> ExtractionResult:
    """Run extraction directly from an authenticated HTTP stream with on-the-fly hashing."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OpenLocationResolver-Ingestion/0.2.0"},
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        return stream_extract_dataset(
            input_stream=response,
            output_path=output_file,
            manifest_path=manifest_file,
            report_path=report_file,
            filter_pipeline=filter_pipeline,
            dataset_name=dataset_name,
            source_name="opencellid_world_export_http",
            source_version_date=source_version_date,
            is_input_gzipped=True,
            strict_header_check=strict_header,
            progress_interval_rows=progress_interval,
        )


def print_result_table(result: ExtractionResult) -> None:
    """Print clean summary table of extraction results."""
    m = result.manifest
    console.print("\n[bold cyan]=== DATASET EXTRACTION & PROVENANCE SUMMARY ===[/bold cyan]")
    console.print(f"Dataset Name: [bold]{m.dataset_name}[/bold]")
    console.print(f"Output File: [bold cyan]{m.output_file}[/bold cyan] ({m.output_size_bytes:,} bytes)")
    console.print(f"Source Checksum (SHA256): `{m.source_checksum}`")
    console.print(f"Output Checksum (SHA256): `{m.output_checksum}`")
    console.print(f"Extraction Time: {m.extraction_timestamp}")
    console.print(f"Elapsed: [bold green]{result.elapsed_seconds}s[/bold green] | Throughput: [bold green]{result.throughput_rows_per_sec:,.0f} rows/s[/bold green]\n")

    table = Table(title="Row Processing Metrics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total Rows Processed", f"{m.rows_processed:,}")
    table.add_row("Total Rows Written (Matching)", f"{m.rows_written:,}")
    table.add_row("Malformed / Skipped Rows", f"{m.malformed_rows:,}")

    for mcc, count in sorted(result.mcc_breakdown.items()):
        table.add_row(f"  └─ MCC {mcc} Matches", f"{count:,}")

    console.print(table)
    console.print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract filtered cellular datasets and generate provenance manifests.")
    parser.add_argument("--source", "-s", type=Path, help="Path to local .csv or .csv.gz source file")
    parser.add_argument(
        "--from-opencellid",
        action="store_true",
        help="Stream directly from OpenCelliD World Export using OPENCELLID_API_KEY from .env",
    )
    parser.add_argument(
        "--dataset-name",
        type=str,
        default="india_cellular_dataset",
        help="Logical dataset name for manifest provenance",
    )
    parser.add_argument(
        "--mcc",
        "-m",
        nargs="+",
        default=["404", "405"],
        help="Target MCC values to extract (default: 404 405 for India)",
    )
    parser.add_argument(
        "--radio",
        "-r",
        nargs="+",
        default=None,
        help="Optional target radio standards (e.g. LTE GSM UMTS)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/raw/india_cell_towers.csv.gz"),
        help="Target output .csv.gz file path",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Manifest output JSON path (defaults to <output>.manifest.json)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Extraction report output JSON path (defaults to reports/extraction/<name>.json)",
    )
    parser.add_argument(
        "--no-strict-header",
        action="store_true",
        help="Disable strict 14-column header validation (not recommended)",
    )
    parser.add_argument(
        "--progress-interval",
        type=int,
        default=500_000,
        help="Log progress every N rows processed",
    )

    args = parser.parse_args()

    if not args.source and not args.from_opencellid:
        console.print("[bold red]Error:[/bold red] Specify either `--source <file>` or `--from-opencellid`.")
        return 1

    # Configure output paths
    output_path = args.output
    base_stem = output_path.name.replace(".csv.gz", "").replace(".csv", "")
    manifest_path = args.manifest or output_path.parent / f"{base_stem}.manifest.json"
    report_path = args.report or Path(f"reports/extraction/{base_stem}.json")

    # Build Filter Pipeline
    pipeline = FilterPipeline()
    if args.mcc:
        pipeline.add_filter(MCCFilter(args.mcc))
    if args.radio:
        pipeline.add_filter(RadioFilter(args.radio))

    try:
        if args.from_opencellid:
            token = settings.OPENCELLID_API_KEY.strip()
            if not token:
                console.print(
                    "[bold red]Error:[/bold red] OPENCELLID_API_KEY is not set in environment or .env file.\n"
                    "Please set your token in .env before streaming from OpenCelliD."
                )
                return 1

            url = OPENCELLID_WORLD_URL_TEMPLATE.format(token=token)
            console.print("[bold blue]Starting streaming extraction from OpenCelliD World Export...[/bold blue]")
            result = extract_from_http(
                url=url,
                output_file=output_path,
                manifest_file=manifest_path,
                report_file=report_path,
                filter_pipeline=pipeline,
                dataset_name=args.dataset_name,
                strict_header=not args.no_strict_header,
                progress_interval=args.progress_interval,
            )
        else:
            assert args.source is not None
            console.print(f"[bold blue]Starting extraction from local file: {args.source}...[/bold blue]")
            result = extract_from_file(
                input_file=args.source,
                output_file=output_path,
                manifest_file=manifest_path,
                report_file=report_path,
                filter_pipeline=pipeline,
                dataset_name=args.dataset_name,
                strict_header=not args.no_strict_header,
                progress_interval=args.progress_interval,
            )

        print_result_table(result)
        console.print(f"Manifest written to: [bold cyan]{manifest_path}[/bold cyan]")
        if report_path:
            console.print(f"Run report written to: [bold cyan]{report_path}[/bold cyan]\n")
        return 0

    except HeaderValidationError as e:
        console.print(f"\n[bold red]Header Validation Failed:[/bold red] {e}")
        return 1
    except Exception as e:
        console.print(f"\n[bold red]Extraction Error:[/bold red] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
