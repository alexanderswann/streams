"""Access roads, parking and trailheads for the maps, for all study areas. No REGION needed; run after 02d_trails.py.

Roads: OSM highway = primary ... unclassified and track, cycleways (paved roads closed to cars, like the West Fork
Road below Cogswell Dam, are often mapped as cycleways), plus residential / service ways tagged unpaved, in mountain
terrain (at least MIN_RELIEF_M of relief within 1 km) or on USFS roads. Each goes in one class by what it takes to
get up it, from OSM tags and the USFS road layers (maintenance level; open to the public or admin only):
  paved            any car
  graded           graded dirt or gravel; a car is fine when dry (OSM tracktype grade1-2 or gravel / compacted
                   surface; USFS maintenance level 3+)
  high_clearance   rough dirt (OSM tracktype grade3-4, smoothness bad or very bad; USFS level 2)
  closed           closed by a current fire closure (LA County's Eaton Fire layer and closure areas)
  4wd              very rough, 4WD only (OSM 4wd_only=yes, tracktype grade5, smoothness horrible or worse)
  bike             closed to cars but open to bikes (and on foot): OSM motor_vehicle / motorcar = no, access = no
                   with bicycles allowed, or USFS roads closed to the public. Not in wilderness (no bikes there).
  dirt             dirt road with no condition data
Left out: private roads (unless bicycles are allowed), roads closed to bikes (bicycle = no, or closed roads in
wilderness), driveways, parking aisles and other service minutiae.

Parking: OSM amenity=parking that is public, in mountain terrain or within 300 m of a trail.
Trailheads: OSM highway=trailhead, USFS recreation sites of type trailhead, and USFS recreation opportunities marked
"Trailhead" (with the forest's page link); points within 150 m of each other are merged, official names first.

Where a road is on the USFS Motor Vehicle Use Map, its official designation decides the class (open to passenger
vehicles: paved or graded; high-clearance only: high_clearance) and its open dates are kept.

Writes data/raw/_shared/access_roads.gpkg and data/raw/_shared/parking_trailheads.gpkg (EPSG:4326).
Map attribution: (c) OpenStreetMap contributors (ODbL), USFS.
"""
import os, re, html, json, time, numpy as np, pandas as pd, geopandas as gpd, shapely
from config import REGIONS, CRS, ROOT, SHARED, has, MIN_RELIEF_M
from geomatch import overpass, esri, relief_at, follow, wilderness_path
import netfetch

EDW = "https://apps.fs.usda.gov/arcx/rest/services/EDW"
TAGS = ["name", "ref", "highway", "service", "surface", "tracktype", "smoothness", "4wd_only", "access",
        "motor_vehicle", "motorcar", "bicycle", "foot", "seasonal", "access:conditional"]
PAVED = {"paved", "asphalt", "concrete", "concrete:plates", "chipseal", "paving_stones", "sett", "metal", "wood"}
UNPAVED = {"unpaved", "gravel", "fine_gravel", "compacted", "dirt", "earth", "ground", "grass", "sand", "rock",
           "pebblestone", "mud", "woodchips"}
SERVICE_SKIP = {"driveway", "parking_aisle", "drive-through", "alley", "emergency_access"}
NO = {"no", "private", "agricultural", "forestry", "delivery"}
OK = {"yes", "permissive", "designated"}

boxes = {k: gpd.GeoSeries([shapely.box(*r["bbox"])], crs=CRS).to_crs(4326).total_bounds for k, r in REGIONS.items()}

