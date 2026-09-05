"""Cell Validation and Quality Classification Layer.

Applies strict geometric, telecommunication identifier, accuracy range, and temporal
validation rules to canonical Cell domain entities, generating structured ValidationResults.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum

from location_resolver.domain.cell import Cell


class RangeClassification(str, Enum):
    """Classification status for cell coverage range estimations."""

    VALID = "VALID"            # Normal expected cell radius (1m - 50,000m)
    SUSPICIOUS = "SUSPICIOUS"  # Extremely large estimated radius (> 50,000m)
    INVALID = "INVALID"        # Zero or negative range value


@dataclass
class ValidationResult:
    """Detailed outcome of validating a canonical Cell entity."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    range_classification: RangeClassification = RangeClassification.VALID

    def add_error(self, message: str) -> None:
        """Record a validation failure."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str) -> None:
        """Record a non-fatal anomaly or quality note."""
        self.warnings.append(message)


class CellValidator:
    """Configurable validator for cellular domain entities."""

    def __init__(
        self,
        target_mccs: set[int] | list[int] | None = None,
        max_valid_range_m: int = 50_000,
        enforce_regional_bbox: tuple[float, float, float, float] | None = None,
    ):
        """Initialize validator with optional regional rules.

        Args:
            target_mccs: Optional set of allowed/expected MCCs (e.g. {404, 405} for India).
            max_valid_range_m: Upper boundary in meters above which range is classified as SUSPICIOUS.
            enforce_regional_bbox: Optional (min_lat, min_lon, max_lat, max_lon) boundary check.
        """
        self.target_mccs = set(target_mccs) if target_mccs else None
        self.max_valid_range_m = max_valid_range_m
        self.enforce_regional_bbox = enforce_regional_bbox

    def validate(self, cell: Cell) -> ValidationResult:
        """Validate a Cell instance against geometric, identifier, and quality constraints."""
        result = ValidationResult(is_valid=True)

        # 1. Geographic Coordinate Integrity (WGS-84)
        if not (-90.0 <= cell.latitude <= 90.0):
            result.add_error(f"Latitude out of bounds [-90, 90]: {cell.latitude}")

        if not (-180.0 <= cell.longitude <= 180.0):
            result.add_error(f"Longitude out of bounds [-180, 180]: {cell.longitude}")

        if cell.latitude == 0.0 and cell.longitude == 0.0:
            result.add_error("Coordinates located at Null Island (0.0, 0.0)")

        # Optional regional bounding box check
        if self.enforce_regional_bbox and result.is_valid:
            min_lat, min_lon, max_lat, max_lon = self.enforce_regional_bbox
            if not (min_lat <= cell.latitude <= max_lat and min_lon <= cell.longitude <= max_lon):
                result.add_warning(
                    f"Coordinates [{cell.latitude}, {cell.longitude}] fall outside regional bounding box "
                    f"[{min_lat}, {min_lon}, {max_lat}, {max_lon}]"
                )

        # 2. Telecommunication Identifiers
        if cell.mcc <= 0:
            result.add_error(f"MCC must be positive integer: {cell.mcc}")

        if cell.mnc < 0:
            result.add_error(f"MNC cannot be negative: {cell.mnc}")

        if cell.lac_tac <= 0:
            result.add_error(f"Area code (LAC/TAC) must be positive: {cell.lac_tac}")
        elif cell.lac_tac > 65535:
            # 2G/3G/4G LAC/TAC is typically 16-bit unsigned (max 65535)
            result.add_warning(f"Area code exceeds standard 16-bit maximum (65535): {cell.lac_tac}")

        if cell.cell_id <= 0:
            result.add_error(f"Cell ID must be positive integer: {cell.cell_id}")

        # Regional MCC check
        if self.target_mccs is not None and cell.mcc not in self.target_mccs:
            result.add_warning(f"Cell MCC {cell.mcc} not in configured target MCC set {self.target_mccs}")

        # 3. Coverage Range Classification
        if cell.range_m <= 0:
            result.range_classification = RangeClassification.INVALID
            result.add_warning(f"Cell coverage range <= 0 meters: {cell.range_m}")
        elif cell.range_m > self.max_valid_range_m:
            result.range_classification = RangeClassification.SUSPICIOUS
            result.add_warning(
                f"Cell coverage range ({cell.range_m:,}m) exceeds threshold ({self.max_valid_range_m:,}m)"
            )
        else:
            result.range_classification = RangeClassification.VALID

        # 4. Observation Samples
        if cell.samples <= 0:
            result.add_warning(f"Sample count <= 0: {cell.samples}")

        # 5. Timestamp Consistency
        if cell.created_epoch is not None and cell.updated_epoch is not None:
            if cell.updated_epoch < cell.created_epoch:
                result.add_warning(
                    f"Updated timestamp ({cell.updated_epoch}) precedes created timestamp ({cell.created_epoch})"
                )

        if cell.created_epoch is not None:
            # Year 2000 epoch = 946684800. Cellular crowdsourcing did not exist before 2000.
            if cell.created_epoch < 946684800:
                result.add_warning(f"Created timestamp is unrealistically old (< year 2000): {cell.created_epoch}")

        # 6. Average Signal (dBm)
        if cell.average_signal is not None:
            # Cellular signals in dBm are negative numbers (typically -140 dBm to -40 dBm)
            if cell.average_signal > 0 or cell.average_signal < -150:
                result.add_warning(
                    f"Recorded average signal ({cell.average_signal} dBm) outside expected range [-150, 0] dBm"
                )

        return result
