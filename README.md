# Stream maps: trout water, waterfalls, swimming holes and lakes

DEM-based stream analysis of twelve areas of the US, used to find remote fishable water and in-stream drops
(waterfalls / plunge pools). Each area is one map: its creeks scored 0–100 for trout, with their summer flow,
estimated summer water temperature and the way in by bike and on foot; the detected drops and the known waterfalls;
lakes with their fish, access and depth; trails, dirt roads, trailheads and road closures. The maps are published at
https://alexanderswann.github.io/streams/ from the public repository github.com/alexanderswann/streams (the code on
`main`, the site in `docs/` on `gh-pages`). Eight maps are listed there; the four Adirondack maps are built and
published but hidden.

## Where things are
- `STATE.md`: how things are now: the live site and what it was built from, the rules in force (their values, code
  locations and dates), sources and licences, open items, the standing checks, building and publishing.
- `MULTI_AREA_LOG.md`: the dated record from 2026-11-18 to 2026-11-23 (frozen): how the areas and rules came about.
- `docs/archive/README_history_2026-11-23.md`: passages moved out of this README: how each rule was found.
- `data/stream_burning/README.md`: the lake-routing work (lake outlets, the parked DEM burn) and the trial harness.
- `audit/`: the audit of 2026-11-22 (`AUDIT_2026-11-22.md`); `audit/scripts/run_all.sh`: the pre-publish check.
- `publish/streams-site/`: a local clone of the site branch (not in this repository); `creek-map/`: a hand-made page
  outside the pipeline.

## One map for all areas
`output/index.html` (`scripts/13_overview.py`, no AREA needed) is a map of every built area: drainage outlines, main
rivers and long trails, with a list of the areas. A click inside an area opens its full map at that spot, and each
area's 2D and 3D map has a "Go to…" menu in the legend that jumps to any other area or back to this map at the
current view. The full detail stays in the per-area maps: every area's detail in one page would be over 200 MB. With
the local preview server it is `http://localhost:8766/`; on the phone copies, `phone/index.html` (port 8765).

Every 2D map (the areas, this map of all areas and the one-file phone map) shares `scripts/map_phone.js` and
`map_phone.css`: on a phone the credits fold to one line (a tap opens them), and a "my location" button under the
zoom buttons puts the map where you are, with a blue dot that follows you (the browser asks first). The 3D maps have
MapLibre's own location button, and their credits start folded behind the "i".

`output/index.html` is only a front page: sent to a phone by itself it has nothing behind its links. Two ways to
carry the maps:
- **One file** (`scripts/14_portable.py` → `output/stream_maps_all.html`, about 40 MB, copied to `phone/`): the map
  of all areas with every listed area's detail packed inside as gzip, unpacked when you zoom in: every reach with the
  full popup, and switches for drops and waterfalls, trailheads and parking, trails and dirt roads, gauges and road
  closures, trout records and lakes. Not in it: the 3D view, profiles, hillshade, fire perimeters, land-status and
  trout-water outlines, fork outlines and labels that bend along lines. Send this one.
- **The website** (`scripts/publish_site.sh`): copies the map of all areas (and its link-preview picture, made by hand
  with `15_preview.py`) and every area's maps into `publish/streams-site/docs/` (the `gh-pages` branch) and commits;
  `publish_site.sh push` also pushes, area by area through a temporary branch so git sends changed files as
  differences and the site builds once, then rebuilds the phone copies from the same maps. It refuses while a build
  runs or when `output/` was written in the last 15 minutes (`push now` skips the wait), touches nothing outside
  `docs/` and stops on a file over 95 MB; GitHub Pages refuses a site over 1 GB. Never publish around it (`STATE.md`
  §7). The maps show each map's drive-time starting point (a ZIP and town).

