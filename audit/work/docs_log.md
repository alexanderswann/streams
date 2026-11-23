# Audit notes: MULTI_AREA_LOG.md (decision log)

Read-only audit, 2026-11-21 23:05–23:40 ET. Marks: **CONFIRMED** = I read the log lines (and the code or site-clone
lines cited) myself; **PLAUSIBLE** = inferred, not verified. "L123" = line of `MULTI_AREA_LOG.md`.
An entry's own "checked" is never taken as proof here.

## 0. What was read, and the state it was in

- `MULTI_AREA_LOG.md` read end to end. It **grew while being read**: 3,196 lines / 287,919 bytes at 23:05, then
  3,227 lines / 291,009 bytes after project commit `729487d` (23:12:35) appended L3198–3227. Nothing above L3196
  moved (checked with `git diff d06b50b HEAD`), so all line numbers below hold for the 3,227-line file.
- Cross-checks, all static: `grep`/`Read` on `scripts/`, targeted `grep` on `README.md`, row counts in
  `data/known_falls_curated*.csv`, and read-only `git log` / `git show --stat` on the project repo and on the site
  clone `publish/alexanderswann.github.io` (HEAD `6875118`). Nothing in `scripts/` was imported or run; `output/`
  and `data/derived/` were not used.
- Project HEAD moved twice during the audit (`729487d` 23:12, `03a1b4d` 23:17); `README.md` and `scripts/06_map.py`
  have uncommitted edits (+9/−1 and +49/−1 lines).

### Cross-cutting findings (they colour every section)

