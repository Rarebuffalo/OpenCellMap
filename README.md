# Open Location Resolution Infrastructure

An open, privacy-conscious, offline-capable cellular location-resolution infrastructure.

---

## 1. What is this Project?

This project provides an open-source, vendor-independent positioning engine that takes raw cellular observations from a device (such as Mobile Country Code, Mobile Network Code, Tracking Area Code / Location Area Code, Cell ID, and signal metrics) and computes:

* **Estimated Geographic Coordinates** (Latitude, Longitude)
* **Estimated Accuracy / Uncertainty Radius** (in meters)
* **Confidence Metric**
* **Resolution Method & Provenance Metadata**

It is designed to serve as an open positioning layer for offline-first tools, disaster recovery, public transport tracking, lost device recovery (e.g., FMD integration), and privacy-conscious applications.

---

## 2. Project Status & Roadmap

| Subsystem / Phase | Status | Description |
| :--- | :--- | :--- |
| **Phase 0: Research & Architecture** | **COMPLETED** | Analysis of cellular identifiers, OpenCelliD / beaconDB datasets, licensing (CC-BY-SA 4.0), and India coverage. |
| **Phase 1: Data Foundation** | **IN PROGRESS** | Local PostGIS environment, dataset profiler, streaming inspection, schema normalization, and validated bulk ingestion. |
| **Phase 2: Exact Cell Resolver** | *PLANNED* | Base station lookup engine and confidence estimation. |
| **Phase 3: Ground-Truth Evaluation** | *PLANNED* | Benchmarking error distributions (P50, P90, P95) against known GPS fixtures. |
| **Phase 4: Multi-Cell & Advanced Resolution** | *PLANNED* | Weighted multi-cell centroiding and radio fingerprint matching. |
| **Phase 5: Reusable Core Library** | *PLANNED* | Decoupled core positioning library. |
| **Phase 6: Public FastAPI Service** | *PLANNED* | REST API endpoints for online resolution. |
| **Phase 7: Offline Resolver & Packs** | *PLANNED* | SQLite-based regional data packs for completely disconnected operation. |

---

## 3. High-Level Architecture (Phase 1 Focus)

```
                            RAW EXTERNAL DATA
                       (e.g., OpenCelliD CSV / GZ)
                                    |
                                    v
                         DATASET INSPECTION TOOL
                         (Streaming Profiler)
                                    |
                                    v
                      INSPECTION REPORT & METRICS
                   (JSON / Markdown Quality Summary)
                                    |
                                    v
                     INGESTION & VALIDATION PIPELINE
             (Streaming Parser -> Normalizer -> Validator)
                                    |
                                    v
                         POSTGRESQL + POSTGIS
                     (Spatial Indexes & Normalized Tables)
```

---

## 4. Quick Start (Development Setup)

### Prerequisites
* Python 3.11+
* Docker & Docker Compose
* `uv` or `venv` + `pip`

### Step 1: Clone and Set Up Virtual Environment
```bash
# Create and activate virtual environment using uv
uv venv
source .venv/bin/activate

# Install dependencies including dev tools
uv pip install -e ".[dev]"
```

### Step 2: Configure Environment
```bash
cp .env.example .env
```

### Step 3: Start Database Services
```bash
docker compose up -d
```

### Step 4: Run Test Suite
```bash
pytest
```

---

## 5. Dataset Inspection

Before designing or modifying database schemas, we inspect the real dataset using our streaming inspection tool:

```bash
python scripts/inspect_dataset.py --file data/raw/sample_opencellid.csv
```

This generates:
* Terminal summary with key data distributions and quality metrics.
* Machine-readable report in `reports/dataset-inspection/<name>.json`.
* Human-readable report in `reports/dataset-inspection/<name>.md`.

---

## 6. Licensing & Attribution

* **Source Code:** Licensed under the **Apache License, Version 2.0**.
* **Cellular Data Attribution:** Datasets ingested from **OpenCelliD** are licensed under the **Creative Commons Attribution-ShareAlike 4.0 International License (CC-BY-SA 4.0)**. 
  * Attribution: *"Data provided by OpenCelliD (https://opencellid.org)"*.
