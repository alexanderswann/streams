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

**15:45 — Audit session finished and handed back** (all clean under `la/`; final outputs 15:40). At ~15:55 it made
the folder a git repository at the user's request (two commits; data, outputs and backups are ignored). I commit
nothing unless the user asks. Baseline for the thermal change: `data/backup_20261118-1545/`.

**16:00 — HU4 codes of the new ranges checked against the national WBD; two areas were wrong and are fixed in
`config.py`.** Vermont's Champlain side is `0430` (not `0415`); North Georgia's Tennessee-side creeks are mostly
`0602` (Hiwassee), with `0601` only in the Rabun box; the Atlanta tailwater box also touches `0307` and `0315`.
Uncorrected, those ranges would have come out with streams missing. The box edges themselves were not moved to
watershed divides: like LA's, they are extents, and `crossbox.py` carries creeks across shared edges.

**16:02 — Base steps started for all five new areas, in the background** (`scripts/run_base.sh`: 01 DEM, 02 NHD +
OSM, 03 hydrology, 04 / 04b drops; logs `data/base_<area>.log`). Two chains: ne_ct → central_vt → jackson, and
lexington_va → n_georgia. A failed step is logged and the range goes on. One hydrology step at a time (memory).
First range done 16:05 (lexington_va/maury_goshen: 4,158 stream links, 49 + 17 drops).

**16:03–16:10 — LA thermal change in: estimated water temperature replaces the elevation band.**
- New `scripts/watertemp.py`: fits July–August daytime site medians (Water Quality Portal) on PRISM August air +
  elevation per area; stores `data/raw/<area>/_shared/water_temp_fit.json`.
- LA fit: water = 10.52 + 0.56 × air − 4.17 × elevation (km); 65 sites; leave-one-out RMSE 3.21 °C (air alone 3.45,
  elevation alone 3.30). Three sites over 30 °C left out (Warm Creek ×2, hot springs; Chino Canyon, one August
  afternoon). The estimate is held at the edge of the fitted range (air 17.2–28.7 °C, elevation 142–2,120 m).
- `scoring.py`: thermal = 0.5 × water-temperature credit + 0.35 shade + 0.15 northness. Credit is full at ≤ 20 °C,
  zero at ≥ 25 °C (`WATER_FULL`, `WATER_ZERO`); no penalty for cold; no estimate → 0.5; tailwaters full as before.
  Why 20 / 25: trout feed and grow well to about 20 °C and can't hold out in sustained 25 °C; on LA's 1,566
  trout-evidence reaches it gives the same mean credit as the old band (0.91) and none drop to zero.
- The heat gate (August air ≥ 29 °C, near-certain only) is unchanged.
- `06_map.py`: `water_aug` column in `stream_reaches_ranked.csv`; popups show "summer water about N °C".
  `fish_score_diagram.py` redrawn. README updated.
- Effect on LA, against the 15:45 baseline (17,519 reaches; no other column changed): 72% unchanged, 95% within
  ±3 points, 33 reaches (0.2%) moved 10+, range −10 to +18. Spearman 0.993. Top 50: 47 the same; top 200: 189.
  By range: Santa Monicas +1.7, Santa Anas +0.6, Sespe +0.4, Sierra Pelona −0.6, San Jacinto −0.5, others within
  ±0.1. Gain most: Arroyo Sequit +9.6, Santa Clara and Ventura rivers +8, upper South Fork Santa Ana +6.5 (it was
  above the old band's 2,300 m top). Lose most: Jenson Creek −4.8, Mojave River −3.8, Cajon Wash −3.5.
  Trout-evidence reaches: mean +0.08, worst −6.
- Still open: concrete flood channels gained a little (Pacoima Diversion Channel +5, Tujunga Wash +4.4); they
  need their own fix by NHD channel type. The 05_score.py first-pass score still uses the 700–2300 m band (it only
  feeds the per-range `streams_scored.gpkg`); it becomes area-aware with the other California-only pieces.

**16:10–16:20 — California-only sources made to switch by area** (user: "work on it simultaneously": the new areas
run in the background while the code is generalised in the foreground).
- `config.py`: each area lists its own `sources` (`cdfw_pad`, `tnc_flows`, `cdfw_trout`, `cal_fire`, `cpad`, `cdec`,
  `ca_closures`, `pct`, `la_trail_layers`; all nine for `la`, none yet for the others); `has("name")` in the
  scripts. Also per area: `elev_band` (first-pass score, LA only), `artificial_path` (NHD river centrelines count
  as perennial outside LA: in wet country they are the rivers; in LA they cross dry washes and reservoirs),
  `min_relief` (trail / road terrain filter: 100 m default, 30 m for NE CT, whose hills are 100–250 m).
- `01_download_dem.py`: retries (a 502 from the 3DEP server had left ne_ct/quinebaug without a DEM; rerun OK).
- `05_score.py`: CDFW barriers only where `cdfw_pad`; first-pass elevation band only where set.
- **Flow outside California** (`02b_download_flow.py`): the TNC model covers California only. Elsewhere the same
  `natural_flows.csv` is built from NHDPlus V2's EROM monthly mean flow (gauge-adjusted long-term mean, on every
  flowline in the country) × a yearly index from the area's own USGS gauges (median over gauges of the month's
  mean ÷ the gauge's long-term mean for that month; 3+ gauges). `05b_flow.py` runs unchanged on it.
  Why not NOAA's National Water Model, which the plan named: its archive needs xarray / zarr / s3fs (not
  installed) and several GB of downloads per area, and its low-flow skill in small headwaters is weak anyway. The
  gauge index measures the real dry years. Known weakness: one index per area, so small headwaters that dry faster
  than the gauged creeks are over-rated in droughts. To check with `data/validate_flow.py` per area.
  Lexington: index from 10 gauges, driest summers 2023 (0.22) and 2026 (0.19); 90% of reaches "year-round".
- `flowlib.py` / `scoring.py`: `DIVERSIONS` and `TAILWATERS` are per area (LA's lists; empty elsewhere for now).
  To add: Buford Dam → Chattahoochee, Blue Ridge Dam → Toccoa, Jackson Lake Dam → Snake.
- `02d_trails.py`, `02e_access.py`: the State Parks, NPS Santa Monica and Eaton Fire layers load only in LA. New
  no-bike rules: the Appalachian Trail, Vermont's Long Trail, and (outside LA) National Park Service trails
  (closed to bikes unless a park designates them: Grand Teton, Blue Ridge Parkway, Chattahoochee River NRA).
- `11_context.py`: fire history from NIFC's interagency perimeter history outside California (CAL FIRE in LA);
  land access from PAD-US (restricted / closed holdings; most eastern holdings are "unknown" there and aren't
  flagged) instead of CPAD; critical habitat keeps any fish, mussel or stream amphibian outside LA; CDFW surveys,
  stocking, Wild Trout Waters and CDEC only in LA; iNaturalist adds brook trout and cutthroat outside LA.
  **Not wired in yet:** each state's own trout data (GA designated trout streams, VA / VT / CT / WY surveys and
  stocking, EBTJV brook trout patches). Until then trout evidence in the new areas is iNaturalist only.