# ---- OSM ----
roads, pts = {}, {}
for key, (W, S, E, N) in boxes.items():
    cache_p = f"{SHARED}/cache/access_osm_{key}.json"   # a week-long cache (REFRESH=1 to force a new download)
    if os.path.exists(cache_p) and time.time() - os.path.getmtime(cache_p) < 7 * 86400 and os.environ.get("REFRESH") != "1":
        els = json.load(open(cache_p))
    else:   # written only after a download: re-saving a cached copy made it look new, so it never turned a week old
        def dl(S=S, W=W, N=N, E=E):
            els = overpass(f"""[out:json][timeout:600];
(way["highway"~"^(primary|secondary|tertiary|unclassified|track)$"]({S},{W},{N},{E});
 way["highway"~"^(residential|service)$"]["surface"~"^(unpaved|gravel|fine_gravel|compacted|dirt|earth|ground|sand|rock)$"]({S},{W},{N},{E});
 way["highway"~"^(residential|service)$"]["tracktype"]({S},{W},{N},{E}););
out geom;
(nwr["amenity"="parking"]({S},{W},{N},{E}); node["highway"="trailhead"]({S},{W},{N},{E}););
out center tags;""")
            os.makedirs(f"{SHARED}/cache", exist_ok=True)
            json.dump(els, open(cache_p + ".tmp", "w"))
            os.replace(cache_p + ".tmp", cache_p)
            return els
        # (when Overpass can't be reached the older download stays, with a dated NOTE: netfetch.keep_old)
        els = netfetch.keep_old(cache_p, dl, f"OSM roads and parking ({key})")
        els = json.load(open(cache_p)) if els is None else els
    # cycleways: a separate query (and cache) so the big one above stays cached
    cyc_p = f"{SHARED}/cache/access_osm_cycleway_{key}.json"
    if os.path.exists(cyc_p) and time.time() - os.path.getmtime(cyc_p) < 7 * 86400 and os.environ.get("REFRESH") != "1":
        cyc = json.load(open(cyc_p))
    else:
        def dl_cyc(S=S, W=W, N=N, E=E):
            cyc = overpass(f'[out:json][timeout:300];way["highway"="cycleway"]({S},{W},{N},{E});out geom;')
            json.dump(cyc, open(cyc_p + ".tmp", "w"))
            os.replace(cyc_p + ".tmp", cyc_p)
            return cyc
        cyc = netfetch.keep_old(cyc_p, dl_cyc, f"OSM cycleways ({key})")
        cyc = json.load(open(cyc_p)) if cyc is None else cyc
    els = els + cyc
    for e in els:
        t = e.get("tags", {})
        if e["type"] == "way" and "geometry" in e and t.get("highway") in (
                "primary", "secondary", "tertiary", "unclassified", "residential", "service", "track", "cycleway"):
            if len(e["geometry"]) >= 2:
                roads[e["id"]] = dict(osm_id=e["id"], **{k: t.get(k) for k in TAGS},
                                      geometry=shapely.LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
        else:
            c = e.get("center") or ({"lon": e["lon"], "lat": e["lat"]} if "lon" in e else None)
            if c:
                kind = "trailhead" if t.get("highway") == "trailhead" else "parking"
                pts[(e["type"], e["id"])] = dict(kind=kind, name=t.get("name"), access=t.get("access"),
                                                 fee=t.get("fee"), capacity=t.get("capacity"), url=None, note=None,
                                                 source="OSM", geometry=shapely.Point(c["lon"], c["lat"]))
    print(f"{REGIONS[key]['label']}: {len(roads)} road ways, {len(pts)} parking / trailhead points so far")

rd = gpd.GeoDataFrame(list(roads.values()), crs=4326).to_crs(CRS).reset_index(drop=True)
rd = rd[~rd.service.isin(SERVICE_SKIP)].reset_index(drop=True)

# ---- USFS roads: open to the public (layer 0) and closed to the public (layer 1) ----
def stack(parts, key):
    parts = [p for p in parts if len(p)]
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs=CRS)
    return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326).pipe(lambda d: d.drop_duplicates(key) if key in d else d[~d.geometry.to_wkb().duplicated()]).to_crs(CRS) \
        .reset_index(drop=True)
