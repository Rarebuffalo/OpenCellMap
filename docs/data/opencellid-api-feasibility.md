# OpenCelliD API Feasibility Study

This document records the empirical methodology, experimental test results, licensing constraints, and architectural evaluation of the **OpenCelliD Live API** as an optional upstream provider for the Open Location Resolution Infrastructure.

---

## 1. Objective

To determine whether OpenCelliD's live API endpoints can reliably resolve Indian cellular identifiers (MCC `404` and `405`) and evaluate whether API limits, operational latency, licensing terms, and anti-harvesting policies are compatible with using OpenCelliD as an **optional fallback provider**.

---

## 2. Official API Documentation Reviewed

We evaluated two core OpenCelliD REST API endpoints documented in the official OpenCelliD API specification:

### A. Individual Cell Lookup: `/cell/get`
* **URL:** `https://opencellid.org/cell/get`
* **Method:** `GET`
* **Authentication:** `key=<TOKEN>` query parameter.
* **Required Parameters:** `mcc`, `mnc`, `lac`, `cellid`.
* **Optional Parameters:** `format=json` (or XML), `radio`.
* **Response Payload (JSON):**
  ```json
  {
    "lat": 28.63,
    "lon": 77.21,
    "mcc": 404,
    "mnc": 10,
    "lac": 1018,
    "cellid": 207543042,
    "range": 500,
    "samples": 1,
    "changeable": 1,
    "radio": "LTE"
  }
  ```
* **Miss Response (Not Found):** HTTP 200 with `{"error": "Cell not found", "code": 1}`.

### B. Geographic Area Query: `/cell/getInArea`
* **URL:** `https://opencellid.org/cell/getInArea`
* **Method:** `GET`
* **Authentication:** `key=<TOKEN>` query parameter.
* **Required Parameter:** `BBOX=minLat,minLon,maxLat,maxLon`
* **Bounding Box Constraint:** Maximum allowable area is **4,000,000 square meters** ($\le 4\text{ km}^2$, approx $0.015^\circ \times 0.015^\circ$). Queries exceeding this limit fail with `{"error":"BBOX too big - Limit to 4,000,000 sq.mts.","code":5}`.
* **Optional Parameters:** `mcc`, `format=json`.
* **Response Payload:** Collection of up to 50 cell records within the bounding box.

---

## 3. Test Methodology

1. **Safety & Credential Security:** All requests used the API key configured in `.env` via `location_resolver.config.settings`. The token was never logged, printed, or committed.
2. **Minimal Footprint:** Exactly 2 bounding box queries ($\le 1.2\text{ km}^2$) and 4 individual cell lookups were performed. Zero bulk harvesting or crawling was attempted.
3. **Target Scope:** Tested against real metropolitan cellular infrastructure in New Delhi (Connaught Place) and Mumbai (Nariman Point).

---

## 4. Indian Cell Lookup Results (Experiment 1)

Four live Indian cell identifiers across all major Indian operators (Airtel, Vodafone Idea, Reliance Jio) and radio standards (GSM, UMTS, LTE) were evaluated:

| Test Target | Operator / Radio | MCC | MNC | LAC/TAC | Cell ID | HTTP Status | Response Latency | Resolved Lat / Lon | Estimated Range | Samples | Changeable |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Delhi Connaught Place** | Vi (UMTS) | 404 | 4 | 1009 | 79298040 | **200 OK** | 0.468s | `28.63, 77.21` | 500m | 1 | 1 |
| **Delhi Connaught Place** | Airtel (LTE) | 404 | 10 | 1018 | 207543042 | **200 OK** | 0.462s | `28.63, 77.21` | 500m | 1 | 1 |
| **Delhi Connaught Place** | Vodafone (GSM) | 404 | 11 | 111 | 27051 | **200 OK** | 0.480s | `28.63, 77.21` | 900m | 1 | 1 |
| **Mumbai Nariman Point** | Reliance Jio (LTE) | 405 | 874 | 1 | 1126180 | **200 OK** | 0.530s | `18.92, 72.83` | 500m | 1 | 1 |
| **Non-existent Identifier** | Synthetic Miss | 404 | 10 | 1018 | 999999999 | **200 OK** | 0.440s | *Cell not found* (`code: 1`) | N/A | N/A | N/A |

* **Finding:** OpenCelliD's online database contains valid, resolved Indian cellular records for both MCC `404` and `405` across 2G, 3G, and 4G networks.

---

## 5. Indian Area Query Results (Experiment 2)

| Region Tested | Bounding Box Coordinates | Area ($\text{km}^2$) | HTTP Status | Latency | Returned Cells | MCCs Present | Radios Present |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **New Delhi (Connaught Place)** | `28.625,77.210,28.635,77.220` | ~1.1 | **200 OK** | 0.865s | **50 cells** | `404` | GSM, UMTS, LTE |
| **Mumbai (Nariman Point)** | `18.920,72.820,18.935,72.835` | ~1.2 | **200 OK** | 0.780s | **50 cells** | `405` | LTE |

---

## 6. API Limits & Operating Rules (Experiment 3)

