# LA Mountains Stream & Waterfall Analysis

DEM-based stream analysis of the mountains around LA, used to find remote fishable water and in-stream drops
(waterfalls / plunge pools). It covers eight ranges, defined in `scripts/config.py`. The boxes
meet edge to edge without overlapping, so a creek that crosses an edge is split between two ranges there:

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

## Outputs (`output/`)
| File | What |
|---|---|
| `stream_map.html` | Combined interactive map. Keep it next to the region folders, which hold the hillshade PNGs |
| `stream_map_3d.html` | The same map in 3D (tilt, rotate, real terrain). Keep it next to `map3d_data.js`. Needs internet for MapLibre and the terrain tiles |
| `stream_reaches_ranked.csv` | Every DEM stream link (≥1 km² drainage), all ranges, ranked by fish score |
| `waterfall_candidates.csv` | All detected drops with height, run, slope above/below, plunge-pool coordinates |
| `waterfall_candidates.gpx` | Waterfall-like steps, cascades and their pools. Import into Gaia, CalTopo or onX |
| `road_closures.csv` / `.gpkg` | Current closures on mountain roads (Caltrans, LA County, SB County), routed along the roads |
| `gated_roads.gpkg` | OSM roads tagged closed to public vehicles (locked fire roads, gated forest roads) |
| `profiles.html` | Creek profile viewer: elevation vs. distance for 241 named creeks, with drops, falls, gauges and fish score / burn / trout-water strips. Keep it next to `profiles_data.js` and the map |
| `context/` | Fire perimeters, stream gauges (USGS + CDEC, live), wilderness, non-Forest-Service land, critical habitat, Wild Trout Waters, trout evidence, springs |
| `<region>/` | The same per range, plus `streams_scored.gpkg` / `waterfall_candidates.gpkg` for QGIS |

## Pipeline (`scripts/`, run from `scripts/` with `../.venv/bin/python`)
Steps 1–5 run once per range, with `REGION=<key>` set (default `san_gabriel`):
1. `01_download_dem.py`: 10 m USGS 3DEP DEM, UTM 11N
2. `02_download_vectors.py`: NHD flowlines/points from USGS bulk GeoPackages (cached in `data/raw/_shared`),
   plus OSM roads/trails/waterfalls/dams
3. `03_hydrology.py`: fill pits/depressions → D8 flow direction → flow accumulation → streams (≥0.25 km²) → Strahler order
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
5. `05_score.py`: attributes, fish score, per-range exports, hillshade. Each link is measured on its own cells:
   drainage area and gradient at its second-to-last vertex (its last vertex is the confluence cell, which would give
   a side creek the trunk's area), Strahler order and elevation at its middle vertex. NHD name and flow class come
   from the nearest NHD lines at three points along the link, each kept when two agree on the name (or the class;
   NHD splits a creek into many short segments). NHD has no name on many lines (e.g. San Antonio Creek below
   Mt. Baldy): those links take the name of OpenStreetMap's named rivers and streams the same way (cached a week in
   `data/raw/<range>/osm_waterways.gpkg`). Links mostly on sea-level
   cells (fake channels across the ocean) are dropped. Known falls are OSM waterfalls, NHD falls and the CDFW
   Passage Assessment Database's natural barriers (falls, cascades and bedrock chutes noted in the field, often with a
   height and plunge-pool depth; records saying the barrier is gone are skipped).