- `06_map.py`, `map_drainages.js`, `map3d.html`: layer names and credits follow the area's sources.
- Not done yet for new areas: road closures (07; California feeds only, so they run without), the long-distance
  trail layer (the PCT layer is LA's; the AT and Long Trail still show in the trails layer by name), NorWeST /
  EcoSHEDS as water-temperature predictors (the air + elevation fit is used first), "Minor front-range drainages"
  wording.
- New drivers: `scripts/run_base.sh` (01–04b), `run_mid.sh` (05, 02b, 05c, 05b, 02d, 02e), `run_late.sh` (08, 10,
  09, 11, watertemp, 06, 12). Logs: `data/base_<area>.log`, `mid_<area>.log`, `late_<area>.log`.
- Progress at 16:17: base steps done for lexington_va and ne_ct; central_vt on its third range; n_georgia on its
  first; jackson queued behind central_vt. Middle steps running for ne_ct, then lexington_va.

**16:21 — LA confirmed unchanged by the area switches.** `11_context.py`, `06_map.py` and `12_profiles.py` re-run for
LA after all of the edits above: every value in `stream_reaches_ranked.csv` (17,519 reaches, all columns) and in the
Sierra Pelona and San Gabriel `context_streams.csv` matches the copies saved just before.

**16:22 — Overpass waits fixed.** NE CT's second range sat 7 minutes in `05_score.py`: the backup Overpass mirror
(kumi) doesn't answer at all and each try waited up to 15 minutes for it. All Overpass calls now give a server 20 s to
connect, and the shared helper retries for about 25 minutes (several ranges share the public server's two slots).

**16:25–16:35 — State trout data wired in** (`scripts/troutdata.py`; sources found and checked against the live
services by a background research agent, then field values checked again here). Same two shapes as CDFW's: evidence
points (surveys, stocking) and trout-water polygons (×1.2 in the trout term, like a CDFW Wild Trout Water).
- `ct_trout` (CT DEEP): fish community samples since 2000 (wild / stocked told apart; per station the latest sample
  and the latest with trout), stocked streams and lakes (stocked in the last 12 months), Wild Trout / Trout
  Management Areas and trophy trout streams. NE CT: 725 survey records (416 with trout, 309 without), 70 stocking
  records.
- `vt_trout` (VT Fish & Wildlife): brook trout waters catchments (wild brook trout / mixed wild trout; sampled
  1954–2013), the 2021 stocking list. Vermont publishes no survey layer with species per site.
- `va_trout` (VA DWR): cold water stream survey wild trout streams, classes I–IV; stocked trout reaches and lakes.
- `ga_trout` (GA DNR): designated trout streams, recently stocked streams, this year's standardized trout samples.
- `wy_trout` (WGFD): fishing-guide streams with trout (ribbon class and game fish present), native cutthroat waters.
- `tu_brook_trout`: Trout Unlimited's current brook trout portfolio (the EBTJV patches), CT to GA. Used instead of
  the EBTJV 2016 copy, which now sits on a third-party host with no stated terms.
- Decisions, following "only penalise when near-certain": a "no trout" record comes only from a CT electrofishing
  sample that lists two or more other species and no trout (seine, gill-net and crayfish samples don't count).
  Wyoming's "Clear (no trout present)" class is a classification, not a dated survey, so it lowers nothing; those
  streams just don't get the trout bonus. Nothing else in these sources lowers a score.
- Names like "Mill Pond Brook" are brooks, not lakes; Virginia's county suffixes ("South River (Rockbridge)") are
  dropped before matching names.
- Not used: Vermont's stocking schedule page and Virginia's daily stocking table (HTML, no geometry); Wyoming's
  stocking report (form, not scriptable); CT cold-water habitat sites (undocumented codes).

**16:34–16:46 — NE Connecticut pilot built end to end; four fixes it turned up.**
- *No national forest* (`11_context.py`): the ownership and wilderness layers can be empty. *No fires*
  (`06_map.py`): empty context layers are skipped instead of drawn.
- *A bug of mine from the refactor, caught here:* the "national" PRISM file was really a clip to the study area, so
  Connecticut's context step re-clipped it and LA lost its air temperatures for any later run. LA's saved outputs
  were not affected (they hold their own air values). Now: the clip is per area
  (`data/raw/<area>/_shared/prism_tmean_aug.tif`, made by `watertemp.air_tif()`), and the 58 MB national file is
  kept in `data/raw/_national/` for the other areas. LA's clip was rebuilt.
- *No-trout samples* (`11_context.py`): with 5 km of reach, CT's no-trout samples flagged about 1,200 reaches,
  including creeks with trout upstream. Outside California a no-trout sample now speaks for the same creek within
  1.5 km of its site only (CDFW's keep 5 km, so LA is unchanged).
- *Water-temperature fit* (`watertemp.py`): air + elevation has no skill in NE CT (air spans 2 °C, elevation
  250 m; the first fit even had the wrong sign). The fit now picks, per area, the best of a few predictor sets by
  leave-one-out error (August air, elevation, log drainage area), only among sets whose coefficients have the
  physical sign; drops sites far off a first fit (3 robust SDs); and is not used at all unless it beats "every
  creek is the average" by 10%.
  - NE CT: water = 15.9 + 2.76 × log10(drainage km²); 60 sites; leave-one-out RMSE 1.66 °C (spread 2.64). A 1 km²
    brook ≈ 16 °C, 10 km² ≈ 19 °C, the Quinebaug ≈ 24 °C. Left out: Moosup and Little rivers (logger records
    reading 9–10 °C in midsummer).
  - Lexington: 21.3 − 7.1 × elevation (km) + 1.6 × log10(drainage km²); 171 sites; RMSE 1.89 °C (spread 2.79).
  - LA: unchanged in form (10.62 + 0.55 × air − 4.23 × elevation km); one more outlier out (Cuyama River, 29 °C);
    64 sites; RMSE 2.98 °C. LA fish scores moved by at most 1 point on 1,181 reaches; against the old elevation
    band the summary is the same as logged at 16:10 (95% within ±3; 34 moved 10+).
  - EcoSHEDS / NorWeST were not needed for these three; still an option where the fit has no skill.
- **Result, NE CT** (`output/ne_ct/`): 3,089 reaches, 371 creek profiles, 7,063 trail pieces, 4,683 access roads,
  751 parking / trailheads, 25 live gauges, 213 restricted-access holdings. Fish score median 55 (LA's is far
  lower: Connecticut has water everywhere, cool brooks, and trout records on two thirds of reaches). Top named
  creeks: Bartlett Brook, Mashamoquet Brook, Yantic, Mount Hope, Willimantic and Hop rivers, Merrick Brook (the
  Class 1 wild trout area), Blackwell and Pease brooks, the Natchaug, Fenton and Moosup. 116 reaches carry a
  no-trout sample (×0.5). Only 45 drops, none waterfall-like: the terrain is gentle.
  Checked in the browser: map loads with no console errors, title "Northeastern Connecticut streams", Air Line
  Trail open to bikes, state-park trails closed to bikes, popups show drive time from Woodstock, summer flow,
  estimated water temperature and the trout records.
- Things to look at in the pilot: the trout bonus covers 66% of reaches (the brook trout patches are broad), so it
  separates creeks less than in LA; remoteness barely matters (median approach 6 minutes); scores are not
  comparable between areas.
- 16:44: the public Overpass server is slow again (32 s for a trivial query); Vermont, Jackson and Lexington are
  each waiting in a download step and will get through on retries.

**16:59 — Lexington, Virginia built** (`output/lexington_va/`): 4,104 reaches, 326 creek profiles, 248 drops (10
at mapped waterfalls, 4 unmapped waterfall-like steps, 69 cascades), 6 wilderness areas, 6 fires since 2016 (NIFC),
10 live gauges, 51 stocked waters, 57 iNaturalist trout sightings. Fish score median 57. Top named creeks: Sinking
Creek, Rocky Creek, Pads Creek, Belle Cove Branch, North Fork Piney River, the St. Mary's River (84 on average, a
53-minute approach in its wilderness), Mills Creek, Irish Creek, the Tye forks. The Maury River averages 55 (big,
roadside). Checked in the browser: no console errors; St. Mary's Wilderness trails closed to bikes; popups show
Virginia's stocking and brook trout records.
- Fix: PAD-US files federal wilderness, national forest and park units as "restricted access", which put a ⚠ on
  every wilderness reach. Those are rules on use, not on entry, so they are no longer flagged (`11_context.py`);
  Lexington's context and map are being rebuilt with it.
- Known limit, as in LA: a river that enters from outside every box has only its in-box drainage (the Maury shows
  373 km² at most; its Calfpasture headwaters are north of the box). Its size term and flow match are low for it.
- 17:00: Vermont on drive times; Jackson on trails; North Georgia still queued at the OSM server in scoring.

**17:02 — Central Vermont built** (`output/central_vt/`): 6,238 reaches, 357 creek profiles, 565 drops (14 at mapped
waterfalls, 3 unmapped waterfall-like steps, 189 cascades, 46 short falls on big creeks), 3 wilderness areas
(Breadloaf, Bristol Cliffs, Joseph Battell), 17 live gauges, 19 waters on the 2021 stocking list, 123 iNaturalist
trout sightings. Water temperature: −13.8 + 1.59 × August air + 0.99 × log10(drainage km²); 242 sites; RMSE 2.36 °C
(spread 3.11). Fish score median 62. Top named creeks: West Branch White River, East Granville Brook (a 2.5-hour
approach), Tweed River, the Middlebury River (84; 10 minutes from the home point) and its branches, Lee River,
Shepard Brook, Huntington River. Checked in the browser: no console errors; the Long Trail is "foot travel only".
Same edge limit as the Maury: Otter Creek and the Winooski enter from outside the boxes, so their size is low.

**17:02–18:51 — The Mac slept** and two downloads never recovered: Jackson's `02e_access.py` and North Georgia's
`05_score.py` (blue_ridge) sat for two hours on dead connections. Both killed at 18:53 and resumed from the step
they were on, now under `caffeinate -i` so the machine stays awake while they run. The user gave full permission
at about 18:50 to build all maps and asked to be contacted when they are done.

**19:27 — Jackson Hole & Hoback built** (`output/jackson/`): 6,217 reaches, 308 creek profiles, 1,889 drops (15 at
mapped waterfalls, 50 unmapped waterfall-like steps, 427 cascades, 35 short falls on big creeks), Gros Ventre and
Jedediah Smith wilderness (1,104 reaches), 7 fires since 2016 (Cliff Creek 2016, Roosevelt 2018; 136 reaches carry a
burn penalty), 14 live gauges, 122 iNaturalist trout sightings, Wyoming trout-stream classes on 3,849 reaches.
Water temperature: 20.3 − 5.36 × elevation (km) + 1.83 × log10(drainage km²); 86 sites; RMSE 3.04 °C (spread 3.7);
estimates run 6–14 °C, so nearly every reach gets full thermal credit. Left out: Granite Hot Springs' outflow
(34.5 °C) and two Ditch Creek records.
- Fish score median 70, and many reaches reach the cap of 100: cold water, year-round flow, trout records and long
  wilderness approaches all at once. The score separates creeks less here than anywhere else; within the area the
  order still makes sense (Granite Creek 93, Cache Creek 93, Cliff Creek 90, Hoback River 78, Snake River 73).
- Fix: a drainage outline became self-crossing when simplified for the map (`06_map.py`); outlines are repaired
  after simplifying. Jackson's map was finished by hand after that step failed.
- Small flaw: at a confluence a reach's trout-water label can carry the neighbouring river's name ("...: Hoback
  River" on lower Granite Creek); the class and fish are right.
- Checked in the browser: no console errors; wilderness and national-park trails closed to bikes; popups show
  drive time from Jackson, summer flow, water temperature and the WGFD class.

**18:56 — North Georgia's cold-release dams added** (`scoring.TAILWATERS`): the Chattahoochee below Buford Dam (Lake
Sidney Lanier) through Bull Sluice Lake to Atlanta, and the Toccoa below Blue Ridge Dam. Jackson Lake Dam is just
north of the Jackson boxes and the Snake below it is cold anyway, so none is listed there.

**19:50 — Overpass mirror switched.** North Georgia sat 20 minutes on one small bike-path query: the main Overpass
server is degraded (33 s for a trivial query) and the kumi mirror is dead. `overpass.openstreetmap.fr` answers in
5 s, so every Overpass call now tries it first and the main server second, and waits only as long as the query's
own time limit plus a minute. North Georgia's access-road step was restarted on it (its finished downloads are
cached).

**20:10 — North Georgia built** (`output/n_georgia/`): 14,230 reaches in four ranges, 1,282 creek profiles, 1,028
drops (117 at mapped waterfalls, 20 unmapped waterfall-like steps, 359 cascades, 104 short falls on big creeks), 11
wilderness areas, 68 live gauges, 43 recently stocked waters, 16 state trout samples, 225 iNaturalist sightings,
Georgia's designated trout streams. Water temperature: 26.4 − 11.45 × elevation (km); 409 sites; RMSE 1.7 °C
(spread 2.37). The fit left out the Chattahoochee tailwater sites as outliers (12–16 °C in midsummer below Buford
Dam): right, since the tailwater rule covers them. Fish score median 56; by range: Toccoa / Blue Ridge 63, Rabun 58,
Cohutta 54, the Atlanta corridor 43. Top named creeks: South Fork Moccasin Creek, Jacks River (94), Overflow Creek,
Corbin Creek, West Fork Chattooga, Noontootla Creek (88), Cooper Creek (85), Chattooga River (82), Dukes Creek (82).
- Three failures on the way, all in `11_context.py`'s download of Forest Service ownership: the layer answers with
  ten whole-forest parcel maps (16 MB for five) and the server fails on a full page. `esri()` now cuts the page to a
  quarter after two failures, down to one feature.
- Tailwaters: the rule's size test used the box's own drainage, which starts again below a dam (the Toccoa below
  Blue Ridge Dam showed 3–7 km² of its 490). It now uses the full drainage (`scoring.tailwater`). LA: the same 72
  reaches as before. North Georgia: 92 tailwater reaches (Chattahoochee 78 from Buford Dam to Atlanta, Toccoa 14 to
  the Tennessee line), mean score 79.5.
- Edge limit again: Lake Lanier's basin is outside the boxes, so the Chattahoochee below the dam shows a small
  drainage and has no flow-model match there (it falls back to "NHD perennial").
- Checked in the browser: no console errors; home pin in Buckhead; 135 Appalachian Trail pieces closed to bikes;
  the tailwater popup names the dam and Georgia's special-regulation designation.

**20:15 — All six areas built from the same code.** LA was rebuilt last (`06_map.py`, `12_profiles.py`): every
value in its ranked table matches the copy from before. 3D maps and the profile viewer were also opened for new
areas (Central Vermont 3D, Jackson profiles): no errors.

| Area | Ranges | Reaches | Median score | ≥ 60 | Drops | At mapped falls | Unmapped waterfall-like | Trout bonus | No-trout | Median water °C |
|---|---|---|---|---|---|---|---|---|---|---|
| `la` | 8 | 17,519 | 6 | 2,272 | 5,083 | 217 | 115 | 9% | 51 | 20.8 |
| `ne_ct` | 2 | 3,089 | 55 | 1,334 | 45 | 0 | 0 | 66% | 116 | 17.4 |
| `lexington_va` | 2 | 4,104 | 57 | 1,764 | 248 | 10 | 4 | 35% | 0 | 19.6 |
| `central_vt` | 3 | 6,238 | 62 | 3,555 | 565 | 14 | 3 | 69% | 0 | 17.0 |
| `jackson` | 3 | 6,217 | 70 | 4,158 | 1,889 | 15 | 50 | 62% | 0 | 10.1 |
| `n_georgia` | 4 | 14,230 | 56 | 6,056 | 1,028 | 117 | 20 | 51% | 0 | 21.7 |

Open questions and things not built, for a later pass:
- The score was tuned for LA, where most channels are dry. In the wet areas most reaches score over 50 and Jackson
  hits the cap of 100 often; the trout bonus covers half to two thirds of reaches. Scores rank creeks within an
  area; they aren't comparable between areas. A per-area rescale, or a narrower trout bonus (wild-trout
  designations only, not the broad brook trout patches), would separate creeks better.
- Flow outside California is long-term mean flow × one yearly gauge index per area: small headwaters are probably
  over-rated in dry years. `data/validate_flow.py` hasn't been run for the new areas.
- Rivers that enter from outside the boxes have only their in-box drainage (Maury, Otter Creek, Winooski,
  Chattahoochee below Lanier, Snake).
- Not built for the new areas: road closures, a long-distance trail layer (the AT and Long Trail are in the trail
  layer), NorWeST / EcoSHEDS as temperature predictors (the per-area fits had skill everywhere, so not needed yet).
- At a confluence a trout-water label can carry the neighbouring river's name.
- Concrete flood channels in LA still score as streams.
- `phone/` still holds LA only. Nothing is committed to git (the user hasn't asked).

## 2026-11-18, evening: "do everything that needs to be done"

The user asked for every open item to be finished. Baseline before this pass: `data/backup_20261118-2030/`.

**20:20–20:50 — Rivers that enter from outside every box now bring their drainage** (`crossbox.py`, cache version 6).
Where an NHDPlus V2 river (stream or river centreline, 10+ km²) crosses the outer boundary of the boxes flowing in,
its drainage at that point is carried down the creek like an inflow from a neighbouring box. Guards against
counting water twice: less what the box's own routing has at that spot; less what an edge link from a neighbouring
box brings in within 3 km (the Santa Clara at Fillmore weaves along box edges); less an earlier entry of the same
river on the same path (the Santa Ana clips a corner twice); side channels within 1.5 km of an entry already taken
are skipped; and nothing is added unless at least 10 km² and a quarter of the river's drainage is missing. A river
that comes in through a reservoir (the Chattahoochee in Lake Lanier) is handed to the cell below the dam, in the
through-dams totals only, like the lake's own water.
- Found: Lexington 13 (Calfpasture 364 km², Little Calfpasture 96, Cowpasture 573, the James 5,415); Vermont 19
  (Otter Creek 1,104, Lamoille 622, Winooski 293); NE CT 11 (Quinebaug 367, Hop River 167); Jackson 23 (Snake
  2,112, Salt 1,823, Gros Ventre 973, Greys 784, Buffalo Fork 622); North Georgia 31 (Chattahoochee 2,553 through
  Lanier, Tugaloo 2,105, Conasauga 287); LA 32 (Santa Clara into the Sespe box 2,921, the Santa Ana 2,502, San
  Jacinto River 1,799, Whitewater 155).
- `05c_drainages.py` and `05b_flow.py` rerun for every range of every area. This also lets the flow step match
  those rivers to their NHDPlus segment (the Maury had 373 km² against the segment's 1,300 and didn't match).

**20:52 — LA refresh started** (`scripts/run_la_refresh.sh`, log `data/la_refresh.log`): the audit session had left
six LA ranges on the previous day's OpenStreetMap files because Overpass was down. With the working mirror they are
downloaded again (02, then 05), closures refreshed (07), drainages and flow for all eight ranges, trails and access
roads downloaded again (`REFRESH=1`), then 08, 10, 09, 11, 06, 12.

**20:50 — Small fixes.**
- *Built channels* (`scoring.channel_factor`): ×0.2 where the name says aqueduct, canal, channel, diversion, ditch,
  flume... with no natural word in it (creek, river, wash, brook, branch, fork, run) and no trout record. In LA:
  the California, Los Angeles and Colorado River aqueducts and the named flood channels (176 reaches on 30 names;
  the Pacoima Diversion Channel was at 55). "Ditch Creek" in Jackson and "Canal Branch" in Georgia are creeks and
  aren't touched. The Los Angeles River and Tujunga Wash have natural names and stay as they are.
- *Standing within the area* (`06_map.py`): new column `area_rank_pct` (the share of the area's reaches that score
  lower) and "ahead of N% of reaches here" in the stream popups, since scores run high outside LA and aren't
  comparable between areas. The score itself is unchanged.
- *Trout-water label* (`11_context.py`, `troutdata.py`): a reach takes a mapped stream's designation before a
  catchment-wide one, and of those the one covering most of it, so lower Granite Creek no longer reads "Hoback River".
- *Long-distance trail layer* (`config.long_trail`, `02c_pct.py`, `06_map.py`, both map pages): the PCT layer is
  now "the area's long trail": the Appalachian Trail in North Georgia (332 km) and at Lexington (432 km), the Long
  Trail in Vermont (327 km), the PCT in LA as before; none for Jackson or NE Connecticut. `run_mid.sh` downloads it.

**20:56 — Flow checked against gauges in the new areas** (`data/validate_flow_areas.py`; gauges below reservoirs
left out; per gauge-summer since 2011, modelled ÷ observed lowest July–October monthly mean):

| Area | Gauges | Summers | Median modelled ÷ observed | Within ×2 |
|---|---|---|---|---|
| NE Connecticut | 11 | 158 | 0.93 | 82% |
| Lexington | 10 | 160 | 1.07 | 84% |
| Central Vermont | 15 | 212 | 1.12 | 78% |
| Jackson | 12 | 181 | 1.04 | 87% |
| North Georgia | 58 | 840 | 1.01 | 88% |

Weak spot: small mountain brooks. Under 25 km² the model is 3.7× high on Vermont's two gauges (Ranch Brook, West
Branch Little River) and 5.4× on Connecticut's one; Georgia's twelve small gauges are at 1.0. Only one gauge fell
under the 0.1 cfs "flowing" line in any summer (Winsor Brook, RI, twice; the model said flowing). So the
"year-round" calls hold where there are gauges, and the cfs shown for small northern brooks is probably generous.
The yearly index is the median over these same gauges, so this tests EROM's spread, not the index.

**21:08 — LA refresh finished** (`data/la_refresh.log`, 20:52–21:08, no failures): fresh OSM for the six stale
ranges, outside-river areas, closures, trails and access roads downloaded again. Its tables were saved to
`data/backup_20261118-2030/la_ranked_after_refresh.csv` before the next change.

**21:00–21:12 — A routing bug found and fixed in `03_hydrology.py`: flow paths died along every big river.**
How it showed: after the outside-river fix the Maury still had 373 km² and the Snake 2,207. Following the inflows
downstream, the D8 paths simply ended mid-valley: 1,123 pit cells in one Connecticut range, and dead ends holding
5+ km² on the White River (519 km²), the Winooski (464), the Maury (365), the Hoback (1,136), the Snake (652). Each
river's drainage started again from nothing below every one.
- Cause: pysheds' `resolve_flats()` raises each cell of a flat by a small step (default 1e-5 m) to give it a slope.
  3DEP flattens the water surface of every river wide enough to map, in short level steps; across a wide flat the
  steps pile up until the flat stands above the next step down and becomes a pit. LA's dry, narrow channels have no
  such surfaces, so there it only showed at reservoirs (and was read as "pysheds can't route across a lake").
- Tested on ne_ct/natchaug: step 1e-5 → 1,158 cells with no flow direction, 43 dead ends of 5+ km², largest
  accumulation 145 km²; 1e-6 → 125 / 6 / 825; 1e-7 → 12 / 1 / 891; **1e-9 → 0 / 0 / 1,001 km²**. Repeating the
  conditioning (up to 6 passes) didn't fix it; 64-bit input changed nothing (it already was). On jackson/hoback,
  la/piru and n_georgia/hooch_tailwater: no dead ends left, flow direction changed on under 0.1% of cells, 99.9% of
  existing channel cells still channels.
- Fix: `resolve_flats(eps=1e-9, max_iter=10000)`. To keep the design that drainages end at dams (and that
  `crossbox.py` carries a reservoir's area past its dam for the reaches' own areas), flow paths are then ended on
  purpose at each lake's outlet: the cell inside each NHD lake or reservoir of 8+ ha (and each lagoon) with the most
  accumulation (`flowlib.still_water`). Before, lakes ended paths at scattered pits; now at one cell at the outlet.
- ne_ct after the fix: the only dead ends are the 55 lake outlets; the Quinebaug is one river (706 reaches in its
  drainage); the big-creek drop pass finds 14 + 22 short falls where it found 0 + 1, since it now knows which
  creeks are big.
- `05b_flow.py` outside California now matches and scales on the full drainage (with the water from above lakes):
  the flow table there is NHDPlus's gauge-adjusted flow, which has the lakes in it. LA keeps the edge area (the TNC
  model is natural flow).
