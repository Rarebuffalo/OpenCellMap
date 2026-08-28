# Dataset Inventory Audit Report

**Audit Directory:** `/home/Krishna-Singh/Downloads/dataset-opencellmap`  
**Audit Timestamp:** 2026-08-28T21:26:00 UTC  
**Audit Type:** Read-Only Non-Destructive Inspection  

---

## 1. Inventory Summary

| File Name | Compressed Size | Uncompressed Size | Format | SHA-256 Checksum | Category | Record Count |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`404.csv.zip`** | 35.35 MB (37,068,517 B) | 147.66 MB (154,829,565 B) | ZIP -> CSV (14 cols) | `fe05e815ee1c47fd6e1f0e838e58cd4d6df5d47fae306d47310743caeef2cb68` | Raw Cellular Data | **1,810,097** |
| **`405.csv.zip`** | 12.88 MB (13,500,546 B) | 55.50 MB (58,194,302 B) | ZIP -> CSV (14 cols) | `d8255b793ecc1c55297131056c8fb49104078b027c97ca92553f0fa0e8de835b` | Raw Cellular Data | **684,762** |
| **`MCC-MNC India.csv`** | 7.48 KB (7,661 B) | 7.48 KB (7,661 B) | CSV (4 cols) | `4bc46bce8ffab937387f7c58a7a15354f3f487b3b37fa2581118dcba6014b00e` | Metadata / Circle Mapping | **93** |
| **`states_india.geojson.zip`** | 2.05 MB (2,147,056 B) | 7.45 MB (7,809,653 B) | ZIP -> GeoJSON | `adae2dee26f142970111d1cb49619c1b13786e90d7378a22ad7162969646d23c` | Geographic Boundaries | N/A (GeoJSON) |
| **TOTAL** | **50.29 MB** | **210.62 MB** | — | — | — | **2,494,859 cells** |

---

## 2. Dataset Classification & Provenance

### A. `404.csv.zip` and `405.csv.zip`
* **Claimed Dataset Origin:** Historical OpenCelliD Indian Country Exports (Kaggle / OpenCelliD legacy archive).
* **Observed Schema (14 columns):**
  `radio,mcc,mnc,lac,cid,changeable_0,long,lat,range,sample,changeable_1,created,updated,avgsignal`
* **Observation Window:** June 2008 through April 2023.
* **Licensing Evidence:** CC-BY-SA 4.0 (OpenCelliD standard dataset license).
* **Total Indian Cell Coverage:** **2,494,859 distinct cell towers** across MCC 404 (1,810,097) and MCC 405 (684,762).

### B. `MCC-MNC India.csv`
* **Contents:** Official mapping table of Indian MCC+MNC pairs to Telecom Operators (Airtel, Vi, Reliance Jio, BSNL) and Telecom Circles (Delhi, Maharashtra, Karnataka, Tamil Nadu, etc.).
* **Schema (4 columns):** `mcc,mnc,operator,circle`
* **Utility:** Provides immediate operator branding and administrative region tagging during database ingestion.

### C. `states_india.geojson.zip`
* **Contents:** Standard GeoJSON `FeatureCollection` containing high-resolution MultiPolygon boundaries for all Indian States and Union Territories.
* **Utility:** Enables spatial point-in-polygon verification and reverse-geocoding state locations directly within PostGIS (`ST_Contains`).
