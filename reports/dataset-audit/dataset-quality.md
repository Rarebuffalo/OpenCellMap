# Dataset Quality & Geographic Integrity Audit Report

**Audit Target:** `404.csv.zip` and `405.csv.zip`  
**Audit Timestamp:** 2026-08-28T21:26:00 UTC  
**Total Records Analyzed:** **2,494,859 cells**  

---

## 1. Executive Quality Summary

| Metric | Measured Value | Quality Assessment |
| :--- | :--- | :--- |
| **Total Indian Cellular Records** | **2,494,859 records** | High Volume (100% India MCC 404/405) |
| **Malformed / Corrupt Rows** | **0** | Perfect 14-column structural integrity |
| **Null Island Coordinates (0.0, 0.0)** | **0** | Clean |
| **Out-of-Bounds WGS-84 Coordinates** | **0** | Clean |
| **Within India Bounding Box** | **2,494,859 (100.00%)** | Fully bounded inside $[6.5^\circ, 37.5^\circ]\text{N}, [68.0^\circ, 97.5^\circ]\text{E}$ |
| **Duplicate Composite Keys** | **0** | 100% unique across `(radio, mcc, mnc, lac, cid)` |
| **Suspicious Range (> 50,000m)** | **587 records (0.02%)** | Isolated outliers requiring clamping during normalization |
| **Observation Span** | June 2008 to April 2023 | 15-year cumulative crowdsourced telemetry |

---

## 2. Radio Technology Breakdown

| Radio Standard | `404.csv` Count | `405.csv` Count | Combined Count | Share (%) |
| :--- | :--- | :--- | :--- | :--- |
| **GSM (2G)** | 987,006 | 365,356 | **1,352,362** | **54.21%** |
| **UMTS (3G)** | 622,989 | 80,885 | **703,874** | **28.21%** |
| **LTE (4G)** | 200,076 | 238,396 | **438,472** | **17.58%** |
| **NR (5G)** | 11 | 125 | **136** | **0.01%** |
| **CDMA** | 15 | 0 | **15** | **< 0.01%** |
| **TOTAL** | **1,810,097** | **684,762** | **2,494,859** | **100.00%** |

---

## 3. Geographic Bounds & Regional Coverage

* **`404.csv` Geographic Extent:**
  * Latitude: `[7.003098, 34.837819]` (Kanyakumari / South to Jammu & Kashmir / North)
  * Longitude: `[68.162613, 96.207962]` (Gujarat / West to Arunachal Pradesh / East)
* **`405.csv` Geographic Extent:**
  * Latitude: `[8.078384, 34.582901]`
  * Longitude: `[68.188705, 96.161270]`
* **Coverage Breadth:** Encompasses all 22 Indian Telecom Circles, covering major metros (Delhi, Mumbai, Bengaluru, Kolkata, Chennai, Hyderabad) as well as Tier-2/Tier-3 towns and rural highways.

---

## 4. Operator Identification & Circle Mapping

* **MCC 404 Operators:** 95 distinct MNCs representing legacy and active operators (Airtel `MNC 10, 45, 49, 92`, Vodafone Idea `MNC 4, 11, 20, 27`, BSNL `MNC 51, 53, 58, 86`).
* **MCC 405 Operators:** 123 distinct MNCs dominated by Reliance Jio (e.g. `MNC 854, 861, 872, 864, 869`) and legacy Reliance/Tata networks.

---

## 5. Schema Comparison & Adapter Requirements

| Standard Field | File Column Header | Required Normalization Mapping |
| :--- | :--- | :--- |
| `radio` | `radio` | Verbatim upper-case (`GSM`, `UMTS`, `LTE`, `NR`) |
| `mcc` | `mcc` | Integer parse |
| `mnc` | `mnc` | Integer parse (maps to `net` in domain entity) |
| `lac_tac` | `lac` | Integer parse (maps to `area` in domain entity) |
| `cell_id` | `cid` | Integer parse (maps to `cell` in domain entity) |
| `pci_psc` | `changeable_0` | Legacy unit field / Scrambling Code |
| `longitude` | `long` | Float parse (maps to `lon`) |
| `latitude` | `lat` | Float parse (maps to `lat`) |
| `range` | `range` | Integer parse (clamp values $> 50000$ to $50000$) |
| `samples` | `sample` | Integer parse (singular in file header) |
| `changeable` | `changeable_1` | Integer parse |
| `created` | `created` | UNIX epoch -> ISO-8601 UTC timestamp |
| `updated` | `updated` | UNIX epoch -> ISO-8601 UTC timestamp |
| `average_signal` | `avgsignal` | Integer parse |