- Everything derived from the routing is being rebuilt for all six areas (`scripts/run_rebuild_a.sh`: 03, 04, 04b,
  05, then 05c, 05b; logs `data/rebuild_<area>.log`), then `run_late.sh` per area. Reach ids change everywhere.

**21:15 — Road closures for four of the new areas** (`07_road_closures.py`; feeds found and fetched by a background
research agent, then run here). None needs an account or key:
- Jackson: Grand Teton NP road status (8 now: Teton Park Road, Moose-Wilson Road, Jenny Lake Loop, Signal Mountain
  Summit Road, Mormon Row closed; US 89/191/26 delays) and Teton County's emergency closures (none active).
- Vermont: New England Compass work-zone feed (17 in the area, 8 in mountain terrain: Lincoln Gap Road closed for
  the winter; lane closures on VT 108, VT 73, VT 12, US 7, I-89).
- North Georgia: Georgia 511 events (5 in the area, none in mountain terrain today).
- Lexington: Blue Ridge Parkway closures from the park's web table, drawn between its milepost points (2 sections:
  mileposts 61.4–66.3 and 66.3–76.4), and Virginia 511's map files (3 in the area, none in mountain terrain).
- No keyless feed exists for WYDOT's highways (HTML table only; its map data is obfuscated) or for Connecticut
  (CTroads needs a registered key), so those are not included. Virginia's files are undocumented and may move.
