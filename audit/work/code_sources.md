# Audit notes: data sources, downloads, caches, access times, context

Scope: `scripts/01_download_dem.py, 02_download_vectors.py, 02b_download_flow.py, 02c_pct.py, 02d_trails.py,
02e_access.py, 02f_known_falls.py, 02g_greenness.py, 07_road_closures.py, 08_hike.py, 09_drive.py, 10_sun.py,
11_context.py, troutdata.py, config.py, geomatch.py` (all read in full), `data/validate*.py`,
`data/check_flow_drops.py`, `requirements.txt`, the curated falls CSVs (headers and source values), and greps of
`lakesources.py, 05d_lakes.py, lake_bathymetry.py, lakelidar.py, lakedata.py, flowlib.py, watertemp.py, areaclip.py,
scoring.py, 06_map.py, map_drainages.js, map3d.html, 13_overview.py, 14_portable.py` and the `run_*.sh` drivers.

How it was done. Static reading only: no script in `scripts/` was imported or run, no network call was made, nothing
was built. Three kinds of evidence beyond the code, all read-only:
- cached downloads under `data/raw/` (JSON / GeoJSON / GPKG / GeoTIFF headers), read with small throw-away scripts
  kept outside the project;
- the published site clone `publish/alexanderswann.github.io/streams` at commit `6875118` (2026-11-21 22:16 -0500);
- the pipeline logs `data/*.log`.
`output/` and `data/derived/` were not used (another session is rebuilding).

Marks: **CONFIRMED** = read end to end in the code (and, where said, seen in cached or published data).
**PLAUSIBLE** = follows from the code but rests on a server's behaviour or an outside fact I could not check offline.
Comments and docstrings were not trusted; where they disagree with the code it is listed (H4).

Counts: A 12 flags (72 endpoints in scope, plus lake and validator tables) · B 16 · C 10 (38 caches) · D 17 biases
+ 5 bike_check gaps (39 rows of constants) · E 16 · F 11 · G 13 · H 21 duplicates + 17 dead items + 11 stale
docstrings + 5 validators · I 26 (most restate a finding above with its failure scenario).

---

## A. Endpoint inventory

### A-table 1. Pipeline steps in scope

T/R = timeout (s) / tries. "none" under R = one try.

| # | Host | Dataset / layer | Used for | Areas | file:line | T / R |
|---|---|---|---|---|---|---|
| 1 | elevation.nationalmap.gov | 3DEPElevation ImageServer `exportImage` (dynamic mosaic, resampled bilinear to 10 m UTM) | DEM tiles | all | 01_download_dem.py:6, 23-35 | 600 / 6 |
| 2 | prd-tnm.s3.amazonaws.com | `StagedProducts/Hydrography/NHD/HU4/GPKG/NHD_H_<hu4>_HU4_GPKG.zip` | NHD flowlines, points, waterbodies | all | 02_download_vectors.py:20-25 | 600 / none |
| 3 | overpass.openstreetmap.fr, overpass-api.de | OSM via Overpass | roads, paths, falls, dams per range | all | 02_download_vectors.py:56-71 -> geomatch.py:10-23 | 20 connect + query limit + 60 / 14 |
| 4 | same | OSM hiking route relations | long trail | areas with `long_trail` | 02c_pct.py:18-36 | (20, 600) / 6 |
| 5 | same | OSM path/footway/bridleway/track + route relations | trail layer | all | 02d_trails.py:61-74, 116-120 | as 3 (own copy) |
| 6 | same | OSM roads, parking, trailheads; cycleways | access roads | all | 02e_access.py:52-58, 67 | as 3 |
| 7 | same | OSM falls, rapids, swimming places (0.5 degree tiles) | known falls | all | 02f_known_falls.py:174-197, 200 | as 3 |
| 8 | same | OSM cycleways (again) | bike lines | all | 08_hike.py:104-118 | as 3 |
| 9 | same | OSM motorway..secondary, home to all boxes | drive graph | all | 09_drive.py:29-41 | (20, 900) / 6 |
| 10 | api.water.usgs.gov | `/geoserver/wmadata/ows` WFS 1.0.0 `wmadata:nhdflowline_network` (NHDPlus V2 + EROM) | COMID network, EROM flows | all | 02b_download_flow.py:71-78 | 300 / 5 |
| 11 | same | same, level-path attributes | drainage trunks | all | flowlib.py:322-326 | 300 / 4 |
| 12 | flow-api.codefornature.org | `/v2/stream/` TNC California Natural Flows | monthly modelled flow | la | 02b_download_flow.py:102-104 | 300 / 5 |
| 13 | api.waterdata.usgs.gov | OGC API `time-series-metadata`, `monitoring-locations`, `daily` | gauge records | all | 02b_download_flow.py:121, 138-146, 176-178 | 300 / 5 |
| 14 | same | OGC API `latest-continuous`, `monitoring-locations` | gauge snapshot | all | 11_context.py:472-473, 486-487 | 300 / 4 |
| 15 | same | `/statistics/v0/observationNormals` | percentiles for today's date | all | 11_context.py:501-503 | 300 / 3 |
| 16 | partnerships.nationalmap.gov | `USGSTrails/MapServer/0` (National Digital Trails) | official trail names, uses | all | 02d_trails.py:33, 145 | 300 / 4 |
| 17 | apps.fs.usda.gov/arcx (EDW) | `EDW_RoadBasic_01/0,1` | USFS roads open / closed | all | 02d_trails.py:34, 147; 02e_access.py:97-98 | 300 / 4 |
| 18 | same | `EDW_MVUM_02/1` | motor vehicle use map | all | 02e_access.py:103 | 300 / 4 |
| 19 | same | `EDW_TrailNFSPublish_01/0` | USFS trail bike rules | all | 02d_trails.py:269 | 300 / 4 |
| 20 | same | `EDW_RecreationOpportunities_01/0`, `EDW_InfraRecreationSites_01/0` | trailheads | all | 02e_access.py:185, 193 | 300 / 4 |
| 21 | same | `EDW_Wilderness_01/0` | wilderness | all | geomatch.py:70-73 | 300 / none, no paging |
| 22 | same | `EDW_BurnedAreaEmergencyResponse_01/1` | soil burn severity | all | 11_context.py:112 | 300 / 12 |
| 23 | same | `EDW_BasicOwnership_02/0` | non-FS land | all | 11_context.py:161 | 300 / 12 |
| 24 | services2.arcgis.com/AhxrK3F6WM8ECvDi | CA State Parks `RecreationalRoutes`; NPS Santa Monica Mtns `NPS_Trail_Inventory` | bike rules | la | 02d_trails.py:265, 273-274 | 300 / 4 |
| 25 | services.arcgis.com/RmCCgQtiZLDCtblq | LA County `Eaton_Fire_Impacted_Trails_and_Roads_WFL1` layers 14, 16 | fire closures | la | 02d_trails.py:266, 275-276; 02e_access.py:141-142 | 300 / 4 |
| 26 | services6.arcgis.com/DZHaqZm9cxOD4CWM (NYSDEC ArcGIS Online) | `NYS_DEC_Lands/0` | "wilderness" (no bikes) | adk_* | geomatch.py:76-77 | 300 / 4 |
| 27 | same | `Inland_Trout_Stream_Fishing/0`, `Water_Quality_Classifications/1`, `Trout_Stream_Fishing_Access/1` | trout waters, stocking | adk_* | troutdata.py:490, 497, 517, 525 | (20, 300) / 4 |
| 28 | services2.arcgis.com/Uq9r85Potqm3MfRV (CDFW BIOS) | `biosds69_fmu` passage barriers | known falls | la | 02f_known_falls.py:259 | 300 / 4 |
| 29 | same | `biosds1356_fpu`, `HWT_Project_Map_WFL1/14`, `biosds2897_fmu` | trout waters, surveys, stocking | la | 11_context.py:217, 251, 260 | 300 / 12 |
| 30 | services1.arcgis.com/fBc8EJBxQRMcHlei (NPS) | `GRSM_WATERFALLS/0` | known falls | smokies | 02f_known_falls.py:279 | 300 / 4 |
| 31 | same | `GRSM_TROUT_DISTRIBUTION/0` | trout waters | smokies | troutdata.py:452 | (20, 300) / 4 |
| 32 | same | `GRTE_MajorRoadStatus_(PublicView)/0`, `SEAC_BLRI_Mileposts/2`, `GRSM_ROADS/0` | closures | jackson, lexington_va, smokies | 07_road_closures.py:279, 389, 447 | 120 / 4 |
| 33 | prd-tnm.s3.amazonaws.com | GNIS `DomesticNames_<ST>_Text.zip`; archive `<ST>_Features_20210825.txt` | known falls | all | 02f_known_falls.py:311-318 | 300 / none |
| 34 | query.wikidata.org | SPARQL | known falls | all | 02f_known_falls.py:345-346 | 180 / none |
| 35 | earth-search.aws.element84.com | STAC `/v1/search` + Sentinel-2 L2A COGs on AWS (read by GDAL) | late-summer NDVI | la, jackson | 02g_greenness.py:32, 41, 64, 108 | 90 / 5; GDAL 5 retries |
| 36 | cwwp2.dot.ca.gov | Caltrans LCS `lcsStatusD06/07/08/12.json` | closures | la | 07_road_closures.py:97 | 120 / 4 |
| 37 | dpw.gis.lacounty.gov | `Road_Closures/MapServer/0` | closures | la | 07_road_closures.py:172 | 120 / 4, no paging |
| 38 | services.arcgis.com/ZZ0KZXZVmgB1v555 | San Bernardino County road closures | closures | la | 07_road_closures.py:182 | 120 / 4 |
| 39 | gis.countyofriverside.us | `roadClosures_wMap_prod/MapServer/11` | closures | la | 07_road_closures.py:192 | 120 / 4 |
| 40 | services5.arcgis.com/LU8yNTyyh8FrdvWy | Ventura County `ActiveRoadClosures/0` | closures | la | 07_road_closures.py:203 | 120 / 4 |
| 41 | services9.arcgis.com/6ukHJ1QHS9lvQoRO | Teton County road closures | closures | jackson | 07_road_closures.py:288 | 120 / 4 |
| 42 | services1.arcgis.com/2iUE8l8JKrP2tygQ | `GDOT_511_Events_Public_View/0` | closures | n_georgia | 07_road_closures.py:312 | 120 / 4 |
| 43 | api.dx.ne-compass.com | `wzdx-latest` (WZDx) | closures | central_vt | 07_road_closures.py:328 | 120 / 4 |
| 44 | 511.idaho.gov | `/api/wzdx` | closures | jackson | 07_road_closures.py:345 | 120 / 4 |
| 45 | data.511-atis-ttrip-prod.iteriscloud.com | four undocumented VDOT 511 GeoJSON files | closures | lexington_va | 07_road_closures.py:361-365 | 120 / 4 |
| 46 | www.nps.gov | `blri/planyourvisit/roadclosures.htm` (HTML table) | closures | lexington_va, smokies | 07_road_closures.py:387 | 120 / none, no status check |
| 47 | services.arcgis.com/NuWFvHYDMVmmxMeM | `NCDOT_TIMS_Incidents/0,1` | closures | smokies | 07_road_closures.py:408 | 120 / 4 |
| 48 | spatial.tdot.tn.gov | `Smartway_Events/0` | closures | smokies | 07_road_closures.py:424 | 120 / 4 |
| 49 | www.nps.gov | `grsm/park-alerts-grsm.json`; `grsm/planyourvisit/seasonalroads.htm` | closures | smokies | 07_road_closures.py:462, 476 | 120 / 4; page: none |
| 50 | www.fs.usda.gov | `r08/cherokee/conditions/road-construction` (HTML table) | closures | smokies | 07_road_closures.py:515 | 120 / none |
| 51 | services1.arcgis.com/jUJYIo9tSA7EHvfZ | CAL FIRE `California_Historic_Fire_Perimeters/0` | fires | la | 11_context.py:78 | 300 / 12 |
| 52 | services3.arcgis.com/T4QMspbfLg3qTGWY (NIFC) | `InterAgencyFirePerimeterHistory_All_Years_View/0`; `WFIGS_Interagency_Perimeters_YearToDate/0` | fires | history: not la; WFIGS: all | 11_context.py:83, 103 | 300 / 12 |
| 53 | services.arcgis.com/v01gqwM5QqNysAAi (USGS) | `USGS_Post_Fire_Hazard_Assessment_Data/5` | debris-flow hazard | all | 11_context.py:140 | 300 / 12 |
| 54 | same | `PADUS_Public_Access/0` | restricted access | not la | 11_context.py:175 (and 05d_lakes.py:1036) | 300 / 12 |
| 55 | gis.cnra.ca.gov | `Boundaries/CPAD_AccessType/MapServer/0` | restricted access | la | 11_context.py:171 | 300 / 12 |
| 56 | services.arcgis.com/QVENGdaPbd4LUkLV | `USFWS_Critical_Habitat/0` | critical habitat | all | 11_context.py:195 | 300 / 12 |
| 57 | services2.arcgis.com/C8EMgrsFcRFL6LrL | `NMFS_ESA_Critical_Habitat_gdb/0` | steelhead habitat | la | 11_context.py:201 | 300 / 12 |
| 58 | api.inaturalist.org | `/v1/observations` | trout sightings | all | 11_context.py:281-283 | 120 / 3 |
| 59 | imagery.geoplatform.gov | `USFS_EDW_NLCD_TCC_CONUS/ImageServer` (info + exportImage) | canopy | all | 11_context.py:386, 392, 402 | info 120 / none; tiles 300 / 4 |
| 60 | cdec.water.ca.gov | `JSONDataServlet` (PIR, PYM) | two Piru gauges | la | 11_context.py:551 | 300 / 4 |
| 61 | services1.arcgis.com/FjPcSmEFuDYlIdKC (CT DEEP) | fish community, stocked streams/lakes, management areas | trout | ne_ct | troutdata.py:132-171 | (20, 300) / 4 |
| 62 | anrmaps.vermont.gov | ANR atlas layers 49, 52 | trout | central_vt | troutdata.py:178-187 | same |
| 63 | services.dwr.virginia.gov | cold water survey, stocked reaches/lakes | trout | lexington_va | troutdata.py:198-211 | same |
| 64 | services6.arcgis.com/9QlSLDqa0P1cHLhu (GA DNR) | trout streams, recent stocking, sampling | trout | n_georgia | troutdata.py:220-237 | same |
| 65 | services6.arcgis.com/cWzdqIyxbijuhPLw (WGFD) | fishing guide streams, CuttslamRivers | trout | jackson | troutdata.py:251-262 | same |
| 66 | gis.psmfc.org (StreamNet) | `Fish_Dist/MapServer/13` (IDFG rows) | trout | jackson | troutdata.py:269-272 | same |
| 67 | fbweb.pa.gov (PFBC); conservationexplorer.dcnr.pa.gov | natural reproduction, special regs, stocked sections/lakes; Class A | trout | se_pa | troutdata.py:280-321 | same; service list 60 / none |
| 68 | enterprise.firstmap.delaware.gov | `DE_Fishing_Access/1` | trout | se_pa | troutdata.py:329-331 | same |
| 69 | services1.arcgis.com/YfqBAUM5nWR3yhGP (NCWRC); services3.arcgis.com/PWXNAH2YKmZY7lBq (TWRA); services.arcgis.com/IT5YbezrAr6F9SXt (EBCI) | PMTW streams/impoundments; stocking, wade sites, genetics; fishing zones | trout | smokies | troutdata.py:354-387, 401-441, 472-483 | same; service list 60 / none |
| 70 | services1.arcgis.com/754BERmVIq3RqSf8 (Trout Unlimited) | brook trout portfolio patches | trout | 10 eastern areas | troutdata.py:532-535 | same |
| 71 | www.waterqualitydata.us | `/data/Result/search`, `/data/Station/search` (legacy profiles) | water-temperature fit | all | watertemp.py:84-89 (and data/validate_heat.py:36) | 900 / none |
| 72 | prism.oregonstate.edu (**ftp://**) | `normals/us/800m/tmean/monthly/prism_tmean_us_30s_202008_avg_30y.zip` | August air | all | watertemp.py:93, 109 | no timeout / none |

Also: www2.census.gov TIGER 2024 states (areaclip.py:17, 28; 600 / none; only central_vt has `clip_state`).

### A-table 2. Lake sources (grep only; another agent reads them in full)

| Host | Dataset | file:line |
|---|---|---|
| www.epa.gov | National Lakes Assessment CSVs 2007, 2012, 2017, 2022 | lakesources.py:31-37 (fetch 40-54: 300 s / 4) |
| CT DEEP, VT ANR, VA DWR, PFBC, DCNR, NCWRC, TWRA, TVA ArcGIS services | launches, access, rules, trout lakes | lakesources.py:84-86, 138, 151, 195, 208, 214, 218 (through geomatch.esri) |
| data.ny.gov | Socrata `mw8j-wduf`, `yvkb-z58x`, `e52k-ymww` | lakesources.py:286, 290-311, 319, 339, 364 (180 s / none) |
| tigerweb.geo.census.gov | counties, towns | lakesources.py:287, 357, 359 |
| api.gbif.org | species match, occurrence search, dataset titles | 05d_lakes.py:835, 839, 848 (60-120 s / none) |
| Overpass | `natural=water` | 05d_lakes.py:635 |
| PAD-US (USGS AGOL) | public access | 05d_lakes.py:1036 |
| tnmaccess.nationalmap.gov; index.nationalmap.gov | 1 m DEM product list; lidar work units | lakelidar.py:29-30, 41 (180 s / 5) |
| CT DEEP AGOL; anrmaps.vermont.gov; www.sciencebase.gov; www.gis.dcnr.pa.gov; pubs.usgs.gov; charts.noaa.gov | bathymetry contours, soundings, grids, ENC cells | lake_bathymetry.py:36-37, 76, 123, 140, 200, 239, 255, 300-302, 318, 356 |
| lakedata.py URLs | citations only, never fetched | lakedata.py:35-132 |

### A-table 3. Validators

| Host | Dataset | file:line | T / R |
|---|---|---|---|
| flow-api.codefornature.org | TNC flows for gauge COMIDs | data/validate_flow.py:45-48 | 300 / none, no User-Agent |
| www.waterqualitydata.us | water temperature | data/validate_heat.py:36-39 | 600 / none |
| apps.fs.usda.gov/ArcX | `EDW_NorWeST_StreamTemperatures_01/2` | data/validate_heat.py:45-57 | 300 / none |
| api.epa.gov | StreamCat `streams/metrics` | data/validate_heat.py:65-66 | 300 / none |

### A flags

- **A1 CONFIRMED. No caller of WaterServices or NWIS is left.** `grep -i "waterservices|nwis|waterdata.usgs"` over
  `scripts/` and `data/*.py` finds only comments (02b_download_flow.py:118, 149, 157; 11_context.py:441, 471) and a
  link to `https://waterdata.usgs.gov/monitoring-location/<site>` written into each gauge popup (11_context.py:543:
  a page link, not a call). Both gauge callers use `api.waterdata.usgs.gov` (02b:121; 11_context.py:445).
- **A2 PLAUSIBLE. The Water Quality Portal calls use its legacy profile endpoints** (`/data/Result/search` with
  `dataProfile=narrowResult`): watertemp.py:84-89 (pipeline: the water-temperature fit) and
  data/validate_heat.py:36-39. From memory, not checked offline: USGS's own samples in the legacy WQP profiles
  stopped being updated on 2024-03-11 (new USGS data is only in the WQX 3.0 profiles). If so the fit sees USGS
  readings only up to March 2024; the state and tribal readings are unaffected. Not part of the 2027-02-22 shutdown.
- **A3 CONFIRMED. A beta API in the pipeline:** `api.waterdata.usgs.gov/statistics/v0/observationNormals`
  (11_context.py:501; the comment at 442 calls it beta). When it fails the step goes on and the gauge is shown as
  "no history" (E7).
- **A4 PLAUSIBLE. `api.water.usgs.gov/geoserver/wmadata/ows`** (02b:71; flowlib.py:322) is the GeoServer behind USGS's
  NLDI, read as WFS 1.0.0 with one `GetFeature` per box and no paging or `maxFeatures`: a server-side feature cap
  would cut the answer without an error. No documented stability promise that I know of.
- **A5 PLAUSIBLE. NHD staged products** (02_download_vectors.py:20): the NHD was frozen in 2023 (3DHP replaces it);
  the staged files are static, which suits a never-refreshed cache, but the bucket path may go away.
- **A6 CONFIRMED. Overpass mirrors are hard-coded in four places** with the same comment "(the kumi mirror stopped
  answering in Nov 2026)": geomatch.py:13, 02d_trails.py:64, 02c_pct.py:26, 09_drive.py:32. A mirror change means four
  edits.
