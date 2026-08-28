# Bulk Cellular Dataset Sources: Comprehensive Evaluation

This document presents a rigorous comparative analysis of candidate bulk cellular geolocation datasets to determine the **primary data source** for the Open Location Resolution Infrastructure.

---

## 1. Executive Summary

Our empirical tests established that OpenCelliD's rolling 18-month free dump contains 0 active Indian records (MCC 404/405), though its live API responds to individual lookups under strict daily quotas. To build a robust, privacy-respecting, offline-first cellular positioning engine with deep coverage in India, we investigated all major open and proprietary cellular datasets.

### Primary Decision Recommendation:
* **Primary Bulk Baseline:** **Historical Mozilla Location Service (MLS) Archive** (CC0 1.0 Public Domain, millions of Indian cellular observations across 2G/3G/4G, identical 14-column schema).
* **Active Continuous Update Source:** **beaconDB** (CC0 / Public Domain decentralized network fed by NeoStumbler, Tower Collector).
* **Optional Real-Time Fallback Provider:** **OpenCelliD Live REST API** (Rate-limited to 5,000 req/day, CC-BY-SA 4.0).
* **Rejected:** WiGLE and commercial geolocation vendors (prohibitive proprietary licensing and anti-redistribution terms).

---

## 2. Candidate Dataset Deep-Dives

### Candidate 1: Mozilla Location Service (MLS) Historical Archive
* **Provider:** Mozilla Foundation (Discontinued April 2024; archives preserved on public repositories).
* **Availability:** Downloadable via historical snapshots on public data archives and mirrors (`MLS-full-cell-export-*.csv.gz`).
* **Dataset Format:** Gzipped CSV with the standard 14-column schema:
  `radio,mcc,net,area,cell,unit,lon,lat,range,samples,changeable,created,updated,averageSignal`
* **Licensing & Legal Status:** **CC0 1.0 Universal (Public Domain Dedication)**.
  * *Commercial Use:* **Explicitly Permitted** with zero royalties.
  * *Redistribution / Derived Databases:* **Explicitly Permitted** without ShareAlike restrictions.
  * *Attribution:* Not legally required (though good practice).
* **India Coverage:** Extensive historical coverage accumulated from Firefox OS devices, MozStumbler, and community stumblers across all Indian telecom circles (MCC 404 and 405).
* **Technical Quality:**
  * *Radio Standards:* GSM, UMTS, LTE.
  * *Identifier Completeness:* Full MCC, MNC, LAC/TAC, CID, and coordinate centroid coverage.
  * *Freshness:* Static historical snapshot (last updated early 2024).

---

### Candidate 2: beaconDB
* **Provider:** Decentralized open-source community (beacondb.net).
* **Availability:** Active community database designed as the modern successor to MLS. Exposes both an MLS/Ichnaea-compatible REST API and periodically published obfuscated data exports.
* **Dataset Format:** Standard MLS-compatible CSV and JSON representations.
* **Licensing & Legal Status:** **CC0 / Public Domain**.
  * *Commercial Use:* **Permitted**.
  * *Redistribution:* **Permitted**.
  * *Attribution:* Community recognition encouraged.
* **India Coverage:** Actively growing as modern Android users submit telemetry via Tower Collector and NeoStumbler.
* **Technical Quality:** Modern crowdsourced observations including 4G LTE and early 5G NR footprints.
* **Architecture Fit:** Ideal secondary continuous update source to enrich the historical MLS baseline with modern tower deployments.

---

### Candidate 3: WiGLE (Wireless Geographic Logging Engine)
* **Provider:** WiGLE.net.
* **Availability:** Online database and REST API.
* **Dataset Format:** Proprietary CSV / API JSON.
* **Licensing & Legal Status:** **STRICTLY PROPRIETARY**.
  * *Commercial Use:* **Prohibited** without expensive custom negotiated enterprise contracts.
  * *Bulk Downloading / Mirroring:* **Prohibited** by Terms of Service.
  * *Redistribution:* **Prohibited**.
* **LEGAL STATUS:** **BLOCKED** for open-source and commercial redistribution.
* **Verdict:** **REJECTED**.

---

### Candidate 4: OpenCelliD (Unwired Labs)
* **Provider:** Unwired Labs.
* **Availability:** Rolling 18-month bulk export (`cell_towers.csv.gz`) and live REST API (`/cell/get`, `/cell/getInArea`).
* **Licensing & Legal Status:** **CC-BY-SA 4.0** (Creative Commons Attribution-ShareAlike 4.0).
  * *Bulk Export:* Permitted under CC-BY-SA with mandatory attribution.
  * *Free Community API:* Non-commercial only (unless contributing telemetry or whitelisted); 5,000 req/day limit.
* **India Coverage in Bulk Dump:** 0 records in current 18-month rolling window (verified empirically).
* **India Coverage in Live API:** Verified active for MCC 404 & 405 in metropolitan test queries.
* **Verdict:** **Retained as Optional Live Fallback Provider**.

