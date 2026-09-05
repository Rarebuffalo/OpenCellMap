"""Ingestion adapters, schema mappings, and validation layers."""

from location_resolver.ingestion.adapter import CellSourceAdapter, SourceSchema, detect_schema
from location_resolver.ingestion.validator import CellValidator, RangeClassification, ValidationResult

__all__ = [
    "CellSourceAdapter",
    "SourceSchema",
    "detect_schema",
    "CellValidator",
    "RangeClassification",
    "ValidationResult",
]