6. `05c_drainages.py`: drainage basins. Every DEM cell is traced down the D8 flow directions to where it leaves the
   study area or ends in a sink (dams). Basins ≥25 km² are named drainages, named after their natural trunk creek
   (canals and aqueducts are skipped; a few NHD gaps are fixed by hand in `NAME_FIX` / `FORK_FIX`). Drainages
   ≥120 km² are split into forks: tributaries ≥35 km² that join the trunk. Everything smaller is grouped as
   "Minor front-range drainages". Writes `drainages.gpkg` (fork polygons) and `stream_drainage.csv`
   (sid → drainage, fork, and Strahler order taken on the channel cell itself).
   - **Across box edges** (`crossbox.py`): each range's hydrology sees only its own box, so a creek crossing in from
     the next box would start again with no drainage area (the Santa Clara River entered the Piru & Castaic box with
     none, so Piru Creek won the trunk and the river's own valley was labelled "Castaic Creek"). Every basin that
     drains off an edge two boxes share is followed into the neighbour, down its flow directions to where the creek
     heads away from the edge, and its area (plus whatever flowed into it from a third box) is added along the creek
     before trunks and forks are picked. Where the neighbour's grid ends the creek in a pit on the edge (a road fill
     just inside: Bouquet Canyon entering the Piru box), the trace restarts from the lowest nearby cell that drains
     away from the edge. The inflow table is cached in `data/derived/_shared/inflows.json` until a `flowdir.tif`,
     the reservoir list or the NHDPlus network changes.
   - **Past dams**: pysheds can't route water across a big flat lake surface, so every large reservoir ends its D8
     paths in pits and the creek below the dam started again near nothing. `crossbox.py` links each reservoir's dead
     ends to the cell below its dam where the water goes on, found by walking down the NHDPlus flowlines leaving the
     lake (Morris 533 km², Pyramid 514, Castaic Lagoon 412, Big Tujunga 212, Littlerock 165, Lake Hemet 143, Big Bear
     137, Matilija 132). Lakes with no outflow (Baldwin Lake) and dead ends away from lakes (desert fans, the sea)
     stay closed. Drainages still end at dams; only areas use this.
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
   old estimate stays, so possible trout water isn't lowered on uncertain evidence. Reaches off the model network take
   the unit-area flow of the first modelled segment downstream ("scaled"). Reaches in or below a reservoir are flagged,
   since releases set their flow. So are reaches below the seven diversions where a USGS gauge on the creek below shows
   it often dry (`DIVERSIONS` in `flowlib.py`): the Santa Ana River No. 1 dam, two Mill Creek intakes, and the Lytle,
   Plunge, City Creek and San Jacinto River diversions. The model can't see water leave in a canal. Their popups
   quote the gauge's share of summers flowing. Writes `flow_streams.csv` / `flow_drops.csv`: typical and drought-year low flow,
   the share of summers since 2011 it kept ≥0.1 cfs, and a class (year-round, usually flows, seasonal, mostly dry,
   reservoir, no data). `02b_download_flow.py` (no REGION needed) also fetches the daily records of every USGS stream
   gauge with 5+ years of data, for `data/validate_flow.py`, from the USGS Water Data API (`api.waterdata.usgs.gov`,
   which replaces WaterServices); it re-downloads its NHDPlus V2 and reservoir caches when ranges are added.

Then `06_map.py` (no REGION needed) merges every finished range into the combined map, CSVs and GPX.

`02c_pct.py` (no REGION needed) downloads the **Pacific Crest Trail** from OpenStreetMap: the ways of the PCT section
relations (tagged `ref=PCT`, named like "PCT - California Section D"), 60 km past the study areas on every side so
the trail runs off the map edge. It writes `data/raw/_shared/pct.gpkg`; `06_map.py` draws it if the file exists.
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
- The road and trail downloads are cached for a week in `data/raw/_shared/cache` (closures for a day); `REFRESH=1`
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
  `#lat,lon,zoom,pitch,bearing` links work, and each map links to the other at the current view.
- The **Pacific Crest Trail** is its own layer, on by default in both maps and drawn above the streams: a thin
  dark dashed line on a soft yellow band, with the PCT section (B–E) on hover. From zoom 11, small labels bend
  along the trail. Each zoom band (11, 12, 13+) has its own smoothed label paths, placed where the real trail
  stays within 5 px of them, so the lettering never kinks on switchbacks or crosses the line.
- **Trails and fire roads** (on by default in 2D, off in 3D): brown dashes on a white edge, revealed by zoom: hiking routes and named
  trails from zoom 10, named fire roads 11, unnamed trails 12, unnamed fire roads and possibly unofficial paths 13.
  Fire roads have longer dashes; closed or private ways are faded; informal or possibly unofficial ones are dotted.
  Named trails get labels that bend along them from zoom 13. Hover for official status, trail number, allowed uses,
  gated roads, difficulty and surface.
