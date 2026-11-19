# Plan: one pipeline, five study areas

Today the pipeline has one study area (LA) split into eight range boxes. The change adds an **area** level above
the ranges. Each area has its own projection, ranges, home point, data sources and score settings, and gets its
own map. Pick the area with `AREA=<key>` (default `la`), and the range with `REGION=<key>` as today.

| Area key | Area | UTM | NHD HU4 | Home (drive times) | Draft ranges (boxes) |
|---|---|---|---|---|---|
| `la` | LA mountains (today's eight ranges) | 11N | 1803–1810 | 90404 | unchanged |
| `jackson` | Jackson Hole & Hoback | 12N | 1704, 1404 | 83001 (town square) | Tetons (east slope) + Snake River Range north end; Gros Ventre; Hoback basin (Granite, Cliff, Shoal creeks) + Hoback Range |
| `n_georgia` | North Georgia mountains + Atlanta tailwater | 17N | 0313, 0315, 0306, 0601 | 30305 | Cohutta / Jacks / Conasauga; Toccoa / Blue Ridge; Chattahoochee headwaters / Dukes / Smith creeks; Rabun / Chattooga / Tallulah; Chattahoochee tailwater below Buford Dam to Atlanta (Buford Dam → Peachtree Creek corridor only) |
| `central_vt` | Central Vermont | 18N | 0415, 0108 | 05753 | Middlebury River / Ripton / Breadloaf / White River; Mad River / Winooski / New Haven River; Stowe / Lamoille headwaters. Boxes reach west to 73.25° W so Middlebury's own creeks are in |
| `ne_ct` | Northeastern Connecticut | 18N | 0110 (+0108, 0109 edges) | 06281 | Natchaug / Fenton / Mount Hope; Quinebaug / Five Mile / Moosup / Pachaug |
| `lexington_va` | Lexington, Virginia | 17N | 0208, 0207 | 24450 | Maury River / Goshen Pass / Buffalo Creek; Blue Ridge: St. Mary's, Irish Creek, upper South River |

The boxes are drafts (in `config.py` as UTM boxes). They get firmed up from the HUC-10 watersheds so a box edge cuts
as few creeks as possible. Rural ZIPs span whole valleys, so their home points are the town centres.

## Decisions (2026-11-18)
- Pilot area: **NE Connecticut**.
- Thermal score: the elevation band is replaced by **PRISM August mean air temperature in every area, LA included**,
  so "cold enough" means the same thing everywhere. LA scores will shift; the change goes in as its own step after the
  refactor, so the shift can be checked on its own.
- LA's data and outputs move under `la/`.
- Lexington, VA added as a sixth area.

## Layout
- `config.py`: `AREAS = {area: dict(label, crs, home, ranges={...}, score={...}, sources={...})}`. `CRS`, `HOME`,
  the ranges list and every tuned constant come from the selected area. Nothing area-specific stays hard-coded
  in the scripts.
- Paths: `data/raw/<area>/<range>`, `data/derived/<area>/<range>`, `output/<area>/...`. National downloads (NHD HU4,
  PRISM) go to `data/raw/_national`; what an area's ranges share (trails, roads, flow, wilderness, caches) to
  `data/raw/<area>/_shared`. LA's existing data and outputs move to `<area>=la` with
  one `mv`, so nothing is recomputed. `phone/` and `creek-map/` get one copy per area.
- The `EPSG:26911` literals (06_map 15×, geomatch, labelpaths, 07, 11) become `config.CRS`.

## What each CA-only source becomes
| Today (LA) | Other areas | Notes |
|---|---|---|
| TNC California Natural Flows (summer flow, per year) | **NOAA National Water Model retrospective v3** (hourly per NHDPlus V2 COMID, 1979–2023, public on AWS). Same "share of summers ≥0.1 cfs" metric | Same COMID network 05b already uses. Needs a feasibility test (zarr read for a few thousand COMIDs). Fallback: NHDPlus EROM monthly means + NHD class (no year-to-year spread) |
| CDFW surveys, stocking, Wild/Heritage Trout Waters | **WY**: WGFD stream classes, cutthroat range. **GA**: DNR designated trout streams (primary/secondary), weekly stocking. **VA**: DWR wild trout streams (class lists), stocking schedule. **VT**: Fish & Wildlife stream surveys, stocking. **CT**: DEEP fish-community surveys, Wild Trout / Trout Management Areas, stocking. **East (GA, VT, CT, VA)**: EBTJV brook trout patches | One adapter per state, same output columns (`trout_found`, `survey_year`, `stocked`, `trout_water`) |
| iNaturalist rainbow + brown trout | Add brook trout and cutthroat (Snake River fine-spotted) | National already |
| CAL FIRE perimeters | NIFC interagency fire perimeter history (national) | BAER, WFIGS and USGS debris-flow already national |
| CPAD restricted access | PAD-US (national, with public-access field) | |
| CDEC Piru gauges | none; USGS only | |
| PCT layer | Per-area long trails from OSM relations: **AT** (GA, VT, VA), **Long Trail** (VT), **Benton MacKaye / Bartram** (GA), **Nipmuck** (CT); none for Jackson | Rename the layer "Long-distance trails" |
| Caltrans + 4 county closure feeds | Per-state 511 adapters (WYDOT, 511GA, New England 511 for VT, CTDOT, VDOT 511) where an open feed exists; else off | Phase 2 |
| NPS Santa Monica, State Parks, Eaton closure layers | dropped outside LA; USGS National Digital Trails, USFS MVUM and wilderness are national | Grand Teton NP: no bikes on trails (NPS rule) |
| `TAILWATERS` (Cogswell, Pyramid) | Jackson Lake Dam → Snake; **Buford Dam → Chattahoochee**; Blue Ridge Dam → Toccoa; Lake Burton/Seed/Rabun → Tallulah?; none known in VT / NE CT / Lexington yet | Per area |
| `DIVERSIONS`, `NAME_FIX`, `FORK_FIX`, `AQUATIC` species | Per area (empty to start) | |

## Score settings that move per area
| Setting | LA | Draft for new areas | How it gets set |
|---|---|---|---|
| Elevation part of thermal | 700–2300 m band | PRISM August mean air temperature, every area (decided) | Band limits set from where trout are recorded, across all areas |
| Heat gate start | 29.0 °C | Hottest trout record in the area + 2 °C, same rule as LA | Computed by `11_context.py` from that area's trout records, then fixed in config |
| Relief filters (trails 100 m, access 100 m, closures 150 m) | as is | CT and the Atlanta corridor have under 100 m relief: drop to ~40 m or skip the filter there | Per area |
| Remoteness scale | 0 → 120 min | Same to start; East has roads everywhere, so revisit after the first run | |
| Gradient band, burn, trout ×1.2 / ×0.5 | | unchanged | |

Following the memory rule: a stream only loses score where it's near-certainly not trout water. The heat gate and
water term keep that rule in every area.

## Order of work
1. **Refactor, no behaviour change**: add the area level, move LA to `AREA=la`, replace constants with config. Check
   that LA's rebuilt `stream_reaches_ranked.csv` matches today's exactly.
2. **Pilot one area end to end** (suggest `ne_ct`: smallest box, 1–2 ranges, fastest run) with national sources
   only: DEM, NHD, hydrology, drops, drainages, trails, access, hike, sun, PRISM, canopy, USGS gauges, iNat,
   PAD-US.
3. **National flow model** (NWM retrospective) → water term for non-LA areas. Validate against that area's USGS
   gauges with `data/validate_flow.py`, as was done for LA.
4. **State trout adapters**, then heat-gate calibration per area.
5. Run `jackson`, `n_georgia`, `central_vt`, `lexington_va`.
6. Road closures and long trails per area (phase 2).

Rough compute: Jackson ≈ 5,000 km², North Georgia ≈ 9,000 km² (mountains + tailwater corridor), central VT
≈ 5,000 km², NE CT ≈ 3,000 km², Lexington ≈ 3,700 km². Together a bit more than LA's 16,000 km².

## Status
- 2026-11-18 15:20: the refactor is in (see `MULTI_AREA_LOG.md`). Earlier note, kept for the record: the refactor was written
  but **parked**. The "Full project audit" session is re-running the whole LA pipeline (`rerun.sh`, log
  `data/fix_run.log`), and every step imports `config.py` fresh, so the refactor and the data move go in only after
  that run ends. Parked copies of the 13 changed scripts: `data/refactor_parked/` (made against the 14:59 scripts; re-apply onto whatever the audit leaves, don't copy over). The originals are
  backed up in `data/backup_20261118-1459/`.
