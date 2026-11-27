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
- **Compressed on the site** (`weblib.pack`, `scripts/web/lib/streams/`, 2026-11-25): the site keeps each area's big
  files gzip-compressed, as `<name>.gz` (the very bytes of `<name>`, level 9, no name or time in it, so an unchanged
  map gives the same bytes): `map3d_data.js`, `stream_map.js`, `map3d_layers.js`, `routes_data.js`,
  `profiles_data.js`, `land_data.js`, `parcels_data.js` and `coverage_data.js` (`weblib.GZ`). They were 663 MB of the site's 717 MB, and are 119 MB so: the site went from 717 to
  171 MB of GitHub Pages' 1 GB, and a saved area takes about a sixth of the room on the phone. Phones download about
  what they did, since Pages already gzipped them on the way. `publish_site.sh` packs them after copying (and stops on
  a page that still loads one of them with a plain `<script src>`, a page from before); `phone_sync.sh` does the same
  for `phone/`. The pages load them through `lib/streams/load.js` (`StreamsLoad`): over the web it fetches
  `<name>.gz` and unpacks it with the browser's `DecompressionStream` as it downloads (Safari 16.4, Chrome 80,
  Firefox 113 and later; older browsers unpack it with `lib/streams/inflate.js`), then runs it as the plain script
  would run; opened from disk (`output/`, `file://`), or where there is no `.gz`, it runs the plain file. So `output/`
  keeps the plain files, and the checks read either (`audit/scripts/sitefile.py`; the publish gate reads a
  `<name>.gz` as the `output/` file it was packed from). Since then the 2D page's own script (folium's map, its layers,
  markers and popups) is `stream_map.js` beside the page, and the layers only the 3D map draws are `map3d_layers.js`
  (they were inline in the pages). A page that can't load one says so at its top.
- **Offline, as an app** (`scripts/weblib.py`, `scripts/web/`, 2026-11-24): the website is also a web app for use
  with no connection. The pages load their libraries from the site's `lib/` (copies of the Leaflet, jQuery, Bootstrap,
  folium plugin, MapLibre, label-font and Plotly versions they loaded from CDNs; licences in `lib/LICENSES.txt`), and
  `sw.js` (the service worker), `offline.js`, `manifest.webmanifest` and `icons/` sit at the site's root:
  `13_overview.py` puts them in `output/`, and `publish_site.sh` copies them and then writes each area's
  `offline.json` (every file its folder holds but its build stamp, with sizes and hashes, and a version) and one at the
  root (the map of all areas, the credits page, `offline.js` and the manifest, which a saved area keeps too; apart, as
  the map of all areas changes with every publish). The publish gate (`build_stamp.py`) wants the web app's code
  committed, as it does `13_overview.py`'s. On an iPhone: open the site in
  Safari, Share → Add to Home Screen, open the app, open an area, and under **Offline use** at the foot of the layer
  list save the area (both maps, profiles, terrain shading) and the USGS topo base map (the whole area to zoom 10–13,
  or the view on the screen to zoom 16, with AWS terrain tiles for the 3D map; the sizes show first). The panel says
  "update available" when the site's copy has changed (only changed files download). With no connection the maps
  switch to the saved topo and our terrain shading, grey out Esri's and OpenTopoMap's layers (their terms don't allow
  keeping tiles; they are never saved), enlarge a coarser saved tile where a zoom isn't saved, and the my-location
  button reads the phone's GPS. `?offline-test` in a page's address makes the site behave as with no connection, on
  a computer, until `?offline-test=0`. A visitor who saves nothing gets the site as before: the worker passes every
  request to the network and nothing is kept. **Taking it back:** any change to `scripts/web/sw.js`, once published,
  reaches every phone at its next page load with a connection and takes over at once (the browser asks the site for
  `sw.js` each time, never its own cache: `updateViaCache: "none"`; then `skipWaiting`, `clients.claim`); bump its
  `VERSION` to send it out unchanged. The kill switch: copy `scripts/web/sw-passthrough.js` over `scripts/web/sw.js`
  and publish: a worker that answers nothing, so every page loads from the network; saved maps stay on the phones
  unused (`WIPE = true` deletes them). Put the real `sw.js` back the same way. A fixed page or library reaches a phone
  that saved its area when the user taps Update ("update available" shows on its next open with a connection);
  `offline.js` and `index.html` refresh by themselves.

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
| CPAD restricted / no public access | PAD-US holdings recorded as restricted or closed. Most eastern holdings are "unknown" there and aren't flagged, nor is restricted land that is open on foot, with rules on use: federal forests, parks and BLM land, wilderness, and the states' parks, forests, wildlife management areas and public lakes, by PAD-US's own manager and designation type (`publicland.py`, 2026-11-24). A holding's name is printed only for public, tribal or non-profit land with a place's name (`landnames.py`): never a private individual's, so an easement shows its status alone |
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
| "Mountain terrain" for the trail, road and parking filters: 100 m of relief within 1 km (on flatter ground the trail and road layers keep what is named, routed or official, or runs along the water: `trailrules.py`) | The same, except 30 m in NE Connecticut and southeastern Pennsylvania and 50 m in the Adirondacks (`min_relief`). Road closures use 150 m everywhere |
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
  with a NOTE); per range `08_hike.py` and `10_sun.py`; `09_drive.py`; `11_context.py`; `11c_land.py` and
  `11d_parcels.py` (a failure is a NOTE, and the map has no land layer, or no parcel owners, until it runs again);
  `watertemp.py` (a failure is a NOTE); `11e_coverage.py` (a failure is a NOTE, and the map has no cell coverage layer
  until it runs again); `06_map.py`; `12_profiles.py` (a new area first gets a copy of the page,
  `scripts/profiles.html`);
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