fields = "objectid,id,name,oper_maint_level,surface_type,openforuseto"
fs_open = stack([esri(f"{EDW}/EDW_RoadBasic_01/MapServer/0", bb, fields) for bb in boxes.values()], "objectid")
fs_closed = stack([esri(f"{EDW}/EDW_RoadBasic_01/MapServer/1", bb, fields) for bb in boxes.values()], "objectid")
print(f"USFS roads: {len(fs_open)} open, {len(fs_closed)} closed to the public")
# USFS Motor Vehicle Use Map: the official designation of which vehicles may use each forest road, and when
mv_fields = ("objectid,id,name,mvum_symbol_name,surfacetype,seasonal,passengervehicle,passengervehicle_datesopen,"
             "highclearancevehicle,highclearancevehicle_datesopen")
mvum = stack([esri(f"{EDW}/EDW_MVUM_02/MapServer/1", bb, mv_fields) for bb in boxes.values()], "objectid")
print(f"MVUM roads: {len(mvum)}")
m_open, m_closed = follow(rd, fs_open), follow(rd, fs_closed)
pick = lambda df, m, c: [df[c].iat[i] if i >= 0 else None for i in m]
rd["fs_id"] = [a or b for a, b in zip(pick(fs_open, m_open, "id"), pick(fs_closed, m_closed, "id"))]
rd["fs_level"] = pd.to_numeric(pd.Series(pick(fs_open, m_open, "oper_maint_level")).str[:1], errors="coerce").values
rd["fs_surface"] = pick(fs_open, m_open, "surface_type")
rd["fs_closed"] = (m_closed >= 0) | pd.Series(pick(fs_open, m_open, "openforuseto")).eq("ADMIN").values
m_mv = follow(rd, mvum)
mvcol = lambda c: pd.Series(pick(mvum, m_mv, c) if c in mvum else [None] * len(rd), index=rd.index)
mv_car, mv_hc = mvcol("passengervehicle").eq("open"), mvcol("highclearancevehicle").eq("open")
rd["mvum"] = mvcol("mvum_symbol_name")
dates = lambda v: v if isinstance(v, str) and v.strip() else None
rd["open_dates"] = [("cars " + a) if dates(a) else ("high-clearance " + b) if dates(b) else None
                    for a, b in zip(mvcol("passengervehicle_datesopen"), mvcol("highclearancevehicle_datesopen"))]
rd["fs_id"] = rd.fs_id.fillna(mvcol("id"))

# ---- classify ----
surf = rd.surface.fillna("")
fs_paved = rd.fs_surface.fillna("").str.match(r"^(AC|BST|PCC|P)\b")
unpaved = surf.isin(UNPAVED) | (rd.highway == "track") & ~surf.isin(PAVED) | rd.tracktype.notna() & ~surf.isin(PAVED) \
    | rd.fs_surface.fillna("").str.match(r"^(NAT|AGG|IMP)\b")
paved = ~unpaved & (surf.isin(PAVED) | fs_paved | (rd.highway != "track") & (surf == ""))
closed_cars = rd.motor_vehicle.isin(NO) | rd.motorcar.isin(NO) | \
    (rd.access.isin({"no", "private"}) & ~rd.motor_vehicle.isin(OK)) | rd.fs_closed | \
    rd.highway.eq("cycleway") & ~rd.motor_vehicle.isin(OK)              # cycleways are closed to cars by default
