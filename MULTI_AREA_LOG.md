# Multi-area work log

Decisions and actions for extending the map from LA to more study areas, newest last. The plan is in
`MULTI_AREA_PLAN.md`; this file records what was decided, why, and what was done.

## 2026-11-18

**14:33 — Scope.** The user asked to extend the map to Jackson/Hoback WY, Atlanta/North Georgia, central Vermont and
northeastern Connecticut. Lexington, VA was added at ~14:55. Each becomes an *area* (its own map, UTM zone, home
point, ranges and data sources) beside LA.

**~14:50 — User decisions.**
- Home points for drive times, by ZIP: 83001 Jackson, 30305 Atlanta (Buckhead), 05753 Middlebury VT, 06281 Woodstock
  CT, 24450 Lexington VA. Rural ZIPs span whole valleys, so the town centre is used.
- Middlebury is west of the Green Mountains, so the Vermont boxes were extended west to 73.25° W (Middlebury River,
  Ripton / Breadloaf, New Haven River, Bristol).
- Pilot area: NE Connecticut (smallest, fastest to shake out the refactor).
- LA's data and outputs move under `la/` so every area has the same layout.
- Thermal score: first decided "PRISM August air everywhere"; revised at 15:2x (below).

**14:59 — Backup.** `scripts/`, `stream_reaches_ranked.csv` and `waterfall_candidates.csv` copied to
`data/backup_20261118-1459/`.

**15:05–15:12 — Refactor written, then parked.** The area level, area-aware paths and the CRS taken from config were
written into 13 scripts. Then it turned out the "Full project audit" session was re-running the whole LA pipeline
(`rerun.sh`, log `data/fix_run.log`), and each step imports `config.py` fresh. All 13 files were restored
byte-for-byte from the backup before its next step started (the step running then had started at 14:44 and was
unaffected). The parked versions are in `data/refactor_parked/`.

**~15:20 — Thermal test on LA (read-only, from the 14:59 ranked table).** I rebuilt every reach's score from its
components (97.7% exact, the rest off by 1 point from rounding), then swapped the 700–2300 m elevation band for an
August-air band (full credit at or below 24.5 °C, zero at 27 °C; no penalty for cold):
- 60% of reaches unchanged, 89% within ±3 points, 535 (3%) move by 10 or more. Spearman 0.984; top 200 93% the same.
- Gainers: coastal / lowland rivers under the marine layer (Santa Clara, Ventura, Malibu, Arroyo Sequit, Santa Paula),
  but also concrete flood channels (LA River, Tujunga Wash, Pacoima Diversion Channel, +10 to +12).
- Losers: warm inland mid-elevation creeks (Mojave River, Big Rock Wash, Palm Canyon side creeks, Cajon Wash).
- Against 62 sites with measured July–August water temperature (Water Quality Portal, `data/validate_heat.py`'s
  cache), leave-one-out RMSE: elevation 4.09 °C, air 4.04 °C, air + elevation 3.89 °C. Each misses at low elevation in
  opposite ways: the Santa Clara River near Piru measured 26.5 °C (air gives full credit); Santa Paula Creek measured
  18.9 °C at 180 m (elevation gives zero).

**~15:30 — Decision (user: "do what you think is best"): thermal = estimated summer *water* temperature, per area.**
Why: a trout's limit is a water temperature and carries across areas; an air cutoff doesn't, because the gap between
air and water depends on the climate (spring-fed eastern creeks run far below their air, LA's lowland rivers above
it). Each area uses the best estimate that passes the same leave-one-out test against measured creeks:
- Jackson: NorWeST (2,781 modelled segments in the box), checked against 97 Water Quality Portal sites and 13 USGS
  logger gauges.
- Central VT, NE CT, Lexington: EcoSHEDS northeast model (Maine–Virginia, streams under 200 km²). Larger rivers and
  any area where it fails the test fall back to the local fit. EcoSHEDS was calibrated on many of the same sites, so
  test it on sites it didn't use.
- North Georgia (no regional model) and LA: a local fit of water temperature on PRISM August air + elevation (best
  in LA at 3.89 °C), on 448 sites and 47 gauges in North Georgia.
- Cutoffs are set in water °C from each area's trout records. The rule stays: only penalise where the water is
  near-certainly too warm.
- Check in the pilot: score NE CT both ways (water estimate vs air band) and keep the water estimate only if it
  matches measured temperatures and trout records better.
- Separate known flaw, both ways: concrete flood channels (LA River, Pacoima Diversion Channel) score 33–49. To fix
  by NHD channel type, logged as its own item.

**Data available (Water Quality Portal stream sites with July–August readings since 2000, draft boxes; USGS
water-temperature series):**

