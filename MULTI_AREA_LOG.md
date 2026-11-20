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

## 2026-11-19, afternoon: drop rules that hid real falls (another session)
The user knows a waterfall on the Middlebury River at 43.97509, -73.06484. The big-creek pass found it (12.1 m
over 68 m, 9.6 m above the creek's trend) and `05_score.py` called it a likely DEM artifact on 2.2 m of fill at
the lip. Checked the artifact rules against all six areas (8,931 drops):
- Fill rule (`04`/`04b`): flagged 61 drops. The fill is about a barrier's height, so it now flags a drop only when
  the drop (or excess) less the fill misses the detector's own bar: 40 stay flagged (fill nearly the whole drop,
  almost all at road culverts), 21 are released, among them this one and three within 26 m of a mapped fall.
- Road rule (`05_score.py`): "a drivable road within 40 m of the top" flagged 741 drops; in 155 the road only runs
  beside the channel (gorges). Now the road has to cross the DEM channel within 40 m of the top, where an embankment
  or bridge deck would make the lip. A first version tested the whole step (top to pool) and newly flagged 19 drops
  with a road bridge below the fall (a 101 m fall in the Santa Ana Mountains); fixed before publishing, so the rule
  now only removes flags.
- A mapped fall within 50 m of the step's top-to-pool line now outranks both artifact tests (14 artifacts had one
  that close; the next was 88 m off). Up to 200 m it still names a drop, as before.
- Result (all six rebuilt from `04`, then `05_score`, `06_map` and `12_profiles` again after the road fix; same
  drops and ids): 165 artifacts released, none newly flagged. Central VT 168 -> 124, LA 268 -> 208, Lexington
  50 -> 34, N Georgia 174 -> 133, NE Connecticut 14 -> 11, Jackson 40 -> 39; matches to mapped falls 14 -> 18,
  217 -> 224, 10 -> 11, 118 -> 122, 0, 15 -> 16. Checked by hand: Texas Falls, Huntington Gorge, Sterling Falls
  Gorge, Otter Creek Falls, Amicalola, Santa Paula Creek and Statons Creek now match their mapped falls; the
  Middlebury fall is an unmapped short fall (28 min approach); the culverts on Muddy Brook and Weaver Creek stay
  artifacts. No failed step in any area.
- Viewer: a click on a profile keeps that spot's details below the chart (the hover values, GPS with a copy
  button, map links, and any drop, mapped fall or gauge within 60 m); the map ring's label has a × to take it off.
  `12_profiles.py` writes drainage as float64 (float32 rounded to 2 places came out as 12.449999809265137).
- Jackson: `08_hike` for teton_snake ran at 15:14 while the lakes pilot's `lakes.gpkg` was briefly in place, so
  it and `09_drive` were rerun without it before the map; the published Jackson has no lake-aware routes.
**Published 15:27 (site commit `31efc26`)** at the owner's word, "don't wait for se_pa, publish the six now", while
se_pa was building: a one-off copy of `publish_site.sh` that left se_pa out and let only se_pa's own build run
(the script's running-build test otherwise stops everything). Checked: all 24 map and data files of the six areas
as served have the build's sizes, Central VT's three match by SHA-256, `streams/se_pa/` is a 404. The six maps'
Go-to menus were built after se_pa entered `config.py`, so they list Southeastern Pennsylvania: a dead link until
se_pa is published. The drainages are the committed `05c` (the sea-level change to `05c` came at 15:21, after
every `05c` run here).

## 2026-11-19, afternoon: known waterfalls from every source (another session)
The user named three Vermont falls missing from the map: Triple Buckets, Bolton Potholes and Texas Falls. Texas Falls
was in fact an OSM waterfall; its drop showed as a likely DEM artifact (fixed by the drop-rule session above).
Bolton Potholes was in OSM only as a park, and Triple Buckets was in no source we read. Known falls had been only OSM
waterfall nodes and NHD waterfall points (plus CDFW in LA), each range taking its own lon/lat box, so falls near a
box edge were drawn twice.
- New step `02f_known_falls.py` (per area, before `05_score`; `run_mid.sh` runs it) merges every source into
  `data/raw/<area>/_shared/known_falls.gpkg`:
  - OSM: waterfall nodes and ways, named rapids, named swimming holes and falls-named features on streams.
  - NHD waterfall points.
  - USGS GNIS Falls and Rapids, from the current file and the 2021 archive.
  - Wikidata. The class ids were checked: Q34038 waterfall, Q695793 rapids, Q7658373 swimming hole.
  - CDFW's barrier surveys, moved here from `05_score`.
  - `data/known_falls_curated.csv`.
- Merge rules: one fall from several sources becomes one point. A point never absorbs a second point from the same
  source. Two different names merge only on the same spot (25 m). Upper, Lower, Little and similar words keep falls
  apart.
- `05_score` takes the falls within 500 m of each box and writes out only those inside it. Only `precise` points (OSM,
  NHD, CDFW and guidebook GPS at the fall) can outrank the artifact tests.
- Curated list: 143 rows from research across the six areas (six research agents, about 450 page reads):
  - Vermont's 1985-88 state inventory: Jenkins & Zika, ANR basin PDFs, read with macOS PDFKit.
  - New England Waterfalls, the World Waterfall Database and Vermont River Conservancy pins.
  - Tom Chester's 1999 San Gabriel waterfall list, Caltech's canyoneering guide and RiverBrain (Chattooga rapids).
  - The Chattahoochee River NRA shoals.
  - Points placed from directions on our DEM's steps say so in their note: Webb Falls, the Granville cascade chain,
    Benjamin Falls and Middlesex Gorge.
  - Left out:
    - The World Waterfall Database's lidar picks with invented names and no other attestation.
    - Pages that withhold coordinates for posted land.
    - Points given only to 30 seconds of latitude and longitude.
- Fixes to source data:
  - GNIS 1918292, a second "Bingham Falls" added in 2001, sits on Hell Brook Cascades in Smugglers Notch, 4.5 km from
    Bingham Falls. It is replaced.
  - Four Wikidata items in Georgia (Mud Creek, Stonewall Creek and Darnell falls, plus a rounded Bad Branch Falls)
    carry Ammons Creek Falls' coordinate or a rounded one. They are dropped.
  - Same-name points GNIS puts 0.5 to 1.4 km off (Raven Cliff, Amicalola) merge with OSM's.
- Held: gawaterfalls.com's 695 Georgia falls (Mark Ozboyd's map data: names, GPS, landowner, height) are in
  `data/known_falls_curated_gawaterfalls.csv.held`. The layers carry no license and many names are his own, so they
  stay off the public site until the owner decides.
- Known falls drawn per area, before (OSM + NHD per range, with edge duplicates) and after: Central VT 27 -> 99 (three
  boxes, before the north extension), NE CT 27 -> 27, Lexington 21 -> 27, N Georgia 206 -> 249 (gawaterfalls held), LA
  209 plus about 270 CDFW -> 412, se_pa 12 -> 13, Jackson 27 -> 23 (rebuilt at 15:55 once the Lakes session was done
  with it; matches 16 -> 18; the lake layer kept).
- Drop statuses after the rebuild (02f, 05_score, 06_map, 12_profiles; same drops and ids): "matches mapped waterfall"
  Central VT 18 -> 57, LA 224 -> 256, N Georgia 122 -> 141, Lexington 11 -> 12, NE CT 0. Artifacts 124 -> 121 (VT:
  Falls Bridge and Halpin falls under their bridges, Allen Brook Cascade below its bridge) and 208 -> 207 (LA, Newton
  Canyon Falls). The offline count with gawaterfalls included: 803 matches.