bikes_barred = rd.bicycle.isin({"no", "private", "dismount"})
private = rd.access.eq("private") & ~rd.bicycle.isin(OK) & rd.fs_id.isna()
wild = gpd.read_file(wilderness_path()).to_crs(CRS).union_all()   # downloaded here if 08_hike.py hasn't yet
in_wild = rd.geometry.interpolate(0.5, normalized=True).within(wild)
smooth = rd.smoothness.fillna("")
four = rd["4wd_only"].eq("yes") | rd.tracktype.eq("grade5") | smooth.isin({"horrible", "very_horrible", "impassable"})
high = rd.tracktype.isin({"grade3", "grade4"}) | smooth.isin({"bad", "very_bad"}) | rd.fs_level.eq(2)
graded = rd.tracktype.isin({"grade1", "grade2"}) | surf.isin({"gravel", "fine_gravel", "compacted"}) | rd.fs_level.ge(3)
# the Motor Vehicle Use Map designation wins on forest roads it covers; OSM tags and USFS levels decide elsewhere
mv_paved = mvcol("surfacetype").fillna("").str.match(r"^(AC|BST|PCC|P)\b")
# current fire closures (LA County's Eaton Fire layer: roads closed, or closed to vehicles only; closure areas written
# by 02d_trails.py): closed roads go in their own class, roads closed to vehicles only are bike roads
LAC_ = "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Eaton_Fire_Impacted_Trails_and_Roads_WFL1/FeatureServer"
eaton = (stack([esri(f"{LAC_}/14", bb, "OBJECTID,Name,Status,Line_Type") for bb in boxes.values()], "OBJECTID")
         if has("la_trail_layers") else [])
e_status = pd.Series(pick(eaton, follow(rd, eaton), "Status") if len(eaton) else [None] * len(rd), index=rd.index).fillna("")
areas_p = f"{SHARED}/closure_areas.gpkg"
areas = gpd.read_file(areas_p).to_crs(CRS).union_all() if __import__("os").path.exists(areas_p) else shapely.Polygon()
in_area = rd.geometry.interpolate(0.5, normalized=True).within(areas)
fire_closed = e_status.eq("Closed") | in_area
rd["closed_why"] = np.where(e_status.eq("Closed"), "Eaton Fire closure (LA County / USFS)",
                            np.where(in_area, "inside the Eaton Fire closure area",
                                     np.where(e_status.eq("Closed Vehicles"), "Eaton Fire: closed to vehicles", None)))
closed_cars = closed_cars | e_status.eq("Closed Vehicles")
rd["cls"] = np.select([fire_closed, mv_car & mv_paved, mv_car, mv_hc, closed_cars, paved, four, high, graded],
                      ["closed", "paved", "graded", "high_clearance", "bike", "paved", "4wd", "high_clearance", "graded"],
                      "dirt")
drop = private | (rd.cls.eq("bike") & (bikes_barred | in_wild)) | \
    (rd.cls.eq("paved") & rd.highway.isin({"residential", "service"}))   # town streets: the basemap has them
rd = rd[~drop].copy()
rel = relief_at(rd.geometry.interpolate(0.5, normalized=True), REGIONS, ROOT)
rd = rd[(rel >= MIN_RELIEF_M) | rd.fs_id.notna()].copy()
rd["name"] = rd["name"].fillna(rd.fs_id.map(lambda v: f"USFS road {v}" if isinstance(v, str) else None))
rd = rd.rename(columns={"access:conditional": "access_conditional"})
cols = ["osm_id", "name", "ref", "highway", "cls", "surface", "tracktype", "smoothness", "fs_id", "fs_level", "seasonal",
        "access_conditional", "mvum", "open_dates", "closed_why", "geometry"]
rd[[c for c in cols if c in rd]].to_crs(4326).to_file(f"{SHARED}/access_roads.tmp.gpkg")
os.replace(f"{SHARED}/access_roads.tmp.gpkg", f"{SHARED}/access_roads.gpkg")    # 08_hike.py may be reading it
km = rd.length / 1000
print("access roads:", len(rd), "ways,", round(km.sum()), "km | km by class:",
      km.groupby(rd.cls.values).sum().round().to_dict())

