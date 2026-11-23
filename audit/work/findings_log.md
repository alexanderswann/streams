# Audit working log (running notes; the report is audit/AUDIT_2026-11-22.md)

Site measured: clone at 6875118 (clean), extracted to scratchpad `site_6875118/`. Six areas' reach tables that
match that commit by checksum were snapshotted before the rebuild overwrote them: scratchpad `snap_live/`
(adk_high_peaks, adk_northwest, adk_southeast, adk_southwest, n_georgia, smokies).
Scratchpad: /private/tmp/claude-501/-Users-mac-Fishing/b1190042-de6e-4861-932a-f7b59d4a72e3/scratchpad

## User instruction received mid-audit (2026-11-21 ~23:10)
"i want all of this code to be as generalizable as possible i want to be able to tell you a new location and it just
works, i dont want to have to make a bunch of one off fixes every single time we look at a new area" -> audit gets a
generalizability section; memory saved (feedback-new-area-just-works.md).

## P1 Provenance
- Live site 6875118 pushed 22:18. Builds: jackson 03b 19:30 (before dd639bf was committed 19:50), mid+late 20:13
  (before 80b42e8 at 20:26); the other 11 areas 20:45-22:04 with 03b (SKIP_03). 40c2aa7 (22:28) changed no script.
  So consistent with 80b42e8 code, but nothing in the outputs records the commit: cannot be proven.
- All 12 published map3d_data.js have the same property keys and popup templates (one 06_map version).
- THE REBUILD NOW RUNNING (started 22:31): scripts were edited while it ran. 15 scripts written 22:31:33 (batch),
  05_score.py 22:41:44, map_drainages.js 22:44:35, 06_map.py 22:57:17 (uncommitted, 50 lines). d06b50b committed 22:46.
  provenance_steps.py at 23:07: la/jackson/central_vt 05_score ran before 05_score.py's last change; la, jackson,
  central_vt, ne_ct, lexington_va 06_map ran before 06_map.py's last change. Re-run before the report.
- No build stamp anywhere (no commit hash / dirty flag in outputs).

## A1 Streams vs NHD HR (tables/streams_vs_nhd*.csv), site 6875118
- Named NHD stream lines with a drawn line within 150 m: la 90, jackson 92, n_georgia 88, central_vt 89, ne_ct 87,
  lexington 90, se_pa 92, smokies 74, adk 92-93 %. The rest is under the 1 km2 floor (MAP_MIN_KM2, 05_score.py:12):
  smokies 25.7 % of 4,314 named mi (about 1,100 mi), n_georgia 12 %, ne_ct 13 %. "Routed 1 km2+ but not drawn" is ~0
  for named streams (only NY-side creeks of central_vt, clipped by design, and centrelines of edge-cut lakes / tidal
  water: Tugaloo 11 mi, Tellico 9.8, Darby 5, Delaware, Christina, Schuylkill tidal).
- Drawn line with NO NHD line of any kind within 150 m: la 10.6 % (1,006 mi), jackson 9.8 % (521), adk_high_peaks
  11.8 % (492), adk_sw 8.7, adk_se 7.8, se_pa 7.6, adk_nw 7.5, lexington 4.2, ne_ct 3.7, central_vt 3.0, n_georgia
  2.0, smokies 0.4. Of fish-60+ line: adk_high_peaks 6.6 % (197 mi), adk_nw 4.7 (134), adk_sw 4.6 (125), jackson 4.0
  (133), adk_se 3.1 (79); others <1.5 %. Nearly all order 1-2 (order 3+: about 1 %). Only a sliver is flagged
  'NHD unmapped' in the map (19 of 492 mi in adk_high_peaks): the rest shows a modelled 'year-round'.
- Course: drawn line sits a median 20-36 ft from NHD's line, 90 % within 60-140 ft.

