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
- **Parked: the burn into the DEM itself** (`burnlib.py`, `patch_burn.py`), measured on 2026-11-20 on two whole
  maps. The user decided then to leave it out and keep it to come back to. It doesn't fix the lake crossings: at a
  lake that drains over a dam, filling raises the burned trench back to the water's level.
- **Log entries** in `MULTI_AREA_LOG.md`:
  - "2026-11-20, afternoon: burning NHD stream lines into the routing DEM";
  - "2026-11-21: NHD's lines through lakes".

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
- **The 10+ point moves:**
  - Mostly reaches whose ends now cross the 50%-in-lake line of the "reservoir" class (the lines inside lakes follow
    NHD's, so the reaches split differently at the shores). About 3 down for every 2 up.
  - The creeks above (all down).
  - LA's flow classes: about 20 Piru Creek reaches below Pyramid Dam would have gone from year-round to seasonal.
    Their natural-flow drainage had included Pyramid Lake's own shores through a path leaking out of the lake. The
    tailwater floor restores them, and 28 that the live build already showed mostly dry or seasonal.
  - Willow Creek (San Bernardinos, 6 reaches) drops a class for the same reason, without a release to keep it up.
  - One San Jacinto River reach changes its NHDPlus line match at a junction and loses its gauge record.
- **Checked by picture:** Jackson Lake, Palisades, Leigh / String / Jenny lakes, Lower Slide Lake, Roseland Lake, and
  the Indian River below its reservoir.

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
  - Since 2026-11-21, `lake_outlets.py` takes the reach carrying the most water within 150 m of NHDPlus's outlet
    point (the nearest one was often a side creek), and `standing.py` counts a reach that starts in the same box as
    continuing a reach end on an edge.
- `results/`: the 2026-11-20 runs.
  - `checks_r0_*` baseline, `checks_r3e_*` the burn above, `checks_r3_adk_northwest` the same without the edge rule.
  - `compare_*` the comparisons; `hragree_live_6_areas.txt`; `classify_short_live_12_areas.txt`.
  - `lakes_2026-11-21/`: the lake routing's 12-area summary and per-area checks and comparisons.