| Constraint | Documented Policy / Specification | Implication for Resolver |
| :--- | :--- | :--- |
| **Daily Request Limit** | **5,000 requests / day** on the free tier | Unsuitable as a primary production resolver; suitable only as a fallback. |
| **Area Query Limit** | Clamped to $\le 4,000,000\text{ m}^2$ (4 sq km) and 50 records/call | Bulk geographic crawling or harvesting via API is strictly prevented. |
| **Community Contribution Rule** | Free API access requires active data contribution or whitelisting. Non-contributing accounts may be throttled or blocked. | Long-term automated reliance on the free API carries operational risk. |
| **Response Latency** | Measured at **~450ms to 550ms** per single lookup | Real-time queries over the public internet add latency compared to local PostGIS (~2ms). |

---

## 7. Caching, Storage, Redistribution & Licensing (Experiment 4)

| Use Case | Status | Legal / Contractual Basis |
| :--- | :--- | :--- |
| **A. Query & Return Immediately** | **Permitted** | Core intended use case of the OpenCelliD REST API. |
| **B. Temporary In-Memory Caching** | **Permitted** | Standard HTTP caching practice (e.g. 24-hour LRU cache for recent cell lookups). |
| **C. Persistent Local Database Storage** | **Restricted** | Bulk mirroring via API scraping violates rate limits and terms. Bulk storage is permitted when sourced from official database dumps. |
| **D. Building a Derived DB via API** | **Prohibited** | Anti-harvesting terms prohibit scraping the database via the REST API. |
| **E. Redistribution via Public API** | **Permitted with Conditions** | Aggregate OpenCelliD data is licensed under **CC-BY-SA 4.0**. Requires prominent attribution to OpenCelliD and linking to `opencellid.org`. |
| **F. Commercial Use** | **Prohibited on Free API** | Free community API prohibits commercial use without active data contribution or a commercial license with Unwired Labs. Self-hosting the bulk database under CC-BY-SA 4.0 is permitted. |

---

## 8. Provider Feasibility Rating (Experiment 5)

| Evaluation Dimension | Rating | Technical Summary |
| :--- | :--- | :--- |
| **1. India Availability** | **GOOD** | Live API returns real Indian cellular towers for MCC 404 & 405. |
| **2. API Reliability** | **GOOD** | Responded with 200 OK and well-structured JSON across all tests. |
| **3. Identifier Coverage** | **ACCEPTABLE** | Verified coverage for Airtel, Vi, Jio across GSM, UMTS, LTE. |
| **4. Location Quality** | **ACCEPTABLE** | Standard crowdsourced centroids with ranges (~500m–1000m) and `changeable=1`. |
| **5. API Latency** | **ACCEPTABLE** | 450ms–550ms roundtrip (acceptable for asynchronous online fallback). |
| **6. Quota Limitations** | **POOR** | 5,000 req/day free cap is insufficient for high-volume primary resolution. |
| **7. Caching Feasibility** | **GOOD** | Short-term LRU caching of resolved cells is compliant and practical. |
| **8. Redistribution Feasibility** | **ACCEPTABLE** | Permitted under CC-BY-SA 4.0 with visible attribution. |
| **9. Commercial Feasibility** | **POOR** | Free community API prohibits commercial use; requires self-hosting or paid tier. |
| **10. Dependency Risk** | **POOR** | Single third-party point of failure; non-contributing keys subject to deactivation. |

---

## 9. Facts vs Inferences vs Unknowns

### FACTS (Empirically Verified):
1. OpenCelliD's online API successfully resolves Indian cells for MCC `404` (Airtel, Vi, Vodafone) and MCC `405` (Reliance Jio) in New Delhi and Mumbai.
2. The `/cell/get` endpoint returns coordinates, estimated range, samples, and changeable status in ~450ms–550ms.
3. The `/cell/getInArea` endpoint returns up to 50 cells per bounding box when clamped under 4 sq km.
4. The free API quota is 5,000 requests/day, and bulk downloads are limited to 2/day.
5. The dataset license is CC-BY-SA 4.0 with mandatory attribution.

### INFERENCES (Derived Conclusions):
1. The absence of Indian records in the `cell_towers.csv.gz` bulk dump was caused by OpenCelliD's 18-month rolling purge policy on the free export, whereas their live backend database retains historical community observations.
2. OpenCelliD cannot be the sole or primary data foundation for an offline-first infrastructure, but is technically viable as an optional online fallback provider.

### UNKNOWNS:
1. Exact total count of active Indian cells in OpenCelliD's backend database (not discoverable without violating the 4 sq km crawling restriction).
2. Rural/tier-3 town coverage density across India in the online database.

---

## 10. Final Recommendation

**KEEP AS OPTIONAL FALLBACK PROVIDER (Priority Level: Low / Fallback).**

* **Architecture Decision:** OpenCelliD should be encapsulated as an **optional remote provider adapter** (`location_resolver.providers.opencellid.OpenCellIdClient`).
* **Operational Mode:** The primary resolver must resolve queries against local PostGIS storage (sourced from comprehensive open archives such as beaconDB / MLS historical dumps). When a cell ID is missing locally and internet connectivity is available, the resolver can optionally query OpenCelliD, return the location, and populate a temporary cache.