## A2 Drainage area (tables/area_vs_*.csv)
- USGS gauges (site record's drainage area, independent): median ratio 0.97-1.02 in every area; within 10 %: la 81,
  jackson 84, n_georgia 76, central_vt 90, ne_ct 84, lexington 100, se_pa 86, smokies 97, adk_hp 89, adk_nw 75,
  adk_sw 54 (13 gauges, tiny research catchments), adk_se 94 %.
- Real misses (best line within reach still off, gauge >= 5 km2): Chattooga at Burrells Ford 0.63 (75.9 vs 121 km2),
  Suwanee Cr 0.66, Big Cr nr Cumming 0.56, Big Cr nr Alpharetta 0.79 (n_georgia); Green River at Garfield VT 0.65;
  French River at N Grosvenordale CT 0.41 (108 vs 262), Quinebaug at Putnam 0.79; NB Neshaminy 0.67, Valley Cr nr
  Downingtown 0.04 (se_pa); Independence River 0.74-0.76 (2 gauges), Sugar River 0.78 (adk_sw); LA: Santa Ana below
  Prado 0.43, LA River at Sepulveda 0.03, Warm Creek 3.5x. Cause in most: headwaters outside the map; crossbox.py
  carries an outside river only if it brings 10 km2+ AND 25 % of the NHDPlus total (crossbox.py:30, :451, :586).
- NHDPlus V2 lines of 100+ km2, best drawn line within reach under half: la 81 of 746, jackson 19, adk_se 19,
  ne_ct 12 (French River), n_georgia 10, se_pa 9, adk_sw 6, adk_nw 5, adk_hp 4, smokies 3, lexington 1, central_vt 0.
- The NEAREST drawn line to a big-river point is often a small side line beside the river: nearest under half at
  20 % of LA's 100+ km2 points, 14 % jackson, 12 % adk_se, 9 % ne_ct (tap on the river, read a 0.5 sq mi creek).

## Popup text defects seen while parsing (site 6875118)
- "hike -0 min" on 130 reaches; "(-0% shaded by terrain)" on 392.
- adk_high_peaks, adk_northwest, adk_southwest popups have no water temperature (fixed in d06b50b's lake term, unpublished).
- Flow class: share of drawn reaches reading 'summer: year-round': jackson 95.5 %, n_georgia 99.2, smokies 99.2,
  central_vt 95.8, adk 96 %; LA 20 %.

## Licence
- troutdata.py:490 NYDEC = services6.arcgis.com/DZHaqZm9cxOD4CWM (DEC's ArcGIS): trout stream reaches, (T)/(TS)
  classes -> popups on ~18k+ ADK reaches ("Trout water, NY class C(T) (NYSDEC)"), fish score evidence. geomatch.py:76
  NYS_DEC_Lands from the same org. Memory says DEC ArcGIS items forbid secondary distribution; the four ADK maps are
  hidden but still published at their addresses.

## A3 Summer flow (tables/flow_vs_gauges*.csv, flow_class_vs_nhd.csv, trout_found_shown_dry.csv), site 6875118
- How the figure is made outside LA: NHDPlus EROM mean monthly flow x a yearly index from the area's gauges
  (02b_download_flow.py:214-228), scaled by drainage. EROM has no drying in it, so every creek of 1 km2+ reads
  year-round: jackson 95.5 % of reaches, n_georgia 99.2, smokies 99.2, central_vt 95.8, adk 96 %. Water term mean
  0.97-1.00 outside LA (ne_ct 0.90): the term carries no information there.
- Against NHD's own label, by drawn miles rated year-round: jackson 2,700 mi perennial + 1,574 intermittent + 688 no
  NHD line (45 % not perennial in NHD); adk_high_peaks 631 + 633 of 4,011 (31 %); lexington 39 %; n_georgia 18.5 %;
  LA 422 intermittent + 227 EPHEMERAL + 97 unmapped of 1,452 (45 %).
- At gauges (5+ summers since 2011, same-size reach): class agrees at every gauge outside LA (all gauged creeks there
  are wet; in-sample). LA: 47 gauges, 81 % same class; 4 of 20 dry gauged creeks still shown usually flows /
  year-round; 1 of 27 wet ones shown dry: PIRU CREEK BELOW SANTA FELICIA DAM (USGS 11109800, 7.7 cfs typical, flows
  every summer): the first 0.87 mi below the dam (3 unnamed pieces, 1,094 km2, 34.4519,-118.7543) is drawn "mostly
  dry, 0.00 cfs, fish 3". Fixed in the local build of 23:00 (reads Piru Creek, year-round, fish 70), not yet live.
- "low flow about X cfs": within 2x of the gauge at 86-100 % of gauges outside LA except central_vt 68 % (small
  mountain creeks read 3x high: W Br Little River 19 vs 6.2 cfs, Ranch Brook 11 vs 3.1) and adk_hp 75 %; LA 46 %
  (28 gauges). Bypassed reaches below dams read the undiverted flow: Tallulah Gorge 277-281 vs 39 cfs, Cheoah 209 vs
  91, Granite Cr (Jackson) 38 vs 9. flowlib.DIVERSIONS lists LA only (flowlib.py:393-402).
- Trout found since 2016 on a reach the map shows as dry: LA 40 reaches mostly dry + 41 seasonal (53 mi; Arroyo
  Trabuco 33.6005,-117.6313, sightings 2023-26, "mostly dry, 0.0 cfs", fish 16-18); ne_ct 14 seasonal; none elsewhere.
- NHD perennial but map "mostly dry": LA 145 mi (Hot Springs Canyon Creek 6.6 mi, San Mateo Creek 4.8, Oso 4.3,
  Black Star 3.2...), jackson 28 mi.

## A4 Sudden changes along a creek (tables/drawn_jumps*.csv)
- Pairs of drawn pieces meeting end to end with the same drainage (within 20 %, 2 km2+) that differ by 2+ flow
  classes or 30+ fish points: LA 210 (93.5 mi on the low side), jackson 17, ne_ct 16, adk_hp 13, others 1-7.
  LA: the Santa Clara River flips seasonal 19-22 <-> year-round 55-61 some twenty times (bare-channel rule decided
  reach by reach); Bear Creek 43/100, Santa Ana River 34-46/84; Spread Creek (jackson) 35-40 vs 86-100 (burn x0.4).
- data/check_flow_drops.py reads the reach tables, so it never sees pieces 06_map.py adds (the Piru case).

## A5 Names, elevation, gradient, canopy, sun, access (tables/popup_checks_summary.csv, name_mismatches.csv)
- Names: where a reach follows one named NHD stream the name agrees on 99.6-99.9 % of miles; 0-4 mi differ and 0.4-6
  mi lack the name per area. LA: 585 mi (20 % of named miles) carry names NHD has no line for (canyon names, OSM).
- Elevation equals the DEM (median -0.5 ft, 95 % within 7-42 ft). Gradient within 0.5-1.3 points (90 %) of
  (top-bottom)/length; 2-12 % of reaches read 0.0 %.
- Canopy equals the canopy raster along the line (median difference 0-2 points). Sun: possible hours 14.2-15.1 by
  latitude, consistent. "(-0% shaded by terrain)" on 392 reaches.
- Access: no impossible values (median implied speed 34-51 mph, 95th pct <= 60; no drive shorter than the straight
  line). No drive time on LA 1.5 %, adk_sw 2.75 %, adk_hp 0.56, adk_nw 0.49 % of reaches. "hike -0 min" on 130.
  "hike 0 min" on 22-67 % of reaches (the creek is at the parking road). Drive and hike times themselves could not be
  checked: nothing independent in the project (needs a routing engine on an OSM extract, or a hand sample).

## A6 Falls and lakes (tables/falls_recall.csv, lakes_*.csv)
- Known waterfalls with a precise point that have a pipeline-found drop within 100 m: la 44 %, jackson 47, n_georgia
  45, central_vt 50, ne_ct 20, lexington 71, se_pa 0 (11 falls), smokies 60, adk_hp 76, adk_nw 55, adk_sw 50, adk_se
  49 %. They are still shown from the lists; the terrain method alone finds about half.
- Lakes layer: 7,450 lakes. Against NHD at each area's own smallest size: 85 NHD lakes missing in all (LA 30, se_pa
  16, central_vt 16 on the NY side, n_georgia 5 ...), mostly treatment / storage basins left out on purpose.
- Measured depth: 170 of 7,450 lakes (2.3 %): jackson 58, ne_ct 44, central_vt 18, n_georgia 9, adk 4-8 each, LA 6,
  se_pa 6, lexington 1, smokies 1. Fish records on 0.5-5.5 % of lakes.
- Smallest lake size is set by hand per area (05d_lakes.py:42 BUILT: 0.5, 1 or 2 ha).

## A7 Fish score (tables/fish_score_*.csv, trout_low_scores.csv, fish_score_vs_surveys.csv)
Tables: live 6875118 for n_georgia, smokies, adk x4 (snapshot); local build (22:58-23:03) for the other six.
- The table reproduces its own score: 99.6-100 % of reaches within 2 points (formula scoring.py:322).
- Spread: LA median 6 (8.9 % of miles 60+); other areas median 57-73, 38-74 % of miles 60+. At 100: jackson 7.3 %,
  adk_sw 4.3, adk_nw 4.2, smokies 3.4, others <= 2 %.
- Term means outside LA: water 0.97-1.00, gradient 0.94-0.97, thermal 0.78-0.89 -> those three barely vary; the
  score there is about 40 + 30 x size + 25 x remoteness, x1.2 with a trout record. Correlation with the score: size
  0.58-0.82, trout 0.29-0.67, remoteness 0.0-0.52, thermal 0.07-0.57, gradient -0.33..0.23.
- Rules that lower, reaches touched: no-trout sample x0.5: ne_ct 154 (117 of them inside a designated trout water or
  brook trout patch), smokies 57, LA 56. Burn: LA 3,886, jackson 141 (55 with trout records; Spread Creek, 70 sq mi,
  year-round cutthroat water, x0.4 -> fish 35), lexington 16, n_georgia 13. Heat gate: LA 507 (none with trout
  evidence). Built channel: LA 86, jackson 9, adk_se 7, se_pa 5. Bare channel: LA 545, jackson 69.
- No flow estimate -> NHD's class instead (unmapped 0.15, intermittent 0.35): 352 reaches outside LA (se_pa 80,
  adk_hp 71, jackson 58, lexington 41, adk_se 38 ...), scoring 8-20 beside neighbours at 60+; LA 1,456.
- Trout on record, score under 40 (lake reaches left out): LA 641 (380 "mostly dry" inside trout waters), ne_ct 400
  (272 small roadside brooks in brook trout patches, 106 halved by a no-trout sample), jackson 63, adk_hp 40,
  n_georgia 40, adk_se 26, central_vt 23, lexington 23, adk_sw 17, smokies 16, adk_nw 14, se_pa 2.
- Score (trout factor taken out) separating reaches where trout were found from reaches whose latest sample found
  none (AUC; 0.5 = no skill): LA 0.63 (766 vs 53), ne_ct 0.73 but 0.51 for wild trout (415 vs 133), smokies 0.93
  (1,623 vs 57; the no-trout samples sit on 1.2 sq mi creeks). Water term alone: LA 0.49.

## C1 Website size (site 6875118: 657.8 MB = 627 MiB of GitHub Pages' 1 GB; 60 commits; local clone .git 2.4 GiB loose)
- By file over the 12 areas: map3d_data.js 229.9 MB, stream_map.html 199.0, stream_map_3d.html 112.5,
  profiles_data.js 69.0, hillshade.png (55) 40.1, index.html 6.5. By area: la 90, n_georgia 78, smokies 61,
  central_vt 58, jackson 57, adk_se 56, adk_hp 52, adk_nw 47, ne_ct 44, se_pa 42, adk_sw 40, lexington 26.
- map3d_data.js by layer: streams 122.5 MB (geometry 37.4; popup sentences dq 24.0 + sun 23.6 + acc 13.7 = 61.3 MB),
  trails 36.9, roads 32.0, streams_lake 13.6, forks 7.4, divides 4.7. The three sentences hold about 8.7 MB of
  numbers: composing them in the page from numbers would save about 52 MB with nothing lost.
- stream_map.html (LA 21.2 MB): 5.6 MB inline GeoJSON (lakes 1.6, fires 1.0, CPAD 0.9, critical habitat 0.5 ...),
  5.5 MB of popup HTML strings, 9,929 circle markers each written out as its own JavaScript (drops, trailheads).
  stream_map_3d.html (LA 10.4 MB) holds the SAME layers again as data (drops 5.5, lakes 1.3, fires 0.9, CPAD 0.7 ...).
  So the 3D-only block (112.5 MB over 12 areas) repeats what the 2D page already carries in folium form: one shared
  data file for these layers, as was done for streams on 2026-11-20, would drop most of one copy (about 100 MB).
- profiles_data.js: distance arrays written out at every 40 m step ("km":[0.0,0.04,0.08,...]).
- gzip (what a phone downloads): LA map3d_data.js 43.1 -> 6.3 MB, stream_map.html 21.2 -> 2.6 MB. The 1 GB limit
  counts the raw bytes.
- Disk leftovers: data/backup_* 11 folders, 3.9 GB (folder copies from 11-18..11-20, ignored by git); publish/ 3.0 GB
  (its .git is 2.4 GiB of loose objects, `git gc` would bring it to about 0.3 GB); phone/ 678 MB; 200+ run logs in data/.

## STATE at 23:45 (2026-11-21)
- Rebuild finished 23:34; all 12 areas. Snapshot of the finished local build: scratchpad `snap_local/` (checksums.txt).
  Commit 8bdf945 (23:37) committed scripts/06_map.py (+50) and logged the rebuild. Site clone still 6875118.
- Provenance of that build: 05_score.py changed at 22:41:44 while LA / jackson / central_vt had already run it, but the
  change was a comment only (diff against the side-effects session's scratch copy rD/scripts/05_score.py). 06_map.py
  changed 22:57:17 (functional, +48 lines); the five areas drawn before it (jackson, central_vt, la, lexington_va,
  ne_ct) were redrawn by hand 22:58-23:04, outside the driver logs; 12_profiles was not rerun (profiles_data.js is
  older than stream_map.html in 11 of 12 areas; it reads stream_reaches_ranked.csv, which 06_map writes).
  So: same code for all 12 in substance, committed after the fact; nothing in the outputs proves it.
- All measurements re-run on the new build: audit/tables/build_2334/ (live: audit/tables/live_6875118/). The accuracy
  figures barely move between the two (named-stream cover, area ratios, flow classes at gauges the same; LA's wet
  gauged creek shown dry 1 -> 0; jumps 287 -> 269).
- audit/scripts/run_all.sh <label> <maps folder> [tables folder] runs the whole set in 4 minutes.

## A8 Table vs map (build_2334/table_vs_drawn.csv)
- Reach tables: 110,665 reaches, 56,033 mi, fish 60+ 26,697 mi. Drawn by default: 107,133 features, 50,526 mi, fish
  60+ 25,112 mi; lake layer 15,804 features, 6,279 mi. A figure from the tables is about 10 % long and 6 % high on
  fish 60+ against what the map shows.
- 06_map.py's own counts on the new builds (tables/map_rules_by_run.csv, summed over 12 areas): stream order raised
  on 9,122 reaches; 1,138 lines (220 km) drawn through breaks below dams and at the outer edge (956 km before the
  carried-water floor of 11-21); 15,160 reaches clipped at lake shores into 10,688 pieces (5,455 km outside lakes);
  8,614 reaches lying in lakes; 2,863 shore stubs dropped; 1,123 pieces re-valued as the river they continue;
  949 joins across dams of 1,438 cells (median 7-18 m); 28,497 unnamed drainage outlines joined, 6,915 placed.
  So the root fixes did NOT retire these rules: they still change tens of thousands of features in the drawing step.

## A9 The 1 km2 floor (MAP_MIN_KM2, 05_score.py:12; build_2334/trout_records_off_map.csv)
- Smokies: 317 of 1,739 named NHD streams not drawn at all, 937 lose half a mile or more of their head; n_georgia 85
  and 434; ne_ct 9 and 95; central_vt 9 and 140; jackson 6 and 132; lexington 7 and 98. The undrawn stretches drain
  0.25-1 km2 for about 55 % of their length, under 0.25 km2 for 45 %.
- Trout-found records (not lake records) on water the map does not draw: 98 of 2,880 (3.4 %), all under the floor:
  ne_ct 25 (22 CT DEEP surveys), smokies 15, central_vt 12, la 10, jackson 9, se_pa 9, n_georgia 8.

## C2 Code inventory (tables/code_*.csv)
- Word-match dead code: 1 unused constant (05d_lakes.py:878 GAME). Scripts are top-level code, so dead code is in
  branches, not names (agents' notes).
- Same helper in two files: overpass (02d_trails.py:61 = geomatch.py:10, identical), esri (11_context.py:46,
  geomatch.py:26), follow (02d_trails.py:160, geomatch.py:114), get (02b:42, 11_context:446), cached (02d:41,
  02f:59), walk (04_knickpoints:57, crossbox:192, flowpath:31), band (3 files), air_at (2).
- Ties to an area or place: 40 has(source) switches in 12 files (tnc_flows 9), 10 AREA switches, 44 table rows keyed
  by an area or box name: 02f STATES (12 areas; a new area gets no GNIS falls), 05d_lakes BUILT (12; a new area gets
  no lakes), lake_bathymetry ADAPTERS (6), lakesources (5 areas), lakedata (jackson, se_pa), scoring _TAILWATERS
  (la, n_georgia, smokies), flowlib _DIVERSIONS (la), 05c NAME_FIX (8 box+name entries) and FORK_FIX (4).
- Drivers: run_base (01 02 03 03b 02b 04 04b), run_mid (02f 02b 05d bathymetry 05_score 02g 05c 05b 02d 02e 02c),
  run_late (07 08 10 09 11 watertemp 06 12 diagram), run_rebuild_a (03 03b 04 04b + mid + late), run_drainage_refresh
  (05c 05b 06 12), run_la_refresh (LA one-off of 11-18, hard-coded ranges). 02b runs in both base and mid; the
  step()/run() helper is written out 4 times; base and rebuild_a carry on after a failed hydrology step.
- No FAILED line in the newest run of any area. LA's 05b NOTE: 2026 counts on 3 of 4 months (October not downloaded).

## L1 Licences (to finish with the sources agent)
- USGS WaterServices: no caller left (grep over scripts/, data/*.py, data/stream_burning). Hosts: api.waterdata.usgs.gov,
  api.water.usgs.gov.
- Credit line (06_map.py:37-40 + map_drainages.js:512): OSM (trails & PCT), USGS National Digital Trails, USFS, CDFW,
  iNaturalist, CAL FIRE / NIFC, WFIGS, USGS gauges & debris-flow hazard, CDEC, TNC Natural Flows / NHDPlus V2, PRISM,
  known falls: OSM, GNIS, Wikidata + guides with 50+ falls. Not in the line (named in popups only): state trout
  agencies, TU / EBTJV, PAD-US / CPAD, USFWS critical habitat, GBIF, EPA NLA, NOAA ENC, Sentinel-2, StreamNet, lidar.
- NY DEC ArcGIS (troutdata.py:490-527, geomatch.py:76): "NYSDEC" occurs 6-8 thousand times in each published ADK file.
- WWD 106 rows (central_vt, la, smokies shown; ADK hidden), nnywaterfalls 116 rows (ADK), gawaterfalls 695 rows
  (n_georgia; author never asked), ncwaterfalls 4, New England Waterfalls 36: no licence or forbidding terms.

## From the drawing/lakes agent (audit/work/code_map_lakes.md), spot-checked by me on the new build
- One root cause behind five patches: 03b ends a lake's paths in a pit at the outlet cell (03b:578) and starts the
  outflow line in the NEXT cell (03b:428): a one-cell gap (33-46 ft). Patched in 05_score.py:161-176, crossbox.py:335-392,
  06_map draw_through, 06_map dam joins 835-920, 06_map 785-807. Fix in 03b removes the need for all five.
- draw_through (06:106-283): 61 % of its actions redraw a reach that is already there (455 second lines 16-26 ft
  beside it, 239 one-point additions); edge branches dead (06:144-148, 158-176, 212-221, ~35 lines). Real work left:
  rivers entering from outside the map.
- 05_score cuts reaches only at lakes of 20 acres+ with level water and 165 ft on each side (flowlib.py:187, 199-207);
  06_map clips at every drawn lake (1.2-5 acres up): two lake sets, two tolerances -> rules A13-A16 in 06.
- Final fish score is computed inside 06_map (06:73 scoring.score); 12_profiles reads it from 06's export.
- Verified by me: H6 adk_southeast order scale collapsed (06:98-101): order 7 = 520 features, smallest 100 sq mi; order 6
  = 11 features, median 1.5 sq mi. H5 "CA State Parks" on 150 trail pieces in adk_southeast, 28 in adk_high_peaks
  (06:1071). H1 maplakes.py:253 tests "no level water", 05d:572 writes "little level water": dry-lake edge never drawn
  (0 of 7,450; 401 popups carry the note).
- Other bugs (agent, published counts): H3 "Outlet creek profile" link is #q=unnamed for 3,601 of 7,450 lakes; H2 major
  depth contours never bold in 3D / one-file map (261 flagged, 0 pass); H8 "trout stocked or recorded" from any GBIF
  Salmonidae record of any year (5 lakes whitefish/cisco only, 49 nothing since 2000); H10 soundings at other spots called
  "conflicts" (Champlain 318 ft "conflicts: 17 ft"); H7 lake's drainage label from before 06 renames (jackson 29 of 34
  ...); H11 a state service down removes facts silently (DWR lakes, lexington tonight); H14 profiles understate drainage
  below lakes (12_profiles.py:82 uses area_km2.tif); H15 06 writes 4 files non-atomically; H16 LA's latitude typed into
  the drawing scale (map_drainages.js:12, map3d.html:203); H19 lidar window cache never expires (lakelidar.py:98-102);
  fish_score_diagram.py: 12 identical files, unpublished, omits the channel factor, LA wording.
- Page code written 2-3 times (map_drainages.js / map3d.html / 14_portable.py / 13_overview.py): about 240 lines; copies
  already drifted. Every point layer built twice in 06 (folium + 3D list).
- Size: 3D-only inline layers 111 MB (lakes 29.4, state trout waters 24.4, restricted access 17.1, drops 13.7, lake depth
  9.0 ...); lake-touching reaches written twice 13 MB; lake depth contours unsimplified (ne_ct 8 MB for 24 lakes); DEM
  colour relief PNGs 40 MB (off by default, 2D only).
- Order 5+ lines draining under 2 sq mi: 121 over the 12 maps (new build).

## STATE at 23:52: the measured build is LIVE
- Site clone d16a885 (pushed 23:47, origin/master = HEAD, clean). All 12 published map3d_data.js are byte-identical to
  my snapshot of the local build (scratchpad snap_local/checksums.txt) -> tables renamed:
  audit/tables/live_d16a885/ (the live site) and audit/tables/before_6875118/ (the site before tonight's publish).
- streams/ at d16a885: 666.6 MB = 635.7 MiB (map3d_data.js 235.5, stream_map.html 201.0, stream_map_3d.html 113.6,
  profiles_data.js 69.0, hillshades 40.1, index 6.6).
- Project HEAD 8bdf945 (06_map.py committed 23:37). So the live site = code at 8bdf945, built 22:31-23:34, with the
  05_score comment edit and the 06_map hand reruns noted above; 12_profiles not rerun after the 06_map reruns.

## From the sources agent (audit/work/code_sources.md); verified items marked (v)
- (v) Winter closures baked into access: Jackson road_closures.csv fetched 11-21 22:38 has Teton Park Road (Nov 1-Apr
  30), Moose-Wilson, North Park Road, Grassy Lake Road, Jenny Lake Loop, Signal Mtn Summit Road, Mormon Row as full
  closures; 08_hike.py:64-68 and 09_drive.py:58-63 cut every full closure "active now"; 07's `long_term` column is read
  by nothing. 276 Jackson reaches "park at Teton Park Road", 330 "park at Grassy Lake Road"; 46 % of Jackson reaches
  have a bike leg (5-28 % elsewhere). Smokies: Parson Branch, Rich Mountain, Heintooga Ridge, Balsam Mountain, Straight
  Fork roads cut until 2027-05-01. Remoteness is 25 % of the score.
- Access model (code, confirmed by agent): any drivable road cell is a start (no parking test; parking layer unused by
  08); OSM tracks never driven (08:61-62, 09:53-54) though 02e knows which are open; walking on a trail uses the
  hillside slope capped 15 % (08:210), README says trail grade; rivers no barrier, channel cells walk at 45 % of Tobler
  (08:210-211); private land and closed trails free on foot (08:98); each box routed alone (08:44); official-only
  trails not walkable (08:59-60); drive_approx never shown (09:167); unroutable closure cut as a straight line
  (07:80-90); closure times in the build computer's zone; gauge times Pacific on every map (11:479).
- bike_check rule not kept: fire roads on the AT / Long Trail ridden unflagged (08:41-42 lacks 02d:328-329's reasons);
  gated non-track roads ridden unflagged (08:134-137); private tracks dropped not flagged (08:136-137).
- Caches: 15 cache families keyed by range/area name only (a moved box edge keeps the old extent silently); never
  expire: NHDPlus V2 table + paths + reservoirs, NDVI rasters, regional roads (09:26-28), wilderness, GNIS; no force
  switch: 02f, canopy, WQP. Today nothing stale is in use (agent checked extents of all 55 boxes). Overpass time-outs
  (HTTP 200 + remark) accepted as complete and cached (geomatch.py:18, 02d:69, 02c:30, 09:36). closure_areas.gpkg
  outlives the closure (02d:298-300). run_base / run_rebuild_a carry on after a failed step.
- Trout evidence: no-trout x0.5 from CDFW (LA), CT DEEP, TWRA; applies to same-named creek within 5 km (CA) / 1.5 km
  (11_context.py:361); beats designation (scoring.py:199). Blank CDFW species field read as "no trout found"
  (11:253-258; 118 LA labels). A reach takes a designation by touching its line (11:590-596): side creeks' lowest
  reach inherits the main stem's. Undated stocking lists stamped with the build year (troutdata.py:55): never age out.
  TU value "Brown & rainbow trout only" labelled "Wild brook trout patch" (3 patches, adk_southwest; troutdata.py:543-556).
  5 Wyoming streams the state lists "Clear (No trout present)" labelled native cutthroat water (troutdata.py:262-264).
- Licences: NYSDEC ArcGIS x4 (3 trout layers troutdata.py:490-527 + NYS_DEC_Lands geomatch.py:76-77); WWD in no
  credit line (50-falls rule per map, 06_map.py:54); curated falls without terms: New England Waterfalls 35,
  tchester SGM list 27, RiverBrain 9, VRC 6, ncwaterfalls 4, Apple Maps 1 point, komoot 1; iNaturalist and GBIF
  per-record licences dropped; Sentinel-2 uncredited; no state fish agency in the credit line; OSM share-alike notice
  missing; home ZIPs printed on every reach (user's earlier choice).
- USGS: no WaterServices caller. WQP legacy profile endpoints (watertemp.py:84-89): USGS samples in legacy WQP stopped
  updating 2024-03-11 (agent's memory, unverified). Beta statistics API (11_context.py:501). PRISM by FTP, no timeout
  (watertemp.py:93,109). NHD frozen 2023 (3DHP replaces it).
- Yearly flow index outside CA uses every ST* gauge incl. canals and tailwaters (02b:149-150, 203-216).
- Dead outputs: hike_minutes.tif per range (written, read by nothing), drive_approx, long_term, burn_count, n_src,
  known_falls_points.gpkg. Duplicated helpers ~200-250 lines (Overpass x4, ArcGIS pager x5, cache helper x11, relief,
  follow, WZDx x2, USGS get x2, User-Agent x14).


## After the report: two questions from the overview session (2026-11-22, on the live build d16a885)

### The Adirondack lake term (watertemp.py), tested: `lake_term_test.py`, tables `lake_term_*.csv`
- Drawn maps, default layer: 10+ points off 133.2 mi (HP 46.3, NW 30.7, SW 56.2); 125.2 mi with a trout record (NY class
  105.3, wild trout patch 18.5, other 1.5); estimates 73-75 F, 61-64 F without; median score 68, median markdown 11.5;
  27.6 mi from 60+ to under 60; 5-10 points off a further 330.8 mi. Knife-edge: 9+ points 189.6 mi, 9.5+ 155.6, 8+ 241.7,
  11+ 80.0 (the overview session counted 179 mi; the log 496 reaches / 322 km on an earlier build).
- Reach tables: 377 reaches, 141.2 mi, 133.0 with a trout record; lake term 5th percentile 0.84, median 0.96.
- By distance below the pond (drawn, 25 m pieces): within 650 ft 28.7 mi; 650 ft-0.6 mi 61.3; 0.6-1.9 mi 31.0; over 1.9 mi
  9.1; no lake found 3.1. By pond: 5-25 acres 20.6; 25-100 acres 54.8; over 100 acres 54.8; none under 5 acres (routing
  counts a pond only with 2 ha level, 03b_stitch.py:44; smallest above a marked-down reach 5.7 acres).
- Measured sites, three maps: 276 on a reach, 36 lake-fed (term 0.5+, 145 readings).
  within 650 ft: 18 sites / 102 readings, 74.9 F, 15 at 73+, 0 at 68 or less, +12.6 (se 0.6) over no-lake, measured - map +2.8 (0.7)
  650 ft-0.6 mi: 8 / 18, 68.3 F, 2 at 73+, 4 at 68-, +6.3 (1.8), -2.4 (2.0)
  0.6-1.9 mi: 7 / 18, 65.5 F, 0 at 73+, 5 at 68-, +3.3 (1.9), -5.3 (2.0)
  over 1.9 mi: 3 / 7, 71.1 F, +8.2 (3.0), +0.6 (3.0)
  650 ft-1.9 mi together: 15 / 36, 67.0 F, +4.9 (1.3), -3.8 (1.4); the 5 sites with 3+ readings 69.9 F, -0.7 (1.4); the 10
  with 1-2 readings 65.5 F, -5.3 (1.8).
- Trout record: 35 of 36 lake-fed sites on a reach with one, 71.3 F, 18 at 73+.
- A two-value lake term (62 sites with lake water and a lake upstream, other terms held): 14.9 F per unit share within
  650 ft, 7.6 F beyond; leave-one-out on lake-fed sites 4.49 F against 5.30 F flat (11.4 F). Markdown that implies on the
  marked-down reaches beyond 650 ft: 4.6 points (2.5 with the 15 zone sites' own 6.4 F; 9.2 with the well-sampled five's
  10.2 F); now 11.8. At the outlet 17.2 against 11.6 now.
- Verdict: supported within 650 ft of the pond (29 mi), overstated below (about 100 mi); exempting trout-record creeks
  takes the term off 94 % of the marked-down miles, warm outlets included.

### Is draw_through (06_map.py:106-283) still needed: `draw_through_test.py`, tables `draw_through_*.csv`
- 1,138 additions, 135.6 mi (743 new pieces, 395 longer heads). 459 redraw a reach already there (10.8 mi; 368 dam, 85
  pond, 6 outside); 241 more under 50 ft (1.1 mi). Real: 438 / 123.8 mi: outside rivers 211 / 65.0; dams 177 / 43.6;
  ponds 50 / 15.2. Of the 227 dam/pond ones, 77 (25.5 mi; 51 dam, 26 pond) start from a link under 0.39 sq mi, 150
  (33.3 mi) from 0.39+ (27 from 39+ sq mi, 7.6 mi; longest tellico:s33 1.82 mi, Little Tennessee below Chilhowee Dam).

## Re-check of the top seven on the live site 6c72e2e (2026-11-22 11:45, at the user's request)

All seven still hold; numbers within a few reaches of the audit's (tables `audit/tables/live_6c72e2e/`; code behind
1, 2, 3, 4, 5, 7 unchanged since 8bdf945). 1: Jackson 534 reaches (463 at 60+) parked at a winter-closed road with a
bike leg (counted from the popups against the build's own closure table; the audit's 666 used another count), Smokies
10, Cascade Creek unchanged. 2: 94.0-99.6 % year-round on ten maps; NE CT 671 perennial reaches below year-round, 396
with trout. 3: LA 81 trout reaches dry or seasonal; 207 sudden changes, 91 mi. 4: Chattooga 29/47 sq mi, French
42/101; 166 big-river points under half. 5: 2,911 of 23,242 named mi undrawn, Smokies 26 %; 97 trout records. 6:
tables 55,988 / drawn 50,513 mi; 15,212 clipped, 1,073 drawn through (172 km), 9,187 orders raised, 935 dam joins.
7: 266 halved by one sample; 4,058 burned reaches marked down. Five fix sessions started (access-times, score-evidence,
flow-class, edges-and-floor, map-step-repairs); list and file areas in the shared note
`audit-recheck-6c72e2e-fix-sessions.md`.