- **A7 CONFIRMED. Stand-in or undocumented sources chosen ad hoc:** DCNR's Conservation Explorer for PFBC's Class A
  layer (troutdata.py:281-282); StreamNet for Idaho Fish & Game (troutdata.py:269-272); Element 84's Earth Search for
  Sentinel-2 (02g_greenness.py:16-17, 32); VDOT 511's "undocumented files ... they may move" (07_road_closures.py:22-23,
  361); three HTML pages scraped with regular expressions (07:387, 476, 515); the park's alerts JSON (07:462).
- **A8 CONFIRMED. Calls with one try (no retry):** NHD zip (02:21), GNIS (02f:299), Wikidata (02f:345), wilderness
  (geomatch.py:70), canopy service info (11_context.py:392), the PFBC and NCWRC service lists (troutdata.py:289, 361),
  WQP (watertemp.py:84), PRISM (watertemp.py:109), TIGER (areaclip.py:28), data.ny.gov (lakesources.py:301), GBIF
  (05d_lakes.py:835-848), the three scraped pages (07:387, 476, 515). Every `requests` call has a timeout.
- **A9 CONFIRMED. One call has no timeout at all and uses plain FTP:** `urllib.request.urlretrieve("ftp://prism.
  oregonstate.edu/...")` (watertemp.py:93, 109). A stalled transfer hangs the step for good. Runs once (the national
  file is kept, 58 MB, on disk since 2026-11-18).
- **A10 CONFIRMED. Secrets read from the environment: one, `USGS_API_KEY`** (02b_download_flow.py:122;
  11_context.py:449). 11_context sends it only to URLs that start with the USGS host (449). 02b sends it to whatever
  URL the API's "next" link names (02b:133: `get(nxt, headers=WD_KEY)`), which is the same host in practice
  (PLAUSIBLE risk, low). Other environment switches: `AREA`, `REGION` (config.py:361, 384), `REFRESH`, `OSM`
  (02:67), `LAKES_OUT`, `LAKE_DEPTH_OUT`, `SKIP_03`, `SKIP_03B`, `PREVIEW`.
- **A11 CONFIRMED. Two states rename their services every year;** the code lists the folder and takes the newest
  (troutdata.py:285-293 PFBC, 357-365 NCWRC). If PFBC's list request fails, its stocked sections are left out with
  no message (G8).
- **A12 CONFIRMED. Fourteen separate User-Agent definitions under two names** ("la-stream-analysis/0.1" in
  02b:25, 02c:29, 02d:32, geomatch.py:7, 07:34, 09:35, 11:40; "stream-analysis/0.1" in troutdata.py:51,
  lakesources.py:28, flowlib.py:326, watertemp.py:87, areaclip.py:28, lake_bathymetry.py x5). No personal detail in
  any of them. data/validate_flow.py and validate_heat.py send none.

---

## B. Licence and attribution

### What the map credits

- 2D map attribution line (map_drainages.js:512-515): "Trails & PCT (c) OpenStreetMap contributors" + `LBL.credits`.
- `LBL.credits` (06_map.py:37-40): USGS National Digital Trails, USFS, [CDFW], iNaturalist, [CAL FIRE | NIFC fire
  history], NIFC WFIGS, USGS gauges & debris-flow hazard, [CDEC], [TNC Natural Flows | NHDPlus V2 (EROM)], PRISM Group
  Oregon State University, "known falls: OSM, USGS GNIS, Wikidata and the guides named in each".