- Park roads are kept wherever they are; other closures only in mountain terrain (150 m of relief within 1 km), as
  in LA. `run_late.sh` now fetches closures first, so approach and drive times route around full closures.

**21:27–21:35 — Every area rebuilt on the fixed routing** (`run_rebuild_a.sh` then `run_late.sh`; no failures). The
only places flow paths end are lake and reservoir outlets. Jackson before → after: Snake River 1,455 → 7,081 km²
(typical summer low 2 → 1,262 cfs), Gros Ventre 597 → 1,569 km² (14 → 201 cfs), Greys 327 → 1,141 km², Hoback
1,197 → 1,401 km²; small creeks unchanged (Granite Creek still 93).

**21:36 — User: "for the snake river everything basically flows into the snake, i want smaller watersheds like the
hoback to stand out before flowing into the snake", and "put everything on the same map so i can go from place to
place".**

**21:36–21:47 — Big tributaries are drainages of their own** (`05c_drainages.py`). With the routing fixed the whole
Jackson area was one "Snake River" drainage, everything a shade of one colour. Rule now: a tributary of 100+ km²
that flows straight into a big river is its own drainage, with its own colour and forks, and the big river keeps
what is left. "Big" is the river's whole size: 2,000+ km² where it leaves the map, followed down the NHDPlus
network past the box but only along its own course (it stops where the drainage more than doubles, i.e. where it
joins a bigger river). A tributary that is itself that big sheds its tributaries the same way; smaller ones keep
their forks (the Hoback, 1,450 km², keeps Granite, Willow, Cliff, Dell and Shoal creeks as forks). The main stem at
a confluence is now picked on the full drainage (with water from above dams): on the old count the Chattahoochee
below Buford Dam was the "smaller arm" at its first side creek. A promoted tributary's reaches no longer carry the
basin's exit point, so `06_map.py` doesn't rename them with the river's basin across a box edge.
- Rules tried and dropped: "the river carries 1,500 km² at the confluence" (missed the Mad River, whose confluence
  sits at 1,450–1,580; with 1,000 it split Granite Creek off the Hoback), and following NHDPlus all the way down
  (made the Gros Ventre "7,000 km²" and shed its side creeks).