| Area | WQP sites (3+ readings) | USGS temp gauges (3+ yrs) | Model |
|---|---|---|---|
| LA | 62 usable | 15 | none good |
| Jackson | 97 (34) | 13 | NorWeST |
| North Georgia | 448 (282) | 47 | none |
| Central VT | 239 (72) | 1 | EcoSHEDS |
| NE CT | 68 (50) | 5 | EcoSHEDS |
| Lexington | 183 (101) | 2 | EcoSHEDS |

**15:15 — The audit session's re-run stopped** (Overpass failed on `san_bernardino 02_download_vectors.py`). Not
caused by the refactor: that step had loaded its code at 14:44. I asked the audit session to hold its restart so the
refactor and data move can go in first; its restart then doubles as the full LA rebuild under the new layout.

**15:16–15:20 — Refactor in.** The audit session confirmed it hadn't restarted and would hold. Its run had stopped
half-way on purpose: san_gabriel and santa_monica have new raw files and new `streams_scored` / `waterfall_candidates`
with older hike/sun/context/flow/area tables; san_bernardino has new NHD files only. That state was moved as is, not
repaired.
- `scripts/config.py`: the parked version (6 areas, `AREA` env var default `la`, `EPSG` / `CRS` / `HOME` / ranges
  from the area, `raw_dir()` / `derived_dir()` / `out_dir()`, `NATIONAL`, `SHARED_DERIVED`).
- Edits re-applied on top of the audit session's current scripts, not copied over them. Each replacement had to
  match exactly once: `01_download_dem`, `02_download_vectors`, `02d_trails`, `06_map`, `07_road_closures`,
  `09_drive`, `11_context`, `12_profiles`, `crossbox`, `flowlib`, `geomatch`, `labelpaths`, plus
  `data/validate_flow.py` and `data/validate_heat.py`. No `26911` or hard-coded `data/raw|derived/{range}` path is
  left outside `config.py`; all scripts compile.
- Data moved (`mv`, so file times kept): `data/raw/<range>` → `data/raw/la/<range>`; NHD HU4 files and PRISM →
  `data/raw/_national/`; the rest of `data/raw/_shared` → `data/raw/la/_shared`; `data/derived/*` →
  `data/derived/la/`; everything in `output/` → `output/la/` (incl. the hand-made `profiles.html`).
- `data/derived/la/_shared/inflows.json` stores absolute paths in its cache key; they were rewritten to the new
  places, and the key still matches, so the cross-box inflow table isn't rebuilt needlessly.
- Checks: every input of all 8 ranges resolves under `AREA=la`; `REGION=sierra_pelona 10_sun.py` (no network)
  rewrote `sun_streams.csv` and `sun_drops.csv` byte-identical to before.
- README: new "Study areas and folders" section; paths updated. Memory notes updated.
- Not changed: `.claude/launch.json` still serves `output/` on 8766, so the LA map is now at `/la/stream_map.html`;
  `phone/` copies untouched.
- The thermal change isn't in yet. It comes after the audit's LA rebuild, so its effect can be checked on its own.

**15:22 — Audit session restarted its LA rebuild under the new layout** (`rerun2.sh`, log `data/fix_run.log`). It
checked first: all scripts compile, config resolves to the `la/` paths, and all 29 of its fixes are still present.
Hands off `scripts/`, `data/` and `output/` until the log ends in `== DONE` or `FAILED` and the audit session reports
its verification and the `phone/` refresh. Then: the thermal (water-temperature) change on LA, and the NE CT pilot
once Overpass is back.

**15:33 — The audit's full LA rebuild finished cleanly under the `la/` layout** (34 steps, 15:21–15:33): the first
end-to-end run of the refactored pipeline. The audit session is doing one more short pass (08_hike × 8, 09_drive,
06_map, 12_profiles; no downloads) and browser checks, so `scripts/`, `data/` and `output/` stay hands-off until it
messages.

**15:40 — Plan for the five new areas (user: "start the water temp change when it's done, what about all of the
other locations?").** Overpass answers again, slowly (36 s for a tiny test query). Once the audit session hands back:
1. LA: the water-temperature thermal change (logged separately when done).
2. In parallel, in the background: check each draft box against HUC-10 divides and the HU4 codes, then run the steps
   that need no area-specific code for all five areas: 01 DEM, 02 NHD + OSM, 03 hydrology, 04 / 04b drops. These are
   the long downloads and computations.
3. Make the California-only sources switch by area, developing on NE CT first: flow model (TNC → NOAA National Water
   Model retrospective), CDFW passage barriers / trout data / Wild Trout Waters → state sources + EBTJV + iNaturalist
   (adding brook trout and cutthroat), CPAD → PAD-US, CAL FIRE history → NIFC, CDEC → none, Caltrans / county
   closures → state 511 feeds or off, PCT → long-distance trails (AT, Long Trail, Benton MacKaye), the LA-only trail
   layers (NPS Santa Monica, State Parks, Eaton) → off, critical-habitat species and tailwaters per area.
4. Then the rest of the pipeline per area (05 onward), NE CT first, then the other four.