- A falls guide is added to that line only when it has **50 or more falls on that map** (06_map.py:54-58).
- 3D map: "USGS NHD" + the same credits (map3d.html:213), OSM for roads and trails (286, 318), "iNaturalist [· CDFW]"
  for the trout points (406), Mapzen / AWS terrain (147). Overview: "Streams: USGS 3DEP & NHD" (13_overview.py:74).
  One-file map: 14_portable.py:114.
- Everything else is credited only inside a record's own text: a trout label ends "(VA DWR)", "(NYSDEC)",
  "(EBTJV / Trout Unlimited)" (troutdata.py); a fall's popup lists its sources and links one (02f:472-484); a road
  closure's tooltip has a Source field (06_map.py:1344-1346); a lake popup names its sources (maplakes.py).

### What the code records about terms

| Source | Terms as recorded | Where recorded | Published in | Credit |
|---|---|---|---|---|
| OpenStreetMap | ODbL | 02d_trails.py:19; 02e_access.py:27 | trails, roads, parking, falls, long trail | attribution line |
| USGS National Digital Trails, USFS | "both public domain" | 02d_trails.py:5 | trails, roads, trailheads | attribution line |
| US Census TIGER | public domain | areaclip.py:13 | clip line only | none (not needed) |
| data.ny.gov | "OPEN-NY terms: free reuse" | lakesources.py:284 | lake records | in text |
| NYSDEC ArcGIS items | "secondary distribution of the data is not allowed" | lakesources.py:284-285; MULTI_AREA_LOG.md:2646-2648 | see B1, B2 | in text |
| PFBC | "with credit to PFBC, as its licence asks" | lakesources.py:12, 140 | lake access; trout labels | in text |
| NOAA ENC | redistribution allowed if origin and agreement are shown | lake_bathymetry.py:17-20, 302, 420 | Lake Champlain depths | in popups |
| gawaterfalls.com | "carry no license"; held, then published by the owner's choice | MULTI_AREA_LOG.md:940-943; 06_map.py:52 | 695 falls, n_georgia | line + popup |
| World Waterfall Database, nnywaterfalls.com | both forbid redistribution; "keep both, ask both"; emails sent 2026-11-20 | MULTI_AREA_LOG.md:1660-1680, 2524 | 106 and 116 falls | see B3 |
| Everything else | nothing recorded | - | - | - |

`data/known_falls_curated*.csv` has the columns `area, name, alt_names, kind, stream, lat, lon, precise, source, url,
note, replaces`: **no column for a source's terms or consent**. The only switch is renaming a whole file to
`.csv.held` (02f_known_falls.py:39-41).

### Findings

- **B1 CONFIRMED. Three NYSDEC ArcGIS layers are still downloaded and published** on the four Adirondack maps (hidden
  from the menus but live): `Inland_Trout_Stream_Fishing`, `Water_Quality_Classifications`,
  `Trout_Stream_Fishing_Access` (troutdata.py:490-527; all four areas have `ny_trout`, config.py:293, 312, 329, 344).
  Their lines become the "Trout waters" layer (11_context.py:219-223 -> 06_map.py:1386-1404), each reach's
  trout label (11_context.py:590-596) and stocking records (troutdata.py:508-514). The project's own log records the
  terms ("may NOT be distributed outside DEC without permission") and lists this as an open follow-up
  (MULTI_AREA_LOG.md:2646-2648, 2712). Cached copies are dated 2026-11-19; the 7-day cache means the next build
  after 11-26 calls DEC again. This is the one place the "New York via data.ny.gov only" decision is not carried out.
- **B2 CONFIRMED. A fourth NYSDEC ArcGIS layer, `NYS_DEC_Lands`,** (geomatch.py:76-77) feeds `wilderness.gpkg`:
  the Adirondack "Wilderness (no bikes)" polygons on the map (11_context.py:156-160 -> 06_map.py:1391), each reach's
  wilderness flag and the bike rules (02d:310, 02e:131, 08:131). The cached files hold 24 DEC units for
  adk_high_peaks and 12 for adk_southwest (read 2026-11-21). Its terms are recorded nowhere. No HuntFishNY endpoint
  is called anywhere (grep).
- **B3 CONFIRMED. World Waterfall Database is named in no map's attribution line; nnywaterfalls.com on one.** The
  50-falls rule (06_map.py:54) is per map: WWD has at most 44 rows on one map (central_vt 44, adk_high_peaks 15, la
  13, adk_northwest 13, adk_southwest 9, adk_southeast 6, smokies 6); nnywaterfalls has 64 on adk_southeast and 26,
  21, 5 on the others. Published credits (site clone, 6875118): central_vt, la, adk_high_peaks, adk_southwest end
  "known falls: OSM, USGS GNIS, Wikidata and the guides named in each"; adk_southeast adds nnywaterfalls.com;
  n_georgia adds gawaterfalls.com. Both sites are named and linked in each of their falls' popups. Worth knowing
  while consent is pending.
- **B4 CONFIRMED. gawaterfalls.com:** 695 rows, all marked precise, all n_georgia; credited in the line and in each
  popup, as decided.
- **B5 CONFIRMED. Other curated sources with no terms on record** (rows by source label, drop rows left out): New
  England Waterfalls 35 (central_vt 32, ne_ct 3), SGM waterfall list / tchester.org 27 (la), RiverBrain 9
  (n_georgia), Vermont River Conservancy 6, ncwaterfalls.com 4 ("states no terms", MULTI_AREA_LOG.md:1667), and one
  row each from Trail Finder, Waterfall Hero, freearenas.com, The Outbound, a Caltech guide. 157 of the 328 rows'
  notes say the point is the source's own coordinates.
- **B6 CONFIRMED. Two rows cite map products:** "Apple Maps · Richmond Land Trust" (Triple Buckets, central_vt: "Point:
  Apple Maps listing (approximate)") and "komoot · Blue Ridge Parkway" (Wigwam Falls: no coordinates of its own, it
  renames an OSM node). Apple's terms do not allow taking data out of Maps; one point.
- **B7 CONFIRMED. iNaturalist observations are published without looking at each observation's licence**
  (11_context.py:274-311 keeps the date, species name, point and link; obscured locations are skipped, 290).
  iNaturalist is in the attribution line; the observer is reachable through the link only.
- **B8 CONFIRMED (grep). GBIF records at lakes: the per-record licence is dropped** (05d_lakes.py:849-854 keeps
  dataset title, species, date, point). For the lakes auditor.
- **B9 CONFIRMED. No state fish agency is in the attribution line.** CT DEEP, Vermont F&W, Virginia DWR, Georgia DNR,
  Wyoming G&F, IDFG / StreamNet, PFBC, DCNR, DNREC, NCWRC, TWRA, the Eastern Band of Cherokee, the park (GRSM) and
  Trout Unlimited / EBTJV are named only inside each label. None of their terms is recorded; the module says each
  was "checked against the live services" (troutdata.py:8), which is about availability.
- **B10 CONFIRMED. Sentinel-2 gets no credit anywhere** (grep for Sentinel / Copernicus finds only docstrings).
  It decides "seasonal: bare channel" on LA and Jackson reaches (02g -> scoring.py:232-237). The Copernicus terms
  ask for "contains modified Copernicus Sentinel data [year]" on what is derived from it.
- **B11 CONFIRMED. Road-closure text is republished word for word** (reason up to 300 characters,
  07_road_closures.py:274) with the agency in each tooltip; no terms recorded for any of the 14 feeds; one is
  undocumented (A7).
- **B12 CONFIRMED. TNC Natural Flows:** credited; no licence recorded (02b_download_flow.py).
- **B13 CONFIRMED. Published with no credit at all (all public domain as far as I know):** USFWS and NMFS critical
  habitat (layer label names neither, 06_map.py:1389), the Water Quality Portal behind every "summer water about"
  figure, EPA, Census; USGS 3DEP and NHD are missing from the 2D map's line though present on the 3D, overview and
  one-file maps. CPAD and PAD-US are named only in the layer's title (06_map.py:34); CPAD asks for a citation.
- **B14 CONFIRMED (observation). The owner's seven home ZIP codes are printed on the public maps** in every reach's
  access line ("Drive 49 min (37 mi) from 83001 Jackson (town square; the ZIP spans the valley)", 06_map.py:483;
  config.py:62, 113, 150, 164, 189, 199, 215). Town-centre points, not addresses.
- **B15 CONFIRMED. Terms that are honoured in the code:** PFBC credit (lakesources.py:140; every PFBC trout label
  ends "(PFBC)"), NOAA ENC (popups name origin and agreement, lake_bathymetry.py:420), OpenTopoMap "(CC-BY-SA)"
  (06_map.py:545), GRSM segments marked "Internal NPS Only" are filtered out though the service serves them
  (troutdata.py:459; 02f:280).
- **B16 CONFIRMED. OSM share-alike:** the trail, road and falls layers are databases derived from OSM and are
  published inside the HTML. The "(c) OpenStreetMap contributors" link is there; nothing says the derived layers are
  offered under ODbL.

### Published sources with a licence or credit problem (the list)

Restrictive or unrecorded terms: NYSDEC ArcGIS x4 (B1, B2); World Waterfall Database and nnywaterfalls.com (known,
consent pending; B3); gawaterfalls.com (known); New England Waterfalls, tchester.org SGM list, RiverBrain,
ncwaterfalls.com, Vermont River Conservancy, Apple Maps (1 point), komoot (1 link), four one-row sites (B5, B6);
iNaturalist per-observation licences (B7); GBIF per-record licences (B8); every state and tribal fish agency layer
(B9); VDOT 511's undocumented files and the other closure feeds (B11); TNC Natural Flows (B12).
No credit: Sentinel-2 / Copernicus (B10); state fish agencies and Trout Unlimited outside their labels (B9);
World Waterfall Database outside popups (B3); USFWS / NMFS, Water Quality Portal, 3DEP / NHD on the 2D map (B13).

---

## C. Cache inventory

Key: what must match for the copy to be used. "name" = a file name built from the range or area name only.