## Study areas and folders
The pipeline handles several study **areas**, each its own map with its own UTM zone, drive-time starting point,
ranges and data sources (`AREAS` in `scripts/config.py`); pick one with `AREA=<key>` (default `la`) and a range with
`REGION=<key>` (default the area's first). An area's range boxes meet edge to edge and must not overlap, or streams
get drawn twice. The pipeline is the same everywhere except where it says otherwise; LA has most sources of its own.

| Area key | Area | Ranges | Drive-time start |
|---|---|---|---|
| `la` | LA mountains | the eight below | 90404 Santa Monica |
| `jackson` | Jackson Hole, Grand Teton & Teton Valley, WY and ID (all of Grand Teton NP, Teton Valley around Driggs, Palisades Reservoir and Alpine, in seven boxes laid out so no lake, and no reservoir's filled basin, crosses an edge between two boxes: see `MULTI_AREA_LOG.md`) | `teton_snake`, `gros_ventre`, `hoback`, `jackson_lake`, `buffalo_fork`, `teton_valley`, `palisades` | 83001 Jackson |
| `n_georgia` | North Georgia mountains | `cohutta`, `blue_ridge`, `rabun`, `hooch_tailwater` | 30305 Atlanta |
| `central_vt` | Central Vermont (the Green Mountains from the White River to the Lamoille, and the Champlain Valley west to the New York line in the middle of Lake Champlain: the boxes reach past the line, and the map is cut at it, `clip_state` in `AREAS` and `areaclip.py`) | `stowe_lamoille`, `mad_winooski`, `white_river` | 05753 Middlebury |
| `ne_ct` | Northeastern Connecticut | `natchaug`, `quinebaug` | 06281 Woodstock |
| `lexington_va` | Lexington, Virginia | `maury_goshen`, `blue_ridge_va` | 24450 Lexington |
| `se_pa` | Southeastern Pennsylvania and northern Delaware, east and south to the Delaware River (from Wilmington Manor and Claymont up past Philadelphia to Morrisville and Washington Crossing: the boxes reach past the river, and the map is cut at the New Jersey line in it, `clip_state` keeping PA, DE and MD; the river above Trenton is kept whole, with Scudders Falls and the Falls of the Delaware) | `brandywine`, `ridley_valley`, `claymont`, `pennypack_neshaminy` | 19063 Media |
| `smokies` | Great Smoky Mountains National Park and around it (TN / NC) | `cades_cove`, `le_conte`, `cataloochee`, `tellico`, `snowbird`, `nantahala`, `tuckasegee` | 30305 Atlanta |
| `adk_high_peaks` | Adirondacks: High Peaks & Lake Placid (the High Peaks, Saranac lakes, Ausable, Boquet, Lake Champlain shore, Chateaugay and Chazy lakes) | `high_peaks`, `boquet`, `saranac`, `wilmington`, `champlain`, `chateaugay` | 05753 Middlebury |
| `adk_northwest` | Adirondacks: Long Lake, Tupper & Cranberry (the Raquette from Raquette Lake to Carry Falls, Stillwater, Cranberry Lake, Five Ponds, the St. Regis) | `beaver`, `long_lake`, `tupper`, `st_regis`, `lake_ozonia` | 05753 Middlebury |
| `adk_southwest` | Adirondacks: Old Forge & West Canada Lakes (the Moose and Black rivers, West Canada Creek, Piseco and Speculator) | `moose`, `west_canada_lakes`, `west_canada`, `speculator` | 05753 Middlebury |
| `adk_southeast` | Adirondacks: Hudson, Indian Lake & Lake George (the Hudson below Newcomb, Indian Lake, the Great Sacandaga, Schroon and Lake George) | `indian_lake`, `minerva`, `siamese`, `sacandaga`, `lake_george` | 05753 Middlebury |

The four `adk_` areas are the whole Adirondack Park (its Blue Line, 23,560 km²) in four maps: one map of the park
would be about 150 MB, over GitHub's 100 MB file limit and too heavy for a phone; the lines between them avoid cutting
lakes and keep each river on one side. They are hidden (`hidden=True` in `AREAS`): built and published at their
addresses, but not on the map of all areas, in the "Go to" menus or in the one-file map; take the flag out to show.

**LA's eight ranges.** A creek that crosses an edge is split between two ranges there. (Only the San Gabriel and Santa
Monica boxes overlap: a 1 × 4 km strip of the San Fernando Valley floor, where a few flat-land channels are drawn by
both.) Warm, low ranges (Santa Anas, Sierra Pelona, much of Piru) score low for trout by design. They are included for
swimming: the popups' NHD flow class and the drop / plunge-pool and waterfall layers apply regardless of fish score.

| Region key | Range | Extent |
|---|---|---|
| `san_gabriel` | San Gabriel Mountains | Tujunga → Lytle Creek headwaters, foothills → Little Rock / Big Rock |
| `santa_monica` | Santa Monica Mountains | Point Mugu → Sepulveda Pass, coast → Simi Hills |
| `san_bernardino` | San Bernardino Mountains | Lytle Creek / Cajon Pass → Whitewater, foothills → Deep Creek / Holcomb |
| `sespe` | Sespe, Topatopa & Mt. Pinos | Matilija / Ojai → Sespe gorge, Fillmore → Mt. Pinos, Lockwood, Frazier Park |
| `piru` | Piru Creek & Castaic | Lake Piru / Castaic → Pyramid Lake, Gorman, the Grapevine |
| `sierra_pelona` | Sierra Pelona | Bouquet and San Francisquito canyons, Lake Hughes |
| `san_jacinto` | San Jacinto Mountains | Idyllwild, Fuller Ridge, Snow Creek → the Palm Springs canyons |
| `santa_ana_mtns` | Santa Ana Mountains | Black Star / Silverado → Trabuco, Ortega Highway, Tenaja |

| Folder | What |
|---|---|
| `data/raw/<area>/<range>/`, `data/derived/<area>/<range>/` | Per-range downloads (DEM, NHD, OSM, canopy) and derived rasters (filled DEM, flow direction, area) |
| `data/raw/<area>/_shared/` | Shared by an area's ranges: trails, access roads, wilderness, flow data, long-distance trail, known falls, the PRISM clip, the water-temperature fit, download caches and last good copies (`netcache`) |
| `data/derived/<area>/_shared/` | Cross-box inflow table (`inflows.json`), lake outlets (`lake_outlets.json`), lakes (`lakes.gpkg`, `lake_depth.gpkg`) |
| `data/raw/_national/` | Downloads every area reuses: NHD HU4 GeoPackages, the PRISM August air temperature grid, USGS GNIS, the Census TIGER/Line state outlines (`areaclip.py`) |
| `output/<area>/` | The combined map, CSVs and GPX below, plus one folder per range |

**What differs outside California.** Each area lists the sources that exist only for it (`sources` in `AREAS`;
`has("name")` in the scripts). LA has all of the California ones; the other areas use national data in their place:

| In LA | In the other areas |
|---|---|
| TNC California Natural Flows (modelled monthly flow per year), scaled by the drainage without the water from above dams (`area_edge_km2`: the model is for natural flow) | NHDPlus V2's EROM mean flow for the month × a yearly index from the area's own USGS gauges (`02b_download_flow.py`), scaled by the full drainage (`area_full_km2`: EROM has the dams in it). One index per area, so small headwaters that dry faster than the gauged creeks are over-rated in droughts |
| CAL FIRE fire history | The interagency fire perimeter history (NIFC) |
| CPAD restricted / no public access | PAD-US holdings recorded as restricted or closed. Most eastern holdings are "unknown" there and aren't flagged |
| CDFW surveys, stocking, Wild / Heritage Trout Waters | Each state's own (`troutdata.py`; the table below) |
| CDFW natural fish-passage barriers among the known falls | none, except the Smokies, where the national park's own waterfalls layer is added; the other sources are the same everywhere (`02f_known_falls.py`) |
| Caltrans and county road closures | Keyless feeds where they exist (step 07 below); none for NE Connecticut, southeastern Pennsylvania or the Adirondacks |
| The Pacific Crest Trail layer | The area's own long trail (`long_trail` in `AREAS`): the Appalachian Trail (North Georgia, Lexington, the Smokies), the Long Trail (Vermont), the Horse-Shoe Trail (southeastern Pennsylvania), the Northville-Placid Trail (the Adirondacks); none for Jackson or NE Connecticut |
| USFS wilderness (no bikes) | The same layer, plus in the Adirondacks the Forest Preserve's Wilderness, Primitive and Canoe areas (NYSDEC lands; the State Land Master Plan keeps bikes out of them), source `nys_forest_preserve` in `geomatch.wilderness_path()` |
| CDEC gauges, the State Parks / NPS / Eaton Fire trail layers | none |
| Late-summer channel greenness (Sentinel-2) for the dry-creek rule | Jackson too; none elsewhere (in the humid areas every channel is green in late summer) |
| Gauged diversions (`DIVERSIONS` in `flowlib.py`) and the below-a-dam water floor | none |
| NHD "artificial paths" (river and lake centrelines) are not perennial: they cross dry washes and reservoirs | They count as perennial: in wet country they are the rivers |
| Elevation band in `05_score.py`'s first-pass score | none |
| "Mountain terrain" for the trail, road and parking filters: 100 m of relief within 1 km | The same, except 30 m in NE Connecticut and southeastern Pennsylvania and 50 m in the Adirondacks (`min_relief`). Road closures use 150 m everywhere |
| Tailwaters (`_TAILWATERS` in `scoring.py`): the West Fork San Gabriel below Cogswell Dam, Piru Creek below Pyramid Dam | North Georgia: the Chattahoochee below Buford Dam (on through Bull Sluice Lake) and the Toccoa below Blue Ridge Dam; the Smokies: the Nantahala below Nantahala Lake, whose powerhouse at Beechertown releases water from the bottom of the lake; none elsewhere |

| Area | Trout sources (`troutdata.py`) |
|---|---|
| NE Connecticut | CT DEEP fish samples, stocking and trout management areas |
| Central Vermont | Vermont's brook trout waters and stocking list |
| Lexington | Virginia DWR wild trout streams (classes I–IV) and stocked waters |
| North Georgia | Georgia DNR designated trout streams, stocking and samples |
| Jackson | Wyoming Game & Fish trout-stream classes and native cutthroat waters; on the Idaho side (Teton Valley, Palisades) Idaho Fish & Game's Yellowstone cutthroat trout streams, as StreamNet's regional fish distribution serves them (Idaho publishes no survey or stocking layer) |
| SE Pennsylvania | the Pennsylvania Fish & Boat Commission's Class A and natural-reproduction wild trout streams, trout special-regulation areas, stocked sections (fish per species) and stocked lakes; Delaware DNREC's designated trout streams |
| The Smokies | North Carolina WRC's mountain trout waters by class (Hatchery Supported and Delayed Harvest, which it stocks, catch-and-release, named Wild Trout Waters; not the game lands' blanket "Wild Trout Waters unless otherwise noted", which covers every creek there); Tennessee WRA's stocking sites, electrofishing samples (1996-2022) and brook trout genetics collections |
| The Smokies (park and tribe) | the national park's own trout distribution map (its "No Fish" code marks unsampled streams and is not used; segments it marks internal are left out) and the Cherokee tribal fishing zones (the Raven Fork trophy section and the Enterprise Waters) |
| The Adirondacks | New York DEC's categorized trout stream reaches (Wild-Quality, Stocked, Stocked-Extended, with the species and number stocked), the streams classed trout (T) or trout spawning (TS) in the state's water quality standards, and public fishing access along trout streams (DEC's fishing rights easements). DEC publishes no survey layer, and its pond stocking list has towns, not coordinates |
| All but LA and Jackson | Trout Unlimited's brook trout patches, from New York and Connecticut to Georgia (a patch of brown and rainbow trout only is not called a brook trout patch) |
| All but LA | iNaturalist (rainbow, brown, brook and cutthroat trout). A no-trout sample counts for the same creek within 1.5 km only, and only Connecticut's and Tennessee's electrofishing samples make one |

Each source marks its records of wild brook trout (`wild_brook`: a survey that found them, a water it lists for them),
which the fish score's size term reads.

## Running the pipeline
Python 3.11 with the packages in `requirements.txt` (`python3.11 -m venv .venv && .venv/bin/pip install -r
requirements.txt`). The scripts run from `scripts/` with `../.venv/bin/python`. Downloads, derived files and outputs
are not in git: the pipeline rebuilds them.

**Drivers** (in `scripts/`; each takes one or more area keys and runs them in turn, logging to `data/`). A step that
downloads and fails is run once more after `NET_PAUSE` s (120; `RETRY` in the log); a step that still fails stops its
area (`FAILED`) and the driver goes on to the next area. Only one conditioning step (03, 03b) runs at a time across
chains: `run_base.sh` and `run_rebuild_a.sh` take `data/.hydro.lock` (`scripts/hydrolock.sh`). A driver that is
stopped (Ctrl-C, `kill`, a closed terminal) stops its step and lets the lock go; after a `kill -9` the next chain
takes the lock over once that driver and its step are gone.
- `./run_base.sh <area> ...` (`base_<area>.log`): per range `01_download_dem.py` and `02_download_vectors.py`;
  `03_hydrology.py` per range (one at a time across all chains, under `data/.hydro.lock`); `02b_download_flow.py`;
  `03b_stitch.py`; per range `04_knickpoints.py` and `04b_bigcreek_steps.py`.
- `./run_mid.sh <area> ...` (`mid_<area>.log`): `02f_known_falls.py`; `02b_download_flow.py`; `05d_lakes.py` (if it
  fails, the last `lakes.gpkg` stays) and `lake_bathymetry.py` (a failure is a NOTE); `05_score.py` per range;
  `02g_greenness.py`; `05c_drainages.py` for every range, then `05b_flow.py` for every range; `02d_trails.py`;
  `02e_access.py`; `02c_pct.py` where the area has a long trail.
- `./run_late.sh <area> ...` (`late_<area>.log`): `07_road_closures.py` (if it fails, the last closure list stays,
  with a NOTE); per range `08_hike.py` and `10_sun.py`; `09_drive.py`; `11_context.py`; `watertemp.py` (a failure is
  a NOTE); `06_map.py`; `12_profiles.py` (a new area first gets a copy of `output/la/profiles.html`);
  `fish_score_diagram.py`.
- `./run_rebuild_a.sh <area> ...` (`rebuild_<area>.log`, then the mid and late logs), after a change to the routing:
  `03_hydrology.py` per range, `03b_stitch.py` (fetching NHDPlus's lines first when they are missing), the drops, then
  `run_mid.sh` and `run_late.sh`, skipping the later stages of an area that failed. `SKIP_03=1` starts at
  `03b_stitch.py`, after a change to it only (03's `dem_cond.tif`, the surface 03b routes on, stays); `SKIP_03B=1`
  starts at the drops, after a change to the drops, the reaches or `crossbox.py` only (the routing stays).
- `./run_drainage_refresh.sh <area> ...` (`drainage_<area>.log`; no retries), after a change to `05c_drainages.py`,
  `05b_flow.py`, `flowlib.py`, `crossbox.py` or `06_map.py`: `05c_drainages.py` for every range, `05b_flow.py` for
  every range, then `06_map.py` and `12_profiles.py`. The reaches and their ids stay; scores change only where a
  reach's flow does.

**One area**, whole: `./run_base.sh <area> && ./run_mid.sh <area> && ./run_late.sh <area>` from `scripts/`, then
`13_overview.py`, `14_portable.py` and `phone_sync.sh` for the map of all areas and the phone copies. One step:
`AREA=<area> REGION=<range> ../.venv/bin/python <step>.py` (`REGION` only for the per-range steps). Which step a change
rebuilds from, and how many builds the Mac takes at once, is in `STATE.md` §7; run long builds under `caffeinate -i`.
Trial builds go in a scratch root with the harness in `data/stream_burning/harness/`: the project drivers write to the
project, so never use them for a trial. Before publishing, run the checks in `STATE.md` §6. The reach and drop keys
(`sid`, `did`) are row numbers `05_score.py` hands out, so every later step runs again after it; `06_map.py` stops if
a range's table lists other reaches or drops than its `streams_scored.gpkg` / `waterfall_candidates.gpkg`. To add a
range, add it to the area's `ranges` in `AREAS` (UTM bbox + NHD HU4 codes) and run the area's drivers. To refresh only
the live data (closures, gauges) before a trip: `07_road_closures.py`, `08_hike.py` per range, `09_drive.py`,
`11_context.py`, `06_map.py`. (`run_la_refresh.sh` was a one-off LA refresh of 2026-11-18, before the current order.)

**Downloads.** Every download goes through `scripts/netfetch.py`: 15 s to connect, the source's own read timeout, a
hard limit on each attempt, and a breaker that stops asking a host (or the whole network) that didn't answer three
(five) requests in a row, for two minutes. A download that still fails is read from its last good copy
(`data/raw/<area>/_shared/netcache`, or the step's own cache), with a dated `NOTE` in the log and "(as of <date>)" in
the source wording the map shows; only a source with no copy at all fails its step. A server that asks for a wait over
two minutes (HTTP 429) isn't waited for when there is a copy. An answer cut short (an Overpass answer stopped by its
time limit, an ArcGIS error sent as HTTP 200, a web page without its `</html>`) is no answer, and one with a part
missing is never kept as a copy. An empty answer (no closed USFS road in a box, no named OSM stream) is kept like
any other: without a copy a step can't run offline. A lidar window that every survey has a gap in is remembered beside
the cached windows (`.gaps.json`), so no lidar tile is read twice; 05d's PAD-US copy, whose box follows the lakes, is
kept under a name of its own and cut to the box asked. `NET_FAIL=1` (or a regex of URLs) makes every download fail at
once, for tests; it doesn't reach GDAL's own reads (the lidar tiles), which `GDAL_HTTP_PROXY=http://127.0.0.1:9` (a
closed port) cuts too. `NET_LOG=1` logs each request. OpenStreetMap downloads try `overpass.openstreetmap.fr` first and the main Overpass
server second. The USGS gauges come from the USGS Water Data API (`api.waterdata.usgs.gov`), which replaces
WaterServices (shut down on 2027-02-22): 1,000 requests an hour without a key, shared with anything else on the same
connection (a fresh `02b` gauge download takes about 115, `11_context.py` under 10). A free key from
https://api.waterdata.usgs.gov/signup/ in `USGS_API_KEY` raises that; the scripts send it only to that API.

## Outputs (`output/<area>/`)
Everything the maps, popups, creek profiles and GPX files show is in imperial units: feet, miles, square miles,
acres and °F (flows in cfs), with scale bars and the measuring tool in feet and miles (owner's choice, 2026-11-19).
The pipeline and its files stay metric (columns `_m`, `_km`, `_km2`, `_ha`); `scripts/units.py` and the pages' own
scripts convert what a person reads, and new popup or legend text goes through them. Text quoted from a source keeps
its words, with the imperial figure in brackets after each metric one (`units.imperial_text`).

| File | What |
|---|---|
| `stream_map.html` | Combined interactive map. It loads `map3d_data.js`; keep it next to that file and the range folders, which hold the hillshade PNGs |
| `map3d_data.js` | The layers both maps draw (streams, drainage fills and divides, the long trail, trails, roads, parking and their labels), loaded by both pages so they are stored once (the website's 1 GB limit) |
| `stream_map_3d.html` | The same map in 3D (tilt, rotate, real terrain), with the layers only it draws inside the page; the rest comes from `map3d_data.js`. Keep it next to that file. Needs internet for MapLibre and the terrain tiles |
| `stream_reaches_ranked.csv` | Every reach of every range, ranked by fish score: the DEM stream links draining 1 km² or more with the water carried to them, or 0.25 km² where NHD maps the creek perennial or names it, cut at lake shores and 200 m below lakes (step 5), with the final score and its terms |
| `waterfall_candidates.csv` | All detected drops with status, height, run, slope above/below, plunge-pool coordinates |
| `waterfall_candidates.gpx` | The unmapped waterfall-like steps, cascades and short falls and the drops at mapped waterfalls, each with its pool. Import into Gaia, CalTopo or onX |
| `road_closures.csv` / `.gpkg` | Current closures on mountain roads (step 07), routed along the roads; whether the approach times count them (`in_season`, `times`) and the access-line note of those they don't (`note`). `road_closures.json`: when the feeds were read |
| `gated_roads.gpkg` | OSM roads tagged closed to public vehicles (locked fire roads, gated forest roads) |
| `lakes.csv` / `lakes.gpx` | The lakes layer's lakes and their facts (Lakes, below) |
| `profiles.html` | Creek profile viewer: elevation vs. distance for every creek with 2 km or more of channel named in NHD (a link from the map to any other creek says it has no profile), with drops, falls, gauges and fish score / burn / trout-water strips. A hand-made page kept in git (no script writes it; `run_late.sh` copies LA's to a new area). Keep it next to `profiles_data.js` and the map |
| `fish_score_diagram.png` | How the fish score is computed (`fish_score_diagram.py`, run by `run_late.sh`; not on the website). It is simpler than the score: it leaves out the channel factor, and its water panel names only the TNC flow model and the diversion gauge, in every area. `scoring.py` is the score |
| `streams_drawn.gpkg` | The stream lines as `06_map.py` draws them, for checking the drawn map |
| `context/` | Fire perimeters, stream gauges (USGS, and CDEC in LA; live), wilderness, land status, critical habitat, trout waters, trout evidence, springs |
| `<range>/` | The same per range, plus `streams_scored.gpkg` / `waterfall_candidates.gpkg` for QGIS. The `fish_score` in a range's own files is `05_score.py`'s first pass (NHD class, size, elevation, gradient, distance to a road); the final score is only in the combined `stream_reaches_ranked.csv` and the maps |

## Pipeline (`scripts/`)
Each step runs per range (`AREA` and `REGION` set) or per area (`AREA` only); the drivers above run them in order.
The rules that decide what the maps show are listed with their values, code locations and dates in `STATE.md` §3.

1. `01_download_dem.py` (per range): 10 m USGS 3DEP DEM, in the area's UTM zone (11N for LA).
2. `02_download_vectors.py` (per range): NHD flowlines/points from USGS bulk GeoPackages (cached in
   `data/raw/_national`), plus OSM roads/trails/waterfalls/dams, for the lon/lat box around the range's UTM box. When
   the public Overpass servers can't be reached, a range keeps the OSM files it already has (`OSM=keep` skips that
   download outright). `02b_download_flow.py` (per area): the flow data (step 7), NHDPlus V2's lines and reservoirs.
3. `03_hydrology.py` (per range) + `03b_stitch.py` (per area): fill pits/depressions → D8 flow direction → flow
   accumulation → streams (≥0.25 km²) → stream order. Boxes that share an edge are solved as one surface (03
   conditions each box's DEM with a 5 km margin of its neighbours, 03b routes the boxes side by side), so a creek
   crosses a box edge as one line with one size, and `area_km2.tif` counts every cell upstream in the joined boxes;
   a lake or filled basin reaching further across an edge is conditioned again as one (`mend_seams`; 03b stops if a
   dead end is left on an edge). Flats rise 1e-9 m a cell, not pysheds' default 1e-5, which piles up across a river's
   flattened water until the flat becomes a pit. The order is pysheds' version of Strahler's: it steps up only where
   all the streams that meet share the highest order, and by one at a lake's outlet.
   - **Filled flats.** A flat of filled ground (10 cells or more, half of them or more raised 5 cm or more by the
     fill: a swamp, a wetland, a valley flat behind a sill) drains along NHD HR's lines instead of resolve_flats'
     shortest ways, which drew ruler-straight lines across it (`flatlines.py`, in 03 and in the pieces 03b conditions
     again at seams). The water runs along the StreamRiver, ArtificialPath and Connector lines, named ones first, to
     the flat's outlet. A line that leaves the flat over a rim 0.5 m high at most, and comes down below it within
     200 m, takes the water out there, but only where the water, followed on the finished surface, stays within 40 m
     of the line for 80 % of the next 200 m. An outlet NHD's line passes a few cells off, and a line broken by a
     hummock the fill left, are joined to it within 100 m. Cells within 100 m of a walked line take the shortest way
     to it; farther ones keep resolve_flats' order, so no new straight way appears away from NHD's lines. Every other
     cell keeps its value, and `dem_filled.tif` and `fill_depth.tif` don't change. A pond is a filled flat too, so its
     water follows NHD's path through it, in one link to its outlet. The size floor reads that link's stretch in the
     pond on its own (5.), which brought back four of the lake outlets this had stopped drawing (Howard Pond, a 4.7
     acre pond, the Dime Creek pond, Dunham Pond Brook); the rest are listed in `data/stream_burning/README.md`.
   - **Lakes.** Flow paths end on purpose at every lake and reservoir of 8+ ha that holds water (2+ ha of its outline
     at one elevation in the DEM), at its outlet: drainages end at dams, and `crossbox.py` carries the area on. Every
     cell of such a lake drains to the outlet along NHD HR's lines through it (`route_lake`), and a stream line runs
     from the outlet to the first stream below (`outflow_streams`), where the lake's water lands. A lake whose water
     leaves it on an edge between two boxes flows on instead; one whose water leaves the map through its own surface
     (Lake Champlain) carries no stream lines.
   - **Lake outlets** (`lake_outlet`). A lake ends where one of NHD HR's stream lines leaves it, followed down to the
     first cell the terrain takes the water on from (within 300 m; a pipe or ditch only where no stream line leaves
     and a stream line goes on from it within 1 km). Of two or three outflow lines, the one NHD names wins (the
     river's bed, not the canal beside it), else the one NHDPlus V2's line leaves by, else the one nearest the cell
     where the DEM gathers the most water. That cell stays the outlet where NHD has no usable outflow line (none, none
     the terrain takes on, one off the map or on an edge between boxes, or NHDPlus and the terrain agreeing on another
     place); the log names each such lake and why. D8 sends a lake's water down one way out, so a creek on another way
     out gets none of the lake's water. `crossbox.py` reads the outlets from `lake_outlets.json`; `03b` stops without
     NHDPlus's lines (`NO_NHDPLUS=1` goes on without them). The one-cell pit at a lake's outlet stays, and NHD's lines
     are not burned into the DEM (that lost waterfall-like steps and reshuffled braided rivers):
     `data/stream_burning/README.md`.
   - **Second outlets.** Each outflow line `lake_outlet` doesn't pick is a second outlet where it passes the outlet's
     own test (the terrain takes the water on down it within 300 m, and its path stays on NHD's line for 200 m), is a
     channel NHD maps (a StreamRiver line, or lines through water running into one, with no connector, canal or
     pipeline before it), and leads neither back into its lake nor up into a lake standing 0.5 m higher (an inflow NHD
     draws the wrong way round). Its way is laid as a stream line to the first stream it meets and listed under
     `sides` in `lake_outlets.json`. No flow direction or drainage area changes, and `crossbox.py` reads only the
     outlets; `05_score.py` draws them (5.).
4. `04_knickpoints.py` (per range): runs of channel steeper than 25% over 30 m that drop 8 m or more, on channels
   draining 1 km² or more, compared with the channel 200 m above and below (the steeper, at least 3%): a
   **waterfall-like step** (max slope ≥ 0.6 and ≥ 2.5× steeper than its neighbours), a **cascade / knickpoint**
   (≥ 1.8×) or a **steep reach** (uniformly steep). `04b_bigcreek_steps.py` (per range) is a second pass for **short
   falls and plunge pools on big creeks** (≥10 km²): ≥3 m of drop over 30 m that is ≥2.5 m more than the creek's
   trend (the steeper of the 200 m above or below, at least 0.5%) and ≥2.5× steeper than it, with `excess_drop_m` and
   `pool_depth_m` (the DEM depression just below the step). Hits within 100 m of a pass-1 drop are dropped, and
   `05_score.py` keeps a pass-2 hit only where the nearest NHD line within 80 m is perennial. Both passes size a
   channel with the water carried to it (`crossbox.carried_km2`: over a dam, past a pond, in from outside the map), so
   a river below a dam is a channel from the dam on; a drop's `area_km2` is this size.
   `02f_known_falls.py` (per area, before step 5) merges the known waterfalls into `known_falls.gpkg`: OSM (falls,
   named rapids and swimming holes, features named for falls or potholes on a stream, and pools in a creek and
   swimming spots, an unnamed one only on a creek and not within 60 m of a lake), NHD waterfall points, USGS GNIS
   Falls and Rapids, Wikidata, CDFW's barrier surveys (LA), the national park's waterfalls (Smokies), Overture Maps
   places, strictly (its waterfall category or a swimming-hole name, on an NHD creek and not by a lake, and only where
   no other source has a fall within 1 km or a fall of that name within 25 km: Overture repeats well-known falls miles
   off; `data/raw/<area>/_shared/overture_places.csv`, which `audit/scripts/completeness_overture.py` writes with each
   Overture release), and the hand-researched falls in `data/known_falls_curated*.csv` (inventories, guidebooks,
   waterfall lists, Google Maps listings looked up by hand with the user's permission for academic use, each row with
   its source page; a row can also name, move or drop a source's point). One fall is one point: the same name within
   500 m (2 km for exactly the same name), an unnamed point within 100 m of a named one, or any two within 25 m; never
   two points of one source, nor two names except on one spot; a name with or without a final s, or with its words run
   together, is the same name (Beldens / Belden Falls, Juneywhank / Juney Whank Falls). `precise` points (OSM, NHD,
   CDFW, guidebook GPS at the fall) can outrank the artifact tests in step 5; the others still name a drop within
   200 m. gawaterfalls.com's Georgia falls (Mark Ozboyd's catalogue; published with credit at the owner's word,
   2026-11-19) link his page; the credits name any guide with 50+ falls on a map.
5. `05_score.py` (per range): attributes, first-pass fish score, per-range exports, hillshade. Each link is measured
   on its own cells: drainage area and gradient at its second-to-last vertex (the last is the confluence cell, which
   would give a side creek the trunk's area), stream order and elevation at its middle vertex. A link is kept when it
   drains 1 km² or more counting the water carried to it (`crossbox.carried_km2`; `area_km2` stays its own area), so a
   river below a lake's outlet has reaches from the outlet on, and down to 0.25 km² (0.1 sq mi, 03b's channel start)
   where NHD maps the link's own line perennial or names it (`nhd_says`): a name it shares with a stream 10 times its
   size within 250 m is that stream's, and so is the year-round class of a river of 50 km² or more it runs along.
   Canals, ditches, pipelines and lines named after one don't count (`floor_lines`: a name is a built channel's where
   NHD gives it a built line of the box and its stream lines carry under a tenth of its length). A link that starts in
   a lake of the lakes layer and isn't kept whole votes again on each part (`nhd_keeps`): its first stretch along NHD's
   path through the lake (not a lake NHD maps as intermittent, and only where NHD maps a creek below it) and its creek
   from where it leaves the lake, so a pond's outlet creek doesn't depend on where the routing splits the link in the
   pond. A creek kept this way runs on down through 0.25-1 km² links until it meets a kept line, across box edges and
   below a pond's outlet; nothing under 0.25 km² is drawn. **Links are cut at lake shores**, so every reach is creek
   or lake water, never both: the shores of the lakes `05b_flow.py` can flag a reach in (NHD's lakes of 8 ha or more,
   with the shore the lakes layer draws, and the layer's own; `05d_lakes.py` runs first). A stretch under 50 m on one
   side of a shore stays with its neighbour. Links mostly on sea-level cells, or past a state line the area is cut
   at, are dropped.
   **The first 200 m (650 ft) below a lake is a reach of its own** (`flowlib.cut_below_lakes`), so a lake outlet's
   warmth is in that stretch's own score (*Water temperature*): each creek is cut where it has run 200 m from the lake
   along the channel the lake's water takes, where the lake term there is 0.5 or more and neither piece would be under
   50 m. The cut is for the water temperature alone: both pieces keep the line's gradient and NHD class, `05b_flow.py`
   reads the cut creek whole and gives both pieces its flow evidence, late-summer greenness and gauge record
   (`cut_sid` names the rest of the line), and `11_context.py` gives both the line's trout records, designated trout
   water, fires and critical habitat (`cut_lines`). Drainage, elevation, August air, canopy, approach time, shade and
   land status are each piece's own.
   **Names.** NHD's name and flow class come from the nearest NHD lines at three points along the link, each kept
   when two agree; where NHD has no name, OpenStreetMap's named streams vote the same way. A link between two links of
   one river takes the river's name when the vote gave it none or a much smaller stream's (NHD draws a creek's line
   out to the river's centreline). A small reach right beside a much bigger reach of its own name is the lower end of
   the creek up its main stem, with that creek's name, or, where its stem lies along NHD's lines of the river, a
   **side channel** (the maps say "(side channel)"; it takes the river's flow evidence and size), else it loses the
   name. A drop takes the name of the link its top cell is on, else the nearest NHD line's within 80 m.
   **A lake's second outlet** (3.) gathers little ground of its own, so its links drain under the size floor: they are
   kept from the lake down to the first link the map keeps on its own (within 5 km; one that meets none isn't drawn)
   and marked side channels of the creek the lake's main outlet starts (`side_lake`, `side_sid`): the maps say "(side
   channel)", and the popup names the lake and what the channel is scored on. Where the map keeps a second outlet's
   first link on its own, it is that creek, drawn from the lake on (the floor's vote reads the outflow line itself
   there; a follow-up counts only the link's own ground). No water is added to any line: NHD gives no split of a
   lake's water. The 200 m cut doesn't reach a second outlet yet (a follow-up).
   **Drop status**, first match wins: **dam / weir** (a mapped dam within 250 m, or the drop starts at a dammed lake's
   outlet, at the lake's level, and ends 3 m or more below it); **matches mapped waterfall** when a precisely placed
   known fall lies on the step itself (within 50 m of its top-to-pool line); **likely DEM artifact** when a drivable
   road crosses the DEM channel within 40 m of the step's top (an embankment or bridge deck can make the lip; a road
   alongside, or crossing below a fall, doesn't count), or when the drop less the DEM's fill at the lip would miss the
   detector's bar; **matches mapped waterfall** for a known fall within 200 m of the top; else the detector's class.
6. `05c_drainages.py` (per range): drainage basins. Every DEM cell is traced down the D8 directions to where it
   leaves the area or ends in a sink (dams). Basins ≥25 km² are named drainages, after their natural trunk creek
   (not canals or aqueducts; a few NHD gaps are fixed by hand in `NAME_FIX` / `FORK_FIX`); drainages ≥120 km² are
   split into forks, tributaries ≥35 km² that join the trunk. At a confluence the bigger arm continues the trunk,
   unless NHDPlus continues the river up the smaller arm (its level path) and the detailed NHD lines agree. The map
   shows one level of forks; the rest is "Minor front-range drainages" (LA) or "Minor drainages". A tributary of
   100+ km² that flows straight into a big river (2,000+ km² where it leaves the map) is a drainage of its own (the
   Hoback beside the Snake). Sea-level water (DEM ≤ 0.5 m) ends a path at the creek's mouth; a creek that reaches the
   sea is named from 5 km², and a lake draining off the map counts as the sea. Writes `drainages.gpkg`,
   `stream_drainage.csv` and the reaches' corrected areas (`area_streams.csv`): `area_edge_km2` (with what flows in
   from other boxes) and `area_full_km2` (also past dams: the fish score's creek size, and the popups' drainage),
   from `crossbox.py`'s inflow table (`inflows.json`, rebuilt when a `flowdir.tif`, the reservoir list or the NHDPlus
   network changes). Drainages still end at dams: forks and names are picked without the water carried past them.
   - **Across box edges**: `area_km2.tif` already counts a creek's ground in the next box, so only the water that came
     into a box from outside the map or over a dam crosses on. Where the box it enters has no line at that cell, that
     water starts its line where it comes in, as a river from outside does (an edge link of 0.25 km² or more).
   - **From outside the boxes**: every NHDPlus V2 main-path line that crosses the outer boundary flowing in, at any
     size, brings NHDPlus's total drainage at its lower end, less what the box's own routing gathers there and what
     the edge links already bring, carried down the creek (the Santa Clara at Fillmore, the Snake). Minor arms of
     split rivers are left out (NHDPlus gives them the whole river's drainage), and the same water counts once,
     decided on NHDPlus's network. Water the terrain sends straight back out over the edge goes in further down the
     mapped river, at the first point whose path stays in. One that comes in through a reservoir (the Chattahoochee in
     Lake Lanier) goes in where that reservoir's own water does. Such a river starts as a reach of its own where its
     water goes in (`crossbox.lead_ins`, laid by `05_score.py`): the terrain path from that cell to the first stream
     line, stopping at a lake whose water leaves the map. Where a river from outside weaves along the
     edge, its terrain path leaving the map within 300 m of the river while NHD's lines stay inside, its water goes in
     again at the first point down the mapped river whose path stays in the map for 200 m, runs along NHD's lines and
     meets no water already taken in (Minister Creek on the SE PA map).
   - **Past dams**: each lake's dead end is linked to the first cell of its way out in `lake_outlets.json` (3.); for a
     lake `03b` leaves at the terrain's cell, or with no NHD outflow line, to the first cell down NHDPlus's (or NHD's)
     line whose path doesn't lead back, moved onto the routed way out within 100 m. A put-in whose path leaves its box
     gets an exit link there. Lakes with no outflow and dead ends away from lakes stay closed.
7. `05b_flow.py` (per range): dry-season water for every reach and drop. A reach's low flow in a year is its lowest
   July–October monthly mean, scaled by drainage: in LA from The Nature Conservancy's California Natural Flows model
   (unimpaired monthly flow per NHDPlus V2 segment), by `area_edge_km2` (not the water from above a dam: the model is
   for natural flow); elsewhere from NHDPlus's EROM flow × the area's gauge index, by `area_full_km2`. Where that would
   lower a reach's estimate below the one from its own box's area, the old estimate stays.
   - **Matching.** A reach takes the nearest segment whose drainage agrees, leaving out the side arms of split
     channels (`flowlib.minor_arms`); ties go to the closer drainage, then the lower comid. Reaches off the model
     network take the unit-area flow of the first modelled segment downstream ("scaled"), on through lakes (a lake
     draining off the map: its line nearest the way in) and into the next box (so `05c` runs for every box first).
   - **NHD's class is the floor of a borrowed estimate.** An estimate scaled from another creek is about the creek
     below: a brook running into a pond inherits the river below it, which is no evidence that the brook dries. So is
     one that leaves out the water from above a lake or dam holding half the drainage (LA's natural flows: the least
     that runs there). Neither puts a reach below NHD's class, valued as the score values NHD's label (perennial 1.0,
     intermittent 0.35, a line NHD gives no class 0.3, no NHD line 0.15, ephemeral 0.05), and a creek NHD maps
     perennial reads year-round whatever the model says (outside California the model is NHDPlus's mean flow, with no
     drying in it). Only a USGS gauge's record, on the creek or below a diversion (`scoring.py`), puts a reach below
     NHD's class. The floor is applied to both passes (own area, and with the water from other boxes) and once at the
     end, so both pieces of a creek cut below a lake take its line's floor (outside California also what like creeks
     read: fish score, *water*); `model_class` keeps the model's class
     where the floor raised a reach, and `water_floor` says which floor (perennial, inherited or dam).
   - **Lakes and dams.** Reaches in or below a reservoir are flagged, since releases set their flow. A reach lying at
     least half inside a lake of 8 ha or more (NHD's, with the shore the map draws, or the lakes layer's where NHD
     maps it as river, leaves it out or draws it too small) is a `reservoir` reach where the lake holds water or the
     reach has no model segment of its own. In LA, reaches below the seven gauged diversions where the gauge shows the
     creek often dry (`DIVERSIONS` in `flowlib.py`: the Santa Ana River No. 1 dam, two Mill Creek intakes, the Lytle,
     Plunge, City Creek and San Jacinto River diversions) carry the gauge's record: the model can't see a canal.
   - Writes `flow_streams.csv` / `flow_drops.csv`: the low flow in a typical (median) and a drought (second-driest)
     year, the share of summers since 2011 the reach kept ≥0.1 cfs through July–October, and a class:

     | Class | Meaning |
     |---|---|
     | year-round | kept ≥0.1 cfs through July–October in more than 85% of the summers since 2011 |
     | usually flows | in more than half of them, up to 85% |
     | seasonal | in more than 20%, up to half |
     | mostly dry | in 20% or fewer |
     | reservoir | the reach lies in a lake or reservoir (above) |
     | no data | no flow estimate: the fish score takes what like creeks read, never below NHD's class |

     The fish score's water rules can set another class; the popups say which rule set it and why.
   - For those rules it also writes each channel's late-summer greenness (`green_p90`: the greenest 10% of Sentinel-2
     NDVI within 30 m of the line, median of three summers, from `02g_greenness.py`; LA and Jackson only) and the
     record of a USGS gauge on the reach's own creek, for the reaches near it on its model line and of about its size
     (`gauge_share`). The record is not carried further along the creek: the canyon above a dry gauge may still run.
   - `02b_download_flow.py`'s downloads (and the gauges' daily records) are kept for 30 days (`REFRESH=1` forces new
     ones): the model gains a month at a time, and while the latest July–October is incomplete that year counts on the
     months it has. `data/check_flow_drops.py` is the standing check for sudden flow drops along a creek;
     `data/validate_flow.py` and `data/validate_flow_areas.py` check the flows against the gauges.

`06_map.py` (per area) merges every range into the combined map, CSVs and GPX. `02c_pct.py` (per area) downloads the
area's **long-distance trail** from OpenStreetMap, 60 km past the area so it runs off the map edge (`pct.gpkg`).

`02d_trails.py` (per area) builds the **trail layer** from **OpenStreetMap** paths, bridleways, footways and tracks
(fire roads), the most complete source in every test area. USGS National Digital Trails (public domain) gives official
name, trail number, agency and allowed uses to OSM ways that follow an official trail, and adds named official trails
missing from OSM, dotted, as "agency records only; may be faint or abandoned"; the USFS layer of roads closed to the
public marks gated fire roads. Left out: sidewalks; paths on flat ground (under the area's relief within 1 km) unless
named, on a route or official; private fire roads unless walking is allowed. Unnamed OSM paths that follow no official
trail or route are "possibly unofficial" (use trails, firebreaks), dotted and shown only from zoom 13. **Mountain
bikes**, first rule that applies: none in wilderness, on the PCT, where OSM says no or where the trail is closed; then
the agencies' designations (USFS trails: no under an order in `bicycle_restricted`, yes when `allowed_terra_use`
contains 3, "N/A" meaning no information, not a ban; State Parks routes; the NPS Santa Monica Mountains inventory);
then OSM bicycle tags; fire roads outside wilderness; state-park singletrack "probably not"; other Forest Service
trails "likely" (open to bikes unless an order closes them). LA County's Eaton Fire layer closes the trails and roads
it lists, and everything inside its closure areas. **Not used:** AllTrails, Gaia GPS, CalTopo, the Strava heatmap,
Wikiloc and Hiking Project (their terms forbid it), and Ventura County's trail layer (internal use only); Gaia's
trails are largely the same open sources. OSM data is ODbL: credit it, and share-alike applies if you publish the
merged trail data itself.

`02e_access.py` (per area, after `02d_trails.py`) builds **access roads, parking and trailheads**. Roads in mountain
terrain or on USFS roads (OSM primary to unclassified, tracks, unpaved residential and service roads, and cycleways,
since paved roads closed to cars are often mapped as cycleways) each get one class by what it takes to get up them,
from OSM tags and the USFS road layers: **paved**, **graded** dirt (car OK when dry: tracktype 1-2, gravel, USFS
level 3+), **high clearance** (tracktype 3-4, rough; USFS level 2), **4WD** (4wd_only, tracktype 5, horrible or
worse), **bike** (closed to cars but open to bikes; not in wilderness), **closed** (a fire closure) and **dirt** (no
condition data); on forest roads the **USFS Motor Vehicle Use Map** decides the class, with its open dates. Private
roads and roads closed to bikes are left out. Parking: public OSM parking in mountain terrain or within 300 m of a
trail. Trailheads: OSM and USFS (with a link and the open / closed status), merged within 150 m, official names
first. Road and trail downloads are cached for a week (`REFRESH=1` forces new ones).

**Map cartography** (`06_map.py` with `map_drainages.js` + `map_style.css`, inlined into the HTML; 3D:
`scripts/map3d.html`):
- Streams are coloured **by drainage**: neighbouring drainages never share a hue, and forks are lighter or darker
  shades of their drainage's. Line width and lightness follow stream order, and order 3+ channels get a white casing.
  Faint basin tints and divides (solid = drainage, dashed = fork) carry the names; a basin cut by a box edge joins the
  drainage it continues into. The legend switch recolours streams by **Drainage**, **Stream order** or **Fish
  score**, and a click on a drainage focuses it. The **3D map** (`stream_map_3d.html`): MapLibre GL JS with AWS
  Terrain Tiles (free, no key), the same colours and overlays draped on the terrain, a slider for terrain height;
  `#lat,lon,zoom,pitch,bearing` links work, and each map links to the other at the current view.
- The area's **long trail**: a thin dark dashed line on a soft yellow band above the streams, with its section on
  hover, and from zoom 11 labels that bend along it (`labelpaths.py`). **Trails and fire roads**: brown dashes on a
  white edge, revealed by zoom (routes and named trails 10, named fire roads 11, unnamed trails 12, unnamed fire roads
  and possibly unofficial paths 13); closed or private ways faded, informal ones dotted; hover for official status,
  trail number, allowed uses, difficulty and surface. **Access roads**, a layer per class (from zoom 10; dirt of
  unknown condition from 11; paved off), cased so they read as roads. **Trailheads** (green T, zoom 11+) and
  **parking** (blue P, zoom 12+). A trail or road running beside a creek is drawn shifted to the creek's far side.
  In the 2D map every vector layer draws on the streams' canvas (Leaflet canvases don't pass mouse events to canvases
  beneath them): area overlays under the streams, points and lines on top.
- **At start** every area map (2D, 3D and the one-file map) shows only streams, drainage outlines and names, the
  long trail, terrain shading, place / road labels and lakes (3D: terrain ×1.6 on a light gray basemap; each overlay's
  start is the last entry of its `ov` row in `map3d.html`); the map of all areas draws no lakes. The rest waits in the
  layer list, each named with its map symbol: drops (a layer per status), waterfalls, trails, trailheads, access
  roads, gauges, closures, fire closure areas, trout waters, trout evidence, springs, lake depth contours.
- **Streams in lakes.** A reach lying at least half in a lake the Lakes layer draws is drawn as the lake while Lakes
  is on, and as a stream when it is off (`STREAMS_LAKE` in `map3d_data.js`); its stretch outside the lake stays, so a
  river reaches the shore. Reaches at lake edges, where the two outlines differ, stay with the other streams.
- **Below dams** (drawing only). The line below a dam starts in the cell below it (`draw_through` in `06_map.py`); a
  straight line of up to 150 m joins it to the lake's shore, unless it would cross another line, meet a creek coming
  in by the dam, or double a line already running by the shore. The stretch from a dam to where the lake's water goes
  on is drawn as creek, with the values of the creek it runs into where that carries about what leaves the lake,
  else those of the lake's own creek. So `06_map.py` draws lines that are not reaches, and cuts and raises some: the
  drawn map and the reach tables differ, an open item (`STATE.md` §3 and §5).
- **Popups.** A stream reach's popup gives its fish score and standing in the area ("ahead of 93% of reaches here"),
  stream order and drainage, the summer flow (class, typical and drought-year low flow, share of summers flowing, and
  what set the class: a gauge, a bare channel, a dam's releases, a diversion's gauge, a trout record, NHD's floor
  where it changed the class; outside California NHD's doubt beside "year-round" or "usually flows" where NHD
  calls the line intermittent or ephemeral or has none; a side channel or a lake's second outlet says so) or, with
  no estimate, what like creeks read, elevation and gradient, the access line (trailhead, drive, bike and hike times,
  "⚠ fire road: double-check bike access", and what the times stand for: "Times for summer (mid-July) · road closures
  as of Nov 22, winter ones not counted"), sun (direct sun, terrain shade, canopy, aspect, August air and the estimated
  summer water temperature), trout waters and records, the heat gate, the latest fire and debris-flow hazard, and
  notes (critical habitat, wilderness, "⚠ No Public Access" or non-Forest-Service land, a built channel), with a link
  to the creek's profile. A drop's popup gives its status and class, height and run, slopes, pool, drainage and flow,
  the access line, any full road closure within 3 km, and links to satellite imagery and the creek's profile.

`07_road_closures.py` (per area) fetches **current road closures**: active now or starting in the next 7 days, in
mountain terrain (≥150 m of relief within 1 km; park roads wherever they are). Run it, then `06_map.py`, for fresh
closures; the layer name shows when they were fetched. Sources, all keyless:
- **LA**: the **Caltrans Lane Closure System** (Districts 6, 7, 8 and 12) on the mountain highways (SR-1, 2, 18, 23,
  27, 33, 38, 39, 74, 126, 138, 142, 150, 173, 189, 243 and 330, and full closures of I-5 over the Grapevine), routed
  along OSM roads between their ends; "full closure (one direction)" closes every lane that way, a closed ramp or rest
  area doesn't close the highway. **LA**, **San Bernardino**, **Riverside** and **Ventura County** closures; the county
  lists sometimes keep closures past their estimated reopening date (labelled). Orange County's feed is empty.
- **Jackson**: Grand Teton National Park's road status, Teton County's emergency closures and Idaho 511's work zones
  (Teton Valley, Palisades). WYDOT's highway conditions and Idaho 511's event feed need a registered key, so the
  state highways (Teton Pass, the Snake River Canyon), Lincoln County (Alpine) and the Idaho side's other closures
  aren't covered. **North Georgia**: Georgia 511. **Central Vermont**: the New England Compass work-zone feed (seasonal
  closures such as Lincoln Gap). **Lexington**: the Blue Ridge Parkway's closure table and Virginia 511's map files.
  **The Smokies**: the Blue Ridge Parkway, NCDOT's incidents (behind DriveNC), TDOT SmartWay, the park's alerts and its
  secondary roads' open seasons, and the Cherokee National Forest's road construction table. The Parkway's table is
  read by its milepost sections: a section is closed when its Status says Closed, and in an open one only the milepost
  ranges its notes call closed; a closed campground or picnic area closes no road. Each closure is laid on the
  Parkway mile by mile between the park's milepost points, and a mile is kept only where a road between them is
  about as long as the mileposts say.
- **None** for NE Connecticut (its closures need a registered key), southeastern Pennsylvania or the Adirondacks
  (511NY needs an API key). Forest Service closure orders are not included anywhere (Caveats).

**Which closures the approach times count.** The approach and drive times are for the season the map scores
(mid-July, the day of the sun hours), not for the day of the build. A full closure cuts its road in `08_hike.py` and
`09_drive.py` only if it will still be in force on the coming July 15, by its own dates and words (`in_season`; the
reason, `times`, is in the layer's tooltip): with an end date (the feed's, or one its notes give: "closed November 1
to April 30"), if that falls on or after the coming mid-July, so winter gates, a night's road work and lapsed county
closures don't count; with none, if it has been in force since before last mid-July or its notes don't call it
seasonal (winter, snow, weather and the like); with neither dates nor notes, as the closure it can only be reached
through. A closure the router couldn't lay on its road cuts nothing, and a counted one cuts the road it runs along,
not the roads it meets (`roadclosures.py`). Today's closures the times don't count are named, dated, on the access
line of each route whose drive runs on them ("⚠ Teton Park Road closed for winter until Apr 30 (as of Nov 22)").

**Access, conditions and context** (run after 05 and 07):
- `08_hike.py` (per range): cost-distance approach time from the nearest road a car can reach, on the 10 m DEM.
  Freeways and their ramps, and road pieces stranded behind a closure, are no places to start from.
  - **Walking** uses Tobler's hiking function on the cell's slope, capped at 15% on anything with a tread (every OSM
    road and trail in the range), since trails switchback. Off-trail creek bottoms walk at 45% of that speed and
    other ground (chaparral) at 30%; slopes over 45° are near-impassable, and so are lakes off trails.
  - **Biking** is used wherever it beats walking: 18 km/h on the flat, slowed by grade (about 10 km/h at 6%), ×0.7 on
    dirt roads and ×0.5 on singletrack, on the road's or trail's own grade along the line over 200 m (capped at 25%),
    not the hillside's. **Bikeable:** every road closed to cars and every fire road (the closures counted for
    mid-July and roads cut off by them, OSM roads tagged access=no / motor_vehicle=no, OSM tracks, access roads of
    class "bike", the trail layer's fire roads), every OSM bike path (downloaded by `08_hike.py`, kept a week), and
    singletrack the trail layer marks bike-legal; never in wilderness. Other singletrack is walked; private roads
    neither layer lists stay out.
  - **Fire roads where bikes may not be allowed are still ridden**, and their bike time counts. A route that rides
    one for a minute or more gets `bike_check` (why: wilderness, posted no bikes, a fire closure, closed or private in
    OSM) and `bike_check_min`; popups say "⚠ fire road: double-check bike access".
  - Each reach/drop gets `approach_min` = `bike_min` + `walk_min` and its trailhead; reaches also get
    `approach_med_min`, the typical time along the reach, and `bike_med_min`, the minutes of it ridden. A point in a
    lake counts as reached at the nearest reachable shore of its own lake, and each lake gets an approach
    (`hike_lakes.csv`).
- `09_drive.py`: free-flow drive time and distance from the area's drive-time starting point (`home` in `AREAS`) to
  each trailhead, over regional OSM highways plus local roads, without the closures counted for mid-July and with
  winding mountain roads at ×0.75 speed; no traffic. A road reaching the network only through streets outside every
  box is joined across the gap (up to 3 km, at 25 km/h), flagged approximate. Run it after `08_hike.py`: it rewrites
  `trailheads.gpkg`.
- `10_sun.py` (per range): hours of direct sun on the water on July 15, from horizons traced in 36 directions out to
  3 km, and `northness`, the aspect of the mountainside within 1 km. Trees aren't in it; `11_context.py` adds them.
- `11_context.py`: fire perimeters since 2016 (CAL FIRE in LA, NIFC elsewhere, WFIGS for this year's, else the
  Forest Service BAER map's outline), each reach's soil burn severity (BAER) and the USGS post-fire debris-flow hazard
  below burns of the last 4 years, USFS tree canopy cover (NLCD TCC, latest year), USGS real-time gauges against the
  daily percentiles for today's date (and CDEC's two Piru Creek gauges in LA), wilderness and land ownership, critical
  habitat for stream species, designated trout waters, trout evidence, springs, the August mean air temperature along
  each reach and at each trout record (PRISM 1991–2020 normal, 800 m, clipped per area from the national file to
  `data/raw/<area>/_shared/prism_tmean_aug.tif`), and holdings with restricted or no public access (CPAD in LA,
  PAD-US elsewhere), flagged ("⚠ No Public Access") and drawn as their own layer.
- **Trout evidence** (`context/trout_evidence.gpkg`): in LA CDFW Heritage & Wild Trout Program surveys (trout found
  or not), CDFW stocking in the last 12 months and iNaturalist research-grade rainbow and brown trout sightings with
  an exact location; elsewhere each state's records (Study areas, above). A survey or stocking point counts for the
  creek of the same name within 5 km; a sighting for its reach (within 150 m) and the same creek within 1.5 km. Lakes
  are left out of the score (their trout are stocked): stocked lakes, and sightings at a lake or within 400 m of a
  stocked one. `scoring.py` merges all of these onto the reaches and drops and computes the final fish score.
- `12_profiles.py` (after `06_map.py`): long profiles for every named creek (`profiles_data.js`): the longest
  connected path through its NHD named flowlines, at the channel bottom (the lowest conditioned DEM cell within 20 m,
  only going down downstream), with drops, falls and gauges snapped on and fish score, burn, trout-water and habitat
  strips from the creek's own channel only (reaches named after it, or unnamed ones up to twice its largest named
  reach + 1 km²). The drainage is the routing's own (`area_km2.tif`), without the water carried past dams or in from
  outside, so below a dam it can read less than the popup. Drop colours match on the map and the profiles (magenta
  waterfall-like step, yellow cascade, violet short fall, ink at mapped waterfalls), colour-blind safe.

## Fish score (0–100, heuristic; `scripts/scoring.py`)
`water × (30% size + 30% thermal + 15% gradient + 25% remoteness) × burn × trout × heat × channel`, capped at 100.
It was tuned on LA's mostly dry channels; in the wet areas most reaches score over 50, so scores rank creeks within
an area and aren't comparable between areas. The ranked table has `area_rank_pct`, the share of the area's reaches
that score lower, and stream popups show it ("ahead of 93% of reaches here"): that is the number to compare. A reach
loses score only where the harm is near-certain; when unsure, a possible trout stream stays in.
- **water:** dry-season flow (`05b_flow.py`, with NHD's class as its floor: step 7): 0.05 + 0.95 × the share of
  summers since 2011 the reach kept ≥0.1 cfs through July–October; 0.3 in a reservoir. A reach with no estimate (no
  model line on the creek or below it on the map) takes the median water term of the area's reaches with the same NHD
  label and a drainage within a factor of 2 (4, then any size, where under 20 such reaches; `typical_water`), never
  below NHD's class: perennial 1.0, intermittent 0.35, a line NHD gives no class (in LA its artificial paths and
  canals) 0.3, no NHD line 0.15, ephemeral 0.05.
  Outside California, where the flow is NHDPlus's mean flow with no drying in it, a borrowed estimate (scaled from
  another creek) never reads drier than that typical value either, and one on a creek NHD has no line along that still
  reads mostly dry shows NHD's label, as a reach with no estimate does (`scoring.borrowed`). In LA, whose natural
  flows see creeks dry up, NHD's class stays the floor: the area's typical value mixes mountain creeks with desert
  washes. Left: 79 LA pieces (46 mi) that read "NHD unmapped" before 2026-11-22 read "mostly dry" on the same scores,
  since `05b_flow.py` doesn't yet record which kind a borrowed estimate is.
  Below a gauged diversion the gauge's own share replaces the model's where it kept flowing in under half of 5+
  summers since 2011, close below the diversion, with no trout known there: today only the San Jacinto River near San
  Jacinto (trout were found below the Santa Ana, Mill, Lytle and Plunge diversions). **Creeks the model rates
  flowing that are dry most summers** are caught one way only, as the owner put it: "id rather rate a dry creek as
  year round than a year round creek as dry".
  1. A **bare channel** (LA, Jackson): the model's typical summer low under 0.45 cfs (there it can't tell wet from
     dry), no green along the channel in late summer (`green_p90` under 0.45 in the median summer and 0.5 in every
     one, and not 0.2 greener than the slopes around, which keeps desert palm oases), NHD intermittent, ephemeral or
     unmapped, and no trout record, dam, tailwater, open water or fire since 2018: water 0.35 ("seasonal"), no lower.
     It is decided per creek between confluences (`creeks()`: reaches end to end with drainage within 0.8 of each
     other): a creek reads seasonal only where all of it passes or already reads mostly dry, and none of it shows
     water (a trout record, a dam or tailwater, NHD perennial, open water, a channel 0.67 green or more).
  2. A **gauge on the creek**: 0.05 + 0.95 × its share of summers flowing, where that differs from the model by more
     than 0.05. It raises a reach anywhere (Piru Creek below Pyramid Dam flows every summer on its releases), and
     lowers one only at or below the gauge and where no trout are known on the creek it stands for.
  3. A **tailwater** (*thermal* below) whose water the gauge rule didn't set: full water, since its dam's releases
     keep it flowing every summer, which the natural-flow model can't see.
  4. **Below a lake or dam** holding half or more of a reach's drainage (LA, where the flows are natural flows), the
     model's figure is only the creek's own ground below it, the least that runs there, so it doesn't put the reach
     below NHD's class: part of `05b_flow.py`'s floor (step 7). A gauge on the reach still sets it.
  5. A **trout record** (trout found since 2016, with no later survey finding none; `trout_signs`) lifts a reach to at
     least "usually flows" (water 0.69): trout don't live in a creek that is dry most summers.

  **A lake's second outlet** is scored on its lake's water: it takes the water term and evidence of the creek its
  lake's main outlet starts where they read it at least as wet as its own, but NHD's class where NHD maps the channel
  intermittent or ephemeral, and it never reads wetter than the creek it runs into below, unless that creek is on its
  lake's own river. A trout record or designated trout water on the channel stands against both.

  The rules catch only some of the dry creeks the model rates flowing (13 of the 35 gauged ones when measured,
  2026-11-20), and the model and NHD often disagree, both ways. The map shows NHD's perennial creeks year-round unless
  a gauge's record says otherwise; at the gauges NHD's perennial is right at 187 of 192 outside LA and 9 of 14 in LA,
  so some LA creeks shown year-round will be dry. Desert-side canyons with year-round water score high on water alone;
  the heat gate takes down only the low desert ones.
- **size:** drainage area, log scale from 1 to 50+ km²: the full area (`area_full_km2`), with what flows in from
  neighbouring boxes and from above reservoirs. A side channel takes the drainage of the river reach beside it, and a
  lake's second outlet the drainage of the creek its lake's main outlet starts.
  **Wild brook trout water** is sized for brook trout, which live in smaller creeks than the other trout
  (`BROOK_SCALE`; the user's choice, 2026-11-22): its drainage counts six times over, so the credit starts at
  0.06 sq mi instead of 0.39 and is full from 3.2 sq mi instead of 19. It is a reach that a designation of wild brook
  trout covers (any of them, not only the label the map shows: a Trout Unlimited / EBTJV brook trout patch; Vermont's
  brook trout waters; a Virginia wild trout stream or a Pennsylvania Class A stream with brook trout; the Smokies
  park's brook trout segments; a Wyoming trout stream with brook trout among its game fish), or where a survey found
  wild brook trout in the last 10 years and no later survey found none. Stocking lists, iNaturalist sightings (they
  can't tell wild fish from stocked), New York's Wild-Quality class and Connecticut's Wild Trout Management Areas
  (they name no species) don't count. Nothing scores lower, and other creeks are unchanged.
- **thermal:** 50% water temperature, 35% summer shade, 15% north-facing mountainside. Water temperature is the
  reach's estimated July–August daytime water temperature (*Water temperature* below): full credit at 20 °C or
  cooler, none at 25 °C or warmer, the same in every area because a trout's limits are water temperatures; no penalty
  for cold. Where an area's fit has no skill, every reach takes the measured sites' mean (a cold area stays cold);
  any other reach with no estimate (no fit, or an input missing) gets half credit. Shade combines the terrain's shade
  with the tree canopy: 1 − (1 − terrain) × (1 − 0.8 × canopy), full credit at 45%. **Tailwaters** (rivers below a
  dam that releases cold water from its bottom; per area in the table under Study areas) get the water-temperature
  part in full: reaches the flow step flags below that dam, and the river's main stem by name (20 km² or more) below a
  set elevation with no dam flagged above it. Nothing stops a tailwater at the next reservoir: lower Piru Creek below
  Lake Piru takes Pyramid Dam's (rightly year-round, by the gauge below Santa Felicia Dam, but its popup credits
  Pyramid Lake's releases).
- **gradient:** 1–8% best. **remoteness:** typical bike+hike approach along the reach, 0 → 120+ min, with each
  minute ridden counted twice (`RIDE_REMOTENESS`): most anglers walk in, so a road closed to cars keeps most out.
- **burn:** fire since 2016, ×0.4 if ≤2 years ago, ×0.7 if 3–5, ×0.9 if 6–9, scaled by the fire's soil burn severity
  where the Forest Service mapped it (BAER): high 100%, moderate 75%, low 40%, very low 15%. A channel takes the ash
  of the slopes above it, so the USGS post-fire debris-flow hazard sets a floor (high 100%, moderate 75%, low 40%),
  and marks down a reach below a burn too. Where neither maps the severity, the fire marks nothing down; the BAER layer
  holds only recent fires, so that is most of LA's 2017–2022 fires (Thomas, Bobcat, Woolsey) and all outside LA.
- **trout:** ×1.2 with evidence of trout (found in the last 10 years by a state survey, stocking or an iNaturalist
  sighting, with no later survey finding none) or on a designated trout water or wild trout patch. A survey that found
  no trout marks nothing down (a later survey of the reach often finds them); the popups still list empty samples.
- **heat (desert gate):** ×1 where the August mean air temperature (PRISM 1991–2020 normal, 800 m) is ≤29 °C, falling
  linearly to ×0.2 at 30.5 °C; never on a reach with trout evidence or below a dam (its releases may run cold). The
  cutoff sits more than 2 °C above the hottest creek with a trout record (lower Piru Creek, a tailwater, at 26.7 °C):
  it takes down only the low desert canyons and fans below the San Jacinto and San Gorgonio escarpments (Whitewater
  River, Palm Canyon Wash, Tahquitz and the lower Andreas and Snow creeks, 29–33 °C), where the water measures hot.
  Upper Murray, Andreas and West Fork Palm canyons (27–29 °C) are probably too warm too, but that isn't certain, so
  they aren't gated. It uses air temperature because no stream-temperature model is good enough here (NorWeST and EPA
  StreamCat missed measured summer water temperatures by 4–6 °C), and Southern California trout also live in warm
  water. `data/validate_heat.py` (from `scripts/`, after `11_context.py`) reproduces the test.
- **channel:** ×0.2 on a built conveyance, by name only: aqueduct, canal, flood-control channel, diversion, ditch,
  flume and the like, with no natural word in the name (creek, river, wash, brook, branch, fork, run) and no trout
  record (in LA the three aqueducts and the named flood channels). A natural name stays as it is, concrete or not
  (the Los Angeles River, Tujunga Wash).

Critical habitat, wilderness and non-Forest-Service land are shown as flags, not scored. Critical habitat is USFWS/NMFS
*designated* habitat, not a closure map: Forest Service closures for arroyo toad and other species are set by forest
orders, usually cover less ground, and have to be checked on the forest's site.

### Water temperature (`watertemp.py`)
`watertemp.py` fits the measured sites' July–August daytime medians (Water Quality Portal) per area (an area cut at a
state line, `clip_state`, on the sites inside its states only), by least squares
on the best of a few predictor sets (PRISM August air temperature, elevation, drainage area, a lake term): the lowest
leave-one-out error among the sets whose coefficients have the physical sign, a simpler set within 0.05 °C first.
Sites are weighted by how well their median is known; sites with a median over 30 °C (hot springs), and in one pass
those more than 3 robust standard deviations off the first fit, are left out. An area needs 25 sites and a fit that
beats "every creek is the average" by 10%, else every reach takes the sites' mean. The estimate is held at the edge of
the fitted range, so it runs narrower than reality. The fit is in `data/raw/<area>/_shared/water_temp_fit.json`.
- **The fits in use** (as stored on 2026-11-22): LA air + elevation; Jackson and Lexington elevation + drainage area;
  North Georgia elevation; NE Connecticut drainage area; Vermont, southeastern Pennsylvania and the Smokies air +
  drainage area; the Adirondacks' High Peaks elevation + lake term, south-west the lake term, south-east drainage
  area, and north-west, with no fit of its own, the fit on all four maps' sites (`water_temp_group` in `config.py`:
  only where that misses the map's own sites by no more than 0.9 × their spread). Southeastern Pennsylvania's fit
  can't see the limestone-spring creeks such as Valley Creek: they read about 22 °C and measure about 15.
- **The lake term** (three Adirondack maps): a lake's outlet runs at its surface temperature, and the warmth fades
  fast. The term is the share of a reach's drainage that comes through a lake, counted only for the part of the reach
  within 200 m (650 ft) below the lake (`LAKE_NEAR_M`; in full for a reach lying in a lake), in full on creeks up to
  50 km² and fading to nothing at 500 km² (a big dam may release cold water from depth). The lake water is what
  `crossbox.py` carries past dams and ponds, and what runs on out of a lake along the routing before `03b_stitch.py`
  ends the lake's paths at its outlet, which can lie past the shore the map draws (`flowlib.lake_water_km2`). A lake's
  second outlet takes the lake share of the creek its lake's main outlet starts, its warm first stretch counted from
  its own start at the lake. The term enters a fit only where 5 measured sites have a term of 0.5 or more.
- **A reach is scored on its estimate as a whole**, the mean along it, and the first 200 m below a lake is a reach of
  its own (step 5), so the outlet's warmth is in that stretch's own score. Where a stretch isn't cut, the popup adds
  its first stretch's warmth ("about 75 °F over its first 650 ft, just below a lake"; `water_outlet`, `outlet_m`, no
  part in the score) where that is 1 °C or more warmer and 50 m or longer. Beyond 200 m a lake-fed creek reads as one
  with no lake, 3–6 °F too cool at the measured sites there, which marks no creek down; the 200 m itself is not sharp.
  With the fade, warm lake-outlet rivers keep their credit (their sites read about 2 °C above the estimate), and a
  river below a dam isn't marked down for warmth.

## Lakes (all 12 areas)
Lakes and ponds as places to go: outline, water level, depth, fish, access and land. Each area keeps lakes from its
own smallest size (`BUILT` in `05d_lakes.py`): 0.5 ha in Jackson, Lexington and the Smokies, 2 ha in North Georgia
(below that, farm ponds), 1 ha elsewhere (in the Adirondacks this keeps the 2.5-acre brook trout ponds); a lake a
state lists at any size, and a named NHD pond down to a quarter acre (0.1 ha, `NAMED_MIN_HA`). `05d_lakes.py` (per
area, before `05_score.py`; it needs nothing of the reaches) writes `lakes.gpkg`, with `lakelidar.py` (1 m lidar),
`lakedata.py` (depths and gill-net surveys typed in from reports) and `lakesources.py` (EPA National Lakes Assessment
soundings; each state's lake access, rules, designations and trout lakes, New York's from data.ny.gov).
`lake_bathymetry.py` then adds measured contours (`lake_depth.gpkg`) and depths. `06_map.py` draws them through
`maplakes.py`: "Lakes", on at start, and "Lake depth contours", off, in the 2D, 3D and one-file maps; `lakes.csv` and
`lakes.gpx`. Fill: blue where the agency lists game fish or trout are stocked or recorded, grey where it lists none
(Jackson's Game & Fish), pale blue with no record either way; a dashed edge where the lidar found little level water.

| Attribute | Source |
|---|---|
| Outline | 1 m lidar (USGS 3DEP), the newest survey over each lake: lidar DEMs are hydro-flattened, so the cells at the lake's one elevation are its shoreline on the survey date (a lake flattened at more than one level takes the patches at the other levels lying mostly inside its outline) |
| Outline (else) | NHD High Resolution where the lidar didn't flatten the lake, for reservoirs and lakes drawn down that day, where the level water runs on past the lake, and over 600 ha |
| Missing lakes | OpenStreetMap water of the area's smallest size or more that no NHD lake covers, kept where the lidar shows level water (not water NHD maps as river, canal or estuary unless OSM tags it a reservoir; not wastewater works). A state's listed lake NHD has no lake for keeps the agency's outline (Cheoah Reservoir) |
| Water level | The lidar's flattened level; the median of a level but unflattened surface; else the 10 m DEM. A lake the lidar caught low shows its normal level. NHD's stage elevations aren't trusted (feet at some lakes, metres at others, metres off at some). Survey date: each lidar survey's span, which can be a year |
| Level water | "largely dry, marsh or overgrown then" where the lidar surface isn't level (2 acres or more, the 10 m DEM agreeing); "caught drained / drawn down" where a dammed lake's bed lies over a metre under its own lidar shore or a neighbour's normal level; "below its normal level when the lidar was flown" for a flattened dammed lake over 2 m under NHD's level |
| Name | GNIS (NHD); Wyoming Game & Fish's where it names a group or adds a qualifier; else OpenStreetMap's, where one named outline and the lake cover half of each other, no lake within 2 km has the name, and it doesn't end in "Dam" |
| Fish (Jackson) | Wyoming Game & Fish's lake fishing guide (game fish or "None", lake class, depths, private shore), with species recorded since 2000 but not on its list shown beside it |
| Fish (elsewhere) | The state's stocking and survey records, where a record names the lake within 2 km or lies within 150 m of the shore (a stream's point beside a pond stays the stream's); New York: DEC's stocking since 2011 and lake fishing list. Everywhere: GBIF records at the lake |
| Depth | Measured values only, best first: published sonar surveys and state bathymetry, EPA National Lakes Assessment sonar (a natural lake's deepest spot, a reservoir's lower bound), fisheries transducer surveys, an agency's listed depth. Disagreements over 20% (and 2 m) are shown. Modelled depths (GLOBathy, HydroLAKES) are never used |
| Inlets, outlets | NHD HR flowlines that start or end at the shore; an unnamed outlet is followed down to the first named water. Many small lakes have no mapped stream: "no mapped inlet or outlet (NHD)" |
| Access, rules | The states' launches, fishing access sites, lake designations, special regulations and boat and motor rules (CT DEEP; Vermont; Virginia DWR; PFBC, with credit as its licence asks, and DCNR; NCWRC, TWRA, TVA and the Calderwood reciprocal licence; DEC's lake fishing list and launches from data.ny.gov). DEC's own ArcGIS layers forbid secondary distribution, so they aren't used for lakes |
| Land | PAD-US (the public-access service); where PAD-US leaves the water out (Jackson Lake), the unit most of the shore lies in. Access is flagged only where closed, or restricted outside federal land |

**Measured depths.** Connecticut DEEP's lake contours (surveys of 1959-2002; the deepest contour is a lower bound);
Vermont ANR's sonar soundings (2020; below the survey day's level); in SE Pennsylvania DCNR / PA Geological Survey
depth maps (Marsh Creek, Hopewell, Scotts Run) and USGS's sonar survey of Chambers Lake; in LA USGS's multibeam survey
of Little Rock Reservoir (2022, doi:10.5066/P9BQW35E; raised 106.4 ft to the 3DEP lidar's datum) and Lake Arrowhead's
2008 Reclamation survey; at Lexington Virginia DWR's map of Lake Robertson (a lower bound). No lake in the Jackson
boxes has a downloadable survey, and the other areas have none that can be used (the surveys checked are listed in
the archive). **Lake Champlain**: NOAA's chart soundings (charts 14781-14784, the 1870-1939 lake surveys) in 20 ft
contours below low lake level, the chart datum (93.0 ft above sea level; the lake usually stands 2-3 ft higher); the
popup names the charts and NOAA's agreement, as it asks, and says the depths aren't for navigation.

**Walking to lakes.** Lakes are impassable on foot off trails: a reach mapped through a lake is reached at the shore,
a river through a big lake takes the time to the nearest shore. Times are a fit hiker's without stops (Tobler), a
little short where a 10 m grid cuts switchbacks. Boats aren't modelled, so in the Adirondacks, where many approaches
are by canoe, routes go round lakes on foot, which raises remoteness and so fish scores.

## Validation (mapped falls matched by a detected drop within 200 m)
All 12 areas on 2026-11-20, from `data/validate.py` (from `scripts/` with `AREA=<area>`). Mapped falls are the known
falls OpenStreetMap or the NHD lists, rapids and swimming holes left out. The check reads the detectors' own output,
before `05_score.py` keeps pass-2 hits on perennial creeks only and sets aside dams and DEM artifacts: all count.
It predates the detectors' change of 2026-11-21 (they count carried water since) and measures only recall: nothing
estimates how many unmapped candidates are real.

| | Pass 1 only | Pass 1 + big-creek pass |
|---|---|---|
| Falls on creeks ≥10 km² | 108 / 270 | 192 / 270 |
| Falls on smaller drainages | 294 / 559 | 294 / 559 |
| **All** | **402 / 829** | **486 / 829** |
| Every precisely placed known fall, any source | 693 / 1,600 | 839 / 1,600 |

- By area (both passes): LA 127 / 212, Jackson 12 / 21, North Georgia 110 / 193, Central Vermont 20 / 30,
  NE Connecticut 4 / 23, Lexington 15 / 21, SE Pennsylvania 0 / 11, the Smokies 97 / 156, and the Adirondacks' High
  Peaks 41 / 53, Northwest 18 / 33, Southwest 6 / 10 and Southeast 36 / 66. SE Pennsylvania and NE Connecticut are the
  weak spots: falls a few metres high in gentle terrain, where the detectors find almost no drops (the known-falls
  layer still shows them).
- LA by range (both passes): San Jacinto 21 / 28, San Bernardino 13 / 15, Santa Monica 14 / 21, San Gabriel 43 / 69,
  Sespe 20 / 32, Santa Ana 16 / 46, Piru 0 / 1. The thresholds were tuned on the San Gabriel, Santa Monica and San
  Bernardino ranges (70 of their 105 here). Falls on drainages under 1 km² lie below pass 1's floor (many of the
  Santa Anas', and Frustration and Middleman Falls beside Deep Creek); Mayberg (flat lowland) and Sycamore (2.9 km²)
  are missed too. The big-creek pass recovers Aztec and Hesperia Falls (Deep Creek), Royal Falls (Arroyo Seco) and
  4 unnamed mapped falls that weren't looked at while tuning.
- The CDFW fish-passage barriers that no other source lists are left out of the table: they are mostly cascades,
  bedrock chutes and boulder jams with no drop a 10 m DEM can show (51 of 172 have a detected drop within 200 m).
- Pass-2 hits are only as good as a 10 m DEM. A 3–5 m "excess drop" can also be a log jam, boulder field, bridge or
  DEM seam, and `pool_depth_m` is usually 0 because lidar returns the water surface, not the pool bottom. Treat them as
  places to check on imagery. Upper Deep Creek near Lake Arrowhead (≈1,770–1,830 m, <250 m from roads) is likely
  culverts or development; the better Deep Creek candidates sit below ~1,550 m.
- A routing change is measured on the drawn maps as well as on the reach tables: comparing the reaches two builds both
  have misses the lines that vanish. The standing checks are in `STATE.md` §6.

## Regional notes
- **San Gabriels**: the best remote trout water is Fish Fork, Iron Fork, Bear Creek, the West Fork, Prairie Fork and
  Little Rock Creek.
- **San Bernardinos**: the best remote trout water is Deep Creek, Bear Creek, Holcomb Creek, the upper Santa Ana River
  and Little Bear Creek.
- **Santa Monicas**: NHD maps almost nothing as perennial, so fish scores are low everywhere. Malibu Creek and Topanga
  hold endangered southern steelhead, and fishing for them is illegal: waterfall / swimming-hole scouting, not trout.

## Caveats
- Drop height is the step over ~30–300 m of channel, not the free-fall height. Treat candidates as places to check on
  satellite imagery, not confirmed falls.
- The NHD perennial/intermittent label is coarse, and flow changes a lot after drought and fire (Bobcat, Eaton, El
  Dorado, Line).
- Check current closures (Angeles NF, San Bernardino NF), CDFW Wild Trout / catch-and-release regulations
  (Deep Creek, Bear Creek), and endangered-species closures (arroyo toad, Santa Ana sucker, steelhead) before going.
  Forest Service closure orders (fire areas, seasonal gates) are published only as web pages and PDFs, so the maps
  don't have them: check the forest's alert pages (fs.usda.gov/angeles, fs.usda.gov/sbnf) before a trip.
- Some "dam / weir" flags come from OSM check dams. Some "DEM artifact" flags are still real falls: one under a road
  bridge, or a slot gorge where the fill behind the lip is most of the drop.
- The approach model assumes closed and gated roads may be walked and biked, and it rides every fire road, even in
  wilderness or where bikes are posted out. Those routes are flagged "double-check bike access". Many long-term
  closures allow walking and biking, but fire and storm closure orders can ban all entry. Hike times are model
  estimates; the canyon-bottom and chaparral speeds are guesses, so expect real off-trail travel to vary a lot.
- Drive times have no traffic. Add 30–60+ min for LA weekday or weekend-morning traffic.
- `non_fs_land` comes from the USFS basic-ownership layer, which only separates Forest Service from everything else.
  It can be private, county or other public land, so check the parcel before crossing it.