- Where a trail or access road runs **beside a creek** (order 2+, within 80 m and roughly parallel), it's drawn shifted
  to the creek's far side so it doesn't cover the stream. `06_map.py` splits those runs out and tags the side and
  distance. Both maps shift them only by what the two line widths need at the current zoom (none once they're apart
  on screen). The 2D map eases the shift in and out at each run's ends. Crossings stay where they are.
- **Access roads**, one layer each (from zoom 10): Paved (off by default; the basemap has them), Graded dirt,
  Rough dirt (high clearance), Very rough (4WD), Closed to cars / open to bikes, Dirt of unknown condition. Cased
  lines (light centre, dark edge) so they read as roads, not streams; hover for USFS road number, maintenance level,
  surface, track grade, smoothness and seasonal restrictions.
- **Trailheads** (green T, zoom 11+; a small P when there is parking) and **parking** (blue P, zoom 12+). Forest
  Service trailheads link to their page. The computed approach start points used for access times are a separate,
  hidden layer.
- Hover highlights are drawn on a separate layer (2D) or as a per-feature state (3D), so they track the cursor.
- In the 2D map, every vector layer draws on the one canvas the streams use (`map.options.renderer` in
  `map_drainages.js`). Leaflet canvases don't pass mouse events to canvases beneath them. Folium's overlays (the fire
  closure areas, on by default) used to get their own full-map canvas above the streams, which took every hover and
  click: the cursor stayed the grab hand and nothing could be clicked. Area overlays now sit under the streams;
  point and line overlays sit on top.
- To keep the map readable, the 3D map starts with only streams, drainage outlines and names, and the PCT
  (terrain height ×1.6, light gray basemap with place labels). The 2D map also starts with trails, access roads,
  trailheads and the Eaton Fire closure areas. Everything else is in the layer list. In 3D, each overlay's starting
  state is the last entry of its `ov` row in `map3d.html`. Drops, waterfalls, gauges, closures,
  trout waters, trout evidence, springs, trails and trailheads are in the (collapsed) layer list, each named with its map symbol.

`07_road_closures.py` (no REGION needed) fetches **current road closures**. Run it, then `06_map.py`, whenever you
want fresh closures on the map; the layer name shows when they were fetched. Sources:
- **Caltrans Lane Closure System** (Districts 6, 7, 8 and 12, live JSON). Only mountain highways are included: SR-1,
  2, 18, 23, 27, 33, 38, 39, 74, 126, 138, 142, 150, 173, 189, 243 and 330, plus full closures of I-5 over the
  Grapevine. Each closure is routed along OSM roads between its begin and end points, and repeat nights of the same
  job are merged. Shown: active now, or starting in the next 7 days.
  "Full closure (one direction)" means every lane in that direction is closed.
- **LA County Public Works**, **San Bernardino County Public Works** and **Riverside County TLMA** road-closure
  services (polylines), and **Ventura County PWA** closures (points with from / to cross streets, drawn along the
  named road between them, e.g. Lockwood Valley Road). The county lists sometimes keep closures after their estimated
  reopening date; those are labelled. Orange County's feed is empty and Kern County has none.
- Closures are kept only in mountain terrain (≥150 m of elevation relief within 1 km), which drops urban roadwork.
- **Not included:** Forest Service closure orders (Bridge/Eaton fire areas, seasonal gate closures). They are
  only published as PDFs, so check fs.usda.gov/angeles and fs.usda.gov/sbnf before a trip.

Drop popups name any full closure within 3 km.

**Access, conditions and context** (run after 05 and 07):
- `08_hike.py` (per REGION): cost-distance approach time from the nearest road a car can reach, on the 10 m DEM.
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
  roads at ×0.75 speed. There is no traffic model.
- `10_sun.py` (per REGION): hours of direct sun on the water on July 15, from horizons traced in 36 directions
  out to 3 km. Also `northness`, the aspect of the mountainside within 1 km (north-facing = cooler).
  Trees aren't modelled here; `11_context.py` adds the tree canopy.