# ---- parking and trailheads ----
p = gpd.GeoDataFrame(list(pts.values()), crs=4326).to_crs(CRS)
trails_p = f"{SHARED}/trails.gpkg"
trail_lines = gpd.read_file(trails_p).to_crs(CRS) if __import__("os").path.exists(trails_p) else gpd.GeoDataFrame(geometry=[], crs=CRS)
near_trail = np.zeros(len(p), bool)
if len(trail_lines):
    tt = shapely.STRtree(trail_lines.geometry.values)
    near_trail[np.unique(tt.query(p.geometry.values, predicate="dwithin", distance=300)[0])] = True
prel = relief_at(p.geometry, REGIONS, ROOT)
p = p[((prel >= MIN_RELIEF_M) | near_trail | (p.kind == "trailhead")) & ~p.access.isin({"private", "no", "customers"})]

strip = lambda s: re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s)))).strip()[:300] if s else None
th_parts = []
for bb in boxes.values():
    a = esri(f"{EDW}/EDW_RecreationOpportunities_01/MapServer/0", bb,
             "recareaname,recareaurl,markeractivity,recareadescription,forestname,openstatus,restrictions",
             where="markeractivity='Trailhead'")
    if len(a):
        th_parts.append(gpd.GeoDataFrame(dict(kind="trailhead", name=a.recareaname, url=a.recareaurl,
                                              note=a.recareadescription.map(strip), source="USFS", rank_=0,
                                              status=a.get("openstatus"), restrict=a.get("restrictions")),
                                         geometry=a.geometry, crs=4326))
    b = esri(f"{EDW}/EDW_InfraRecreationSites_01/MapServer/0", bb, "site_name,site_subtype,development_status",
             where="site_subtype='TRAILHEAD' AND development_status='EXISTING'")
    if len(b):
        th_parts.append(gpd.GeoDataFrame(dict(kind="trailhead", name=b.site_name.str.title(), url=None, note=None,
                                              source="USFS", rank_=1), geometry=b.geometry, crs=4326))
fs_th = gpd.GeoDataFrame(pd.concat(th_parts, ignore_index=True), crs=4326).to_crs(CRS) if th_parts else \
    gpd.GeoDataFrame(geometry=[], crs=CRS)
# merge: official trailheads first (recreation pages before the sites list), then OSM trailheads, then parking; a
# point within 150 m of one already kept adds its name / url / note if those are missing and is otherwise dropped
allp = pd.concat([fs_th.sort_values("rank_") if len(fs_th) else fs_th,
                  p[p.kind == "trailhead"], p[p.kind == "parking"]], ignore_index=True)
kept = []
for r in allp.itertuples():
    hit = next((k for k in kept if k["geometry"].distance(r.geometry) < 150 and (k["kind"] == r.kind or r.kind == "parking")), None)
    if hit is None:
        kept.append(dict(kind=r.kind, name=r.name if isinstance(r.name, str) else None, url=r.url, note=r.note,
                         fee=getattr(r, "fee", None), capacity=getattr(r, "capacity", None), source=r.source,
                         status=getattr(r, "status", None) if isinstance(getattr(r, "status", None), str) else None,
                         parking=r.kind == "parking", geometry=r.geometry))
    else:
        hit["name"] = hit["name"] or (r.name if isinstance(r.name, str) else None)
        hit["url"] = hit["url"] or r.url
        hit["note"] = hit["note"] or r.note
        st = getattr(r, "status", None)
        hit["status"] = hit.get("status") or (st if isinstance(st, str) else None)
        if r.kind == "parking":
            hit["parking"] = True
            hit["fee"] = hit.get("fee") or getattr(r, "fee", None)
            hit["capacity"] = hit.get("capacity") or getattr(r, "capacity", None)
pt = gpd.GeoDataFrame(kept, crs=CRS)
pt.to_crs(4326).to_file(f"{SHARED}/parking_trailheads.gpkg")
print("trailheads:", int((pt.kind == "trailhead").sum()), "(with parking", int(((pt.kind == "trailhead") & pt.parking).sum()),
      ") | parking lots:", int((pt.kind == "parking").sum()))
