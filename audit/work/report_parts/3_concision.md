## 3. Concision: what can go, and what has to move first

The code is 16,900 lines in 55 files. Little of it is dead in the plain sense: a word search finds one unused
constant. The waste is of another kind: the same job done in several steps with slightly different definitions, and
later steps repairing what an earlier step leaves. Deleting the repairs is only safe after the cause is fixed, so
this section is ordered by cause.

### 3.1 The drawing step, and the three causes behind its rules

`06_map.py` (1,541 lines) is meant to draw what earlier steps computed. On the live builds it still changes stream
features on this scale (its own counters in `data/late_<area>.log`; per-area table T9 below):

| Rule in `06_map.py` | Lines | Still changes (12 areas) | Verdict |
|---|---|---:|---|
| Final fish score computed here | 73 | all 110,665 reaches | move to a scoring step that writes the table |
| Stream order raised where water is carried in | 84-105 | 9,122 reaches | move to 03b / 05c; has the order-7 fault |
| `draw_through`: lines drawn below dams, ponds and at the outer edge | 106-283 | 1,138 lines, 137 mi | keep for rivers entering the map; the dam and pond part goes with cause A; 35 lines are dead branches (144-148, 158-176, 212-221) |
| Basins joined across box edges, unnamed outlines placed, sliver drainages | 289-468 | 28,497 joined, 6,915 placed | move to one area-level pass after 05c |
| Reaches lying in a lake moved to the Lakes-off layer | 695-713 | 8,614 reaches | remove; use the flag the reach already has |
| Every reach clipped at every drawn lake's shore | 732-753 | 15,160 reaches, 10,688 pieces | keep until cause B is fixed, then it only assigns layers |
| Shore stubs dropped; slivers under 66 ft dropped | 754-768, 820-826 | 2,863 stubs | remove after cause B |
| Lake-end pieces given the neighbour reach's values | 769-819 | 1,123 pieces | remove after cause B |
| Straight joins across dams; pieces to a pit by the dam | 835-939 | 949 joins, median 23-59 ft | remove after cause A |
| " (side channel)" added to the name | 949-952 | 215 names | pass a flag, let the page add the words |

**Is `draw_through` still needed?** Measured on the live build (`draw_through_test.py`, `draw_through_*.csv`). Its
1,138 additions come to 136 mi:

| What the addition is | Additions | Miles |
|---|---:|---:|
| A second line within 26 ft of a reach that is already there | 459 | 10.8 |
| Under 50 ft long | 241 | 1.1 |
| A river entering the map, drawn from the edge to the first reach | 211 | 65.0 |
| Below a dam or pond, carrying 0.39 sq mi or more | 150 | 33.3 |
| Below a dam or pond, carrying less than the map's own 0.39 sq mi floor | 77 | 25.5 |

So 700 of its 1,138 actions (62 %) add nothing. The 65 mi where rivers enter the map are its real job today. The
33 mi below dams include the first stretch of big rivers that exist on the map only as these borrowed-value lines,
not as reaches with a score and a profile: the Little Tennessee below Chilhowee Dam (1.8 mi, 35.546, -84.050), the
Chattahoochee below Buford Dam (0.5 mi, 34.16, -84.08), the Lamoille below Arrowhead Mountain Lake (0.4 mi, 44.64,
-73.11), the Snake at the head of Palisades Reservoir (0.5 mi, 43.17, -111.06). The 25 mi below small dams and ponds
are creeks the size floor would not draw anywhere else. Once the outlet is fixed (cause A) and
rivers entering the map are seeded as reaches the way lake outlets now are, all 175 lines of it can go.

**Cause A: the one-cell gap at every lake outlet.** `03b_stitch.py` ends each lake's water in a pit at the outlet
cell (`:577-578`) and starts the outflow line in the next cell (`:428`). Everything downstream then finds the water
again: `crossbox.py` scans for the dead ends, walks NHDPlus's outlet line, falls back on NHD HR for ponds and moves
the cell back to the routed way out (`:230-391`, about 160 lines; 85 % of the time it ends at the cell 03b already
knew); `05_score.py:86-90`, `:161-176` and the drop detectors count the carried area; `05b_flow.py` jumps the pit
and floors what it finds; `05c_drainages.py` rejoins the basins (its own `pond_links`, `:446-506`, repeats crossbox
and now joins 1 basin of 1,234); `06_map.py` estimates the order back and draws the join. At least 59 pitted lakes
pass nothing on, and no log line names them. Letting the water run on at the outlet, and taking the outlet from NHD's
line leaving the lake (finding 8), removes the need for all of it except closed lakes and rivers from outside.