| # | Finding | Evidence | Mark |
|---|---|---|---|
| X1 | **The log is behind the code by one large commit.** `d06b50b` (11-21 22:46: 17 scripts, +841/−120 lines; lines changed: `watertemp.py` 226, `flowlib.py` 166, `05_score.py` 141, `lake_bathymetry.py` 134, `crossbox.py` 71, `05b_flow.py` 64, `scoring.py` 44 ...) has no entry. Its subject line lists five changes (reaches cut at lake shores; side channels; drops and water below dams; a lake term for water temperature; Lake Champlain's depths). The log names it once, in passing (L3223). | `git show --stat d06b50b`; `grep d06b50b` → L3223 only | CONFIRMED |
| X2 | **The live site was built before that commit.** Site clone HEAD is `6875118` (11-21 22:16). Its data files hold 0 occurrences of the "(side channel)" name marker `d06b50b` introduces, in all 12 areas. The uncommitted `06_map.py` edit (a further drawing patch, see §4) is in neither the log nor the site. | grep on `streams/*/map3d_data.js` in the site clone; `git diff scripts/06_map.py` | CONFIRMED |
| X3 | **Entries are missing.** No entry for adding SE Pennsylvania (site commit `c28add0`, 11-19 15:42; "19063"/"Media" never appear), none for the imperial-units change (only referred to: L1390–1395, L2020), none for the link-preview card (`5696cf1`, `61fc692`; mentioned at L858). | grep; site clone log | CONFIRMED |
| X4 | **The log is not append-only.** L1156–1157: "Another session's rewrite of this log dropped it before the 16:47 checkpoint, so it is restored here in short." One entry is known to have been lost and rewritten from memory; others may have been. | L1156–1157 | CONFIRMED |
| X5 | **Not chronological; authorship ambiguous.** Order of headings: L1113 "11-19 evening" → L1155 "11-19 afternoon"; L1884 "11-20 after midnight" → L1965 "11-19 evening"; L2988 "late evening" → L3021 "evening". Of the 38 headings, 8 say "(this session)" and 10 "(another session)", each for a different author; 15 name a session by role; 5 name none. The Mac's clock moved from Pacific to Eastern around 16:20 PT on 11-19 (L1019–1020, L1064, L1115), so times before and after are in different zones. | `grep '^## '` | CONFIRMED |
| X6 | **Builds ran from a shared, uncommitted working tree.** Project commits are after-the-fact checkpoints (23 as of 23:17; e.g. `4a8c1c8` "Work in progress from the running sessions"). The log itself records code changing mid-rebuild: L2348 (scoring.py and 06_map.py edited at 15:28 during the 15:24–15:34 rebuild), L895–896, L901, L1151. No entry can prove which code state a given area's step ran on. | L2348, L895, L901, L1151; `git log` | CONFIRMED |
| X7 | **Four site commits are never cited in the log**: `c28add0`, `5696cf1`, `61fc692`, `68d952e` (11-20 23:49, the all-12 pass of 23:38–23:47). `855954f` (11-21 01:53) is cited only in the last entry (L3205), not in the entry for its own pass (L3041–3082). | site clone log vs grep of hashes | CONFIRMED |
| X8 | The tables' own arithmetic holds: 12 per-area tables or sums re-added (L886, L1741–1753, L2075–2087, L2277, L2343, L2388, L2534, L2736–2739, L3008–3010, L3035, L3066–3070, L3216) all match their totals. The contradictions in §2 are between entries, not inside them. | re-added by hand | CONFIRMED |

## 1. Open items never closed

### 1A. Still open (no later entry closes it; code checked where it could be)

| # | Date | Lines | What / where | Script | Status |
|---|---|---|---|---|---|
| A1 | 11-18 | L57–58, L157–158, L370, L404, L581 | LA: concrete channels with natural names (LA River, Tujunga Wash) still score as streams | `scoring.py:202–211` (`channel_factor`; `NATURAL` at :204 exempts river/wash) | OPEN — CONFIRMED |
| A2 | 11-18 | L176–177, L363–364, L425–429, L577 | Flow outside CA is EROM mean × one yearly index per area; under 25 km² the model is 3.7× high on Vermont's two gauges (Ranch Brook, West Branch Little River), 5.4× on Connecticut's one | `02b_download_flow.py`, `05b_flow.py` | OPEN — CONFIRMED (no later entry) |
| A3 | 11-18, 11-19 | L264–266, L359–362, L575–576, L1488–1491 | Scores not comparable between areas; Jackson at the cap of 100; trout bonus on 49–86 % of reaches. Only mitigation: `area_rank_pct` (L405–407) | `scoring.py` | OPEN (design) — CONFIRMED |
| A4 | 11-18, 11-19 | L471–472, L578, L1465 | No road-closure feed for NE Connecticut (CTroads key), Wyoming state highways / Teton Pass (WYDOT), the Adirondacks (511NY key). Needs a registered key: the user's step | `07_road_closures.py:26` | OPEN — CONFIRMED |
| A5 | 11-18 | L579–580 | Tugaloo River (enters N Georgia through Lake Hartwell's arm) not carried in; rivers along a box edge short of drainage for a few km | `crossbox.py` | OPEN — PLAUSIBLE |
| A6 | 11-19, 11-20 | L1047–1061, L2829–2835 | Download caches don't notice a moved box (OSM trails/roads/cycleways of 02d/02e/08, 05_score's waterways, 11_context's canopy, troutdata, watertemp's WQP, PRISM clip, 02b's NHDPlus table, flowlib's reservoir list). "whoever moves a box next must clear the same files, or make them record their box". Cleared by hand twice; the second time it cost Vermont its Wikidata falls source | only `02f_known_falls.py:60–82` stamps its box; no stamp found in the other scripts | OPEN — CONFIRMED by grep |
| A7 | 11-19 | L1124–1125 | LA: a straight stream line about 2.5 km out to sea off Malibu, "Not changed" | `06_map.py:114` (`draw_through`), `05_score.py:89–90` | OPEN — PLAUSIBLE |
| A8 | 11-19 | L1172–1173, L1177 | 47 creek profiles still read >1.5× their drainage (6 at 10×+), 80 best scores from another stream; only the 22 name-vote cases were then fixed | `12_profiles.py:25` (`OWN_CAP`) | OPEN — PLAUSIBLE |
| A9 | 11-19 | L1197–1198 | The perennial test for big-creek drops still uses the nearest NHD line | `04b_bigcreek_steps.py` | OPEN by choice |
| A10 | 11-19 | L1302–1303 | An area built but not yet published can be a dead link in other maps' Go-to menus | `06_map.py:26` | OPEN (minor) |
| A11 | 11-19 | L1342, L1344–1346 | Smokies: park's three-pass electrofishing workbook (2,631 station-visits) and NC DEQ fish samples (154 visits) not used; USFS MVUM seasonal dates not used for closures | `troutdata.py`, `07_road_closures.py` | OPEN — CONFIRMED (grep: absent) |
| A12 | 11-19, 11-21 | L1358–1360, L3113–3116 | Nantahala's bypassed reach above the powerhouse measures 20.6 °C; the tailwater flag "overrates it by about 2 points" | `scoring.py:162–165`, `:176–186` | OPEN — CONFIRMED |
| A13 | 11-19 | L1438–1439, L1528 | Round Pond (0.92 km²) and Square Pond (0.86 km²) lie across the line between the adk_northwest and adk_high_peaks maps; Queer Lake touched | `config.py` | OPEN — CONFIRMED |
| A14 | 11-19 | L1502–1504 | Reach ends on a shared box edge with no partner within 30 m: High Peaks 10, northwest 13, southwest 5, southeast 3 (Central Vermont 3). "Not chased." | `03b_stitch.py` | OPEN/unclear — other scripts later report 0 (§2 C4) |
| A15 | 11-19, 11-20 | L1623–1625, L2232–2233 | Teton Valley's warm floor creeks not told apart from cold canyon creeks; three Adirondack fits without skill | `watertemp.py` | OPEN in the log (see B6) |
| A16 | 11-20 | L1957–1963 | adk_northwest: short "Raquette River" reaches of 1–30 km²; the stretch between Simon Pond and Raquette Pond (~28 km² against 1,324); 6 lakes under half of NHDPlus below their outlets (Big Moose Lake, Rollins and Floodwood ponds, Bridge Brook Pond, two unnamed). "Not chased." | `03b_stitch.py`, `crossbox.py` | OPEN — PLAUSIBLE (L3176 gives only an all-map 45 → 26) |
| A17 | 11-20 | L2381–2382 | 7 Adirondack reaches lying in lake pieces with no level water "left as they are" | `05b_flow.py:78–81` | OPEN (minor) — CONFIRMED |
| A18 | 11-20 | L2497–2499 | Each lake layer stored twice (2D folium + 3D inline); drawing 2D from `MAP3D.lakes` would save ~20 MB, "worth it before more areas are added" | `06_map.py:1221` (`SHARED_3D` has no lakes) | OPEN — CONFIRMED |
| A19 | 11-20 | L2509 | `git gc` in the site clone would free ~1.2 GB (local only) | — | OPEN |
| A20 | 11-19, 11-20 | L1668–1685, L2524–2525 | Consent of nnywaterfalls.com and the World Waterfall Database: emails sent by the user 11-20, "replies awaited". If refused, pull rows by `source` and rebuild the affected areas | `data/known_falls_curated.csv` (116 + 106 rows) | OPEN, waiting on third parties — CONFIRMED |
| A21 | 11-20 | L2646–2648, L2712 | NY DEC's terms on the three stream layers the Adirondack maps already publish | `troutdata.py:490–527` | OPEN — CONFIRMED (§5) |
| A22 | 11-20 | L2713–2714 | DEC contour-map depths to type in for the bigger lakes | `lake_bathymetry.py` | OPEN / declined |
| A23 | 11-20 | L2716 | NY stocked waters whose name repeats in their town left unmatched: 18, 16, 2, 4 on the four Adirondack maps | `05d_lakes.py` | OPEN (minor) |
| A24 | 11-20 | L2788–2790 | Dry-creek rule: imagery is 2022–24 (re-measure before refreshing); Indian Creek above Palisades (model 22 cfs, dry 1954–60) left as is | `02g_greenness.py`, `scoring.py:138–143` | OPEN (minor) |
| A25 | 11-20 | L2913–2917 | Defects carried through the edge-lake rebuild because they were "the same before and after": Smokies 2 dead reach ends (Santeetlah Creek; a 1 km² creek); Jackson's Yeaman Creek and a 1.2 km order-3+ gap in the Palisades box; LA gaps 0.1–1.5 km a box and two flow drops; adk_northwest's Tooley Pond Outlet; adk_southwest three flow drops (the Sacandaga among them); adk_southeast one; High Peaks' Saint Regis drop | `03b_stitch.py`, `05b_flow.py` | OPEN — CONFIRMED lines; never chased |
| A26 | 11-20 | L3015 | N Georgia: Tallulah Falls (dam, forebay, tunnel) "stays a small tangle of the routing's own lines" | routing | OPEN (minor) |
| A27 | 11-20 | L3039 | The user asked whether to draw streams whole and let opaque lakes cover them. "Not decided." | `06_map.py`, `map_drainages.js` | OPEN — to the user |
| A28 | 11-21 | L3130, L3161 | The Snake's first 0.4 mi below Palisades Dam has no name | `05_score.py` name vote | OPEN (minor) |
| A29 | 11-21 | L3121–3122 | One San Jacinto River reach matches the next NHDPlus line at a junction and loses its gauge record | `flowlib.py:570` (`gauge_record`) | OPEN (minor) |
| A30 | 11-21 | L3191–3193 | Lower Piru Creek below Lake Piru: popup credits Pyramid Lake's releases; "A `TAILWATERS` entry for Lake Piru would name the right dam" | `scoring.py:154` has no Lake Piru entry | OPEN — CONFIRMED |
| A31 | 11-21 | L3196 | 31 short adk_northwest reaches (4.9 km) carry a river's stream order with a creek's drainage | `03b_stitch.py:126`, `06_map.py:84–105` | OPEN |
| A32 | 11-21 late | L3210–3216, L3223–3226 | **Fault 1, lake put-ins** (live on the site): of 1,430 lakes with a link, 192 put their water in so that 200+ m of the way out misses it; 31 firm cases carrying 1,041 km² (adk_southwest 10, adk_northwest 6, ne_ct 5, adk_southeast 3, adk_high_peaks 2, la 2, se_pa 2, central_vt 1). Seventh Lake: 43.5 km² goes in 555 m from its outlet; the channel to Fifth Lake (16.9 sq mi, fish 87 before) isn't drawn | `crossbox.py:262` (`_dam_links`), `:335` (`_at_outflow`, `OUTFLOW_NEAR_M = 100` at :31) | OPEN — CONFIRMED; `_at_outflow` "leaves 29 of the 31" |
| A33 | 11-21 late | L3217–3222 | **Fault 2, the outlet itself** (live): 03b's outlet is the lake cell with the most water, in 77 lakes 300+ m from NHD's outlet (Raquette Lake 9.1 km, Upper Saranac 6.8 km, Arrowhead Mountain Lake 5.3 km); `route_lake` sends the whole lake there | `03b_stitch.py:357` | OPEN — "Fix proposed, not made here" |
| A34 | 11-21 | L3194–3195 | 48 creek pieces drawn with a lake's values (22.5 km) and 37 lake reaches with creek outside the lake "wait for the in-lake rule the side-effects session is changing" | `05b_flow.py`, `05_score.py` | OPEN in the log (see B5) |
| A35 | 11-20, 11-21 | L2547, L2584–2588, L3101–3102 | DEM burn parked by the user; three ideas listed to try | `data/stream_burning/` | PARKED |
| A36 | 11-20 | L2832–2835, L2868 | Vermont's known falls lack Wikidata as a source since the 16:00 build; "the next 02f run fetches Wikidata again" — no entry says it did | `02f_known_falls.py` | PLAUSIBLY closed by the 11-21 `run_mid` (`run_mid.sh:17`); unverified |
| A37 | 11-20 | L3007–3012 | 103 of 393 cells below a dam on the shown maps (285 of 1,043 on the Adirondack ones) get no join; reasons listed, not counted | `06_map.py:835–945` | OPEN (minor) |
| A38 | 11-18 | L472 | "Virginia's files are undocumented and may move." | `07_road_closures.py` | standing risk |
| A39 | 11-19 | L645–648 | The GitHub token expires; the user makes a new one when a push is refused | `publish_site.sh` | standing, user |

### 1B. Closed in the code but not in the log (the log still reads "open")

| # | Open in the log | Closed where | Mark |
|---|---|---|---|
| B1 | Side channels: ~790 reaches carry a big river's name; two options "put to the user", "Not built" (11-20, L2718–2731; same thing at L1272–1274 Lamoille, L1598 Snake, L1957 Raquette) | `05_score.py:211–278` (`SIDE_RATIO, SIDE_RIVER_KM2, SIDE_NEAR_M, SIDE_ALONG, SIDE_ON_RIVER = 10.0, 50.0, 250.0, 0.6, 0.6` at :224), `scoring.py:279–280`, `map_drainages.js:108–109`; commit `d06b50b`. Not on the site (X2) | CONFIRMED |
| B2 | "Drops (04) near an outer-boundary entry still see only the in-map area there" (11-19, L793) | `04_knickpoints.py:24–31`, `04b_bigcreek_steps.py:32–33` add `crossbox.carried_km2` (`d06b50b`) | CONFIRMED |
| B3 | Lake Champlain's depth, NOAA multibeam not read (11-20, L2652, L2867–2868) | `lake_bathymetry.py:302`, `:420` (NOAA ENC charts), `README.md:896–900` (`d06b50b`) | CONFIRMED |
| B4 | Willow Creek below Lake Arrowhead drops a class, "Left as they come out" (11-21, L3120–3121) | `scoring.py:255–273` (rule "below a dam", `DAM_HELD = 0.5` at :144) (`d06b50b`) | CONFIRMED |
| B5 | In-lake rule and cutting reaches at lake shores, left to the side-effects session (11-21, L3164–3166, L3194–3195) | `05_score.py:95–106`, `flowlib.py:187` (`LAKE_PIECE_M = 50.0`), `:246–279` (`lake_water`, `shore_cuts`, `cut_at_shores`) (`d06b50b`) | CONFIRMED |
| B6 | Three Adirondack water-temperature fits without skill (11-20, L2232) | `watertemp.py:180–187` (lake term, `LAKE_MIN_SITES = 10`), `config.py:291` (`water_temp_group="adirondack"`), `README.md:786–794` (`d06b50b`) | CONFIRMED |
| B7 | Run order: the log says `run_mid.sh` runs 05d "between the 05c and 05b loops" (11-20, L2339–2340) | `run_mid.sh:18–32` now runs 02b, then 05d, then 05_score. A comment at `05b_flow.py:120` still says 05d "reads 05c's drainages"; `run_mid.sh:23–24` says it needs nothing of the reaches', and grep finds no drainage file read in `05d_lakes.py` | CONFIRMED (log and one code comment stale) |

### 1C. Closed by a later entry (for traceability)

66 small ponds restart the brook's area (L722–725, L792) → L2203–2209. Vermont north edge effects (L1091–1101) → L1253–1271.
Piseco Outlet (L1404–1410, L1510–1512) → L1776–1801. 05b's scaled flow stops at box edges (L1619–1622) → L2132–2159.
Bull Sluice tailwater and the flow-drop check in LA (L1877–1882) → L2181–2196. Run order and vertex truncation
(L2121–2129, L2161–2167) → L2175–2180, L2220–2223. Cheoah Reservoir scored as river (L2317–2329, L2714–2715) → L2338–2347.
Palisades crossing (L2350–2354) → L2380–2392. README validation table stale (L582–583) → L2527–2538.
Edge-lake fix for the other 11 areas (L2867) → L2886–2939. "Creeks below lakes still have no reaches of their own"
(L3038) and the Pilgrim Creek / Trout Creek lines (L3080–3082) → L3096–3100, L3128–3130, L3153–3154.
"Minor front-range drainages" wording (L193–194) → `config.py:59`, `:376` (code only).

### 1D. Verification gaps the log admits

- 3D view never looked at: Vermont north box (L1088–1089), Jackson expansion (L1611–1612); 3D toggle left to a later
  pass (L2403), then checked on Jackson only (L2406–2407).
- Live site not opened in a browser after `4d76f17` (L805); download of the live Jackson data "cut off by a
  connection reset and not repeated" (L865–866).
- Post-publish checks are hash comparisons of served files against the build, plus spot checks of named places.
  They show the upload was faithful, not that the build was right (see §2 C5, C6).

## 2. Result claims that a later entry contradicts or revises

| # | Claim | Later | Mark |
|---|---|---|---|
| C1 | **Site history size.** 11-19: "about 108 MB to about 250 MB" (L657); "now 338 MB" (L806); "already about 772 MB (GitHub recommends under 1 GB)" (L1305); "814 MB of history before it" (L1392); "about 883 MB now" (L1399) | 11-20: "packed history was about 300 MB before this push" (L2158); "**History is not near 1 GB.** GitHub reports 397 MiB; a local repack gives 294 MB. The 1.4 GB local `.git` is loose objects" (L2422–2423); then 457 MiB (L2459), 527 → 413 MiB (L2508). Two decisions rested on the wrong figure: leaving a dead Go-to link live rather than republish (L1304–1307) and merging two sessions' publishes into one commit (L1391–1393) | CONFIRMED |
| C2 | **`streams/` size, MiB written as MB.** Same commit `3303d03`: "577 MB in 117 files" (L2261) vs "117 files and 604.5 MB" (L2457). Same commit `2fcc91f`: "615 MB" (L2702) vs "644.3 MB" (L2504) / "644 MB" (L2708). Before `3303d03`: "stays 859 MB" (L2158) vs "891 MB" (L2417) | 577 MiB = 605 MB and 615 MiB = 645 MB, so two units are in use against the same 1 GB limit. The current "628 MB of Pages' 1 GB" (L3189) has no unit check | CONFIRMED |
| C3 | **Sudden flow drops.** "0 sudden drop-and-recover reaches in every area" (11-19, L828) | Same evening: "NE CT has 1 and LA 4" (L1145). Late 11-19, another check: LA 1,000, Jackson 48, N Georgia 2, se_pa 1, adk_southwest 1, adk_southeast 1 (L1741–1752), "LA's ~1,000 by this check are the check itself" (L1765). 11-20 new `check_flow_drops.py`: 0 everywhere (L2192–2193, L2247, L2299, L2346). Hours later the Vermont session's checks list LA two drops, adk_southwest three "(the Sacandaga among them)", adk_southeast one, High Peaks one (L2915–2916). 11-21: "Flow drops 0 → 0" (L3109), "no sudden flow drops" (L3177). Three check definitions; the 0s and the 7 are never reconciled | CONFIRMED |
| C4 | **Dead reach ends on shared edges.** "270 -> 0 (every area 0)" (11-19, L773); Smokies "0 of 126" (L1364–1365) | Adirondacks 10 / 13 / 5 / 3 and "Central Vermont, published, gives 3 by the same script" (L1502–1504) against Central Vermont "0 of 72" by another script (L1070); "Smokies' 2 dead ends (Santeetlah Creek, a 1 km2 creek), Jackson's Yeaman Creek" (L2914) against "0 → 0" (L3109) | CONFIRMED |
| C5 | **The 03b check of 11-19 morning.** "Redrawn from the rebuilt data and looked at: all nine of the user's views (... Jackson's two ...)" (L773–777); published `4d76f17` | Afternoon: 39.6 km of the Snake missing below the Hoback (int32 overflow). "I missed it on the morning's check: the test looked at box edges, and on the redrawn Jackson view the Snake ending at the confluence was there to be seen" (L838–846) | CONFIRMED |
| C6 | **Lake routing (11-21), revised three times.** Measured: "Fish 60+ 42,159 → 41,911 km ... Most are reaches whose ends now cross the 50 %-in-lake line" (L3111–3112); Jackson published on it (`797a30e`) | (1) "What my first measurement missed ... I read ... as class churn at lake shores and said so to the user; part of both was these lost lines" (L3150–3152). (2) After the floor fix: "km of fish 60+ 42,159 → 42,721, up on every map" (L3173). (3) "My figures were from the reach tables, and I gave them as the map's": drawn line 50,436 → 50,438 mi, "fish 60+ 25,024 → 25,095 mi, down on five maps", and "The four Jackson creeks I reported missing from the map published at 19:49 were drawn on it" (L3202–3209, against L3145–3146) | CONFIRMED |
| C7 | **Lake outlets under half of NHDPlus.** adk_northwest "flags 6 lakes where it flagged 17" (L1941); all maps "45 → 39" (L3105) | "45 → 26" (L3176); and the check itself was changed in between: it "now takes the reach carrying the most water near NHDPlus's outlet point, not the nearest; the nearest was often a side creek" (L3105–3106); "my NHDPlus comparison misread Silverwood Lake" (L1961–1963) | CONFIRMED |
| C8 | **Breaks at dams.** An earlier count of "about 30 breaks" (not itself in the log) | "missed most of them: it looked at line ends, and these are line starts": 393 cells below a dam on the shown maps and 1,043 on the Adirondack ones (L2994–2996). The code comment still says "some 335 outlets over the eight shown maps" (`06_map.py:838`) | CONFIRMED |
| C9 | **Adirondack water-temperature fits.** Table lists a fit for each map: "elevation, 109 sites", "August air, 87 sites", "drainage area, 115 sites" (11-19, L1483–1485); "all their fits pass (ratios 0.57-0.78)" (L1586) | "adk_high_peaks, adk_northwest, adk_southwest still have no skill" (11-20, L2232); `README.md:790–791`: three of the four "had no fit with skill (leave-one-out error 0.92-1.02 of the spread) and gave every reach its area's mean, full credit everywhere" | PLAUSIBLE (L1586 may predate the Adirondack builds) |
| C10 | **Dry-creek baseline.** The map "called a creek flowing in 60% of the summers its gauge was dry (75% since 2011)"; "227 flowing most summers" (L2736–2740) | "summers since 2011 called flowing while the gauge was dry 82% -> 13%"; "none of the 221 gauged creeks that flow most summers" (L2767–2769). The gauge set changed after the user's approval ("gauges below diversions and dams included", L2747) and the baseline was not restated | PLAUSIBLE |
| C11 | **Lake Champlain's made-up lines** in adk_high_peaks: "1,113 km of DEM lines" and "593 reaches" (L2814–2818) | "Lines on the water: High Peaks 647 km -> 0.5" and "the lake's 596 reaches gone" (L2909–2911) | CONFIRMED (two measures, not said which) |
| C12 | **Raquette between Simon Pond and Raquette Pond**: "about 28 km2 against 1,324" (L1958) | "2 → 1,485 km2" (L2568) | CONFIRMED |
| C13 | **N Georgia known falls**: "N Georgia rescored at 16:10 (929 known falls)" (L1016) | "Georgia now shows 925 known falls (693 from gawaterfalls.com)" 13 minutes later (L1021); the file has 695 rows | CONFIRMED |
| C14 | **Vermont reach counts**: "733 new reaches (Vermont 6,681 → 7,434)" (L1072; the difference is 753); "965 reaches (Vermont 6,681 → 7,666)" (L1281; 985) | 7,632 in the same build's flow table (L1744) | CONFIRMED |
| C15 | **adk_northwest reach counts**: 8,459 "ranked table" (L1484), 8,264 (L1750), 8,276 (L2084) | "The local map loaded with 8,473 reaches" (L1952) | CONFIRMED |
| C16 | **N Georgia drainages**: 51 (table, L554) | "N Georgia has 49 drainages, not 50" (L693) | CONFIRMED |
| C17 | **adk_northwest dead ends**: "all 7 dead ends on edges mended" (L1934) | "Dead ends on shared edges: 0 (was 5)" (L1937) | CONFIRMED |
| C18 | **Mapped-falls validation**: `data/validate.py` "had reported 0 of 0 mapped falls in every area since 2026-11-19" (L2528): the standing check was dead for a day of rule changes. Then "every precisely placed known fall: 839 of 1,600" (L2534) | "all known falls 1,025 → 1,025" (L3107–3108), a third figure with no definition | CONFIRMED / PLAUSIBLE |
| C19 | **Lake reaches drawn as lake**: "jackson 431, smokies 565" (L2388) | "streams_lake in map3d_data.js (smokies 481, jackson 428)" after the final pass (L2410) | CONFIRMED |
| C20 | **Connecticut lakes**: published `e70326e` | "161 Connecticut lakes had been read wrongly, published e70326e, fixed fb69421" (L1995) | CONFIRMED |
| C21 | **LA water-temperature fit**: 65 sites, RMSE 3.21 °C, "33 reaches (0.2%) moved 10+" (L141–152) | 64 sites, RMSE 2.98 °C, "the summary is the same as logged at 16:10 (95% within ±3; 34 moved 10+)" (L251–253) | CONFIRMED (minor) |
| C22 | **Publish times and file counts**: `3303d03` "about 12:50" (L2253) vs "pushed at 12:43" (L2455) vs 12:42 in the clone; `31efc26` 15:27 (L897) vs 15:31 (L1003); "all seven files as served" for `739374b` and `ffe5189` (L1107, L1287), which changed 5 and 6 files; "all 16 files" for `5f7660b` (L1714), which changed 12 | site clone | CONFIRMED (minor) |

## 3. Rules made for one named place, and constants picked from one case

### 3A. No measurement across all areas recorded

| # | Rule / constant | Code (confirmed present) | Named case | All-area measurement in the log? |
|---|---|---|---|---|
| R1 | A no-trout sample speaks for the creek within **1.5 km** outside California (5 km in CA) | `11_context.py:357–367` (`reach_m = 5000 if (e.trout or CA) else 1500` at :361) | NE Connecticut pilot: ~1,200 reaches flagged (11-18, L239–241) | **No.** One area's count; since applied to TWRA samples too (L1332–1333) |
| R2 | Water-temperature credit full at **20 °C**, zero at **25 °C** | `scoring.py:149` (`WATER_FULL, WATER_ZERO`) | LA's 1,566 trout-evidence reaches (11-18, L144–147) | **No.** Only per-area medians afterwards |
| R3 | A waterbody ends flow paths only if **2+ ha** of its outline is at one elevation; NHD lakes of **8+ ha** | `03b_stitch.py:44` (`LEVEL_HA = 2`, used :562); `flowlib.py:8` (`MIN_RESERVOIR_KM2 = 0.08`) | Devil's Gate on the Arroyo Seco, Temescal and Pacoima washes (11-18, L533–542): "The split is clean in LA" | **No.** LA only |
| R4 | Built channels ×0.2 by name | `scoring.py:202–211` | Pacoima Diversion Channel and LA's aqueducts: 176 reaches on 30 names (11-18, L400–404) | **No.** Two non-cases named elsewhere ("Ditch Creek", "Canal Branch"); never counted in the six later areas |
| R5 | A named drainage under **2 km²** joins its neighbour | `06_map.py:454–470` (`a_ < 2e6` at :458) | Pacific Creek at Moran, 1 km² inside the boxes (11-19, L760–761). Since Jackson's expansion the creek's lower course is on the map (L1543; "Pacific Creek ... 415 km2, order 6", L1887), so the case no longer applies — PLAUSIBLE | **No** |
| R6 | 05b: a reach half or more inside an NHD lake with no model segment reads "reservoir" | `05b_flow.py:576–591`, `flowlib.py:341` (`share=0.5`) | Fontana Lake's arms, "year-round, 1,304 cfs, fish 83" (11-19, L1371–1377) | **After the fact.** Affected reaches counted in 8 areas; effect measured in the Smokies only (211 reaches, median −43); "The other areas change at their next `05b` run". Their effect is reported later (L1814–1816: central_vt 149 scores, median −27) |
| R7 | NHDPlus split-channel flags (second version of `minor_arms`, from the se_pa work, which has no entry) | `flowlib.py:12–40` | se_pa (unlogged); first version: Guys Run, Lexington (L808–819) | **No, and it failed.** "The first LA run, with the rule as written, moved 68 LA fish scores, 48 of them down" (Bear Creek 100 → 38); then limited to `not has("tnc_flows")` (11-19, L1126–1137; `flowlib.py:40`) |
| R8 | Tailwater floor: a `TAILWATERS` reach with no gauge record gets full water credit | `scoring.py:248–254` | Piru Creek below Pyramid Dam (11-21, L3113–3119) | **LA only** ("LA's fish 60+ goes 1,389 → 1,396 km"). It also covers the Chattahoochee, Toccoa and Nantahala. Site clone at `6875118`: the rule's popup text appears 44 times in LA's data and 0 times in n_georgia and smokies, so it changed nothing there |
| R9 | Shore pieces under **20 m** left off | `06_map.py:820` | Jackson Lake (11-20, L2876–2883: "Measured on Jackson") | **No** (counts only, L2918–2920) |
| R10 | Joins across dams: **150 m** max, river's line within **300 m**, none where the line runs by the shore within **80 m** | `06_map.py:847` (`DAM_TOL, TRUNK_TOL = 150, 300`), `:902` | The 80 m rule from one case: "it drew a 'v' beside Salacoa Creek at a pond's tip in North Georgia" (11-20, L3004–3005) | **Counts only** (L3007–3012); five places looked at |
| R11 | A lake outlet's path into a stream carrying over **1.5×** its water is the lake's own creek; a piece never **40 m** from the shore is dropped | `06_map.py:179–255` (:230), `:762–768` (:766), `:797` | Taggart Creek read "Cottonwood Creek, 67.4 sq mi"; the Snake's stubs at Donoho Point, 34–73 m (11-20, L3022–3037) | **Counts only** (383 outlet paths, 3,501 stubs); Jackson alone looked at |
| R12 | Search for a lake's NHDPlus line within **4 km** | `05b_flow.py:185–187`, `:353`, `:374` | "Big Brook off Port Kent had taken a line 3.5-4.1 km out; a first try capped at 3 km missed it" (11-20, L2956–2959) | Constant from one creek; score check on 12 areas recorded (L2971–2983) |
| R13 | PAD-US "restricted" not flagged on federal wilderness, forest and park units | `11_context.py:173–178` | Lexington's wilderness reaches (11-18, L277–279); Wyoming Range (L998–1001) | **No** |
| R14 | Dry-creek thresholds: model low < **0.45 cfs**, NDVI p90 < **0.45 / 0.5**, strip **0.2**, water **0.35**; gauge within **4 km**, 2/3–1.5× drainage | `scoring.py:138–143`, `flowlib.py:461` | Fitted on LA: 6 wet against 25 dry gauged creeks in the 0.1–0.45 cfs band (11-20, L2741–2745) | **Partly.** No flowing gauged creek lowered on 12 maps; humid areas "measured in all nine", nothing found (L2767–2771). In Jackson it sets 69 unnamed draws "seasonal" (L2778) with no dry Jackson gauge behind the constants |
| R15 | "Names along rivers": every other reach of the name within **3 km** drains under half as much | `05_score.py:151`, `:201–202` | The Snake at Station Creek, the Santa Clara below Castaic, the Chauga at Hell Hole Creek (11-19, L1177–1199) | Six areas (L1212–1219). se_pa got it a day later, unmeasured, by a side effect of another rebuild: "5 reaches moved about 10 points" (L2935–2937) |
| R16 | Place overrides | `05c_drainages.py:46–65` (`NAME_FIX`, 8 entries), `:67–76` (`FORK_FIX`, 4); `scoring.py:153–165` (`_TAILWATERS`, Bull Sluice 265 → 250 m, L2181–2186) | Gorman Creek → Piru Creek (L543); Cuddy Creek, Ocoee River (L763); Fishtrap Branch (L1378–1381) | n/a: place-specific by design. Two San Gabriel `FORK_FIX` entries were removed when a general rule made them wrong (L2294–2296) |
| R17 | Rules in `d06b50b` with no log entry at all: `LAKE_PIECE_M = 50.0`; `SIDE_*` = 10, 50 km², 250 m, 0.6, 0.6; `DAM_HELD = 0.5`; `OUTFLOW_NEAR_M = 100`; `LAKE_MIN_SITES = 10` | `flowlib.py:187`; `05_score.py:224`; `scoring.py:144`; `crossbox.py:31`; `watertemp.py:183` | Spencer Pond / Big Pond (NE CT), Willow Creek below Lake Arrowhead, Cottonwood Creek beside the Snake (code comments) | **Not in the log.** Per-area files exist under `data/stream_burning/results/shores_2026-11-21/` (not read) |

### 3B. One-place rules where the log does record an all-area measurement (for contrast)

`resolve_flats(eps=1e-9)` (`03_hydrology.py:33`; Natchaug, then 3 more boxes, L444–448 — 4 of 16 boxes, partial);
promoted tributaries 100 into 2,000 km² (`05c_drainages.py:29–30`; the Hoback; results listed for the six areas of the
day, L498–504); drop-artifact rules, 40 m road crossing and 50 m mapped fall (`05_score.py:332–356`; the Middlebury
River fall; all 8,931 drops, L874–891); `minor_arms` first version (L818–819, L829–833); `OWN_CAP = (2.0, 1.0)`
(`12_profiles.py:25`; Cabin Creek; 2,962 profiles, L1166–1173); Piseco Outlet fix and its refinement (all 55 boxes,
L1730–1791); `mend_seams` (`03b_stitch.py:43–48`, `:268`; Raquette Pond; every area's output, L1923–1925); cross-box
scaled flows (L2068–2098); pond links, tie-break, weighted fit (L2198–2251); in-lake rule and main-path trunks
(L2272–2301); lakes-layer rule for Cheoah (L2330–2347); Palisades' touching pieces ("changes exactly that one reach
over the 12 areas", L2353); lake rules (L2601–2633, L2665–2678); edge lakes (33 lakes on 12 maps, L2817–2819);
lake-reach piece values (L3053–3072); `route_lake`, `LINE_PULL = 5.0` (`03b_stitch.py:45`; L3103–3112 — measured on
all 12, then found wrong twice, §2 C6).

## 4. Fixes made where the problem shows

All ten are still in the code. The log's own words for them: "symptom repairs" (L742), "For drawing only" (L697–699),
"Drawing only" (L2882, L3005), "**Not fixed at the root**" (L3038), "The root fix is for 03b ..." (L3081–3082),
"A real fix would follow the river's path through the whole lake" (L2372).

| # | Date, lines | Patch in the drawing step | Still present | Root fix recorded later | Should it now be unnecessary? |
|---|---|---|---|---|---|
| D1 | 11-19, L695–699, L742–743 | Stream order raised for reaches carrying over twice their box's drainage | `06_map.py:84–105` | `03b_stitch.py` joined routing (L747–764); `outflow_streams` (L3099–3100) | Mostly. A32's 31 reaches with "a river's stream order with a creek's drainage" (L3196) look like its residue — PLAUSIBLE |
| D2 | 11-19, L671–675 | Unnamed pockets along shared edges placed by the outline across the edge, or under 5 km² by shared boundary | `06_map.py:398–453` (:428) | 03b joined routing, same day (L747–764) | Not stated; the step prints its own count, never quoted after 11-19 |
| D3 | 11-19, L760–761 | Named drainage under 2 km² joins its neighbour | `06_map.py:454–470` | Jackson's expansion put the creek's lower course on the map (L1543, L1887) | Probably, for the named case — PLAUSIBLE |
| D4 | 11-19, L759–760; counts at L1125, L2250–2251 | `draw_through`: lines drawn on below dams and at outer-boundary entries | `06_map.py:114–281`, extended by the uncommitted edit (:227–246) | `03b_stitch.outflow_streams` + the `05_score.py` floor on carried water (L3099–3100, L3153–3154; `05_score.py:87–90`) | Yes below dams. The last entry says it had been hiding the gap: it "already drew a creek through below every dam and pond with the next reach's values: 927 of the 1,100 km" (L3202–3204), so maps showed lines the reach tables, ranks and profiles lacked |
| D5 | 11-20 ~16:00, L2383–2384 | Reaches lying in a lake left off the stream lines | `06_map.py:687–713` | `03b_stitch.route_lake` (L3096–3098) | Partly: the wrong names came from paths over flat water, which `route_lake` replaces |
| D6 | 11-20 16:34, L2393–2405 | `STREAMS_LAKE` copy shown while Lakes is off (repairs D5's own regression: `21266ec` went out with the lines hidden "whatever the Lakes switch, and the map of all areas lost its rivers at every lake") | `06_map.py:693`, `:1221`, `:1233`; `map_drainages.js:181–192`, `:510`; `map3d.html:116–117`, `:556`; `14_portable.py:22`, `:208` | none | Depends on A27 (undecided) |
| D7 | 11-20 16:30, L2870–2884 | A lake reach's stretch outside the lake drawn, cut at the shore; pieces under 20 m dropped (repairs D5: lines stopped 18.9 km short around Jackson Lake) | `06_map.py:714–834` | Shore cut in `05_score.py:95–106` via `flowlib.cut_at_shores` (`flowlib.py:279`); in `d06b50b`, **not in the log** | Yes once reaches are cut at shores. Instead the block gained code for the root fix's side effect (:787–807) |
| D8 | 11-20 22:56, L3021–3039 | Lake outlet's path drawn as "the lake's own creek" with borrowed values; every reach cut at the shore; 40 m stub rule | `06_map.py:179–255`, `:762–768` | `outflow_streams` + carried-water floor (11-21) | Yes: the creek below a lake now has reaches of its own (L3171) |
| D9 | 11-20 23:02, L2988–3019 | Straight joins across dams, from the line below the dam to the lake shore | `06_map.py:835–945` | `route_lake` + `outflow_streams` | Yes where the outlet pit is at the dam; with Fault 2 (A33) a join can meet a lake routed to the wrong end — PLAUSIBLE |
| D10 | 11-21 01:40, L3041–3082 | A lake reach's piece past the lake takes the values of the reach below or above | `06_map.py:776–819` | `route_lake` (same day) and the shore cut (`d06b50b`) | Yes |

Pattern (CONFIRMED from L2383 → L2393 → L2873 → L3027 → L3051 → `06_map.py:227–229`): six patches in about 30 hours,
each repairing an effect of the one before; then the root fixes of 11-21 arrived and none of the patches was removed.
The newest, uncommitted one exists because the root fix changed what `draw_through` meets ("530 m between Spencer Pond
and Big Pond in NE Connecticut, fish 15 for 57"). It is recorded only in the working-tree `README.md`.

Not patches: `simplify_together` (L685–686, `06_map.py:1494`) and the self-crossing outline repair (L308–309) are
drawing concerns. `12_profiles.py`'s `OWN_CAP` (L1158–1173) was followed by a root fix in `05_score.py`'s name vote
(L1189–1198) and is still needed for NHD lines drawn out to the river's centreline.

## 5. Licences, terms of use, consent, attribution

**Flagged: recorded as forbidding redistribution, or with no stated licence, and used or published all the same.**

| # | Source | What the log says | Lines | Now | Mark |
|---|---|---|---|---|---|
| F1 | **NY DEC ArcGIS stream layers** (`ny_trout`: Inland_Trout_Stream_Fishing, Water_Quality_Classifications, Trout_Stream_Fishing_Access) | Used from 11-19 ("All on DEC's ArcGIS Online", L1451–1455). 11-20: DEC's ArcGIS items say "secondary distribution of the data is not allowed"; "three stream layers the Adirondack maps already use carry that or stronger terms (Inland_Trout_Stream_Fishing: 'may NOT be distributed outside DEC without permission')" (L2646–2648). Listed as a follow-up (L2712); nothing after. No consent sought | L1451–1455, L2646–2648, L2712 | `troutdata.py:490–527` still reads all three; `lakesources.py:284–285` quotes the prohibition for lakes only. The four maps are `hidden=True` (`config.py:291, 311, 328, 343`) but "their pages stay at their addresses on the site" (L2857–2859) and were republished in `6875118`; "NYSDEC" occurs 7,866 times in adk_high_peaks' published data, 6,838 in adk_northwest's, 5,966 in adk_southwest's, 6,226 in adk_southeast's | CONFIRMED |
| F2 | **nnywaterfalls.com** (David J. Schryver) | "It is forbidden to distribute or otherwise exploit the content within this site in any form ... without the express written permission" (L1661–1663). Found after the first publish (`138467b`). User's decision 22:55: "keep both, ask both" (L1668); batch 2 (93 more rows) published after the terms were known (`5f7660b`, L1686, L1713). Its labels for unnamed falls kept as names (L1690–1691). Emails sent 11-20, "replies awaited" (L2524–2525) | L1634, L1660–1691, L2524–2525 | 116 rows in `data/known_falls_curated.csv`; present in the live hidden Adirondack pages | CONFIRMED |
| F3 | **World Waterfall Database** | "No part of this website may be reproduced in any form or redistributed without prior written consent." (L1664–1665). 106 rows: central_vt 44, adk_high_peaks 15, la 13, adk_northwest 13, adk_southwest 9, adk_southeast 6, smokies 6 (L1675). First-round rows went out on 11-19 15:45 (`93a2cc3`) before the terms were read. Same decision and email as F2 | L926, L1631, L1664–1685, L2524–2525 | 106 rows in the CSV; live on **shown** maps: the credit string occurs in the published central_vt (88), la (26) and smokies (24) data, and in the hidden Adirondack pages | CONFIRMED |
| F4 | **gawaterfalls.com** (Mark Ozboyd), 695 Georgia falls | "The layers carry no license and many names are his own, so they stay off the public site until the owner decides." (L941–943). Then "16:00, owner: 'Publish with credit'" (L1013–1015); published `38a2dd7`. "Owner" is the project's owner (as at L897, L1668, `README.md:227–228`), not the site's. No request to the author is recorded; the two consent emails went to F2 and F3 only | L941–943, L1013–1024, L1308 | `data/known_falls_curated_gawaterfalls.csv`, 695 rows; live in n_georgia (credited and linked) | CONFIRMED |
| F5 | **ncwaterfalls.com** | "ncwaterfalls.com states no terms." All 292 pages read by script | L1387–1388, L1633, L1667, L1686 | 4 rows in the CSV; live in smokies (15 occurrences in its published data) | CONFIRMED |
| F6 | Other guide sites behind the 143 first-round curated rows: New England Waterfalls, Vermont River Conservancy pins, Tom Chester's 1999 San Gabriel list, Caltech's canyoneering guide, RiverBrain | Listed as sources; no terms recorded for any | L924–930 | 36 CSV rows name New England Waterfalls | CONFIRMED that no terms are recorded; terms themselves unknown |

`README.md` records none of F1–F3: grep finds no "nnywaterfalls", "consent", "Inland_Trout" or "secondary distribution"
there; line 218 lists the World Waterfall Database as a plain source. The terms problem lives only in this log and
the memory notes.

**Other statements (not flagged).**

| Source | What the log says | Lines |
|---|---|---|
| EBTJV 2016 brook trout copy | "sits on a third-party host with no stated terms": not used; Trout Unlimited's portfolio used instead (TU's own terms not recorded) | L220–221 |
| First publish | Built pages "scanned for local paths, the user's email and LAN addresses: none". User chose to post "Everything" and "Keep the ZIPs" (home ZIP codes shown). No licence review recorded before going public | L598–607 |
| Closure feeds | "None needs an account or key". Not used: WYDOT ("its map data is obfuscated"), CTroads (registered key), 511NY (key). Used though "undocumented and may move": Virginia 511's map files. Blue Ridge Parkway closures read "from the park's web table". Idaho 511's WZDx feed needs no key | L462–472, L1465, L1555–1557 |
| NPS Great Smoky Mountains | Segments and the fish-barriers layer marked "Internal NPS Only" are left out | L1334–1337 |
| World Waterfall Database | "lidar picks with invented names" and "Unofficial" names left out; "Pages that withhold coordinates for posted land" left out | L931–934, L1637 |
| nyfalls.com, swimmingholes.org | "answers automated reads with a Cloudflare bot check"; shut down: neither used | L1635–1636 |
| data.ny.gov | "open terms": DEC's lake fishing list, launches, stocking since 2011 (e52k-ymww, mw8j-wduf) used for lakes | L2627–2630, L2642–2644 |
| HuntFishNY layer | "no stated licence or owner at DEC": not used | L2648–2649, L2713 |
| Adirondack Lakes Survey pond pages | "forbid automated access": not used | L2649–2650 |
| PFBC lake access points | used "with credit to PFBC as its licence asks" | L2635 |
| USACE Lanier transects; CA DWR multibeam; Lake George multibeam | "CUI-marked" / "Not public": not used | L1991–1992, L2651–2652 |
| Depths typed in from reports and papers | Larsen 2016, McGlue 2023, Stephens & Gipson 2005, Reclamation 2008, Virginia DWR contour map; no terms recorded | L990–993, L1990–1991 |
| GBIF records (MARIS, iNaturalist, USGS NAS, museums); iNaturalist sightings | used; licences not recorded (GBIF datasets carry their own) | L187, L984–985 |
| Vermont Fish & Wildlife map server | "refuses paged queries: `troutdata.fetch` asks for ids first" (a server limit worked around, not a licence) | L1981–1982 |
| StreamNet (Idaho cutthroat streams) | credited in popups "(IDFG, via StreamNet)"; terms not recorded | L1553–1555, L1611 |
| Esri World Imagery | used to check lake outlines; not published | L2010, L2655 |
| Earth Search Sentinel-2; Census TIGER/Line 2024; OSM relation 1695394 | "no key"; sources named | L2750, L2798, L1415 |
| OpenStreetMap (ODbL) | **Never mentioned in the log.** `README.md:455` says "share-alike applies if you publish the merged trail data itself"; the site publishes OSM-derived trail, road and parking layers | — (PLAUSIBLE gap) |
| NOAA ENC charts (Lake Champlain) | Not in the log; agreement quoted at `README.md:898–900`, `lake_bathymetry.py:302`, `:420` | — |
| Removal procedure | "To pull a site: move its rows (match `source`) into a `.held` file; then for each affected area run 02f, 05_score for each range, 06_map and 12_profiles, and publish" | L1684–1685 |

## 6. Timeline: what was built and published, when

Site commits, times and areas are from the site clone (`git log`, `git show --name-only`), not from the log, so
they are CONFIRMED. "What" is the log's claim. Times are Pacific up to `af1e0d2` and Eastern from `94566e0` on.

| Site commit | Time | Areas changed (files) | What the log says went out | Lines |
|---|---|---|---|---|
| `595be46` | 11-18 22:35 | local only, amended | first copy, with `.nojekyll` | L607 |
| `e965e59` | 11-18 22:48 | six areas + index (53) | first publish: six areas rebuilt from 03 on the fixed routing (22:17), default layers (22:40). Pushed by the user on 11-19 | L545, L619, L631–643 |
| `d23a486`, `3409314` | 11-19 08:12, 08:14 | six + index (19 each) | **pushed by mistake**: another session's unfinished drainage refresh | L650–657 |
| `2aefe20`, `31cab68` | 11-19 08:13, 08:15 | reverts | back to `e965e59` | L654–656 |
| `4d76f17` | 11-19 12:08 | six + index (19) | 03b joined routing, all six rebuilt. Carried the Snake overflow bug and the Guys Run flow bug | L797–806, L854–855 |
| `5696cf1`, `61fc692` | 11-19 13:13, 13:25 | index + preview.jpg | link-preview card. **Not in the log** | (L858) |
| `5ba0dcf` | 11-19 13:34 | six + index (25) | int32 fix (Jackson rebuilt from 03b), `minor_arms`, 05b stale-estimate rule; pushed by another session | L857–866 |
| `31efc26` | 11-19 15:27 | six + index (31) | drop-artifact rules (all six rebuilt from 04) | L885–903 |
| `c28add0` | 11-19 15:42 | se_pa + index (8) | SE Pennsylvania added. **Not in the log** | — |
| `93a2cc3` | 11-19 15:45 | central_vt, la, lexington_va, n_georgia, ne_ct (20) | known falls from every source (02f) | L948–956 |
| `af1e0d2` | 11-19 15:51 | profiles data of jackson, la, lexington_va, n_georgia, ne_ct (5) | profiles take drainage from the creek's own channel. central_vt not included | L1174 |
| `94566e0` | 11-19 19:18 | jackson (4) | Jackson lakes pilot | L1007–1012 |
| `38a2dd7` | 11-19 19:24 | n_georgia (3) | gawaterfalls list with credit | L1019–1024 |
| `739374b` | 11-19 19:27 | central_vt + index (5) | Vermont north box to Jeffersonville (full rebuild) | L1103–1107 |
| `458a1fe` | 11-19 19:43 | la, se_pa + index (7) | sea-level drainages (LA), se_pa known falls | L1148–1153 |
| `ffe5189` | 11-19 20:18 | central_vt + index (6) | Vermont north edge to 4,950,000; names-along-rivers | L1210, L1286–1288 |
| `f7d56a2` → `e5749e0` | 11-19 20:23, 20:25 | la, lexington_va, n_georgia, ne_ct (12); maps put back (8) | names-along-rivers; the three maps reverted (unbuilt Smokies in their menus), profiles kept | L1243–1248 |
| `e70326e`, `fb69421` | 11-19 20:34, 20:44 | ne_ct | Connecticut lakes; unit fix for 161 lakes | L1995 |
| `f674be0` | 11-19 21:48 | central_vt (3) | Vermont lakes | L2022 |
| `c6df975` | 11-19 22:05 | central_vt, ne_ct, se_pa, smokies + index (28) | imperial units; Smokies added | L1391–1398 |
| `aa7035d` | 11-19 22:14 | lexington_va + index (6) | Lexington lakes | L1520, L2022 |
| `138467b` | 11-19 22:17 | four adk_* + index (41) | Adirondack Park as four maps | L1519–1526 |
| `3c421fe` | 11-19 22:36 | jackson + index (13) | Jackson grown to seven boxes | L1614–1617 |
| `449abcd`, `96b604b` | 11-19 22:43 | central_vt, ne_ct | lake names from OSM | L2022 |
| `5f7660b` | 11-19 23:08 | smokies, adk_high_peaks, adk_southwest, adk_southeast (12) | falls batch 2; Piseco (05b in-lake line) fix | L1713–1716, L1851–1853 |
| `a742b5c` | 11-19 23:13 | ne_ct + index (4) | Piseco fix; Stiles Pond | L1854 |
| `c22ed4c` | 11-19 23:16 | central_vt, jackson, lexington_va, se_pa (12) | Piseco fix | L1859–1871 |
| `bf15161`, `7caab8b`, `38ef337`, `c9c8f60`, `97e45b8`, `5c8845e` | 11-20 00:29–00:47 | n_georgia, la, central_vt, ne_ct, la, lexington_va | lakes layers and lake fixes with the 05b fix | L1855, L1875, L2022 |
| `9363c92` | 11-20 10:25 | adk_northwest (3) | `mend_seams` (rebuilt from 03b) | L1950–1954 |
| `80562eb` | 11-20 10:35 | **all 12** + index (37) | cross-box scaled flows: 05b in all 55 boxes, 06 and 12 for all 12 | L2140–2159 |
| `3303d03` | 11-20 12:42 | **all 12** + index (49) | pond links, tie-break, 05b walk, weighted fit; shared data file layout | L2198–2265, L2455–2465 |
| `4cb3d68` | 11-20 13:43 | 10 areas + index (41); not se_pa, smokies | in-lake rule (05b), main-path trunks (05c) | L2272–2313, L2480–2489 |
| `2fcc91f` | 11-20 15:07 | **all 12** + index (49) | lakes on all 12, lake rules, 08_hike nearest shore | L2500–2508, L2659–2709 |
| `2db6522` | 11-20 15:54 | **all 12** + index (48) | dry-creek rule; lakes-layer in-lake rule; Lakes on by default | L2338–2349, L2772–2787 |
| `21266ec` | 11-20 16:25 | **all 12** + index (32; central_vt 7, jackson 4, others 2) | Vermont to the New York line (full rebuild from 01); Adirondack maps hidden; lake reaches drawn as lake | L2380–2394, L2837–2865 |
| `6d1eeef` | 11-20 17:41 | **all 12** + index (49) | edge-lake rule: ten areas rebuilt from 03b (not lexington_va; central_vt already); lake reaches back when Lakes is off; rivers drawn to the shore | L2408–2412, L2886–2939 |
| `68d952e` | 11-20 23:49 | **all 12** + index (46) | pass of 23:38–23:47: lake-line flow restore (05b in 25 boxes), joins across dams, outlets as own creek, shore cut. **Hash not in the log** | L2965–2968, L3007, L3034 |
| `855954f` | 11-21 01:53 | **all 12** + index (25) | 06_map-only pass of 01:40–01:51: lake-reach pieces take the river's values. Hash only at L3205 | L3065–3072 |
| `797a30e` | 11-21 19:47 | jackson + index (5) | `route_lake` / `outflow_streams` / tailwater floor: Jackson rebuilt from 03b 19:30–19:40, with the old 1 km² floor | L3125–3133 |
| `6875118` | 11-21 22:16 | **all 12** + index (49) | lake routing + carried-water floor on all 12. **Current live state** | L3167–3189 |
| — | 11-21 22:46 → | not published | `d06b50b` and the uncommitted `06_map.py` edit; a rebuild is running | X1, X2 |

**"All N areas rebuilt" claims, and how deep each rebuild went** (from the log; not verifiable from here):

| When | Claim | Steps rerun | Lines |
|---|---|---|---|
| 11-18 20:15 | "All six areas built from the same code" | full | L345 |
| 11-18 21:27–21:35 | "Every area rebuilt on the fixed routing" | 03 on | L476 |
| 11-18 22:17 | "all six areas rebuilt from `03_hydrology.py` on the same code" | 03 on | L545 |
| 11-19 morning | "all six areas rebuilt (`run_drainage_refresh.sh`...)" | 05c, 06, 12 only | L701 |
| 11-19 ~09:30–12:00 | 03b stitch, six areas | 03 on | L764, L778–790 |
| 11-19 ~13:00 | "All six areas ... rebuilt"; Jackson from 03b | 05c, 05b, 06, 12 | L834–835, L848 |
| 11-19 15:00 | "all six rebuilt from `04`" | 04 on | L885 |
| 11-19 19:40–20:01 | names-along-rivers: central_vt, lexington_va, ne_ct, n_georgia, la | 05_score, 05c, 11, 06, 12. **Not jackson, se_pa** (se_pa got it 11-20 evening, L2935–2937) | L1207–1210 |
| 11-19 22:54–22:56 | "05b ... in every box except adk_northwest's" | 05b; rendering split over three sessions | L1803–1816 |
| 11-20 10:2x–10:35 | "05b in all 55 boxes"; 06 and 12 for all 12 | 05b, 06, 12 | L2140–2146 |
| 11-20 12:08–12:33 | the package, all 12 | 05c, 05b, watertemp, 06, 12 | L2198–2251, L2441 |
| 11-20 13:24–13:39 | two more rules, all 12 (10 published) | 05c, 05b, 06, 12 | L2272–2305 |
| 11-20 13:23–14:51 | "Rebuilt, all 12 areas" (lakes) | 05d, bathymetry, 08, 09, 06, 12 | L2659–2663 |
| 11-20 15:24–15:52 | lakes-layer rule, then dry creeks, all 12 | 05b, 06, 12 (scoring.py edited mid-run, L2348) | L2341, L2772 |
| 11-20 16:00–17:39 | edge lakes: central_vt from 01; ten areas from 03b; lexington_va map step only | 03b, 04, 04b, mid, late; then 06, 12 for all 12 | L2837, L2888–2893 |
| 11-20 23:38–23:47 | all 12 | 05b in 25 boxes; 06, 12 | L2965–2966 |
| 11-21 01:40–01:51 | all 12 | 06 only | L3065 |
| 11-21 19:30–22:04 | all 12 from 03b (`SKIP_03=1`): jackson 19:30; ne_ct, lexington_va, se_pa before 20:11 with the old floor, then mid and late again; central_vt mid and late; smokies, n_georgia, la and the four adk_* from 03b after 20:24 | 03b on; 03 not rerun | L3125–3133, L3155–3168 |

Which code built the live site: by the log's account `6875118` was built on the scripts later committed in `dd639bf`
(19:50: 03b, scoring, 06_map) and `80b42e8` (20:26: 05_score, crossbox, run_mid); `40c2aa7` (22:28) touched only the
log and README. The
side-effects session's files were last written 22:31–22:57 and committed at 22:46; the log says that session "rebuilds
after this session has published" (L3166), and the site data shows none of its side-channel names (X2). Whether any of
its edits sat in `scripts/` during the 20:24–22:04 rebuild cannot be told from the log — PLAUSIBLE that none did.
`03_hydrology.py` (conditioned DEMs) last ran per area on different days: central_vt 11-20 16:00 (L2837); jackson,
smokies and the four adk_* on 11-19 evening (L1559–1574, L1348, L1473); la, n_georgia, ne_ct, lexington_va on 11-19
morning (L764, L789); se_pa unlogged.

## 7. Concision

**How it is built.** 3,227 lines, 291 KB, 38 `##` sections of 9 to 367 lines, each one session's narrative of one task.
By day: 11-18 55 KB (19 %), 11-19 115 KB (40 %), 11-20 103 KB (35 %), 11-21 17 KB (6 %). Entries mix five things
in prose: the user's request, the cause, the change, per-area numbers, and publishing and coordination with other
sessions. There is no index, no list of current rules, and no single list of open items: 37 lines carry "Open" /
"Still open" / "Left" / "Not done" / "Follow-ups" in 22 of the 38 sections, which is why §1 took a full read.

**What repeats.**
- Publish and verification boilerplate: "Published" 28 times, "SHA-256" 22, "no console errors" 27, "phone" 51,
  "byte for byte / byte-identical" 16. Lines with publish, commit or phone words: 322 lines, 33 KB.
- Session traffic: 236 lines (26 KB) name a session (who reran what, who publishes, who was told).
- Together with "checked / rendered / browser" lines these are 60 KB, about 20 % of the file, and none of it
  describes how the pipeline works now.
- The same mechanism re-explained in each entry that touches it: a river "starts again from nothing" below a lake
  or box edge (14 times); what `draw_through` does; what the 50 %-in-lake rule is.
- Superseded content kept at full length: rules "tried and dropped" (L495–497, L742–745, L2355–2372), first versions,
  intermediate layouts (Jackson's three, L1559–1574), numbers later revised (§2). All of 11-18's per-area result
  tables describe builds replaced at least five times.
- The standing checks are restated with fresh numbers in 7 entries, by 3 different scripts (§2 C3, C4).

**Proposal.**
1. **Freeze and archive** everything up to the last full rebuild as `docs/log_archive/2026-11-18_to_2026-11-21.md`
   (L1–L3196, 288 KB, verbatim, never edited again). Every area was rebuilt from 03b on 11-21, so nothing older
   describes a current build.
2. **`STATE.md`, about 30 KB, kept current** (edited in place, not appended):
   - *Current rules and constants*: one row each: rule, constant, `script:line`, the case it came from, areas it was
     measured on, date. About 70 rows, 12 KB. §3 is a start.
   - *Open items*: one line each with area, script, date, owner (user / a session / third party). About 45 rows,
     5 KB. §1A and §1B are a start.
   - *Sources and licences*: source, layer or URL, terms as read, date read, used where, credit shown, consent
     status. About 45 rows, 6 KB. §5 is a start. This is the register the terms problems of 11-19 and 11-20 lacked.
   - *Build and publish ledger*: one row per publish: time with zone, site commit, areas, deepest step rerun per
     area, project commit of the code. About 60 rows so far, 6 KB. §6 is a start.
   - *Standing checks*: the one script and definition for each (flow drops, dead reach ends, order-3+ gaps, lake
     outlets against NHDPlus, mapped falls found), 1 KB, so that "0" means the same thing each time.
3. **New log entries in a fixed short form**, 25 lines at most: When (with zone) / Session / Request / Cause /
   Change (`script:line`) / Measured on (which areas, which script) / Result / Published (site commit, areas) /
   Open. Per-area tables go to a results file beside the code, as the stream-burning session already does
   (`data/stream_burning/README.md`, `results/`), with a link. At that size the four days would have been about 40
   entries × 2 KB = 80 KB instead of 291.
4. **One rule for corrections**: when a later entry revises a number, strike the old one where it stands with a
   pointer forward. Today the reader of L3111 or L3173 has no way to know L3202 exists.