| # | File pattern | Written by | Key | Expiry | Force | Stale after a box-edge move? | When the fetch fails |
|---|---|---|---|---|---|---|---|
| 1 | `<range>/dem_tiles/dem_<x0>_<y0>.tif` | 01:14-37 | tile origin in the name + right/top bounds (19-21) | none | delete | no (short tiles refetched; off-grid tiles orphaned) | exit after 6 tries; old `dem_10m.tif` stays |
| 2 | `<range>/dem_10m.tif` | 01:40-46 | rebuilt every run | - | - | no | - |
| 3 | `_national/NHD_H_<hu4>_HU4_GPKG.zip/.gpkg` | 02:17-32 | HU4 | none | delete | n/a | crash; **not atomic** (21-25, 29-31) |
| 4 | `<range>/nhd_flowlines.gpkg`, `nhd_points.gpkg` | 02:46-53 | rebuilt every run | - | - | no | - |
| 5 | `<range>/osm_roads/trails/waterfalls/dams.gpkg` | 02:98-101 | rebuilt unless `OSM=keep` or Overpass down | none | run again | **yes** under `OSM=keep` or an outage (66-77: no extent test) | old files kept, NOTE in the log, exit 0 |
| 6 | `_shared/flow/nhdplus_v2.gpkg` + `.regions.json` | 02b:66-86 | set of range names | none | delete both | **yes, silent** | crash |
| 7 | `_shared/flow/nhdplus_v2_paths.csv` + sidecar | flowlib.py:307-338 | set of range names | none | delete | **yes, silent** | crash after 4 tries |
| 8 | `_shared/flow/reservoirs.gpkg` + sidecar | flowlib.py:156-183 | set of range names | none | delete | **yes, silent** | - (local read) |
| 9 | `_shared/flow/nf_batches/<first>_<last>_<n>.csv` | 02b:96-109 | first and last COMID + count | 30 d | `REFRESH=1` | no (new COMIDs give new names) | crash |
| 10 | `_shared/flow/daily_<site>.csv` | 02b:168-186 | site | 30 d | `REFRESH=1` | no | crash; an empty answer is cached as "no record" (C8) |
| 11 | `_shared/pct.gpkg` | 02c:52 | none (no cache) | - | - | no | crash; run_mid stops the area |
| 12 | `_shared/cache/trails_osm_<range>.json` | 02d:116 | name | 7 d | `REFRESH=1` | **yes, up to 7 d** | crash; **not atomic** (51) |
| 13 | `cache/trails_usgs_*, usfs_closed_roads_*, usfs_trails_v2_*, csp_routes_*, nps_trail_inventory_*` | 02d:145-148, 267-274 | name | 7 d | `REFRESH=1` | **yes, up to 7 d** | crash; empty answers not cached (56-57) |
| 14 | `cache/eaton_lines_*, eaton_areas_*` | 02d:275-276 | name | 1 d | `REFRESH=1` | yes, 1 d | crash |
| 15 | `_shared/closure_areas.gpkg` | 02d:298-300 | written only when not empty | none | delete | - | **stays after the closure ends** (C6) |
| 16 | `cache/access_osm_<range>.json` | 02e:48-61 | name | 7 d | `REFRESH=1` | **yes, up to 7 d** | crash |
| 17 | `cache/access_osm_cycleway_<range>.json` | 02e:63-68 | name | 7 d | `REFRESH=1` | **yes** | crash; not atomic (68) |
| 18 | `cache/cycleways_<range>.json` (same data as 17) | 08:104-118 | name | 7 d | `REFRESH=1` | **yes** | old copy used, one printed line; not atomic (114) |
| 19 | `_shared/wilderness.gpkg` + `.extent.json` | geomatch.py:53-88 | old extent contains the new one | none | delete | no | crash (KeyError on an error answer) |
| 20 | `_shared/osm_falls.json` | 02f:59-84, 200 | lon/lat box stored in the file | 7 d | **none** | no | old copy with a NOTE (says if it was for other boxes), else goes on without |
| 21 | `_shared/wikidata_falls.json`, `cdfw_pad.json`, `grsm_falls.json` | 02f:262, 282, 350 | box in file | 30 d | **none** | no | as 20 |
| 22 | `_national/gnis/*` | 02f:296-304 | file name | none | delete | n/a | NOTE, goes on without GNIS |
| 23 | `<range>/late_summer_ndvi_<year>.tif` + `.json` | 02g:72-130 | name + year | none ("kept once made") | delete | **yes, silent** (new strip has no greenness: no creek is lowered there) | crash; run_mid stops |
| 24 | `cache/trout_<key>.geojson` (also lakesources' `trout_lake_*`) | troutdata.py:74-95 | name (two include the year) | 7 d | `REFRESH=1` | **yes, up to 7 d** | crash, or source left out with a NOTE (`_try`, 343-350) |
| 25 | `<range>/canopy_tcc.tif` | 11:387-417 | name | 90 d | **none** | **yes, up to 90 d** (new strip NaN) | crash |
| 26 | `_shared/prism_tmean_aug.tif`; `_national/prism_tmean_aug_us.zip` | watertemp.py:94-120 | bounds contain the area; national file by name | none (a 30-year normal) | delete | no | crash, or hang (A9) |
| 27 | `cache/wqp_result_temp.csv`, `wqp_station_temp.csv` | watertemp.py:73-91; validate_heat.py:26-41 | name | 30 d | **none** | **yes, up to 30 d** | crash; run_late goes on with the last fit |
| 28 | `_shared/osm_major_roads.gpkg` + `.extent.json` | 09:20-47 | old extent contains boxes + home + 0.15 degrees | **none** | delete | no | crash; not atomic (46-47) |
| 29 | `output/<area>/road_closures.gpkg/.csv` | 07:576-583 | rebuilt every run; removed when empty | - | - | no | **old file stays and is used** (run_late.sh:19; 08:64; 09:58) |
| 30 | `output/<area>/context/*.gpkg`, `context_*.csv` | 11 | rebuilt every run (no cache: about 12 services each run) | - | - | no | crash; run_late stops the area |
| 31 | `_national/tl_2024_us_state.zip` | areaclip.py:28-32 | name | none | delete | n/a | crash |
| 32 | `cache/ny_<dataset>.json` | lakesources.py:290-311 | name | 7 d | `REFRESH=1` | yes | "lake source unavailable", goes on |
| 33 | `cache/osm_water.json`, `cache/gbif_salmonidae.csv` | 05d_lakes.py:630-631, 831-856 | name | 7 d | `REFRESH=1` | yes | (lakes auditor) |
| 34 | `cache/lidar_catalog.json`, `cache/lake_dem1m/*` | lakelidar.py:55-58; 05d:440 | name / window | 30 d / none | `REFRESH=1` | (lakes auditor) | - |
| 35 | `_national/nla/*.csv` | lakesources.py:40-54 | name | none | delete | n/a | returns a path that may not exist |
| 36 | bathymetry downloads | lake_bathymetry.py | name | none | delete | n/a | printed, lake left without |
| 37 | `_shared/flow/nf_gauges_full.csv` | data/validate_flow.py:41-51 | name | **none** | delete | - | crash |
| 38 | `cache/norwest.gpkg`, `streamcat_temp.csv` | data/validate_heat.py:44-67, 94-96 | name | 30 d | none | yes | crash |

### Findings

- **C1 CONFIRMED (latent). Sixteen cache families are keyed by a range or area name only,** so moving a box edge
  leaves the old extent in use with no message: rows 5 (with `OSM=keep` or during an outage), 6, 7, 8, 12, 13, 14,
  16, 17, 18, 23, 24, 25, 27, 32-33. Two expire never (6-8, 23), one after 90 days (25). The comment at 02b:67 says
  "re-download when ranges are added": a moved edge is not an added range. Only 02f's cache (20-21), the wilderness
  file (19), the PRISM clip (26) and the major roads (28) test the extent. **Checked today (2026-11-21, read-only):**
  for all 55 ranges of the 12 areas the DEM, canopy and NDVI rasters cover the configured box and every area's
  NHDPlus V2 table reaches its boxes' envelope; central_vt's caches were all refetched after its west edge moved
  (trails reach lon -73.45). So nothing stale is in use now; the hole is in the code.
- **C2 CONFIRMED. Caches that never expire:** NHD (3), NHDPlus V2 and its two companions (6-8), wilderness (19),
  GNIS's "current" file (22: new names never arrive), NDVI (23), the regional road network (28: roads added,
  closed or re-tagged in OSM after the first download never reach the drive graph, and a moved junction no longer
  joins the weekly local copy, which is matched on coordinates rounded to 0.1 m, 09:70-80), `nf_gauges_full.csv` (37).
- **C3 CONFIRMED. No force-refresh switch:** 02f's four caches (its `cached()` never reads `REFRESH`, 59-84), canopy
  (11:390), WQP (watertemp.py:76), and every never-expiring cache in C2. `REFRESH=1` works for 02b, 02d, 02e, 08,
  troutdata, lakesources, 05d, lakelidar.
- **C4 CONFIRMED. Fallbacks to an old copy.** With a line in the log: OSM per range (02:75-77), 02f (75-78, the best
  of them: date and whether it was for other boxes), cycleways (08:116), lakes (run_mid.sh:30). **With no warning
  where it is used:** road closures after a failed 07 (run_late.sh:19 says "continuing without fresh ones", but 08
  and 09 read whatever file is there, 08:64-67, 09:58-63; the map then prints the old "fetched" time, 06_map.py:1335,
  which is honest but easy to miss); `closure_areas.gpkg` (C6). None of this reaches the map.
