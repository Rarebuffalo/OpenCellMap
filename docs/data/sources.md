# External Data Sources & Licensing

This document tracks all external datasets used by the project, their licensing constraints, schemas, and attribution requirements.

---

## 1. OpenCelliD (Initial Source)

* **Provider:** Unwired Labs / OpenCelliD Community
* **Website:** https://opencellid.org/
* **License:** Creative Commons Attribution-ShareAlike 4.0 International (CC-BY-SA 4.0)
* **Access Method:** Daily differential and snapshot CSV downloads requiring an API access token.

### Schema Documentation (Official OpenCelliD Specification)
| Field | Type | Description |
| :--- | :--- | :--- |
| `radio` | String | Cellular radio standard (`GSM`, `UMTS`, `LTE`, `CDMA`) |
| `mcc` | Integer | Mobile Country Code (e.g., `404`, `405` for India) |
| `net` | Integer | Mobile Network Code (MNC) |
| `area` | Integer | Location Area Code (LAC) or Tracking Area Code (TAC) |
| `cell` | Long Integer | Cell ID (CID for 2G/3G, ECI for LTE) |
| `unit` | Integer | Primary Scrambling Code (UMTS) or Physical Cell ID (PCI for LTE) |
| `lon` | Float | Longitude in decimal degrees (WGS 84) |
| `lat` | Float | Latitude in decimal degrees (WGS 84) |
| `range` | Integer | Approximate coverage radius in meters |
| `samples` | Integer | Number of distinct crowdsourced observation measurements |
| `changeable` | Integer | `1` = calculated from crowdsourced stumbles; `0` = verified coordinates |
| `created` | Integer | Creation UNIX timestamp |
| `updated` | Integer | Last observed UNIX timestamp |
| `averageSignal` | Integer | Average received signal strength (where recorded) |

### Licensing Compliance & Attribution
* Any publicly deployed service or distributed database derived from OpenCelliD must visibly provide attribution:
  > *"Cellular location data provided by OpenCelliD (https://opencellid.org), licensed under CC-BY-SA 4.0."*
* If modified databases or offline packs are distributed directly to end users, the data files must be distributed under the CC-BY-SA 4.0 license. (The application code querying the database remains under Apache 2.0).

---

## 2. beaconDB (Planned Complementary Source)

* **Provider:** BeaconDB Community
* **Website:** https://beacondb.net/
* **License:** Public Domain / Creative Commons CC0
* **Status:** In active development as an open, privacy-centric alternative to MLS. Future data dumps will be integrated to augment OpenCelliD coverage without ShareAlike restrictions.
