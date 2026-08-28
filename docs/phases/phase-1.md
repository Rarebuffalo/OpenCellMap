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
- [x] **Milestone 1.4:** Build extensible dataset extractor (`scripts/extract_dataset.py`) with strict header validation, streaming filters, and manifest provenance system.
- [ ] **Milestone 1.5:** Obtain India dataset via extraction and execute inspection tool.
- [ ] **Milestone 1.6:** Analyze inspection report and formally propose the normalized database schema.
- [ ] **Milestone 1.7:** (Awaiting Approval) Implement PostGIS schema migrations and repository layer.
- [ ] **Milestone 1.8:** Implement parser, normalizer, validator, and bulk loader.
- [ ] **Milestone 1.9:** Ingest and verify dataset with automated integration tests.

---

## 4. Environment & Tooling Choices

* **PostgreSQL 16 + PostGIS 3.4:** Enables spatial indexing (`GIST`) and native geometry operations.
* **Polars & Streaming Gzip Readers:** Provides memory-safe streaming processing for multi-million-row CSV files without disk bloat.
* **Dataset Manifests (JSON):** Implements cryptographic data provenance for every generated extract.
* **Pydantic v2:** Provides strict schema validation and configuration management.
* **Pytest:** Automated test verification for parsers, filters, and manifests.

---

## 5. Architectural Decision: World Export -> Streaming MCC Extraction

* **Decision:** Derive the India dataset (`data/raw/india_cell_towers.csv.gz`) by stream-filtering the World Export (`cell_towers.csv.gz`) for `mcc in (404, 405)`.
* **Why:** OpenCelliD does not provide India as a separate pre-sliced file in the country export table. Streaming extraction processes the global stream on-the-fly, avoiding storing 5 GB uncompressed data on disk.
* **Tradeoffs:** Requires a single download of the ~1 GB world dump or direct HTTP stream, but results in a clean, isolated ~100 MB regional file for all subsequent local development.