**Cause B: "which water is a lake" is decided five ways.** `flowlib.py:135-153` (the pits), `:156-180` (reservoirs
of 20 acres), `:199-207` (the lakes layer, level in the lidar), `03b_stitch.py:632-638` (lakes that drain off the
map), `flowlib.py:232-243` (a lake is "wet" only in the box holding its pit). Reaches are cut at one set with a
165 ft tolerance and drawn against another from 1.2 acres. Hence three in-lake tests and three "reservoir" patches in
`05b_flow.py:576-598`, and four clipping rules in the map step. One set of outlines (the drawn ones), cut once in
`05_score.py`, makes "creek or lake" a property of the reach.

**Cause C: values that exist only in the map step.** The final score, the raised order and the renamed drainages are
made while drawing, so `stream_reaches_ranked.csv` is an export of the map step, `12_profiles.py` reads the score
from there, a lake's popup shows the drainage from before the renaming, and every check that reads a per-box table
sees something else than the map. A scoring-and-naming step that writes one area table, which the map and the
profiles both read, ends that.

{{T8}}

**Lines.** With the three causes fixed, about 300 lines leave `06_map.py`, 150 `crossbox.py`, 150 `05b_flow.py`,
60 `05c_drainages.py` and 40 `05_score.py`: roughly 700. The gain that matters more is one definition each of lake,
outlet and reach, and a table that equals the map.

**Risk.** High if done blind: these rules touch a fifth of all reaches. Do it in a scratch clone on one small area
first, with the standing checks of 3.6 before and after, then all 12.

{{T9}}

### 3.2 Smaller layering in the core steps

- Five separate rules say "an inherited flow estimate never puts a reach below NHD's class", each written for one
  case (`05b_flow.py:518`, `:532`, `:556`, `:568`; `scoring.py:265-273`). A plain in-box inherited estimate has no
  such floor (the helpers count 1,229 NHD-perennial reaches below their class that way). One rule replaces the five
  (about 75 lines) and closes the gap.
- Reach names: a three-point vote, then two repair passes for its two kinds of error (`05_score.py:124-132`,
  `:149-207`, `:209-278`; 1,243 + 668 reaches renamed). The vote reads every NHD line type, pipelines included
  (`05_score.py:24`); in the San Gabriel box that is 700 mi of storm drain against 265 mi of perennial stream. NHDPlus
  lines, which the flow step already matches by drainage, carry the name.
- "No NHD stream here" is a failed vote, not a finding: no line within 200 ft at two of three points
  (`05_score.py:132`). 8,433 reaches are "unmapped"; 808 of them drain 8 sq mi or more (33 on the Snake).
- The reaches are written in longitude and latitude and every later step snaps them back to the grid
  (`05_score.py:369`; `05b_flow.py:173-175`; `05c_drainages.py:368-375`, `:553`).
- Tailwaters are found by river name and a hand-set elevation (`scoring.py:184`); "downstream of this dam to the next
  lake" is what the routing already knows.
- Two LA boxes overlap by 1.5 sq mi (`config.py:66`, `:69`), which `config.py:14-15` forbids.

### 3.3 The same logic written more than once

| What | Where | Lines to save |
|---|---|---:|
| Following the flow direction from a cell | 15 copies: `crossbox.py` x6, `05b_flow.py` x2, `05c_drainages.py` x2, `03b_stitch.py` x2, `04_knickpoints.py` x2, `flowpath.py`, `06_map.py` | 120 |
| `flowpath.py` ("shared by the step detectors") re-typed in `04_knickpoints.py:36-110` | | 45 |
| Pond outflow from NHD lines | `05c_drainages.py:446-506` = `crossbox.py:210-259` | 60 |
| "Walk a mapped line until the path ends elsewhere" | `crossbox.py` x4, `05c_drainages.py` | 60 |
| Download-with-cache | 11 variants over `02b`, `02d`, `02e`, `02f`, `08`, `11`, `troutdata`, `lakesources`, `05d`, `lakelidar`, `watertemp` | 60-80 |
| Overpass call | `geomatch.py:10` = `02d_trails.py:61` (identical), `02c_pct.py:25`, `09_drive.py:31` | 33 |
| ArcGIS paging | `geomatch.py:26` = `02d_trails.py:77`, `11_context.py:46`, `troutdata.py:62`, `data/validate_heat.py:44` | 75 |
| Relief within 0.6 mi; line matching `follow()` | `geomatch.py` = `02d_trails.py` (identical) | 40 |
| The same OpenStreetMap roads and paths downloaded three times per box | `02_download_vectors.py:56`, `02d_trails.py:116`, `02e_access.py:52`; cycleways twice (`02e:62`, `08:104`) | 15, and two downloads per box |
| Popups, tooltips, legends, unit helpers, colour ramps | `map_drainages.js`, `map3d.html`, `14_portable.py`, `13_overview.py` | 240 |
| Every point layer built twice (folium markers and a list for 3D) | `06_map.py:1283-1471` | 60 |
| Lake name matching x3, species tables x4, survey months x2 | `05d_lakes.py`, `maplakes.py`, `lakedata.py` | 40 |
| Bathymetry: download-rename x4, contour loop x4 | `lake_bathymetry.py` | 40 |
| The score's weights typed out again | `fish_score_diagram.py`, `scoring.py` docstring, README | drift |