- Result: Jackson: Hoback, Gros Ventre, Greys, Flat Creek, Fish Creek, Cottonwood Creek, Buffalo Fork, Pacific
  Creek, Spread Creek, Fall Creek beside the Snake. Vermont: Mad River, Dog River, Stevens Branch and Huntington
  River beside the Winooski; Middlebury and New Haven rivers beside Otter Creek. Lexington: the Maury beside the
  James, and Buffalo Creek, South River, Little Calfpasture and Mill Creek beside the Maury (2,000+ at its mouth).
  North Georgia: Peachtree Creek and Big Creek beside the Chattahoochee; Coosawattee and Holly Creek. LA: Piru and
  Castaic creeks, San Francisquito Creek and the South Fork beside the Santa Clara; Temescal Wash beside the Santa
  Ana. NE Connecticut: none (no river that big).

**21:40–21:47 — Outside rivers, three more fixes** (`crossbox.py`, cache version 11), found while checking why
Buffalo Fork and Pacific Creek weren't separated:
- A river segment that starts inside, leaves and comes back counts as entering at its last crossing (the Snake
  weaves across the north edge at Moran).
- At a box edge the routing drains a flat river surface back out through the edge (the edge is the lowest way out
  it can see): the Snake's 2,112 km² came in and left again 1 km on. The water is now handed over further down the
  mapped river, at the first point (50 m steps, up to 6 km) whose path doesn't end back on the border.
- A tributary that joins further down is its own water (the guard against counting a river twice now looks only
  1.5 km down the path, plus a rule for NHDPlus's twin channels: same drainage within 2%, within 3 km, paths
  meeting within 6 km). A river that comes in through a lake is followed down the mapped river to the first cell
  below the dam.

**21:47–21:52 — One map for everything** (`scripts/13_overview.py` → `output/index.html`; "Go to…" menu in both
maps). All six areas in one full-detail page would be 209 MB of 2D map (LA alone 67 MB; 162 MB of 3D data), too
heavy to open, on a phone above all. So:
- The front page is a map of all areas: each area's drainage outlines and main rivers (order 4 and up), drainage
  names from zoom 9, a list of the areas, the home points. A click inside an area gives links to its full map (2D,
  3D, profiles) at that spot; zoomed in, a button opens the full map at the current view. 3.5 MB. Built from an
  `overview.json` that each area's `06_map.py` now writes.
- Every area's 2D and 3D map has a "Go to…" menu in the legend: any other area, or "All areas map" at the
  current view. So one click goes from place to place in either direction.
- Fixed while testing in the browser: the view has to be set before the layers are added (removing a label while
  the map was still starting up broke its start); a location in the address is followed when the page is already
  open; the area list folds away (and starts folded on a phone).
- `scripts/phone_sync.sh` lays `phone/` out like `output/` (index + one folder per area), so the links work there
  too; LA's old top-level file names forward to `phone/la/`.