**One area**, whole: `./run_area.sh <area> [from-step]` from `scripts/` (2026-11-23). It runs `run_base.sh`,
`run_mid.sh` and `run_late.sh` in turn, in one build slot, from the step named on (`../.venv/bin/python build_stamp.py
steps` lists them; the drivers skip the steps before it, with a line in their logs), then the checks on the new map
(`audit/scripts/check_build.sh`, this area only), and ends with one line each: OK or what failed. A new area needs only
a label, a home and an outline in `config.py`: `00_area.py`, run_base's first step, works out the rest. Then
`13_overview.py`, `14_portable.py` and `phone_sync.sh` for the map of all areas and the phone copies. One step:
`AREA=<area> REGION=<range> ../.venv/bin/python <step>.py` (`REGION` only for the per-range steps). Which step a change
rebuilds from, and how many builds the Mac takes at once, is in `STATE.md` §7; run long builds under `caffeinate -i`.
Trial builds go in a scratch root with the harness in `data/stream_burning/harness/`: the project drivers write to the
project, so never use them for a trial. Before publishing, run the checks in `STATE.md` §6. The reach and drop keys
(`sid`, `did`) are row numbers `05_score.py` hands out, so every later step runs again after it; `06_map.py` stops if
a range's table lists other reaches or drops than its `streams_scored.gpkg` / `waterfall_candidates.gpkg`. To add a
range, add it to the area's `ranges` in `AREAS` (UTM bbox + NHD HU4 codes) and run the area's drivers. To refresh only
the live data (closures, gauges) before a trip: `07_road_closures.py`, `08_hike.py` per range, `09_drive.py`,
`11_context.py`, `06_map.py`.