About 900 lines. The copies have already drifted: the 3D map's side-channel profile link fails where the 2D map's
works; major depth contours are bold in 2D and thin in 3D; fires are named with their source in one map and not the
other.

### 3.4 Dead code, dead outputs, files nothing needs

- `05_score.py:280-288`: a first-pass score, with `config.ELEV_BAND` and the reaches' `road_m` / `trail_m`, thrown
  away at `06_map.py:73`.
- `hike_minutes.tif`: written for all 55 boxes on every run, 3.0 GB on disk, read by nothing (`08_hike.py:376-378`).
- Columns written and never read: `drive_approx`, `long_term`, `burn_count`, `n_src`; file `known_falls_points.gpkg`.
- `fish_score_diagram.py` (191 lines): run for every area, 12 identical unpublished files, one factor short.
- `run_la_refresh.sh`: a one-off for the Overpass outage of 18 November, with LA's box names typed in.
- Branches for states that no longer occur: "no lakes layer" (`05b_flow.py:133`, `flowlib.py:193`, `05_score.py:323`),
  not-stitched boxes (`crossbox.py:151-164`, `:421-433`), `PLANNED` in `05d_lakes.py:47`, the Natural-Flows branch of
  `minor_arms` (`flowlib.py:29-37`).
- About 30 unused imports and parameters (lists in `audit/work/code_core.md` E, `code_sources.md` H2,
  `code_map_lakes.md` F).
- `MULTI_AREA_PLAN.md`: superseded, referenced by nothing. `creek-map/` (12 MB): an LA-era copy outside the pipeline.
- On disk, ignored by git: `data/backup_*` (11 folders, 3.9 GB, copies from 18-20 November); 191 run logs in `data/`;
  the site clone's `.git` is 2.4 GiB of loose objects that `git gc` would bring to about 0.3 GB.

### 3.5 Drivers and caches

| Driver | Steps |
|---|---|
| `run_base.sh` | 01, 02, 03, 03b, 02b, 04, 04b |
| `run_mid.sh` | 02f, 02b, 05d, lake_bathymetry, 05_score, 02g, 05c, 05b, 02d, 02e, 02c |
| `run_late.sh` | 07, 08, 10, 09, 11, watertemp, 06, 12, fish_score_diagram |
| `run_rebuild_a.sh` | [03], [03b], 04, 04b, then mid and late |
| `run_drainage_refresh.sh` | 05c, 05b, 06, 12 |
| `run_la_refresh.sh` | LA one-off |

They can be one driver with one ordered step list and a "start from" argument; the `step()` / `run()` helper is
written out four times and the flow download runs in both base and mid. Three faults to fix on the way:
`run_base.sh:19-20` and `run_rebuild_a.sh:22-23` log FAILED and run the next step, then mid and late regardless;
the lock has no clean-up, so a killed run leaves `data/.hydro.lock` and every later run waits for ever; and the
Adirondack water-temperature fit depends on the order the four maps are built in (tonight the north-west map's
driver run ended "no skill" and a hand rerun after the other three gave it the group fit, `watertemp.py:353-361`).

Caches: 15 families are keyed by a box or area name only, so a moved box edge keeps the old extent with no message;
the NHDPlus table, the reservoir list, the regional road network, the greenness rasters and GNIS never expire; the
known-falls caches, canopy and the temperature readings have no refresh switch. Nothing stale is in use today (a
helper checked the extents of all 55 boxes). The per-box tables are joined on row numbers and tested only for their
count (`scoring.py:100-104`), so rerunning `05_score.py` by hand can attach old values to renumbered reaches. One
cache helper, keyed by the box's extent and the request, written through a temporary file, with an age limit, a
refresh switch and "old copy with a note" on failure (the rules `02f_known_falls.py:59-84` already has) replaces the
11 variants and closes all of these.

