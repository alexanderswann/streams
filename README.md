# LA Mountains Stream & Waterfall Analysis

DEM-based stream analysis of the mountains around LA, used to find remote fishable water and in-stream drops
(waterfalls / plunge pools). It covers eight ranges, defined in `scripts/config.py`. The boxes
meet edge to edge, so a creek that crosses an edge is split between two ranges there. (Only the San Gabriel and
Santa Monica boxes overlap: a 1 × 4 km strip of the San Fernando Valley floor, where a few flat-land channels are
drawn by both.)

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

Warm, low ranges (Santa Anas, Sierra Pelona, much of Piru) score low for trout by design. They are included for
swimming: the stream popups' NHD flow class (perennial or not) and the drop / plunge-pool and waterfall layers apply
there regardless of fish score.

## One map for all areas
`output/index.html` (`scripts/13_overview.py`, no AREA needed) is a map of every built area: drainage outlines and
main rivers, with a list of the areas. A click inside an area opens its full map at that spot, and each area's 2D
and 3D map has a "Go to…" menu in the legend that jumps to any other area or back to this map at the current view.
The full detail stays in the per-area maps because all six in one page would be over 200 MB. With the local preview
server it is `http://localhost:8766/`; on the phone copies, `phone/index.html`.

`output/index.html` is only a front page: sent to a phone by itself it has nothing behind its links. Two ways to
carry the maps:
- **One file** (`scripts/14_portable.py` → `output/stream_maps_all.html`, about 24 MB): the same map of all areas
  with every area's detail packed inside it as gzip and unpacked when you zoom in there: every stream reach with the
  full popup, and switches for drops and waterfalls, trailheads and parking, trails and dirt roads, gauges and road
  closures, trout records. No 3D view, creek profiles, hillshade or land-status layers. Send this one.
- **After a change to the drainages** (`05c_drainages.py`, `crossbox.py`, the outline part of `06_map.py`):
  `scripts/run_drainage_refresh.sh <area> ...` redoes 05c per range, the map and the profiles; then
  `13_overview.py`, `14_portable.py` and `phone_sync.sh`. The scores don't change.
