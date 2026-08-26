# OpenCelliD Source & Export Verification

This document records the verified status of OpenCelliD data availability, export formats, download mechanisms, and regional coverage.

---

## 1. Verified Export Mechanisms

OpenCelliD provides two primary download mechanisms via token authentication:

### A. Country Specific Exports Table
* **Total Entries in Table:** 207 country files.
* **Format:** Gzipped CSV files (named by MCC, e.g. `<MCC>.csv.gz`).
* **Header Quirk:** Official documentation notes that country-specific exports often omit the CSV header line for legacy compatibility.
* **India Status:** **India (MCC 404 and 405) is NOT present in the current 207-entry Country Specific Exports table.**

### B. Worldwide Dataset (World Export)
* **File Name:** `cell_towers.csv.gz`
* **File Size:** ~900 MB to 1.5 GB compressed (~3.5 GB to 5.0 GB uncompressed).
* **Update Frequency:** Daily snapshot.
* **Header:** Includes the standard 14-column header row.
* **Contents:** Global observations from all MCCs, including India (MCC 404 and 405).
* **Data Freshness Policy:** Contains cell towers observed within a rolling **18-month window**. Older unobserved cell records are pruned by OpenCelliD to maintain network accuracy.
* **Download Restrictions:** Rate limited to **2 downloads per file, per day** per API token.

---

## 2. India Cellular Data Availability

* **Fact:** India is not offered as a pre-split Country Specific Export file in the download portal table.
* **Fact:** Indian cellular records (MCC 404 and 405) are contained within the Worldwide Dataset (`cell_towers.csv.gz`).
* **Strategy:** To work with Indian cellular infrastructure locally without loading the full 45M+ row global dataset into working memory:
  1. Stream `cell_towers.csv.gz` through an on-the-fly decompressor.
  2. Filter lines where `mcc == 404` or `mcc == 405`.
  3. Write the extracted subset to `data/raw/india_cell_towers.csv.gz`.

---

## 3. Official 14-Column CSV Schema Specification

| Index | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| 0 | `radio` | String | Cellular radio standard (`GSM`, `UMTS`, `LTE`, `CDMA`) |
| 1 | `mcc` | Integer | Mobile Country Code (e.g., 404, 405 for India) |
| 2 | `net` | Integer | Mobile Network Code (MNC) |
| 3 | `area` | Integer | Location Area Code (LAC) or Tracking Area Code (TAC) |
| 4 | `cell` | Long Integer | Cell ID (CID for 2G/3G, ECI for LTE) |
| 5 | `unit` | Integer | Primary Scrambling Code (UMTS) or Physical Cell ID (LTE) |
| 6 | `lon` | Float | Longitude in decimal degrees (WGS 84) |
| 7 | `lat` | Float | Latitude in decimal degrees (WGS 84) |
| 8 | `range` | Integer | Estimated cell coverage radius in meters |
| 9 | `samples` | Integer | Total number of crowdsourced measurements |
| 10 | `changeable` | Integer | `1` = calculated from crowdsource; `0` = operator verified |
| 11 | `created` | Integer | First recorded UNIX timestamp |
| 12 | `updated` | Integer | Last observed UNIX timestamp |
| 13 | `averageSignal` | Integer | Average recorded signal strength (dBm) |