### 3.6 The check scripts: a standing set to run before every publish

Today: 33 scripts (1,950 lines) in `data/stream_burning/checks/`, five in `data/`, and about 200 more in session
scratch folders that a reboot clears. Three scripts with three definitions report "sudden flow drops", and most read
the reach tables rather than what is drawn.

Proposed standing set, all on the drawn maps, old side = the site clone, new side = `output/`, each ending in one
line that says pass or lists what failed:

| Check | Script | Passes when |
|---|---|---|
| Built by one committed code state | `audit/scripts/provenance_steps.py`, until outputs carry a stamp | no step older than its code; tree clean |
| Named creeks drawn | `audit/scripts/streams_vs_nhd.py` | no named NHD stream above the floor without a line |
| Drainage against gauges and NHDPlus | `audit/scripts/area_vs_reference.py` | no new gauge off by 25 %; the list of half-size rivers does not grow |
| Flow against gauges | `audit/scripts/flow_vs_gauges.py` | no wet gauged creek shown dry |
| Trout on record shown dry | `trout_found_shown_dry.csv` from the same run | list does not grow |
| Sudden changes along a creek | `audit/scripts/drawn_jumps.py` | count does not grow; new ones listed |
| Lines gone and new against the live site | `data/stream_burning/checks/drops.py` and the overview session's `gone_new.py` | every gone line explained |
| Lake outlets drawn | the overview session's `outlets.py` | no NHD-mapped outlet loses its line |
| Creek line drawn with a lake's values | `data/stream_burning/checks/drawn_lake_values.py` | none new |
| Popup text and access oddities | `audit/scripts/popup_checks.py` | no "-0", no missing drive time, no impossible speed |
| Score reproduces; rule counts | `audit/scripts/fish_score_audit.py` | 99 %+ within 2 points; counts per rule listed against the last publish |
| Falls found; lakes against NHD | `audit/scripts/falls_lakes_checks.py` | no known fall or NHD lake lost |

`audit/scripts/run_all.sh <label> <maps folder> [tables folder]` runs mine in about five minutes. The other 25 scripts
in `checks/` were measurements for the lake-routing work and can be archived with its results.

### 3.7 Website size

636 MiB of 1 GB at `d16a885`; 61 commits, about 413 MiB of history on GitHub.

| What | Now | After | How |
|---|---:|---:|---|
| Three sentences on every reach (flow, sun, access) | 62 MB | 9 MB | store the numbers; the page writes the sentence |
| Lakes, drops, trout waters, land and fire layers: once as folium code in the 2D page (201 MB) and again as data in the 3D page (114 MB) | 315 MB | about 130 MB | one shared data file for these layers, drawn by the page script, as was done for streams on 20 November |
| Lake-touching reaches written twice | 13 MB | 0 | store the in-lake and out-of-lake parts once each |
| Lake depth contours, not simplified (NE Connecticut: 8 MB for 24 lakes, twice) | about 18 MB | about 4 MB | simplify as the other layers |
| Profile data: distance and gradient arrays that follow from the step | 69 MB | about 58 MB | make them in the page |
| Colour-relief pictures, off by default, 2D only | 40 MB | 40 or 0 | your call |

That is roughly 380-400 MiB with nothing removed, about 40 less without the relief pictures (the layer saving is an
estimate until it is built). Each step is a rebuild from `06_map` and can be
checked the way the 20 November shrink was (same data hashes, same pixels). History only shrinks by squashing the map
commits, which needs your say and a force-push.

### 3.8 Docs

- `README.md` (989 lines, 114 KB): the manual build block no longer builds an area; 14 statements are wrong and 18
  stale (`audit/work/docs_readme.md`). About 300 lines are the history of how each rule was found. Moving that out
  leaves about 690 lines with every current rule still in it.
- `MULTI_AREA_LOG.md` (3,487 lines, 314 KB): not in time order, one entry lost and rewritten, 39 open items spread
  over 22 sections, figures corrected three entries later with no mark where they stand. A fifth of it is publish and
  session traffic.
- Proposed: freeze the log as an archive; keep one short state file edited in place with five tables: current rules
  and constants (rule, value, `file:line`, the case it came from, areas measured on), open items, sources and
  licences, a build-and-publish ledger (time, site commit, areas, code commit), and the standing checks. New log
  entries in a fixed short form. Delete `MULTI_AREA_PLAN.md`.