- **C5 CONFIRMED. Steps that go on after a failed download.**
  Drivers: run_base.sh:19-20 and run_rebuild_a.sh:22-23 log "FAILED" and run the next step (so a failed DEM
  download for a grown box is followed by 03_hydrology on the old mosaic of the old extent); run_late.sh:19 (07),
  :23 (watertemp); run_mid.sh:27-31 (lakes). run_mid and run_late stop an area at other failures.
  Inside scripts: 02 (75-77), 02f (79, 307, 322-323), troutdata `_try` (343-350: NC, TN, GRSM, EBCI, NY), PFBC's
  service list (288-293: silent), 08 cycleways (115-118), 11's statistics (504-506) and CDEC (554-555: silent), 07's
  VDOT files (366-368), Blue Ridge page (403-404), Smokies (489-490), Cherokee (537-538), lakesources (88-94, 320,
  341). Seen once in the logs: central_vt was built on 2026-11-20 without Wikidata ("502 ... no earlier copy; going on
  without it", data/mid_central_vt.log:1677); the 11-21 run fetched it.
- **C6 CONFIRMED. `closure_areas.gpkg` outlives the closure.** 02d writes it only `if len(eaton_areas)` (298-300).
  When LA County empties its closure-area layer the file stays: 02e still marks every road whose middle lies in it
  "closed" (145-148), 08 flags rides there "fire closure" (177), and the map still draws the polygons
  (06_map.py:1357-1364), while 02d's own trails are open again (it uses the live layer, 293). Fix: write or delete.
- **C7 CONFIRMED. Code and config changes are not in any key.** The NHDPlus table's column list changed on
  2026-11-19 and the comment says "delete it" (02b:74-75); the wilderness file does not record whether
  `nys_forest_preserve` was on (geomatch.py:66-69); a changed field list in troutdata keeps the old file for 7 days.
  One cache name carries a hand-made version ("usfs_trails_v2", 02d:269).
- **C8 PLAUSIBLE. An empty answer is stored as a finding.** troutdata writes an empty collection when the id query
  returns no ids (81, 88) and keeps it 7 days; 02b writes an empty `daily_<site>.csv` when a batch comes back with no
  rows (176-183) and then drops the gauge for 30 days (189). A service hiccup that answers 200 with nothing would do
  it. (Error bodies are caught: troutdata.py:66.)
- **C9 CONFIRMED. The same download is cached twice:** cycleways per range by 02e (63-68) and by 08 (104-118); the
  two files are the same size on disk (central_vt: 120,710 / 768,207 / 121,520 bytes each).
- **C10 CONFIRMED. Overpass time-outs are accepted as complete answers and then cached.** An Overpass query that
  runs out of time answers HTTP 200 with a `remark` and whatever elements it had. No caller looks for `remark`
  (grep: none): geomatch.py:18, 02d:69, 02c:30-36, 09:36-45. The partial answer is then kept 7 days (02d, 02e, 02f)
  or for good (09). 02f's own docstring records such time-outs (186-188).

---

## D. Access times (08_hike.py, 09_drive.py, with 02d, 02e, 07)

### The model, as coded

**Start points ("park at").** Every 10 m cell on an OSM road that is not `highway=track`, not tagged
`access=private/no` or `motor_vehicle=no/private` (08:61-62), not a motorway or its ramps (101), not inside today's
full closures buffered 25 m (64-68), and whose road piece is joined, through shared OSM nodes, to a piece that comes
within 300 m of the box edge (74-88). The parking and trailhead layer from 02e is not used (grep: only 06_map reads
`parking_trailheads.gpkg`). The name shown is the nearest named drivable road within 300 m of the start cells, pooled
on a 250 m grid (357-365); 901 of Jackson's 6,103 published reach lines have no "park at".

**Walking.** Tobler's function averaged up and down: `0.5 (6 e^(-3.5|s+0.05|) + 6 e^(-3.5|-s+0.05|))` km/h (51-53).
On any cell touched by an OSM path or road of any kind, private ones included (98): Tobler at
`min(cell slope, 0.15)` (210), so 5.0 km/h on flat ground down to 3.6 km/h wherever the hillside is 15 % or steeper.
Off trail on a channel of 1 km2 or more: 45 % of Tobler at the cell's slope (2.3 km/h flat). Other ground: 30 %
(1.5 km/h flat, 0.9 at 20 %, 0.3 at 50 %). Off-trail cells steeper than 100 %: 0.05 km/h (212). Lake cells off any
path: 0.05 km/h (224-229). No-data: 0.001. Cost is minutes per cell, eight neighbours (231-235).

**Riding.** `18 / (1 + 12 x grade)` km/h x 1.0 paved, 0.7 dirt, 0.5 singletrack (218, 168); grade is the line's own
rise over 200 m from the DEM, capped at 25 % (184-213). A bike cell takes the faster of riding and walking (219);
all its minutes count as bike minutes (289). Ridden lines (130-161): today's closed segments, road pieces stranded
by closures, OSM roads with `access=no` or `motor_vehicle=no` and every OSM track that is not `access=private`,
02e's class "bike", every fire road of the trail layer, OSM cycleways, and trails 02d marks bike = "yes". Paths and
cycleways are cut at wilderness (162-164); roads are ridden through it and flagged.

**Barriers.** Lakes: yes, off paths. Rivers: none (D4). Private land: none on foot (D5). Wilderness: bike paths only.
Cliffs: over 45 degrees off trail. Box edges: the model stops there (D6).

**Outputs** (307-341). Per reach: `approach_min` = minutes to the cheapest point (sampled every 20 m), `bike_min`,
`walk_min` = the rest, `approach_med_min` and `bike_med_min` at the median point (the fish score uses these two,
scoring.py:297-298), `route_km`, the start cell. Drops: the nearer of top and pool. Lakes: the shore ring 7 m out.
The popup: "Drive N min (M mi) from <home> -> park at <road> -> bike N min on closed roads, fire roads or bike trails
(⚠ fire road: double-check bike access, N min of the ride: <why>) -> hike N min" (06_map.py:477-492).

**Driving** (09). Graph: OSM motorway..secondary from home to all boxes (cached for good) + each range's local roads
of the classes in the speed table; every vertex a node, joined on coordinates rounded to 0.1 m; undirected; today's
full closures cut out with a 25 m buffer (58-63). Edge time = length / class speed, x0.75 on a way longer than
500 m whose length is over 1.3 times its ends' distance (75). Home snaps to the nearest node (100). A trailhead snaps
to the nearest node within 400 m; else to the nearest reachable node within 2 km plus the gap at 25 km/h (150-167).
Road islands holding trailheads are joined across gaps up to 3 km at 25 km/h, up to four rounds (113-139).

### Constants

| Constant | Value | file:line | How chosen (as recorded) |
|---|---|---|---|
| `RES` | 10 m | config.py:10 | the DEM |
| Tobler 6, 3.5, 0.05 | - | 08_hike.py:53 | the published function |
| `TRAIL_MAX_GRADE` | 0.15 | 08:34 | "trails switchback" (docstring) |
| `CHANNEL_FACTOR` | 0.45 | 08:35 | "boulder-hopping, wading"; README:986 "guesses" |
| `OFFTRAIL_FACTOR` | 0.30 | 08:35 | "SoCal chaparral"; README:986 "guesses" |
| channel threshold | 1.0 km2 | 08:211 | not recorded |
| `CLIFF_SLOPE`, `CLIFF_KMH` | 1.0, 0.05 km/h | 08:36 | "nearly impassable" |
| no-data speed | 0.001 km/h | 08:221 | not recorded |
| `BIKE_FLAT_KMH`, `BIKE_GRADE_K` | 18, 12 | 08:37 | "~10 km/h at 6 %" |
| `DIRT_FACTOR`, `SINGLETRACK_FACTOR` | 0.7, 0.5 | 08:37 | not recorded |
| `BIKE_MAX_GRADE`, `GRADE_WINDOW_M` | 0.25, 200 m | 08:38 | West Fork Road: 1.4 % against the hillside's 30 % |
| line grade sampling; minimum run | 5 m; 50 m | 08:184, 202 | not recorded |
| `CHECK_MIN` | 1.0 min | 08:39 | "a crossing takes a few seconds" |
| `PAVED` surfaces | 9 values | 08:40 (copy of 02e:36) | - |
| `NO_BIKES` reasons | 6 strings | 08:41-42 | must match 02d's rule texts (bike_check gap a, below) |
| closure buffer | 25 m; 30 m for the ridden piece | 08:67, 135; 09:62 | not recorded |
| edge test for "joined to the outside" | 300 m | 08:81 | not recorded |
| bike layers clipped to | box + 2 km | 08:131, 133 | - |
| cycleway cache | 7 d | 08:109 | - |
| reach sampling | 20 m | 08:307 | - |
| lake shore ring | 7 m out, 5 m inside the box | 08:352-353 | - |
| trailhead grid; road name within | 250 m; 300 m | 08:359, 365 | - |
| `KMH` | motorway 100, link 60, trunk 80, link 50, primary 60, link 40, secondary 50, link 35, tertiary 45, unclassified 35, residential 30, service 15; other 30 | 09:14-15, 75 | "free-flow speeds by road class"; no source |
| `WINDING`, `WINDING_FACTOR`, minimum way length | 1.3, 0.75, 500 m | 09:16-17, 75 | not recorded |
| `SNAP_M` | 400 m | 09:18 | not recorded |
| `FAR_SNAP_M`, `GAP_KMH`, `BRIDGE_M`, rounds | 2000 m, 25 km/h, 3000 m, 4 | 09:116, 121 | Bautista Road (comment) |
| regional road pad | 0.15 degrees | 09:24-25 | - |
| node rounding | 0.1 m (09), 1 m (08), 0.1 m (07) | 09:70; 08:77; 07:70 | - |
| `MATCH_M`, `MATCH_SHARE` | 25 m, 0.6 | 02d:26-27; geomatch.py:114 | Gabrielino example |
| official-only trail: off OSM, length, median distance, same name within | 40 m, 400 m, 300 m, 150 m | 02d:203-213 | Gabrielino 80-90 m off its OSM line |
| relief window; `MIN_RELIEF_M` | 1 km; 100 / 50 / 30 m by area | 02d:233-246; config.py:187, 212, 292, 373 | per-area notes in config |
| parking near a trail; trailhead merge | 300 m; 150 m | 02e:178, 206 | - |
| closure look-ahead | 7 d | 07:36 | - |
| Caltrans routes | 18 routes; I-5 full closures only | 07:38-43 | mountain highways |
| minor-road routing cost | x3 | 07:69 | - |
| closure end-point snap; spot ring; route sanity | 150 m; 60 m; 3 x crow + 500 m | 07:80, 84, 90 | - |
| closure relief filter | 150 m within 1 km | 07:551-563 | "drops urban stretches"; not the area's `MIN_RELIEF_M` |
| Blue Ridge milepost match | 1.5 mi | 07:399 | - |
| gated road minimum | 300 m | 07:588 | - |

### Systematic biases

- **D1 CONFIRMED. Any drivable road cell is a place to park.** No parking, pull-out or shoulder test; `service` ways
  count and their sub-type is thrown away at download (02:94-95 keeps highway, name, access, motor_vehicle), so an
  untagged driveway or parking aisle is a start. Times run short where a road has nowhere to leave a car.
- **D2 CONFIRMED. No track is ever driven** (08:61-62 and 09:53-54 drop `highway=track`), though 02e knows which are
  open to cars from the Motor Vehicle Use Map (02e:113, 153). Places up an open forest road tagged as a track get a
  bike or walk leg instead; times run long there, and the remoteness score with them.
- **D3 CONFIRMED. Walking on a trail uses the hillside's slope, not the trail's grade.** `tobler(min(slope, 0.15))`
  (08:210) reads the cell gradient; the line's own grade is worked out only for bike lines (208-213). A level trail
  or road benched into a steep wall walks at 3.6 km/h instead of 5.0 (40 % long); a trail that climbs straight up at
  30 % also walks at 3.6 where Tobler gives 2.1 (40 % short). The code fixed exactly this for bikes (West Fork Road,
  docstring 17-19). README:579 says "use the trail grade".
- **D4 CONFIRMED. Rivers are not barriers, and a channel is faster than the ground beside it.** Every cell draining
  1 km2 or more walks at 45 % of Tobler whatever the river's size (08:210-211); other ground at 30 %. A route fords
  the Snake, the Chattahoochee or the Hudson in two or three cells. Only lakes are closed (224-229). Scenario: a
  side creek on the far bank of a river with the road on the near bank is "reached" in minutes.
- **D5 CONFIRMED. Private land and closed trails cost nothing on foot.** `on_path` is every OSM path and road,
  private ones too (98); off-trail travel ignores ownership; the trail layer's `closed` flags and the fire closure
  areas are read only for the bike flags (172-178). In the mostly private areas (se_pa, ne_ct) a printed "hike N min"
  may cross yards and posted land.
- **D6 CONFIRMED. Each box is routed alone.** The cost surface is the range's own DEM (08:44) and nothing joins boxes
  afterwards (grep: no approach or hike code in crossbox.py or 03b). A reach near an edge whose nearest road lies in
  the next box is timed from a road in its own box. Same for the sun horizon (E1).
- **D7 CONFIRMED. Raster shortcuts.** Lines are burned with `all_touched=True` (96): switchback legs under about
  20 m apart merge, a road on a bridge joins the creek under it, and a trail on the far side of a narrow gorge joins
  the road. README:923-925 measured routes 8-13 % short of the Park Service's trail distances in Jackson.
- **D8 CONFIRMED. One off-trail factor for every landscape.** 0.30 was set for chaparral (08:7, 35) and has no
  per-area value (grep config.py). Open eastern hardwoods are faster, Adirondack blowdown and spruce slower.
- **D9 CONFIRMED (code and published maps). Access times are a snapshot of the build day's closures, winter closures
  included.** 08:66 and 09:60 cut every "full closure" that is "active now"; the `long_term` column 07 computes is
  read by nothing. On the maps published 2026-11-21: Jackson has Teton Park Road, Jenny Lake Loop, Moose-Wilson Road,
  Signal Mountain Summit Road, Mormon Row, North Park Road and Grassy Lake Road cut "indefinite" (the park's winter
  closure, 07:277-285), and Cascade Creek reads "Drive 49 min (37 mi) -> park at Teton Park Road -> bike 57 min on
  closed roads ... -> hike 213 min"; 47 % of Jackson's reach lines have a bike leg. The Smokies have Parson Branch,
  Rich Mountain, Heintooga Ridge, Balsam Mountain and Straight Fork roads cut until 2027-05-01; central_vt a town
  highway until 2027-05-14; Lexington the Parkway at milepost 61.4-66.3. The closures layer is dated ("fetched ..."),
  the access line is not. The same rule cuts a four-hour Caltrans night closure if the build runs during it, and LA
  County closures whose own reopening date passed months ago (published: "Marathon | 06 30 26", "Cave Way | 11 09 26",
  "Mint Canyon Road | 11 20 26"; 07:163-171 notes it in the reason and still closes the road).
- **D10 CONFIRMED. A closure the router cannot place becomes a straight line, and the straight line is cut out of
  the network.** `route()` returns `LineString([p, q])` when an end is over 150 m from a road vertex, no path exists
  or the path is over 3 x the distance (07:80-90); only one end has to be on the map (115). 08 and 09 then remove
  every road within 25 m of that line: the roads it happens to cross, not the closed road.
- **D11 CONFIRMED. Trails the map draws from official data are not trails to the router.** 02d adds named official
  trails missing from OSM (198-221, "official only"); 08 walks on `osm_trails.gpkg` and `osm_roads.gpkg` from 02
  (59-60, 98) and never reads the trail layer's geometry for walking. Those trails are crossed at off-trail speed.
- **D12 PLAUSIBLE, one published example. Drive times: class speeds without a source, and several things left out.**
  No one-way streets (the tag is downloaded, 09:43, and unused), no turns, signals or traffic, no `maxspeed`.
  Motorways at 100 km/h are slower than rural interstates; primaries at 60 km/h are slower than a 55 mph highway;
  city streets with no stops are faster than life. Published Jackson: "Cottonwood Creek -> Drive 39 min (17 mi)",
  26 mph over a trip that is mostly US 89 at 55 mph. North Georgia's medians (92-115 min to the mountain boxes) look
  right. The winding test is per OSM way, so the same road is slowed or not by how mappers split it.
- **D13 CONFIRMED. A trailhead snaps to the nearest vertex of any road,** a freeway's included, within 400 m (09:118,
  158); vertices, not points along a segment, so a trailhead in the middle of a long straight piece can fall to the
  2 km rule and gain a 25 km/h gap.