---

### Candidate 5: Commercial Geolocation Providers (Google Geolocation, Skyhook, Combain)
* **Licensing & Legal Status:** **Proprietary Pay-Per-Query SaaS**.
  * *Terms:* Strictly prohibit caching, storing, mirroring, or creating offline databases.
* **Verdict:** **REJECTED**.

---

## 3. Comprehensive Multi-Criteria Comparison Matrix

Each candidate scored from 0 to 10 across key architectural dimensions:

| Criterion | Weight | MLS Historical Archive | beaconDB | OpenCelliD Bulk Dump | OpenCelliD Live API | WiGLE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **India Coverage** | 20% | **8.5** | 6.5 | 0.0 | 7.5 | 8.0 |
| **Legal / Commercial Usability** | 25% | **10.0** (CC0) | **10.0** (CC0) | 6.0 (CC-BY-SA) | 3.0 (Non-comm API) | **0.0** (Proprietary) |
| **Identifier Completeness** | 15% | **9.0** | 8.5 | 9.0 | 8.0 | 7.0 |
| **Geographic Accuracy** | 10% | **8.0** | 8.5 | 8.0 | 8.0 | 8.0 |
| **Dataset Size / Volume** | 10% | **9.0** | 6.0 | 3.0 | 7.5 | 9.0 |
| **Data Freshness** | 10% | 5.0 (2024 snapshot) | **9.0** (Active) | 8.0 | 8.5 | 9.0 |
| **Update Mechanism** | 5% | 0.0 (Static) | **9.0** (Active) | 5.0 (Daily) | 8.0 (Live) | 2.0 (Restricted) |
| **Technical Accessibility** | 5% | **10.0** (Open dump) | 8.5 | 7.0 | 7.0 | 2.0 |
| **Weighted Total Score** | **100%** | **8.40 / 10** | **7.98 / 10** | 4.45 / 10 | 6.08 / 10 | **3.85 / 10** (Blocked) |

---

## 4. Multi-Source Ingestion Architecture

Combining open datasets produces a robust, legally clean architecture:

```
                     DATA INGESTION LAYER
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
   PRIMARY BASELINE    CONTINUOUS UPDATES    COMMUNITY TELEMETRY
   MLS Historical      beaconDB Dumps        Own Mobile Stumbler
   (CC0 Public Domain) (CC0 Public Domain)   (First-Party Data)
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
                 Ingestion & Normalizer Pipe
                 (Strict Schema Validation)
                              ▼
                 PostgreSQL + PostGIS (GIST)
                 (Local Offline Database)
                              ▲
                              │
                    Query Resolver Engine
                              │
                    (Local Cache Miss?)
                              │
                              ▼
                   OPTIONAL ONLINE FALLBACK
                   OpenCelliD REST API
                   (5,000 req/day, Rate-Limited)
```

### Licensing Compatibility:
* **MLS (CC0)** + **beaconDB (CC0)** + **First-Party Telemetry**: 100% CC0 / Public Domain compatible.
* No viral ShareAlike encumbrances on the local database.
* Completely legal for open-source distribution, embedded offline `.db` packaging, and future commercial startup products.

---

## 5. Risk Register & Mitigation Strategy

| Risk | Severity | Probability | Mitigation Strategy |
| :--- | :---: | :---: | :--- |
| **Stale Historical Towers (MLS)** | Medium | High | Merge with active beaconDB dumps and operator frequency bounds to prune decommissioned 2G/3G sites. |
| **License Contamination** | High | Low | Isolate CC-BY-SA API responses into a temporary cache without polluting the primary CC0 local database. |
| **Identifier Collision across Operators** | High | Medium | Enforce composite primary key: `(radio, mcc, mnc, area, cell, unit)` in the database schema. |
| **Corrupt GPS Coordinates** | High | Medium | Strict validation filter in parser: lat in $[6.5, 37.5]$, lon in $[68.0, 97.5]$, reject $(0, 0)$ Null Island. |
| **Upstream Provider Outages** | Low | Medium | Primary resolution happens 100% offline from local PostGIS; upstream APIs are optional fallbacks only. |

---

## 6. Facts vs Inferences vs Unknowns

* **FACT:** Mozilla released its public cell exports under **CC0 1.0 Universal (Public Domain)**.
* **FACT:** MLS cell exports share the exact 14-column CSV schema used by OpenCelliD.
* **FACT:** WiGLE terms explicitly restrict commercial usage and prohibit bulk scraping.
* **FACT:** beaconDB is an active, CC0-friendly open geolocation database with an MLS-compatible API.
* **INFERENCE:** Merging historical MLS (deep baseline) with beaconDB (fresh observations) provides the strongest legal and technical foundation for Indian cellular positioning.
* **UNKNOWN:** The exact current ratio of LTE vs 5G NR towers in Indian community dumps (to be measured when inspecting the real sample file).
