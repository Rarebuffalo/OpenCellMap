# Streaming Dataset Extraction & Provenance Guide

This document explains the architecture, extensible filter pipeline, dataset manifest provenance, and usage of `scripts/extract_dataset.py`.

---

## 1. Why Streaming Extraction & Provenance?

The OpenCelliD Worldwide Dataset (`cell_towers.csv.gz`) is ~1.2 GB compressed and ~4.5 GB uncompressed, containing over 45 million records across 200+ countries. 

Rather than decompressing and storing 5 GB on disk or loading millions of non-target rows into working memory, the extraction tool (`scripts/extract_dataset.py`):
1. Reads the HTTP binary stream or local file chunk-by-chunk in $64\text{ KB}$ buffers.
2. Validates the CSV header against the official OpenCelliD 14-column specification.
3. Evaluates an extensible filter pipeline (`MCCFilter`, `RadioFilter`, etc.).
4. Writes matching records directly into a target compressed `.csv.gz` file.
5. Computes SHA256 cryptographic hashes and writes an immutable `.manifest.json` alongside the dataset for full provenance.
6. Writes a detailed execution report in `reports/extraction/`.
7. Preserves the exact original header, field order, and byte formatting without modifying or normalizing values.

```
                              OpenCelliD World Export (cell_towers.csv.gz)
                                                   │
                                                   ▼
                                       Streaming Decompressor
                                     (64 KB In-Memory Buffer)
                                                   │
                                                   ▼
                                        Header Schema Validation
                                                   │
                                                   ▼
                                        Extensible Filter Pipeline
                                     (MCCFilter, RadioFilter, etc.)
                                    ┌──────────────┴──────────────┐
                                    ▼                             ▼
                            Matched Records                 Other Records
                                    │                             │
                                    ▼                             ▼
                        Compressed Gzip Writer                 Discarded
                                    │
                                    ▼
                    ┌───────────────────────────────┬───────────────────────────────┐
                    ▼                               ▼                               ▼
    data/raw/india_cell_towers.csv.gz    india_cell_towers.manifest.json    reports/extraction/india.json
```

---

## 2. Dataset Manifest Specification

Every generated dataset produces an accompanying `<dataset>.manifest.json` file recording complete provenance:

```json
{
  "dataset_name": "india_cellular_dataset",
  "source_dataset": "cell_towers.csv.gz",
  "source_checksum": "a3f5b8...",
  "source_version_date": "2026-08-28",
  "extraction_timestamp": "2026-08-28T18:00:00.000000+00:00",
  "extractor_version": "0.2.0",
  "filters_applied": [
    {
      "type": "mcc_filter",
      "target_mccs": ["404", "405"]
    }
  ],
  "rows_processed": 45120000,
  "rows_written": 4650000,
  "malformed_rows": 12,
  "output_checksum": "e7b9c1...",
  "output_size_bytes": 105489000,
  "output_file": "india_cell_towers.csv.gz"
}
```

---

## 3. Strict Header Validation

The extractor verifies that the incoming CSV header contains the exact 14 columns required by the OpenCelliD specification:
```
radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal
```
If columns are missing or corrupted, the extractor raises a `HeaderValidationError` and halts execution immediately.

---

## 4. How to Run Extraction

### Option A: Directly from OpenCelliD HTTP Stream
Configure your `OPENCELLID_API_KEY` in `.env` and execute:
```bash
python scripts/extract_dataset.py \
    --from-opencellid \
    --mcc 404 405 \
    --output data/raw/india_cell_towers.csv.gz
```

### Option B: From a Local World Export File
```bash
python scripts/extract_dataset.py \
    --source data/raw/cell_towers.csv.gz \
    --mcc 404 405 \
    --output data/raw/india_cell_towers.csv.gz
```

### Option C: Optional Multi-Filter (e.g. India LTE Only)
```bash
python scripts/extract_dataset.py \
    --source data/raw/cell_towers.csv.gz \
    --mcc 404 405 \
    --radio LTE \
    --output data/raw/india_lte_towers.csv.gz
```

---

## 5. Resource & Performance Profile

* **Memory Usage:** Constant $O(1)$ memory ($\le 25\text{ MB}$ RSS) via streaming line buffers.
* **Throughput:** Typically $500,000\text{ to }1,000,000\text{ rows/second}$ on modern multi-core systems.
* **Progress Interval:** Logs throughput and match rate every 500,000 rows.