- **The website** (`scripts/publish_site.sh`): copies the map of all areas and every area's maps into
  `publish/alexanderswann.github.io/streams/` (a local copy of the GitHub Pages site; `streams/` was 605 MB on
  2026-11-20, and GitHub Pages refuses a site over 1 GB) and commits
  there; `scripts/publish_site.sh push` also pushes, which puts it live at
  `https://alexanderswann.github.io/streams/` (published 2026-11-19; the login is a token for that one repository
  in the Mac's keychain). A push goes up area by area, through a temporary branch `publish-upload`, then `master`
  once, so the site builds once: in a single push git sends most files whole, 85–134 MB for a full republish instead
  of a few MB (2026-11-20). Afterwards it rebuilds the phone copies (`14_portable.py`, `phone_sync.sh`) from the same
  maps. It stops while a build is running; with `push now` (maps just built and checked), test runs in a session's
  scratchpad folder don't count, unless they run a step that writes published files. It adds the `streams/` folder
  and nothing else: the site already
  there is not changed, and the script stops if its commit would touch anything outside `streams/`. The maps
  show the start ZIPs; that was the owner's choice.

## Study areas and folders
The pipeline handles several study **areas**, each its own map with its own UTM zone, home point for drive times,
ranges and data sources (`AREAS` in `scripts/config.py`). Pick one with `AREA=<key>` (default `la`) and a range
within it with `REGION=<key>` (default the area's first range). Everything described below is the `la` area unless
it says otherwise. `MULTI_AREA_LOG.md` is the dated record of how the other areas were added and why.

| Area key | Area | Ranges | Home (drive times) |
|---|---|---|---|
| `la` | LA mountains | the eight above | 90404 Santa Monica |
| `jackson` | Jackson Hole, Grand Teton & Teton Valley, WY and ID (all of Grand Teton NP, Teton Valley around Driggs, Palisades Reservoir and Alpine; grown from three boxes to seven on 2026-11-19, laid out so no lake, and no reservoir's filled basin, crosses an edge between two boxes: see `MULTI_AREA_LOG.md`) | `teton_snake`, `gros_ventre`, `hoback`, `jackson_lake`, `buffalo_fork`, `teton_valley`, `palisades` | 83001 Jackson |
| `n_georgia` | North Georgia mountains | `cohutta`, `blue_ridge`, `rabun`, `hooch_tailwater` | 30305 Atlanta |
| `central_vt` | Central Vermont (the Green Mountains from the White River to the Lamoille, and since 2026-11-20 the Champlain Valley west to the New York line in the middle of Lake Champlain: the boxes reach past the line, and the map is cut at it, `clip_state` in `AREAS` and `areaclip.py`) | `stowe_lamoille`, `mad_winooski`, `white_river` | 05753 Middlebury |
| `ne_ct` | Northeastern Connecticut | `natchaug`, `quinebaug` | 06281 Woodstock |
| `lexington_va` | Lexington, Virginia | `maury_goshen`, `blue_ridge_va` | 24450 Lexington |
| `se_pa` | Southeastern Pennsylvania (and northern Delaware) | `brandywine`, `ridley_valley` | 19063 Media |
| `smokies` | Great Smoky Mountains National Park and around it (TN / NC) | `cades_cove`, `le_conte`, `cataloochee`, `tellico`, `snowbird`, `nantahala`, `tuckasegee` | 30305 Atlanta |
| `adk_high_peaks` | Adirondacks: High Peaks & Lake Placid (the High Peaks, Saranac lakes, Ausable, Boquet, Lake Champlain shore, Chateaugay and Chazy lakes) | `high_peaks`, `boquet`, `saranac`, `wilmington`, `champlain`, `chateaugay` | 05753 Middlebury |
| `adk_northwest` | Adirondacks: Long Lake, Tupper & Cranberry (the Raquette from Raquette Lake to Carry Falls, Stillwater, Cranberry Lake, Five Ponds, the St. Regis) | `beaver`, `long_lake`, `tupper`, `st_regis`, `lake_ozonia` | 05753 Middlebury |
| `adk_southwest` | Adirondacks: Old Forge & West Canada Lakes (the Moose and Black rivers, West Canada Creek, Piseco and Speculator) | `moose`, `west_canada_lakes`, `west_canada`, `speculator` | 05753 Middlebury |
| `adk_southeast` | Adirondacks: Hudson, Indian Lake & Lake George (the Hudson below Newcomb, Indian Lake, the Great Sacandaga, Schroon and Lake George) | `indian_lake`, `minerva`, `siamese`, `sacandaga`, `lake_george` | 05753 Middlebury |

The four `adk_` areas are the whole Adirondack Park (its Blue Line, 23,560 km²) in four maps: one map of the park
would be about 150 MB, over GitHub's 100 MB file limit and too heavy for a phone. The lines between them avoid
cutting lakes and keep each river on one side (see `config.py` and `MULTI_AREA_LOG.md`, 2026-11-19 evening).
Since 2026-11-20 they are hidden (`hidden=True` in `AREAS`): still built, kept and published at their addresses, but
not on the map of all areas, in the other maps' "Go to" menus or in the one-file map. Take the flag out to show them.

| Folder | What |
|---|---|
| `data/raw/<area>/<range>/`, `data/derived/<area>/<range>/` | Per-range downloads (DEM, NHD, OSM, canopy) and derived rasters (filled DEM, flow direction, area) |
| `data/raw/<area>/_shared/` | Shared by an area's ranges: trails, access roads, wilderness, flow model, long-distance trails, download caches |
| `data/derived/<area>/_shared/` | Cross-box inflow table (`inflows.json`) |
| `data/raw/_national/` | Downloads every area reuses: NHD HU4 GeoPackages, the PRISM August air temperature grid, the Census TIGER/Line state outlines (`areaclip.py`) |
| `output/<area>/` | The combined map, CSVs and GPX below, plus one folder per range |

**What differs outside California.** Each area lists the sources that exist only for it (`sources` in `AREAS`;
`has("name")` in the scripts). LA has all of the California ones; the other areas use national data in their place:

| In LA | In the other areas |
|---|---|
| TNC California Natural Flows (modelled monthly flow per year) | NHDPlus V2's EROM mean flow for the month × a yearly index from the area's own USGS gauges (`02b_download_flow.py`). One index per area, so small headwaters that dry faster than the gauged creeks are over-rated in droughts |
| CAL FIRE fire history | The interagency fire perimeter history (NIFC) |
| CPAD restricted / no public access | PAD-US holdings recorded as restricted or closed. Most eastern holdings are "unknown" there and aren't flagged |
| CDFW surveys, stocking, Wild / Heritage Trout Waters | Each state's own (`troutdata.py`): CT DEEP fish samples, stocking and trout management areas; Vermont's brook trout waters and stocking list; Virginia DWR wild trout streams (classes I–IV) and stocked waters; Georgia DNR designated trout streams, stocking and samples; Wyoming Game & Fish trout-stream classes and native cutthroat waters; Idaho Fish & Game's Yellowstone cutthroat trout streams, as StreamNet's regional fish distribution serves them (the Idaho side of the Jackson map: Teton Valley and Palisades; Idaho publishes no survey or stocking layer); the Pennsylvania Fish & Boat Commission's Class A and natural-reproduction wild trout streams, trout special-regulation areas, stocked sections (fish per species) and stocked lakes; Delaware DNREC's designated trout streams; in the Smokies, North Carolina WRC's mountain trout waters by class (Hatchery Supported and Delayed Harvest, which it stocks, catch-and-release, named Wild Trout Waters; not the game lands' blanket "Wild Trout Waters unless otherwise noted", which covers every creek there), Tennessee WRA's stocking sites, electrofishing samples (1996-2022) and brook trout genetics collections, the national park's own trout distribution map (its "No Fish" code marks unsampled streams and is not used; segments it marks internal are left out) and the Cherokee tribal fishing zones (the Raven Fork trophy section and the Enterprise Waters); in the Adirondacks, New York DEC's categorized trout stream reaches (Wild-Quality, Stocked, Stocked-Extended, with the species and number stocked), the streams classed trout (T) or trout spawning (TS) in the state's water quality standards, and public fishing access along trout streams (DEC's fishing rights easements; DEC publishes no survey layer, and its pond stocking list has towns, not coordinates); plus Trout Unlimited's brook trout patches from New York and Connecticut to Georgia, and iNaturalist (rainbow, brown, brook and cutthroat trout). Outside California a no-trout sample counts for the same creek within 1.5 km only, and only Connecticut's and Tennessee's electrofishing samples make one |
| CDFW natural fish-passage barriers among the known falls | none, except the Smokies, where the national park's own waterfalls layer is added; the other sources are the same everywhere (OSM, NHD, USGS GNIS, Wikidata and the area's guidebook and inventory falls, `02f_known_falls.py`) |
| Caltrans and county road closures | Keyless feeds where they exist: Grand Teton NP and Teton County (Jackson), Georgia 511, New England Compass (Vermont), the Blue Ridge Parkway and Virginia 511 (Lexington); in the Smokies the Blue Ridge Parkway, NCDOT's incident layer (the TIMS feed behind DriveNC), TDOT SmartWay's event points, the park's own alerts (closures by road name, drawn on the park's roads layer) and its table of secondary roads' open seasons, and the Cherokee National Forest's road construction table (North Carolina's national forests publish closures only as prose and PDFs); none for NE Connecticut, southeastern Pennsylvania or the Adirondacks (511NY needs an API key) |
| The Pacific Crest Trail layer | The area's own long trail (`long_trail` in `AREAS`): the Appalachian Trail (North Georgia, Lexington, the Smokies), the Long Trail (Vermont), the Horse-Shoe Trail (southeastern Pennsylvania), the Northville-Placid Trail (the Adirondacks); none for Jackson or NE Connecticut |
| USFS wilderness (no bikes) | The same layer, plus in the Adirondacks the Forest Preserve's Wilderness, Primitive and Canoe areas (NYSDEC lands; the State Land Master Plan keeps bikes out of them), source `nys_forest_preserve` in `geomatch.wilderness_path()` |
| CDEC gauges, the State Parks / NPS / Eaton Fire trail layers | none |
| NHD "artificial paths" (river and lake centrelines) are not perennial: they cross dry washes and reservoirs | They count as perennial: in wet country they are the rivers |
| Elevation band in `05_score.py`'s first-pass score | none |

The fish score itself is the same everywhere, but it was tuned for LA, where most channels are dry: in the wet
areas most reaches score over 50, so scores rank creeks within an area and aren't comparable between areas. The
water-temperature fit (`watertemp.py`) is made per area from the best of August air, elevation and drainage area
(LA: air + elevation; NE Connecticut: drainage area; Lexington and Jackson: elevation + drainage area; Vermont:
air + drainage area; North Georgia: elevation; southeastern Pennsylvania: air + drainage area, which can't see the
limestone-spring creeks such as Valley Creek: they read about 22 °C and measure about 15). Tailwaters are listed per area in `scoring.py` (LA's two; in North
Georgia the Chattahoochee below Buford Dam and the Toccoa below Blue Ridge Dam; in the Smokies the Nantahala below
Nantahala Lake, whose powerhouse at Beechertown releases water from the bottom of the lake); diversions in `flowlib.py` (LA
only).

To build another area, from `scripts/`: `./run_base.sh <area>` (DEM, NHD + OSM, hydrology, drops), then
`./run_mid.sh <area>` (reach scoring, flow, drainages, trails, access roads, the long trail), then
`./run_late.sh <area>` (road closures, approach times, sun, drive times, context, water-temperature fit, maps,
profiles). After a change to the hydrology, `./run_rebuild_a.sh <area>` redoes 03, 03b and the drops, then runs `run_mid.sh` and
`run_late.sh` (`SKIP_03=1` starts at 03b, after a change to `03b_stitch.py` only: 03's surface stays as it is). `./phone_sync.sh` copies every area's maps to `phone/` with an index page.
`data/validate_flow_areas.py` checks an area's flow table against its gauges. Logs go to `data/base_<area>.log`,
`mid_<area>.log` and `late_<area>.log`. Run long builds under `caffeinate -i` (a sleeping Mac froze two downloads).
OpenStreetMap downloads try `overpass.openstreetmap.fr` first and the main Overpass server second.

## Outputs (`output/la/`)
Everything the maps, popups, creek profiles and GPX files show is in imperial units: feet, miles, square miles,
acres and °F (flows in cfs), with scale bars and the measuring tool in feet and miles (owner's choice, 2026-11-19).
The pipeline and its files stay metric (the columns are named `_m`, `_km`, `_km2`, `_ha`); `scripts/units.py`
converts what a person reads, and the pages' own scripts carry the same few conversions. New popup or legend text
goes through those helpers. Text quoted from a source keeps its words, with the imperial figure in brackets after
each metric one (`units.imperial_text`: CDFW's surveyors write "2.5 meters [8.2 ft] wide by 2.5 feet high").

| File | What |
|---|---|
| `stream_map.html` | Combined interactive map. It loads `map3d_data.js`; keep it next to that file and the region folders, which hold the hillshade PNGs |
| `map3d_data.js` | The layers both maps draw (streams, drainage fills and divides, the long trail, trails, roads, parking and their labels), loaded by both pages: one copy instead of two since 2026-11-20 (the website's 1 GB limit). The 2D page points its `window.STREAMS` etc. at its entries |
| `stream_map_3d.html` | The same map in 3D (tilt, rotate, real terrain), with the layers only it draws inside the page (after `Object.assign(window.MAP3D, `); the rest comes from `map3d_data.js`. Keep it next to that file. Needs internet for MapLibre and the terrain tiles |
| `stream_reaches_ranked.csv` | Every DEM stream link (≥1 km² drainage), all ranges, ranked by fish score |
| `waterfall_candidates.csv` | All detected drops with height, run, slope above/below, plunge-pool coordinates |
| `waterfall_candidates.gpx` | Waterfall-like steps, cascades and their pools. Import into Gaia, CalTopo or onX |
| `road_closures.csv` / `.gpkg` | Current closures on mountain roads (Caltrans, LA County, SB County), routed along the roads |
| `gated_roads.gpkg` | OSM roads tagged closed to public vehicles (locked fire roads, gated forest roads) |
| `profiles.html` | Creek profile viewer: elevation vs. distance for about 490 creeks (those with 2 km or more of channel named in NHD; a link from the map to any other creek says it has no profile), with drops, falls, gauges and fish score / burn / trout-water strips. Keep it next to `profiles_data.js` and the map |
| `context/` | Fire perimeters, stream gauges (USGS + CDEC, live), wilderness, non-Forest-Service land, critical habitat, Wild Trout Waters, trout evidence, springs |
| `<region>/` | The same per range, plus `streams_scored.gpkg` / `waterfall_candidates.gpkg` for QGIS. The `fish_score` in a range's own `streams_scored.gpkg` and `stream_reaches_ranked.csv` is `05_score.py`'s first pass (NHD class, size, elevation, gradient, distance to a road); the final score is only in the combined `stream_reaches_ranked.csv` and the maps |

## Pipeline (`scripts/`, run from `scripts/` with `../.venv/bin/python`)
Steps 1–5 run once per range, with `REGION=<key>` set (default `san_gabriel`; for another area add `AREA=<key>`):
1. `01_download_dem.py`: 10 m USGS 3DEP DEM, in the area's UTM zone (11N for LA)
2. `02_download_vectors.py`: NHD flowlines/points from USGS bulk GeoPackages (cached in `data/raw/_national`),
   plus OSM roads/trails/waterfalls/dams. Both are read for the lon/lat box around all four corners of the range's
   UTM box. When the public Overpass servers can't be reached, a range keeps the OSM files it already has
   (`OSM=keep` skips that download outright); run the script again later to refresh them
3. `03_hydrology.py` (per box) + `03b_stitch.py` (per area): fill pits/depressions → D8 flow direction → flow accumulation → streams (≥0.25 km²) → Strahler order.
   Boxes that share an edge are solved as one surface: 03 conditions each box's DEM together with a 5 km margin of its
   neighbours, and 03b takes the flow directions, drainage areas, streams and stream orders across the boxes side by
   side, so a creek crosses a box edge as one line with one size. (Until 2026-11-19 each box was solved alone and no
   stream crossed an edge.) `area_km2.tif` counts every cell upstream in the joined boxes; `crossbox.py` adds only what
   the terrain can't see: rivers entering from outside every box, and lakes' water past their dams.
   A lake, or a reservoir's basin filled to its spill level, that reaches further across an edge than the 5 km margin
   can be filled one way by each box, and its water stopped on the edge short of the dam (the Snake below Jackson Lake,
   the Raquette below Raquette Pond and Carry Falls). Since 2026-11-20 03b finds every such dead end and conditions a
   piece of the DEM around it again as one (`mend_seams`); it exits with an error if one is left. A lake whose water
   leaves it on an edge between two boxes flows on instead of ending there, since `crossbox.py` carries a lake past its
   dam only within one box.
   Flats are given their slope in steps of 1e-9 m a cell, not pysheds' default 1e-5: the default piles up across the
   flattened water surface of a mapped river until the flat becomes a pit, which ended flow paths all along the big
   rivers of the wetter areas (found 2026-11-18; LA's dry channels showed it only at reservoirs). Flow paths are
   still ended on purpose at every lake and reservoir of 8+ ha that holds water, at the cell where the water leaves
   it: drainages end at dams, and `crossbox.py` carries the area on. "Holds water" means 2+ ha of the outline at
   one elevation in the DEM; water runs through dry flood-control basins and reservoirs that were drawn down when
   the DEM was flown (San Gabriel Reservoir, Cogswell, Devil's Gate). A lake whose water leaves the map through its
   own surface (where most of its water gathers is on the map's edge: Lake Champlain, Tellico, Hartwell) carries no
   stream lines since 2026-11-20: its flat water had drained to the edge along dozens of parallel made-up creeks.
   The creeks end at its shore, and `03b` lists such lakes per box (`lakes_off_map.gpkg`) for `05c`.
   Since 2026-11-21 every cell of a lake that holds water drains to its outlet along NHD HR's lines through the lake
   where they run (`route_lake`: a least-cost path over the lake's cells, a step off the lines counting five along
   them), and the way the water takes below the outlet is a stream line down to the first stream it meets
   (`outflow_streams`). Only the path that gathered the most water used to end at the outlet. The flat water's own
   directions let other paths cross the lake and leave it on their own: Pilgrim Creek's ran to Jackson Lake Dam beside
   the Snake's outlet, so the line across the lake and over the dam was Pilgrim Creek's, and Palisades Reservoir's
   crossing read Trout Creek. They drew 986 km of straight made-up lines across lakes over the 12 maps (now 266 km).
   And with no line of its own below the outlet, the lake's water, which `crossbox.py` puts back in below the dam,
   landed on the first line it met and was counted along that whole link, a side creek's included: Lower Slide Lake's
   1,539 km² on a 2.7 km creek beside the Gros Ventre, Leigh Lake's on a creek beside String Lake (120 such creeks over
   the 12 maps). Measured on all 12 maps before it went in (`data/stream_burning/`): drops, known falls, flow drops and
   edge dead ends unchanged or better; lake outlets reading under half of NHDPlus 45 → 39. The folder also keeps the
   experiment this came from, NHD's lines burned into the DEM itself, which is not used: burned everywhere they lost
   waterfall-like steps in the mountains, burned on flat ground only they reshuffled braided rivers' arms.
4. `04_knickpoints.py`: step detection. Contiguous runs of channel steeper than 25% (30 m window), compared
   with the channel 200 m above and below. Classes:
   - **waterfall-like step**: max slope ≥ 0.6 and ≥ 2.5× steeper than the neighbouring channel
   - **cascade / knickpoint**: ≥ 1.8× steeper than neighbours
   - **steep reach**: uniformly steep, no clear break
   `04b_bigcreek_steps.py`: second pass for **short falls and plunge pools on big creeks** (≥10 km² drainage).
   It flags ≥3 m of drop over 30 m that is ≥2.5 m more than the creek's trend (the steeper of the 200 m above or below)
   and ≥2.5× steeper than that trend. It records `excess_drop_m` and `pool_depth_m` (DEM depression just below the step).
   Only hits on NHD-perennial creeks are kept, and anything pass 1 already found is dropped.
   Shared flow-path code lives in `flowpath.py`.
   `02f_known_falls.py` (per area, before step 5; `run_mid.sh` runs it first): the known waterfalls, every source merged
   into `data/raw/<area>/_shared/known_falls.gpkg`. Sources: OpenStreetMap (queried in tiles of at most 0.5 degrees: one
   query over a whole area's box hung on both public servers; waterfall nodes and ways, named rapids,
   named swimming holes, and features named for falls, cascades or potholes that sit on a stream); NHD waterfall points;
   USGS GNIS features of class Falls or Rapids (the current file and the 2021 archive, in `data/raw/_national/gnis`);
   Wikidata waterfalls, rapids and swimming holes; CDFW's barrier surveys (LA); the national park's waterfalls layer
   (Smokies); and the hand-researched falls in
   `data/known_falls_curated.csv`: Vermont's 1985-88 state inventory of waterfalls, cascades and gorges, New England
   Waterfalls, the World Waterfall Database, the Vermont River Conservancy, the 1999 San Gabriel waterfall list
   (Chester, Strong & Ayers) and others, each row with its source page and a note on how its point was placed. One fall
   from several sources becomes one point: the same name within 500 m (2 km for exactly the same name: GNIS puts
   Raven Cliff Falls 1.4 km off), an unnamed point within 100 m of a named one, or any two within 25 m; never two
   points of one source, and never two different names except on the same spot ("Little Moss Glen Falls" is not
   Moss Glen Falls). `precise` marks points on the fall itself (OSM, NHD, CDFW, guidebook GPS at the fall): only those
   can outrank the artifact tests in step 5; GNIS points and points placed from directions still name a drop within
   200 m. A curated row can also name, move or drop a source's point (`replaces`: the misplaced second GNIS "Bingham
   Falls" in Smugglers Notch is Hell Brook Cascades). `known_falls_points.gpkg` beside the output lists every source
   point with the fall it went into. gawaterfalls.com's 695 Georgia falls (Mark Ozboyd's catalogue; published with credit
   at the owner's word, 2026-11-19) are in `data/known_falls_curated_gawaterfalls.csv`: each popup names and links his
   page for that fall, and `06_map.py` names any guide with 50+ falls on a map in its credits.
5. `05_score.py`: attributes, fish score, per-range exports, hillshade. Each link is measured on its own cells:
   drainage area and gradient at its second-to-last vertex (its last vertex is the confluence cell, which would give
   a side creek the trunk's area), Strahler order and elevation at its middle vertex. NHD name and flow class come
   from the nearest NHD lines at three points along the link, each kept when two agree on the name (or the class;
   NHD splits a creek into many short segments). NHD has no name on many lines (e.g. San Antonio Creek below
   Mt. Baldy): those links take the name of OpenStreetMap's named rivers and streams the same way (cached a week in
   `data/raw/<area>/<range>/osm_waterways.gpkg`). A link between two links of one river takes the river's name when
   the vote gave it none, or the name of a much smaller stream (every other link of that name within 3 km drains
   under half as much). Its two neighbours are its largest upstream link and the link below, with unnamed links
   passed over. This matters because NHD draws a creek's line out to the river's centreline, so on a short river link
   two of the three points can lie nearest the creek's line. A drop takes the name of the link its top cell is on; on
   an unnamed link it takes the nearest NHD line's within 80 m. Links mostly on sea-level
   cells (fake channels across the ocean) are dropped. Known falls are the area's list from `02f_known_falls.py`, taken
   within 500 m of the range's box; each range writes out only those inside its box, so each fall is drawn once.
   Each drop gets a status, first match wins: **dam / weir** (a mapped dam within 250 m); **matches mapped
   waterfall** when a precisely placed known fall lies on the step itself (within 50 m of its top-to-pool line); **likely DEM
   artifact** when a drivable road crosses the DEM channel within 40 m of the step's top, where an embankment or bridge
   deck would make the lip (a road only running alongside, as in many gorges, or crossing below a fall doesn't
   count), or when the detector's filled depression at the lip is so deep that the drop less
   the fill would miss its bar (the fill is about a barrier's height: a dam, culvert embankment or bridge deck);
   **matches mapped waterfall** for a known fall within 200 m of the top; otherwise the detector's class, unmapped.
6. `05c_drainages.py`: drainage basins. Every DEM cell is traced down the D8 flow directions to where it leaves the
   study area or ends in a sink (dams). Basins ≥25 km² are named drainages, named after their natural trunk creek
   (canals and aqueducts are skipped; a few NHD gaps are fixed by hand in `NAME_FIX` / `FORK_FIX`). Drainages
   ≥120 km² are split into forks: tributaries ≥35 km² that join the trunk. At a confluence the bigger arm continues
   the trunk, except where NHDPlus continues the river up the smaller arm (its level path, `flowlib.level_paths()`):
   each arm and the river below matched 300 m from the confluence, NHDPlus's own junction of the two branches where
   ours is, and the detailed NHD lines not naming that arm something else. Since 2026-11-20; before, the upper
   Conasauga was a fork "Jigger Creek", the upper Chestatee "Dicks Creek", upper Piru Creek "Mutau Creek" (33
   confluences on 11 maps changed; reaches whose label is their own name 484 -> 1,122). The map shows one level of
   forks, so a tributary of an arm that becomes a fork is grouped under it (Bear Creek under the West Fork San
   Gabriel). Everything smaller is grouped as
   "Minor front-range drainages". A tributary of 100+ km² that flows straight into a big river (2,000+ km² where
   it leaves the map, followed down the NHDPlus network along its own course) is a drainage of its own, with its
   own colour and forks, and the big river keeps what is left: Piru and Castaic creeks beside the Santa Clara; the
   Hoback, Gros Ventre and Greys beside the Snake; the Mad and Dog rivers beside the Winooski. A tributary that is
   itself that big sheds its own the same way; smaller ones keep their forks (Granite Creek stays in the Hoback).
   Sea-level water (DEM ≤ 0.5 m: the sea, tidal rivers) ends a path at the creek's mouth and belongs to no
   drainage; the DEM stores it as flat 0 m, and paths running on across it joined every creek on the tidal Delaware
   into one drainage. A creek that reaches the sea is named from 5 km². A lake whose water leaves the map (`03b`'s
   `lakes_off_map.gpkg`) counts as the sea here. Writes `drainages.gpkg` (fork polygons) and `stream_drainage.csv`
   (sid → drainage, fork, and Strahler order taken on the channel cell itself).
   - **Across box edges** (`crossbox.py`): each range's hydrology sees only its own box, so a creek crossing in from
     the next box would start again with no drainage area (the Santa Clara River entered the Piru & Castaic box with
     none, so Piru Creek won the trunk and the river's own valley was labelled "Castaic Creek"). Every basin that
     drains off an edge two boxes share is followed into the neighbour, down its flow directions to where the creek
     heads away from the edge, and its area (plus whatever flowed into it from a third box) is added along the creek
     before trunks and forks are picked. Where the neighbour's grid ends the creek in a pit on the edge (a road fill
     just inside: Bouquet Canyon entering the Piru box), the trace restarts from the lowest nearby cell that drains
     away from the edge. The inflow table is cached in `data/derived/<area>/_shared/inflows.json` until a `flowdir.tif`,
     the reservoir list or the NHDPlus network changes.
   - **From outside the boxes**: a river that enters from outside every box (the Santa Clara at Fillmore, the Maury
     above Goshen Pass, Otter Creek, the Snake) started with nothing too. Where an NHDPlus V2 river of 10+ km² crosses
     the outer boundary flowing in, its drainage there, less what the box's own routing and the edge links already
     have at that spot, is carried down the creek the same way. One that comes in through a reservoir (the
     Chattahoochee in Lake Lanier) is handed to the cell below the dam.
   - **Past dams**: every lake and reservoir ends its D8 paths at its outlet (`03b_stitch.py`; not one whose outlet is
     on an edge between two boxes), so the creek below the dam starts again near nothing (since 2026-11-21 on a line of
     its own from the outlet down to the first stream it meets, so the lake's water lands on the river below that
     junction, not along a side creek's line: see 3.). `crossbox.py` links each reservoir's dead
     ends to the cell below its dam where the water goes on, found by walking down the NHDPlus flowlines leaving the
     lake (Morris 533 km², Pyramid 514, Castaic Lagoon 412, Big Tujunga 212, Littlerock 165, Lake Hemet 143, Big Bear
     137, Matilija 132). Lakes with no outflow (Baldwin Lake) and dead ends away from lakes (desert fans, the sea)
     stay closed. Drainages still end at dams; only areas use this. NHDPlus (1:100,000) has no flowline for most small
     ponds, and below them a brook's drainage started again from nothing (293 ponds over the 12 areas, 2026-11-20:
     7,751 reaches too small for a stretch, the Soquee 390 km2 at the Chattahoochee where NHDPlus has 414): where
     NHDPlus has no line in the lake (or its lines find no way on), the box's detailed NHD stream line leaving the lake
     gives the cell below its outlet. Those links carry the reaches' areas (`area_full_km2`) but not the forks and
     drainage names: on them near-equal arms tipped the other way and the trunk left the named river (the upper
     Chattahoochee came out as a fork "Chickamauga Creek"), so `05c` picks forks on the area without them (and its
     trunks follow NHDPlus's main path, below).
   - Each reach's corrected areas go to `area_streams.csv`, added where `05_score.py` measured `area_km2`:
     `area_edge_km2` (with what flows in from other boxes; `05b_flow.py` uses it) and `area_full_km2` (also past dams;
     the fish score's creek size, and the area popups show).
   - Unnamed basins that drain off an edge get outlines too; `06_map.py` joins them, like the reaches, to the drainage
     and fork they continue into (upper San Francisquito Canyon → Santa Clara River) and drops the rest. Big
     tributaries stay drainages of their own (Sespe, upper Piru above Pyramid Lake, Castaic above Castaic Lake, Santa
     Paula): only pieces of one creek cut by an edge are joined. The Santa Clara River's own drainage covers
     1,675 km² of its 4,210 km² watershed; the rest is those tributaries or lies outside every study box.
7. `05b_flow.py`: dry-season water for every reach and drop, from The Nature Conservancy's California Natural Flows
   model (modelled unimpaired monthly flow per NHDPlus V2 segment, downloaded by `02b_download_flow.py`). A reach's low
   flow in a year is its lowest July–October monthly mean, scaled by drainage area: the reach's `area_edge_km2`, which
   counts what flows in from other boxes but not water from above a dam (the model assumes natural flow, and a dam
   can hold it back). Where that area would lower a reach's estimate below the one from its own box's area (41
   reaches: the model now matching a creek it didn't before, or a side creek inheriting a different segment), the
   old estimate stays, so possible trout water isn't lowered on uncertain evidence. A reach takes the nearest segment
   whose drainage agrees, leaving out the side arms of split channels (`flowlib.minor_arms`), which NHDPlus gives the
   whole drainage but little of the flow: NHDPlus's own minor-path flags (divergence 2, streamcalc 0) where the flow is
   NHDPlus's (every area but LA; each table was fetched again with the flags on 2026-11-19), and a pair rule for the
   rest. LA's Natural Flows model gives a minor path the natural flow of its whole drainage, so there only the pair
   rule applies. Two lines the same distance from a reach (it lies nearest to the node they share) go to the closer
   drainage, then the lower comid: the sort was unstable until 2026-11-20, so a change anywhere else could flip such a
   tie. Reaches off the model network take
   the unit-area flow of the first modelled segment downstream ("scaled"); the way down is the D8 walk from the reach's
   end, on through a lake from the cell below its outlet (crossbox's links), with each line vertex rounded to its cell
   (a vertex is a cell corner; until 2026-11-20 truncation put about half of them one row or column off, and walks
   that ought to stop in a lake slipped past it beside the channel). A segment found down a way that went through a
   lake may raise a creek's estimate but never lower it below NHD's class, as for one found in another box: a brook
   running into a pond inherits the river below it, which is no evidence that the brook dries. A way that ends in a
   lake draining off the map (`03b`'s `lakes_off_map.gpkg`, which carries no reaches) takes that lake's NHDPlus line
   nearest where the way enters the water, under the same rule, applied in each of the two passes (own area, and with
   the water from other boxes) before they are weighed (since 2026-11-20).
   `data/check_flow_drops.py` is the standing check for sudden flow drops (a reach under a quarter of the flow per
   km2 of both the reach above it and the one below it on the same creek). Where a creek has none below it in its own
   box (by either area) and its way leaves the box, the search goes on in the box it runs into: `03b_stitch.py` routes
   an area's boxes as one surface, but each box's reaches end at its rim, so until 2026-11-20 such creeks read "no
   data" (10 % of Jackson's reaches within 1.5 km of an edge between boxes; 569 reaches over the 12 areas). That box's
   reaches are matched as its own run matches them, with the water from other boxes from its `area_streams.csv`, so
   run `05c_drainages.py` for every box before `05b_flow.py`. A segment found in another box may raise a creek's
   estimate, never lower it below NHD's class (possible trout water stays in). Reaches in or below a reservoir are flagged,
   since releases set their flow. A reach lying at least half inside an NHD lake or reservoir with no model segment of
   its own is a reservoir reach too (until 2026-11-19 such reaches read "no data" or took the flow of the river below
   the dam, and were scored as streams: Fontana Lake's arms at fish 83), and since 2026-11-20 so is one with a segment
   of its own, where the lake holds water (`03b`'s level test puts a pit at its outlet): a reach matched to the creek's
   line above the lake had read as that creek (a reach all inside String Lake scored 100; 397 such reaches over the 12
   areas). One in a lake with no level water (a marsh or meadow NHD maps as a pond) keeps its own evidence. Where NHD maps a lake as river area, leaves it out or draws it smaller than the water, the lakes layer's outline counts too (`05d_lakes.py`, which `run_mid.sh` runs between `05c` and `05b`): a lake of 8+ ha, level in the lidar, not intermittent and not a lagoon (since 2026-11-20: the Little Tennessee inside Cheoah Reservoir, NHD river area, had scored 73 as a river; 196 reaches over the 12 areas, 125 of them at fish 60+). A lake NHD stores as several touching pieces counts as one for the share inside it (Palisades Reservoir is four: the Salt River's crossing, 72% in the four and under half in any one, had scored 80 as a river); whether it holds water is still read from the piece holding most of the reach. So are reaches below the seven diversions where a USGS gauge on the creek below shows
   it often dry (`DIVERSIONS` in `flowlib.py`): the Santa Ana River No. 1 dam, two Mill Creek intakes, and the Lytle,
   Plunge, City Creek and San Jacinto River diversions. The model can't see water leave in a canal. Their popups
   quote the gauge's share of summers flowing. Writes `flow_streams.csv` / `flow_drops.csv`: typical and drought-year low flow,
   the share of summers since 2011 it kept ≥0.1 cfs, and a class (year-round, usually flows, seasonal, mostly dry,
   reservoir, no data). `02b_download_flow.py` (no REGION needed) also fetches the daily records of every USGS stream
   gauge with 5+ years of data, for `data/validate_flow.py`, from the USGS Water Data API (`api.waterdata.usgs.gov`,
   which replaces WaterServices); it re-downloads its NHDPlus V2 and reservoir caches when ranges are added. The
   Natural Flows batches and the gauge records are kept for 30 days, then fetched again (`REFRESH=1` forces it): the
   model gains a month at a time. `05b_flow.py` prints a note when the latest year's July–October isn't complete yet;
   that year then counts on the months it has.
   Since 2026-11-20 `05b_flow.py` also writes the evidence `scoring.py` reads for creeks the model rates flowing that
   are dry most summers: each channel's late-summer greenness (`green_p90`: the greenest 10% of the Sentinel-2 NDVI
   pixels within 30 m of the line, the median of three summers; `flowlib.channel_green`), and the record of a USGS gauge
   on the reach's own creek (`gauge_share` and its site, years and distance; `flowlib.gauge_record`: gauges that
   measure a creek, not a canal, with 5+ summers since 2011, for the reaches within 4 km on its model line that drain
   2/3 to 1.5× its area). `02g_greenness.py` (per area, no REGION) downloads the greenness: Sentinel-2 L2A from Earth
   Search (Element 84's STAC API over the AWS open-data copy), no key, NDVI for 15 Aug–30 Sep of 2022–24 per box,
   `data/raw/<area>/<range>/late_summer_ndvi_<year>.tif`, kept once made. Only for areas with the `late_summer_green`
   source (LA and Jackson, about 0.7 and 0.4 GB): in the humid areas every channel is green in late summer and the rule
   changed nothing (measured 2026-11-20). Earth Search's `earthsearch:boa_offset_applied` flag is wrong on some
   scenes, so the step reads the +1000 offset from the pixel values.

Then `06_map.py` (no REGION needed) merges every finished range into the combined map, CSVs and GPX.

`02c_pct.py` (no REGION needed) downloads the **Pacific Crest Trail** from OpenStreetMap: the ways of the PCT section
relations (tagged `ref=PCT`, named like "PCT - California Section D"), 60 km past the study areas on every side so
the trail runs off the map edge. It writes `data/raw/<area>/_shared/pct.gpkg`; `06_map.py` draws it if the file exists.
Re-run it if the official route changes (OSM follows the PCTA route, including road walks).

`02d_trails.py` (no REGION needed, after every range's DEM exists) builds the **trail layer**:
- **Base geometry: OpenStreetMap** paths, bridleways, footways and tracks (fire roads), with name, difficulty
  (`sac_scale`), surface, access and the hiking routes they belong to. OSM was the most complete source in every
  test area (Mt. Wilson, Topanga, Idyllwild, Wheeler Gorge, Trabuco).
- **Enrichment (public domain):** USGS National Digital Trails (USFS, NPS, State Parks and LA County trails in one
  service) gives official name, trail number, agency and allowed uses to OSM ways that follow an official trail
  (within 25 m over 60% of their length), and adds named official trails missing from OSM. The USFS roads layer
  closed to public vehicles marks gated fire roads (e.g. Mt. Lowe Road, 2N50).
- **Dropped:** sidewalks and crossings; flat valley-floor paths (under 100 m relief within 1 km) unless named, on a
  route or official; private or no-access fire roads unless walking is allowed.
- **Flagged:** unnamed OSM paths that follow no official trail or route are "possibly unofficial" (use trails,
  firebreaks): dotted and shown only from zoom 13. The NPS Santa Monica Mountains inventory also marks trails it lists
  as unofficial. Official trails missing from OSM (at least 300 m from any OSM line) are added, dotted, as "agency
  records only; may be faint or abandoned".
- **Mountain bikes**, first rule that applies: no bikes in wilderness or on the PCT, where OSM says no, or where the
  trail is closed; then the agencies' own designations: USFS trails (no when `bicycle_restricted` holds an order's
  dates, yes when `allowed_terra_use` contains 3; many USFS records are "N/A" throughout, which means no information,
  not a ban), State Parks routes (`TRAILDES`), and the NPS Santa Monica Mountains inventory (multi-use vs hikers /
  horses only); then OSM bicycle tags; fire roads outside wilderness; state-park singletrack "probably not"; other
  Forest Service trails "likely" (forest trails are open to bikes unless an order closes them). (The USGS service's
  bike field is empty on Forest Service trails, so it isn't relied on.)
- **Closures:** LA County's Eaton Fire layer closes trails and roads it lists as closed (and roads closed to vehicles
  become bike roads); its closure areas close everything inside them and show on the map. Forest Service closure
  orders are otherwise only published as web pages and PDFs: check the forests' alert pages before a trip.
- **Gaia GPS:** its trail and road data isn't published for reuse (its terms forbid scraping). It is built largely
  from the same open sources used here (OpenStreetMap, USFS roads and trails, the Motor Vehicle Use Map, USGS); the
  Gaia-only parts (user tracks, condition reports, curated hikes) can't be used.
- **Not used:** AllTrails, Gaia GPS, CalTopo, the Strava heatmap, Wikiloc and Hiking Project (their terms forbid it),
  and Ventura County's trail layer (internal use only). OSM data is ODbL: credit it, and share-alike applies if you
  publish the merged trail data itself.

`02e_access.py` (no REGION needed, after `02d_trails.py`) builds **access roads, parking and trailheads**:
- Roads (OSM primary to unclassified and tracks, cycleways, plus unpaved residential / service roads, in mountain
  terrain or on USFS roads). Paved roads closed to cars are often mapped as cycleways: the West Fork Road from
  Highway 39 to Cogswell Dam is one, and was missing until they were added (their own small Overpass query and
  cache). Each road gets one class by what it takes to get up it, from OSM tags (surface, `tracktype`, `smoothness`,
  `4wd_only`, access) and the USFS road layers (maintenance level, open to the public or not):
  **paved** (any car), **graded** dirt (car OK when dry: tracktype 1-2, gravel, USFS level 3+), **high clearance**
  (tracktype 3-4, rough; USFS level 2), **4WD** (4wd_only, tracktype 5, horrible or worse), **bike** (closed to cars
  but open to bikes and on foot: OSM motor_vehicle=no etc., or USFS roads closed to the public; not in wilderness,
  where bikes are banned) and **dirt** (no condition data). Private roads and roads closed to bikes are left out.
  On forest roads covered by the **USFS Motor Vehicle Use Map** (the official record of which vehicles may use each
  road, and when), that designation decides the class (open to passenger vehicles: paved or graded; high-clearance
  only: rough dirt), and the open dates show on hover.
- Parking: public OSM parking in mountain terrain or within 300 m of a trail. Trailheads: OSM `highway=trailhead`,
  USFS trailhead recreation sites and USFS recreation pages marked "Trailhead" (with a link and the Forest Service's
  open / closed status: closed trailheads are greyed out); points within 150 m are merged, official names first.
- The road and trail downloads are cached for a week in `data/raw/<area>/_shared/cache` (closures for a day); `REFRESH=1`
  forces new downloads.

**Map cartography** (`06_map.py` with `map_drainages.js` + `map_style.css`, inlined into the HTML):
- Streams are coloured **by drainage**. Neighbouring drainages never share a hue, and forks are lighter or darker
  shades of their drainage's hue. Line width and lightness follow Strahler order, and order 3+ channels get a white
  casing, so the trunks read first. Faint basin tints and divides (solid = drainage, dashed = fork) carry the
  drainage and fork names; labels that would collide are skipped.
- The legend switch recolours streams by **Drainage**, **Stream order** (monochrome blue) or **Fish score**.
  Clicking a drainage in the legend focuses it (others fade) and lists its forks.
- **3D map** (`stream_map_3d.html`, from `scripts/map3d.html`): MapLibre GL JS with AWS Terrain Tiles (free, no
  key), with the same colours, legend, focus and overlays. Streams and labels drape on the terrain, and creek names
  follow the channels from zoom 12. Right-drag or Ctrl-drag tilts and turns the view; the slider sets terrain height.
  `#lat,lon,zoom,pitch,bearing` links work, and each map links to the other at the current view. The zoom in a link
  is the 2D map's: MapLibre shows the same scale one zoom level lower, so the 3D page shifts it by one.
- The **Pacific Crest Trail** is its own layer, on by default in both maps and drawn above the streams: a thin
  dark dashed line on a soft yellow band, with the PCT section (B–E) on hover. From zoom 11, small labels bend
  along the trail. Each zoom band (11, 12, 13+) has its own smoothed label paths, placed where the real trail
  stays within 5 px of them, so the lettering never kinks on switchbacks or crosses the line.
- **Trails and fire roads** (off until switched on in the layer list): brown dashes on a white edge, revealed by zoom: hiking routes and named
  trails from zoom 10, named fire roads 11, unnamed trails 12, unnamed fire roads and possibly unofficial paths 13.
  Fire roads have longer dashes; closed or private ways are faded; informal or possibly unofficial ones are dotted.
  Named trails get labels that bend along them from zoom 13. Hover for official status, trail number, allowed uses,
  gated roads, difficulty and surface.
- Where a trail or access road runs **beside a creek** (order 2+, within 80 m and roughly parallel), it's drawn shifted
  to the creek's far side so it doesn't cover the stream. `06_map.py` splits those runs out and tags the side and
  distance. Both maps shift them only by what the two line widths need at the current zoom (none once they're apart
  on screen). The 2D map eases the shift in and out at each run's ends. Crossings stay where they are.
- **Access roads**, one layer each (from zoom 10): Paved (off by default; the basemap has them), Graded dirt,
  Rough dirt (high clearance), Very rough (4WD), Closed to cars / open to bikes, Dirt of unknown condition (from
  zoom 11), and Closed: fire closure. Cased
  lines (light centre, dark edge) so they read as roads, not streams; hover for USFS road number, maintenance level,
  surface, track grade, smoothness and seasonal restrictions.
- **Trailheads** (green T, zoom 11+; a small P when there is parking) and **parking** (blue P, zoom 12+). Forest
  Service trailheads link to their page. The computed approach start points used for access times are a separate,
  hidden layer.
- Hover highlights are drawn on a separate layer (2D) or as a per-feature state (3D), so they track the cursor.
- In the 2D map, every vector layer draws on the one canvas the streams use (`map.options.renderer` in
  `map_drainages.js`). Leaflet canvases don't pass mouse events to canvases beneath them. Folium's overlays (the fire
  closure areas) used to get their own full-map canvas above the streams, which took every hover and
  click: the cursor stayed the grab hand and nothing could be clicked. Area overlays now sit under the streams;
  point and line overlays sit on top.
- Every map (2D, 3D, the map of all areas and the single-file map) opens with only streams, drainage outlines and
  names, the area's long trail (PCT, Appalachian Trail, Long Trail), terrain shading and place / road labels
  (3D: terrain height ×1.6 on a light gray basemap). Trails, access roads, trailheads, parking and the fire closure
  areas used to start on in the 2D map; since 2026-11-18 they wait in the layer list like everything else. The
  bike colouring and the trail key come on with the trail layer. In 3D, each overlay's starting
  state is the last entry of its `ov` row in `map3d.html`. Drops, waterfalls, gauges, closures,
  trout waters, trout evidence, springs, trails and trailheads are in the (collapsed) layer list, each named with its map symbol.
- Reaches lying in a lake are drawn as the lake while the Lakes layer is on (it starts on), and as streams again when
  it is switched off, so the rivers run on through the lakes (since 2026-11-20): a reach `05b` reads as lying in a lake
  (below_dam "in:") that lies at least half inside a lake the Lakes layer draws goes whole into a layer of its own
  (`STREAMS_LAKE` in `map3d_data.js`), which `map_drainages.js` (2D), `map3d.html` (3D, the `lk` filter) and
  `14_portable.py` (`!lakes`) show only while Lakes is off; its stretch outside the lake stays with the other streams,
  so a river reaches the shore (the lakes session). The routing ran its paths dead straight across flat water, and their
  names and colours came from the lake's own drainage vote ("Trout Creek" across Palisades Reservoir). About 8,200
  reaches over the 12 maps; about 170 at lake edges, where the two outlines differ, stay with the other streams. The
  map of all areas draws no lakes, so its main rivers keep the whole reaches. Their data stays: scores, ranks,
  profiles, `stream_reaches_ranked.csv`.
- Rivers leaving a lake over a dam start at its shore (since 2026-11-20, late): the routing ends a river in a pit in
  or beside the lake and starts it again in the cell below the dam (`crossbox.py`'s dam and pond links, which
  `draw_through` in `06_map.py` draws on from), so the line below a dam began a median 21-35 m from the shore. A short
  straight line joins it to the nearest point of the shore, or to the end of the river's own line where that stops in
  a pit beside the lake and is nearer; where the river's own line ends inside the lake, a second one joins that end to
  the same point of the shore in the layer shown while Lakes is off. Left out: joins over 150 m, ones that would cross
  another line, ones to a creek coming in by the dam, and where the line below the dam already runs by the shore. 290
  of the 393 cells below a dam on the eight shown maps, 1,048 of 1,436 over all 12 (median 28-57 m). Drawing only.

`07_road_closures.py` (no REGION needed) fetches **current road closures**. Run it, then `06_map.py`, whenever you
want fresh closures on the map; the layer name shows when they were fetched. Sources:
- **Caltrans Lane Closure System** (Districts 6, 7, 8 and 12, live JSON). Only mountain highways are included: SR-1,
  2, 18, 23, 27, 33, 38, 39, 74, 126, 138, 142, 150, 173, 189, 243 and 330, plus full closures of I-5 over the
  Grapevine. Each closure is routed along OSM roads between its begin and end points, and repeat nights of the same
  job are merged. Shown: active now, or starting in the next 7 days.
  "Full closure (one direction)" means every lane in that direction is closed. A closed ramp, connector or rest
  area is listed as "ramp / rest area closed": it doesn't close the highway, so the routing leaves the road in (and
  on I-5 it isn't listed at all).
- **LA County Public Works**, **San Bernardino County Public Works** and **Riverside County TLMA** road-closure
  services (polylines), and **Ventura County PWA** closures (points with from / to cross streets, drawn along the
  named road between them, e.g. Lockwood Valley Road). The county lists sometimes keep closures after their estimated
  reopening date; those are labelled. Orange County's feed is empty and Kern County has none.
- Closures are kept only in mountain terrain (≥150 m of elevation relief within 1 km), which drops urban roadwork.
- **Not included:** Forest Service closure orders (Bridge/Eaton fire areas, seasonal gate closures). They are
  only published as PDFs, so check fs.usda.gov/angeles and fs.usda.gov/sbnf before a trip.
- **Other areas** (feeds that need no account): Grand Teton National Park's road status and Teton County's
  emergency closures (Jackson); Georgia 511 events; the New England Compass work-zone feed (Vermont, with seasonal
  closures such as Lincoln Gap); the Blue Ridge Parkway's closure table and Virginia 511's map files (Lexington).
  Park roads are kept wherever they are, the rest only in mountain terrain. WYDOT's highway conditions,
  Idaho 511 and Connecticut's closures need a registered key, so NE Connecticut has no closure layer, and on the
  Jackson map the state highways (Teton Pass, the Snake River Canyon), Lincoln County (Alpine) and the Idaho side
  (Teton Valley, Palisades) aren't covered.

Drop popups name any full closure within 3 km.

**Access, conditions and context** (run after 05 and 07):
- `08_hike.py` (per REGION): cost-distance approach time from the nearest road a car can reach, on the 10 m DEM.
  Freeways and their ramps don't count as places to start from.
  - **Walking** uses Tobler's hiking function. Trails, tracks and closed roads use the trail grade, capped at 15%.
    Off-trail creek bottoms walk at 45% of that speed and chaparral at 30%; slopes over 45° are near-impassable.
  - **Biking** is used wherever it beats walking: 18 km/h on the flat, slowed by grade (about 10 km/h at 6%), ×0.7 on
    dirt roads and ×0.5 on singletrack. The grade is the road's or trail's own, from the DEM along the line over
    200 m (capped at 25%). A cell's own slope is the hillside's: the West Fork Road climbs 1.4% across a 30% canyon
    wall, and riding it at hillside grade took twice as long.
  - **Bikeable:** every road closed to cars and every fire road. That means today's closure segments, roads cut off
    by closures, OSM roads tagged access=no / motor_vehicle=no, OSM tracks, access roads of class "bike"
    (`02e_access.py`) and all fire roads in the trail layer (`02d_trails.py`). Also every OSM bike path
    (`highway=cycleway`) in the range, which `08_hike.py` downloads itself and keeps for a week (`02e_access.py`
    keeps only those in mountain terrain; the paved West Fork Road to Cogswell Dam is one), and singletrack the
    trail layer marks bike-legal ("yes").
    Other singletrack is walked. Other private roads (ranch roads that neither layer lists) stay out.
  - **Fire roads where bikes may not be allowed are still ridden**, and their bike time counts in the approach.
    A route that rides one for a minute or more gets `bike_check` (why: in a wilderness, where bikes are banned by
    law; posted or designated no bikes; in a fire closure; or tagged closed or private in OpenStreetMap) and
    `bike_check_min` (how long). Popups show "⚠ fire road: double-check bike access".
  - Road pieces stranded behind a closure are not trailheads. Each reach/drop gets
    `approach_min` = `bike_min` + `walk_min` and its trailhead. Reaches also get `approach_med_min`, the typical
    time along the reach, and `bike_med_min`, the minutes of it ridden.
- `09_drive.py`: free-flow drive time and distance from `HOME` in `config.py` (ZIP 90404) to each trailhead.
  It routes over regional OSM highways plus local roads, with today's full closures removed and winding mountain
  roads at ×0.75 speed. There is no traffic model. A road that reaches the network only through local streets
  outside every box (Bautista Road) is joined to it across the gap (up to 3 km, at 25 km/h); those drive times are
  flagged approximate.
- `10_sun.py` (per REGION): hours of direct sun on the water on July 15, from horizons traced in 36 directions
  out to 3 km. Also `northness`, the aspect of the mountainside within 1 km (north-facing = cooler).
  Trees aren't modelled here; `11_context.py` adds the tree canopy.
- `11_context.py`: fire perimeters since 2016 (CAL FIRE's historic perimeters, published once a year; this year's
  fires from the interagency WFIGS year-to-date perimeters; a fire in neither, like the 2026 Bouquet Fire, from the
  outline of its Forest Service BAER burn-severity map), the BAER soil burn severity of each reach's latest fire
  (area-weighted within 30 m), the USGS post-fire debris-flow hazard on channels below burns of the last 4 years,
  USFS tree canopy cover along each reach (NLCD TCC, latest year, so the 2024–25 fires show; 30 m, cached 90 days in
  `data/raw/<area>/<range>/canopy_tcc.tif`), USGS real-time gauges vs. daily percentiles for today's date (from the USGS
  Water Data APIs at `api.waterdata.usgs.gov`, which replace WaterServices: latest discharge from the OGC API,
  percentiles from the Statistics API, still in beta) plus CDEC's Piru Creek gauges (above Pyramid Lake, and the
  dam's release to lower Piru Creek), USFS wilderness and ownership, USFWS/NMFS critical habitat for stream
  species, CDFW Heritage and Wild Trout Waters, trout evidence, springs and seeps (NHD), the August mean air
  temperature along each reach and at each trout record (PRISM 1991–2020 normal, 800 m; the national file is
  downloaded once and clipped to `data/raw/_national/prism_tmean_aug.tif`), and CPAD (California
  Protected Areas Database) holdings with restricted or no public access, flagged on reaches and drops ("⚠ No
  Public Access: ...") and drawn as their own layer.
- **Trout evidence** (`output/la/context/trout_evidence.gpkg`, its own map layer): CDFW Heritage & Wild Trout Program
  surveys (electrofishing / snorkel, 2023–24 so far: trout found or not), CDFW trout stocking in the last 12 months,
  and iNaturalist research-grade rainbow and brown trout sightings with an exact location (obscured ones are skipped).
  A survey or stocking point counts for the creek of the same name within 5 km; a sighting for its reach (within
  150 m) and the same creek within 1.5 km. Lakes are left out of the score (their trout are stocked): stocked lakes,
  and sightings at a lake or within 400 m of a stocked one.
- `scoring.py`: merges these onto reaches/drops and computes the final fish score (used by `06_map.py`).
- `12_profiles.py` (after `06_map.py`): long profiles for every named creek, written to `output/la/profiles_data.js`
  for `profiles.html`.
  - The creek line is the longest connected path through the creek's NHD named flowlines.
  - Elevation is the channel bottom: the lowest hydro-conditioned DEM cell within 20 m, forced to only go down
    downstream.
  - Drops, mapped falls and gauges are snapped on, and per-reach fish score, burn, trout-water and
    critical-habitat values are added as strips along the profile.
  - Drainage and the strips come from the creek's own channel only: DEM reaches named after the creek, or unnamed
    ones up to twice its largest named reach + 1 km² (`OWN_CAP`), and never the cell where a reach joins the next
    stream. A creek's NHD line runs out to the receiving river's centreline, so any channel near the mouth used to
    give the creek the river's drainage and fish score.
  - Stream and drop popups on the map link to the profile; "Show on map" in the viewer opens
    `stream_map.html#lat,lon,zoom`.
  - Drop colors match on the map and the profiles: magenta waterfall-like step, yellow cascade, violet short fall,
    ink for drops at mapped waterfalls. This set passes the all-pairs color-blind check in light and dark mode.

`02b_download_flow.py` and `11_context.py` use the USGS Water Data API. Without a key it allows 1,000 requests an
hour, shared with anything else using it from the same internet connection. A fresh `02b` gauge download takes about
115 requests (runs in the next 30 days fetch only gauges not yet cached), and `11_context.py` under 10. When the API says the hour's
limit is reached, the scripts wait until it resets (up to an hour). For a higher limit, put a free key from
https://api.waterdata.usgs.gov/signup/ in `USGS_API_KEY` (e.g. `export USGS_API_KEY=...` in `~/.zshrc`); the scripts
send it only to `api.waterdata.usgs.gov`.

```bash
for r in san_gabriel santa_monica san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns; do for s in 01_download_dem 02_download_vectors 03_hydrology; do REGION=$r ../.venv/bin/python $s.py; done; done; ../.venv/bin/python 03b_stitch.py; for r in san_gabriel santa_monica san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns; do for s in 04_knickpoints 04b_bigcreek_steps 05_score; do REGION=$r ../.venv/bin/python $s.py; done; done; ../.venv/bin/python 07_road_closures.py
../.venv/bin/python 02b_download_flow.py
for s in 05c_drainages 05b_flow; do for r in san_gabriel santa_monica san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns; do REGION=$r ../.venv/bin/python $s.py; done; done
../.venv/bin/python 02c_pct.py; ../.venv/bin/python 02d_trails.py; ../.venv/bin/python 02e_access.py
for r in san_gabriel santa_monica san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns; do for s in 08_hike 10_sun; do REGION=$r ../.venv/bin/python $s.py; done; done
../.venv/bin/python 09_drive.py; ../.venv/bin/python 11_context.py; ../.venv/bin/python 06_map.py
../.venv/bin/python 12_profiles.py
```

To refresh only the live data (closures, gauges) before a trip: `07_road_closures.py`, then `08_hike.py` per region,
`09_drive.py`, `11_context.py` and `06_map.py` (about 5 minutes).

The order matters. `08_hike.py` reads the trail and access-road layers that `02d_trails.py` and `02e_access.py`
write. The reach and drop keys (`sid`, `did`) are row numbers `05_score.py` hands out, so after re-running it for a
range, re-run that range's `05c`, `05b`, `08`, `10` and `11_context.py` before `06_map.py`, and `05b` of the ranges
whose creeks run on into it (their flows can come from its reaches). `06_map.py` stops if one
of their tables doesn't list the same reaches or drops as the range's `streams_scored.gpkg` /
`waterfall_candidates.gpkg`, and notes any table older than those files.

To add a range, add an entry to the area's `ranges` in `AREAS` in `config.py` (UTM bbox + NHD HU4 codes; keep boxes from overlapping, or
streams get drawn twice) and run the per-range loop for it, then the shared steps. The wilderness layer (fetched by
whichever of `02d_trails.py`, `02e_access.py`, `08_hike.py` and `11_context.py` runs first) and `09_drive.py`'s
major roads re-download when the ranges outgrow them. `08_hike.py` also downloads each range's OSM bike paths, kept
for a week. Run `09_drive.py` after it: it rewrites `trailheads.gpkg`.

## Fish score (0–100, heuristic; `scripts/scoring.py`)
`water × (30% size + 30% thermal + 15% gradient + 25% remoteness) × burn × trout × heat × channel`
- **water:** dry-season flow from the Natural Flows model (`05b_flow.py`): 0.05 + 0.95 × the share of summers since
  2011 the reach kept ≥0.1 cfs through July–October; 0.3 in a reservoir. Reaches the model doesn't cover (about 9%)
  fall back to the NHD class: perennial 1.0, intermittent 0.35, unmapped 0.15, ephemeral 0.05.
  Below a gauged diversion, the gauge's own share replaces the model's only when three things hold: it kept flowing
  in under half of 5+ summers since 2011, the reach is close below the diversion, and no trout are known there.
  Today that is only the San Jacinto River near San Jacinto, which the gauge found flowing in 19% of summers. Trout
  were found below the Santa Ana, Mill, Lytle and Plunge diversions in 2019–2024, so those stay on the model.
  **Creeks the model rates flowing that are dry most summers** (2026-11-20). Against the USGS gauges of all 12 areas,
  31 of LA's 53 gauged creeks that are dry most summers were rated "usually flows" or "year-round", nearly all where
  the model's typical summer low is 0.1–0.45 cfs (25 of 31 gauged creeks there are dry most summers); outside LA only
  Dead Creek in the Champlain lowland. The fix is one-sided, as the owner put it: "id rather rate a dry creek as year
  round than a year round creek as dry". (1) A **bare channel**: model low under 0.45 cfs, no green along the channel
  in late summer (`green_p90` under 0.45 in the median summer and 0.5 in every one, and not 0.2 greener than the slopes
  around, which keeps desert palm oases like Andreas Canyon), NHD intermittent, ephemeral or unmapped, and no trout
  record, dam, tailwater, open water or fire since 2018: water 0.35 ("seasonal"), never lower. Every gauged creek in
  that range that flows most summers has a green channel (0.67–0.86). (2) A **gauge on the creek**: 0.05 + 0.95 × its
  share of summers flowing. It raises a reach anywhere (Piru Creek below Pyramid Dam flows every summer on its releases,
  where the natural-flow model said seasonal), and lowers one only at or below the gauge and where no trout are known
  on the creek it stands for. Measured before installing: none of the 221 gauged creeks that flow most summers is
  lowered, 13 of the 35 dry ones rated flowing are caught, and the summers since 2011 called flowing while the gauge
  was dry fall from 82% to 13%; it changes 636 LA reaches (33 of them up), 69 in Jackson and 13 on Dead Creek, and no
  others. (3) A **tailwater** (see *thermal* below) with no gauge record on the reach: full water, since its dam's
  releases keep it flowing every summer, which the natural-flow model can't see (since 2026-11-21). Piru Creek below
  Pyramid Dam had read mostly dry or seasonal on 28 of its reaches, against the gauge just below the dam, which ran
  in 11 of 11 summers; the gauge above Lake Piru (31% of summers) still sets the reaches it stands for. Popups say
  which rule set the class and why. The
  model and NHD
  often disagree: of NHD's 2,430 "perennial" reaches the model has 619 drying in some or most summers, and 850 NHD
  "ephemeral" reaches flowing through most summers. Popups show the model's typical and drought-year low flow.
  Desert-side canyons with year-round water score high on water alone. The heat gate below takes down only the low
  desert ones (Whitewater, Palm Canyon Wash, Tahquitz). Murray and upper Andreas canyons stay up because it isn't
  certain they're too warm.
- **size:** drainage area, log scale from 1 to 50+ km². The full area (`area_full_km2`): with what flows in from
  neighbouring boxes and from above reservoirs, which each box's own routing misses.
- **thermal:** 50% water temperature, 35% summer shade, 15% north-facing mountainside. Water temperature is the
  reach's estimated July–August daytime water temperature (`watertemp.py`; see *Stream temperature* below): full
  credit at 20 °C or cooler, none at 25 °C or warmer (`WATER_FULL`, `WATER_ZERO` in `scoring.py`). There's no
  penalty for cold water. Where an area's fit has no skill (it can't beat "every creek is the average" by 10 %), every
  reach takes that average, the measured sites' mean (`watertemp.area_mean()`): a cold area stays cold rather than
  unknown. Since its 2026-11-19 expansion that is Jackson (145 sites, mean 13.4 °C, fit 3.37 °C off against a 3.72 °C
  spread), so its reaches keep full credit, as under its earlier fit (which put every reach under 18 °C). A reach with
  no estimate in an area with no measured sites gets half credit. Until 2026-11-18 this part was an elevation
  band (700–2300 m); the estimate replaced it so the same cutoffs work in every study area. Shade combines the
  terrain's shade with the tree canopy along the reach: 1 − (1 − terrain) × (1 − 0.8 × canopy), full credit at 45%.
  **Tailwaters** get the water-temperature part in full whatever the estimate says. These are the rivers below a dam that
  releases cold water from the bottom of its reservoir: the West Fork San Gabriel below Cogswell Dam, down to the
  San Gabriel Reservoir, and Piru Creek below Pyramid Dam, down to Lake Piru (`TAILWATERS` in `scoring.py`). Other
  dams in the ranges are flood-control basins, dry lakes or warm surface-spill lakes, so they aren't on the list.
- **gradient:** 1–8% best.
- **remoteness:** typical bike+hike approach along the reach, 0 → 120+ min, with each minute ridden counted twice
  (`RIDE_REMOTENESS` in `scoring.py`). Most anglers walk in, so a road closed to cars keeps most of them out.
- **burn:** fire since 2016, ×0.4 if ≤2 years ago, ×0.7 if 3–5, ×0.9 if 6–9. Where the Forest Service mapped the
  fire's soil burn severity (BAER), the penalty is scaled by it: high 100%, moderate 75%, low 40%, very low 15%.
  A channel also takes the ash and sediment of the burned slopes above it, so the USGS post-fire debris-flow hazard
  sets a floor (high 100%, moderate 75%, low 40%), and a reach below a recent burn that didn't burn itself is
  penalised from the hazard's fire year.
- **trout:** ×1.2 with evidence of trout (found in the last 10 years by a CDFW survey, CDFW stocking or an iNaturalist
  sighting, with no later survey finding none) or on a CDFW Wild/Heritage Trout Water; ×0.5 when the latest CDFW
  survey found no trout (e.g. Mill, Hemlock and East Twin creeks, Big Santa Anita Canyon in 2023–24).
- **heat (desert gate):** only where the water is near-certainly too warm for trout. When unsure, a possible trout
  stream stays in. ×1 where the August mean air temperature (PRISM 1991–2020 normal, 800 m) is ≤29 °C, falling
  linearly to ×0.2 at 30.5 °C and above. Never applied to a reach with trout evidence (above) or below a dam (its
  releases may run cold). It works off air temperature because no stream-temperature model is good enough here
  (see *Stream temperature* below). The cutoff sits more than 2 °C above the trout records: of ~330 creek records
  (CDFW surveys, stocking, iNaturalist), the hottest site is 26.7 °C (lower Piru Creek, a tailwater), and the next
  are Coldwater Canyon Creek 26.5 °C and Plunge Creek 26.2 °C. That leaves only the low desert canyons and fans below
  the San Jacinto and San Gorgonio escarpments (Whitewater River, Palm Canyon Wash, Tahquitz and the lower Andreas
  and Snow creeks), 29–33 °C, where the water measures hot. In the Water Quality Portal, the Whitewater River at White
  Water read 24–27 °C on April afternoons and 25.7 °C in early June. The Agua Caliente Band's readings in Palm, Andreas, Murray, Tahquitz and West Fork canyons
  were 17–22 °C on March–April mornings, when mountain trout creeks run 5–13 °C. Chino Canyon Creek read 32.7 °C on
  an August afternoon, though at 28.8 °C air it sits below the gate. Upper Murray, Andreas and West Fork Palm
  canyons (27–29 °C) are probably too warm too, but that isn't certain, so they aren't gated.

### Stream temperature: what was tested and why the gate uses air temperature
The models were checked against 83 sites with measured July–August water temperatures in the eight ranges (Water
Quality Portal: USGS, Forest Service, EPA, and the Morongo, Soboba and Agua Caliente tribes). The error is
leave-one-out RMSE of a linear fit, where the site-to-site spread is 5.7–6.0 °C:
- **NorWeST** (USFS, August mean): 5.6 °C. It has only ~54 calibration sites in these ranges, mostly big lowland
  rivers (Santa Ana, Santa Clara, Santa Paula, Sespe, Piru). On the spring-fed upper Santa Ana River and its side
  creeks it predicts 20–23 °C August means where summer readings are 11–16 °C. It also has nothing in the Salton
  Sea basin (HU 1810: the Palm Springs and San Gorgonio Pass canyons, 1,476 of our reaches).
- **EPA StreamCat** (Hill et al. 2013, July–August mean): 4.1 °C. It rates Palm Canyon (23.0 °C) about the same as
  Deep Creek and Piru Creek, which both hold trout.
- **PRISM August air temperature**: 4.0 °C.

Southern California trout also live in warm water. Deep Creek near Hesperia averages 24.8 °C in August (USGS,
2017–26) and has wild trout upstream. SCCWRP's regional study (Tech. Report 1084, 2019) found O. mykiss mostly where
the warmest week averaged under about 22 °C, and none above a 32.5 °C weekly maximum. So the gate only takes down
water hotter than every place trout are recorded. `data/validate_heat.py` (run from `scripts/` after
`11_context.py`) reproduces these numbers and lists the readings inside the gated zone.

**The water-temperature estimate (thermal term).** `watertemp.py` fits the measured sites' July–August daytime
medians on PRISM August air temperature and elevation, per study area, and stores the fit in
`data/raw/<area>/_shared/water_temp_fit.json` (run `../.venv/bin/python watertemp.py` to refit; `06_map.py` only
reads it). Since 2026-11-20 each site is weighted by how well its median is known, 1 / (τ² + σ²/n): σ is the spread
of single readings around their site's median (1.3-3.9 °C by area), n the site's number of readings, τ² what the
predictors miss on a well-measured site; a single grab sample counts for less than a logger's summer. The skill test
and the area mean are weighted the same way. Jackson's fit has skill since (0.887 of the spread against 0.906), so
its reaches carry an estimate; elsewhere scores moved by 2 points at most. In the LA ranges: water = 10.5 + 0.56 × August air (°C) − 4.17 × elevation (km), on 65 sites, with a
leave-one-out RMSE of 3.2 °C (air alone 3.45, elevation alone 3.3). Three sites with medians over 30 °C are left out
(two on Warm Creek in San Bernardino, which is fed by hot springs, and one August afternoon reading in Chino
Canyon). The estimate is held at the edge of the fitted sites' range (air 17.2–28.7 °C, elevation 142–2,120 m), and
it runs narrower than reality: 11–26 °C over all reaches. Air and elevation each miss at low elevation in opposite
ways: the Santa Clara River near Piru measured 26.5 °C under cool coastal air, and Santa Paula Creek 18.9 °C at
180 m. On the 1,566 reaches with trout evidence the new term gives the same mean credit as the elevation band did
(0.91). Against the elevation band, 95% of reaches moved by 3 points or less and 33 by 10 or more; 189 of the top
200 stayed. Stream popups show the estimate ("summer water about 21 °C").

- **channel:** ×0.2 on a built conveyance, by name: aqueduct, canal, flood-control channel, diversion, ditch, flume
  and the like, with no natural word in the name (creek, river, wash, brook, branch, fork, run) and no trout record.
  In LA that is the three aqueducts and the named flood channels. A channel with a natural name stays as it is,
  concrete or not (the Los Angeles River, Tujunga Wash).

The ranked table also has `area_rank_pct`, the share of the area's reaches that score lower, and stream popups show
it ("ahead of 93% of reaches here"). The score was tuned on LA's mostly dry channels and runs high in wet country,
so the standing within an area is the number to compare.

Critical habitat, wilderness and non-Forest-Service land are shown as flags, not scored. Critical habitat is USFWS/NMFS
*designated* habitat clipped to the study areas. It is not a closure map: Forest Service closures for arroyo toad and
other species are set by forest orders, usually cover less ground, and have to be checked on the forest's site.

## Lakes (all 12 areas; the first six 2026-11-19, the other six 2026-11-20)
Lakes and ponds as places to go: outline, water level, depth, fish, access and land. Built for all 12 areas, each from
its own smallest size (`BUILT` in `05d_lakes.py`): Jackson 0.5 ha, NE Connecticut 1 ha, central Vermont 1 ha,
Lexington 0.5 ha, North Georgia 2 ha (below that it has 1,835 farm ponds), LA 1 ha, SE Pennsylvania 1 ha (450 suburban
and farm ponds of 0.5-2 ha, few named), the Smokies 0.5 ha (mountains with few ponds) and the four Adirondack maps 1 ha
(natural ponds; this keeps the 2.5-acre brook trout ponds). A lake a state lists is kept at any size.
- `05d_lakes.py` (AREA only, after `05c_drainages.py`) writes `data/derived/<area>/_shared/lakes.gpkg`, with
  `lakelidar.py` (1 m lidar), `lakedata.py` (measured depths and gill-net surveys typed in from their reports, and
  the trout family's names), `lakesources.py` (EPA National Lakes Assessment soundings, every area; each state's lake
  access, rules and designations, and its own list of trout lakes: NCWRC's impoundments and PFBC's stocked lakes as
  outlines, New York DEC's stocking list and lake fishing list from data.ny.gov). New York's stocking and lake-list
  records are written beside the lakes (`lake_records.gpkg`) and read by `maplakes.py` with the trout evidence.
- `lake_bathymetry.py` (after it) reads measured depth surveys: contours into `lake_depth.gpkg`, and each surveyed
  lake's maximum and mean depth into `lakes.gpkg`. Running it twice gives the same result.
- `08_hike.py` reads the lakes: impassable for walking off trails (before, a flat lake surface read as easy ground
  and routes crossed lakes on foot), a point in a lake counts as reached at the nearest shore of its own lake that can be
  reached (not at its quickest shore anywhere: a creek's mouth 20 km up an arm of Fontana Lake had read 2 min away; a
  shore reached across the water, an island's, is no target), and each lake gets an approach (`hike_lakes.csv` per
  range). Every route also has `route_km`, its length.
- `06_map.py` draws them through `maplakes.py`: a "Lakes" layer and a "Lake depth contours" layer, both off at start,
  in the 2D, 3D and one-file maps (a click on a contour opens its lake); `output/<area>/lakes.csv` and `lakes.gpx`.
  Fill: blue where trout are stocked or recorded (Jackson: where Game & Fish lists game fish), pale blue where there
  is no record (Jackson: grey where the agency lists none); a dashed edge where the lidar found little level water.
- `run_mid.sh` runs `05d_lakes.py` then `lake_bathymetry.py` after the drainages and flow (a failed download keeps the
  last `lakes.gpkg`).

| Area | Lakes | Lidar shorelines | Measured depth | Depth contours | Trout stocked or recorded | Walk-in times changed |
|---|---|---|---|---|---|---|
| Jackson | 543 | 238 | 58 | none public | Game & Fish list: 56 with game fish | 272 of 6,419 reaches (pilot) |
| NE Connecticut | 706 | 632 | 44 | 1,098 lines at 35 lakes (CT DEEP) | 24 | 482 reaches quicker, none 5+ min slower |
| central Vermont | 411 | 292 | 17 | 516 lines at 14 lakes (VT ANR) | 23 | 274 reaches quicker, none 5+ min slower |
| Lexington | 182 | 111 | 1 | none public | 2 | 50 quicker; 2 slower by 5 and 9 min, beside a pond |
| North Georgia | 551 | 490 | 9 | none public | 13 (Lake Burton, Winfield Scott, Black Rock, Nancy Town...) | 782 reaches quicker (median 7 min); 4 reaches and 3 drops 5+ min slower, at most 24 |
| LA | 389 | 86 | 6 | 39 lines at Little Rock Reservoir (USGS) | 18 (Big Bear, Jenks, Gregory, Hansen Dam, Yucaipa...) | 462 reaches quicker (median 12 min); 22 reaches and 29 drops 5+ min slower, up to 3 h, all beside Castaic, Pyramid, Morris, San Gabriel, Big Tujunga or Cogswell: their old routes walked on the water |
| SE Pennsylvania | 262 | 200 | 6 | 56 lines at 4 lakes (DCNR / PA Geological Survey, USGS) | 3 (Scotts Run Lake, Loch Alsh Reservoir, Marsh Creek) | 45 reaches quicker (median 2 min); 2 reaches 5+ min slower, at most 8 |
| the Smokies | 180 | 83 | 1 | none public | 10 (Cheoah, Calderwood, Chilhowee, Tellico, Queens Creek Lake, Max Patch Pond...) | 183 reaches quicker (median 2 min); 438 reaches and 47 drops 5+ min slower, up to 10 h: Fontana's north-shore creeks and the reaches inside Fontana, Cheoah, Calderwood and Chilhowee, whose old routes walked on the water |
| Adirondacks: High Peaks | 768 | 548 | 8 | none public | 114 (DEC's stocking and lake lists: Lake Placid, the Saranacs, Taylor Pond...) | 1,068 reaches quicker (median 7 min); 406 reaches 5+ min slower, at most 119 |
| Adirondacks: northwest | 1,313 | 980 | 7 | none public | 95 (Cranberry Lake, Raquette Lake, Stillwater Reservoir...) | 683 quicker (median 4 min); 953 reaches 5+ min slower, at most 307 |
| Adirondacks: southwest | 953 | 701 | 4 | none public | 118 (Fourth Lake, Piseco Lake, Lake Pleasant...) | 409 quicker (median 3 min); 429 reaches 5+ min slower, at most 100 |
| Adirondacks: southeast | 1,137 | 808 | 8 | none public | 116 (Lake George, Indian Lake, Schroon Lake, Brant Lake...) | 945 quicker (median 5 min); 324 reaches 5+ min slower, at most 171 |

The rule fixes of 2026-11-20 (the outline rows and the walking bullet above) changed the first six areas' walk-in
times as well: a reach lying in a lake is reached at its nearest shore, not the lake's quickest, so 35 (Lexington) to
405 (North Georgia) reaches got 5+ min slower, the most where a river is mapped through a big lake (the Snake through
Jackson Lake up to 11.5 h, the San Gabriel through its reservoir 5 h). Fish scores moved by 5+ points at 0-154 reaches
per area (Jackson 154, LA 60), by at most 10.

Each attribute comes from the best source there is for it, and the sources were checked against each other:

| Attribute | Source | Checked |
|---|---|---|
| Outline | 1 m lidar (USGS 3DEP), the newest survey over each lake, read in place from USGS's cloud-optimized tiles (tiles in another UTM zone are reprojected). Lidar DEMs are hydro-flattened, so the cells at the lake's one elevation are its shoreline on the survey date. A lake flattened at more than one level (flown on two days, or pools split by a causeway) takes the flat patches at the other levels lying mostly inside its outline; flattened water is one patch of 200 m² or more. NHD High Resolution where the lidar didn't flatten the lake, for reservoirs and lakes drawn down that day, where the water at the lake's level runs on past it (off the window, or into NHD river area), and over 600 ha. Touching NHD lakes trim each other's lidar water. A lake mostly outside the map with under the area's smallest size inside is left out; one reaching far past the map is stored to 2 km past its boxes (its size and facts the whole lake's) | Jackson: median overlap with NHD 0.78; on imagery the lidar follows the water (Lower Slide Lake's vegetated inlet delta, Table Mountain Lake's bare shore band are in NHD's outline). North Georgia: with one level only, Tugaloo Lake was 100 ha of its 203 (now 195.5), Seed Lake 29 of 77 (now 73); Toccoa Reservoir is two pools either side of a causeway. Adirondacks: Figure Eight Pond had flooded along its flow to 5.6 times its size, Upper St. Regis into Spitfire Lake. A size rule (lidar over 1.5 times NHD: keep NHD) was tried and dropped: in Connecticut and Jackson the bigger lidar outline is usually the right one |
| Water level, elevation | The lidar's flattened level; the median of a level but unflattened surface (70%+ within 15 cm); else the 10 m DEM. A lake the lidar caught low shows its normal level | NHD's stage elevations are in feet at some lakes and metres at others (read per lake against the DEM) and can be metres off: Table Mountain Lake 12 m, 50 North Georgia lakes 2-28 m |
| Survey date | Each lidar survey's span: one can fly for a year (VA_West_Chesapeake_B1_2017: 2017-04 to 2018-05) | |
| Missing lakes | OpenStreetMap water of the area's smallest size or more that no NHD lake covers, kept where the lidar shows level water; NHD's dropped treatment and storage ponds count as covering, and water NHD maps as river, canal or estuary isn't a missing lake unless OpenStreetMap tags it a reservoir. An NHD lake OpenStreetMap names a wastewater works is left out. A state's listed lake NHD has no lake for keeps the agency's outline (Cheoah Reservoir, which NHD draws as river) | se_pa had taken in 7 tidal creeks by the Delaware, flattened at sea level, and 4 concrete or treatment basins; North Georgia 5 lined basins and a river channel; Connecticut 3 aerated lagoons. Lakes added from OpenStreetMap before that rule (2026-11-19): Jackson 61, Connecticut 124, Vermont 13, Lexington 11, North Georgia 52, LA 7 |
| Name | GNIS (NHD); Wyoming Game & Fish's where it names a group or adds a qualifier; else OpenStreetMap's, where one named outline and the lake cover half of each other, no lake within 2 km has the name, and it doesn't end in "Dam" (166 lakes); Connecticut's survey name for one more | Virginia's public-fishing-lake layer isn't used for names: it calls the 189-acre Mill Creek Reservoir "Mill Reservoir" (DWR's own page and OpenStreetMap: Mill Creek Reservoir) |
| Fish | Jackson: Wyoming Game & Fish's lake fishing guide (game fish or "None", lake class, depths, private shore). Elsewhere: the state's stocking and survey records already gathered for the streams (`context/trout_evidence.gpkg`: CT DEEP stocking and electrofishing, Vermont's trout stocking list, Virginia's trout stocking plan, Georgia DNR stocking and surveys, CDFW's stocking schedule, PFBC's stocked lakes, NCWRC's mountain trout impoundments, TWRA's reservoir stocking): a record naming the lake within 2 km (word order aside: "Gregory Lake" is Lake Gregory), or a lake record within 150 m of the shore. A stream's stocking or survey point beside a pond stays the stream's (CT DEEP's stream surveys sit at the inlets and outlets of 44 ponds). A lake record inside an unnamed lake names it (Yucaipa Lake). New York: DEC's stocking since 2011 (data.ny.gov; names by town, matched to NHD lakes by name in the town, else the only one of the name in the county) and DEC's lake fishing list (its species). SE Pennsylvania: PFBC's 2021 trap-net survey of Scotts Run Lake. Everywhere: GBIF records at the lake (state surveys, iNaturalist, USGS NAS, museums), shown with source and year | Species recorded since 2000 but not on Game & Fish's list are shown beside it (brown trout in Leigh Lake) |
| Depth | Measured values only, best first: published sonar surveys and state bathymetry (CT DEEP contours, a lower bound; Vermont ANR sonar soundings, gridded per lake), EPA National Lakes Assessment sonar (the index site: a natural lake's deepest spot, a reservoir's lower bound), fisheries transducer surveys, an agency's listed depth. SE Pennsylvania: DCNR / PA Geological Survey depth maps (Marsh Creek, Hopewell and Scotts Run lakes: the map's deepest point, its depth bands drawn as contours) and USGS's sonar survey of Chambers Lake | Vermont's grid against published figures: Lake Dunmore 106 ft deep and 29 ft mean (published 105 and 28). Disagreements over 20% (and 2 m) are shown |
| Inlets, outlets | NHD HR flowlines that start or end at the shore; an unnamed outlet is followed down to the first named water | Many small lakes have no mapped stream: "no mapped inlet or outlet (NHD)" |
| Access, rules | Connecticut: CT DEEP boat launches, fisheries-management lake designations. Vermont: fishing access areas, special regulations, restricted waters. Virginia: DWR public fishing lakes and their boat and motor rules. SE Pennsylvania: PFBC lake access points (ramps, piers, motor rules; with credit to PFBC, as its licence asks), DCNR state park launches, PFBC lake special regulations and boating rules. The Smokies: NCWRC boating access and public fishing areas, TWRA access sites, TVA ramps, NCWRC impoundment classes, the Calderwood reciprocal licence. The Adirondacks: DEC's lake fishing list (launch type, hike-in, bait and motor rules, contour map links) and DEC's launches and fishing access sites, all from data.ny.gov | DEC's own ArcGIS layers say "secondary distribution of the data is not allowed", so they aren't used for lakes |
| Land | PAD-US (the public-access service). Where PAD-US leaves the water out (Jackson Lake, with ~300 m of shore), the unit most of the shore lies in. Access is flagged only where closed, or restricted outside federal land | |
| Level water | Lakes of 2 acres or more whose lidar surface isn't level (under half the outline within 15 cm), with the 10 m DEM agreeing: "largely dry, marsh or overgrown then". A dammed lake whose bed lies over a metre under its own lidar shore, or under a neighbour's normal level where its own shore lies at that level: "caught drained / drawn down". A flattened dammed lake over 2 m under NHD's level, with its normal shore over 1 m clear of the water: "below its normal level when the lidar was flown" | On imagery (Esri World Imagery) the flagged lakes in Lexington, North Georgia and LA are forest, field, marsh, bare or low basins. Without the shore test, NHD's level made 50 full North Georgia lakes "drawn down" |

**Bathymetry.** Connecticut DEEP's lake contours (24 surveys of 1959-2002 by depth finder, GPS or lead line; feet;
the deepest contour is a lower bound) and Vermont ANR's sonar soundings (2.4 million points in 66 lakes, compiled
2020; depth below the survey day's level) are read by `lake_bathymetry.py`. No lake in the Jackson boxes has a depth
survey that can be downloaded (checked 2026-11-19): Jenny Lake, Jackson Lake and Palisades Reservoir are surveyed
but published only as figures or held by their authors. LA: USGS's multibeam survey of Little Rock Reservoir (8-9 Feb 2022, a 1 m grid, doi:10.5066/P9BQW35E) gives 16 contour lines, 76 ft deep and 38 ft mean below the lidar's water level (the spillway crest). Its file says ft NAVD88, but its elevations sit 106.4 ft under the 3DEP lidar on land (the geoid separation here), so they are raised by that much; the deepest bed then comes to USGS's own stage-storage zero (3,197.5 against 3,199.5 ft). Lake Arrowhead's 2008 Reclamation sonar survey (a report: area-capacity table) gives 152 ft deep, 61 ft mean below full pool, typed in; EPA's 2007 sounding, 153 ft, agrees. California DWR's multibeam surveys of Castaic, Pyramid and Silverwood are not public. North Georgia: USACE's Lake Lanier cross-section surveys (1955-90) are sparse lines and carry a CUI marking, so they are not used; TVA has published one drawdown waterline of Chatuge; nothing for Georgia Power's or the Forest Service's lakes (Georgia DNR's contour layer covers south Georgia only). Lexington: Virginia DWR's map of Lake Robertson (5 ft contours, deepest 45 ft) is a picture, so its depth is typed in as a lower bound. Checked 2026-11-20. Modelled depths (GLOBathy, HydroLAKES) are
never used. SE Pennsylvania (checked 2026-11-20): DCNR's state park lake depth bands from the PA Geological Survey's water-depth
maps (Marsh Creek Lake, surveyed January 2005 by USGS and the Survey, 5 ft bands, deepest point 78.5 ft; Hopewell and
Scotts Run lakes, April 2017, 2 ft bands, 20 and 22 ft), drawn as contours with each map's deepest point typed in; and
USGS's sonar survey of Chambers Lake (Gyves 2015, SIM 3346: 150,779 soundings by acoustic profiler with RTK GPS,
September 2014; 47 ft deep, 12 ft mean below normal pool, as USGS's own volume table gives; its grid reads within 0.9 ft
of the 3DEP lidar along the lidar's shoreline). The Adirondacks: DEC's contour maps are scanned images without a date
or datum (linked in the popups where DEC's lake list gives them); Lake George's multibeam isn't public; NOAA's 2018
multibeam of Lake Champlain (198 MB) isn't read; the depths in the HuntFishNY layer and the Adirondack Lakes Survey's
pond pages have no stated licence (the survey's site forbids automated access). The Smokies: no published survey of
Fontana, Santeetlah, Nantahala or the Tapoco lakes; North Carolina's water-quality profiles give only lower bounds
(Fontana at least 80 m), and Duke's relicensing figures come from design drawings.

**Walking.** Making lakes impassable mostly makes routes quicker: a reach mapped through a lake now counts as reached
at the shore. Few got slower, and only where the quickest route had crossed a lake on foot (Jackson: Leigh Creek's
canyon by Leigh Lake, up to 37 min). Summer routes in Jackson, without road closures, run within about 10% of the Park
Service's trail distances (Taggart Lake 1.3 mi against 1.5, Amphitheater Lake 4.5 against 4.9), a little short
because a 10 m grid cuts switchbacks. Times are a fit hiker's without stops (Tobler); boats aren't modelled. A
point in a lake is reached at the nearest reachable shore of its own lake (2026-11-20; before, at the lake's quickest
shore, which on Fontana Lake made a creek's drowned mouth 20 km up an arm 2 min from the road). So where a river is
mapped through a big lake its reaches take the time to the nearest shore on foot: the Snake through Jackson Lake up
to 11.5 h, the Little Tennessee below Calderwood Dam about 2 h (it read 6-10 min, across Chilhowee Lake's water). In
the Adirondacks, where many approaches are by canoe, routes that crossed lakes on foot now go round them: 324-953
reaches per map 5+ min slower, and their remoteness raises fish scores (5+ points at 22-214 reaches per map).

## Validation (mapped falls matched by a detected drop within 200 m)
All 12 areas on 2026-11-20, from `data/validate.py` (run from `scripts/` with `AREA=<area>`, one area at a time).
Mapped falls are the known falls that OpenStreetMap or the NHD lists, rapids and swimming holes left out:

| | Pass 1 only | Pass 1 + big-creek pass |
|---|---|---|
| Falls on creeks ≥10 km² | 108 / 270 | 192 / 270 |
| Falls on smaller drainages | 294 / 559 | 294 / 559 |
| **All** | **402 / 829** | **486 / 829** |
| Every precisely placed known fall, any source | 693 / 1,600 | 839 / 1,600 |

- By area (both passes): LA 127 / 212, Jackson 12 / 21, North Georgia 110 / 193, Central Vermont 20 / 30,
  NE Connecticut 4 / 23, Lexington 15 / 21, SE Pennsylvania 0 / 11, the Smokies 97 / 156, and the Adirondacks' High
  Peaks 41 / 53, Northwest 18 / 33, Southwest 6 / 10 and Southeast 36 / 66.
- SE Pennsylvania and NE Connecticut are the weak spots. Their falls are a few metres high in gentle terrain, where the
  detectors find almost no drops: SE Pennsylvania's two boxes have 36 and 46 in all, none within 450 m of a mapped fall.
  The known-falls layer still shows those falls.
- LA by range (both passes): San Jacinto 21 / 28, San Bernardino 13 / 15, Santa Monica 14 / 21, San Gabriel 43 / 69,
  Sespe 20 / 32, Santa Ana 16 / 46, Piru 0 / 1. In the 2026-11-18 run, 25 of the Santa Anas' 46 mapped falls sat on
  drainages under 1 km², below pass 1's floor. The thresholds were tuned on the San Gabriel, Santa Monica and San
  Bernardino ranges (now 70 of their 105).
- The CDFW fish-passage barriers that no other source lists are left out of the table: they are mostly cascades,
  bedrock chutes and boulder jams with no drop a 10 m DEM can show (51 of 172 have a detected drop within 200 m).
- Before 2026-11-20 the check counted no falls at all: since 02f_known_falls.py (2026-11-19) a fall's `src` lists all
  its sources' labels ("OpenStreetMap · USGS GNIS"), and the check still looked for the old single values "OSM"/"NHD".

- The big-creek pass recovers Aztec and Hesperia Falls (Deep Creek) and Royal Falls (Arroyo Seco). It also recovers 4
  unnamed mapped falls that weren't looked at while tuning the thresholds.
- Frustration and Middleman Falls are not on Deep Creek. They sit on tiny side tributaries (<0.5 km²), below
  pass 1's 1 km² floor. Mayberg (flat lowland) and Sycamore (2.9 km²) are also still missed.
- Pass-2 hits are only as good as a 10 m DEM. A 3–5 m "excess drop" can also be a log jam, boulder field,
  bridge or DEM seam, and `pool_depth_m` is usually 0 because lidar returns the water surface, not the pool bottom.
  Treat them as places to check on imagery.
- Upper Deep Creek near Lake Arrowhead (≈1,770–1,830 m, <250 m from roads) is likely culverts or development. The
  better Deep Creek candidates sit below ~1,550 m.

## Regional notes
- **San Gabriels**: the best remote trout water is Fish Fork, Iron Fork, Bear Creek, the West Fork, Prairie Fork and Little Rock Creek.
- **San Bernardinos**: the best remote trout water is Deep Creek, Bear Creek, Holcomb Creek, the upper Santa Ana River and Little Bear Creek.
- **Santa Monicas**: NHD maps almost nothing as perennial, so fish scores are low everywhere. Malibu Creek and Topanga hold
  endangered southern steelhead, and fishing for them is illegal. Treat this range as waterfall / swimming-hole scouting, not trout water.

## Caveats
- Drop height is the step over ~30–300 m of channel, not the free-fall height. Treat candidates as places to check on
  satellite imagery, not confirmed falls.
- The NHD perennial/intermittent label is coarse, and flow changes a lot after drought and fire (Bobcat, Eaton, El Dorado, Line).
- Check current closures (Angeles NF, San Bernardino NF), CDFW Wild Trout / catch-and-release regulations
  (Deep Creek, Bear Creek), and endangered-species closures (arroyo toad, Santa Ana sucker, steelhead) before going.
- Some "dam / weir" flags come from OSM check dams. Some "DEM artifact" flags are still real falls: one under a road
  bridge, or a slot gorge where the fill behind the lip is most of the drop.
- The approach model assumes closed and gated roads may be walked and biked, and it rides every fire road, even in
  wilderness or where bikes are posted out. Those routes are flagged "double-check bike access". Many long-term
  closures allow walking and biking, but fire and storm closure orders can ban all entry. Hike times are model
  estimates; the canyon-bottom and chaparral speeds are guesses, so expect real off-trail travel to vary a lot.
- Drive times have no traffic. Add 30–60+ min for LA weekday or weekend-morning traffic.
- `non_fs_land` comes from the USFS basic-ownership layer, which only separates Forest Service from everything else.
  It can be private, county or other public land, so check the parcel before crossing it.