**21:55 — A side effect of the routing fix caught in the LA comparison, and fixed.** After the first rebuild LA
was close to before (98% of reaches at the same spot, 94% of those with the same score), but the Arroyo Seco had
dropped 9 points, Pacoima Wash 7 and Temescal Wash 17, all through the water term. Cause: I had ended flow paths
at every NHD lake or basin of 8+ ha. That includes dry flood-control and debris basins (Devil's Gate on the Arroyo
Seco) and reservoirs that were drawn down when the DEM was flown, which the old routing ran straight through, so
the creek below lost its drainage in the flow step. Now a waterbody ends flow paths only if it holds level water
in the DEM: 2+ ha of its outline at one elevation. The split is clean in LA: Morris 41 ha, Big Tujunga 6, Little
Rock 27, Pyramid 441, Castaic 504, Big Bear 792 against San Gabriel Reservoir 0.5, Cogswell 0.1, the debris
basins under 0.2. That is the same set the old routing stopped at (per the README's list of dam links). All six
areas are being rebuilt again from `03_hydrology.py`.
- Also: the basin above Pyramid Lake had taken the name "Gorman Creek"; `NAME_FIX` returns it to "Piru Creek".

**22:17 — Final state: all six areas rebuilt from `03_hydrology.py` on the same code, no failures.**

| Area | Reaches | Drainages | Median score | ≥ 60 | Drops | At mapped falls | Waterfall-like | Short falls, big creeks | No flow data | Closures now | Water-temperature fit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `la` | 17,681 | 61 | 6 | 2,329 | 5,068 | 217 | 113 | 77 | 8% | 31 | air + elevation, 3.0 °C |
| `ne_ct` | 3,351 | 13 | 58 | 1,598 | 49 | 0 | 0 | 4 | 5% | no feed | stream size, 1.7 °C |
| `lexington_va` | 4,201 | 15 | 57 | 1,863 | 248 | 10 | 4 | 14 | 2% | 2 | elevation + size, 1.9 °C |
| `central_vt` | 6,497 | 24 | 64 | 3,909 | 569 | 14 | 3 | 44 | 5% | 8 | air + size, 2.4 °C |
| `jackson` | 6,257 | 27 | 72 | 4,397 | 1,878 | 15 | 48 | 35 | 4% | 8 | elevation + size, 3.0 °C |
| `n_georgia` | 14,897 | 51 | 58 | 6,798 | 1,023 | 116 | 20 | 109 | 1% | 0 today | elevation, 1.7 °C |

- Rivers now carry their real size: Snake 10,034 km² (typical summer low 1,781 cfs), Gros Ventre 1,607, Hoback
  1,452; Chattahoochee 3,848 (1,147 cfs), Toccoa 901; Winooski 2,460, Otter Creek 1,949, White River 1,593; Maury
  1,988; Quinebaug 1,689. Reaches with no flow estimate fell to 1–8% (they were 9–21% in the new areas).
- **LA against the start of this evening's pass** (`data/backup_20261118-2030/`): 17,519 → 17,681 reaches; 98% at
  the same spot, of which 94% have the same score and 96% are within ±3; Spearman 0.974; median score unchanged
  (6); reaches at 60+ 2,272 → 2,329. Unchanged: Arroyo Seco 66.7, Sespe Creek 76.9, Deep Creek 87, Piru Creek 76.
  Up: creeks that gained drainage the routing had cut (Rancho Nuevo Creek +41, Agua Blanca +17, Grapevine +18, San
  Gorgonio River +9). Down: the built channels by design (Pacoima Diversion Channel −44, Haines Canyon Channel −11);
  and three lowland channels below lakes that hold water, whose flow no longer counts the water above them
  (Temescal Wash −21 below Lake Elsinore and Lee Lake, Chino Creek −18 below Prado, Pacoima Wash −7 below Pacoima
  Reservoir's pool). Drainage legend: Piru and Castaic creeks, San Francisquito Creek and the South Fork Santa
  Clara are drainages of their own beside the Santa Clara; the rest as before.
- Checked in the browser (2D, 3D and the phone-size layout): the all-areas map; the click and button links into an
  area; "Go to" from LA to Vermont and back to the all-areas map at the same view; LA's old phone bookmark
  forwarding with its location; Jackson in 3D with the Hoback, Gros Ventre and Flat Creek drainages; Vermont's
  Long Trail and road-closure layers. No console errors.
- `phone/` synced (`scripts/phone_sync.sh`): 429 MB, index + six area folders.

Still open:
- Scores rank creeks within an area (popups show the standing: "ahead of N% of reaches here"); they aren't
  comparable between areas, and Jackson still reaches the cap of 100 often.
- Small northern brooks' summer flow is probably generous (3–5× on the three small gauges in VT and CT).
- No closure feed for NE Connecticut or for Wyoming's state highways (Teton Pass) without a registered key.
- The Tugaloo River (enters North Georgia through Lake Hartwell's arm and leaves the box before a dam) is not
  carried in; rivers along a box edge can still be short of drainage for a few km.
- Channels with natural names that are concrete (the LA River, Tujunga Wash) still score as streams.
- The README's validation table for mapped falls (`data/validate.py`) and its counts of reaches and profiles are
  from before this pass; LA's numbers moved slightly (drops 5,083 → 5,068, same 217 at mapped falls).

## 2026-11-18, late: phone, website, defaults

**22:25 — User: "give me the link"; then "i sent the .html to my phone but it would not let me look in depth at the
different locations".** `output/index.html` is only a front page: it opens each area's map from the folders beside
it, so alone on a phone its links lead nowhere. Two answers:
- **A single file with the detail inside** (`scripts/14_portable.py` → `output/stream_maps_all.html`, 23.8 MB, also
  in `phone/`). It opens as the map of all areas; each area's layers sit in the page as gzip (LA 4.4 MB of streams
  and points + 3.8 MB of trails and roads; all six 12.2 + 8.2 MB) and are unpacked when you zoom in there (browser
  `DecompressionStream`, with pako from the CDN for older phones). At most two areas stay unpacked. Every reach has
  the full map's popup. Tested at phone size: Jackson unpacks 6,257 reaches, North Georgia 14,897; no errors.
  Fixed on the way: the overview data and the unpacked network both used `a.streams`.
- On home Wi-Fi the phone can open the Mac's copy directly while the phone preview server runs.

**22:35 — User: "i want to publish this on my alexanderswann.github.io website".** Looked before touching anything:
the site repository is public, branch `master`, a 3.4 MB hand-written site last changed in 2020, no Jekyll
features, live (HTTP 200). This Mac has no GitHub CLI and no saved GitHub login (a dry-run push asks for a user
name), so the push is the user's step. The built pages were scanned for local paths, the user's email and LAN
addresses: none. Asked two things, since this goes on the public web:
- What to post → **"Everything"** (the map of all areas, the six full maps, 3D, profiles; not the single file).
- The start pins and drive times, labelled with ZIP codes → **"Keep the ZIPs"**.
`scripts/publish_site.sh` copies it all into `publish/alexanderswann.github.io/streams/` (418 MB; LA's map 67 MB
and 3D data 53 MB are over GitHub's 50 MB warning size and under its 100 MB limit), adds an empty `.nojekyll` at
the top of the site, and commits in that local copy (commit `595be46`, about 108 MB packed). Not pushed.

**22:40 — User: defaults for all maps = streams, drainages, the long trail, terrain shading and place / road
labels only; no other trails, roads, parking or trailheads.**
- 2D (`map_drainages.js`, `06_map.py`): trails, access roads, trailheads, parking and the Eaton Fire closure
  areas no longer start on; the bike colouring and the trail key come on with the trail layer. Checked: LA and
  Vermont open with exactly Terrain shading, Place & road labels, Streams, Drainage outlines and the long trail
  ticked, and trails still switch on with their key.
- 3D already opened that way.
- Map of all areas (`13_overview.py`): terrain shading and each area's long trail added (from `overview.json`).
- Single file (`14_portable.py`): the same five things; drops and waterfalls, trailheads and parking, trails and
  dirt roads, gauges and road closures, trout records each have a switch, all off.
- All six areas' maps rebuilt; `phone/` and the publish copy refreshed with them.

## 2026-11-19

**Push sign-in.** The push from the terminal failed: GitHub answered "Invalid username or token" (it takes an
access token there, not the account password). GitHub Desktop is installed on this Mac and signs in through
GitHub's own web page, so the publish copy was opened in it for the user to press "Push origin". Still the
user's step.

**User: "there is already something at https://alexanderswann.github.io/ dont interfere with that".** Checked
the pending commit against the site as it is on GitHub: 53 files added under `streams/`, plus the empty
`.nojekyll` at the top; nothing existing changed or removed, and the old site has nothing named `streams`.
The `.nojekyll` was the only thing outside `streams/`, so it was taken out (commit now `e965e59`): the old
site's 32 files have no Jekyll front matter, the map files don't either, and none has a name starting with `_`
or `.`, so GitHub's Jekyll step copies everything as it is without that file. `publish_site.sh` no longer
makes it and now stops if its commit would touch anything outside `streams/`. No link to the maps is added to
the old pages: they are reached only at `/streams/`.

**Published.** The user made a fine-grained token for the one repository (the first try was refused, error 403:
the token had no write access to Contents) and pushed from a terminal. Checked afterwards: GitHub's `master` is
at `e965e59`; nothing outside `streams/` differs from the old site and the home page is byte-for-byte the old
`index.html`; all 53 files under `streams/` are served with the right sizes; in Chrome the live front page shows
all six areas and the live Jackson map opens with Terrain shading, Place & road labels, Streams and Drainage
outlines ticked, the Hoback as its own drainage, the "Go to" menu listing the other areas, no console errors.
Live at https://alexanderswann.github.io/streams/.

**User: "can you now push when you make an update?"** Standing OK to push map updates. The token is saved in
the Mac's keychain (a dry-run push from the pipeline's shell goes through without a prompt), so
`scripts/publish_site.sh push` now commits and pushes in one step; it still refuses if anything outside
`streams/` would change. The token expires: when a push is refused the user makes a new one.

**Mistake while testing the one-step publish, put right.** To try `publish_site.sh push` end to end I ran it for
real, twice, expecting "nothing new". Another session was at that moment redoing the drainages
(`run_drainage_refresh.sh`, with uncommitted changes to `05c_drainages.py`, `crossbox.py`, `06_map.py`), so
`output/` no longer matched the published copy and both runs pushed that session's unfinished, unchecked maps
(commits `d23a486` at 08:13 and `3409314` at 08:14; 19 files each, all inside `streams/`). Each was reverted
and pushed within about two minutes (`2aefe20`, `31cab68`); the live files were then compared with the checked
version `e965e59` by content: identical, and the home page is still the old `index.html`. Nothing outside
`streams/` changed at any point. Cost: the site repository's history grew from about 108 MB to about 250 MB.
- `publish_site.sh` now stops when a pipeline step or a `run_*.sh` driver is running, or when anything in
  `output/` was written in the last 15 minutes.
- Rule for me: never run the publish script with `push` as a test; publish only maps this session built or
  checked, and look at `git status` and running jobs first. The drainage-refresh maps are NOT published: that is
  for whoever finishes and checks that work.
- Every publish of rebuilt maps adds roughly 100 MB to the site repository's history (GitHub recommends staying
  under 1 GB, hard limit far higher), so publish finished batches, not every small change.

**User: a line splits the Lexington map down the middle; "there are other ones too ... find them and fix them".**
(Work of the main session; the fork that handled the publishing logged the two entries above.) The line was the
edge between the area's two boxes. Measured on every area's outlines before touching anything
(`overview.json`): 20 to 65 km2 uncovered within 600 m of the shared edges in each area, 13 to 58 holes inside
single drainages, 1 to 5 km2 of overlap between neighbouring drainages. Four causes, four fixes:
- **Pockets and notches along a shared edge.** Unnamed basins that leave over the edge were kept only from
  0.5 km2, and one that found no mapped stream within 6 km across the edge was dropped. `05c` now keeps every
  one on a shared edge; `06_map.py` places those the streams can't: by the outline the exit lands in across the
  edge (passes for chains), then, under 5 km2, by the named outline it shares the most boundary with. Their
  reaches follow. Basins that drain off the outer boundary of the map stay unnamed, as before.
- **The two halves not joining.** `drainages.gpkg` was written in lat/lon and read back, so the two boxes'
  straight edge no longer matched to the millimetre and the dissolve left the line. Now written in the area's
  own CRS.
- **White holes at ponds** (worst in NE Connecticut: 19 % of its reaches had no drainage). Flow paths end in
  every lake with level water, so a pond's basin too small for a name was left unnamed. It now joins the
  drainage and fork its outflow runs into: by crossbox's dam links (`crossbox.dam_links`, cache VERSION 12, the
  `edge` and `full` area tables checked identical to before), and where NHDPlus has no flowline for the pond,
  by the detailed NHD stream line that leaves the lake (`pond_links` in `05c`; lakes no stream leaves stay
  closed). For the drainage names only: the areas, flows and scores are untouched.
