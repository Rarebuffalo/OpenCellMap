# Phase 1: Data Foundation — Engineering Record

This document is the continuous engineering record for Phase 1. It records our goals, environment setup, dataset inspection results, schema design decisions, and verification steps.

---

## 1. Phase Objective

Establish a robust, reproducible data ingestion pipeline that takes raw, external cellular data (specifically OpenCelliD), validates geographic and cellular identifier integrity, normalizes records into a unified internal model, and stores them in PostgreSQL with PostGIS spatial indexing.

---

## 2. Why This Phase Exists

Without a clean, validated data foundation, all subsequent positioning algorithms (single-cell lookup, multi-cell weighted centroiding, fingerprint matching) will produce flawed or misleading results. We must understand actual data anomalies (e.g., coordinates at `0.0, 0.0`, missing area codes, out-of-range signal values) before creating the database schema.

---

## 3. Implementation Milestones

- [x] **Milestone 1.1:** Minimal repository structure, `pyproject.toml`, Docker Compose (PostGIS 3.4), and `.env.example`.
- [x] **Milestone 1.2:** Implement streaming dataset inspection tool (`scripts/inspect_dataset.py`) and synthetic test fixtures.
- [x] **Milestone 1.3:** Source verification: verified OpenCelliD export structure (World Export vs 207 Country Exports table, India MCC 404/405 availability in World Export).
- [ ] **Milestone 1.4:** Obtain verified real dataset export and execute inspection tool.
- [ ] **Milestone 1.5:** Analyze inspection report and formally propose the normalized database schema.
- [ ] **Milestone 1.6:** (Awaiting Approval) Implement PostGIS schema migrations and repository layer.
- [ ] **Milestone 1.7:** Implement parser, normalizer, validator, and bulk loader.
- [ ] **Milestone 1.8:** Ingest and verify dataset with automated integration tests.

---

## 4. Environment & Tooling Choices

* **PostgreSQL 16 + PostGIS 3.4:** Enables spatial indexing (`GIST`) and native geometry operations.
* **Polars:** Provides memory-safe streaming processing for multi-million-row CSV files.
* **Pydantic v2:** Provides strict schema validation and configuration management.
* **Pytest:** Automated test verification for parsers and statistical calculations.

---

## 5. Source Verification Findings

* **Fact:** India is absent from the 207-entry Country Specific Exports table on OpenCelliD.
* **Fact:** Indian cellular data (MCC 404 and MCC 405) is contained inside the Worldwide Dataset (`cell_towers.csv.gz`).
* **Fact:** World Export contains the standard 14-column header, while country exports often omit headers.
* **Fact:** Exports cover observations from a rolling 18-month window.
