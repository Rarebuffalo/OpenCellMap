"""Canonical Cellular Domain Entity Model.

Defines source-independent representation for cellular base stations, technology-specific
identifiers, spatial coordinates, accuracy metrics, and provenance metadata.
"""

from __future__ import annotations

import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RadioType(str, Enum):
    """Supported cellular radio access technologies."""

    GSM = "GSM"
    UMTS = "UMTS"
    LTE = "LTE"
    NR = "NR"
    CDMA = "CDMA"

    @classmethod
    def from_str(cls, value: str) -> RadioType:
        """Parse radio string safely, defaulting to upper-case representation."""
        val = value.strip().upper()
        try:
            return cls(val)
        except ValueError:
            # Handle common aliases if any
            if val in ("5G", "5G-NR", "NEW_RADIO"):
                return cls.NR
            if val in ("3G", "WCDMA", "HSPA"):
                return cls.UMTS
            if val in ("2G", "GPRS", "EDGE"):
                return cls.GSM
            if val in ("4G", "LTE-A"):
                return cls.LTE
            raise ValueError(f"Unsupported radio access technology: {value}")


class Cell(BaseModel):
    """Canonical domain representation of a cellular base station/tower observation."""

    model_config = ConfigDict(frozen=True)

    # Core Identifiers
    radio: RadioType = Field(description="Radio access technology standard (GSM, UMTS, LTE, NR, CDMA)")
    mcc: int = Field(description="Mobile Country Code (e.g. 404, 405 for India)")
    mnc: int = Field(description="Mobile Network Code (operator identity)")
    lac_tac: int = Field(description="Location Area Code (2G/3G) or Tracking Area Code (4G/5G)")
    cell_id: int = Field(description="Cell Identity (CID for 2G/3G, ECI for 4G LTE, NCI for 5G NR)")
    unit: int | None = Field(
        default=None,
        description="Physical scrambling code / PCI / sector unit (technology-dependent)",
    )

    # Spatial Coordinates (WGS-84)
    latitude: float = Field(description="WGS-84 Latitude in decimal degrees")
    longitude: float = Field(description="WGS-84 Longitude in decimal degrees")

    # Quality & Estimation Metrics
    range_m: int = Field(default=1000, description="Estimated coverage radius in meters")
    samples: int = Field(default=1, description="Total crowdsourced measurement observations")
    changeable: bool = Field(
        default=True,
        description="True if calculated from crowdsourced averages, False if operator verified",
    )

    # Observation Freshness & Timestamps
    created_at: datetime.datetime | None = Field(
        default=None,
        description="Timezone-aware UTC datetime of first recorded observation",
    )
    updated_at: datetime.datetime | None = Field(
        default=None,
        description="Timezone-aware UTC datetime of latest recorded observation",
    )
    created_epoch: int | None = Field(
        default=None,
        description="Original raw integer UNIX timestamp for exact provenance",
    )
    updated_epoch: int | None = Field(
        default=None,
        description="Original raw integer UNIX timestamp for exact provenance",
    )

    # Signal Metrics
    average_signal: int | None = Field(
        default=None,
        description="Measured average signal strength in dBm (None if missing/unavailable)",
    )

    # Provenance Tracking
    source: str = Field(default="unknown", description="Originating provider or dataset name")
    source_dataset: str | None = Field(default=None, description="Source archive or filename")

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def ensure_utc_timezone(cls, v: Any) -> datetime.datetime | None:
        """Ensure datetimes are timezone-aware UTC."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            if v <= 0:
                return None
            return datetime.datetime.fromtimestamp(float(v), datetime.timezone.utc)
        if isinstance(v, datetime.datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=datetime.timezone.utc)
            return v.astimezone(datetime.timezone.utc)
        return None

    @property
    def composite_key(self) -> tuple[str, int, int, int, int]:
        """Unique natural key composite for cellular base stations."""
        return (self.radio.value, self.mcc, self.mnc, self.lac_tac, self.cell_id)

    @property
    def enodeb_id(self) -> int | None:
        """Derived eNodeB ID for 4G LTE cells (ECI // 256)."""
        if self.radio == RadioType.LTE and self.cell_id > 0:
            return self.cell_id // 256
        return None

    @property
    def lte_sector_id(self) -> int | None:
        """Derived sector ID for 4G LTE cells (ECI % 256)."""
        if self.radio == RadioType.LTE and self.cell_id > 0:
            return self.cell_id % 256
        return None
