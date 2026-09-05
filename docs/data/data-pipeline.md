# End-to-End Data Pipeline Architecture

This document explains the complete lifecycle of cellular location data in the Open Location Resolution Infrastructure, from raw vendor exports to spatially indexed database storage.

---

## 1. Overview of the Pipeline

The positioning engine requires clean, reliable, and standardized data. Raw external datasets (such as OpenCelliD) contain global records, anomalies, corrupt coordinates, missing columns, and technology-specific quirks.

To transform raw data into a reliable positioning foundation, data flows through six discrete, isolated stages:

```
+-----------------------------------------------------------------------------------+
| 1. RAW DATA SOURCES (MLS Historical Dumps / beaconDB Open Dumps: *.csv.gz)        |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 2. STREAMING EXTRACTION & PROVENANCE (scripts/extract_dataset.py)                 |
| - Memory-safe chunked decompression                                               |
| - Strict 14-column header schema validation (MLS/OpenCelliD compatible)           |
| - Filter target MCCs (e.g. 404, 405 for India)                                    |
| - Generates: dataset.csv.gz + dataset.manifest.json + extraction report           |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 3. DATASET INSPECTION & PROFILING (scripts/inspect_dataset.py)                     |
| - Streaming statistical profiling                                                 |
| - Radio standard distribution (GSM, UMTS, LTE, NR)                                |
| - Geographic sanity checks (bounding box, Null Island 0,0, out-of-bounds coords)  |
| - Identifies identifier ranges, duplicate composite keys, and samples dispersion  |
| - Generates: inspection report (JSON and Markdown)                                |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 4. VALIDATION & SANITIZATION (src/location_resolver/ingestion/validator.py)       |
| - Rejects mathematically impossible WGS-84 coordinates                            |
| - Quarantines corrupt rows (missing fields, negative identifiers)                 |
| - Flags low-confidence towers (samples = 1, range <= 0)                           |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 5. NORMALIZATION (src/location_resolver/ingestion/normalizer.py)                  |
| - Maps vendor-specific headers to internal Domain Cell Entity                     |
| - Computes technology-specific node IDs (e.g. eNodeB_ID and Sector_ID from ECI)  |
| - Converts timestamps to ISO-8601 UTC                                             |
+-----------------------------------------------------------------------------------+
                                          |
                                          v
+-----------------------------------------------------------------------------------+
| 6. DATABASE PERSISTENCE & SPATIAL INDEXING (PostgreSQL + PostGIS)                 |
| - Fast streaming bulk insertion via PostgreSQL COPY binary/text                   |
| - Composite unique constraints on (radio, mcc, mnc, lac_tac, cell_id)             |
| - GIST Spatial R-Tree Indexing on GEOMETRY(Point, 4326)                           |
+-----------------------------------------------------------------------------------+
```

---

## 2. Detailed Explanation of Each Pipeline Stage

### Stage 1: Raw Data Source
* **What it is:** The uncompressed or gzipped multi-gigabyte export provided by external sources (OpenCelliD World Export `cell_towers.csv.gz`).
* **Why it matters:** Contains 45M+ rows covering the entire globe.
* **Architecture Rule:** The raw source is treated as read-only and is never modified in place.

### Stage 2: Streaming Extraction & Provenance
* **What it is:** A lightweight streaming filter that extracts target country or network records on-the-fly without decompressing 5 GB of raw CSV to disk.
* **Why it matters:** Allows developers and production servers to extract specific regions (e.g., India MCC 404/405) in under a minute with constant memory usage (~15 MB RAM).
* **Provenance Manifest:** Produces an immutable `.manifest.json` recording source checksum, filters applied, row counts, and output SHA256 checksum so that any dataset can be audited and reproduced.

### Stage 3: Dataset Inspection & Profiling
* **What it is:** A read-only analytical tool that computes distributions of coordinates, signal measurements, samples, and duplicates.
* **Why it matters:** Prevents designing database schemas based on incorrect assumptions. Data anomalies (such as Null Island `0.0, 0.0` or out-of-bounds coordinates) are identified empirically before touching the database.

### Stage 4: Source Ingestion Adapter & Normalization (`location_resolver.ingestion.adapter`)
* **What it is:** Converts heterogeneous source headers (such as legacy Indian `404.csv`/`405.csv` and standard OpenCelliD/MLS CSVs) into the canonical `Cell` domain entity (`location_resolver.domain.cell.Cell`).
* **Why it matters:** Isolates vendor-specific representations (`long` -> `longitude`, `lac` -> `lac_tac`, `cid` -> `cell_id`, `sample` -> `samples`, `avgsignal` -> `average_signal`) so downstream database and resolver layers remain strictly source-agnostic. In 4G LTE, it decomposes the 28-bit ECI into underlying `eNodeB_ID` (`CID // 256`) and `Sector_ID` (`CID % 256`).

### Stage 5: Validation & Quality Classification (`location_resolver.ingestion.validator`)
* **What it is:** Strict geometric, telecommunication identifier, and accuracy classification rules applied to canonical `Cell` entities.
* **Why it matters:** Enforces WGS-84 coordinate integrity ($-90 \le \text{lat} \le 90$, $-180 \le \text{lon} \le 180$, rejecting $(0, 0)$ Null Island), validates identifier positive bounds, and classifies coverage radius (`VALID`, `SUSPICIOUS` $> 50\text{ km}$, `INVALID` $\le 0$).

### Stage 6: Database Ingestion (PostgreSQL + PostGIS)
* **What it is:** Bulk loading validated canonical records into relational tables with spatial geometry.
* **Why it matters:** Spatial indexes (`GIST`) enable instant geographic queries (such as finding all towers within 2 kilometers of a point) without loading millions of rows into Python memory.

---

## 3. Separation of Concerns Summary

| Stage | Modifies Values? | Creates Database Records? | Output |
| :--- | :--- | :--- | :--- |
| **Extraction** | No (verbatim subset) | No | `.csv.gz` + `.manifest.json` |
| **Inspection** | No (read-only profiling) | No | `.json` + `.md` reports |
| **Validation** | No (pass or quarantine) | No | Validated stream + error logs |
| **Normalization** | Yes (standardizes types/keys) | No | Internal Domain Objects |
| **Ingestion** | No | Yes (PostgreSQL + PostGIS) | Database rows + Spatial indices |
