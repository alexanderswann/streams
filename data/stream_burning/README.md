# Stream burning: NHD lines into the routing (lakes installed 2026-11-21; the DEM burn parked)

**Status:**
- **Installed 2026-11-21: NHD's lines through lakes** (`harness/patch_lakes.py`, now in `scripts/03b_stitch.py`).
  - `route_lake`: every cell of a lake that holds water drains to its outlet, along NHD HR's lines through the lake
    where they run.
  - `outflow_streams`: the way the water takes below the outlet is a stream line down to the first stream it meets.
  - It went in with a tailwater floor in `scripts/scoring.py`: a `TAILWATERS` reach with no gauge record gets full
    water credit.
  - Asked for by the user ("implement and commit the nhd stream burning") after the routing let Pilgrim Creek, not
    the Snake, cross Jackson Lake to the dam. Measured on all 12 maps first: see *Lakes* below.
  - **It needs `05_score.py`'s size floor to count carried water** (added the same evening): without it the creek
    below a lake's outlet is no longer a reach. See *What the lake measurement missed*.
- **Parked: the burn into the DEM itself** (`burnlib.py`, `patch_burn.py`), measured on 2026-11-20 on two whole
  maps. The user decided then to leave it out and keep it to come back to. It doesn't fix the lake crossings: at a
  lake that drains over a dam, filling raises the burned trench back to the water's level.
- **Log entries** in `MULTI_AREA_LOG.md`:
  - "2026-11-20, afternoon: burning NHD stream lines into the routing DEM";
  - "2026-11-21: NHD's lines through lakes";
  - "2026-11-21, evening: creeks below lake outlets".