- **Neighbours pulled apart on the map of all areas.** Each drainage was simplified on its own (overlaps and
  slivers along the divides). `06_map.py` now simplifies them together as one coverage (`simplify_together`).

Found along the way and fixed:
- **N Georgia: Hightower Creek's basin stopped on the box edge** for 10 km instead of joining the Hiwassee: Lake
  Chatuge lies across the edge, so each side led into the other and no stream was found in the lake. A named
  basin whose crossing finds no stream now takes the outline across the edge (only into a bigger basin), and of
  two named basins that lead into each other the smaller is the tributary. Hightower Creek is now a fork of the
  Hiwassee River (438 km2); N Georgia has 49 drainages, not 50. A named basin's dam- or pond-ended parts now go
  with it when it is renamed across an edge (before, the outline took the new name and those reaches kept the old).
- **Rivers broken where they cross between boxes** (the Maury from Rockbridge Baths to Lexington, in the user's
  screenshot too). A river coming in from the next box, from outside or over a dam restarted at stream order 1
  in the box's own count: thin on the full maps, missing from the map of all areas (order 4 and up). For
  drawing only, a reach that carries over twice its own box's drainage gets at least the usual order in the area
  for its full drainage (median full area per order, from reaches with no outside water).

Result, all six areas rebuilt (`scripts/run_drainage_refresh.sh`: 05c per range, 06, 12; then 13, 14, phone):

| area | lake basins joined (by detailed lines) | reaches given a drainage | holes inside drainages, km2 before -> after | overlap km2 before -> after |
|---|---|---|---|---|
| la | 18 (7) | 250 | 48.5 -> 2.3 | 5.4 -> 0 |
| jackson | 11 (3) | 97 | 36.7 -> 0 | 3.2 -> 0 |
| n_georgia | 63 (10) | 517 | 84.9 -> 0.5 | 4.9 -> 0 |
| central_vt | 38 (13) | 132 | 18.0 -> 0.01 | 3.2 -> 0 |
| ne_ct | 132 (35) | 460 | 41.3 -> 0.01 | 1.0 -> 0 |
| lexington_va | 7 (1) | 67 | 9.1 -> 0 | 2.1 -> 0 |

Checks: LA, reach by reach against the copy from before: 250 reaches changed drainage, every one unnamed before;
no reach that had a drainage changed it, no fork-only changes. The drainage lists of LA, Jackson, Vermont,
Connecticut and Lexington are the same names and sizes (within 5 %); only N Georgia's changed (above). Fish
scores: nothing 05c writes feeds them. In the browser: the user's Lexington view on the map of all areas (no
line, the Maury unbroken), Lexington's full map (no console errors), Connecticut and LA on the map of all areas.
Copies of the old outlines and tables are in `data/backup_20261119-seams/`.

Still there, known:
- Short stretches (the longest 1.7 km; 0.4 to 4.8 km per area in all) where an outline still follows a box
  edge: both boxes are sure of their own named basin there and the routing runs along the border.
- **Not fixed, affects the scores a little:** below a pond NHDPlus has no flowline for (66 ponds over the six
  areas, 35 of them in NE Connecticut), the brook's drainage area still starts again from nothing, so its size
  and flow are low for a stretch. The detailed-line link could carry the area too; that changes scores, so it
  is left for the user to decide.
- Not pushed to the website by this session: the live site still has the 2026-11-18 maps.

**User: nine more screenshots of box edges in every area; "no stream or river is able to cross any of these
artifacts ... find the root cause and tackle the problem from there, dont just address the symptoms".**
Measured first, on the reaches themselves: 270 reach ends stopped dead on an edge two boxes share (LA 65,
Jackson 57, Vermont 58, N Georgia 45, Lexington 23, NE Connecticut 22; 43 of them rivers of 50 km2 and up), and
at none of 585 crossings did the two boxes' lines meet (median gap 280 to 490 m, up to 2.1 km).

*Root cause.* Each box did its whole hydrology alone (`03_hydrology.py`). The box's rim is then a wall: water
that reaches it runs along the border to a low cell and ends; a river that crosses into the next box arrives
with no drainage, so its line there starts only where 0.25 km2 has gathered again, as an order-1 creek. Two
more layers of the same thing: `05_score.py` drops reaches under 1 km2 of in-box drainage, so a river's first
stretch inside a box was thrown away; and `crossbox.py` had to guess where a creek went on across an edge
(25 m / 10-cell searches), which lost creeks that run along an edge (Hays Creek's 200 km2 never reached the
Maury: 910 km2 at Rockbridge Baths where it is 1,111).

*Tried and dropped the same morning (symptom repairs, not kept):* raising the drawn stream order by drainage
area (kept, but only matters now below dams and outer-boundary entries), drawing each line through along
crossbox's path, and re-solving a 6 km strip along each edge to draw lines through (`seamstrips.py`, deleted).
They closed most gaps on the drawing but left the network and the areas wrong.

*The fix, in the hydrology.*
- `03_hydrology.py` now only conditions the DEM (fill pits, fill depressions, resolve flats), with a 5 km halo
  of the neighbouring boxes' terrain, and saves the box's part (`dem_cond.tif`, float64).
