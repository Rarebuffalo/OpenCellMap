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
- [x] **Milestone 1.5:** Execute real streaming extraction on OpenCelliD World Export and inspect empirical results.
- [ ] **Milestone 1.6:** Review empirical findings and formally propose the normalized database schema.
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

## 5. Empirical Extraction Findings (OpenCelliD World Export)

* **Extraction Timestamp:** 2026-08-28T19:34:47 UTC
* **Source Dataset:** `cell_towers.csv.gz` from `https://download.unwiredlabs.com/ocid/downloads`
* **Source Checksum (SHA256):** `8a54f13363219a95886e85441ebb8cd64e46eeee3f5ca0e5340b4c5b320bf909`
* **Extraction Duration:** 55.22 seconds (Throughput: 97,305 rows/second)
* **Total Global Rows Processed:** 5,372,778
* **Header Compliance:** Valid 14-column official OpenCelliD CSV header.
* **Malformed Rows:** 0
* **MCC 404 (India) Rows:** 0
* **MCC 405 (India) Rows:** 0
* **Total Matching India Rows:** 0

### Analysis:
1. **Fact:** The live OpenCelliD World Export snapshot contains 5,372,778 rows total.
2. **Fact:** All 5.37M rows correspond to non-Indian MCCs (primarily European, US, Middle Eastern, and African operators).
3. **Inference:** OpenCelliD applies an 18-month rolling window filter to its free community export. India does not have active community contributors reporting to OpenCelliD within that rolling window, explaining why neither the country table nor the world export contains active Indian cell observations.

---

## 6. OpenCelliD Live API Feasibility Experiment

* **Experiment Date:** 2026-08-29
* **Endpoint Tested:** `https://opencellid.org/cell/get` and `https://opencellid.org/cell/getInArea`
* **Findings:**
  1. **Individual Cell Lookup (`/cell/get`):** Successfully resolved live Indian cell towers for MCC 404 (Airtel, Vi, Vodafone) and MCC 405 (Reliance Jio) in ~450ms–550ms.
  2. **Area Query (`/cell/getInArea`):** Returned 50 Indian cells per bounding box when constrained under the 4 sq km limit.
  3. **Architectural Role:** OpenCelliD is technically viable as an **optional online fallback provider** for single-cell lookups, but its 5,000 req/day quota and non-commercial community restrictions mean it cannot serve as our primary database layer. Full details in `docs/data/opencellid-api-feasibility.md`.