- Checked on the rendered maps (2D layer and popups; the 3D data carries the popups; the 3D canvas doesn't draw in the
  hidden preview pane, so its click popup wasn't clicked). **Published 15:50 (site commit `93a2cc3`)**: Central VT, NE CT,
  Lexington, N Georgia and LA only, by a one-off copy of `publish_site.sh` limited to those areas (Jackson was being
  rebuilt by the Lakes session; se_pa was its own session's; the front page didn't change). se_pa was rebuilt with
  02f at 15:50 but not published; the running-build check stopped it, and it goes out with the next publish.
- `02f`'s caches now carry the lon/lat box they were fetched for, so an area whose boxes grow fetches again.
- Vermont's north box grew to Jeffersonville (another session, rebuild 15:55-16:45). The strip's falls were researched
  and added to the curated list before that rebuild's 02f ran: Brewster River Gorge, Jeff Falls, Ithiel Falls, Green
  River Falls, Woods, Milton and Clarks falls, Sloping Falls, Gihon River and Waterman Brook falls, and Cadys Falls.
  Rows also rename OSM's Dog Head and Fairfax falls and add the 1985 inventory's notes. The curated list now has 156
  rows plus the 695 held.

## 2026-11-19, afternoon: lakes, piloted in Jackson (this session)
The user asked how to bring lakes into the analysis, chose a Jackson pilot, and asked for it to be "incredibly
accurate ... the highest quality data" with "high quality bathymetry for all of the lakes". Built: `05d_lakes.py`,
`lakelidar.py`, `lakedata.py`, `maplakes.py`, `lake_bathymetry.py` (ready, no public source to feed it), and hooks in
`08_hike.py`, `06_map.py`, `map3d.html`, `14_portable.py` that do nothing where an area has no `lakes.gpkg`. README:
"Lakes (pilot: Jackson)".
- **357 lakes.** 309 from NHD HR (1,490 touching the boxes; treatment / storage ponds out; under 0.5 ha only when an
  agency lists or a survey names them), 47 from OpenStreetMap where the lidar shows level water, 1 with the agency's
  outline (Sleeping Indian Pond).
- **Outlines and levels from 1 m lidar.** The newest survey per lake, read from USGS's cloud-optimized tiles. The
  seamless service serves the 2014 Grand Teton survey, not the 2022-23 QL1 one, which was checked tile by tile.
  167 shorelines from lidar (median overlap with NHD 0.78), 245 measured water levels. NHD's elevations were off by
  up to 12 m (Table Mountain Lake), and its outlines by whole deltas (Lower Slide Lake 206 vs 172 ha, checked on
  imagery).
- **No level water.** Three cases, after the first rule flagged fish lakes as dry: flattened (lidar shoreline);
  level within 15 cm but not flattened (Bills Bayou Pond, 95%: NHD outline, lidar level); not level (Dry Basin Lake,
  13 m of relief), flagged only with the 10 m DEM agreeing (28 lakes) or, where the bed lies below a normal water
  level, as drawn down that day (4; the unnamed 15 ha lake by Jackson Lake was drained in the fall 2022 flight).
  Checked on imagery: Hardemann Reservoir is meadow, Cow Lake's water fills under half its outline.
- **Fish.** Wyoming Game & Fish lake guide: 104 lakes, 46 with game fish, 58 with none, joined by NHD reach code
  (102). Cross-checks: GBIF records at 17 lakes (MARIS state surveys 154, iNaturalist 30, USGS NAS 23, museum 4;
  NAS alone is too coarse, mostly park or refuge centroids) and the 2002-03 Game & Fish / NPS gill-net survey of 22
  alpine lakes. No conflicts; brown trout (Leigh Lake) and brook trout (Bearpaw Lake) recorded beyond the agency
  list.
- **Bathymetry.** A research pass (NPS DataStore, USGS ScienceBase, Reclamation, Game & Fish, University of Wyoming,
  NOAA, the 3DEP topobathy index) found no downloadable survey for any lake here. Jenny, Jackson and Palisades are
  surveyed, but published only as figures or held by the authors. So depths are measured maxima, each checked in its
  source: Larsen et al. 2016 (Jenny ~73 m, mean ~43 m; the Game & Fish guide's 423 ft is shown as a conflict),
  McGlue et al. 2023 (Jackson ~143 m in 2018), EPA NLA sonar (Phelps 48.4 m 2012, Icefloe 32 m 2017), Stephens &
  Gipson 2005 (24 alpine lakes, transducer), the Game & Fish guide (20 more). 46 lakes.
- **Walking.** Lakes are impassable off trails. A first run sent reaches mapped through lakes to "swim" (one +37 h);
  a lake cell now takes its lake's quickest shore. Final: 272 of 6,419 reaches changed, 212 quicker (median 5 min),
  18 longer by 15+ min (max 37, Leigh Creek's canyon); 48 drops changed (max 39). Summer routes, without closures, run
  within ~10% of the Park Service's trail distances (Taggart 1.3 vs 1.5 mi, Amphitheater 4.5 vs 4.9 mi).
- **Land.** The PAD-US public-access service gives one record per place, often a designation; its "restricted" on
  federal land is about use rules (the Wyoming Range Withdrawal Area is mineral leasing), so only closed land and
  non-federal restricted land is flagged (10 + 2). It leaves Jackson Lake's water and ~300 m of shore out: those
  lakes take their shore's unit.
- **Coordination.** Four other sessions were rebuilding and publishing. The lake file was held out of the live path
  until Classification criteria's publish (31efc26, 15:31). Its Jackson rebuild had run the Tetons box once with the
  file in place, and it re-ran that box before publishing, so nothing lake-aware was published. The Jackson map was
  rebuilt at 15:56 after the known-falls session's 05_score and 12_profiles. 14_portable.py (last run 15:48, which
  has the lakes but not the final notes) and publishing wait for the Vermont north rebuild (15:55-16:45).
- **Later the same afternoon.** `run_mid.sh` runs `05d_lakes.py` after the drainages and flow; a failed download
  keeps the last `lakes.gpkg`. Published on the user's "Yes, publish then", after the Vermont north rebuild finished:
  Jackson only, by hand (the files `publish_site.sh` copies for an area), commit 94566e0 at 19:18 EST, 4 files under
  `streams/jackson/`. It carries the known-falls session's Jackson rescore, which that session had checked. The live
  2D map, 3D page and 3D data were confirmed byte for byte against the build: the first check of the 3D data hit a
  cached copy from mid-deploy. `14_portable.py` (28.6 MB, 7 areas) and `phone_sync.sh` were rerun after it.
- 16:00, owner: "Publish with credit" for the gawaterfalls.com list. It is now
  `data/known_falls_curated_gawaterfalls.csv` with the source "gawaterfalls.com (Mark Ozboyd)". Each popup links his page
  for that fall, and `06_map` adds any guide with 50+ falls on a map to its credit line. N Georgia rescored at 16:10
  (929 known falls); the se_pa session's drainage refresh rebuilds its map and profiles. Stamping the old download
  caches with their boxes (they predate the box key) stopped 02f refetching Overpass for areas whose boxes didn't change;
  one such refetch had hung for 10 minutes.
- 16:23 PT (the machine's clock switched to Eastern time around then: logs and file times after it read 3 hours
  later): N Georgia's 06_map and 12_profiles with the gawaterfalls list; the drainage refresh hadn't reached it. Georgia
  now shows 925 known falls (693 from gawaterfalls.com) and 455 drops matched to a known fall (was 141). Checked on the
  rendered map: popups carry the credit and a link to his page for that fall, and the credit line names him.
  **Published alone at 16:25 PT (site commit `38a2dd7`)**: only `streams/n_georgia/`, front page untouched. The live
  Georgia data carries the credit.


## 2026-11-19, evening: Vermont's north box reaches Jeffersonville (another session)
**User: "expand the Vermont north map to include the stowe valley", then "i want bingham falls if its not already in
it".** Both were already in. The north box (`stowe_lamoille`, "Stowe & upper Lamoille") held the whole Little River
drainage (290 km², 0.1 to 0.85 km inside the edge at its closest). Bingham Falls is a known fall (OSM, USGS GNIS and
NHD agree) with two drops on the West Branch Little River (16.5 and 9.8 m) matched to it, in the 2D and 3D maps and
the profiles. The waterfall layers start off (default-layer rule), which may be why it wasn't seen. The box's north
edge then ran at 44.56 to 44.57° N, through Morrisville and just past Smugglers Notch. The user asked how far north
Johnson and Jeffersonville were, then chose "Jeffersonville, where the Brewster River meets the Lamoille" (5.4 mi
north of the old edge at the town centre) over the suggested ~7 mi.

**Change.** `config.py`: stowe_lamoille's bbox top goes from 4,937,000 to 4,947,000 (+10 km, 6.2 mi). The edge now
runs from 44.647° N at the east end to 44.663° N at the west end. The Brewster's mouth (NHD) is at y 4,946,327, 0.4 mi
past the town centre, so the edge sits 0.7 km beyond it.
- The box gains 650 km²: the north side of Smugglers Notch and the whole Brewster River; the Lamoille from Morrisville
  through Hyde Park, Johnson and Jeffersonville to Cambridge, and on to Milton in the west; the lower ends of the creeks
  joining it from the north (Gihon, Green River, Wild Branch, Seymour River, Kenfield Brook, Malletts Creek).
- The falls session first added the strip's falls to `data/known_falls_curated.csv` (Brewster River Gorge, Jeff
  Falls, Ithiel, Dog's Head, Cadys, Green River, Woods, Milton, Clarks, Gihon River and Waterman Brook falls).
  Vermont now has 114 known falls, 15 of them in the strip.

**Caches that don't notice a bigger box.** These were found before the run and moved to
`data/backup_20261119-vtnorth/caches/`, so they were fetched again.
- DEM tiles (`01_download_dem.py`). A tile on the box's top or right edge is cut there but saved under the full
  tile's name, so the old top row (cut at 4,937,000) would have been reused, leaving a 6 km strip with no terrain.
  **Fixed in the script:** a tile whose bounds don't match is fetched again (all five were).
- Keyed only by range name and age:
  - the OSM trail, access-road and cycleway caches (`02d`, `02e`, `08`);
  - `05_score`'s OSM waterways;
  - the canopy raster (`11_context`, 90 days);
  - `troutdata`'s state and TU layers;
  - `watertemp`'s Water Quality Portal downloads;
  - the PRISM clip (made once).
- Keyed by the set of range names: `02b`'s NHDPlus V2 table and `flowlib`'s reservoir list.
- `02f`'s OSM and Wikidata falls caches now record their box (the falls session's change). The rest still don't
  notice a box change: whoever moves a box next must clear the same files, or make them record their box.

**Run.** `01` and `02` for stowe_lamoille, then `run_rebuild_a.sh central_vt`, from 15:51 PT to 19:16 ET, about 25
minutes, with no failed step. The Mac's clock switched from Pacific to Eastern time partway through, so the log's
16:08 to 19:15 for `11_context` is about 7 minutes. The lid was closed for 8 minutes during white_river's `08_hike`,
which carried on afterwards.

**Checks** (scratch script `checks_vt.py`; the standing list from the memory notes):
- No empty terrain cells in the strip. No negative drainage cells (largest 1,680 km²). Order-3+ stream cells with no
  reach within 25 m: 0.0 km in all three boxes. Reach ends dead on a shared edge: 0 of 72. Sudden flow drops: 0.
- The strip:
  - 733 new reaches (Vermont 6,681 → 7,434): 687 year-round, 40 with no flow data, 5 reservoir; median fish score 62.
  - The Lamoille's drainage matches NHDPlus along its course: 333 vs 331 km² entering at the east edge, 977 vs 976 at
    Johnson, 1,275 vs 1,275 below Jeffersonville, 1,863 vs 1,863 at Milton. The Brewster has 50.7 vs 51.0 km² at its
    mouth.
  - Two USGS gauges joined the flow data (27 gauges; the yearly index now comes from 16, and no year moved by more
    than 0.02).
- The rest of Vermont against the build before (`data/backup_20261119-vtnorth/`): 99.5 % of reaches are at the same
  spot. Of those, 88.5 % have the same score and 99.9 % are within 5 points; 0.6 % changed flow class; the median stays
  at 64. Three reaches moved 10+ points, all at the old edge:
  - Kenfield Brook +27 and Malletts Creek +17: the old edge had cut them off (1.2 → 24 km² and 4.3 → 49 km²).
  - The Creek −35: its reach lies in an unnamed NHD reservoir on the refreshed reservoir list and now reads reservoir.
- On the rendered map:
  - the Brewster from the Notch to Jeffersonville, with its falls (Jeff Falls' popup says swimming, private land,
    visitors allowed);
  - Bingham Falls still marked;
  - no console errors.
- The 3D page loads its data (which has the Brewster and Gihon) with no errors. The browser pane draws no WebGL, though
  (the untouched Connecticut 3D page is blank there too), so the 3D view itself wasn't looked at.

**Edge effects of this edge (open; for the user to decide).** The Lamoille meanders across y 4,947,000 six times, and
two reservoirs straddle it.
- Between Cambridge and Milton the Lamoille loops north of the edge through Fairfax. On the 3 reaches (1.5 km) where it
  comes back, the routing drains them back out through the edge, so they show 3 to 5 km² and no flow. By design,
  crossbox hands the river's 1,820 km² on just below them. Between Johnson and Jeffersonville the river is off the map
  for about 4 km.
- The edge cuts Green River Reservoir (y 4,942,903 to 4,948,941). The routing drains the flat lake out through the
  edge, so the lake has no dead end to carry past its dam. The Green River below the dam (about 4 km) starts from
  nothing: 1.6 to 12.5 km² against NHDPlus's 38 to 50.
- An edge at 4,950,000 (8.1 mi from the old edge, 1.9 mi more) crosses neither the Lamoille nor any reservoir; it
  crosses only Lake Champlain, as the west edge already does. 4,949,500 still cuts Arrowhead Mountain Lake.

**Published (site commit `739374b`, 19:27 ET (16:27 PT)).** Only `streams/central_vt/` went up: the 2D map, the 3D
data, the profiles data and the north box's hillshade. `streams/index.html` went up too, with only Vermont's entry
replaced in the live page's area list. LA and Jackson had been rebuilt locally after their last publish, so the
regenerated page was not used: the other six entries and all the text around the list are byte for byte the live ones.
- Checked afterwards: all seven files as served have the same SHA-256 as the pushed ones, and the home page answers 200.
- The other sessions were told before and after the build. The lakes session ran `14_portable` and `phone_sync` once
  the build was done, so `phone/` and the single file have the new Vermont.
- Not committed in this project. Backups are in `data/backup_20261119-vtnorth/`: outputs, derived data, the north
  box's raw files, `config.py` and `01_download_dem.py` from before the change, and the cleared caches.

## 2026-11-19, evening: the two fixes applied to the other areas
**User: "Yes, apply them"** (both fixes from the se_pa work, in the other six areas). Times from here on are Eastern:
the Mac's clock moved from Pacific to Eastern around 16:20 PT.
- **Sea-level paths (05c).** Only LA's santa_monica box has sea cells. `run_drainage_refresh.sh la`: 174 reaches
  changed drainage, all on the Malibu coast.
  - Santa Monica Creek is its own drainage (before: a fork of Topanga).
  - Topanga 186 -> 51 km2; Arroyo Sequit 99 -> 28.
  - The "Zuma Creek" and "Solstice Canyon Creek" groups split into their own creeks, and 16 coastal creeks are named
    (Kenter, Trancas, Santa Ynez, Las Flores, Ramirez, Corral, Escondido, Carbon, Encinal, Temescal, ...).
  - Flows and fish scores are unchanged.
  - On the rendered map the outlines end at the shoreline.
  - Also seen, and older than today's work: a straight stream line about 2.5 km out to sea off Malibu. 06_map's
    drawn-through count is 59 breaks / 61.7 km before and after. Not changed.
- **NHDPlus split-channel flags (`flowlib.minor_arms`).** The first LA run, with the rule as written, moved 68 LA fish
  scores, 48 of them down:
  - Bear Creek below Big Bear: 100 -> 38.
  - Smith Creek: about 59 -> 28.
  - A Santa Clara River stretch: 60 -> 35.
  - Day Creek: 55 -> 15, as "no data".
  LA's flows come from TNC Natural Flows, which gives a minor path's COMID the natural flow of its whole drainage
  (Day Creek's line 0.63 cfs, a Santa Clara arm 0.16, where EROM has 0.02 and 0.002). So in LA those lines aren't the
  near-dry trap they are with NHDPlus's EROM flows, and leaving them out only moved reaches onto other lines.
  Streamcalc 0 also marks main lines inside a minor path's own split (Day Creek's line has divergence 1). The rule
  now applies only where the flows are NHDPlus's (`not has("tnc_flows")`). After the LA rerun, no segment, flow or
  score differs from before.
- **Tables fetched again with the flags.**
  - ne_ct, lexington_va, jackson and n_georgia by this session; central_vt by the Vermont session's rebuild (18:56);
    LA's table has them too, unused.
  - Against copies taken just before (`data/backup_20261119-fixes/`, Jackson and N Georgia re-copied after the
    waterfalls session's rebuilds): ne_ct no change; Lexington 3 segments / 1 low flow; Jackson 1 segment;
    N Georgia 2 segments / 2 low flows. No flow class or fish score changed in any of them.
  - Standing checks: no negative areas. No reach end dead on a shared edge; the creek heads that start at a box edge
    are the same as before. Flow drops: 0 in Lexington, Jackson and N Georgia. NE CT has 1 and LA 4, all on reaches
    whose flows today's work didn't change. NE CT's is the known below-pond case: a 2 km2 "Quinebaug River" reach
    below a lake that carries 33 km2.
- **Published (19:43, site commit `458a1fe`), by hand again.** The new `smokies` area's base build was running.
  - Published: `streams/la/`, `streams/se_pa/` (the waterfalls session's checked known-falls rebuild) and LA's
    front-page entry. The live files match the build by SHA-256.
  - Not published: ne_ct, lexington_va, jackson, n_georgia. They were rebuilt after `smokies` entered `config.py`
    (19:24), so their "Go to" menus list it; their changes are negligible. They go out with the first smokies publish
    (told that session).

## 2026-11-19, afternoon: creek profiles take drainage from the creek's own channel (another session)
(This entry was first written at about 15:55 PT. Another session's rewrite of this log dropped it before the 16:47
checkpoint, so it is restored here in short.)
- **Symptom.** The Cabin Creek profile (Hoback) said "Drainage at mouth 3,138 km²". That is the Snake River's figure;
  the creek drains 24 km².
- **Cause, in `12_profiles.py`.**
  - A point's drainage was the largest value within 60 m of the NHD line. The search is that wide because the line can
    sit up to about 60 m off the DEM channel.
  - NHD draws every creek out to the receiving river's centreline, so at a mouth the search reached the river's
    channel. A running maximum then carried the river's value to the mouth.
  - The strips used the nearest reach of any name, which at a mouth is the river's.
- **Scale.** 1,983 of 2,962 checkable profiles read more than 1.5x their own drainage. 1,091 showed the receiving
  stream's fish score as their best.
- **Fix.** Drainage, strips and best score now come only from the creek's own channel:
  - reaches named after the creek;
  - unnamed reaches up to 2x its largest named one + 1 km² (`OWN_CAP`);
  - never a reach's junction cell.
- **After.** 47 profiles still read more than 1.5x (6 at 10x or more), and 80 best scores still come from another
  stream. Ids, lines, elevations and drops are unchanged.
- **Published** 15:51 (site commit `af1e0d2`). Committed in `e8d5957` by the overview session.

## 2026-11-19, evening: reach names along rivers, and drops named after their reach (another session)
Of the 47 profiles left high above, 22 came from `05_score.py`'s name vote. The vote takes the nearest NHD line at
three points of each reach. Where a creek comes in, NHD draws the creek's line out to the river's centreline, so on a
short river reach two of those points can lie nearest the creek's line. Examples of river reaches that took a
creek's name:
- The Snake at Little Red Creek's and Station Creek's mouths (3,321 and 3,242 km²).
- The Santa Clara River below Castaic Creek (1,008 km²).
- The Chauga at Hell Hole Creek's mouth.

Many short river reaches also got no name at all. The same nearest-line rule named drops after a neighbouring stream:
two Jackson drops on Little Cottonwood and Blue Bell creeks read "Snake River", and the Pigpen Falls drops read
"Lick Log Creek".

**Fix, in `05_score.py`.**
- A reach between two reaches of one river takes the river's name. Its two neighbours are its largest upstream reach
  and the reach below, with unnamed reaches passed over. It applies when the vote gave the reach no name, or the name
  of a much smaller stream (every other reach of that name within 3 km drains under half as much).
- Streams of about the same size keep the vote: forks, the Chattooga and Tugaloo in Tugaloo Lake, and spelling
  variants such as Trabuco Creek / Arroyo Trabuco.
- The rule runs once, from the vote's names. Repeated passes flipped such pairs back and forth.
- A drop takes the name of the reach its top cell is on. On an unnamed reach it takes the nearest NHD line's, as before.
- The perennial test for big-creek drops still uses the nearest NHD line. Its disagreements with the reach are mostly
  NHD gaps, not junctions, and changing it would change the set of drops and their ids.

**`05c_drainages.py`.** NHD calls the East Fork's stem "San Gabriel River". Its fork had been named from the one reach
that carried "East Fork San Gabriel River", which this fix renames. That left 271 reaches labelled "Prairie Fork",
until a `FORK_FIX` entry put "East Fork San Gabriel River" back.

**Test.** Before the real rebuild, the script was run in scratch on five areas. Only names changed: reach ids, drop
ids, scores, flow classes and statuses all matched.

**Rebuild.** Per range `05_score` then `05c`, then `11_context`, `06_map` and `12_profiles`, for central_vt,
lexington_va, ne_ct, n_georgia and la (19:40–20:01 ET).
- Jackson is left to the Wyoming expansion rebuild. Central VT was rebuilt again afterwards by the Vermont session,
  and that session published it at 20:18 (`ffe5189`). Both runs include this change.

| | reaches renamed | of those, had a wrong name | drops renamed |
|---|---|---|---|
| la | 208 | 20 | 456 |
| n_georgia | 249 | 17 | 29 |
| ne_ct | 73 | 7 | 4 |
| lexington_va | 32 | (not counted) | 7 |
| central_vt | 91 | 3 | 28 |
| jackson (tested in scratch only) | 103 | 5 | 108 |

**What else changed.** No drop status changed. Trout records follow the corrected names, so some fish scores moved:
- **Down:** the Mill Creek reach below Mountain Home Creek 85 -> 35 (Mill Creek's surveys found no trout); a Great
  Meadow Brook gap 76 -> 31.
- **Up:** the Chauga at Hell Hole Creek 75 -> 90; a Quinebaug reach 65 -> 78.
- **Tailwaters:** three lower Piru Creek gaps and one Chattahoochee gap now count as tailwaters (about +10).
- **Built channels:** five gaps filled with an aqueduct's name now take the built-channel x0.2.

**Profiles.** The ones above 1.5x their own reaches drop again. Some of the larger moves:

| creek | before (km²) | after (km²) |
|---|---|---|
| Castaic Creek | 1,008 | 108 |
| Deep Creek (San Bernardino) | 356 | 1.0 |
| Sneaking Creek | 321 | 5.2 |
| Chicken Creek | 165 | 21 |
| Hell Hole Creek | 66 | 2.5 |
| Labonte Brook | 102 | 2.9 |
| Marl Creek | 73 | 18.6 |

**Checked.** The North Georgia map labels the 65 km² reach "Chauga River" (32 cfs low flow, fish score 90), and the
two Pigpen Falls drops "Pigpen Branch".

**Published.**
- 20:23 (site `f7d56a2`): la, n_georgia and lexington_va maps and profiles, plus ne_ct's profiles. ne_ct's map was
  rebuilt by the lakes session at 20:02, after this run, so it was left to that session.
- The three maps were rebuilt after `smokies` entered `config.py`, so their "Go to" menus list the unpublished
  Smokies. They were put back to the previous versions at 20:25 (`e5749e0`).
- Live now: the profiles. The maps go out with the first Smokies publish (that session was told).

**Committed.** The overview session committed `05_score.py`, the README note and the `FORK_FIX` entry in `4a8c1c8`.
This entry is new since then.

**Moved on to 4,950,000 (user: "Yes, move it"), 19:47 to 20:20 ET.** `config.py`: stowe_lamoille's top goes from
4,947,000 to 4,950,000, 13 km (8.1 mi) north of this morning's edge. The edge now runs at about 44.67° N at the east end
and 44.69° N at the west. It crosses neither the Lamoille nor any reservoir: Arrowhead Mountain Lake, Green River
Reservoir and Schofield Pond are now inside, and only Lake Champlain is cut, as the west edge already cuts it.
- Same cache clearing as before, now also the three `trout_lake_vt_*` caches that the lakes work had added. `01`
  fetched again the five tiles of the row cut at 4,947,000; `02f` refetched its falls on its own (its caches know
  their box now).
- Run 19:48 to 19:58 ET, with no failed step. `05d_lakes` did nothing: asked first, the lakes session took central_vt
  out of `BUILT` at about 19:50 (Vermont's lakes aren't ready), and will add them itself.

*Checks.*
- No empty terrain cells in the strip (8.45 M cells), no negative drainage cells, order-3+ cells with no reach 0.0 km,
  dead ends on shared edges 0 of 72, sudden flow drops 0.
- The two edge flaws are gone:
  - The Lamoille is continuous through the Fairfax loop and between Johnson and Jeffersonville (21.8 km drawn there).
    From Cambridge past Fairfax to Milton it carries 1,398 → 1,746 → 1,804 km², against NHDPlus's 1,408 / 1,784 /
    1,863. Lamoille reaches with no flow data went from 3 to 1 (a 157 m side reach in Arrowhead Mountain Lake).
  - The Green River below its reservoir now carries the reservoir's water: 28 to 39 km² against NHDPlus's 42 to 50,
    where it had 1.6 to 12.5. Its fish scores rose 11 to 27 points, to 79 to 92.
- Still there, and not caused by the edge: 12 short reaches named "Lamoille River" carry little drainage. They are
  side channels and tributary mouths beside the river, plus two small creeks along NHD's line through Arrowhead
  Mountain Lake (one is 2 km long, 4.2 km², 700 m from the routed river) that take the river's name by vote.
- Against the Jeffersonville build: 96.7 % the same score, 99.8 % within 5 points. Ten reaches moved 10+: the 8 Green
  River reaches above, and two short reaches at dams now matched to the NHDPlus line inside the lake, so they read
  reservoir (54 m inside Waterbury Reservoir, 80 → 24; 215 m at Lake Lamoille, −56).
- Against this morning's build, before both moves: 99.5 % of reaches at the same spot; of those, 88.9 % the same score,
  99.9 % within 5 points, median 64. Five moved 10+: the Waterbury Reservoir reach and The Creek (both inside
  reservoirs), an unnamed reach +14, and Malletts Creek +17 and Kenfield Brook +27 (no longer cut off).
- The strip north of this morning's edge: 965 reaches (Vermont 6,681 → 7,666), 791 km of stream, 94 % year-round,
  3.9 % with no flow data, 509 reaches at fish 60+. 16 known falls (Five Chutes joined).
- Rendered map: the Lamoille whole from the east edge to Milton; Green River Reservoir's basin inside the map, with the
  Green River running from the dam to the Lamoille; no console errors.

**Published (site commit `ffe5189`, 20:18 ET).** `streams/central_vt/` (the 2D map, the 3D page and data, the
profiles data, the north box's hillshade) and only Vermont's entry in the live front page. Checked afterwards: all
seven files as served match the build by SHA-256, and the home page answers 200.
- `phone/`: only Vermont was refreshed (its files and its entry in `phone/index.html`), because Jackson's expansion
  and the new Smokies area were mid-build. The single file (`stream_maps_all.html`) still has the 19:16 Vermont until
  the next full `14_portable` / `phone_sync`.
- The project commits `e8d5957` and `4a8c1c8` (made by another session at the user's request) hold this session's
  `config.py` and `01_download_dem.py` changes; this entry is not committed.
- Backups: `data/backup_20261119-vtnorth2/` (the Jeffersonville build and the caches cleared for this run).

**Go-to menus listed unbuilt areas (raised by the Cabin Creek session).** The Vermont map published as `ffe5189` lists
"Great Smoky Mountains" in its Go-to menu (in `stream_map.html` and `map3d_data.js`). That area entered `config.py`
during the build, and no Smokies map exists yet, locally or on the site, so the entry leads to a missing page.
- Cause: `06_map.py` built the menu from every area in `config.AREAS`. Fixed: it now lists only areas whose
  `output/<key>/stream_map.html` exists (plus its own area). An area appears in other maps' menus once it is built
  and those maps are rebuilt.
- Still open: an area built but not yet published can still be a dead link on the site, if another map is
  published in between.
- The live Vermont map was left as it is: its Smokies entry starts working when the Smokies map is published, and a
  republish to hide it would add about 64 MB to the site repository, which is already about 772 MB (GitHub
  recommends under 1 GB). The Cabin Creek session put its la, n_georgia and lexington_va maps back to the previous
  build instead (`e5749e0`).
- Checked later in the user's Chrome on the live site (the 3D canvas doesn't draw in a hidden preview pane): the 3D maps' known-falls popups work. Central VT: Bolton Potholes shows its kind, three sources, note and source link. N Georgia: Frogface Falls shows the gawaterfalls.com (Mark Ozboyd) credit and his page's link, and the credit line names him. No change was needed.

## 2026-11-19, evening: Great Smoky Mountains, a new area (this session)
User: "add in smokey mountain NP and the surrounding areas as a new location too". Asked which town drive times should
start from, the user answered "30305" (Buckhead, as for North Georgia).

**The area (`smokies`, UTM 17N, HU4 0601 and 0602, 7,901 km2).** The whole national park (its NPS boundary spans x
226.8-319.1 km, y 3923.7-3968.5 km) and the trout country around it, in seven boxes: `cades_cove` (Abrams Creek, Cades
Cove, Little River, Twentymile), `le_conte` (Elkmont, Gatlinburg, Greenbrier, Deep Creek, the Oconaluftee), `cataloochee`
(Raven Fork, Cosby, Big Creek, Cataloochee, Maggie Valley, Max Patch), `tellico` (Tellico and Bald rivers, Citico
Creek), `snowbird` (Snowbird, Santeetlah, Joyce Kilmer), `nantahala` (Nantahala Lake, the gorge, Wesser), `tuckasegee`
(Bryson City's south side to Dillsboro, Sylva, Cullowhee, Caney Fork).
- Outer edges were placed by measuring, for each candidate edge, the named streams (NHD) the edge would cut into pieces
  that leave the map and come back in (each piece starts again from nothing) and the lakes it would cross: the first
  layout cut Waldens, Burningtown, Scott and Hanging Dog creeks and the Hiwassee (79 km of stranded pieces, weighted);
  moving edges by 2-6 km brought it to 47, most of it the Little Tennessee inside Tellico Lake. Tellico Lake still
  crosses the Tellico box's north edge (below it, half of Citico Creek would be lost; the lake's dam is 30 km outside
  the map). The tuckasegee box's east edge (x 308.7 km) clears Cedar Cliff Lake.
- The first base build was started on the first layout, stopped in its DEM step and restarted after the edges moved
  (only the new area's own folders were cleared; DEM tiles cut at the old edges were refetched by `01`).

**Sources.** Trout: `nc_trout` (NCWRC's 2026 Public Mountain Trout Waters, streams and impoundments: Hatchery Supported
and Delayed Harvest, which it stocks, catch-and-release and the named Wild Trout Waters; left out, the game lands'
blanket "Wild Trout Waters unless otherwise noted", drawn on every creek there, 85 % of the km), `tn_trout` (TWRA's 201
stocking sites, its 1996-2022 wadeable electrofishing samples: 39 site records with trout, 88 with 2+ other species and
none, which count as no-trout records like Connecticut's; the 2016 brook trout genetics collections), `grsm_trout`
(the park's trout distribution, 1,828 segments; its "No Fish" code marks unsampled streams and is not used; segments
the park marks "Internal NPS Only" are left out), `ebci_trout` (the Raven Fork trophy section and the Enterprise
Waters), plus Trout Unlimited's 447 brook trout patches. Left out on purpose: NC's HUC12 trout watersheds (whole
catchments) and the park's fish barriers layer (all "Internal NPS Only"). Falls: `grsm_falls`, the park's own 80
waterfalls (precise where placed to under 14 m). Roads: the Blue Ridge Parkway, `ncdot_tims` (NCDOT's TIMS incidents,
the feed behind DriveNC; its old eapps API is gone), `tdot_smartway` (points), `grsm_roads` (the park's alerts JSON,
which names roads without geometry, matched to the park's roads layer; and its seasonal-roads table), `cherokee_nf`
(the Cherokee NF's road construction table, dates in words: "Fall 2026"). North Carolina's national forests publish
closures only as prose and PDFs; USFS MVUM seasonal dates exist as data but are not used for any area yet. Long trail:
the Appalachian Trail. Tailwater: Nantahala Lake -> Nantahala River (from 850 m, just below the dam at 848 m).
- Not used yet: the park's three-pass electrofishing workbook (1983-2024, 2,631 station-visits, on NPS DataStore)
  and NC DEQ fish samples through the Water Quality Portal (154 visits with species lists); both would add dated
  surveys and a few no-trout records.

**Build.** Base 19:48-19:58 ET (checks: no DEM holes, elevation 204-2,025 m, no negative areas). `02f` hung twice
on its one Overpass query over the whole lon/lat box (28 minutes, then 15, on both public servers), while the same
query in six 0.5-degree tiles answered in 2-3 s each: `02f` now runs its OSM query in tiles of at most 0.5 degrees
(all areas; same result, merged by element id). `09_drive`'s major roads (Atlanta to the Smokies, 52,146 ways) were
fetched the same way into its cache. Each step ran under a time limit with one retry.
- 9,017 reaches; median fish score 62; 4,995 at 60+. Drive from Buckhead: median 170 min to the Tuckasegee box, 261 to
  Cades Cove, 269 to the Gatlinburg/Le Conte box, 291 to Cataloochee. 207 known falls (OSM 161, NPS 79, NHD 44, GNIS
  26, Wikidata 5; 190 precisely placed); every famous one checked is there (Abrams, Laurel, Grotto, Rainbow, Ramsey
  Cascades, Thousand Drips, Lynn Camp, Mingo, Soco, Bald River, Falls Branch...). 20 closures today, among them six
  park roads and the Citico Creek Road bridge. Water temperature fit: August air + drainage area, 248 sites, leave-one-
  out RMSE 1.6 C. The Tuckasegee is not a tailwater: 14.7 C once below the dams near Cullowhee, 19.4 at East LaPorte,
  23.0 at Bryson City (45 readings). The Nantahala's bypassed reach above the powerhouse measures 20.6 C (2 readings),
  so the tailwater flag from the dam down overrates it by about 2 points at most.
- Bike access inside the park: 1,205 km of park trails are posted no-bikes in OSM, the AT no-bikes; the few fire roads
  read as bikeable are mostly the lower Deep Creek and Indian Creek trails (bikes allowed) and roads open to cars, so
  no change to the NPS rule (which would also have flagged Forest Service roads crossing the AT corridor elsewhere).
- Standing checks: order-3+ cells with no reach within 25 m 0.0-0.1 km per box; reach ends dead on a shared edge 0 of
  126; sudden flow drops 0; the big rivers end to end (Little Tennessee, Tuckasegee, Nantahala, Oconaluftee, Raven
  Fork, Deep Creek, Little River, Little Pigeon and its prongs, the Pigeon, Big Creek, Cataloochee, Abrams, Hazel,
  Tellico, Citico, Cheoah, Snowbird, Scott, Cosby). Rendered map: no console errors, default layers as set, popups
  checked at Fontana Lake and on the Nantahala, Soco Creek whole across the box edge.

**Two fixes found on the rendered map.**
- `05b_flow.py`: a reach lying at least half inside an NHD lake or reservoir with no model segment of its own was scored
  as a stream: "no data" took NHD's perennial label, "scaled" took the flow of the river below the dam (Fontana Lake's
  arms showed "year-round, 1,304 cfs, fish 83"). Such reaches are now "reservoir", the test model segments already got
  (`below_dam_comids`: half the length in the water). Counted on the builds as they stood: no data / scaled inside
  lakes LA 64 / 122, Jackson 198 / 138, N Georgia 48 / 230, Vermont 91 / 57, NE CT 54 / 79, Lexington 0 / 5, se_pa 2 /
  7, Smokies 93 / 118. In the Smokies 211 reaches changed, all to reservoir, median -43 points, no other reach changed.
  The other areas change at their next `05b` run; the Wyoming and Adirondacks sessions were told.
- `05c_drainages.py` NAME_FIX / FORK_FIX: in the le_conte box the Little Tennessee's arm of Fontana Lake took the name
  of the one named creek in its basin, Fishtrap Branch (the lake's centreline has no river name there), and `06_map`
  passed it up the Little Tennessee, Alarka, Burningtown and Tellico creeks across the box edges. Now "Little
  Tennessee River".
- Also checked at the Wyoming session's warning about lakes across box edges (in Jackson they broke the carry past
  dams): Fontana and Chilhowee cross edges here, but the full drainage just below every dam matches NHDPlus within
  1-4 % (Fontana 4,042 vs 4,089 km2, Cheoah 4,681 vs 4,726, Calderwood 4,777 vs 4,821, Chilhowee 5,096 vs 5,150,
  Santeetlah 453 vs 458, Nantahala 234 vs 243).
- Final rebuild 21:57-21:59 ET with the falls deep-dive session's three curated rows (the park layer's second "Chasteen
  Creek Cascade", which its own fields put on Flat Creek, now Flat Creek Falls; two roadside falls on Cooper Creek
  Road from ncwaterfalls.com): `02f`, `05_score` for the seven ranges (reach ids, geometry and names checked identical
  to the run before, so the flow, drainage, hiking and sun tables stand), `06_map`, `12_profiles`. 208 known falls.
  Standing checks as above; the map is in imperial units (the units session's change, picked up by `06_map`).
- Publishing: by agreement with the imperial-units session, one combined commit (its se_pa, central_vt and ne_ct
  re-renders, `streams/smokies/` and a front page with the Smokies), to keep the site repository's growth down (814 MB
  of history before it; GitHub recommends under 1 GB). The Cabin Creek session's la, n_georgia and lexington_va maps
  are left to the Lakes session, which rebuilds them with lakes.
- **Published (site commit `c6df975`, pushed by the imperial-units session at about 22:07 ET; live at 22:08).** Checked
  afterwards: all 12 files of `streams/smokies/` as served (2D and 3D maps, 3D data, profiles page and data, seven
  hillshades) match the build by SHA-256; the live front page is the committed one and lists eight areas, the Smokies
  among them; the old home page answers 200. Live at https://alexanderswann.github.io/streams/smokies/stream_map.html.
  The site repository's history is about 883 MB now. The Smokies map's Go-to menu lists the Adirondack maps, which
  stay dead links until they are published; maps of other areas list the Smokies once they are rebuilt.
- Not committed in this project's git: the changes after the 17:04 PT checkpoint (05b lake rule, 02f tiling and park
  falls, troutdata NC/TN/park/Cherokee sources, 07 closure feeds, 05c name fix, config sources and home, README, this
  entry).
- Open, raised by the Adirondacks session (adk_southwest, `speculator:s518` Piseco Outlet, 700 m below Piseco Lake: 0.43
  cfs on 174 km2) and diagnosed here, not changed: the reach's own NHDPlus line runs mostly through the lake, so it is
  flagged "in:Piseco Lake" and the full-area match reads "reservoir"; `05b`'s keep-the-higher-estimate rule then keeps
  the box-area estimate, scaled from the river downstream by 1.3/374 km2. Possible fixes: treat a reach outside the
  lake that matches an "in:" segment as below the dam, or don't keep a scaled box-area estimate where the full area
  is many times the box area. Not caused by the new lake rule (which only touches reaches lying in a lake); none in
  the Smokies.

## 2026-11-19, evening: the Adirondack Park (this session)

**20:00 — Request.** "add in the adirondacks park as a new location too". Read as the whole park inside the Blue Line.
The boundary is OpenStreetMap relation 1695394 (source: Adirondack Park Agency): 23,560 km², x 474.2-635.8 km,
y 4,766.7-4,970.1 km in UTM 18N, about four times Central Vermont.

**Four maps, not one.** At the other areas' 4-8 KB of map per km², one map of the park would be about 150 MB: over
GitHub's 100 MB limit for a file (`publish_site.sh` stops at 95 MB) and too heavy for a phone. So the park is four
areas, each its own map, linked by the "Go to" menus and the map of all areas:
`adk_high_peaks` (High Peaks & Lake Placid), `adk_northwest` (Long Lake, Tupper & Cranberry), `adk_southwest`
(Old Forge & West Canada Lakes), `adk_southeast` (Hudson, Indian Lake & Lake George). 20 boxes, 29,700 km² of
boxes for the park's 23,560.

**Where the maps meet.** Each map's hydrology ends at its edge (03b joins only one area's boxes), so the lines
between maps and the outer edges were placed with scripts (scratch, not kept) that scored every candidate line
by the NHD lakes it cuts (a lake cut at an outer edge drains out through it, as Green River Reservoir did in
Vermont) and the named streams it crosses more than once (a creek that leaves and comes back starts again from
nothing, the Smokies' lesson). The first layout counted only rivers and missed creeks that run along a line
(Fourth Creek, Browns Tract Inlet, Bear Brook on y 4,850; the West Branch Oswegatchie for 13 km along the west
edge; the Black River at Forestport; the Saranac at Plattsburgh; the Hudson meandering along y 4,867.6 at
Newcomb, where it runs through lakes as NHD artificial paths); the final one counts every named stream,
artificial paths included. Results:
- No lake of 1 km² or more is cut by a line between maps. Long Lake, the Raquette from Long Lake past its loop at
  Axton to Tupper Lake, Stillwater, Raquette Lake, Forked Lake and Blue Mountain Lake are in the northwest map; the
  whole Saranac chain in the High Peaks map; Indian Lake and the Hudson below Newcomb in the southeast; the Black
  River from Forestport to Lyons Falls in the southwest.
- Cut and left so: Round Pond (0.92 km², by Long Lake's east shore) and Square Pond (0.86 km², St. Regis Canoe
  Area) lie across the line between the northwest and High Peaks maps; Queer Lake (0.48) is touched.
- Creeks that still leave a map and come back, all outside the park or big enough for `crossbox.py` to carry
  their NHDPlus drainage back in: the Salmon at Plattsburgh (1.9 km), the Little River (9 km, northwest corner),
  Halfway Brook (Queensbury), Kennyetto, Crook Brook and Chase Vly Creek (south of the Great Sacandaga), East
  Canada Creek (0.5 km), the Cedar River (0.3 km at a corner), Sucker Brook (2.5 km, on the northwest/southwest
  line).
- Inside a map, box edges may cut lakes (Raquette Pond, Lake Clear, Carry Falls Reservoir, Seventh Lake...):
  03b routes an area's boxes as one surface.

**Area-specific code.**
- `config.py`: the four areas; `min_relief=50` (the Champlain valley and the western plains are gentle);
  `long_trail` the Northville-Placid Trail (OSM relation 4286650, no ref, matched by name).
- `troutdata.py`: `ny_trout` (`_ny`): NYSDEC's categorized trout stream reaches (Wild-Quality, Stocked,
  Stocked-Extended; species, schedule and number stocked, as trout waters and as stocking records), the streams
  classed trout (T) or trout spawning (TS) in the water quality standards, and public fishing access along trout
  streams (DEC's fishing rights easements, other agencies' banks). All on DEC's ArcGIS Online (services6 ...
  DZHaqZm9cxOD4CWM). Not used: DEC's pond stocking list on data.ny.gov (towns, no coordinates). Plus
  `tu_brook_trout` (1,602 brook trout patches in the park's box).
- `geomatch.wilderness_path()`: source `nys_forest_preserve` adds the Forest Preserve's Wilderness, Primitive and
  Canoe areas (NYSDEC lands layer, CLASS) to the wilderness layer: no bikes there by the State Land Master Plan,
  so trails in them are "no bikes" and fire-road rides through them get the bike_check flag, as in a federal
  wilderness. Other areas unchanged (NE Connecticut's file re-read: 0 units).
- `02f_known_falls.py`: STATES for the four areas (NY; VT too for the two whose east edges reach the Vermont shore).
- Home for drive times: 05753 Middlebury, the user's nearest home ZIP (Central Vermont's), following the Smokies
  session, whose user answer was "the same home as North Georgia". Not asked here; easy to change (09_drive,
  06_map).
- Road closures: none (511NY's API needs a key).
- `troutdata._tu()` fix (general, found here): Trout Unlimited's patch layer in New York also covers catchments
  marked "No trout documented" (229 of the High Peaks map's 638 patches) and "Brook trout predicted" (213, a
  model), and `_tu()` labelled every patch "Wild brook trout patch", which gives the creeks in it the trout-water
  bonus. Those two classes are now left out (no label, no bonus; nothing lowers a score), and "Brown trout only" /
  "Rainbow trout only" patches are labelled "Wild trout patch". Checked every other area's cached patches: none
  has any of these four values (Central Vermont: 165 patches before and after), so no other map changes.

**Builds (all four on the same code; base 20:41-21:54, re-run of mid + late 21:58-22:14).** Two chains, base then
mid then late per area. Two steps stalled on the network and recovered by themselves (the northwest's 01 on a 3DEP
transfer for ~50 min, the southwest's 05_score in the Overpass retry loop). The known-falls session's 52 curated
Adirondack rows (World Waterfall Database, nnywaterfalls.com / David J. Schryver, the Beaver Meadow(s) and Falls of
Carillon merges) landed at 21:57, so every area re-ran run_mid and run_late before the first publish; that also gave
all four the Smokies session's 05b lake rule (21:25) and the imperial display units. Then 06_map again for the three
maps rendered before the northwest map existed, so every Go-to menu lists all twelve areas.

| Map | Boxes | Reaches (ranked table) | Median fish score | Known falls (drawn) | Drops at a mapped fall | Water-temperature fit |
|---|---|---|---|---|---|---|
| adk_high_peaks | 6 | 9,800 | 67 | 67 (66) | 56 | elevation, 109 sites |
| adk_northwest | 5 | 8,459 | 67 | 71 (71) | 27 | August air, 87 sites |
| adk_southwest | 4 | 6,951 | 73 | 49 (48) | 11 | drainage area, 115 sites |
| adk_southeast | 5 | 8,704 | 64 | 79 (79) | 34 | drainage area, 54 sites (leave-one-out RMSE 2.53 C) |

- Trout-water labels: 70% of the southeast's reaches, 86% of the High Peaks' (Central Vermont 61%, NE CT 57%,
  N Georgia 49%). Checked that this isn't the 25 m buffer clipping tributary mouths: requiring 20% of a reach
  inside a record would only take the High Peaks from 85% to 81%. The rest is real: DEC classes most Adirondack
  streams (T) and the brook trout patches cover much of the park.
- Northville-Placid Trail: 148 OSM ways, 220.9 km. Drive times from Middlebury: 18-200 min (the southeast's Lake
  George box reaches the Vermont shore; Indian Lake 96-200, median 130).
- Wilderness layer, e.g. the southeast: 25 Forest Preserve units (Siamese Ponds, West Canada Lake, Hudson Gorge,
  Pharaoh Lake wildernesses, Essex Chain Lakes and other primitive areas).

**Standing checks (scratch script, vectorised).** Reaches are stored in lon/lat: reproject before measuring (my
first run measured nothing and reported hundreds of km).
- Negative cells in any area_km2.tif: 0 in all 20 boxes.
- Order-3+ stream cells of 1+ km2 with no reach within ~25 m: 0.0-0.1 km per box (Central Vermont 0.0 by the same
  script).
- Reach ends on a shared box edge with no other reach end within 30 m, downstream ends only (creek heads that start
  on an edge set aside): High Peaks 10, northwest 13, southwest 5, southeast 3, all first- or second-order creeks of
  1-2 km2; Central Vermont, published, gives 3 by the same script. Not chased.
- Sudden flow drops (flow per km2 under a quarter of both neighbours; lake reaches excluded, they are low on
  purpose): 0 in the High Peaks, northwest and southeast; 1 in the southwest: speculator:s518, Piseco Outlet 700 m
  below Piseco Lake, 0.43 cfs on 174 km2. Diagnosed by the Smokies session (read-only): its own NHDPlus line
  (22297164) runs mostly through the lake, so the full-area pass classes it "reservoir"; the box-area pass (1.3 km2,
  restarting at the outlet) walks down to the West Branch Sacandaga (374 km2) scaled by 1.3/374, and "keep the old
  estimate where the new one would be lower" keeps that. **Open**, two fixes proposed there: treat a reach outside
  the lake that matches an "in:<lake>" segment as below that dam with the segment's flow, or don't keep a scaled
  box-area estimate when area_edge is many times area_box.
- Looked at on the rendered maps (local server): the Hudson leaving the High Peaks map at Newcomb and entering the
  southeast map as one thick line, with the Boreas and Goodnow; the Raquette in the northwest map from Long Lake
  north past the Axton bend and west toward Tupper Lake, the Cold River entering from the High Peaks side; the
  Black River in the southwest map from Forestport across the box edge toward Lyons Falls, with Woodhull Creek;
  the West Branch Ausable at Wilmington Notch with The Flume Fall.

**Published (site commit `138467b`, 22:18 ET)** by hand on top of the imperial-units session's `c6df975` (and the
Lexington lakes commit `aa7035d`): `streams/adk_high_peaks|northwest|southwest|southeast/` (map, 3D page and data,
profiles, hillshades; 64 / 46 / 44 / 62 MB) and the four entries added to the live front page's area list from each
area's overview.json, with "eight" -> "twelve" in its two descriptions; nothing else in the page changed. Checked
afterwards: the twelve served files (map, 3D data and profile data of each area) have the pushed SHA-256s, the front
page answers 200 and says twelve. `streams/` is now 822 MB, near GitHub Pages' 1 GB site limit: the next areas will
need a plan (for example leaving the 3D data off the site). Local 13_overview (12 areas, 9.5 MB), 14_portable (51.5 MB,
was about 24), phone_sync (phone/ 881 MB) run at 22:22, before Jackson's re-run reached its map step.

**Open:** Piseco Outlet's flow (above); Round Pond and Square Pond on
a line between maps; the known-falls session's second batch (nyfalls.com blocks automated reads); DEC's pond stocking
list (towns, no coordinates) not used; maps rendered by other sessions before 22:14 list three of the four adk_
areas in their Go-to menus until their next 06_map.

**After publishing (2026-11-19, late).** Asked whether to keep 05753 Middlebury as the Adirondack maps' start for drive
times, the user answered "Keep Middlebury". Nothing to rebuild. The Piseco Outlet flow fix runs in its own session
("Fix scaled flows on reaches just below lakes").

## 2026-11-19, evening: the Wyoming map takes in all of Grand Teton NP, Driggs and Alpine (this session)
**User: "expand the wyoming map to include all of GTNP, driggs, and alpine".** The Jackson map ended at y 4,856 km,
straight through Jackson Lake (Grand Teton's NPS boundary reaches y 4,881.2), 4 km east of Driggs (x 491.1) and 2 km
west of Alpine, with Palisades Reservoir cut in two.

**New extent** (`config.py`): seven boxes, 9,305 km² (was 5,670), label "Jackson Hole, Grand Teton & Teton Valley".
North to y 4,885: all of the park, Flagg Ranch and Huckleberry Hot Springs. The Rockefeller Parkway's last 1.6 km to
Yellowstone are left out, because Yellowstone's own boundary cuts Grassy Lake Reservoir, Winegar and Tanager lakes
and runs along Calf and Harebell creeks. West to x 476: Teton Valley from Victor past Driggs and Tetonia to Badger and
Bitch creeks; Palisades Reservoir, its dam and the Snake down to Irwin. Boxes: `teton_snake` (now ends at y 4,842),
`gros_ventre` (ends at y 4,842), `hoback` (starts at x 506), `jackson_lake` (y 4,842-4,885, x 495-548), `buffalo_fork`
(new, x 548-558, y 4,842-4,856), `teton_valley` (new, x 476-495, y 4,800-4,878), `palisades` (new, x 476-506,
y 4,767-4,800). Edges were scored on NHD first: no lake of 2+ ha on an edge between two boxes, and no named creek
crossing an outer edge twice. The Teton Valley box reaches y 4,878 because at y 4,870 Bitch Creek crosses x 495
exactly at the corner. GRTE lies wholly inside, Driggs 15 km and Alpine 12.6 km from the nearest edge.

**Idaho.** New source `id_trout` (`troutdata.py`): Idaho Fish & Game's Yellowstone cutthroat streams, as StreamNet's
regional fish distribution serves them (layer 13; 124 lines here, from the 2002 and 2023 range-wide status
assessments and IFWIS records). Idaho publishes no survey or stocking layer. New closure feed `id_511`
(`07_road_closures.py`): Idaho 511's WZDx work-zone feed, which needs no key (its event API does); none in the area
tonight. 02f already took GNIS falls for WY and ID.

**Three box layouts in one evening** (backups in `data/backup_20261119-wyexpand/`, with the cleared caches):
1. Three boxes added beside the old three, which kept their edges. The checks found the Snake below Jackson Lake Dam
   at 16-28 km² for 5 km (NHDPlus 2,088) and short by about 2,100 km² all the way down; the South Fork below
   Palisades Dam had 1,130 km² (NHDPlus 13,444). (The user saw this build: "the Snake below the dam draws as a creek",
   reported through another session.) Cause: both reservoirs lay across edges between boxes (Jackson Lake under
   y 4,856 and x 528, Palisades under x 495). Each box conditions the flat water within its 5 km halo its own way, so
   the lakes' water ended in pits and flats on the edges (478 km² on jackson_lake's bottom row, the Snake's 3,836 km²
   on hoback's west column), 03b's outlet (the most-water cell) was one of those edge pits, and crossbox treats a pit
   on a box border as an exit, not a lake dead end, so nothing was carried past either dam.
2. Boxes laid out so each lake lies in one box. Jackson Lake then ended in one dead end 247 m from its dam and
   crossbox carried 1,949 km² past it. But the Snake's 3,619 km² still ended on the new Palisades edge at x 503: the
   Palisades box fills the reservoir's basin to its spill level (1,716.6 m), a flat reaching 4 km up the Snake to
   x 503.8, while the Hoback box, which can't see the dam, leaves those cells unfilled, 2 m lower. **An edge between
   two boxes must clear every lake and every filled flat around one, not just the lake's outline.**
3. Palisades edge at x 506. A gate after 03b (dead ends of 20+ km² on a shared edge) found none. The other session
   that ran it over all twelve areas found such dead ends only in adk_northwest and adk_high_peaks.

**Fixes in shared code that this expansion turned up:**
- `04b_bigcreek_steps.py` crashed on a box with no candidate (the 10 x 14 km Buffalo Fork box), and its first fix
  wrote the empty file with text-typed columns, which made that box's drops text and stopped 06_map. Now it writes an
  empty, numeric file.
- `watertemp.py` / `scoring.py`: with the new sites the water-temperature fit lost its skill (145 sites, leave-one-out
  RMSE 3.37 °C against a 3.72 °C spread: 0.906, bar 0.9; Jackson's was already marginal at 0.82, and with the larger
  spread the outlier pass no longer dropped Ditch Creek's two single readings of 22-23 °C). With no fit every reach
  got the neutral half credit and every Jackson score fell about 7.5 points (median 72 -> 64), although the old fit put
  every reach below 18 °C. A fit with no skill now falls back to the model the skill test compares with: every reach
  takes the measured sites' mean (13.4 °C here, full credit; `watertemp.area_mean()`, `mean_sites` in the fit file).
  No other area changes: all their fits pass (ratios 0.57-0.78).
- `03b_stitch.py` prints a WARNING for lakes lying across an edge between two boxes (print only). The Smokies
  session checked Fontana and Chilhowee, which do cross edges: their carries hold, since each dam and outlet sit well
  inside one box.

**Results** (checked against the build before the expansion, scratch `checks_jackson.py`):
- Standing checks: no negative drainage cells; order-3+ stream cells with no drawn reach 0.0 km in six boxes, 1.2 km in
  palisades (cells along its outer south edge, where the ground slopes off the map; no reach is drawn there: only
  3.1 km of drawn line lies within 25 m of the whole outer boundary); reach ends dead on a shared edge 0 of 163 (12 in
  layout 1); one sudden flow drop, an unnamed 11 km² reach near Moose that had it before (1.99 cfs then, 1.94 now).
- The Snake against NHDPlus: Flagg Ranch 1,209 vs 1,207 km², below Jackson Lake Dam at Moran 2,101 vs 2,112, Deadman's
  Bar 3,824 vs 3,929, Alpine 8,812 vs 8,959, below Palisades Dam 13,042 vs 13,234. The Teton River leaves the map with
  1,706 km² (NHDPlus 1,663). 16 short "Snake River" reaches are side channels, as before.
- 10,561 reaches (was 6,448), 2,524 drops, 547 lakes (139 on Game & Fish's list, 58 with a measured depth), 526 creek
  profiles. New boxes' median fish score: jackson_lake 74, buffalo_fork 77, palisades 63, teton_valley 61 (109 valley
  reaches "mostly dry": creeks that sink into the valley fill or go to ditches).
- The old area: 97 % of its reaches at the same spot; 85.6 % with the same score, 98 % within 5 points; median 72 -> 74.
  The big drops are reaches inside lakes (Jenny, Leigh, String, Taggart, Lower Slide), now "reservoir" by the Smokies
  session's 05b change. The big rises are creeks on the old outer edges that now get their drainage or Idaho's
  trout designation (Corral Creek, East Fork Palisades Creek, King Creek).
- Names the Cabin Creek session asked about hold: the Snake at Station Creek's mouth is "Snake River"; the drops on
  Little Cottonwood and Blue Bell creeks carry those names. Table Mountain Lake has its 1.34 ha lidar shoreline and
  no drawn-down note (the lakes session's 05d fix).
- On the rendered map: the Snake draws at full width from the dam through Oxbow Bend to Moran (popup: order 7,
  808 sq mi, "below Jackson Lake: releases set the flow"); below Palisades Dam 5,035 sq mi; Teton River popups read
  "Yellowstone cutthroat trout water (IDFG, via StreamNet)"; no seam at y 4,842; no console errors. The 3D page loads
  its data; the pane draws no WebGL, so the 3D view itself wasn't looked at.

**Published** (site commit `3c421fe`): `streams/jackson/` and the jackson element of `streams/index.html`'s area list,
by hand, after pulling the other sessions' commits (smokies, imperial units, the Adirondacks); the rest of the page
was checked byte for byte unchanged. `phone/jackson/` and phone/index.html's jackson entry updated the same way.
`14_portable.py` not rerun (other areas' lake builds were running).

**Open:**
- 05b's "scaled" flow (a reach off the model network takes the flow of the first modelled segment downstream) looks
  only within its own box, so small creeks draining across an edge between boxes get "no data": 10 % of reaches
  within 1.5 km of a shared edge here, 2.5 % overall (14 % near edges in the old build). It affects every area.
- In Teton Valley the fit's single estimate is the area mean, so a warm valley-floor creek isn't told apart from a
  cold canyon one in the thermal term (as before: the old fit put none above 18 °C). Single grab samples (n = 1) carry
  most of the misfit; weighting sites by their readings would help every area and wasn't tried.

## 2026-11-19, late: known falls for the Smokies and the four Adirondack maps (another session)
The guidebook research the first round did for seven areas, now for `smokies` and the four `adk_*` maps. Rows go in
`data/known_falls_curated.csv`; `02f_known_falls.py` is unchanged.
- **Research.** Six agents ran for 35 minutes against the first publishes' deadline. Scripted passes followed:
  - the World Waterfall Database's state KML exports (NY, VT, NC, TN) and each candidate's page (name status, height,
    form, status);
  - all 292 pages of ncwaterfalls.com;
  - nnywaterfalls.com's county list (630 falls in 12 counties).
  nyfalls.com answers automated reads with a Cloudflare bot check, and swimmingholes.org has shut down, so neither was
  used. A script checked every coordinate against its own page (decimal, or DMS within a second).
- **Left out:** names the WWD made up (marked "Unofficial") unless a guidebook it cites backs them; falls that are now
  dams or are gone (Union, Franklin, Dills, Stark, Rainbow on the Raquette, the La Chute mill dams); Mingus Mill's millrace
  fall; entries with no height; and catalogue points that conflict with existing ones (Tenant Creek's upper falls, Jay
  Falls).
- **Source-data fixes:**
  - The park layer's second "Chasteen Creek Cascade" sits on Flat Creek (its own stream and trail fields say so). It
    is renamed and now merges with OSM/GNIS Flat Creek Falls.
  - OSM "Beaver Meadow Falls" and GNIS "Beaver Meadows Falls" (90 m apart, kept apart by the plural) now merge.
  - OSM "Falls of Carrilon" and Wikidata "Falls of Carillon" (70 m apart) now merge.
  - OSM's "Indian Lake Day Use Area" node, tagged as a waterfall 21 m from Beaver Brook Waterfall, is dropped.
- **Batch 1 (55 rows, 21:57 ET)** was folded into both build sessions' first builds and published: the Adirondacks in
  site commit `138467b`, the Smokies with the imperial-units commit. 02f's NOTE lines: none.

  | known falls | before | after |
  |---|---|---|
  | smokies | 207 | 208 |
  | adk_high_peaks | 60 | 67 |
  | adk_northwest | 67 | 71 |
  | adk_southwest | 27 | 49 |
  | adk_southeast | 77 | 79 |

  Checked on the rendered Southwest map: the falls layer draws the new points, and their popups show name, source, note
  and source link.
- **Terms problem, found after that publish.** Two of the sources forbid redistribution:
  - nnywaterfalls.com: "It is forbidden to distribute or otherwise exploit the content within this site in any form,
    commercially or otherwise, without the express written permission of nnywaterfalls.com", covering its lists and
    data.
  - The World Waterfall Database: "No part of this website may be reproduced in any form or redistributed without prior
    written consent."

  ncwaterfalls.com states no terms.
- **The owner's decision (22:55 ET): "keep both, ask both".** Points from both sites stay live, each credited in
  `source` and linked to the site's page for that fall. The held batch is published, and the owner asks both sites for
  consent. If a site says no, its points come off everywhere, including the first round's WWD rows in central_vt and
  la. Rows by source in `data/known_falls_curated.csv` now:

  | source | rows | areas |
  |---|---|---|
  | World Waterfall Database | 106 | central_vt 44, adk_high_peaks 15, la 13, adk_northwest 13, adk_southwest 9, adk_southeast 6, smokies 6 |
  | nnywaterfalls.com (David J. Schryver) | 116 | adk_southeast 64, adk_southwest 26, adk_high_peaks 21, adk_northwest 5 |

  **Consent pending.** Draft emails are in the session notes:
  - david@nnywaterfalls.com, from the site's Contact Us page;
  - contact@worldwaterfalldatabase.com; its contact form is broken.

  Nothing has been sent.

  To pull a site: move its rows (match `source`) into a `.held` file; then for each affected area run 02f, 05_score
  for each range, 06_map and 12_profiles, and publish that area's folder.
- **Batch 2 (117 rows)** landed at 22:57 ET: 93 nnywaterfalls, 23 WWD, 1 ncwaterfalls (Bunches Creek Falls). Rules:
  - WWD falls only where its page calls the name official, historical or colloquial. Exceptions: three "unofficial"
    names that its pages tie to Kevin Adams' or Russell Dunn's guides (Buckner Branch, Wilson Creek and Hull Basin
    Brook falls).
  - nnywaterfalls falls if named, or unnamed and at least 10 ft. Its labels for unnamed falls are kept as names, and
    the note says so.
  - The Opalescent Falls row lost its "Opalescent Flume" alias: the WWD page lists none, and nnywaterfalls puts the
    flume 1.8 km away.
  - Three notes no longer repeat a name that 02f already appends as "Also called".
- **Rebuilt** smokies, adk_high_peaks, adk_southwest and adk_southeast (02f, 05_score for each range, 06_map,
  12_profiles; 22:57 to 23:07 ET). The builds carry the Piseco Outlet session's 05b fix, as agreed. No NOTE lines from
  02f.

  | known falls | before batch 1 | batch 1 | batch 2 |
  |---|---|---|---|
  | smokies | 207 | 208 | 212 |
  | adk_high_peaks | 60 | 67 | 88 |
  | adk_northwest | 67 | 71 | 81 (dry run; its rebuild belongs to the Jackson Lake outlet session) |
  | adk_southwest | 27 | 49 | 56 |
  | adk_southeast | 77 | 79 | 143 |

- **Checked on the rendered maps** (falls layer on, popups opened, no console errors):
  - known-falls markers drawn: Smokies 211, High Peaks 87, Southwest 55, Southeast 143;
  - the new falls appear, among them Basin Creek, Bunches Creek, Beer Walls, Gleasmans, Trenton, The Potholers and
    Natural Stone Bridge falls;
  - the Southeast credits line now names nnywaterfalls.com (David J. Schryver), which supplies 50 or more of that
    map's falls.
- **Published 23:09 ET (site commit `5f7660b`):** smokies, adk_high_peaks, adk_southwest and adk_southeast only, by a
  one-off copy of `publish_site.sh` limited to those folders. Checked at 23:12: all 16 files as served (map, 3D page and
  data, profiles data for each of the four) match the build by SHA-256, and the home page answers 200. adk_northwest
  goes out once the Jackson Lake outlet session's rebuild is done and checked (expected 23:45 to 00:15).

## 2026-11-19, late evening: creeks on NHDPlus lines that run through a lake (Piseco Outlet) (another session)
Task from the Smokies/Adirondacks sessions: the last sudden flow drop in the Adirondack maps, adk_southwest
`speculator:s518`, Piseco Outlet 700 m below Piseco Lake: 0.43 cfs on 174 km2, where the reach below carries 75.

**Cause.** The reach's own NHDPlus V2 line, comid 22297164 (Piseco Outlet, ArtificialPath, 176.5 km2), is 3.9 km long
and 73 % inside Piseco Lake; its last kilometre runs on down the outlet, 13 m from the reach's midpoint (the reach
itself starts 400 m below the shore, 0 % in the lake). `flowlib.below_dam_comids` flags the line "in:Piseco Lake",
so the full-area pass (173.67 km2) read the reach "reservoir" (water 0.3). The box-area pass (1.3 km2: the box's
routing starts the outlet again from nothing) matched no line and scaled the West Branch Sacandaga (22297212,
374 km2) by 1.3/374, year-round (water 1.0). "Keep the old estimate where the new one would be lower" kept that,
since its line (374 km2) passes the under-half-the-drainage test.

**Both candidate fixes measured on all 12 areas** before choosing. A scratch copy of 05b computed the current code
and each variant in one pass per box (55 boxes), writing only to a scratch folder. Where an area's last 05b ran on
the current code (Jackson, the Smokies, the four Adirondack maps), its baseline matched the tables on disk exactly.
- (a) A reach lying outside the lake (under half its length in any NHD lake, the Smokies lake rule's test) that
  matches an "in:<lake>" line isn't "reservoir": it takes the line's flow, as below that dam.
- (b) Don't keep a scaled box-area estimate where the reach's full area is over K times its box area (K = 2, 4, 10).
- Sudden flow drops: the Adirondack session's check (dry cfs per km2 of `area_full_km2` under a quarter of both the
  reach above and below; reaches of 1+ km2 with a flow, "reservoir" reaches left out), run on each variant's tables.

| Map | Reaches | Changed by (a) | "reservoir" -> creek | other flow source | below the lake (dam set) | Sudden drops now -> (a) | (b), K=2: changed / creeks made "reservoir" / downgraded |
|---|---|---|---|---|---|---|---|
| la | 17,857 | 12 | 12 | 0 | 0 | 1,000 -> 1,002 | 9 / 0 / 9 |
| jackson | 10,530 | 5 | 4 | 1 | 0 | 48 -> 48 | 17 / 1 / 0 |
| n_georgia | 15,045 | 20 | 18 | 2 | 0 | 2 -> 1 | 26 / 2 / 0 |
| central_vt | 7,632 | 7 | 7 | 0 | 1 | 0 -> 0 | 1 / 0 / 0 |
| ne_ct | 3,436 | 13 | 8 | 5 | 0 | 0 -> 0 | 18 / 1 / 0 |
| lexington_va | 4,287 | 3 | 3 | 0 | 0 | 0 -> 0 | 0 / 0 / 0 |
| se_pa | 4,623 | 2 | 2 | 0 | 0 | 1 -> 1 | 0 / 0 / 0 |
| smokies | 9,000 | 9 | 7 | 2 | 0 | 0 -> 0 | 15 / 0 / 0 |
| adk_high_peaks | 9,688 | 24 | 21 | 3 | 3 | 0 -> 0 | 23 / 2 / 0 |
| adk_northwest | 8,264 | 20 | 17 | 3 | 2 | 0 -> 0 | 33 / 0 / 0 |
| adk_southwest | 6,816 | 17 | 15 | 2 | 4 | 1 -> 0 | 12 / 1 / 0 |
| adk_southeast | 8,557 | 29 | 20 | 9 | 2 | 1 -> 0 | 18 / 3 / 0 |
| all | 105,735 | 161 | 134 | 27 | 12 | | 172 / 10 / 9 |

- (a): 134 reaches outside lakes had read "reservoir". Most are creeks coming into a lake that matched the line's
  part in the water: Eagle, Noland, Alarka and Sawyer creeks at Fontana Lake; the Nottely River above Nottely Lake;
  the Jessup and Miami rivers above Indian and Lewey lakes; the Willimantic above Eagleville Lake; the West Fork San
  Gabriel at San Gabriel Reservoir. Nearly all now read year-round. 27 more take the in-lake line's flow instead of a
  scaled or "no data" one: Piseco Outlet 0.43 -> 70 cfs; the Indian River below Indian Lake, no data -> 123 cfs; the
  Little Tennessee at Chilhowee Lake's head, no data -> 1,524 cfs; the Hubbardton River 2.1 -> 11 cfs. 5 drops follow
  their reaches.
- Drops found by the check: adk_southwest 1 -> 0 (Piseco Outlet), adk_southeast 1 -> 0 (lake_george:s1126, the
  Hubbardton River), n_georgia 2 -> 1 (cohutta:s606). The two LA additions are the check, not drops: dry side creeks
  of 2 and 4 km2 (san_gabriel:s3004, santa_ana_mtns:s367) whose main-stem neighbours were "reservoir", so left out
  of the check, and now count. LA's ~1,000 by this check are the check itself: LA's flows are natural flows scaled on
  the area without dammed water (area_edge), and the check divides by area_full. Not chased; nor Jackson's 48,
  se_pa's brandywine:s2587 or n_georgia's remaining one (all there before this change).
- (b) alone changes 172 reaches:
  - 153 are reaches inside lakes whose cfs changes while they stay "reservoir" (a reservoir's popup shows no cfs);
  - 10 are creeks outside lakes that it makes "reservoir": Piseco Outlet itself, the Greys River above Palisades
    Reservoir, the Hubbardton River, Mayfield Creek and others;
  - 9 in LA move down a class, from year-round or usually flows to seasonal: 7 reaches of Smith Creek (san_jacinto,
    9-22 km2 in its box, 55-68 with the inflow) and 2 in the San Bernardino box. That is the drop the keep rule
    exists to stop ("keep possible trout water").
  K = 4 or 10 shrinks the same kinds (81 and 23 reaches). On top of (a) it finds no further drop.
- Chosen: (a), the root cause: a line's "in:" flag was applied to a reach lying outside the water.

**One refinement, from looking at the reaches (a) changed.** As first written, (a) put every such reach "below" the
lake. But a creek matched to a side arm's in-lake line would then read "below Indian Lake: releases set the flow"
(indian_lake:s759, 8.5 km2, on Indian Lake's shore). So the dam is set only where the reach sits on the line's
stretch below the lake: its midpoint projects onto the line past the line's last point in that lake. NHDPlus lines
run downstream (checked on 3,000 of them). That is 12 of the 161:
- Piseco Outlet, below Piseco Lake;
- the North Branch Moose below Dart Lake;
- Black Cat Outlet;
- the Indian River below Indian Lake;
- Spring Run below Lake Lonely;
- the outlets of Lake Kushaqua, Spectacle Ponds, Spitfire Lake, Loon Pond and Handsome Pond;
- Martin Brook in Vermont.
The other 149 get no dam, and their class comes from their flow. Flow and class are the same either way, so the
counts above stand.

**Code (`05b_flow.py` only; nothing in flowlib).** Each reach's largest share inside one NHD lake is now computed
once; the Smokies lake rule reuses it, with the same result. A new `below_lake()` does the downstream test above. In
`evidence()`, for a reach or drop outside the water, the "in:" flag is dropped, or turned into the lake's name where
the reach sits below the lake. Each run prints how many reaches this applied to. Checks:
- the installed file against the scratch measurements on all 55 boxes: flow columns equal (a)'s, the dam text is as
  described, nothing else moves, the output columns are unchanged;
- the tables written by the reruns are byte-identical to that test run.
Installed at 22:52 in one write (the "Let scaled flows follow creeks across box edges" session edits 05b next, on
top of this).

**Reruns.** 05b at 22:54-22:56 in every box except adk_northwest's.
- Rendered here: se_pa (06_map, 12_profiles 22:57-22:58).
- Rendered by the known-falls session for its second falls batch: smokies, adk_high_peaks, adk_southwest,
  adk_southeast (22:58-23:06), which it publishes together.
- jackson, lexington_va, central_vt: rendered here (06_map, 12_profiles 23:08-23:10), after the lakes session
  checked that its latest lake fix changes nothing there.
- la, n_georgia, ne_ct: the lakes session runs 06_map and 12_profiles there after this 05b, with its own lake changes
  (a corrected drawn-down rule, Stiles Pond's lidar outline), and publishes them. Pending when this was written
  (23:12).
- adk_northwest: no 05b from here. The Jackson Lake outlet session's rebuild (03b lakes across box edges, 03 -> late)
  runs this 05b, and was running when this was written.
- The reruns also brought the Smokies lake rule into six areas whose tables predated it: la 186, n_georgia 278,
  central_vt 148, ne_ct 133, lexington_va 5, se_pa 9 reaches differ for that reason. Scores from it: central_vt 149
  (median -27), se_pa 9 (-34), lexington_va 5 (-29), all reaches in lakes now "reservoir".

**After, on the rendered maps** (before/after of stream_reaches_ranked.csv; the check on the tables on disk):

| Map | Fish scores changed by the fix (median) | Sudden drops |
|---|---|---|
| se_pa | 2 (+29.5) | 1 (brandywine:s2587, there before) |
| jackson | 4 (+53.5) | 48, there before (see below) |
| lexington_va | 3 (+40) | 0 |
| central_vt | 8 (+39.5) | 0 |
| smokies | 8 (+43) | 0 |
| adk_high_peaks | 22 (+56) | 0 |
| adk_southwest | 16 (+44.5) | 0 |
| adk_southeast | 22 (+46) | 0 |
| la | 12 (+33.5) | 1,002 (the check, above) |
| n_georgia | 20 (+45) | 1 (cohutta:s13, there before) |
| ne_ct | 9 (+41) | 0 |
| adk_northwest | rebuilt by the Jackson Lake outlet session: its 05b (00:27) read 20 reaches as creeks, 2 below a lake, as measured (Bog Stream and Moshier Creek 28-29 -> 94-98) | 0 (that session's check) |

Jackson's 48:
- 47 are small creeks in the Teton Valley (1-20 km2, little summer water next to the spring-fed Teton River). The
  check takes two main-stem reaches as their "above" and "below".
- The 48th is the Snake below Jackson Lake (teton_snake:s818: 1,656 km2, 51 cfs on a Gros Ventre line), the Jackson
  Lake outlet session's case.

The biggest moves are creeks that had been scored as "reservoir": Eagle Creek into Fontana Lake (67 km2, 33 cfs) 34
-> 100, Noland Creek 27 -> 90, the Jessup River above Indian Lake 28 -> 93, the East Branch St. Regis above Meacham
Lake 26 -> 86. Piseco Outlet stays at 70: its water term was already 1.0, and only its flow figures were wrong.

**Checked on the rendered map** (adk_southwest, local server, no console errors). Piseco Outlet's popup reads: fish
70, 67.1 sq mi, "year-round · low flow about 70 cfs in a typical July–October, 44 cfs in a drought year · kept
flowing 100% of summers since 2011 · below Piseco Lake: releases set the flow". The reaches below read 75-80 cfs,
the lake's own reaches "reservoir (Piseco Lake)".

**Publishing.**
- Live with this fix: smokies, adk_high_peaks, adk_southwest, adk_southeast. They went out in site commit
  `5f7660b` (23:09), pushed by the known-falls session with its second falls batch. Checked: the four maps as pushed
  are byte-identical to the builds checked here, and adk_southwest's carries Piseco Outlet's 70 cfs.
- ne_ct: live in site commit `a742b5c` (23:13), pushed by the lakes session with its Stiles Pond change.
- la, n_georgia: live in site commits `7caab8b` and `bf15161` (00:29), pushed by the lakes session with its lake
  layers. Both were rendered after this 05b (its tables unchanged since), and the maps as pushed match their builds.
- adk_northwest: the Jackson Lake outlet session's rebuild ran this 05b at 00:27 and rendered the map at 00:30. Not
  published when this was written (00:35); checking and publishing it is that session's part.
- se_pa, jackson, lexington_va, central_vt: published at the user's OK ("Yes, publish them"), by hand, in site
  commit `c22ed4c` (23:16). publish_site.sh would have copied every area, including the ones other sessions were
  still building.
  - Commit and push: only these four folders (12 files: each map, 3D data and profile data; the hillshades and page
    shells were unchanged); nothing outside streams/.
  - Before the push: each map loaded locally without console errors and showed the fix's reaches as year-round. No
    map code had changed since these areas' previous live renders, so the flows are the only change.
  - After the push: all 12 files as pushed match the builds by SHA-256. streams/ stays 848 MB, since these files
    replace ones of about the same size.
  - Live from about 23:19; all 12 served files match by SHA-256. (Two read different on a first fetch while the CDN
    was still updating, and matched on the second.) The live adk_southwest map, from the known-falls session's
    push, matches its build too, and its Piseco Outlet popups read "about 70 cfs ... below Piseco Lake: releases set
    the flow".
  - 13_overview, 14_portable and phone_sync were not rerun.
  - central_vt's render (23:09) predates the lakes session's maplakes.py fix (about 23:20: a White River stocking
    record no longer shows on Sunset Lake). The lakes session re-rendered it over these flows and published it again
    in `38ef337` (00:29); ne_ct went out again in `c9c8f60` (00:30). streams/ is now 858 MB.

**Open:**
- The Chattahoochee at Bull Sluice Lake's head (hooch_tailwater:s1492, 260 m, outside the lake) now reads
  year-round, 1,177 cfs, tailwater. scoring.TAILWATERS' 265 m split names that tailwater Bull Sluice Lake, though
  the reach is above Morgan Falls Dam and the cold water is Lanier's. The thermal term is the same either way.
- The sudden-flow-drop check doesn't work in LA: it divides LA's natural flows, scaled on area_edge, by area_full.
  And at confluences it pairs side creeks with the main stem (Jackson's Teton Valley).

## 2026-11-20, after midnight: lakes cut by an edge between boxes lost their water (03b fix; another session)

**Reported:** the user's screenshot of Jackson's 20:55 map: "at the outlet of jackson lake the snake river gets jacked
up". Below the dam the Snake drew as a creek, 1.8 km2 at order 2 and still 27.6 km2 at Pacific Creek, which (415 km2,
order 6) drew as the main river. The user asked for the root cause and where else it happens, then said to fix it in
03b and rebuild adk_northwest.

**Cause:** 03_hydrology conditions each box with only a 5 km halo of its neighbours. A lake, or a reservoir's basin
filled to its spill level, that reaches further across a shared edge is filled and drained one way by each box.
- Jackson's first expansion layout put the jackson_lake / teton_snake edge at y 4,856,000, through the lake about
  150 m from the dam.
- At Raquette Pond (adk_northwest) the long_lake box filled the pond 6 cm above its raw surface (469.92 m, its spill
  level), while the tupper box left its 273 m sliver at 469.86 m, draining it to its own halo's edge.
- In 03b's joined directions the higher side points into the lower, and all the water stops in a pit on the edge:
  154 km2 at Raquette Pond.
- crossbox reads a dead end on a box's rim as water leaving the box, not as a lake. `_dam_links` carries a lake past
  its dam only within one box. So nothing went past the dam, and 06_map's order raise had no carried area to work
  with.
- Jackson was fixed by the Wyoming session's relayout (its 22:28 map: order 7 and 2,077 km2 below the dam). The
  standing checks found the same bug live only in adk_northwest:
  - Raquette Pond and Carry Falls Reservoir: the Raquette below them drew at 3-13% of NHDPlus's drainage, from
    Tupper Lake to Warm Brook Flow.
  - Grass Pond: 61 km2 stopped on an edge.
  - adk_high_peaks: Lake Champlain stops on an edge too, but its outlet is off the map anyway.

**Fix, in `03b_stitch.py`:**
- **Step 2b, `mend_seams()`.** Every dead end of 0.25+ km2 on an edge between boxes gets a piece of the raw DEM around
  it conditioned again, whole, as 03 does it.
  - The cells whose direction that changes, joined to the dead end, take the new directions.
  - The piece starts 3 km each way and doubles, to 30 km at most, while those cells reach a 1.5 km band inside its
    own edges.
  - The new directions are kept only if the water then leaves the re-routed cells without a loop: off the map, or on
    to a dead end further down that has its own mend.
  - A first version demanded the map's edge and failed Raquette Pond, whose water met Carry Falls' unmended dead end.
- **03b exits 1** after writing its files if any such dead end is left. This is the Wyoming session's edge gate,
  built in.
- **Lakes with their outlet on an edge flow on.** A lake whose outlet cell (the one gathering the most water) is
  within one cell of an edge shared with another box no longer ends in a pit. Raquette Pond's water leaves it through
  tupper's sliver, 13 m from the dam in long_lake, where crossbox couldn't carry it.
- **Which areas this changes.** On every area's current 03b output both rules change nothing (0 dead ends on shared
  edges, no lake outlet within a cell of one), except adk_northwest and adk_high_peaks (Champlain, at its next 03b
  run). Other near-edge lake pits are 2-4 cells in and keep their pits.
- **Rebuild.** adk_northwest was rebuilt 00:24-00:31 with 03b → 04/04b → run_mid → run_late. 03 wasn't rerun
  (dem_cond unchanged, the mend reads dem_10m). The run picked up the 22:52 05b fix (creeks on NHDPlus lines through
  a lake) and the known-falls session's 22:57 falls (81 known falls).
- **Numba cache.** Testing the mend in memory, by importing 03b with importlib, wrote a numba cache that the real run
  couldn't load ("No module named '<dynamic>'"). Removed (scripts/__pycache__/03b_stitch.accumulate-75.*). In tests,
  set NUMBA_CACHE_DIR to a scratch folder.

**Results (adk_northwest):**
- **03b:** all 7 dead ends on edges mended (5,928 cells re-routed; pieces 12-48 km). 2 lakes flow on. 03b took about
  2 minutes; an earlier test took an hour while the machine was swapping (10 of 11 GB of swap in use).
- **Standing checks:** no negative drainage cells. Order-3+ cells with no drawn reach: 0.0-0.1 km per box. Dead ends
  on shared edges: 0 (was 5). Reach ends dead on a shared edge: 0 of 108. Sudden flow drops: 0.
- **The Raquette against NHDPlus:** about 0.9 from Long Lake down, now also below Tupper Lake.
  - On the rendered map: Raquette Pond's outlet order 7, 1,698 km2; Piercefield 1,812; below Carry Falls 2,097.
  - Before the fix: 51 km2 (order 4) below the pond, and 80-331 km2 below Carry Falls.
  - The NHDPlus comparison of lake outlets flags 6 lakes where it flagged 17; all 7 reservoirs of the Raquette chain
    are fixed.
- **Against the 22:06 build:**
  - 99.8% of reaches are at the same spot; 99.2% keep their score; 1.4% changed flow class.
  - 165 reaches changed full drainage by 20%+, 110 of them on the Raquette.
  - 45 moved 10+ points, all upward: the Raquette's main stem from "no data" to year-round (e.g. 12 → 82), plus
    side creeks from the 05b lake fix.

**Open:**
- Published at the user's OK ("Yes, publish it") in site commit `9363c92` (2026-11-20 10:25). By hand, only
  `streams/adk_northwest/` stream_map.html, map3d_data.js and profiles_data.js; the hillshades, profiles.html and
  stream_map_3d.html were unchanged. The local map loaded with 8,473 reaches and no console errors. Live from 10:28;
  the three served files match the build by SHA-256. The cross-box flow session's 05b change was rerunning in every
  area at the time; it re-renders all 12 areas, adk_northwest included, and publishes them after this commit.
- The "Let scaled flows follow creeks across box edges" session's 05b change waits for the user's OK. It will need
  adk_northwest's 05b/06_map again.
- Short "Raquette River" reaches of 1-30 km2 lying on NHDPlus's line are left over: side channels and stubs, and the
  stretch between Simon Pond and Raquette Pond (about 28 km2 against 1,324). They were the same in the 22:06 build;
  not chased.
- 6 small lakes in adk_northwest still read under half of NHDPlus below their outlets (Big Moose Lake, Rollins and
  Floodwood ponds, Bridge Brook Pond, two unnamed). They aren't on edges and crossbox links them; my NHDPlus
  comparison misread Silverwood Lake the same way (89 of 91 km2 carried, but the DEM's channel lies over 300 m from
  NHDPlus's line). Not chased.

## 2026-11-19, evening: lakes in five more areas, and the lake rules checked across all six (this session)
The user asked to extend the Jackson lakes pilot to the other areas at the same accuracy, and later to sync up with
the sessions fixing flows at lakes. Lakes are now built in Jackson, NE Connecticut, central Vermont, Lexington, North
Georgia and LA (`BUILT` in `05d_lakes.py`, smallest size per area), and published per area with
`publish_area.sh`-style commits that touch only `streams/<area>/` and that area's front-page entry.

| Area | Lakes | Lidar shorelines | Named from OSM | Measured depth | Contours | Trout stocked or recorded |
|---|---|---|---|---|---|---|
| Jackson (0.5 ha) | 547 | 244 | 3 | 58 | 0 | (Game & Fish list) |
| NE Connecticut (1 ha) | 725 | 650 | 83 | 45 | 1,076 lines, 35 lakes | 24 |
| central Vermont (1 ha) | 412 | 294 | 7 | 16 | 520 lines, 14 lakes | 23 |
| Lexington (0.5 ha) | 184 | 113 | 5 | 1 | 0 | 2 |
| North Georgia (2 ha) | 560 | 501 | 22 | 9 | 0 | 13 |
| LA (1 ha) | 398 | 92 | 46 | 6 | 16 lines, 1 lake | 18 |

- **State sources** (`lakesources.py`). Connecticut: CT DEEP boat launches and fisheries-management lake designations.
  Vermont: Fish & Wildlife fishing access areas, special regulations and restricted waters (its map server refuses
  paged queries: `troutdata.fetch` asks for ids first). Virginia: DWR public fishing lakes, with their boat and motor
  rules. EPA National Lakes Assessment soundings are now read for every area (they were typed in for Jackson).
- **Bathymetry** (`lake_bathymetry.py`). CT DEEP's lake contours (24 surveys of 1959-2002, a lower bound: "deepest
  contour X ft"); Vermont ANR's 2.4 million sonar soundings (compiled 2020), gridded at 5 m per lake with the shore
  at 0: Lake Dunmore 106 ft deep, 29 ft mean (published: 105 and 28). The script now repeats exactly when run twice,
  and `run_mid.sh` runs it after `05d_lakes.py` (before, a rebuild dropped the surveyed depths). LA: USGS's 2022
  multibeam grid of Little Rock Reservoir (76 ft deep, 38 ft mean; its elevations sit 106.4 ft under NAVD88 though
  labelled NAVD88, found against the lidar on land and confirmed by USGS's stage-storage zero) and Lake Arrowhead's 2008
  Reclamation sonar survey (152 ft, 61 ft mean, typed in from the report). Virginia: Lake Robertson's DWR contour map
  (deepest contour 45 ft, typed in). Not public or not usable: California DWR's Castaic, Pyramid and Silverwood
  multibeam; USACE's Lanier transects (sparse, CUI-marked); TVA's single Chatuge drawdown line. A research agent checked
  ScienceBase, the 3DEP topobathy inventory, state portals and agency services.
- **NHD's normal levels are unreliable, so the lidar decides.** Stage elevations are in feet at some lakes and metres
  at others, read per lake against the DEM (161 Connecticut lakes had been read wrongly, published e70326e, fixed
  fb69421). "Drawn down" needed a dam (reservoir, OSM dam or NHD dam line within 100 m), then also the normal shore
  standing over 1 m above the water in the same lidar: at 50 dammed North Georgia lakes NHD's level sits 2-28 m over
  water whose shore the lidar shows at the water's edge (Teague Lake, Etowah Number 32 Lake), so they were full and
  NHD is wrong. A bed under a neighbour's normal level counts only where its own shore lies at that level (the lake
  by Jackson Lake, 0.5 m under it); Cochrans Lake North sits 9.7 m below Cochrans Lake South's level and fills on its
  own. A dammed lake without an NHD level is judged against its own lidar shore (Cave Mountain Lake, a Forest Service
  swimming lake full on today's imagery, lay drained in the 2017-18 flight). A lake caught low shows its normal level
  as its elevation (Lynchburg Reservoir 1,029 ft, not the 1,014 ft of that day).
- **Lidar dates** are each survey's span ("2017-04 to 2018-05"): VA_West_Chesapeake_B1_2017 flew for 13 months, so
  no single month says when a lake was seen.
- **Names.** Where NHD has none, OpenStreetMap's, if one named outline and the lake cover half of each other and no
  lake within 2 km has the name; not a name ending in "Dam" (the dam's). 166 lakes across the six areas, e.g.
  Stonehouse Lake and Mill Creek Reservoir (Virginia DWR's own page; its GIS layer says "Mill Reservoir", so that
  layer isn't used for names). The popup says "name from OpenStreetMap".
- **Checked on imagery** (Esri World Imagery, outlines drawn over it): the "largely dry, marsh or overgrown" lakes in
  Lexington, North Georgia and LA are forest, field, marsh or bare basins; the drawn-down reservoirs (San Gabriel,
  Cogswell, Big Tujunga, Gypsum Pond) show low water or exposed beds. LA keeps its debris, percolation and flood
  control basins: their names say what they are, and a name rule would also drop Hansen Flood Control Basin, which
  held level water.
- **Fish records.** A stocking or survey record attaches to a lake by name (within 2 km, word order aside), or by position (150 m) only if it is a lake record: CT DEEP's stream electrofishing at pond inlets and outlets had given 44 Connecticut ponds fish records that were the streams' (trout lakes there 44 -> 24), Vermont's White River stocking had shown on Sunset Lake, Georgia's Blue Ridge tailwater stocking on a 5 ha pool of the Toccoa. A lake record inside an unnamed lake names it (Yucaipa Lake, CDFW).
- **Smaller fixes.** One shared table of trout-family names (popups showed "Salmo salar", "Oncorhynchus
  virginalis"); `regulated` written as true/false (it was text, and "False" reads true); a contour click opens its
  lake's popup in the 2D and 3D maps.
- **Walking.** Lakes are impassable off trails, as in the Jackson pilot. Vermont: 274 reaches quicker, none 5+ min slower. Connecticut: 482 quicker, none 5+ min slower. Lexington: 50 quicker, 2 slower by 5 and 9 min beside a pond. North Georgia: 782 quicker (median 7 min), 4 reaches and 3 drops 5+ min slower (at most 24). LA: 462 quicker (median 12 min); 22 reaches and 29 drops 5+ min slower, up to 3 h, every one beside Castaic, Pyramid or Morris (water) or San Gabriel, Big Tujunga or Cogswell (caught low but normally full): the old routes walked on the water, and boats aren't modelled. Dry debris and flood-control basins are barriers too; one reach is 12 min slower for it.
- **Coordination.** The imperial-units session converted the popups and notes while this ran; the flow session
  for reaches below lakes reran `05b_flow` in North Georgia, LA, Connecticut and Vermont before this session's
  `06_map`, so one publish carries both (the session for flows across box edges reran nothing). Published per area: Vermont f674be0, 449abcd, 38ef337; Lexington aa7035d; Connecticut 96b604b, a742b5c, c9c8f60; North Georgia bf15161; LA 7caab8b, 97e45b8; Lexington again 5c8845e (Jackson by the Wyoming session, 3c421fe). streams/ is 858 MB of GitHub Pages' 1 GB limit after these (848 before North Georgia and LA).


## 2026-11-20, after midnight: scaled flows follow creeks across box edges (measured here; installed and published the next morning, below; another session)
Task from the Wyoming session. 05b's "scaled" flow (a reach off the NHDPlus model network takes the unit-area flow
of the first modelled segment downstream) searched only the reach's own box. A creek whose way left its box over an
edge shared with another box got flow_src "none" ("no data"), and the fish score's water term fell to NHD's class
(often "unmapped", 0.15). Jackson: 9.9 % of the reaches within 1.5 km of a shared edge read "no data", 2.5 % overall.
On the rendered map the creeks above Deadman's Bar (jackson_lake, just above its edge with teton_snake at
y 4,842 km) read "NHD unmapped", fish 8-11, and turn blue right past the edge: the same creek there
(teton_snake:s14) reads year-round, 1.22 cfs, fish 65.

**Cause.** 03b_stitch routes an area's boxes as one surface: a line that leaves its box ends on the first cell of the
next box, where that box's line for the same creek starts. But each box's reaches and 05b's D8 walk end at the
box's rim, so the search for a modelled reach below stopped there.

**Change (`05b_flow.py` only, on top of the lake-line fix, sha1 7399164; in scratch, not installed):**
- The D8 walk is a small class (`Walk`), run one reach at a time. For the box itself it gives exactly the old walk:
  the next reach of every reach is identical in all 55 boxes. It no longer reads area_km2.tif or builds full-grid
  pointer arrays.
- A creek with no segment in its own box by either drainage area (its box's own, or with the water from other
  boxes) is followed into the box it runs into. The way leaves its box at the line's last vertex, where the line
  runs on into the next box; else at the rim cell where its walk stops: a direction pointing off the grid, or a pit
  or flat on the rim, which steps straight out as in crossbox.exit_points.
- In the next box the way runs to the first reach it meets, then on through that box's reaches as that box's own run
  walks them, to the first with a segment of its own. Limits: 60 reaches per box, 4 boxes, loops stopped. Each reach
  is settled once: the first version walked the same chains once per creek and took up to 18 min in a Smokies box;
  now 2-3 s.
- The next box's reaches are matched with the areas its own run uses: with the water from other boxes, from its
  area_streams.csv when that lists its current reaches (the test scoring.attach makes), else its own box's areas,
  with a NOTE. This matters. On box areas alone, the Snake below Jackson Lake (698 km2 in teton_snake's own routing,
  3,986 on NHDPlus) took the Hoback River's segment, and the Snake below Palisades Dam took Palisades Creek's. That
  is 28 Jackson reaches, 11 each in adk_high_peaks and adk_northwest, 2 each in lexington_va and adk_southeast.
- A reach with a segment in its own box by either area keeps the result it always had. In the first version the keep
  rule could prefer the other area's segment, found far down another box: 7 Jackson reaches, e.g. teton_snake:s483
  0.11 -> 0.49 cfs from the Hoback box.
- A segment found in another box may raise a creek's water estimate, never lower it below NHD's class (what the map
  had). This follows the keep rule's reasoning: a side creek inheriting a segment further down is no evidence that it
  dries, and possible trout water stays in. Without this rule 9 scores fell by 10+:
  - ne_ct: Smith Brook 59 -> 45 and Skinner Brook 58 -> 37 (both trout water, perennial on NHD, "usually flows"
    scaled from the Little River); Cedar Swamp Brook 45 -> 32;
  - central_vt: two 1 km2 creeks in stowe_lamoille, 53 -> 34 and 42 -> 27;
  - LA: Encino Creek 43 -> 5 (perennial on NHD; mostly dry, scaled from the LA River's natural flow in the San
    Gabriel box).
  78 reaches keep NHD's class this way: LA 61, ne_ct 8, central_vt 6, lexington_va 2, adk_high_peaks 1.

**Measured on all 12 areas.** The current 05b and the new one ran in every box on the same inputs, writing only to
scratch. Fish scores came from scoring.score() on each area's stream_reaches_ranked.csv with only the flow columns
swapped. The current 05b's run reproduces every published score where its flow columns equal the published ones
(0 differ in 105,747 reaches). adk_northwest was measured on its 00:30 rebuild (the 03b lake fix).

| Map | Reaches | No data -> scaled | Class changes | Keep NHD's class | Fish +10 or more | Fish -10 or more | No data within 1.5 km of a shared edge | No data, all reaches |
|---|---|---|---|---|---|---|---|---|
| jackson | 10,530 | 185 | 185 | 0 | 122 | 0 | 9.9 % -> 0.0 % | 2.5 % -> 0.8 % |
| la | 17,857 | 34 | 34 | 61 | 3 | 0 | 12.1 % -> 9.5 % | 7.9 % -> 7.7 % |
| n_georgia | 15,045 | 9 | 9 | 0 | 0 | 0 | 1.6 % -> 0.0 % | 0.3 % -> 0.2 % |
| central_vt | 7,632 | 56 | 54 | 6 | 3 | 0 | 11.3 % -> 2.7 % | 2.4 % -> 1.7 % |
| ne_ct | 3,436 | 4 | 4 | 8 | 3 | 0 | 7.1 % -> 5.5 % | 2.0 % -> 1.9 % |
| lexington_va | 4,287 | 3 | 3 | 2 | 0 | 0 | 2.7 % -> 1.7 % | 1.4 % -> 1.4 % |
| se_pa | 4,623 | 2 | 2 | 0 | 1 | 0 | 0.9 % -> 0.0 % | 2.1 % -> 2.1 % |
| smokies | 9,000 | 23 | 18 | 0 | 0 | 0 | 1.9 % -> 0.3 % | 0.4 % -> 0.2 % |
| adk_high_peaks | 9,688 | 124 | 118 | 1 | 52 | 0 | 10.8 % -> 1.5 % | 3.6 % -> 2.3 % |
| adk_northwest | 8,276 | 80 | 68 | 0 | 31 | 0 | 6.2 % -> 1.1 % | 1.8 % -> 1.0 % |
| adk_southeast | 8,557 | 35 | 31 | 0 | 14 | 0 | 7.2 % -> 2.9 % | 2.6 % -> 2.2 % |
| adk_southwest | 6,816 | 14 | 14 | 0 | 9 | 0 | 3.6 % -> 1.1 % | 1.0 % -> 0.8 % |
| all | 105,747 | 569 | 540 | 78 | 238 | 0 | | |

- Nothing else moves. No reach changes source except "none" -> "scaled", and no score goes down. The 29 that change
  source but not class lie in lakes and stay "reservoir".
- New classes: year-round nearly everywhere; "mostly dry" in LA (ephemeral on NHD); a few "usually flows" or
  "seasonal" in ne_ct and central_vt (intermittent or unmapped on NHD).
- Median rise where scores move: 41-45 in Jackson and the Adirondacks, 20-28 in Vermont and Connecticut, 3 in LA.
- Still "no data" near edges, as they should be:
  - creeks leaving the map over its outer edge near a corner (sierra_pelona 21, piru 10);
  - creeks that run into the next box but have no modelled reach below them there either, so they read "no data"
    in that box too (piru -> sierra_pelona 17, champlain -> boquet 10, mad_winooski -> stowe_lamoille 4);
  - in LA, most of the rest are the reaches kept at NHD's class by the rule above.

**Checked.**
- Traces (the way into the next box, the first reach met there, the segment taken):
  - the Deadman's Bar creeks enter teton_snake at y 4,842 km and reach the Snake 4 reaches on (segment 23123161,
    3,986 km2, 66 m from that reach's midpoint): 0.17-1.22 cfs, fish 8-11 -> 54-72 (the brief's ~65);
  - Glacier Gulch -> Cottonwood Creek;
  - saranac:s79 -> the same creek in wilmington (Grass Pond Outlet), fish 14 -> 92;
  - tupper:s59 -> the Jordan River in st_regis; tupper:s810 -> the Raquette (1,855 km2) in long_lake;
  - Monty Brook -> the Little River in quinebaug; Elizabeth Lake Canyon -> itself in the piru box.
- On the rendered maps (local server, the builds before this change), the seam is where the counts put it:
  - Jackson above Deadman's Bar: jackson_lake:s2210 "NHD unmapped", fish 11, now 1.22 cfs, the same as its
    continuation past the edge;
  - adk_high_peaks south of Grass Pond: saranac reaches at fish 12-14 next to wilmington's 79-100, now 81-92.

**Not installed; nothing rebuilt or published.** scripts/05b_flow.py is unchanged (sha1 7399164), so no session's
05b run picks the change up before the user's OK. After the OK:
1. Apply the change on top of the 05b on disk, with the patch script.
2. Update README's 05b paragraph.
3. Run 05b for every box (no 05c needed), then 06_map and 12_profiles per area.
4. Publish.
The new file, the patch script, the diff and the summary are in the side-session notes folder.

**Open:**
- Run order. run_mid.sh, run_drainage_refresh.sh and run_la_refresh.sh run 05c and 05b box by box. With this
  change, a box's 05b can read a neighbour's area_streams.csv before that box's 05c has rerun. Where the neighbour's
  reaches changed (a 03b rebuild), 05b falls back to box areas for that neighbour and prints a NOTE. Running 05c for
  every box before any 05b avoids this. run_mid.sh is the lakes session's file; to be agreed with it.
- 05b maps a reach's vertices to cells by truncation, though the vertices are cell corners (+-3e-10 m after the
  round trip through EPSG:4326). About half of them land one column or row off. The walk still finds its reaches (the
  same before and after this change), and rounding would be exact. Not changed: it would move own-box results.
  Worth measuring separately.


## 2026-11-20, morning: cross-box scaled flows installed; all 12 maps rebuilt and published (another session)
**User: "Yes, install and rebuild"** (the question asked about installing, rebuilding and publishing all 12 maps).

- **Installed.** `05b_flow.py` was patched on top of the file on disk (sha1 7399164) and replaced in one move. The
  result, sha1 a093ae9, is byte-identical to the file measured above.
- **README.** The 05b paragraph now says that creeks with no segment in their own box follow their way into the next
  box, that 05c must run for every box before 05b, and that a segment found across an edge never lowers a creek
  below NHD's class.
- **05b in all 55 boxes** (10:2x). The 110 flow tables (streams and drops) are byte-identical to the measured runs.
  The run's own counts sum to 569 reaches scaled from another box, as measured.
- **06_map and 12_profiles for all 12 areas** (10:26-10:35, no failures). Each area's new stream_reaches_ranked.csv
  was compared with a snapshot taken just before the render. Only the measured reaches changed, by the measured
  amounts: flow source on the same 569 reaches, fish score on the same 252, of which 238 rose by 10+ and none fell.
  area_rank_pct shifts with them (2,991 reaches in Jackson, 1,417 in adk_high_peaks, 0 in n_georgia, lexington_va
  and the Smokies).
- **Checked on the rendered maps** (local server, no console errors):
  - Jackson above Deadman's Bar: the creek just above the jackson_lake/teton_snake edge (jackson_lake:s2210) has
    the popup "year-round · low flow about 1.2 cfs in a typical July–October, 0.98 cfs in a drought year · kept
    flowing 100% of summers since 2011 (… scaled from the creek below) · NHD: unmapped", fish 72 (was "NHD
    unmapped", 11). The five creeks above it read year-round, fish 54-64 (were 8-10). The gray seam at the edge is
    gone.
  - adk_high_peaks south of Grass Pond: saranac:s78-80 read year-round, fish 81-92 (were 12-14).
- **13_overview, 14_portable and phone_sync rerun.** stream_maps_all.html is 53.1 MB; phone/ is 893 MB.
- **Published.** Site commit 80562eb, on top of 9363c92 (the 03b session's adk_northwest). The copy step was done by
  hand with publish_site.sh's guards, so the commit could say what changed. It holds 37 files: each area's
  stream_map.html, map3d_data.js and profiles_data.js, plus streams/index.html. Nothing outside streams/ changed;
  streams/ stays 859 MB, and the site repository's packed history was about 300 MB before this push. Live in about
  90 s; all 37 live files match the build by SHA-256.

**Not done:**
- **Run order.** Splitting the 05c/05b loop in run_mid.sh and run_drainage_refresh.sh (05c for every range, then 05b
  for every range) was refused by the permission check; run_mid.sh is the lakes session's file. Until it is split,
  a box's 05b that reads a neighbour's area_streams.csv written for other reaches (after a 03b rebuild) matches that
  neighbour on its own box's areas and prints a NOTE; rerunning that box's 05b after the neighbour's 05c fixes it.
  This rebuild ran only 05b, on tables that all listed their current reaches (no NOTE in any box).
- **Vertex-to-cell truncation** in 05b (see the entry above): unchanged.

## 2026-11-20, late morning: the open items from the overnight sessions (this session)
Task from the "Today's task overview" session: the six open items in its brief (run order, ponds, adk_northwest
leftovers, lakes for six maps, Teton Valley water temperature, smaller ones). Proposed order sent to the user: 1, 2,
3, 6, then 4 and 5. Work in progress; this entry is updated as items finish.

**Done so far:**
- **Run order (item 1).** `run_mid.sh`, `run_drainage_refresh.sh` and `run_la_refresh.sh` now run 05c for every range,
  then 05b for every range. The lakes session agreed for `run_mid.sh` (its 05d_lakes / lake_bathymetry block stays
  after both loops). README's manual LA command and the note on re-running a range's 05_score updated (rerun 05b of
  the ranges whose creeks run on into it too). Dry run of the drivers with a stand-in Python: the order is as meant.
  The cross-box session's own attempt at this edit had been refused by the permission check in that session; this
  session made it as part of its brief, and has told the user.
- **Bull Sluice Lake's tailwater (item 6a).** `scoring._TAILWATERS`: Bull Sluice Lake's line 265 -> 250 m. Its lake
  lies at 260 m on the DEM and the river below Morgan Falls Dam starts at 242 m, so at 265 m the reach of the lake's
  stretch lying outside its outline (hooch_tailwater:s1492) took Bull Sluice's tailwater. Checked on the tables: it is
  the only reach between 250 and 265 m with no dam flag; it now reads Lake Sidney Lanier's tailwater; 0 fish scores
  change (a tailwater's thermal and heat terms are the same whichever dam). n_georgia's 06_map waits for the next
  rebuild there.
- **Sudden-flow-drop check (item 6b): `data/check_flow_drops.py`**, a standing check in the repo instead of scratch
  scripts. It divides a reach's flow by the area 05b scales with (area_edge in LA, area_full elsewhere), compares a
  reach only with the reach above it that it continues (the inflow with the most drainage, at least half of this
  reach's) and the reach below it that it feeds at least half of, both flowing (0.1+ cfs), and follows a creek into
  the next box as 05b does. Planted drops (a reach's flow at 2 % of its own) on 15 random judgeable reaches in each of
  se_pa and lexington_va: 15 of 15 found. On the current builds: 0 in Jackson (the old check's 48), 1 in LA (the old
  ~1,000; sespe:s2237, 0.0 cfs between two reaches of 0.06, below the flowing floor once that was added: now 0), 0 in
  n_georgia, se_pa and lexington_va. brandywine:s2587 (0.48 cfs on 23.5 km2 below Little Mill Creek's 4.47) can't be
  judged: walked from its true end cell its way stops on the Christina River's tidal flats. 05b's truncated walk
  found a reach below it there (see the rounding measurement, item 6c).

**The package (items 2, 5, 6c and two findings), measured, installed at the user's "yes, go ahead" (12:05),
rebuilt 12:08-12:24.** Measured first on all 12 areas with a scratch harness that runs the real 05c / 05b source per
box with outputs redirected (its baseline reproduced every project table byte for byte and every published fish score).
Installed by a script that patches the files exactly as measured (`crossbox.py`, `flowlib.py`, `05b_flow.py`,
`05c_drainages.py`, `watertemp.py`); README updated.
- **Ponds (item 2), `crossbox._dam_links`.** Where NHDPlus has no line in a lake, or its lines find no way on, the
  box's detailed NHD stream line leaving the lake gives the cell below its outlet (`_pond_outflow`, the walk 05c's
  `pond_links` did for names only). 293 lakes and ponds over the 12 areas, Lake Placid among them (its dead end had no
  link: Outlet Brook below it read 3-4.5 km2, now 54-56, fish 57-66 -> 82-88). Links of kind "pond" carry the reaches'
  areas (`area_full_km2`); the "edge" totals (LA's flows) don't take them. crossbox VERSION 16; its cache key now
  includes each box's `nhd_flowlines.gpkg`. 7,751 of 105,747 reaches gain drainage (median +3 km2), none lose any. The
  Soquee at the Chattahoochee 390 -> 414 km2 (NHDPlus 413.97).
- **Drainage labels kept.** On the new areas the bigger-arm rule made the Soquee the Chattahoochee's trunk (the upper
  Chattahoochee became a fork "Chickamauga Creek"), Tesnatee Creek the Chestatee's, and relabelled 1,590 reaches. So
  05c picks forks, promoted tributaries and drainage names on the area without the pond links (crossbox's
  `full_dams` totals, `inflows(..., ponds=False)`): 0 labels change. A name rule from reach names was tried and
  rejected (reach names near confluences come from a nearest-line vote; it broke the Chestatee and the Chattooga /
  Tugaloo as it fixed the Conasauga and Piru Creek). Trunk naming by NHDPlus's main path is the follow-up (below).
- **Tie-break, `flowlib.match_points`.** Two NHDPlus lines at the same distance (a point nearest their shared node)
  in the same drainage bucket went whichever way an unstable sort left them, which depended on every other point
  (4 of 2,500 matches in one box changed with the points' order; Stevenson Brook and the Little River at Waterbury
  Reservoir flipped in a run that changed neither). Now the closer drainage, then the lower comid. 4 reaches move.
- **05b's walk (item 6c).** Vertices are rounded to their cell (truncation put about half one row or column off), and
  a walk that reaches a lake's dead end goes on from the cell below its outlet (crossbox's links), as the water does.
  Rounding alone was worse: the exact walk stopped in lakes that truncation had slipped past by accident (LA's upper
  Temescal Wash, dozens of Adirondack brooks above Lake Placid and other ponds to "no data").
- **Guard.** A segment found down a way that went through a lake may raise a creek's water estimate, never lower it
  below NHD's class, as for one found in another box (Partridge Brook and three more Connecticut brooks above ponds
  would have dropped 15-27 points). Cost: about 30 LA washes that inherit "mostly dry" through a lake keep NHD's class
  (upper Temescal Wash 5 -> 47).
- **Weighted water-temperature fit (item 5), `watertemp.py`.** Each site weighted 1/(tau^2 + sigma_w^2/n) (sigma_w the
  robust spread of single readings around their site's median, 1.3-3.9 C; tau^2 the first fit's residual variance less
  the mean sampling variance); weighted skill test and area mean. Jackson's fit has skill now (0.887 of the spread
  against 0.906): every Jackson reach carries an estimate, no Jackson score changes (all under 20 C). Elsewhere at most
  +-2 points. adk_high_peaks, adk_northwest, adk_southwest still have no skill. It doesn't separate Teton Valley's
  floor creeks from its canyons: elevation and drainage size can't see a valley floor warming.

**Effect, all 12 areas against the build before** (the package without the weighted fit: 1,364 fish scores up, 243 by
10+; 145 down, 8 by 10+; 311 flow classes change; with the fit's +-1-2: 2,833 up, 1,742 down). The 8 drops of 10+: five
reaches lying mostly inside a lake now read reservoir (Northwest Bay Brook, 95 % in Lake George, 86 -> 26; Grass Pond
Outlet; Stevenson Brook, 52 % in Waterbury Reservoir; the Little River, 55 % in Hanover Reservoir; hooch_tailwater:s2084);
two tidal reaches on the Christina River (brandywine:s2587, s2562) whose flow came only from truncation's slip; one tie
(Grass Valley Creek 50 -> 38). The big rises: brooks below ponds (Norwichtown Brook 1.3 -> 4.5 km2, seasonal ->
year-round, 26 -> 66), creeks that now find the river below their lake (Taggart Creek "no data" -> year-round, 15 ->
100), LA washes kept at NHD's class by the guard.

**Checked after the rebuild, all 12 areas:** every box's area_streams, stream_drainage, flow_streams and flow_drops
byte-identical to the measured run; every fit equal to the measured weighted fit; every fish score equal to an
independent recompute (the pre-rebuild table with the new flow, area and fit columns); 0 drainage or fork labels
changed; `check_flow_drops.py` 0 in every area. On the rendered maps (local server, no console errors): Taggart Creek
year-round 100; Norwichtown Brook 4.45 km2 year-round 66; Partridge Brook "NHD perennial" 60; Outlet Brook 54-56 km2,
order 4, 82-88; the Soquee 412-414 km2 with the upper Chattahoochee still the trunk; hooch_tailwater:s1492 "tailwater
below Lake Sidney Lanier". Creeks drawn through below dams and ponds: ne_ct 115 -> 150 breaks (73 -> 101 km of line),
adk_high_peaks 155 -> 195, adk_southeast 217 -> 282, LA 59 -> 67. 14_portable and phone_sync rerun (12:25).

**Published** in site commit `3303d03` (about 12:50), together with the site-size session's layout change (one
shared data file per map, outlines at 6 decimals), as agreed with it: one full push instead of two. That session reran
06_map on these tables (12:27-12:33) and checked its output against them; this session then checked its reaches on
the new layout (map3d_data.js; the n_georgia map in the browser, no console errors) and published.
- publish_site.sh's copy and guards were run by hand. Its busy test matched the lakes session's scratch-only 05d
  check builds: they write `LAKES_OUT` in that session's scratch; neither `output/` nor the live lakes.gpkg was touched.
- 49 files changed: index.html and four files for each of the 12 areas (stream_map.html, stream_map_3d.html,
  map3d_data.js, profiles_data.js). Nothing was added or removed, and nothing outside `streams/` changed.
  `streams/` is 577 MB in 117 files.
- 14_portable and phone_sync were rerun by the site-size session at about 12:40, with its patched scripts.
- Live by 12:44. 16 served files match the push by SHA-256: index.html, all 12 stream_map.html, and one each of
  map3d_data.js (ne_ct), profiles_data.js (n_georgia) and stream_map_3d.html (adk_high_peaks). The site-size session
  checks the rest and the repository's history size.

**Next (the user's "and the others"):** lakes for se_pa, the Smokies and the four Adirondack maps run in their own
session ("Lakes for SE Pennsylvania, the Smokies and the Adirondacks"); trunk naming by NHDPlus's main path (levelpathi,
fetched; a prototype on LA swaps 5 confluences: upper Piru Creek and Holcomb Creek right, the San Gabriel's East Fork
in conflict with FORK_FIX, one at the Whitewater to look at); the 429 reaches lying at least half in a lake that score
as creeks (most in lakes the routing treats as holding water: String Lake 100, Jackson Lake 73-76); burning NHD streams
into the DEM for side channels and basins routed into the wrong valley (826 named reaches with under a quarter of
their NHDPlus line's drainage).

## 2026-11-20, midday: website size and phone copies (this session)
Task from the "Today's task overview" session. Full numbers:
`~/Library/Application Support/Claude/side-session-notes/local_e3cdfffb-0b65-41f5-9ffa-1ded44d9d362/site-size.md`.
- **Published site:** `streams/` is 891 MB against GitHub Pages' 1 GB limit per site.
  - Shares: `stream_map.html` 440 MB, `map3d_data.js` 341 MB, `profiles_data.js` 68 MB, hillshades 40 MB.
  - 231 MB of the 2D pages is data that is also, value for value, in `map3d_data.js`: STREAMS through PARKING.
  - The land-status and trout-water outlines carry 15 decimals.
  - LA's `stream_map.html` is 69 MB; GitHub refuses files over 100 MB.
- **History is not near 1 GB.** GitHub reports 397 MiB; a local repack gives 294 MB. The 1.4 GB local `.git` is
  loose objects.
- **Full republishes push big packs.** A full 12-area republish pushes 134 MB, because git's thin pack finds the
  previous version of only one file per file name. All areas share the names, so the other 11 go whole. Diffed per
  area, the 80562eb publish is 5.2 MB. A one-area publish pushes 0.1–0.4 MB.
- **Done, user's choice "Shared file + rounding" (12:00):**
  - **Change.** In `06_map.py`, the 2D page no longer inlines `window.STREAMS` … `PARKING`. It loads
    `map3d_data.js` and a one-line script points the same globals at `window.MAP3D`'s entries (`SHARED_3D`).
    - `map3d_data.js` holds only those 11 shared layers.
    - The layers only the 3D map draws are written inline into `stream_map_3d.html`, after its
      `<script src="map3d_data.js">`, as `Object.assign(window.MAP3D, {...})`. They are escaped so nothing in them
      can close the `<script>`.
    - New `r6()`: road closures, closure areas, fire perimeters, wild trout waters, critical habitat, wilderness,
      non-FS land and PAD-US outlines are written at 6 decimals instead of 15.
    - `14_portable.py` reads the 3D-only part from `stream_map_3d.html` too; old-layout areas still work.
    - Only the `map3d.html` header comment and the README file table changed besides.
    - The published file names are the same, so `publish_site.sh` and `phone_sync.sh` are untouched.
  - **Combined with the open-items session's flow/drainage refresh: one rebuild, one push.**
    - Its 12 areas were snapshotted at 12:24 (old layout).
    - The patch went in, then 06_map ran for all 12 from 12:27 to 12:33 (`data/sitesize_06map.log`).
  - **Checks:**
    - Lexington A/B: old and new `06_map.py` on identical inputs.
    - All 12 areas against the snapshot: the shared layers are identical to the old 2D inline data and to the old
      `map3d_data.js`. The 3D-only layers are identical except the outlines' coordinates (np.round, 6 places). The
      2D page outside the data is identical once folium ids are normalised.
    - Browser, all 12 areas, every overlay on, zooms 10/13/16: the same data hashes, overlay lists and layer
      counts. Only 0–416 edge pixels per view differ, from the rounding.
    - 3D pages assemble the same MAP3D, with no console errors. The MapLibre map can't draw in the hidden preview
      pane, for the old pages too; to check live in Chrome.
    - The three map files went from 785.0 to 485.8 MB.
    - `14_portable` was rerun: the one-file map is identical to the 12:25 one except the rounded closure lines.
    - `phone_sync` was rerun: `phone/` 893 → 639 MB, equal to `output/`.
  - **Handed to the open-items session to check its content and publish once (12:42).**
  - **Published: site commit `3303d03`, together with that session's flow/drainage package.** It was pushed at
    12:43 and the Pages deployment finished at 12:44.
    - `streams/` is 117 files and 604.5 MB, down from 891 MB. By file: map3d_data.js 215.5, stream_map.html 175.9,
      stream_map_3d.html 94.4, profiles_data.js 68.4, hillshades 40.0, index.html 9.6 MB.
    - The push pack was 84.6 MB, against 134 MB for the previous full republish. GitHub now reports 457 MiB of history.
  - **Live check:**
    - Nothing outside `streams/` changed. The older site is byte-identical to `cbbb0b8` (2020).
    - All 49 changed files and all 31 served older-site files match the commit by SHA-256. `.gitignore` isn't
      served by Pages, as before.
    - In Chrome, the live Lexington 2D and 3D maps and the LA 2D map load the shared file with no console errors.
      The 3D style has its 91 layers. LA 2D is 2.7 + 6.3 MB gzipped over the wire.
  - **Still open:**
    - A full republish still pushes about 85 MB: git's thin pack finds the previous version of only one file per name.
      Pushing area by area, through a temporary branch so Pages builds once, would cut that to a few MB. This needs a
      `publish_site.sh` change and the user's OK.
    - `git gc` in the site clone would free about 1.2 GB of local disk (local only).
  - **For anyone parsing the maps:** `window.STREAMS` is now in `map3d_data.js` (`D["streams"]`, and so on). The
    3D-only layers are the JSON after `Object.assign(window.MAP3D, ` in `stream_map_3d.html`.
- **Phone copies:** current. The flow session reran `phone_sync` at 10:37 after its publish. Every `phone/` file
  matches the live site by hash, and `output/stream_maps_all.html` holds all 12 areas. `phone/stream_maps_all.html`
  was a stale 6-area copy from 11-18; it was replaced with the current file.
- **One metric leftover on the maps:** LA's Little Rock Reservoir depth note, "222,765 m² of 1 m grid", from
  `lake_bathymetry.py:186`.

## 2026-11-20, early afternoon: the last metric note, and the consent emails (overview session)
- LA's Little Rock Reservoir depth note now reads "55 acres surveyed on a 3.3 ft grid; depth below the lake's lidar
  water level (3,273 ft NAVD88)" instead of "222,765 m² of 1 m grid; ..." (`lake_bathymetry.py`, `usgs_little_rock`,
  which now imports `acres` from `units.py`). The live LA maps and `phone/la` keep the old text until LA's lakes (05d)
  and map (06) are rebuilt and published; the "Lakes for SE Pennsylvania, the Smokies and the Adirondacks" session was
  asked to check the note after its LA rebuild.
- The user sent both consent emails (nnywaterfalls.com, World Waterfall Database) on 2026-11-20; replies awaited. If
  either says no, pull its rows by `source` everywhere (see the known-falls entries above).