## Lakes (installed 2026-11-21)
Measured with `harness/measure_area.sh` (each area's scratch copy from 03b, the live 03 outputs linked) against the
live build, all 12 maps; `harness/remeasure_05b.sh` after the lakes layer (05d's `lakes.gpkg`, which 05b reads) was
copied into the copies; totals by `checks/summarize.py`:

| all 12 maps | live | lake routing |
|---|---|---|
| straight made-up lines across lakes (300+ m runs) | 986 km | 266 km |
| lake outlets reading under half of NHDPlus (`lake_outlets.py`, the reach carrying the most water) | 45 | 39 |
| HR lines D8 misses (`hragree.py`) | 1,811 | 1,784 |
| NHDPlus V2 line ends under half | 669 | 677 |
| mapped falls found (`data/validate.py`, both passes) | 486 of 829 | 487 |
| known falls found (any source, 200 m, `falls.py`) | 1,025 of 2,127 | 1,025 |
| sudden flow drops; reach ends dead on an edge between boxes | 0; 0 | 0; 0 |
| reaches | 105,478 | 104,999 |
| km of fish 60+ | 42,159 | 41,911 |
| reaches moving 10+ fish-score points | | 265 up, 408 down |

- **Fixed:**
  - Jackson Lake's crossing (the Snake's line now runs to the dam; nothing crosses beside it).
  - Palisades (45 of 47 in-lake reaches named Snake River, against 6 of 46).
  - 120 creeks drawn carrying a lake's water lose it: Lower Slide Lake's 1,539 km² on a 2.7 km creek, Jenny, Leigh,
    Roseland and Bailey lakes' outlets, and others.
  - Lake Mathews' 111 km² reaches Temescal Wash (113 km² below it; NHDPlus 105).
- **The 10+ point moves** (by cause, `checks/drops.py`): of the 408 down, 276 are reaches that now read "reservoir"
  (their ends cross the 50%-in-lake line: the lines inside lakes follow NHD's, so the reaches split differently at
  the shores), 100 are the creeks above, which had carried a lake's water, 12 lost drainage another way, 12 changed
  flow class and 8 are other; of the 265 up, 213 left the "reservoir" class.
  - **Corrected 2026-11-21, evening:** the table's "reaches 105,478 → 104,999" and "km of fish 60+ 42,159 → 41,911"
    were first read as that lake-shore churn. Part of both was creek lines that vanished: see the next section.
  - LA's flow classes: about 20 Piru Creek reaches below Pyramid Dam would have gone from year-round to seasonal.
    Their natural-flow drainage had included Pyramid Lake's own shores through a path leaking out of the lake. The
    tailwater floor restores them, and 28 that the live build already showed mostly dry or seasonal.
  - Willow Creek (San Bernardinos, 6 reaches) drops a class for the same reason, without a release to keep it up.
  - One San Jacinto River reach changes its NHDPlus line match at a junction and loses its gauge record.
- **Checked by picture:** Jackson Lake, Palisades, Leigh / String / Jenny lakes, Lower Slide Lake, Roseland Lake, and
  the Indian River below its reservoir.

## What the lake measurement missed (2026-11-21, evening)
Found while breaking the 408 drops down by cause for the overview session (the user's rule: mark a stream down only
when near-certain). The checks above compare the reaches two builds share. `checks/drops.py` also lists the lines only
one build has, and the measured lake-routing builds lacked 197 creek reaches (286 km) of the builds before: not lake
reaches, 200+ m outside every lake outline.

- **Cause.** `05_score.py` kept a stream link when its own D8 drainage was 1 km² or more. A lake ends its paths at
  its outlet, so the creek below starts again near nothing: its links stayed under the floor until it had gathered
  1 km² again or met a creek that had. Where the old builds did draw that stretch, a path had leaked across the lake
  and left it beside the outlet. `route_lake` sends every lake cell to the outlet, so those stretches went:
  102 links, 103 km over the 12 maps (83 km of it fish 60+). North-west Adirondacks: 1.5 km of the Oswegatchie, the
  Raquette between Raquette Lake and Forked Lake, Salmon Lake Outlet, South Pond Outlet, Cage Lake Outlet. Jackson
  (published 19:49 with it): Emma Matilda Lake's outlet and three more, 3.4 km.
- **The gap behind it** (`checks/outlet_gaps.py`, on the 12 lake-routing builds): stream links (`dem_streams.gpkg`)
  under 1 km² of their own that carry 1 km² or more with the water crossbox links to them, and that no reach covers.

  | map | links | km | along an NHD stream line | drawn before the lake routing |
  |---|---|---|---|---|
  | adk_northwest | 336 | 255.0 | 247.7 km | 35.3 km |
  | adk_southeast | 282 | 204.4 | 194.2 km | 17.1 km |
  | adk_southwest | 223 | 170.1 | 163.7 km | 12.2 km |
  | adk_high_peaks | 199 | 129.7 | 125.8 km | 6.8 km |
  | ne_ct | 139 | 95.5 | 91.5 km | 5.7 km |
  | n_georgia | 100 | 67.2 | 55.9 km | 7.1 km |
  | central_vt | 65 | 46.3 | 45.0 km | 4.7 km |
  | la | 62 | 43.4 | 38.5 km | 8.7 km |
  | jackson | 48 | 32.8 | 28.6 km | 3.4 km |
  | se_pa | 27 | 16.7 | 15.4 km | 2.2 km |
  | lexington_va | 18 | 13.6 | 11.1 km | 0.0 km |
  | smokies | 21 | 12.8 | 12.0 km | 0.0 km |
  | all 12 | 1,520 | 1,087.5 | 1,029.4 km | 103.2 km |

  185 of the links carry 100 km² or more: rivers below dams, and rivers where they enter a map.
- **Fix** (`scripts/05_score.py`, `scripts/crossbox.py`, `scripts/run_mid.sh`): the floor counts the water that
  reaches the link from elsewhere (`crossbox.carried_km2`: every `inflows(through_dams=True)` entry's area added down
  its D8 path, as 05c does for `area_full_km2`), sampled where the link's own area is. `run_mid.sh` runs
  `02b_download_flow.py` before `05_score.py`, since crossbox needs the reservoir list and NHDPlus's lines.
- **Jackson rebuilt with it** (mid and late, 20:13-20:22): 54 links, 33 km kept on carried water; none left undrawn.
  Against the build before any of this: creek lines gone 8 → 3 (one drains 0.95 km² once the lake's cells no longer
  pad it, one is drawn 116 m away, one is 141 m at a lake's edge), 49 new creek reaches (40 km, 26 km of it fish 60+), km of
  fish 60+ 5,588 → 5,607, flow drops 0, mapped falls 12 of 21 as before. On the rendered map: Emma Matilda Lake's
  outlet creek, Taggart Creek from its lake, the Snake from Palisades Dam.
- **Lesson for the next routing change:** run `drops.py` against the build before. A reach count that falls
  (105,478 → 104,999 here) is lines lost, whatever the matched reaches say.

## Installed on all 12 maps (2026-11-21; live 22:18, site commit 6875118)
Both changes, the lake routing and the floor that counts carried water, built into every map and checked against the
builds before either (`results/installed_2026-11-21/`). Jackson by mid and late steps from 20:13; ne_ct,
lexington_va, se_pa and central_vt the same way from 20:24; smokies, n_georgia, la and the four Adirondack maps from
03b (`SKIP_03=1 run_rebuild_a.sh`), the last done 22:04.

| map | links kept on carried water | km | reaches, before → now | km of fish 60+ | 10+ points down (lake / lost a lake's water / other) | up |
|---|---|---|---|---|---|---|
| jackson | 54 | 33.0 | 10,528 → 10,553 | 5,588 → 5,607 | 27 (18 / 5 / 4) | 29 |
| ne_ct | 155 | 96.7 | 3,419 → 3,588 | 1,189 → 1,204 | 42 (16 / 17 / 9) | 14 |
| lexington_va | 18 | 13.6 | 4,287 → 4,302 | 1,397 → 1,402 | 1 (1 / 0 / 0) | 1 |
| se_pa | 26 | 14.9 | 4,623 → 4,638 | 1,392 → 1,402 | 1 (1 / 0 / 0) | 4 |
| central_vt | 63 | 45.5 | 8,298 → 8,358 | 3,489 → 3,507 | 14 (6 / 6 / 2) | 3 |
| smokies | 21 | 12.9 | 8,947 → 8,921 | 3,800 → 3,812 | 14 (7 / 2 / 5) | 13 |
| n_georgia | 104 | 67.5 | 14,912 → 14,945 | 5,379 → 5,399 | 29 (21 / 5 / 3) | 15 |
| la | 65 | 43.8 | 17,805 → 17,867 | 1,389 → 1,396 | 21 (4 / 0 / 17) | 36 |
| adk_southwest | 232 | 170.9 | 6,815 → 6,999 | 4,493 → 4,608 | 43 (31 / 9 / 3) | 31 |
| adk_northwest | 355 | 256.5 | 8,279 → 8,492 | 4,747 → 4,899 | 91 (63 / 18 / 10) | 51 |
| adk_high_peaks | 219 | 131.6 | 9,138 → 9,306 | 5,055 → 5,129 | 79 (53 / 20 / 6) | 33 |
| adk_southeast | 298 | 205.5 | 8,427 → 8,640 | 4,241 → 4,357 | 92 (63 / 19 / 10) | 60 |
| all 12 | 1,610 | 1,092 | 105,478 → 106,609 | 42,159 → 42,721 | 454 (284 / 101 / 69) | 290 |

- **Every build check passes on all 12:** no failed step; 03b's rasters and drops equal the measured lake-routing
  builds (`verify_install.py <root> hydro`); no reach ends dead on an edge between boxes; no sudden flow drops;
  mapped falls found as in the measured builds.
- **Stream links below outlets** (`outlet_gaps.py`): 1,622 links, 1,100 km (95% along NHD's stream lines, 199
  carrying 100+ km²); all drawn but 7 (3.0 km): three at sea level on the tidal Delaware (se_pa) and four west of
  Vermont's line in Lake Champlain's New York shore (central_vt), which other rules leave out.
- **Lake outlets reading under half of NHDPlus** (`lake_outlets.py`): 45 before, 39 with the lake routing alone,
  26 now. Lake Junaluska (0.96 of NHDPlus), Little Rock Reservoir (1.00) and The Vly (1.00), which the lake routing
  alone had made worse, are right.
- **Stream line drawn with a lake's values outside the lakes the map draws** (`drawn_lake_values.py`): 390 → 173 km.
  341 pieces (223 km) of creek are put right; 48 pieces (22.5 km) are newly marked down, 45 of them fish 40+ before:
  headwater reaches lying half or more in a lake. Theirs is 05b's 50%-in-lake rule, which the session "Fix the
  lake-routing side effects and open items" is changing.
- **Creek lines only one build has** (not lake reaches, 200+ m outside every lake outline): 1,196 new (983 km, 695 km
  of it fish 60+) against 121 gone (174 km).
  - Of the gone, 20 (32 km, 14 km fish 60+) lie along an NHD stream line with no reach of the new build nearby
    (`why_gone.py`). One is the Lamoille's line inside Arrowhead Mountain Lake, now a lake reach, with the river
    drawn from the dam.
  - The other 19 are headwater creeks whose own drainage is 0.52-0.99 km² where they now end, with no water carried
    to them: under the floor. The build before drew each as part of a longer link that reached 1 km² further down;
    a new line (a lake's outlet line, NHD's line through a lake) now joins it and ends the link there, or lake
    cells that had padded it drain to the lake's outlet. Finkle Brook's upper 1.4 km (0.86 km²) is one.
- **The 10+ point moves down, 454** (`drops.py` against the builds before, `why_moved.py` for the terms):
  - 284 now read "reservoir": half or more of the reach lies in a lake. 185 of them were fish 60+. 37 have 200+ m
    outside every lake outline (24 km of creek in all).
  - 101 had carried a lake's water that belongs to another line. Where NHDPlus V2 has a line by the reach (40 of
    them), the new drainage is within 0.5-2x of V2's on 34; the old was on 6. 46 of the 101 still score 60+.
  - 69 other (18 lost drainage another way, 12 changed flow class, 39 neither). 48 of them are reaches cut
    differently: a newly drawn line joins the creek, the reach ends there, and each piece is scored on its own.
    - 11 pieces no longer touch the trout record the whole reach touched (a state trout-water line, a brook trout
      patch, a survey point) and lose the 1.2 factor: the Opalescent 100 → 88, Kunjamuk River 92 → 74, Stewart
      Brook 88 → 74, the Oswegatchie 83 → 70, West Branch Sacandaga 82 → 68, Doyle Brook 84 → 70.
    - 12 are short flat open pieces beside a lake (20-700 m) that lose gradient and shade credit.
    - The rest are upper pieces with less drainage than the whole reach had at its lower end.
  - LA, 17: Willow Creek below Lake Arrowhead (7 reaches) and the South Fork San Jacinto below Lake Hemet (2): LA's
    flows leave out water held behind a dam, and both lakes now end at theirs. 4 small creeks that left a lake's
    outline and read mostly dry like their neighbours. One Piru Creek reach just above its gauge above Lake Piru
    (73 → 25): its drainage crossed the size at which the gauge's record (flowing 31% of summers) applies, as it
    does on the 7 reaches below it. Three more are small pieces, two of them inside lakes.
  - Smokies, 4 (Mingo Creek): the way in is 31 minutes shorter (no ride), which lowers remoteness. Not routing.
  - 244 reaches in all went from 60+ to under 60 (lake 185, lost a lake's water 44, other 15); 154 went the other way.
- **Checked on the rendered maps:** adk_northwest (Salmon Lake Outlet 100, South Pond Outlet 89, Cage Lake Outlet
  91, the Raquette from Raquette Lake to Forked Lake at 114 sq mi), ne_ct (four pond outlets), la (Piru Creek),
  jackson (Emma Matilda Lake's outlet, Taggart Creek, the Snake below Palisades Dam).
- **Left open:**
  - Lower Piru Creek below Lake Piru (19 reaches) now reads year-round, fish 64-73, where it read mostly dry: the
    tailwater floor reaches it because `scoring.tailwater()` takes Piru Creek by name below 700 m and doesn't stop at
    Lake Piru. The rating is right (USGS 11109800 below Santa Felicia Dam: 7 cfs or more on every July-September
    day on record since 2011), but the popup credits Pyramid Lake's releases. A `TAILWATERS` entry for Lake Piru would name the right dam.
  - 31 short reaches in adk_northwest (4.9 km) carry a river's stream order with a creek's drainage; 29 did before.
  - The first 0.4 mi of the Snake below Palisades Dam has no name on it.

## The question
In flat ground the 10 m DEM's D8 routing can send a creek's water somewhere other than where NHD's stream network
sends it. The idea: lower ("burn") NHD HR's stream lines into the DEM before routing. Does that fix those places,
and at what cost?

## What was measured

### The problem is smaller than it looked
The count that started this was 826 reaches named after the NHDPlus V2 line they lie on, with under a quarter of
its drainage.
- **About half are side arms of split rivers.** D8 sends all the water down one arm, so the other reads only its
  own small drainage. No burn changes this.
- **Most of the rest are an artefact of that comparison.** V2 gives a line's drainage at its lower end. These
  reaches sit near the top of long V2 lines: in jackson and central_vt, a median of 15-18 % of the way down lines
  of 9-10 km, and 88-95 % of them in the upper half. Against NHD HR's own network their drainage is normal (km of
  HR line upstream per km2 of our drainage is the area's usual density).
- **The West Branch Beaver (adk_northwest) is V2's own network.** V2 sends Twitchell Creek's 50 km2 east into the
  West Branch. HR's lines and the DEM both send it north-west into Stillwater Reservoir.
- **Real disagreement with NHD HR is small.** `checks/hragree.py` asks, for each HR line, whether the D8 path from
  its middle reaches its end or the lines below it. It fails on 0.2-2.7 % of HR lines across 7 areas, mostly small
  lines in flat lowlands and wetlands (se_pa's 2.7 % is the tidal Delaware).

### Burning every NHD line hurts the waterfalls
Window test, n_georgia's rabun box, 19 x 19 km with 50 mapped falls:
- The DEM already agreed with every HR line there.
- At every depth tried (1, 3, 10 m), the burn lost 3 of the 4 waterfall-like steps and added 5 / 13 / 89 false
  cascades: burned paths run beside a fall instead of over it. Rejected.

### Burning flat ground only
The burn: lines lowered 3 m where the 50 m mean slope is under 5 %, and nothing within 2 km of an area's outer edge.
Without that edge rule, burned lines led the Deer River, the St. Regis and the West Branch Oswegatchie off the map.
Measured on whole areas, against baselines that reproduce the live builds byte for byte:

| | adk_northwest | jackson |
|---|---|---|
| HR lines D8 misses | 131 → 109 | 169 → 112 |
| NHDPlus V2 line ends where we read under half | 71 → 56 | 107 → 98 |
| reaches moving 10+ fish-score points (up / down) | 58 / 56 | 126 / 119 |
| km of drawn stream lines moving 20+ m | 741 of 6,963 | 753 of 9,240 |
| known falls found (both drop passes, 200 m) | 29 → 29 of 81 | 13 → 13 of 27 |
| sudden flow drops (`data/check_flow_drops.py`) | 0 → 0 | 0 → 1 |
| dead ends on edges between boxes; lake outlets under half | 0 → 0; 9 → 9 | 0 → 0; 0 → 0 |

- **Fixed:**
  - adk_northwest: the Raquette between Simon Pond and Raquette Pond (about 2 → 1,485 km2 on its reaches), stretches
    of the St. Regis and the Oswegatchie, and Sucker, Hopkinton, South Creek, Dan Wright and Indian River brooks.
  - jackson: the Snake fits V2 better (45 → 53 of its V2 lines within 0.67-1.5x), and so do the Salt and the
    Teton's Spring Creek arm.
  - Both: straight flat-resolution lines across wetlands and lakes drop by about a quarter in adk_northwest.
- **Made worse:**
  - Braided valley-floor rivers swap which arm carries the river. The lower Gros Ventre's named arm drops
    1,600 → 15 km2, and one Teton River stretch 1,042 → 71.
  - Windfall Brook drops 20 → 1, and one Raquette arm too.
  - A new sudden flow drop (teton_valley:s636).
  - In adk_northwest, 56 reaches swing 50-70 points only because their ends cross the 50 %-in-lake line of the
    "reservoir" class.
- **Overall:** jackson's 10+ point moves by drainage are 99 up and 91 down, a reshuffle. Fish 60+ km:
  adk_northwest 4,801 → 4,720, jackson 5,604 → 5,565.

### Verdict
Not worth installing as it stands.
- It fits NHD's lines better, but leaves the maps' content about level: a reshuffle in jackson, a small gain with as
  much churn in adk_northwest.
- It adds a flow-drop error.
- Installing changes every reach id and needs a full rebuild (`run_rebuild_a.sh`) and republish of all 12 maps.

## If we come back to it
Ideas, in the order they look most promising:
- **Burn only where the routing disagrees.** Burn just the HR lines `hragree.py` flags on the unburned build, plus
  their way on downstream, on flat ground. That would keep fixes like the Raquette without reshuffling braided rivers
  or moving lines elsewhere. Reach ids would still change wherever a box's routing changes.
- **Braided rivers.** Prefer NHDPlus's main path at splits, for example by burning lines that lie on V2 main paths
  (divergence 0/1) a little deeper than minor ones (divergence 2).
- **Side arms**, half of the original count, aren't a routing question. They would need a label ("side channel of
  the Snake") or the main river's size for the score.
- **The lake-class churn** comes from the 50 %-in-lake rule meeting new reach ends, not from the burn as such.
- **`checks/hragree.py` and `checks/v2_ends.py` are better routing checks** than the short-named count. Worth
  making standing checks in `data/` for any future routing change.

## How it works
- `harness/burnlib.py` builds the burn.
  - Lines: StreamRiver, ArtificialPath and Connector from every box's `nhd_flowlines.gpkg` (each box's file reaches
    0.5-3.7 km past its box, so together they cover any halo); canals, pipelines and coastline left out.
  - Rasterized one cell wide and lowered `BURN_M` m.
  - Only where the ground's 50 m mean slope is under `BURN_SLOPE` (0 = everywhere).
  - Not within `BURN_EDGE_M` m of the area's outer edge (edges between boxes are inside).
- `harness/patch_burn.py` patches a copy of `scripts/`:
  - `03_hydrology.py` keeps its unburned fill for `dem_filled.tif` / `fill_depth.tif` (what drops, profiles and
    crossbox measure on) and conditions the burned DEM for `dem_cond.tif` (the routing surface).
  - `03b_stitch.py`'s `condition()` (the seam mends) burns its piece of raw DEM the same way.
  - With `BURN_M=0` both run exactly as before.
- Lakes: the HR line through a lake that holds water is burned like any flat line. The lake drains along it to NHD's
  outlet, which 03b's lake rule then takes as the cell where paths end.
- Seams: every box's halo is burned from the same lines, so both sides of a shared edge see the same surface. 03b
  mended every dead end on a shared edge in both test areas.

## Rerunning the measurement
Put the roots outside the repo: they hold 0.5-1.5 GB per area once built. One heavy step at a time: 03 peaks at
2.8 GB on a big box, 03b at about 2.5 GB. If another session is about to publish, pause: `publish_site.sh`'s
build guard can't tell a scratch 03b from a real build.
```
H=/Users/mac/Fishing/data/stream_burning/harness
$H/setup_root.sh /private/tmp/burn/r0 adk_northwest      # baseline copy
$H/setup_root.sh /private/tmp/burn/r3e adk_northwest     # burned copy
# baseline: copy the project's dem_cond / dem_filled / fill_depth into r0/data/derived/<area>/<box>/, then start at 03b
BURN_M=0 $H/run_chain.sh /private/tmp/burn/r0 adk_northwest 03b
BURN_M=3 BURN_SLOPE=0.05 BURN_EDGE_M=2000 $H/run_chain.sh /private/tmp/burn/r3e adk_northwest 03
$H/run_checks.sh /private/tmp/burn/r0 adk_northwest
$H/run_checks.sh /private/tmp/burn/r3e adk_northwest
$H/compare.sh /private/tmp/burn/r0 /private/tmp/burn/r3e adk_northwest
```
- `setup_root.sh` copies `scripts/` (patched), links the raw inputs one file at a time, and copies the area's
  `_shared` (its `cache/` linked). Nothing in the project is written.
- `run_chain.sh` runs 03 → 03b → 04 / 04b → 05_score → 05c → 05b. It takes `BOXES="a b"` to condition only some
  boxes, and starts at `04` to resume after a finished 03b. Each step's time and memory go in
  `<root>/data/chain_<area>.log`.
- `run_checks.sh` runs everything below.
  - `score_root.py` gives the root's reaches fish scores without the late steps. Access, sun and context come from
    the project's reach nearest each new reach (they belong to the place, not the routing); area, flow and reach
    attributes come from the root's own build. It refuses to run on the project.
  - Then `standing.py` (lowest drainage, dead ends on shared edges, order-3+ cells with no reach), `short_named.py`,
    `classify_short.py`, `v2_ends.py`, `hragree.py`, `lake_outlets.py`, and the root's `check_flow_drops.py` and
    `validate.py`.
- `compare.sh` lists the reach moves (`compare_roots.py`), how far the lines moved (`moved.py`), straight runs
  (`straight.py`) and known falls found (`falls.py`).
- A baseline that doesn't reproduce the live build means the pipeline has changed under it. Check flowdir,
  area_km2, knickpoints and streams_scored byte for byte before trusting a comparison.
- Window tests, quick and light (a 15-20 km window in a few seconds):
  - `window_hr.py` scores depths by HR agreement;
  - `window_drops.py` scores them by drops and known falls (it copies 04's detector);
  - `window_plot.py` draws two depths side by side.
  - Set `NUMBA_CACHE_DIR` to a scratch folder when importing `03b_stitch.py` from tests, so no numba cache lands in
    `scripts/__pycache__`.
- One pitfall already met: scipy's `uniform_filter` keeps a running sum, so one `inf` turns the rest of its row into
  NaN. `burnlib.flat()` gives no-data cells 1e3 instead.

## Files
- `harness/`:
  - the DEM burn (parked): `burnlib.py`, `patch_burn.py`;
  - the lake routing (installed): `patch_lakes.py`, which patches a `scripts/` copy (or the project) exactly as
    measured;
  - scratch builds: `setup_root.sh`, `run_chain.sh` (starts at 03, 03b, 04 or 05b), `run_checks.sh`, `compare.sh`;
  - whole-area measuring against the live build: `measure_area.sh`, `remeasure_05b.sh`;
  - windows: `window_hr.py`, `window_drops.py`, `window_plot.py`.
- A scratch copy needs the area's lakes layer, which 05b reads: copy `data/derived/<area>/_shared/lakes.gpkg` into
  it, or its reservoir classes differ from the live build's.
- `checks/`: the measures above, plus:
  - `summarize.py` (one table over the measured areas);
  - `hr_density.py` (HR km per km2 of drainage for flagged reaches);
  - `xref.py` (flagged reaches against nearby HR misses).
  - `drops.py` (two builds of one area: the 10+ point fish-score moves by cause, and the lines only one has);
    `outlet_gaps.py` (stream links under 05_score's floor that carry a lake's water); `drawn_lake_values.py` (stream
    line a map draws with a lake's values outside the lakes it draws, in two versions of its `map3d_data.js`);
    `summarize_drops.py` (their CSVs over the areas); `verify_install.py <root> hydro` compares only 03b's rasters
    and the drops.
  - `why_moved.py` (which score terms moved for the moves in a cause group, and whether the reach was cut
    differently); `why_gone.py` (what 03b has now along a creek line only the older build draws); `totals.py`
    (reaches, km, km of fish 60+ per area for any builds).
  - Since 2026-11-21, `lake_outlets.py` takes the reach carrying the most water within 150 m of NHDPlus's outlet
    point (the nearest one was often a side creek), and `standing.py` counts a reach that starts in the same box as
    continuing a reach end on an edge.
- `results/`: the 2026-11-20 runs.
  - `checks_r0_*` baseline, `checks_r3e_*` the burn above, `checks_r3_adk_northwest` the same without the edge rule.
  - `compare_*` the comparisons; `hragree_live_6_areas.txt`; `classify_short_live_12_areas.txt`.
  - `lakes_2026-11-21/`: the lake routing's 12-area summary and per-area checks and comparisons.
  - `installed_2026-11-21/`: the 12 installed builds (lake routing and the carried-water floor) against the builds
    before: totals, moves by cause, the named cases, lines gone, lake outlets, each area's checks.