- **D14 CONFIRMED. `drive_approx` is never shown.** 09:167 writes it; nothing reads it (grep; scoring.py:115-116
  merges only id, road, minutes, km, position). README:602 says such times "are flagged approximate". n_georgia has
  17 of them, per its log.
- **D15 CONFIRMED. Closures off the map or on gentle ground do not exist for the drive.** 07 keeps a closure only if
  it touches the boxes + 2 km (47, 115, 252) and has 150 m of relief within 1 km or is a park road (551-563). A closed
  road between home and the mountains is driven.
- **D16 CONFIRMED. Closure times are printed in the build computer's time zone, with no zone named.**
  `datetime.fromtimestamp` and `datetime.now()` are local (07:35, 108-110, 176, 266, 327). The builds run on Eastern
  time (logs against published gauge times), so LA's Caltrans windows read three hours late.
- **D17 CONFIRMED. `route_km` and the flags describe the route to the cheapest point; the score uses the median
  point** (08:316-340). A reach can be flagged for a ride its typical approach does not make, or the reverse.

### bike_check: does the code keep the owner's rule?

Rule: every fire road is ridden; doubtful bike access is flagged, never dropped; the timing stays.

Kept: all fire roads of the trail layer are ridden whatever their bike status (08:141, 159), in wilderness too
(162-164 cuts only paths); four reasons are flagged when the route spends a minute or more on such cells (171-179,
331): wilderness, posted no bikes, fire closure, closed or private in OSM. The popup says so (06_map.py:487-490).

Not kept:
- **(a) CONFIRMED. Fire roads that carry the Appalachian Trail or the Long Trail are ridden with no flag.** 02d gives
  them bike = "no" with the reasons "Appalachian Trail: no bikes" and "Long Trail: foot travel only" (328-329);
  08's `NO_BIKES` lists six reasons and not these two (41-42), and no other test catches them.
- **(b) CONFIRMED. Closed or gated roads that are not tracks are ridden with no flag even where bikes are barred.**
  They come from `osm_roads.gpkg`, which never had the `bicycle` tag (02:94-95; 08:134-137). 02e drops such roads
  from its "bike" class (156), but 08 takes them from the raw file anyway. The "posted" flag is built from fire roads
  only (176). Same for today's closed segments and stranded pieces: a road shut by a fire or storm order is ridden,
  and only the drop popup carries the general "some closure orders ban all entry" line (06_map.py:1274-1276).
- **(c) CONFIRMED. Tracks tagged `access=private` are dropped from riding** unless 02d kept them (walking allowed, or
  a gated USFS road: 02d:248-249; 08:136-137). By design (08 docstring, 13), but it is "dropped, not flagged".
- **(d) PLAUSIBLE. Fire roads inside national parks get "fire road outside wilderness: yes"** (02d:342); the park
  rule in 02d covers trails only (323, 340). Parks allow bikes on roads open to cars and on named routes only.
- **(e) CONFIRMED (minor). The one-minute test is per reason** (08:331): 0.6 min in wilderness plus 0.6 min posted is
  not flagged, though the total (`dsum[-1]`) is worked out.

---

## E. Sun, canopy, air temperature and context (10_sun.py, 11_context.py)

**Sun (10).** Date 2026-07-15, day 196 (14). Declination by Cooper's formula (30). Solar time, 04:00-20:00 in
10-minute steps (16, 31-32). One latitude per box: its south-west corner (26). Horizon: 36 directions, rays to 3 km
in 30 m steps, nearest cell, eye 1 m above the DEM (15, 18, 45-58); samples past the raster are ignored (54-57).
The sun counts when its altitude clears the horizon, interpolated between directions (60-71). Four points per reach,
averaged (19, 84-95); a drop at its pool (88). `shade_pct` = 100 x (1 - sun hours / flat-horizon day length) (97).
`northness` = mean of cos(aspect) x sin(slope) over a 2 km square (17, 39-43, 74). The aspect formula is right.

**Canopy (11:385-438).** USFS NLCD tree canopy cover, 30 m, the service's last time step (392, 404), nearest
neighbour, tiled; per reach the mean of 3 x 3 cell means at points every 30 m (about 45 m either side).

**Air (11:226-245; watertemp.py:93-120).** PRISM 1991-2020 August mean, 30 arc-seconds, nearest cell at points every
200 m along the reach. File on disk: `prism_tmean_us_30s_202008_avg_30y` (checked).

**Fires (11:76-146).** Since 2016 (31). CAL FIRE in LA, NIFC history elsewhere; this year's from WFIGS (wildfires of
10 acres or more); else the outline of a BAER severity map. Severity weights 0.15 / 0.4 / 0.75 / 1.0 (101, no
source given). Debris-flow hazard for fires of the last 4 years (145). Reach buffers: 30 m; drops 60 m (618).

**Gauges (11:440-567).** Latest discharge of gauges that reported in 183 days; percentiles for today's month-day;
status by the usual five classes (529-540).

Data vintages: DEM as served on the download day; NHD frozen 2023; NHDPlus V2 (EROM means 1971-2000); OSM at most
7 days old except the regional roads (never refreshed); PRISM 1991-2020; canopy year **not recorded anywhere**;
Sentinel-2 summers 2022-2024 (flowlib.py:460); GNIS current file of 2026-11-19 plus the 2021 archive; TIGER 2024;
Vermont stocking list 2021; Tennessee samples 1996-2022; park trout map mostly 2014 and 2018; CT samples since 2000;
WQP since 1995.

Findings:

- **E1 CONFIRMED. Sun hours lean high in four ways, and the popup says none of them.** Trees are left out (docstring:
  "an upper bound"); ridges beyond 3 km are not seen (the Tetons stand 5-10 km west of the valley floor and take
  about an hour of evening sun); within 3 km of a box edge the terrain past the edge is missing (D6); the first
  sample is 30 m out, so a gorge narrower than that is open sky. The popup prints `"{h:.1f} h direct sun mid-July
  ({p:.0f}% shaded by terrain)"` (06_map.py:965): tenths of an hour and whole per cents from 10-minute steps and
  10-degree directions.
- **E2 CONFIRMED. A point on no-data gets full sun** (10:55-57: all rays NaN, horizon -90 degrees).
- **E3 CONFIRMED. Northness is a 2 km square,** not "within 1 km of the channel" in the round (17, 74), and is
  smeared at box edges (`mode="nearest"`).
- **E4 CONFIRMED. The canopy's year is unknown to the build.** It asks for the service's last time step and stores
  neither the year nor a sidecar (11:392-417). scoring.py:40-41 says "latest year" and README:611 adds "so the
  2024-25 fires show": true only if the service's last year is 2025. PLAUSIBLE that it is not (the national product has run
  about two years behind). The cache is 90 days by range name with no extent test and no force switch (C1, C3).
- **E5 CONFIRMED. "August air averages N °F"** (06_map.py:968) is one 800 m cell value per 200 m of reach from a
  normal that ends in 2020; in a canyon the cell's mean elevation can sit hundreds of metres above the creek. The water estimate
  beside it carries its error ("± x °F", 06_map.py:674); the air figure does not.
- **E6 CONFIRMED (code and published maps). Gauge times are Pacific on every map, and the layer is called "live".**
  11:479 converts every reading to America/Los_Angeles; the popup prints "N cfs at 2026-11-21 17:35" with no zone
  (06_map.py:1415). Published central_vt: latest readings 17:15-17:35 while that build ran at 20:41 Eastern, so they
  are three hours off for Vermont (and one for Jackson). The layer title is "(live, 2026-11-21)" and the popup says
  "% of median for today" (06_map.py:1412, 1416); the pages do not fetch anything, so both mean the build day.
- **E7 CONFIRMED. A failed statistics request turns into "no history".** 11:504-506 prints and breaks; the gauges of
  that batch (20 at a time) keep NaN percentiles and `rel()` returns "no history" (531-532), which the map shows as
  a fact about the gauge.