**Build stamps.** Every step stamps itself: `output/<area>/build_stamp.json` says which committed code made each file
(`build_stamp.py show <area>`), and `publish_site.sh` refuses a publish whose changed files came from uncommitted or
mixed code, a failed step, a step older than one before it, or a map the checks haven't passed (`build_stamp.py
gate`). The check after a build is `audit/scripts/check_build.sh`, the same one a session runs on its scratch build
before handing a patch on (with the patch chain as its last words): the code is the committed or patched tree, the
standing audit tables, the golden places (`audit/golden_places.csv`), and lines, drainage, scores and lake outlets
against the live maps, summed up in `audit/tables/<label>/PREHANDOFF.md`. `scripts/baseline.sh make|clone|list` keeps
frozen copies of the built project for scratch builds to start from. `scripts/new_area_test.sh <area> <scratch
folder>` builds a test place from `tests/new_areas.json` from nothing in a scratch copy and writes a report.

**Downloads.** Every download goes through `scripts/netfetch.py`: 15 s to connect, the source's own read timeout, a
hard limit on each attempt, and a breaker that stops asking a host (or the whole network) that didn't answer three
(five) requests in a row, for two minutes. A download that still fails is read from its last good copy
(`data/raw/<area>/_shared/netcache`, or the step's own cache), with a dated `NOTE` in the log and "(as of <date>)" in
the source wording the map shows, and the legends name those layers in one line with the copy's day; only a
source with no copy at all fails its step. A server that asks for a wait over
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
https://api.waterdata.usgs.gov/signup/ gets 1,000 an hour of its own, not shared with the connection (its
`X-RateLimit-Limit` on 2026-11-24): `USGS_API_KEY`, or when that's unset the private file `~/.config/usgs/api_key`
(the key alone, `chmod 600`); `netfetch.usgs_key` sends it only to that API, in the `X-Api-Key` header, and never
prints it. The FCC's mobile coverage (`11e_coverage.py`) comes through the FCC's Public Data API (`bdc.fcc.gov`; the
National Broadband Map's website turns programs away): it answers only a user of an FCC account, with an API token made
in the map (sign in at broadbandmap.fcc.gov, the username's menu, "Manage API Access", "Generate"; the FCC's terms are
agreed there), at most 10 calls a minute. Both are in the private file `~/.config/fcc/bdc_api` (`chmod 600`; the
user's since 2026-11-25), two lines `username=...` and `token=...`, or in `FCC_BDC_USERNAME` and `FCC_BDC_TOKEN`;
`netfetch.fcc_auth` sends them only to that API and never prints them. Without them the step runs on its saved copies.

## Outputs (`output/<area>/`)
Everything the maps, popups, creek profiles and GPX files show is in imperial units: feet, miles, square miles,
acres and °F (flows in cfs), with scale bars and the measuring tool in feet and miles (owner's choice, 2026-11-19).
The pipeline and its files stay metric (columns `_m`, `_km`, `_km2`, `_ha`); `scripts/units.py` and the pages' own
scripts convert what a person reads, and new popup or legend text goes through them. Text quoted from a source keeps
its words, with the imperial figure in brackets after each metric one (`units.imperial_text`).

| File | What |
|---|---|
| `stream_map.html` | Combined interactive map. It runs `map3d_data.js`, then `stream_map.js` (its own script: the map, its layers, markers and popups); keep it next to them and the range folders, which hold the hillshade PNGs. On the website these and the other big files are `<name>.gz` (Compressed on the site, above) |
| `stream_map.js` | The 2D map's own script, written by folium (in the page until 2026-11-25) |
| `map3d_data.js` | The layers both maps draw (streams, drainage fills and divides, the long trail, trails, roads, parking and their labels), loaded by both pages so they are stored once (the website's 1 GB limit) |
| `stream_map_3d.html` | The same map in 3D (tilt, rotate, real terrain). It runs `map3d_data.js` and `map3d_layers.js` (the layers only it draws; inside the page until 2026-11-25); keep it next to them. Needs internet for the terrain tiles, unless saved for offline use |
| `map3d_layers.js` | The layers only the 3D map draws (lakes, falls, drops, context layers ...) |
| `stream_reaches_ranked.csv` | Every reach of every range, ranked by fish score: the DEM stream links draining 1 km² or more with the water carried to them, or 0.25 km² where NHD maps the creek perennial or names it, and those creeks on up from where NHD's line starts (step 3), cut at lake shores and 200 m below lakes (step 5), with the final score and its terms |
| `waterfall_candidates.csv` | All detected drops with status, height, run, slope above/below, plunge-pool coordinates |
| `waterfall_candidates.gpx` | The unmapped waterfall-like steps, cascades and short falls and the drops at mapped waterfalls, each with its pool. Import into Gaia, CalTopo or onX |
| `road_closures.csv` / `.gpkg` | Current closures on mountain roads (step 07), routed along the roads; whether the approach times count them (`in_season`, `times`) and the access-line note of those they don't (`note`). `road_closures.json`: when the feeds were read |
| `gated_roads.gpkg` | OSM roads tagged closed to public vehicles (locked fire roads, gated forest roads) |
| `lakes.csv` / `lakes.gpx` | The lakes layer's lakes and their facts (Lakes, below) |
| `profiles.html` | Creek profile viewer: elevation vs. distance for every creek with 2 km or more of channel named in NHD (a link from the map to any other creek says it has no profile), with drops, falls, gauges and fish score / burn / trout-water strips. A hand-made page kept in git, its source `scripts/profiles.html` (no script writes it; `run_late.sh` copies it to a new area). Keep it next to `profiles_data.js` and the map |
| `fish_score_diagram.png` | How the fish score is computed (`fish_score_diagram.py`, run by `run_late.sh`; not on the website). It is simpler than the score: it leaves out the channel factor, and its water panel names only the TNC flow model and the diversion gauge, in every area. `scoring.py` is the score |
| `streams_drawn.gpkg` | The stream lines as `06_map.py` draws them, for checking the drawn map |
| `routes_data.js` | Each drawn reach's approach route (Approach routes, below), loaded by both maps on the first tap on a reach; keep it next to the map. A range's whole route network is in `<range>/hike_routes.gpkg` (segments: `seg`, `parent`, `kind` 0 bike, 1 on a trail or road, 2 off trail, 3 creek bottom) and `<range>/hike_route_starts.csv` (each reach's, drop's and lake's first segment and the metres of each kind) |
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
   - **Named and year-round creeks above the channel start** (`low_channels`). Where NHD HR names a creek or maps it
     year-round above 0.25 km², its channel starts where NHD's line starts, on the terrain's own channel: going down
     NHD's line from its upper end, the first cell that is the wettest within 40 m of the line, gathers 1 ha or more,
     lies nearest that line and whose D8 path follows NHD's lines (80 % of its next 200 m within 40 m), and from there
     down its D8 path to the first stream. Not where under 70 % of the new line would lie within 40 m of NHD's lines,
     nor where NHD's network above the head reaches the map's edge (a creek from outside, whose line is cut off at the
     edge). Each such line is a link of its own (`low_channel` in `dem_streams.gpkg`), order 1, ending on the stream it
     runs into, which isn't cut there: the 0.25 km² network, its links and its orders don't change.
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
   below a pond's outlet. Under 0.25 km² only the lines 03b starts along NHD's named and year-round creeks are drawn
   (`low_channel`), on the same vote without the test against a bigger stream alongside, and the creek such a line
   runs into goes on with it to a kept line (a link drawn only for that is marked with them, `low_channel` 2). These
   lines take their values from the reaches around them, but the
   rules that read one reach by others (from here to the map) leave them out for the rest: every reach of the
   0.25 km² network reads as it did without them. **Links are cut at lake shores**, so every reach is creek
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

`02d_trails.py` (per area) builds the **trail layer** from **OpenStreetMap** paths, bridleways, footways, steps, bike
paths (`highway=cycleway`: paved greenways like the Rottenwood Creek Trail, mapped as the Bob Callan Trail; one OSM
names as a road, like Old Pass Road, is a road closed to cars in the road layer) and tracks (fire roads), the most
complete source in every test area. USGS National Digital Trails (public domain) gives official name, trail number,
agency and allowed uses to OSM ways that follow an official trail, and adds named official trails missing from OSM,
dotted, as "agency records only; may be faint or abandoned" (the approach times walk them as faint trails, slower
than a trail: `08_hike.py`); its water trails (canoe and paddle routes, such as the
Chattooga River Canoe Trail or Tennessee's river segments: NDT's trail type "Water Trail" or surface "Water") are no
walking or biking trails: they name no path, draw no line and aren't in the approach times (their pieces stay in the
data for the parking test). The USFS layer of roads closed to the public marks
gated fire roads. Left out: sidewalks; sidepaths (an unnamed footway, path or bike path within 20 m of a car road for
60 % of its length: the road's own side path, often untagged in OSM) aren't drawn, though the approach times and the
parking test still use them; on flat ground (under the area's relief
within 1 km), a way that is unnamed, on no route and follows no official trail, unless it runs along the water (half
its length within 150 m of a reach the map draws or of a lake: `trailrules.py`, the user's choice of 2026-11-25); private
fire roads unless walking is allowed. Unnamed OSM paths that follow no official trail or route are "possibly
unofficial" (use trails, firebreaks), dotted and shown only from zoom 13; an unnamed bike path is not. **Mountain
bikes**, first rule that applies: none in wilderness, on the PCT, where OSM says no or where the trail is closed; then
the agencies' designations (USFS trails: no under an order in `bicycle_restricted`, yes when `allowed_terra_use`
contains 3, "N/A" meaning no information, not a ban; State Parks routes; the NPS Santa Monica Mountains inventory);
then OSM bicycle tags; fire roads outside wilderness; state-park singletrack "probably not"; other Forest Service
trails "likely" (open to bikes unless an order closes them). LA County's Eaton Fire layer closes the trails and roads
it lists, and everything inside its closure areas. **Not used:** AllTrails, Gaia GPS, CalTopo, the Strava heatmap,
Wikiloc and Hiking Project (their terms forbid it), and Ventura County's trail layer (internal use only); Gaia's
trails are largely the same open sources. OSM data is ODbL: credit it, and share-alike applies if you publish the
merged trail data itself.

`02e_access.py` (per area, after `02d_trails.py`) builds **access roads, parking and trailheads**. Roads (OSM primary to
unclassified, tracks, unpaved residential and service roads, and the cycleways OSM names as roads or that are USFS
roads, since paved roads closed to cars are often mapped as cycleways): paved ones in mountain terrain or on USFS roads
(elsewhere the basemap draws them), dirt roads and tracks anywhere, on flat ground when named or along the water as
the trail layer's paths are (`trailrules.py`). Each gets one class by what it takes to get up it,
from OSM tags and the USFS road layers: **paved**, **graded** dirt (car OK when dry: tracktype 1-2, gravel, USFS
level 3+), **high clearance** (tracktype 3-4, rough; USFS level 2), **4WD** (4wd_only, tracktype 5, horrible or
worse), **bike** (closed to cars but open to bikes; not in wilderness), **closed** (a fire closure) and **dirt** (no
condition data); on forest roads the **USFS Motor Vehicle Use Map** decides the class, with its open dates. Private
roads and roads closed to bikes are left out. Parking: public OSM parking in mountain terrain or within 300 m of a
trail the trail rule kept before 2026-11-25 (in mountain terrain, on a route, official, or named like a trail; a bike
path only where it follows an official trail, as a rail trail does), so a town lot beside a greenway or riverside path
is no trail parking; and any lot OSM names after a trail
("Schuylkill River Trail Parker Ford Trailhead") or a way onto the water (a boat ramp or launch, a fishing or canoe
access). Trailheads: OSM and USFS (with a link and the open / closed status), merged within 150 m, official names
first. **Forest Service roads OSM lacks** (the user, 2026-11-25: "Draw and ride them") are roads too: the pieces of
the USFS road lines (open and closed to the public) more than 40 m from every way the maps have, 200 m or longer, and
not an offset copy of an OSM way (half the piece within 100 m of one, or within 300 m with 60 % of it running beside
one within 30° of its direction: `trailrules.usfs_only`). They are classed like the others by their USFS layer, level
and MVUM designation, named from the USFS record, and say "From Forest Service records only; not in OpenStreetMap,
may be overgrown or gated". **Official fishing access sites and boat ramps** (the user, 2026-11-25; `accesspoints.py`)
come from the agencies that publish them for the states each map's boxes reach into: CDFW's fishing guide launches,
WGFD's ramps, Public Access Areas and river access, IDFG's access sites, Georgia DNR's water access points, SCDNR's
public water access, NCWRC's boating access and public fishing areas, TWRA's access sites, Virginia DWR's boating
access, PFBC's access areas, DNREC's fishing access, CT DEEP's boat launches, Massachusetts' and Rhode Island's access
sites, Vermont Fish & Wildlife's fishing access areas, and DEC's launches, access sites, piers and Public Fishing Rights
parking (data.ny.gov), with USFS fishing and boating sites, the Park Service's boat launches and water access, and
TVA's ramps everywhere. Each keeps its name, type (boat ramp, hand launch, walk-in access, fishing pier, parking),
water, agency and page; sites within 75 m are one, an OSM lot within 150 m is its parking, and only sites inside the
boxes and within 1 km of water the map draws are kept (not the tidal Delaware's or the ocean's). Sources whose terms
forbid passing the data on, or ask to be contacted first, are left out (DEC's own ArcGIS layers, MassWildlife's,
West Virginia DNR's). Road and trail downloads are cached for a week (`REFRESH=1` forces new ones).

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
  white edge, revealed by zoom (routes and named trails 10, named fire roads 11, unnamed trails and bike paths 12,
  unnamed fire roads and possibly unofficial paths 13); closed or private ways faded, informal ones dotted; hover for official status,
  trail number, allowed uses, difficulty and surface. **Access roads**, a layer per class (from zoom 10; dirt of
  unknown condition from 11; paved off), cased so they read as roads. **Trailheads** (green T, zoom 11+),
  **parking** (blue P, zoom 12+) and **fishing access & boat ramps** (teal A, zoom 11+: type, water, parking, the
  agency and its page). A trail or road running beside a creek is drawn shifted to the creek's far side.
  In the 2D map every vector layer draws on the streams' canvas (Leaflet canvases don't pass mouse events to canvases
  beneath them): area overlays under the streams, points and lines on top.
- **At start** every area map (2D, 3D and the one-file map) shows only streams, drainage outlines and names, the
  long trail, terrain shading, place / road labels and lakes (3D: terrain ×1.6 on a light gray basemap; each overlay's
  start is the last entry of its `ov` row in `map3d.html`); the map of all areas draws no lakes. The rest waits in the
  layer list, each named with its map symbol: drops (a layer per status), waterfalls, trails, trailheads, parking,
  fishing access and boat ramps, access roads, gauges, closures, fire closure areas, trout waters, trout evidence, springs, lake depth contours.
- **Streams in lakes.** A reach lying at least half in a lake the Lakes layer draws is drawn as the lake while Lakes
  is on, and as a stream when it is off (`STREAMS_LAKE` in `map3d_data.js`); its stretch outside the lake stays, so a
  river reaches the shore. Reaches at lake edges, where the two outlines differ, stay with the other streams.
- **Below dams** (drawing only). The line below a dam starts in the cell below it (`draw_through` in `06_map.py`); a
  straight line of up to 150 m joins it to the lake's shore, unless it would cross another line, meet a creek coming
  in by the dam, or double a line already running by the shore. The stretch from a dam to where the lake's water goes
  on is drawn as creek, with the values of the creek it runs into where that carries about what leaves the lake,
  else those of the lake's own creek. So `06_map.py` draws lines that are not reaches, and cuts and raises some: the
  drawn map and the reach tables differ, an open item (`STATE.md` §3 and §5).
- **Popups.** A stream reach's popup gives its specs (below), its fish score and standing in the area ("ahead of 93%
  of reaches here"), the summer flow (class, typical and drought-year low flow, share of summers flowing, and
  what set the class: a gauge, a bare channel, a dam's releases, a diversion's gauge, a trout record, NHD's floor
  where it changed the class; outside California NHD's doubt beside "year-round" or "usually flows" where NHD
  calls the line intermittent or ephemeral or has none; a side channel or a lake's second outlet says so) or, with
  no estimate, what like creeks read, the access line (trailhead, drive, bike and hike times,
  "⚠ fire road: double-check bike access", and what the times stand for: "Times for summer (mid-July) · road closures
  as of Nov 22, winter ones not counted"), sun (direct sun, terrain shade, canopy, aspect, August air and the estimated
  summer water temperature), trout waters and records, the heat gate, the latest fire and debris-flow hazard, and
  notes (critical habitat, wilderness, "⚠ No Public Access" or non-Forest-Service land, a built channel), with a link
  to the creek's profile; and the route's miles ("bike 3.1 mi · hike 1.2 mi, 0.9 mi of it on trails or roads"), below
  the access line. A drop's popup gives its status and class, height and run, slopes, pool, drainage and flow,
  the access line, any full road closure within 3 km, and links to satellite imagery and the creek's profile.

- **Stream specs and similar streams** (the user, 2026-11-25, after an r/bluelining thread on an ArcGIS map of NHDPlus
  High Resolution's flowlines). The popup's first row, in its head above the fish score: "about 10 cfs mean, 1.1 ft/s ·
  slope 2.4% · order 3 · 5.7 sq mi · lower end 1,532 ft". The mean annual flow is NHDPlus V2's gauge-adjusted mean
  (EROM's QE_MA, 1971-2000) of the line `05b_flow.py` matched the reach to, scaled to the reach's drainage as 05b scales
  that line's summer flows (`streamspecs.py`; every area, LA too). At 479 USGS gauges it comes to the gauge's own
  1971-2000 mean (median ratio 1.00, 88% within 25%) and to 1.07 of its whole record. The velocity is at that flow, by
  NHDPlus's own formula (Jobson 1996) from the reach's flow, drainage and slope (`map_specs.js`; the Firehole example of
  the thread, 55 cfs, 33 sq mi, 2.64%, gives its 1.49 ft/s); none in a lake, and "under" on a reach the DEM reads flat.
  The lower end is the DEM at the reach's lowest cell, where its gradient is measured to. A reach with no flow estimate
  shows none. "Similar streams ›" after the specs dims the map's streams unlike this one and lays a yellow glow under
  those like it: mean annual flow within x/÷ 2 (drainage where either has no flow estimate), slope within x/÷ 1.5 (at
  least ±0.3 points) and the lower end within ±750 ft; each band a switch in a note by the layer panel, "order" (the same
  order) off at first, "wider" x/÷ 3, x/÷ 2 (±0.5) and ±1,500 ft. Among the streams the filters keep; it rides the 2D/3D
  link as `&like=`. The one-file phone map shows the specs only. The stream filters (`map_filter.js`) have a mean-flow
  slider in cfs beside the drainage one (the user, 2026-11-25): any, 0.5, 1, 3, 5, 10, 15, 25, 50, 100, any, on the flow
  the specs line shows; a stream with no flow estimate leaves the map while a flow limit is set; `&cfs=3-15` in the link.

- **Approach routes** (the user, 2026-11-24). A tap on a reach draws its fastest route from the trailhead to its
  approach point, as `08_hike.py` found it (`map_routes.js`, in both maps): the bike leg orange; the walk raspberry,
  solid on a trail or road (drawn on that line), dashed off trail, dotted up a creek bottom; the trailhead a white dot.
  On a phone the popup covers most of the map, so the route stays when the popup closes, until the next tap on the map
  or on another reach; "See it on the map" in the popup closes it and fits the whole route into view (the user's choice,
  2026-11-24). The routes of a map are in `routes_data.js`, loaded on the first tap. A reach drawn in pieces (cut at a
  pond) or a stretch drawn for another reach shows its reach's route, and a reach in a lake is reached at the shore.

- **Live gauge readings and My Waters** (the user, 2026-11-25, from onWater's "My Waters"; `map_gauges.js`, in both
  maps). A tap on a USGS gauge shows its latest flow (cfs), gauge height (ft) and water temperature (°F), as far as the
  gauge reports them, with the reading's time and how the flow compares with the usual for the date: the visitor's own
  browser asks the USGS Water Data API (`latest-continuous`, and once a day per gauge the Statistics API's percentiles,
  read as `11_context.py` reads them). Both answer any web site (CORS); no key is sent (keyless requests count against
  the visitor's own connection; the project's key is for builds only and never goes in a page). The phone keeps every
  reading it gets (localStorage): with no connection, or when USGS doesn't answer, a popup shows the newer of the last
  reading the phone saw and the build's (`LBL.gauge_list`), and says which and from when; a value the gauge didn't send
  shows USGS's reason (ice, equipment...). A saved area (Offline, as an app) keeps its gauges' readings: fetched as it
  is saved, and again when it is opened with a connection and they are over 30 minutes old. A gauge's icon takes the
  colour of the newest reading the phone has. **My Waters:** "☆ Add to My Waters" in a gauge's popup; a name, an ideal
  flow range and, if wanted, a gauge-height range; green inside, red outside, grey with no range or no reading; kept on
  the device only, no account, one list for all maps; the ★ button under the map's buttons (there once the list has a
  gauge) opens it, and "Show on map" goes to the gauge (`#lat,lon,zoom&on=gauges&gauge=<site>` opens its popup). The
  trout calendar's "now" on a reach with a USGS gauge on its creek (`05b_flow.py`'s `gauge_site`, stream property `g`)
  shows the gauge's reading under the flow note. LA's two CDEC gauges keep the build's reading (CDEC answers no other
  site). In an iPhone's Home Screen app the list is the app's own, apart from Safari's. The build's own readings
  (in a popup until the live one comes, and in the one-file map) show on the area's clock with its zone ("Nov 25,
  7:30 AM EST"): `11_context.py` keeps gauge times in UTC.

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
    road and trail in the range, the trail layer's steps and bike paths, and the Forest Service roads OSM lacks), since
    trails switchback. The agencies' trails OSM lacks (the trail layer's dotted "official only" ones) are **faint
    trails**, walked at 60% of a trail's speed where no OSM way runs (the user, 2026-11-25: "Walk them slower", since
    OSM's lack of a trail often means it is overgrown). Off-trail creek bottoms walk at 45% of a trail's speed and
    other ground (chaparral) at 30%; slopes over 45° are near-impassable, and so are lakes off trails.
  - **Biking** is used wherever it beats walking: 18 km/h on the flat, slowed by grade (about 10 km/h at 6%), ×0.7 on
    dirt roads and ×0.5 on singletrack, on the road's or trail's own grade along the line over 200 m (capped at 25%),
    not the hillside's. **Bikeable:** every road closed to cars and every fire road (the closures counted for
    mid-July and roads cut off by them, OSM roads tagged access=no / motor_vehicle=no, OSM tracks, access roads of
    class "bike", the trail layer's fire roads, the Forest Service roads OSM lacks), every OSM bike path (downloaded
    by `08_hike.py`, kept a week), and
    singletrack the trail layer marks bike-legal; never in wilderness. Other singletrack is walked; private roads
    neither layer lists stay out.
  - **Fire roads where bikes may not be allowed are still ridden**, and their bike time counts. A route that rides
    one for a minute or more gets `bike_check` (why: wilderness, posted no bikes, a fire closure, closed or private in
    OSM, a Forest Service road missing from OSM) and `bike_check_min`; popups say "⚠ fire road: double-check bike access".
  - Each reach/drop gets `approach_min` = `bike_min` + `walk_min` and its trailhead; reaches also get
    `approach_med_min`, the typical time along the reach, and `bike_med_min`, the minutes of it ridden. A point in a
    lake counts as reached at the nearest reachable shore of its own lake, and each lake gets an approach
    (`hike_lakes.csv`).
  - Last, **the routes themselves** (`approach_routes.py`), for the maps to draw on a tap: every route followed back
    from its approach point through the cost-distance's traceback to its trailhead, kept once as a network
    (`hike_routes.gpkg`, `hike_route_starts.csv`: the routes share their trunks), cut where they join, start or change
    kind (bike, on a trail or road, off trail, creek bottom; a run under 30 m between two of one other kind takes
    theirs, under 60 m between off trail and creek bottom). A bike run or a trail-or-road run is drawn on the line `08_hike.py` burned in, not on the 10 m cells.
    Read after everything above is written: the times don't change.
  - **Official access sites start routes too**: a fishing access site or boat ramp with parking (`02e_access.py`) within
    400 m of an open road is a start, so a site at the end of a lane OSM marks private or doesn't map counts, and a route
    that starts at one says so ("park at Johnson Ferry North Boat Launch").
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
- `11c_land.py` (after `11_context.py`): the **land-ownership layer** (`land_data.js` beside the map pages, loaded the
  first time the layer is turned on; `map_land.js` draws it on both maps). PAD-US 4.1's fee holdings, easements and
  tribal and military boundaries, cut against each other, the reaches' access flags (`context/cpad_restricted.gpkg`)
  and the counties (TIGERweb), and sorted by PAD-US's own owner type (its manager's where it records no owner) and
  public access into public land, conservation or open private land (land trusts and other non-profits, private land
  open to the public, easements with access), tribal land and private land (everything else, and all land PAD-US
  doesn't list). A piece inside a flagged holding says what the creeks' popups there say, so the two never disagree.
  Every name PAD-US gives is shown, easements and private holdings included (the user, 2026-11-25: "i want names of
  owners, clearly private land, clearly public land"), and the popups say where each comes from. Organizations get
  their own website and office phone (`scripts/land_contacts.csv`, by organization); a private person never gets a
  phone, e-mail or address. Private land links instead to its county's official parcel viewer
  (`scripts/county_viewers.csv`, at the spot where the viewer allows it). The step's NOTEs list the biggest
  organizations with no contact and the counties with no viewer. The look is the user's pick of three iPhone mockups:
  public land solid green, conservation land teal, tribal land violet, private land red stripes, with a key in plain
  words and names written on the land once zoomed in.
- `11d_parcels.py` (after `11c_land.py`): **owners' names for the private parcels beside the water**
  (`parcels_data.js`, loaded by `map_land.js` once zoomed in to 13 with the land layer on). It takes every parcel on
  the land layer's private land that touches a drawn stream or a lake's shore within 30 m, from the official parcel
  layers in `scripts/parcel_sources.csv`: layers whose terms allow reuse, and official layers that publish owner names
  openly with no reuse terms stated (the user's choice, 2026-11-25). Never one whose terms restrict or forbid reuse,
  never a data broker. The servers are asked only for parcels near the water (an ArcGIS distance query along the
  streams and lake shores, a cell at a time) and only for the owner fields. A name a source withholds by law shows as
  withheld. Each popup gives the owner, the source and its date, and the county's official record; never a mailing
  address. A source that can't be read leaves its counties without names (a NOTE), and its last good copy is used
  offline. Each layer is on the credits page with its licence.
- **Trout evidence** (`context/trout_evidence.gpkg`): in LA CDFW Heritage & Wild Trout Program surveys (trout found
  or not), CDFW stocking in the last 12 months and iNaturalist research-grade rainbow and brown trout sightings with
  an exact location; elsewhere each state's records (Study areas, above). A survey or stocking point counts for the
  creek of the same name within 5 km; a sighting for its reach (within 150 m) and the same creek within 1.5 km. Lakes
  are left out of the score (their trout are stocked): stocked lakes, and sightings at a lake or within 400 m of a
  stocked one. `scoring.py` merges all of these onto the reaches and drops and computes the final fish score.
- **Trout species** (`troutspecies.py`), for the maps' species filter: `11_context.py` gives each reach the species its
  trout records name, with the latest year of each (`spp_found`: "brook 2018, brown 2024"), and those its own designated
  waters name (`spp_water`), read as its own trout water is (a tributary that only touches a designated river at its
  mouth reads none of the river's). A species counts only where the words name it: a record's label, a water's
  designation, and a water a source lists for wild brook trout; hybrids, steelhead and golden trout count as none of
  brook, brown, rainbow, cutthroat and lake trout. The pages carry it per reach as `sp` (`06_map.py`, `map_filter.js`).
- `11e_coverage.py` (before `06_map.py`): the **cell coverage layer** (`coverage_data.js` beside the map pages, loaded
  the first time the layer is turned on; `map_coverage.js` draws it on both maps). The user, 2026-11-25, from onWater:
  where each carrier has signal, to know where to save an offline map before heading out. The FCC's National Broadband
  Map (Broadband Data Collection), mobile broadband availability as of its latest date: each facilities-based
  carrier's 4G LTE (5/1 Mbps) and 5G-NR (7/1 Mbps) coverage outdoors, modelled by the carrier under the FCC's rules (a
  90 % chance at the cell's edge, the cell half loaded), as the FCC's own H3 hexagons (resolution 9: 0.1 km², about
  1,100 ft across), by carrier and state. A file is read once for every map: its hexagons within all of config.py's
  areas are dissolved into one outline and kept as `data/raw/_national/fcc_bdc/<the FCC's file name>.json.gz` (about
  100 MB for the 12 maps); the download (126 files, about 7.6 GB for the 12 maps' 16 states) is deleted as it goes. A
  file the FCC revises has a new name and is read again; a map whose boxes a copy doesn't cover reads it again; offline
  the copies are all it needs. Each map gets every carrier the FCC lists there with at least 1 km² of it, each one's
  share of the map, and "any carrier", outlined on the hexagons (60 m of simplification, which leaves them as they
  are). A picker in the legend shows one at a time; with the layer on a tap on the map gives each carrier's signal
  there, and the other popups end with the same line. The FCC's API terms ask for the notice "This product uses the FCC
  Data API but is not endorsed or certified by the FCC", in the layer's key and on the credits page. 5G at 35/3 Mbps
  lies inside 5G at 7/1 and isn't read; 3G isn't shown.
- `12_profiles.py` (after `06_map.py`): long profiles for every named creek (`profiles_data.js`): the longest
  connected path through its NHD named flowlines, at the channel bottom (the lowest conditioned DEM cell within 20 m,
  only going down downstream), with drops, falls and gauges snapped on and fish score, burn, trout-water and habitat
  strips from the creek's own channel only (reaches named after it, or unnamed ones up to twice its largest named
  reach + 1 km²). The drainage is what the map's reaches carry (`area_full_km2`): the routing's own and the water from
  outside the map, over dams and past ponds, added on the creek's own reaches (an unnamed one only within the same cap
  on full drainage), so a river from outside reads its whole basin (the Schuylkill 1,192 sq mi where it leaves the
  Brandywine box, was 142). Drop colours match on the map and the profiles (magenta
  waterfall-like step, yellow cascade, violet short fall, ink at mapped waterfalls), colour-blind safe.

## Fish score (0–100, heuristic; `scripts/scoring.py`)
`water × (30% size + 30% thermal + 15% gradient + 25% remoteness) × burn × trout × heat × channel × warm`, capped at 100.
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
- **warm (warm-water gate, the user's choice 2026-11-25):** ×0.5 where the reach's estimated summer water temperature
  (`watertemp.py`) is 74 °F (23.3 °C) or more, unless it is a tailwater, a survey found trout
  on it in the last 10 years with no later survey finding none (`11_context.py`'s `trout_survey`: an agency's sampling,
  not a stocking list or an iNaturalist sighting), or it is wild brook trout water. A designation, stocking or a
  sighting alone doesn't exempt it. From the r/bluelining rules of thumb ("most trout above 1,600 ft" in the southern
  Appalachians): on the maps of 2026-11-25 half of north Georgia's best water lay below 1,600 ft at an estimated
  70–75 °F (`bluelining-bands-report.md` in the overview's notes). The popup's Heat row and the score's breakdown
  ("Warm water ×0.5") say so.
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
| Land | PAD-US (the public-access service); where PAD-US leaves the water out (Jackson Lake), the unit most of the shore lies in. Access is flagged only where closed, or restricted outside federal land. The holding's name only where `landnames.py` allows (never a private individual's); an easement reads "(easement)" |

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
a river through a big lake takes the time to the nearest shore. A point in a lake takes the nearest shore cell that can
be reached by land, or, where it is quicker, the quickest shore of the mainland (land joined to a road without crossing
water, not an island's) with the walk along the shore for its extra distance beyond the nearest one charged at the
off-trail pace (so a shore kilometres off never wins); a faster network can't make that second part slower. A Forest
Service road record under a lake (a drowned road) is cut at the shore, not used as a causeway. Times are a fit hiker's without stops (Tobler), a
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