- `11_context.py`: fire perimeters since 2016 (CAL FIRE's historic perimeters, published once a year; this year's
  fires from the interagency WFIGS year-to-date perimeters; a fire in neither, like the 2026 Bouquet Fire, from the
  outline of its Forest Service BAER burn-severity map), the BAER soil burn severity of each reach's latest fire
  (area-weighted within 30 m), the USGS post-fire debris-flow hazard on channels below burns of the last 4 years,
  USFS tree canopy cover along each reach (NLCD TCC, latest year, so the 2024–25 fires show; 30 m, cached 90 days in
  `data/raw/<range>/canopy_tcc.tif`), USGS real-time gauges vs. daily percentiles for today's date (from the USGS
  Water Data APIs at `api.waterdata.usgs.gov`, which replace WaterServices: latest discharge from the OGC API,
  percentiles from the Statistics API, still in beta) plus CDEC's Piru Creek gauges (above Pyramid Lake, and the
  dam's release to lower Piru Creek), USFS wilderness and ownership, USFWS/NMFS critical habitat for stream
  species, CDFW Heritage and Wild Trout Waters, trout evidence, springs and seeps (NHD), the August mean air
  temperature along each reach and at each trout record (PRISM 1991–2020 normal, 800 m; the national file is
  downloaded once and clipped to `data/raw/_shared/prism_tmean_aug.tif`), and CPAD (California
  Protected Areas Database) holdings with restricted or no public access, flagged on reaches and drops ("⚠ No
  Public Access: ...") and drawn as their own layer.
- **Trout evidence** (`output/context/trout_evidence.gpkg`, its own map layer): CDFW Heritage & Wild Trout Program
  surveys (electrofishing / snorkel, 2023–24 so far: trout found or not), CDFW trout stocking in the last 12 months,
  and iNaturalist research-grade rainbow and brown trout sightings with an exact location (obscured ones are skipped).
  A survey or stocking point counts for the creek of the same name within 5 km; a sighting for its reach (within
  150 m) and the same creek within 1.5 km. Lakes are left out of the score (their trout are stocked): stocked lakes,
  and sightings at a lake or within 400 m of a stocked one.
- `scoring.py`: merges these onto reaches/drops and computes the final fish score (used by `06_map.py`).
- `12_profiles.py` (after `06_map.py`): long profiles for every named creek, written to `output/profiles_data.js`
  for `profiles.html`.
  - The creek line is the longest connected path through the creek's NHD named flowlines.
  - Elevation is the channel bottom: the lowest hydro-conditioned DEM cell within 20 m, forced to only go down
    downstream.
  - Drops, mapped falls and gauges are snapped on, and per-reach fish score, burn, trout-water and
    critical-habitat values are added as strips along the profile.
  - Stream and drop popups on the map link to the profile; "Show on map" in the viewer opens
    `stream_map.html#lat,lon,zoom`.
  - Drop colors match on the map and the profiles: magenta waterfall-like step, yellow cascade, violet short fall,
    ink for drops at mapped waterfalls. This set passes the all-pairs color-blind check in light and dark mode.

`02b_download_flow.py` and `11_context.py` use the USGS Water Data API. Without a key it allows 1,000 requests an
hour, shared with anything else using it from the same internet connection. A fresh `02b` gauge download takes about
115 requests (later runs fetch only gauges not yet cached), and `11_context.py` under 10. When the API says the hour's
limit is reached, the scripts wait until it resets (up to an hour). For a higher limit, put a free key from
https://api.waterdata.usgs.gov/signup/ in `USGS_API_KEY` (e.g. `export USGS_API_KEY=...` in `~/.zshrc`); the scripts
send it only to `api.waterdata.usgs.gov`.

```bash
for r in san_gabriel santa_monica san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns; do for s in 01_download_dem 02_download_vectors 03_hydrology 04_knickpoints 04b_bigcreek_steps 05_score; do REGION=$r ../.venv/bin/python $s.py; done; done; ../.venv/bin/python 07_road_closures.py
../.venv/bin/python 02b_download_flow.py
for r in san_gabriel santa_monica san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns; do for s in 05c_drainages 05b_flow; do REGION=$r ../.venv/bin/python $s.py; done; done
for r in san_gabriel santa_monica san_bernardino sespe piru sierra_pelona san_jacinto santa_ana_mtns; do for s in 08_hike 10_sun; do REGION=$r ../.venv/bin/python $s.py; done; done
../.venv/bin/python 02c_pct.py; ../.venv/bin/python 02d_trails.py; ../.venv/bin/python 02e_access.py; ../.venv/bin/python 09_drive.py; ../.venv/bin/python 11_context.py; ../.venv/bin/python 06_map.py
../.venv/bin/python 12_profiles.py
```

To refresh only the live data (closures, gauges) before a trip: `07_road_closures.py`, then `08_hike.py` per region,
`09_drive.py`, `11_context.py` and `06_map.py` (about 5 minutes).

To add a range, add an entry to `REGIONS` in `config.py` (UTM bbox + NHD HU4 codes; keep boxes from overlapping, or
streams get drawn twice) and run the per-range loop for it, then the shared steps. `08_hike.py` (wilderness) and
`09_drive.py` (major roads) re-download their shared caches when the ranges outgrow them. `08_hike.py` also
downloads each range's OSM bike paths, kept for a week. Run `09_drive.py` after it: it rewrites `trailheads.gpkg`.

## Fish score (0–100, heuristic; `scripts/scoring.py`)
`water × (30% size + 30% thermal + 15% gradient + 25% remoteness) × burn × trout × heat`
- **water:** dry-season flow from the Natural Flows model (`05b_flow.py`): 0.05 + 0.95 × the share of summers since
  2011 the reach kept ≥0.1 cfs through July–October; 0.3 in a reservoir. Reaches the model doesn't cover (about 9%)
  fall back to the NHD class: perennial 1.0, intermittent 0.35, unmapped 0.15, ephemeral 0.05.
  Below a gauged diversion, the gauge's own share replaces the model's only when three things hold: it kept flowing
  in under half of 5+ summers since 2011, the reach is close below the diversion, and no trout are known there.
  Today that is only the San Jacinto River near San Jacinto, which the gauge found flowing in 19% of summers. Trout
  were found below the Santa Ana, Mill, Lytle and Plunge diversions in 2019–2024, so those stay on the model. The
  model and NHD
  often disagree: of NHD's 2,425 "perennial" reaches the model has 630 drying in some or most summers, and 837 NHD
  "ephemeral" reaches flowing through most summers. Popups show the model's typical and drought-year low flow.
  Desert-side canyons with year-round water score high on water alone. The heat gate below takes down only the low
  desert ones (Whitewater, Palm Canyon Wash, Tahquitz). Murray and upper Andreas canyons stay up because it isn't
  certain they're too warm.
- **size:** drainage area, log scale from 1 to 50+ km². The full area (`area_full_km2`): with what flows in from
  neighbouring boxes and from above reservoirs, which each box's own routing misses.
- **thermal:** 50% elevation band (700–2300 m), 35% summer shade, 15% north-facing mountainside. Shade combines the
  terrain's shade with the tree canopy along the reach: 1 − (1 − terrain) × (1 − 0.8 × canopy), full credit at 45%.
  **Tailwaters** get the elevation part in full whatever their elevation. These are the rivers below a dam that
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

Critical habitat, wilderness and non-Forest-Service land are shown as flags, not scored. Critical habitat is USFWS/NMFS
*designated* habitat clipped to the study areas. It is not a closure map: Forest Service closures for arroyo toad and
other species are set by forest orders, usually cover less ground, and have to be checked on the forest's site.

## Validation (mapped falls from OSM + NHD matched by a detected drop within 200 m)
| | Pass 1 only | Pass 1 + big-creek pass |
|---|---|---|
| Falls on creeks ≥10 km² | 16 / 26 | 23 / 26 |
| Falls on smaller drainages | 45 / 72 | 45 / 72 |
| **All** | **61 / 98** | **68 / 98** |

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
- Some "dam / weir" flags come from OSM check dams. Some "DEM artifact" flags are real falls next to roads.
- The approach model assumes closed and gated roads may be walked and biked, and it rides every fire road, even in
  wilderness or where bikes are posted out. Those routes are flagged "double-check bike access". Many long-term
  closures allow walking and biking, but fire and storm closure orders can ban all entry. Hike times are model
  estimates; the canyon-bottom and chaparral speeds are guesses, so expect real off-trail travel to vary a lot.
- Drive times have no traffic. Add 30–60+ min for LA weekday or weekend-morning traffic.
- `non_fs_land` comes from the USFS basic-ownership layer, which only separates Forest Service from everything else.
  It can be private, county or other public land, so check the parcel before crossing it.
