"""High-speed Streaming Bulk Ingestion Loader for PostgreSQL + PostGIS.

Uses PostgreSQL's native COPY protocol via psycopg to ingest multi-million row
cellular datasets with constant memory footprint and high throughput.
"""

from __future__ import annotations

import csv
import io
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from psycopg import sql

from location_resolver.db.connection import get_connection
from location_resolver.domain.cell import Cell
from location_resolver.ingestion.adapter import CellSourceAdapter
from location_resolver.ingestion.validator import CellValidator, RangeClassification


@dataclass
class IngestionStats:
    """Telemetry and metrics recorded during bulk dataset ingestion."""

    source_path: str
    dataset_name: str
    total_rows_read: int = 0
    total_valid_rows: int = 0
    total_invalid_rows: int = 0
    suspicious_range_rows: int = 0
    batch_count: int = 0
    elapsed_seconds: float = 0.0
    throughput_rows_per_sec: float = 0.0


def load_operator_networks(csv_path: Path) -> int:
    """Ingest operator and telecom circle metadata (MCC-MNC mapping) into database."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Operator metadata file not found: {csv_path}")

    inserted_count = 0
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        with get_connection() as conn:
            with conn.cursor() as cur:
                for row in reader:
                    try:
                        mcc = int(row["mcc"].strip())
                        mnc = int(row["mnc"].strip())
                        operator = row.get("operator", "Unknown").strip()
                        circle = row.get("circle", "National").strip()
                        cur.execute("""
                            INSERT INTO operator_networks (mcc, mnc, operator_name, telecom_circle)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (mcc, mnc) DO UPDATE 
                            SET operator_name = EXCLUDED.operator_name,
                                telecom_circle = EXCLUDED.telecom_circle;
                        """, (mcc, mnc, operator, circle))
                        inserted_count += 1
                    except (ValueError, KeyError):
                        continue
            conn.commit()

    return inserted_count


class CellBulkLoader:
    """Streams canonical Cell entities directly into PostGIS using PostgreSQL COPY."""

    COPY_SQL = r"""
        COPY cell_towers (
            radio, mcc, mnc, lac_tac, cell_id, unit,
            latitude, longitude, location,
            range_m, is_suspicious_range, samples, changeable,
            created_at, updated_at, created_epoch, updated_epoch,
            average_signal, source, source_dataset
        ) FROM STDIN WITH (FORMAT text, NULL '\N')
    """

    @staticmethod
    def format_cell_copy_row(cell: Cell) -> str:
        """Convert a canonical Cell into a PostgreSQL COPY text-formatted TSV row."""
        unit_str = str(cell.unit) if cell.unit is not None else r"\N"
        created_at_str = cell.created_at.isoformat() if cell.created_at else r"\N"
        updated_at_str = cell.updated_at.isoformat() if cell.updated_at else r"\N"
        created_epoch_str = str(cell.created_epoch) if cell.created_epoch is not None else r"\N"
        updated_epoch_str = str(cell.updated_epoch) if cell.updated_epoch is not None else r"\N"
        avg_sig_str = str(cell.average_signal) if cell.average_signal is not None else r"\N"
        source_dataset_str = cell.source_dataset if cell.source_dataset else r"\N"
        is_suspicious_str = "t" if cell.range_m > 50000 else "f"
        changeable_str = "t" if cell.changeable else "f"
        
        # PostGIS EWKT Point representation: SRID=4326;POINT(longitude latitude)
        ewkt_location = f"SRID=4326;POINT({cell.longitude:.6f} {cell.latitude:.6f})"

        cols = [
            cell.radio.value,
            str(cell.mcc),
            str(cell.mnc),
            str(cell.lac_tac),
            str(cell.cell_id),
            unit_str,
            f"{cell.latitude:.6f}",
            f"{cell.longitude:.6f}",
            ewkt_location,
            str(cell.range_m),
            is_suspicious_str,
            str(cell.samples),
            changeable_str,
            created_at_str,
            updated_at_str,
            created_epoch_str,
            updated_epoch_str,
            avg_sig_str,
            cell.source,
            source_dataset_str,
        ]
        return "\t".join(cols) + "\n"

    def stream_copy_batch(self, cells: Sequence[Cell]) -> int:
        """Write a batch of Cell objects to PostGIS using COPY."""
        if not cells:
            return 0

        buffer = io.StringIO()
        for cell in cells:
            buffer.write(self.format_cell_copy_row(cell))

        payload = buffer.getvalue()
        with get_connection() as conn:
            with conn.cursor() as cur:
                with cur.copy(sql.SQL(self.COPY_SQL)) as copy:
                    copy.write(payload)
            conn.commit()

        return len(cells)

    def ingest_archive(
        self,
        file_path: Path,
        dataset_name: str,
        source_name: str = "opencellid_legacy",
        batch_size: int = 50000,
        validator: CellValidator | None = None,
        progress_callback: Any = None,
    ) -> IngestionStats:
        """Stream an uncompressed or zipped CSV file directly into PostGIS via COPY.

        Args:
            file_path: Path to the .csv, .zip, or .csv.gz file.
            dataset_name: Label representing the dataset batch (e.g. '404.csv').
            source_name: Provenance source label.
            batch_size: Number of records to buffer before triggering a COPY stream.
            validator: Optional CellValidator instance.
            progress_callback: Optional callable(stats: IngestionStats) invoked periodically.
        """
        stats = IngestionStats(source_path=str(file_path), dataset_name=dataset_name)
        val = validator or CellValidator(max_valid_range_m=50000)
        start_time = time.time()

        def _process_text_stream(text_stream: Iterator[str]) -> None:
            header_line = next(text_stream, None)
            if not header_line or not header_line.strip():
                return

            adapter = CellSourceAdapter.from_header_line(header_line, source_name=source_name)
            batch: list[Cell] = []

            for line in text_stream:
                raw_line = line.strip()
                if not raw_line:
                    continue

                stats.total_rows_read += 1
                try:
                    fields = raw_line.split(",")
                    cell = adapter.parse_row(fields, source_dataset=dataset_name)
                    v_res = val.validate(cell)

                    if not v_res.is_valid:
                        stats.total_invalid_rows += 1
                        continue

                    if v_res.range_classification == RangeClassification.SUSPICIOUS:
                        stats.suspicious_range_rows += 1

                    batch.append(cell)
                    stats.total_valid_rows += 1

                    if len(batch) >= batch_size:
                        self.stream_copy_batch(batch)
                        stats.batch_count += 1
                        batch.clear()
                        if progress_callback:
                            stats.elapsed_seconds = time.time() - start_time
                            stats.throughput_rows_per_sec = stats.total_rows_read / max(0.001, stats.elapsed_seconds)
                            progress_callback(stats)

                except Exception:
                    stats.total_invalid_rows += 1

            if batch:
                self.stream_copy_batch(batch)
                stats.batch_count += 1
                batch.clear()

        # Handle zip or standard text file
        if zipfile.is_zipfile(file_path):
            with zipfile.ZipFile(file_path, "r") as z:
                # Find the primary .csv file inside
                csv_names = [n for n in z.namelist() if n.endswith(".csv")]
                target_csv = csv_names[0] if csv_names else z.namelist()[0]
                with z.open(target_csv, "r") as f:
                    wrapper = io.TextIOWrapper(f, encoding="utf-8", errors="replace")
                    _process_text_stream(wrapper)
        else:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                _process_text_stream(f)

        stats.elapsed_seconds = time.time() - start_time
        stats.throughput_rows_per_sec = stats.total_rows_read / max(0.001, stats.elapsed_seconds)
        return stats
