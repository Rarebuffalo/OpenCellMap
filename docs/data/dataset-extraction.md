# Streaming Dataset Extraction Guide

This document explains the design, operation, memory characteristics, and reproducibility of the streaming MCC extraction pipeline.

---

## 1. Why Streaming MCC Extraction?

The OpenCelliD Worldwide Dataset (`cell_towers.csv.gz`) is ~1.2 GB compressed and ~4.5 GB uncompressed, containing over 45 million records across 200+ countries. 

Rather than decompressing and storing 5 GB on disk or loading millions of non-target rows into working memory, the extraction tool (`scripts/extract_mcc.py`):
1. Reads the HTTP binary stream or local file chunk-by-chunk in small $64\text{ KB}$ buffers.
2. Decompresses line-by-line in flight.
3. Inspects column index 1 (`mcc`).
4. Writes matching records (`mcc == 404` or `mcc == 405`) directly into a target compressed `.csv.gz` file.
5. Preserves the exact original 14-column header, field order, and byte formatting without modifying or normalizing values.

```
                              OpenCelliD World Export (cell_towers.csv.gz)
                                                   │
                                                   ▼
                                       Streaming Decompressor
                                     (64 KB In-Memory Buffer)
                                                   │
                                                   ▼
                                           Line-by-Line CSV
                                                   │
                                                   ▼
                                    Filter: MCC in (404, 405)
                                    ┌──────────────┴──────────────┐
                                    ▼                             ▼
                            Match (404/405)                 Other MCCs
                                    │                             │
                                    ▼                             ▼
                        Compressed Gzip Writer                 Discarded
                                    │
                                    ▼
                    data/raw/india_cell_towers.csv.gz
```

---

## 2. Memory & Disk Characteristics

* **Memory Usage:** Constant $O(1)$ memory (~$15\text{ MB}$ maximum resident set size) regardless of whether processing a $1\text{ MB}$ fixture or a $5\text{ GB}$ global stream.
* **Disk Usage:** Only the filtered output is persisted (estimated at ~$80\text{ MB}$ to $150\text{ MB}$ compressed for India's ~4.5M cells), avoiding the need to store the 5 GB global uncompressed database.

---

## 3. How to Run Streaming Extraction

### Option A: From Local World Export File
If you already have `cell_towers.csv.gz` locally:
```bash
python scripts/extract_mcc.py \
    --source data/raw/cell_towers.csv.gz \
    --mcc 404 405 \
    --output data/raw/india_cell_towers.csv.gz
```

### Option B: Directly from OpenCelliD HTTP Stream
Configure your `OPENCELLID_API_KEY` in `.env` and execute:
```bash
python scripts/extract_mcc.py \
    --from-opencellid \
    --mcc 404 405 \
    --output data/raw/india_cell_towers.csv.gz
```

---

## 4. Security & Rate-Limiting Controls

1. **Token Protection:** The API access token is never passed as a plaintext CLI argument in shell history or printed in logs; it is loaded directly from the local `.env` file via `location_resolver.config.settings`.
2. **Download Quota:** OpenCelliD enforces a limit of **2 downloads per file, per day**. Do not run the `--from-opencellid` command repeatedly in a loop.
