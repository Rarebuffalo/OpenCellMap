"""Source Ingestion Adapter.

Maps and normalizes heterogeneous external raw cellular records (such as OpenCelliD standard
exports, legacy country archives, and MLS dumps) into canonical Cell domain entities.
"""

from __future__ import annotations

import csv
import datetime
import io
from dataclasses import dataclass, field
from typing import Iterator, Sequence

from location_resolver.domain.cell import Cell, RadioType


class UnknownSchemaError(ValueError):
    """Raised when an input CSV header cannot be mapped to a known source schema."""
    pass


class RowParseError(ValueError):
    """Raised when a raw row cannot be parsed into canonical domain representations."""
    pass


@dataclass(frozen=True)
class SourceSchema:
    """Column index mapping specification for external cellular CSV formats."""

    name: str
    radio_idx: int
    mcc_idx: int
    mnc_idx: int
    lac_tac_idx: int
    cell_id_idx: int
    unit_idx: int | None
    longitude_idx: int
    latitude_idx: int
    range_idx: int
    samples_idx: int
    changeable_idx: int | None
    created_idx: int | None
    updated_idx: int | None
    average_signal_idx: int | None
    expected_column_count: int


def detect_schema(header_fields: Sequence[str]) -> SourceSchema:
    """Detect and construct a SourceSchema from CSV header column names.

    Supports:
    1. Legacy India country export:
       radio,mcc,mnc,lac,cid,changeable_0,long,lat,range,sample,changeable_1,created,updated,avgsignal
    2. Standard OpenCelliD / MLS 14-column export:
       radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
    3. Dynamic header matching for arbitrary permutations of known column names.
    """
    clean_cols = [c.strip().lower() for c in header_fields]
    col_map = {name: idx for idx, name in enumerate(clean_cols)}

    # Check required core identifiers
    radio_idx = col_map.get("radio")
    mcc_idx = col_map.get("mcc")
    mnc_idx = col_map.get("mnc") if "mnc" in col_map else col_map.get("net")
    lac_idx = (
        col_map.get("lac_tac")
        or col_map.get("lac")
        or col_map.get("area")
        or col_map.get("tac")
    )
    cid_idx = (
        col_map.get("cell_id")
        or col_map.get("cid")
        or col_map.get("cell")
        or col_map.get("eci")
    )
    lon_idx = col_map.get("longitude") or col_map.get("lon") or col_map.get("long")
    lat_idx = col_map.get("latitude") or col_map.get("lat")

    missing = []
    if radio_idx is None: missing.append("radio")
    if mcc_idx is None: missing.append("mcc")
    if mnc_idx is None: missing.append("mnc/net")
    if lac_idx is None: missing.append("lac/area")
    if cid_idx is None: missing.append("cid/cell")
    if lon_idx is None: missing.append("lon/long")
    if lat_idx is None: missing.append("lat")

    if (
        missing
        or radio_idx is None
        or mcc_idx is None
        or mnc_idx is None
        or lac_idx is None
        or cid_idx is None
        or lon_idx is None
        or lat_idx is None
    ):
        raise UnknownSchemaError(
            f"Input header cannot be recognized as a valid cellular schema. "
            f"Missing required fields: {missing}. Observed columns: {list(header_fields)}"
        )

    # Optional / quality fields
    unit_idx = (
        col_map.get("unit")
        if "unit" in col_map
        else col_map.get("changeable_0")
        if "changeable_0" in col_map
        else col_map.get("pci")
    )
    range_idx = col_map.get("range_m") or col_map.get("range") or -1
    samples_idx = col_map.get("samples") or col_map.get("sample") or -1
    changeable_idx = (
        col_map.get("changeable")
        if "changeable" in col_map
        else col_map.get("changeable_1")
        if "changeable_1" in col_map
        else None
    )
    created_idx = col_map.get("created_at") or col_map.get("created")
    updated_idx = col_map.get("updated_at") or col_map.get("updated")
    sig_idx = (
        col_map.get("average_signal")
        or col_map.get("averagesignal")
        or col_map.get("avgsignal")
    )

    schema_name = "custom_cellular_csv"
    if "cid" in col_map and "long" in col_map and "sample" in col_map:
        schema_name = "legacy_india_opencellid_csv"
    elif "net" in col_map and "area" in col_map and "cell" in col_map:
        schema_name = "standard_opencellid_mls_csv"

    return SourceSchema(
        name=schema_name,
        radio_idx=radio_idx,
        mcc_idx=mcc_idx,
        mnc_idx=mnc_idx,
        lac_tac_idx=lac_idx,
        cell_id_idx=cid_idx,
        unit_idx=unit_idx,
        longitude_idx=lon_idx,
        latitude_idx=lat_idx,
        range_idx=range_idx,
        samples_idx=samples_idx,
        changeable_idx=changeable_idx,
        created_idx=created_idx,
        updated_idx=updated_idx,
        average_signal_idx=sig_idx,
        expected_column_count=len(header_fields),
    )