- New `03b_stitch.py` (per area) puts boxes that share an edge side by side and works out, across them: D8
  directions (each box with a one-cell ring of its neighbours' conditioned surface; same rule as pysheds), the
  lake-outlet rule (a lake across an edge now has one outlet), accumulation, streams from 0.25 km2 counted
  across the boxes, stream order (pysheds' rule, reimplemented), and each box's stream lines (with a one-cell
  ring, so a line that leaves a box ends on the first cell of the next, where that box's line begins).
  `area_km2.tif` counts every cell upstream in the joined boxes.
- `crossbox.py` (VERSION 15): crossings between boxes routed together are exact (the cell the box points at);
  a basin that leaves over such an edge hands on only what came into it from outside the map or over a dam,
  because the raster already has the rest. `05c`: basin sizes take the raster's value at the outlet.
- `06_map.py`: the strip repair is gone; lines are still drawn through below dams and at outer-boundary
  entries (`draw_through`), where the routing really does stop. A named drainage under 2 km2 in all joins its
  neighbour (Pacific Creek at Moran). `05c`: a thin basin whose outlet leaves over a shared edge is kept
  whatever its outline's distance from the edge (thin fingers were being dropped, leaving white slivers).
- Names: `("cohutta", "Ocoee River") -> "Toccoa River"`, `("piru", "Cuddy Creek") -> "Grapevine Creek"`.
- Drivers: `run_base.sh` and `run_rebuild_a.sh` run 03 per box, then 03b, then the rest.

*Checks.*
- A box with no neighbour (N Georgia's Chattahoochee tailwater) through the new code: flow directions, areas,
  filled DEM and all 4,474 stream lines identical to the old method; stream order differs only on the
  one-cell rim (46 cells, where pysheds left 0).
- Lexington, new against old: flow direction identical in 100.0000 % of cells further than 6 km from an edge,
  99.98 % overall. No flow loops in any area's joined surface; no path ends within 30 m of a shared edge
  except two cells at the outer corners of the map.
- Reach ends dead on a shared edge: 270 -> 0 (every area 0). Redrawn from the rebuilt data and looked at: all
  nine of the user's views (Georgia's two edges, Vermont's two, Jackson's two, LA's Sespe-Piru, Santa Clara
  and Lytle Creek edges), plus Rockbridge Baths (Hays / Walker Creek now reaches the Maury) and the James at
  the Appalachian Trail footbridge (one line, one width). In the browser: the James view and Rockbridge Baths
  on Lexington's full map (no console errors), Georgia and Jackson on the map of all areas.
- Scores against the build before: reaches in the same spot 93 to 98 % per area; of those, the same score in
  97 to 99 % and within 5 points in 99 to 100 %; every area's median unchanged (LA 6, Jackson 72, N Georgia
  58, Vermont 64, NE Connecticut 58, Lexington 57). 12 to 31 reaches per area moved 15 points or more (rivers
  just inside an edge that now carry their real size). Reaches: LA 17,681 -> 17,887, Jackson 6,257 -> 6,365,
  N Georgia 14,897 -> 15,105, Vermont 6,497 -> 6,681, NE Connecticut 3,351 -> 3,511, Lexington 4,201 -> 4,296
  (the stretches just inside box edges that used to be dropped). Reach ids changed everywhere.
- Drainage lists: LA and Jackson the same; N Georgia: Fightingtown Creek is now a fork of the Toccoa (it joins
  it at McCaysville; the box edge had kept it apart), Cherry Log Creek (37 km2) stands apart from the Ellijay
  (a pond on the edge now ends its paths); Vermont: Muddy Branch into the New Haven, Pekin Brook into
  Kingsbury Branch; Lexington: Buffalo Creek (321 km2) is its own drainage (the Maury's full size is now seen,
  so the 100-into-2,000 km2 rule applies); NE Connecticut: Shetucket, Pachaug and Little River shifted 10-50 %.
- Run times: 5 to 20 minutes an area, no failed steps. The Mac slept 09:54-11:49 with the lid closed, in the
  middle of N Georgia's approach-time step; it carried on by itself afterwards and finished clean.

*Still open.* The 66 small ponds NHDPlus has no flowline for still restart the brook's area below them (as
before). Drops (04) near an outer-boundary entry still see only the in-map area there. Not pushed to the
website: the live site has the 2026-11-18 maps. Backups: `data/backup_20261119-seams/` (scripts and outputs
from before each stage).

**Published (12:09).** The user said "Yes, push", then "push it now". Found first that `publish_site.sh` had
lost its `DEST=$SITE/streams` line (dropped in the fork session's last edit, after its own runs), so as it
stood it would have copied nothing into the site: restored. The script's 15-minute wait after the last map
write was skipped on the user's word with a new second argument (`publish_site.sh push now`; the
running-build test still applies). Commit `4d76f17`, 19 files, all inside `streams/`; nothing outside
`streams/` differs from the original site (`cbbb0b8`). Checked afterwards: all 19 files as served at
https://alexanderswann.github.io/streams/ have the same SHA-256 as the pushed ones, the pushed maps are the
built and checked ones for all six areas, and the home page still serves the old `index.html` byte for byte.
Not opened in a browser on the live address (the same files were looked at locally). The site repository's
history is now 338 MB.

**User (screenshot of Guys Run, Lexington): one reach with fish score 13 between reaches in the 80s; "is this
the results of a larger bug".** Yes, a matching bug, separate from the box edges. Counted first: reaches whose
dry-season flow per km2 is under a quarter of both the reach above and the reach below: 16 (Lexington 10, five of
them on the Maury itself at 0.00 to 0.08 cfs where it carries 90 to 150; NE Connecticut 5; N Georgia 1; none in
Vermont, Jackson or LA). Two causes, both fixed where they arise:
- **Side arms of split channels** (`flowlib.minor_arms`, used by `match_points`). Where a creek splits and
  rejoins, NHDPlus gives both arms the whole drainage (totdasqkm) and nearly all the flow to the main arm: beside
  Guys Run's 18.65 km2 / 13 cfs runs an unnamed arm with 18.51 km2 / 0.14 cfs. The matching (nearest line with
  agreeing drainage) took the side arm when the reach lay 7 m from it. A side arm is now recognised (two lines
  into the same downstream line, drainage within 3 %, under half the other's flow; and the lines above it on
  the same arm) and left out of the matching: Lexington 95 lines (all unnamed, 22 km of 4,002), LA 297, NE
  Connecticut 25, N Georgia 14, Vermont 8, Jackson 7. Flow: qe_ma, or the Natural Flows mean in California.
- **A stale estimate kept below ponds** (`05b_flow.py`). The step makes two estimates (the reach's area without
  and with the water carried past dams) and keeps the first where the second would be lower (the user's rule:
  possible trout water stays in). Below a pond the first area starts again from nothing, so the first estimate
  there is whatever small line matched it: the Pachaug River inside Pachaug Pond (129 km2) stood as "usually
  flows, 0.23 cfs" from a 2.3 km2 brook, where the second estimate says reservoir. The first estimate is now
  dropped when its line has under half the reach's drainage. One with no line at all (NHD's own label) still
  stands, as before (a first version of this dropped those too and rated two James River reaches dry; caught
  on the list of changes and corrected before anything was published).
Result: 0 sudden drop-and-recover reaches in every area. Guys Run's reach: 0.07 cfs "mostly dry", fish 13 ->
3.2 cfs "year-round", fish 83. Score changes against the build before, reach by reach: Lexington 13 up (Maury
5, Cowpasture 3, Guys Run), 0 down; NE Connecticut 8 up, 23 down; N Georgia 1 up, 20 down; Jackson 1 up, 2
down; LA 16 up, 4 down; Vermont none. Every "down" outside LA is a reach lying in a mapped lake or pond that
now reads "reservoir" (Tallulah River in its lakes, the Chattahoochee in Lake Lanier, the French and Pachaug
rivers' ponds, the Gros Ventre in Lower Slide Lake). No river of 200 km2 or more outside LA is rated dry or
seasonal. `run_drainage_refresh.sh` now runs 05b after 05c. All six areas, the map of all areas, the single
file and `phone/` rebuilt. Not pushed, not committed.

**User (screenshot, Jackson): the Snake River is missing from the Hoback confluence down to Alpine; "is this
part of a larger bug? why did this happen?"** My bug, from the morning's `03b_stitch.py`: the drainage area was
written as `acc[sl] * (RES * RES) / 1e6` with `acc` in int32, and cells x 100 m2 wraps past 2,147 km2. The
Snake passes that exactly where the Hoback joins (1,738 + about 1,500 km2 inside the boxes), so `area_km2.tif`
was negative along 3,959 cells (39.6 km) from the confluence to Palisades, and `05_score.py` threw every reach
there away as under 1 km2. Checked every box of every area for negative cells: only Jackson's Hoback box (no
other area has 2,147 km2 of drainage inside its boxes: the next largest are 1,875 in Lexington and 1,677 in
Vermont), so one stretch of one river, but it would have hit any bigger river added later. I missed it on the
morning's check: the test looked at box edges, and on the redrawn Jackson view the Snake ending at the
confluence was there to be seen.
- Fix: the count goes to float64 before it is multiplied, and 03b stops if any area is negative.
- Jackson rebuilt from 03b on (drops, scores, flows, drainages, approach times, maps): no failed steps. The
  Snake in the Hoback box: 89 reaches, 50.1 km, 6,876 to 10,048 km2, to the box's west edge at Alpine;
  year-round. Dead ends on shared edges 0, sudden flow drops 0.
- New standing check (all areas): stream cells of order 3 and up with no reach within 25 m. Jackson 0.1 km,
  Lexington 0.1, N Georgia 0.1, Vermont 0.0, NE Connecticut 0.0; LA 39.7 km, of which 36.0 in the Santa Monica
  box, where the sea's flat cells trace channels that 05_score drops on purpose.
Map of all areas, single file and `phone/` rebuilt. The website (12:09 build) still has the Snake missing and
the Guys Run flow bug: not pushed. Not committed.

**Published (13:34, by another session).** The user said "Yes, push" to the Snake and flow fixes at 13:35; a
second session working in this project (a road-crossing ring on the maps and profiles, and the link-preview
card) had run `publish_site.sh push` a minute earlier, after its own rebuild of the maps, and that push (commit
`5ba0dcf`, 25 files) is the build that holds both fixes. Nothing more was pushed from here. Checked: the 18 map
and data files of the six areas as served have the same SHA-256 as the current build (LA's three caught up a
few minutes after the rest); the front page and `preview.jpg` match what was pushed; the built Jackson data,
identical to the pushed file, has 69 Snake River reaches west of 110.75 W, below the Hoback (8,571 to 10,046 km2, to Alpine) and
the built Lexington data has Guys Run's 18.5 km2 reach at fish 83, year-round; nothing outside `streams/`
differs from the original site and the home page is the old file. A direct download of the live Jackson data
was cut off by a connection reset and not repeated.
Three sessions wrote to this folder today; the project's uncommitted changes are a mix of theirs
(`12_profiles.py`, `13_overview.py`, `15_preview.py`, `map_drainages.js`, `map_style.css`, `publish_site.sh`)
and this session's (`03b_stitch.py`, `05b_flow.py`, `flowlib.py`, `run_drainage_refresh.sh`, this log).