- **E8 CONFIRMED. Fire acres are added up across duplicate perimeters** outside California: the NIFC history is
  dissolved by name and year with `acres: "sum"` (11:95), while this year's perimeters use `"max"` (110). The
  history layer holds one fire several times (PLAUSIBLE, from the layer's own description); the tooltip shows
  the sum as "Acres" (06_map.py:1382).
- **E9 CONFIRMED. A reach takes a trout designation by touching it.** The reach's 30 m buffer against lines buffered
  25 m (troutdata.py:114), any intersection, no minimum share (11:590-596). The lowest reach of every side creek
  ends on the main stem's line, so it carries the main stem's designation ("Class A wild trout stream: Valley
  Creek") and the x1.2. The comment at 592-593 knows the neighbour's line clips the reach; the sort only chooses
  between designations, it does not drop a slight one.
- **E10 CONFIRMED. A record counts for every creek of the same name within 5 km** (trout found, or any record in
  California) or 1.5 km (no trout, elsewhere) (11:349-368), with no test that the two are one stream. "Mill Creek"
  is on Delaware's stocked list (cached data): any other Mill Creek within 5 km of its middle is stocked too.
- **E11 PLAUSIBLE. A CDFW survey with nothing in its species field reads as "no trout found".** `fillna("")`, then
  `found = contains("trout")` (11:253-258). Published LA: 118 label occurrences are a bare "no trout found" (the
  field was empty or "None", the label cannot tell which) and 4 name another species. These carry x0.5 (G3).
- **E12 CONFIRMED. iNaturalist:** a sighting with no stated accuracy passes the 500 m test (`or 0`, 11:291); the
  query stops without a word at 10,000 per species (277).
- **E13 PLAUSIBLE. 11's ArcGIS pager stops on any short page** (11:70: `len(batch) < page or not exceeded`). A
  server whose own limit is under 1,000 answers short with `exceededTransferLimit: true` and the loop ends there.
  The two other pagers use the safe form (geomatch.py:47; 02d:97). Whether any of 11's twelve services has such a
  limit I could not check.
- **E14 PLAUSIBLE. A gauge with two discharge series keeps whichever comes first** (11:482: sorted by site only,
  then `drop_duplicates`). 02b's own note says such gauges exist (154-157).
- **E15 CONFIRMED. Fires are merged by title-cased name and year** (11:94-95): two fires of one name in one year
  become one. Rare.
- **E16 CONFIRMED. `trout_found` means "found, stocked or sighted", and undated stocking lists are stamped with the
  build year** (G5). The reach popup shows the labels, which are worded honestly; the score reads the year.

---

## F. Known waterfalls (02f_known_falls.py)

Per source:

| Source | What is taken | precise | Placement rank | Naming rank | Cache |
|---|---|---|---|---|---|
| OSM falls, node | `waterway=waterfall` or `natural=waterfall` (226-231) | yes | 0 | 1 | 7 d |
| OSM falls, way or area | same; centre of the bounding box | yes if under 100 m across | 3 | 1 | |
| OSM rapids (named) | `waterway=rapids` (232-236) | as above | 0 / 3 | 1 | |
| OSM other named features | swimming places, parks, attractions, waters named for falls; under 400 m; not a business or road (173-182, 207-244); must be on a stream (162-169: 60 m from an NHD line, not within 20 m of a lake) | no | 6 | 1 | |
| NHD points, FType 487 | 247-252 | yes | 2 | 3 | from 02 |
| CDFW barrier surveys | natural barriers; notes saying it is gone are skipped (257-275) | yes | 2 | 3 | 30 d |
| NPS (Smokies) | unrestricted rows (277-292) | yes if the stated accuracy is under 14 m | 2 / 4 | 2 | 30 d |
| GNIS Falls, Rapids | current file + 2021 archive (294-332) | no | 5 | 2 | for good |
| Wikidata | waterfall, rapids, swimming hole classes (335-361) | no | 7 | 4 | 30 d |
| curated CSVs | 363-393 | as the row says | 1 if precise, else 4 | 0 | - |

Merge rules: inside one source, the same word set within 150 m, or two unnamed points within 15 m, become one
(404-423). Across sources, pairs within 2 km, best first (430-463): same name (one word set inside the other, and
the extra words not among upper / lower / little / numbers, 111-120) within 500 m, or the identical word set within
2 km; an unnamed point within 100 m of a named one; any two within 25 m. A cluster never takes two points of one
source, nor two different names unless within 25 m. Kept: the best-placed point's position and `precise`, the
best-ranked name, all sources' labels, all notes, the first URL (465-484). Points over 300 m outside the boxes are
dropped (55, 397).

Curated files: 328 + 695 rows; 316 of the 328 have coordinates, 14 use `replaces`, 3 are `drop` rows; 112 are
marked precise, and all 695 Georgia rows.

Findings:

- **F1 CONFIRMED. The `precise` flag is given by source type, not measured.** Every OSM falls node, every NHD point
  and every CDFW survey point is precise (228, 252, 274). Precise falls may overrule 05_score's artifact tests within
  50 m (docstring 28-30). No test compares a point with the channel.
- **F2 CONFIRMED (measured, small). OSM falls nodes that still sit on a GNIS coordinate:** 29 of 1,205 nodes in the
  12 areas' cached files are within 15 m of the GNIS position (Sturtevant Falls, Laurel Falls, Grotto Falls, Rainbow
  Falls, Raquette Falls ...). They are marked precise and outrank everything; GNIS itself is not precise. Some of
  the 29 may simply be right.
- **F3 CONFIRMED. A dam mapped as a line is stored as its first vertex.** 02_download_vectors.py:83 takes
  `el["geometry"][0]` for a way. A long dam's point then lies at one abutment: 05_score.py:314-315 records Buford
  Dam's "mapped point is 506 m off". The fix belongs here (keep the line, or the point of it nearest the channel),
  not in the tests downstream that measure distance to a dam point (05_score.py:311; 05d_lakes.py:508-522).
- **F4 CONFIRMED. A road drawn on the dam's own way is lost.** Any element whose `waterway` matches dam or weir goes
  to the dams and `continue`s (02:82-86), so a way tagged both `highway` and `waterway=dam` never reaches the road
  list; 08 and 09 then have a gap at the dam.
- **F5 CONFIRMED. No force switch, and GNIS is never refreshed** (C2, C3).
- **F6 CONFIRMED. The step goes on without a source that fails** and the map gives no sign (C5); seen once.
- **F7 PLAUSIBLE. The 2 km same-name rule can swallow a second fall** where one source lists only fall A and
  another only fall B of the same name ("High Falls", "Twin Falls") within 2 km.
- **F8 CONFIRMED. States per area are a hand-kept table** (45-49); an area missing from it gets a NOTE and no GNIS.
  All 12 are listed.
- **F9 CONFIRMED. Wikidata is asked once, with no retry** (345-347); the cache's fallback covers it.
- **F10 CONFIRMED. `known_falls_points.gpkg` and the `n_src` column are written for checking and read by nothing.**
- **F11. Terms:** see B3-B6.

---

## G. Trout evidence (troutdata.py, with 11_context.py and scoring.py)

How a record reaches the score: `waters()` polygons give a reach `trout_water` (11:590-596). `evidence()` points give
`trout_found` (latest year of any record with trout: survey, stocking or sighting) and `trout_absent` (latest year
of a survey without trout) (11:372-374). scoring.py:189-199: found within 10 years and not older than the latest
no-trout survey: **x1.2**; else a no-trout survey within 10 years: **x0.5**; else a designation: **x1.2**.

| State / source | Becomes | Class | Notes |
|---|---|---|---|
| CA: CDFW (11:217, 251-272) | waters; surveys (found or not); stocking in the last 365 d | wild / none / stocked | E11 |
| CT DEEP (133-174) | samples since 2000, latest with and latest without trout per station; stocking in the last 365 d; management areas | found / **none** / stocked / designated | species names tell wild from stocked; both count as found |
| Vermont (179-194) | brook trout catchments ("Wild brook trout water", "Mixed wild trout water"); the 2021 stocking list | wild (broad) / stocked 2021 | cached values: only those two |
| Virginia (199-216) | classes I-IV "Wild trout stream"; stocking plan | wild / stocked, year = build year | V-VIII left out |
| Georgia (221-247) | designated streams; stocking in the last 365 d; this year's sampling with fish | designated / stocked / found | zero-fish rows dropped |
| Wyoming (252-265) | guide streams with trout, not "Clear"; CuttslamRivers as "Native ... cutthroat water" | wild | G2 |
| Idaho (270-276) | StreamNet Yellowstone cutthroat rows compiled by IDFG | wild | G11 |
| Pennsylvania (296-325) | Class A; natural reproduction; trout special regulations; newest stocked sections; stocked lakes | wild / designated / stocked | G8 |
| Delaware (330-340) | designated trout streams | stocked, year = build year; designated | |
| North Carolina (368-397) | Public Mountain Trout Waters by class; blanket game-land rule left out | designated; stocked (two classes), year = build year | |
| Tennessee (404-448) | stocking sites; wade-site samples (found or not); brook trout genetics | stocked, year = build year / found / **none** | G3 |
| Smokies park (455-468) | species per segment, codes 1-7 | wild | G7 |
| Cherokee (475-486) | two fishing zones | designated | |
| New York (493-528) | DEC reaches by category; class (T) / (TS) waters; fishing access easements | wild / stocked, year = build year / designated | B1, G6 |
| Trout Unlimited (534-556) | patches by trout community | wild (broad) | G1 |

Findings:

- **G1 CONFIRMED (code and cached data). One trout-community value falls through the list and is labelled as brook
  trout water.** The code drops "No trout documented" and "Brook trout predicted" (543), names "Brown trout only"
  and "Rainbow trout only" as "Wild trout patch" (554-556), and calls everything else "Wild brook trout patch".
  adk_southwest's cached layer has 3 patches valued **"Brown & rainbow trout only"**: they become "Wild brook trout
  patch (EBTJV / Trout Unlimited): Brown & rainbow trout only". Same family as the earlier New York bug: the code
  lists what to leave out, so any new value is brook trout by default. Listing what to keep would end it. The factor
  is x1.2 either way; the label is wrong.
- **G2 CONFIRMED (code and cached data). Five Wyoming streams the state classes "Clear (No trout present)" are
  labelled native cutthroat water.** Every CuttslamRivers line becomes "Native Snake River Cutthroat water (WGFD)"
  (262-264) without a look at the fishing guide. In Jackson's cached layers 5 "Clear" guide streams (28 km: Indian
  Creek South Fork, Box Creek, Cabin Creek, Table Creek West, Cabin Creek South; game fish "None") lie on Cuttslam
  lines. They get the label and x1.2. (160 guide streams are "Clear"; the code rightly leaves those out of the
  guide's own labels, 258.)
- **G3 CONFIRMED. "No trout" records lower a score, by half, in three areas; the module says one.** scoring.py:194-199
  gives x0.5. The records come from CDFW surveys (LA), CT DEEP samples (ne_ct) and TWRA samples (smokies:
  troutdata.py:418-438). troutdata's docstring says "only ... (CT). Nothing else here lowers a score" (43-44) and
  scoring's says "CDFW survey" (53-55). Cached data: CT 435 station-years without trout of 1,659; Tennessee 100 of
  144, 33 of them from 2016 on (the ones still inside the 10-year window). A record speaks for the same-named creek
  within 5 km in California and 1.5 km elsewhere (11:361).
- **G4 CONFIRMED. The half comes before the designation.** `np.select([pos, neg, trout_water.notna()], [1.2, 0.5,
  1.2])` (scoring.py:199): a reach inside a Wild Trout Management Area, a Class A stream or a brook trout patch that
  also has one no-trout sample nearby gets x0.5. The heat gate and the channel rule treat a designation as trout
  (scoring.py:211, 220); this factor does not. Against "only penalise when near-certain": a designation plus one
  empty sample is not near-certain absence. How many reaches: for the scoring auditor to count.
- **G5 CONFIRMED. Undated stocking lists are stamped with the build year,** `THIS_YEAR` (55): Virginia (213), PFBC
  lakes (323), Delaware (335), North Carolina (384, 395), Tennessee (417), New York (511). So their x1.2 never ages
  out and always beats a later no-trout survey (`found >= absent`, scoring.py:193). Vermont's list is honestly
  2021 (192) and keeps its x1.2 until 2031. All in the direction of keeping water in.
- **G6 CONFIRMED. New York:** fishing-rights easements go in as trout water (525-527: "Public fishing access on a
  trout stream") and so earn x1.2 for access, not for fish; DEC categories other than Wild-Quality and Stocked* get
  the bare label "Trout stream" (503-505; the cache has one "Other"); all three layers are DEC ArcGIS (B1).
- **G7 PLAUSIBLE. The park's uncertified segments count like certified ones:** 270 of the 1,828 kept segments are
  marked "Raw" (463 drops only "Invalid"). The species meanings of codes 1-7 are typed in with no source (464-465);
  the cached counts (1: 659, 2: 453, 4: 398, 5: 262, 7: 48, 6: 8, no 3) fit the table as written.
- **G8 CONFIRMED. Pennsylvania's stocked sections vanish without a word if one request fails.** `_pfbc_stocked`
  returns `(None, None)` on any error (288-291: one try, 60 s) and `_pa` then uses an empty layer (312). No NOTE.
- **G9 PLAUSIBLE. Connecticut's "2 other species" can include crayfish:** the species count runs over every row of
  the station-year, bycatch rows too (149; sample types in the cache: 945 crayfish bycatch rows).
- **G10 CONFIRMED (cosmetic). Two raw codes reach the map:** Georgia's "TGT" (tiger trout) prints as "tgt" on two
  streams (239-244); Virginia's "FF" prints as "(FF)" on Wilson Creek (209-215).
- **G11 CONFIRMED (latent). Idaho's use type is downloaded and not tested** (272); every cached row is "Year-round
  use", so nothing is wrong today.
- **G12 CONFIRMED. A source that is down is dropped for that build even with a week-old copy on disk.** `fetch`
  never falls back to an expired cache (79-90); `_try` then leaves the source out with a NOTE (343-350). Opposite
  to 02f, which keeps the old copy.
- **G13 CONFIRMED. The "no trout" test for Tennessee has no sample-type check** (431) where Connecticut's has (149);
  the layer is all wade-site electrofishing, so it holds today.

---

## H. Duplicates, dead code, validators

### H1. The same logic written more than once

| # | What | Places | Lines saved if merged |
|---|---|---|---|
| 1 | Overpass call with retries and two mirrors | geomatch.py:10-23; **02d_trails.py:61-74 (identical)**; 02c_pct.py:25-36; 09_drive.py:31-41 | about 33 (and one place for the `remark` test, C10) |
| 2 | ArcGIS paging | geomatch.py:26-50; **02d_trails.py:77-100 (identical but for `where`)**; 11_context.py:46-74; troutdata.py:62-95; data/validate_heat.py:44-58; no paging at all in 07:140-154, 246-252 and geomatch.py:70-73 | 24 at once; about 50 more with one pager (troutdata's ids-then-features is the sturdiest) |
| 3 | Download-with-cache | 02d:41-58; 02f:59-84; 02b:34-36; 02e:48-61, 63-68; 08:104-118; troutdata.py:77-90; lakesources.py:290-311; 05d:631, 832; lakelidar.py:58; 11:389-391; watertemp.py:73-79 = data/validate_heat.py:26-31; extent sidecars 09:26-28, geomatch.py:66-69; range sidecars 02b:67-68, flowlib.py:159-160, 313-314 | 60-80; one helper with 02f's rules (box-keyed, atomic, old copy with a NOTE) would also close C1, C3 |
| 4 | Relief within 1 km | geomatch.py:91-111; **02d_trails.py:224-242 (identical)**; a third form in 07:551-563 | 19 |
| 5 | `follow()` line matching | geomatch.py:114-134; **02d_trails.py:160-180 (identical)** | 21 |
| 6 | `stack()` | 02d:149-154; 02e:90-95 | 6 |
| 7 | Cycleway download | 02e:62-68; 08:104-127 | about 15, and one Overpass call per range |
| 8 | Three Overpass downloads of the same roads and paths per range | 02:56-62 (4 tags kept); 02d:116-120; 02e:52-58 | one download with all tags would feed 02d, 02e, 05, 07, 08, 09 and end D11 and bike_check (b) |
| 9 | WZDx feed | 07:325-341 (Vermont); 07:342-358 (Idaho), the same 14 lines | 14 |
| 10 | HTML table cell cleaner | 07:390, 477, 516 | 4 |
| 11 | PRISM sampling `air_at` | 11:229-235; watertemp.py:123-128; data/validate_heat.py:86-90 | 12 |
| 12 | WQP download | watertemp.py:81-91; data/validate_heat.py:34-41 | 8 |
| 13 | USGS `get` with rate-limit waits | 02b:42-62; 11:446-466 | about 18 |
| 14 | "Newest yearly service" | troutdata.py:285-293; 357-365 | 7 |
| 15 | Sample -> trout / no trout | troutdata.py:138-157 (CT); 421-438 (TN) | about 12 |
| 16 | PAD-US download | 11:175-187; 05d_lakes.py:1036 | one download |
| 17 | Area lon/lat box | every file, with buffers of 0 (02d, 02e, 08), 300 m (02f), 2 km (02b, 07, flowlib), 3 km (troutdata, 11, watertemp, 05d) | about 15, as `config.area_bounds(buffer)` |
| 18 | `PAVED` surface set | 02e:36; 08:40 | 1 |
| 19 | `LAKE` name pattern | troutdata.py:53; 11:249 | 1 |
| 20 | User-Agent header | 14 places (A12) | 13 |
| 21 | Closure reading | 08:64-67; 09:58-62 | 4 |

02d already imports from geomatch (line 24); rows 1, 2, 4 and 5 there are pure copies: 78 lines.

### H2. Dead code and dead outputs (each checked by grep over `scripts/` and `data/`)

1. `data/derived/<area>/<range>/hike_minutes.tif`: written every run, a full raster per range (08:376-378); read
   by nothing.
2. `drive_approx` (09:167): read by nothing (D14).
3. `long_term` (07:134, 171, 181, 191, 239, 264): written to the closures file; read by nothing.
4. `burn_count` (11:579): read by nothing.
5. Gauge columns `years`, `p10`, `p25`, `p75`, `p90` (11:526-528): used inside 11 for the status only; the map
   reads `p50`.
6. `n_src` and `known_falls_points.gpkg` (02f:484, 489-490).
7. `osm_waterfalls.gpkg` (02:98): read only as 02f's last resort (203-206).
8. `oneway` on the regional roads (09:43): never used.
9. `xs, ys` (09:67): assigned, never used.
10. `relief_at(..., root)` (geomatch.py:91): the `root` argument is unused; callers pass `ROOT` (02e:159, 179).
11. `__import__("os")` at 02e:146, 174 with `os` already imported (29).
12. Unused imports: 02 `json`, `time` (2); 02b `np` (19); 02d `ROOT` (23); 02g `raw_dir` (25); 07 `json` (28), `ROOT`
    (31); 08 `Point` (30); 09 `ROOT` (12); 11 `glob`, `urllib.request` (21), `from_bounds` (23), `ROOT`, `SHARED` (26);
    troutdata `io` (47).
13. Tags downloaded and never used: 02d's `operator`, `horse`, `tracktype`, `motor_vehicle` (28-29).
14. `_ev(..., url=None)` (troutdata.py:104): no caller sets it.
15. `Designation_Boundary=None` (troutdata.py:118): filled only by CDFW's layer.
16. `relief_m` (07:562): kept in the file, shown nowhere.
17. `road_closures.csv` (07:579): written, read by no script (an export).

### H3. Are the validators runnable against today's layout? (static check: every path they read is still written,
every name they import still exists)

| Script | Reads | Written by | Verdict |
|---|---|---|---|
| data/validate.py | `output/<area>/<range>/known_falls.gpkg`; `knickpoints.gpkg`, `knickpoints_bigcreek.gpkg`, `area_km2.tif` | 05_score.py:397-398; 04, 04b; 03b | runnable (reloads `config` per range; that also makes folders) |
| data/validate_flow.py | `flow/nhdplus_v2.gpkg`, `gauge_sites.gpkg`, `gauges_daily.csv.gz`, each range's `nhd_flowlines.gpkg`; `flowlib.below_dam_comids`, `match_points` | 02b; 02; flowlib.py:106, 341 | runnable; **California only in effect** (asks TNC's API for every gauge COMID, no `has("tnc_flows")` guard); its own download never expires (C2) |
| data/validate_flow_areas.py | the same + `natural_flows.csv`; `FLOWING_CFS` | 02b:230-231; flowlib.py:369 | runnable |
| data/validate_heat.py | WQP caches (shared with watertemp), `nhdplus_v2.gpkg`, `output/<area>/context/trout_evidence.gpkg`; `scoring.HEAT_START`, `HEAT_FULL`, `watertemp.air_tif` | 11:324; scoring.py:135; watertemp.py:94 | runnable in the West; NorWeST covers no eastern area, so it stops on an empty layer there (PLAUSIBLE) |
| data/check_flow_drops.py | `streams_scored.gpkg`, `flow_streams.csv` (dry_cfs, water_class, flow_src), `area_streams.csv`, `flowdir.tif`; `flowpath.CODES`, `FLOWING_CFS` | 05_score; 05b_flow.py:474-491; 05c_drainages.py:558; 03b; flowpath.py:5 | runnable |

validate_heat.py repeats watertemp's cache helper, WQP call and `air_at` while already importing watertemp (H1 rows
3, 11, 12).

