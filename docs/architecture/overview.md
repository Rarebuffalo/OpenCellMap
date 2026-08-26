# Architecture Overview

## 1. System Vision

The **Open Location Resolution Infrastructure** is an offline-capable, privacy-respecting positioning system. It decouples the core algorithmic positioning logic from both database engines and delivery protocols (such as HTTP APIs or mobile application layers).

```
+-----------------------------------------------------------------------------------+
| APPLICATION LAYER (Independent Consumers)                                         |
| [Android App]      [FMD / Device Recovery]      [Disaster Field App]  [Public API]|
+-----------------------------------------------------------------------------------+
                                       |
                                       v
+-----------------------------------------------------------------------------------+
| CORE RESOLVER ENGINE (Independent Python Library)                                 |
| - Exact Cell-ID Lookup                                                            |
| - Multi-Cell Weighted Centroid Estimation                                         |
| - Uncertainty & Confidence Quantification                                         |
+-----------------------------------------------------------------------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
+------------------------------------+   +------------------------------------------+
| SERVER REPOSITORY (PostgreSQL/GIS) |   | EMBEDDED REPOSITORY (SQLite / Pack)      |
| Used in Online API & Research      |   | Used in Disconnected Mobile Apps         |
+------------------------------------+   +------------------------------------------+
                   ^
                   |
+-----------------------------------------------------------------------------------+
| INGESTION & DATA FOUNDATION LAYER                                                 |
| [OpenCelliD / beaconDB] -> [Parser] -> [Normalizer] -> [Validator] -> [Loader]    |
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Subsystems

### A. Ingestion Layer (Isolated Source Adapters)
External datasets differ in column names, units, and encoding quirks.
* The ingestion subsystem isolates source-specific details in dedicated packages (e.g. `location_resolver.ingestion.opencellid`).
* Output is converted into unified domain structures before touching the database.

### B. Storage Layer (PostgreSQL + PostGIS)
* PostgreSQL stores millions of normalized cell records.
* PostGIS spatial indices (`GIST` on `geometry(Point, 4326)`) allow high-performance radial queries, bounding-box filtering, and distance computations without moving millions of rows into Python memory.

### C. Resolution Core
* Pure algorithmic library accepting `ResolutionRequest` domain objects.
* Never depends on database drivers directly; consumes repository interfaces.
* Quantifies accuracy as an explicit uncertainty radius in meters.