class CellSourceAdapter:
    """Converts raw cellular CSV rows into canonical Cell domain entities."""

    def __init__(self, schema: SourceSchema, source_name: str = "unknown"):
        self.schema = schema
        self.source_name = source_name

    @classmethod
    def from_header_line(cls, header_line: str, source_name: str = "unknown") -> CellSourceAdapter:
        """Create adapter by parsing header line string."""
        fields = [f.strip() for f in header_line.rstrip("\r\n").split(",")]
        schema = detect_schema(fields)
        return cls(schema=schema, source_name=source_name)

    def parse_row(
        self,
        row_fields: Sequence[str],
        source_dataset: str | None = None,
    ) -> Cell:
        """Parse a list of string fields into a canonical Cell instance."""
        s = self.schema
        if len(row_fields) < s.expected_column_count:
            raise RowParseError(
                f"Row contains {len(row_fields)} columns; expected {s.expected_column_count} columns."
            )

        try:
            # 1. Parse Radio
            radio_str = row_fields[s.radio_idx].strip()
            radio = RadioType.from_str(radio_str)

            # 2. Parse Integer Identifiers (handle any accidental floats like '404.0')
            mcc = int(float(row_fields[s.mcc_idx].strip()))
            mnc = int(float(row_fields[s.mnc_idx].strip()))
            lac_tac = int(float(row_fields[s.lac_tac_idx].strip()))
            cell_id = int(float(row_fields[s.cell_id_idx].strip()))

            # 3. Parse Unit / PSC / PCI
            unit: int | None = None
            if s.unit_idx is not None and s.unit_idx < len(row_fields):
                u_str = row_fields[s.unit_idx].strip()
                if u_str and u_str != "":
                    try:
                        unit = int(float(u_str))
                    except ValueError:
                        unit = None

            # 4. Parse Coordinates
            lat = float(row_fields[s.latitude_idx].strip())
            lon = float(row_fields[s.longitude_idx].strip())

            # 5. Parse Range & Samples
            range_m = 1000
            if s.range_idx >= 0 and s.range_idx < len(row_fields):
                r_str = row_fields[s.range_idx].strip()
                if r_str:
                    range_m = int(float(r_str))

            samples = 1
            if s.samples_idx >= 0 and s.samples_idx < len(row_fields):
                samp_str = row_fields[s.samples_idx].strip()
                if samp_str:
                    samples = int(float(samp_str))

            # 6. Parse Changeable flag (1 = True, 0 = False)
            changeable = True
            if s.changeable_idx is not None and s.changeable_idx < len(row_fields):
                ch_str = row_fields[s.changeable_idx].strip()
                if ch_str == "0":
                    changeable = False
                elif ch_str in ("1", "true", "True"):
                    changeable = True

            # 7. Parse Timestamps
            created_epoch: int | None = None
            created_at: datetime.datetime | None = None
            if s.created_idx is not None and s.created_idx < len(row_fields):
                c_str = row_fields[s.created_idx].strip()
                if c_str and c_str != "0":
                    try:
                        c_val = int(float(c_str))
                        if c_val > 0:
                            created_epoch = c_val
                            created_at = datetime.datetime.fromtimestamp(
                                float(c_val), datetime.timezone.utc
                            )
                    except (ValueError, OSError):
                        pass

            updated_epoch: int | None = None
            updated_at: datetime.datetime | None = None
            if s.updated_idx is not None and s.updated_idx < len(row_fields):
                u_str = row_fields[s.updated_idx].strip()
                if u_str and u_str != "0":
                    try:
                        u_val = int(float(u_str))
                        if u_val > 0:
                            updated_epoch = u_val
                            updated_at = datetime.datetime.fromtimestamp(
                                float(u_val), datetime.timezone.utc
                            )
                    except (ValueError, OSError):
                        pass

            # 8. Parse Average Signal (0 is treated as missing / None in bulk exports)
            average_signal: int | None = None
            if s.average_signal_idx is not None and s.average_signal_idx < len(row_fields):
                sig_str = row_fields[s.average_signal_idx].strip()
                if sig_str:
                    try:
                        sig_val = int(float(sig_str))
                        # In bulk datasets, 0 is a default null sentinel. Real dBm measurements are negative (e.g. -75 dBm)
                        if sig_val != 0:
                            average_signal = sig_val
                    except ValueError:
                        pass

            return Cell(
                radio=radio,
                mcc=mcc,
                mnc=mnc,
                lac_tac=lac_tac,
                cell_id=cell_id,
                unit=unit,
                latitude=lat,
                longitude=lon,
                range_m=range_m,
                samples=samples,
                changeable=changeable,
                created_at=created_at,
                updated_at=updated_at,
                created_epoch=created_epoch,
                updated_epoch=updated_epoch,
                average_signal=average_signal,
                source=self.source_name,
                source_dataset=source_dataset,
            )

        except Exception as e:
            raise RowParseError(f"Failed to parse row {row_fields}: {e}") from e

    def parse_stream(
        self,
        line_stream: Iterator[str],
        source_dataset: str | None = None,
    ) -> Iterator[Cell]:
        """Streamingly yield Cell domain objects from a text line generator."""
        for line in line_stream:
            raw = line.rstrip("\r\n")
            if not raw.strip():
                continue
            fields = raw.split(",")
            yield self.parse_row(fields, source_dataset=source_dataset)
