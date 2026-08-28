# Architecture Decision Records (ADR)

This document records the foundational architectural decisions made for the Open Location Resolution Infrastructure.

---

## ADR 001: Use PostgreSQL + PostGIS for Server Storage

* **Status:** Accepted
* **Context:** The system must store millions of global cell towers and perform geographic queries (e.g., finding cell towers within a spatial radius or bounding box, calculating geographic centroids).
* **Decision:** We use PostgreSQL 16 with the PostGIS 3.4 spatial extension.
* **Why:**
  * **Simple Explanation:** PostGIS lets PostgreSQL natively understand coordinates on the Earth's curved surface and find nearby points instantly without needing our code to calculate distances across millions of points.
  * **Technical Explanation:** PostGIS adds native spatial data types (`GEOMETRY(Point, 4326)`) and bounding-box R-Tree spatial indexing (`GIST`). This offloads distance checks (`ST_DWithin`, `ST_Distance`) and geographic aggregations directly into the database engine, avoiding memory-intensive in-Python calculations.
* **Alternatives Considered:**
  * *Plain SQLite:* Lightweight, but lacks native R-Tree spatial index performance for multi-million-row server-side ingestion and concurrent multi-client queries. (SQLite will be used later specifically for offline mobile packs).
  * *Elasticsearch / OpenSearch:* Good spatial support, but introduces heavy operational complexity, JVM overhead, and weaker relational integrity constraints.
* **Consequences:** Requires running a PostgreSQL container in local development.

---

## ADR 002: Use Polars for Ingestion and Dataset Inspection

* **Status:** Accepted
* **Context:** OpenCelliD dataset extracts range from hundreds of megabytes (regional) to several gigabytes (global with 45M+ rows). Standard Python CSV processing or Pandas can easily exhaust available system RAM.
* **Decision:** Use `polars` as the streaming and parsing engine for data inspection and batch ingestion.
* **Why:**
  * **Simple Explanation:** Polars processes huge data files in small streaming chunks using all CPU cores in parallel without crashing or running out of memory.
  * **Technical Explanation:** Polars is written in Rust and operates natively on the Apache Arrow columnar memory model. It features query optimization, lazy execution, and chunked streaming, reducing memory footprints by 4x to 10x compared to Pandas.
* **Alternatives Considered:**
  * *Pandas:* High memory overhead ($O(N)$ memory spikes during CSV parsing); single-threaded parsing bottlenecks on large files.
  * *Standard Python `csv` module:* Low memory footprint, but slow and lacks vectorized type inference and statistical profiling operations.
* **Consequences:** Introduces `polars` dependency.

---

## ADR 003: Isolated External Source Adapters

* **Status:** Accepted
* **Context:** Initial data comes from OpenCelliD, but future data may come from beaconDB, MLS archives, or direct user observations.
* **Decision:** Isolate all OpenCelliD-specific parsing, column headers, and quirks under `src/location_resolver/ingestion/opencellid/`.
* **Why:**
  * **Simple Explanation:** If OpenCelliD changes their CSV column names or we switch data providers tomorrow, we only have to change one isolated adapter file instead of refactoring our entire project.
  * **Technical Explanation:** Domain models and repository interfaces remain strictly vendor-agnostic. The adapter converts external raw rows into normalized internal domain objects (`Cell`).
* **Consequences:** Requires an explicit mapping step during ingestion.

---

## ADR 004: Dataset Provenance and Manifest System

* **Status:** Accepted
* **Context:** Ingesting cellular data from external global sources into regional extracts requires strict auditability and reproducibility. Without metadata, it is impossible to know when an extract was generated, which source checksum it came from, or what filters were applied.
* **Decision:** Every generated dataset artifact must automatically create an accompanying `.manifest.json` file containing source checksums, extraction timestamps, extractor version, applied filters, and row counts.
* **Why:**
  * **Simple Explanation:** A manifest tells any developer or auditor exactly where a dataset came from, what filters created it, and proves its integrity with cryptographic checksums.
  * **Technical Explanation:** Provides verifiable provenance and data immutability. Ensures that downstream inspection, validation, and benchmarking results can be traced back to the exact source version.
* **Consequences:** Requires the extraction and ingestion tools to generate and validate manifest JSON files alongside `.csv.gz` files.

---

## ADR 005: Multi-Source Primary Data Sourcing Strategy (CC0 Baseline + beaconDB)

* **Status:** Proposed / Accepted in Research
* **Context:** Empirical testing showed that OpenCelliD's rolling 18-month community public export lacks active Indian records (MCC 404/405), and its live API enforces strict 5,000 req/day caps with non-commercial restrictions. We need a legally clean, high-volume local dataset foundation for India that supports offline packaging and commercial startup viability.
* **Decision:** 
  1. Use **Historical Mozilla Location Service (MLS) Archives** (CC0 1.0 Public Domain) as our foundational bulk offline dataset for Indian cell towers.
  2. Use **beaconDB** (CC0 / Public Domain) as our active continuous update source.
  3. Relegate **OpenCelliD Live REST API** to an **optional online fallback provider** for resolving single cell cache misses.
* **Why:**
  * **Simple Explanation:** CC0 data has zero commercial restrictions, zero viral share-alike requirements, and deep historical coverage across India. OpenCelliD fills in recent individual misses via its API when online.
  * **Technical Explanation:** MLS exports share the exact same 14-column CSV schema (`radio,mcc,net,area,cell,...`) as our existing extractor. CC0 licensing permits building unencumbered offline SQLite databases for mobile distribution without triggering CC-BY-SA copyleft constraints.
* **Consequences:** The ingestion pipeline will support ingesting both MLS-formatted CSV dumps and continuous beaconDB updates, while the query resolver delegates online misses to an optional OpenCelliD adapter.