### H4. Docstrings and comments that no longer match the code

1. 02d:18, 02e:26: "Writes data/raw/_shared/..." (it is `data/raw/<area>/_shared`).
2. 09:1 and README:599: "from HOME (config.py, ZIP 90404)" (each area has its own).
3. 11:19: "Writes output/context/*.gpkg and output/<region>/..." (both under `output/<area>/`); 10:9 likewise.
4. 11:338-339: "latest CDFW survey year that found none" (also CT and Tennessee).
5. troutdata.py:43-44: no-trout records "only ... (CT)" (also Tennessee, 418-419).
6. troutdata.py:561: "a reach's label is the first that covers it" (it is the one covering most, 11:592-596).
7. scoring.py:53-55: the trout factor described as CDFW only.
8. 07:3-26: the source list stops at the Blue Ridge Parkway; NCDOT, TDOT, the Smokies and the Cherokee NF are coded
   (406-539).
9. README:579: walking "use[s] the trail grade" (D3).
10. README:602: approximate drive times "are flagged" (D14).
11. geomatch.py:1: "02d_trails.py has its own copies".

---

## I. Bugs and accuracy risks, each with a failure scenario

Ordered by how much they change what the map says.

1. **CONFIRMED. Winter road closures are baked into the published access times** (07:277-285, 475-488 -> 08:64-68;
   09:58-63). Built on 2026-11-21, Jackson's map sends Cascade Creek's angler by bike for 57 minutes up a road that
   is open to cars from May. See D9.
2. **CONFIRMED. NYSDEC ArcGIS data is still published** (troutdata.py:490-527; geomatch.py:76). See B1, B2.
3. **CONFIRMED. A no-trout sample halves a designated trout water** (scoring.py:199). A Connecticut brook in a Wild
   Trout Management Area, electrofished once in a warm August with no trout in the net within 1.5 km, scores half.
   See G3, G4.
4. **CONFIRMED. Overpass time-outs pass as complete** (geomatch.py:18; 02d:69; 02c:30; 09:36). On a slow evening the
   road query for a box returns two thirds of its ways with a `remark`; `osm_roads.gpkg` is written; 08 strands the
   roads beyond the gap and turns them into bike roads; 09 routes around. Nothing in the log. See C10.
5. **CONFIRMED. Gauge times are Pacific everywhere and unlabelled; closure times are the build computer's**
   (11:479; 07:108-110). A Vermont gauge read at 08:35 prints "05:35". See E6, D16.
6. **CONFIRMED. A closure that cannot be routed is cut as a straight line** (07:80-90). A Caltrans closure of SR-2
   with one end off the map becomes a line across the range; every road it crosses loses 50 m and SR-2 stays open.
   See D10.
7. **CONFIRMED. `closure_areas.gpkg` survives the closure** (02d:298-300; 02e:145-148; 06_map.py:1357). The day LA
   County lifts the Eaton closure area, roads inside stay "closed" and the polygon stays on the map. See C6.
8. **CONFIRMED. Stale closures after a failed 07** (run_late.sh:19; 08:64). Caltrans's server is down at build time;
   last week's closures are cut out again; the map shows last week's "fetched" time. See C4.
9. **CONFIRMED. Trout labels by default** (troutdata.py:543-556; 262-264). "Wild brook trout patch: Brown & rainbow
   trout only" (3 patches); "Native Snake River Cutthroat water" on 5 streams the state says hold no trout. See G1, G2.
10. **CONFIRMED. A side creek's lowest reach inherits the main stem's designation** (11:590-596). An unnamed
    tributary of a Class A stream is labelled Class A and gets x1.2. See E9.
11. **CONFIRMED. Rivers can be forded anywhere at 2.3 km/h** (08:210-211). See D4.
12. **CONFIRMED. Walking speed on trails follows the hillside, not the trail** (08:210). See D3.
13. **CONFIRMED. Range-name caches after a box-edge move** (C1). Move a box's west edge 5 km and run within the
    week: trails, access roads, trout layers and canopy stop at the old edge; NHDPlus V2 and the NDVI rasters stop
    there until someone deletes them.
14. **CONFIRMED. Fire roads on the Appalachian Trail and Long Trail are ridden unflagged; gated non-track roads with
    `bicycle=no` likewise** (08:41-42, 134-137, 176). See D bike_check (a), (b).
15. **CONFIRMED. Official-only trails are bushwhacks to the router** (08:59-60, 98). See D11.
16. **CONFIRMED. A dam's point is its line's first vertex** (02:83). See F3.
17. **CONFIRMED. `drive_approx` never reaches the map** (09:167). See D14.
18. **CONFIRMED. The regional road network is never refreshed** (09:26-28). A highway realigned in OSM after the
    first download keeps its old line in the graph for good, and its junctions no longer meet the weekly local copy.
19. **CONFIRMED. A failed statistics request reads "no history"** (11:504-506, 531-532). See E7.
20. **CONFIRMED. Pennsylvania's stocked sections can vanish silently** (troutdata.py:288-293, 312). See G8.
21. **CONFIRMED. Fire acres summed over duplicate perimeters** (11:95 against 110). See E8.
22. **CONFIRMED. The yearly flow index outside California uses every "ST*" gauge, canals and dam tailwaters
    included** (02b:149-150, 203-216); flowlib's `PLUMBING` filter (flowlib.py:465-468) is not applied. In Jackson
    the Snake below its two dams and the valley's canals vote on how dry the year was for headwater creeks. The
    median softens it. PLAUSIBLE in effect.
23. **PLAUSIBLE. Blank species field read as "no trout found"** (11:253-258). See E11.
24. **PLAUSIBLE. 11's pager truncates on a server limit under 1,000** (11:70). See E13.
25. **PLAUSIBLE. A blocked or error page from nps.gov or fs.usda.gov reads as "nothing closed"** (07:387, 476, 515:
    `.text` with no status test). The Parkway is then open in the model.
26. **CONFIRMED (low odds). Downloads written in place:** an interrupted NHD download or extraction leaves a broken
    file that the next run tries to use (02:21-31); the JSON caches of 02d:51, 02e:68, 08:114 and the regional roads
    (09:46-47) likewise.

Checked and found fine: no WaterServices caller (A1); cache extents today (C1); iNaturalist's cutthroat query still
returns Jackson's cutthroat (published: 178 Snake River fine-spotted and 48 Yellowstone labels); Georgia's rows
with no species have no fish and are dropped; Vermont's trout status has only two values, both trout; the sun's
aspect and azimuth formulas; the five gauge classes; PRISM's file is the 1991-2020 normal.
