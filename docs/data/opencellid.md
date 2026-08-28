# OpenCelliD Source & Export Verification

This document records the empirically verified status of OpenCelliD data availability, export formats, download mechanisms, and regional coverage.

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
* **Download URL:** `https://download.unwiredlabs.com/ocid/downloads?token={token}&file=cell_towers.csv.gz`
* **File Size:** ~160 MB compressed (~750 MB to 1.1 GB uncompressed).
* **Observed Row Count (Empirical Fact):** Exactly **5,372,778 rows**.
* **Source SHA256:** `8a54f13363219a95886e85441ebb8cd64e46eeee3f5ca0e5340b4c5b320bf909` (extracted 2026-08-28).
* **Header:** Includes the standard 14-column header row (`radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal`).
* **Data Freshness Policy:** Contains cell towers observed within a rolling **18-month window**. Older unobserved cell records are pruned from the free open export.
* **Download Restrictions:** Rate limited to **2 downloads per file, per day** per API token. When rate-limited, the server returns HTTP 200 with JSON payload `{"status":"error","message":"RATE_LIMITED",...}` instead of standard HTTP 429.

---

## 2. Empirical Findings: India Cellular Data in World Export

During our live extraction pass on the complete 5,372,778 rows of `cell_towers.csv.gz`:

* **FACT:** Total rows processed = 5,372,778. Malformed rows = 0.
* **FACT:** MCC 404 matches = 0.
* **FACT:** MCC 405 matches = 0.
* **FACT:** Total India matches in current 18-month rolling export = 0.
* **FACT:** The active records in `cell_towers.csv.gz` are predominantly European (e.g. MCC 262 Germany, 208 France, 214 Spain, 222 Italy), North American (MCC 310 USA), and select Middle Eastern/African regions.
* **INFERENCE:** OpenCelliD community stumbler contributions from India have not occurred or have not met the rolling 18-month update threshold in the public open database dump. The historical 2.89 million Indian cells reported on the website statistics reflect cumulative historical telemetry (dating back to 2010) or Unwired Labs' commercial database.
* **ASSUMPTION / NEXT STEP:** To evaluate our schema and positioning resolver with realistic Indian cellular data (MCC 404/405) across all radio technologies (GSM, UMTS, LTE, NR) and network operators (Jio, Airtel, Vi, BSNL), we should either ingest community dumps that preserve historical observations (such as beaconDB or OpenCelliD historical archives) or test against European/US subsets of the live OpenCelliD export alongside representative synthetic/historical Indian fixtures.

---

## 3. Official 14-Column CSV Schema Specification

| Index | Field | Type | Description |
| :--- | :--- | :--- | :--- |
| 0 | `radio` | String | Cellular radio standard (`GSM`, `UMTS`, `LTE`, `NR`, `CDMA`) |
| 1 | `mcc` | Integer | Mobile Country Code (e.g., 404, 405 for India) |
| 2 | `net` | Integer | Mobile Network Code (MNC) |
| 3 | `area` | Integer | Location Area Code (LAC) or Tracking Area Code (TAC) |
| 4 | `cell` | Long Integer | Cell ID (CID for 2G/3G, ECI for LTE, NCI for 5G) |
| 5 | `unit` | Integer | Primary Scrambling Code (UMTS) or Physical Cell ID (LTE/NR) |
| 6 | `lon` | Float | Longitude in decimal degrees (WGS 84) |
| 7 | `lat` | Float | Latitude in decimal degrees (WGS 84) |
| 8 | `range` | Integer | Estimated cell coverage radius in meters |
| 9 | `samples` | Integer | Total number of crowdsourced measurements |
| 10 | `changeable` | Integer | `1` = calculated from crowdsource; `0` = operator verified |
| 11 | `created` | Integer | First recorded UNIX timestamp |
| 12 | `updated` | Integer | Last observed UNIX timestamp |
| 13 | `averageSignal` | Integer | Average recorded signal strength (dBm) |
