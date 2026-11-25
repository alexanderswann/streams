"""Hiking trails and fire roads for the maps, for all study areas. No REGION needed.

Base geometry is OpenStreetMap: ways tagged highway=path / bridleway / footway / steps and highway=cycleway (trails; a bike path
is a trail unless OSM names it a road, which 02e_access.py draws as a road closed to cars) and highway=track (fire
roads, truck trails), with the tags that matter for hiking and the names of the route=hiking relations they belong to.
Official data enriches it (both public domain):
  - USGS National Digital Trails (USFS, NPS, State Parks and county trails in one service): official name, trail
    number, managing agency and allowed uses for OSM ways that follow an official trail; named official trails missing
    from OSM are added.
  - USFS roads closed to public vehicles (EDW RoadBasic, layer 1): fire roads gated to cars but open to walking.
Dropped: sidewalks and other footway=* street furniture; ways on flat ground (under MIN_RELIEF_M of relief within 1 km) unless they are named,
part of a hiking route or an official trail, or run along a creek or lake the map draws (trailrules.py); private or
no-access fire roads unless walking is allowed or they are USFS roads. Official water trails (canoe and paddle routes)
are not walking trails: they name no OSM way, and the pieces OSM lacks stay in the layer only for the parking test (a lot
by a river's put-in), undrawn. A sidepath (an unnamed footway, path or bike path beside a car road: trailrules.py) stays
in the layer for the approach times and the parking test, undrawn too (the basemap draws its road): `undrawn`.
Unnamed OSM paths that follow no official trail or hiking route are flagged "possibly unofficial" (use trails,
firebreaks); the maps draw them dotted and only up close.
Each way gets a rank, used by the maps to reveal detail with zoom:
  1 hiking route or named trail, 2 named fire road, 3 unnamed trail, 4 unnamed fire road or possibly unofficial path.

Writes data/raw/_shared/trails.gpkg (EPSG:4326). Needs every region's DEM (01_download_dem.py) for the relief test.
Map attribution: trails and fire roads (c) OpenStreetMap contributors (ODbL), USGS National Digital Trails, USFS.
"""
import os, re, time, requests, numpy as np, pandas as pd, geopandas as gpd, rasterio, shapely
from scipy.ndimage import maximum_filter, minimum_filter
from config import REGIONS, CRS, ROOT, SHARED, raw_dir, has, MIN_RELIEF_M
from geomatch import wilderness_path
import trailrules

MATCH_M = 25            # an OSM way follows an official line if most of it lies within this distance
MATCH_SHARE = 0.6
TAGS = ["name", "ref", "highway", "footway", "sac_scale", "mtb:scale", "trail_visibility", "informal", "surface", "access", "foot",
        "bicycle", "horse", "motor_vehicle", "operator", "tracktype", "is_sidepath"]
STREET = {"sidewalk", "crossing", "traffic_island", "access_aisle", "link", "alley"}
WALK_OK = {"yes", "designated", "permissive"}
UA = {"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"}
USGS = "https://partnerships.nationalmap.gov/arcgis/rest/services/USGSTrails/MapServer/0"
USFS_CLOSED_ROADS = "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RoadBasic_01/MapServer/1"
# downloads are cached for a week (REFRESH=1 to force), so re-runs skip the slow public servers
CACHE = f"{SHARED}/cache"
CACHE_DAYS = 7
os.makedirs(CACHE, exist_ok=True)


def cached(name, fetch, days=CACHE_DAYS):
    """fetch() result cached as JSON (OSM elements) or GeoJSON (GeoDataFrame) under data/raw/_shared/cache. Written
    through a temporary file, and only from a whole answer (an empty one too); when a refresh fails, the earlier copy
    is used (with a dated NOTE, netfetch.keep_old)."""
    import json
    import netfetch
    path = f"{CACHE}/{name}"
    fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < days * 86400 \
        and os.environ.get("REFRESH") != "1"
    if name.endswith(".json"):
        if fresh:
            return json.load(open(path))
        def refresh():
            out = fetch()
            json.dump(out, open(path + ".tmp", "w"))
            os.replace(path + ".tmp", path)
            return out
        out = netfetch.keep_old(path, refresh, f"{name} (trails)")
        return json.load(open(path)) if out is None else out
    if fresh:
        return gpd.read_file(path)
    def refresh_gj():      # an empty answer is kept too (no closed USFS roads in NE Connecticut's box): it is the
        out = fetch()      # box's last good copy, and without one the step can't run offline
        out.to_file(path + ".tmp", driver="GeoJSON")
        os.replace(path + ".tmp", path)
        return out
    out = netfetch.keep_old(path, refresh_gj, f"{name} (trails)") if os.path.exists(path) else refresh_gj()
    return gpd.read_file(path) if out is None else out


def overpass(q):
    """An Overpass query's elements (netfetch.overpass: the mirrors in turn; a timed-out answer is not taken)."""
    import netfetch
    return netfetch.overpass(q)


import netfetch


def esri_lines(url, bbox, fields):
    """All features of an ArcGIS layer in a lon/lat box, paging through the server's record limit."""
    feats, off = [], 0
    while True:
        for attempt in range(4):
            try:
                r = netfetch.get(f"{url}/query", headers=UA, timeout=300, params=dict(
                    where="1=1", geometry=",".join(map(str, bbox)), geometryType="esriGeometryEnvelope", inSR=4326,
                    spatialRel="esriSpatialRelIntersects", outFields=fields, outSR=4326, f="geojson",
                    resultOffset=off, resultRecordCount=1000))
                js = r.json()
                if "features" in js:
                    break
            except (requests.RequestException, ValueError):
                js = {}
            if attempt < 3:
                netfetch.wait(10 * (attempt + 1), url)
        if "features" not in js:    # a server that is down is not a layer with nothing in the box: stop, don't return less
            raise RuntimeError(f"{url}: no usable answer after 4 tries ({str(js)[:200]})")
        batch = js["features"]
        feats += [f for f in batch if f.get("geometry")]
        if len(batch) < 1000 and not js.get("properties", {}).get("exceededTransferLimit"):
            break
        off += len(batch)
    return gpd.GeoDataFrame.from_features(feats, crs=4326) if feats else gpd.GeoDataFrame(geometry=[], crs=4326)


def norm(s):
    """Name for comparing: lower case, no punctuation or trail / road / fork words."""
    s = re.sub(r"[^a-z0-9 ]", " ", str(s).lower())
    return " ".join(w for w in s.split() if w not in {"trail", "tr", "road", "rd", "motorway", "fire", "truck", "the",
                                                       "national", "recreation", "nrt", "fork", "spur", "connector"})


# ---- OSM ----
ways, route_of = {}, {}
boxes = {}
for key, reg in REGIONS.items():
    box = gpd.GeoSeries([shapely.box(*reg["bbox"])], crs=CRS).to_crs(4326)
    W, S, E, N = boxes[key] = box.total_bounds   # all four corners, so the lon/lat box covers the whole UTM box
    els = cached(f"trails_osm_{key}.json", lambda: overpass(f"""[out:json][timeout:600];
way["highway"~"^(path|footway|bridleway|track|steps)$"]({S},{W},{N},{E})->.w;
.w out geom;
rel(bw.w)["route"~"^(hiking|foot)$"];
out body;"""))
    n0 = len(ways)
    for e in els:
        if e["type"] == "way" and "geometry" in e and len(e["geometry"]) >= 2:
            t = e.get("tags", {})
            ways[e["id"]] = dict(osm_id=e["id"], **{k: t.get(k) for k in TAGS},
                                 geometry=shapely.LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
        elif e["type"] == "relation":
            nm = e.get("tags", {}).get("name")
            if nm:
                for m in e.get("members", []):
                    if m["type"] == "way":
                        route_of.setdefault(m["ref"], set()).add(nm)
    # bike paths: the download 02e_access.py reads too (one copy, trailrules.cycleway_elements). A bike path OSM names
    # as a road (Old Pass Road, Mount Hollywood Drive: a paved road closed to cars) is left to the road layer
    n1 = len(ways)
    for e in trailrules.cycleway_elements(key, (W, S, E, N)):
        t = e.get("tags", {})
        if e["type"] == "way" and "geometry" in e and len(e["geometry"]) >= 2 and e["id"] not in ways \
                and not re.search(trailrules.ROAD_NAME, t.get("name") or "", re.I):
            ways[e["id"]] = dict(osm_id=e["id"], **{k: t.get(k) for k in TAGS},
                                 geometry=shapely.LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
    print(f"{reg['label']}: {n1 - n0} OSM ways, {len(ways) - n1} bike paths")

g = gpd.GeoDataFrame(list(ways.values()), crs=4326)
g["route"] = [", ".join(sorted(route_of.get(i, ()))) or None for i in g.osm_id]
g = g[~g.footway.isin(STREET)]
gu = g.to_crs(CRS).reset_index(drop=True)
gu["kind"] = np.where(gu.highway == "track", "fire road", "trail")
gu["source"] = "OSM"

# ---- official lines (regions' lon/lat boxes overlap a little, so de-duplicate on the services' own ids) ----
off_parts, gated_parts = [], []
for key, bb in boxes.items():
    off_parts.append(cached(f"trails_usgs_{key}.geojson", lambda: esri_lines(
        USGS, bb, "permanentidentifier,name,trailnumber,sourceoriginator,hikerpedestrian,bicycle,packsaddle,trailtype")))
    gated_parts.append(cached(f"usfs_closed_roads_{key}.geojson", lambda: esri_lines(
        USFS_CLOSED_ROADS, bb, "objectid,id,name,openforuseto")))
def stack(parts, key):
    parts = [p for p in parts if len(p)]
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs=CRS)
    out = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326)
    return out.pipe(lambda d: d.drop_duplicates(key) if key in d else d[~d.geometry.to_wkb().duplicated()]).to_crs(CRS).reset_index(drop=True)
off = stack(off_parts, "permanentidentifier")
gated = stack(gated_parts, "objectid")
# official water trails (canoe and paddle routes down a river: the Chattooga River and Toccoa canoe trails, the
# Schuylkill River and Tidal Delaware water trails) are no walking trails: an OSM path along the bank doesn't take their
# name, and they add no line. NDT's trail type says so; a copy saved before the type was asked for (2026-11-25) goes by
# the name ("... canoe trail", "... water trail"; a canoe carry or portage is a trail on land and stays). They stay in
# the list the ways are matched against, so a way between two land trails takes the one it took before
water = np.zeros(len(off), bool)
if len(off):
    water = (off.get("trailtype", pd.Series(None, index=off.index)).eq("Water Trail") | off["name"].fillna("").str.contains(
        r"\b(?:canoe|paddl\w*|kayak\w*|water)\s+(?:trail|route|way)\b|\bblueway\b", case=False)).values
    print(f"official water trails left out: {int(water.sum())} lines, {round(off.length[water].sum() / 1000)} km")
print(f"official trail lines {len(off) - int(water.sum())}, gated USFS road lines {len(gated)}")


def follow(lines, ref):
    """For each line, the index of the ref line it mostly follows (within MATCH_M over MATCH_SHARE of its length),
    else -1. Uses points every 25 m along each line."""
    if not len(ref):
        return np.full(len(lines), -1)
    tree = shapely.STRtree(ref.geometry.values)
    pts, owner = [], []
    for i, ln in enumerate(lines.geometry.values):
        n = max(2, int(ln.length // 25) + 1)
        pts.append(shapely.line_interpolate_point(ln, np.linspace(0, ln.length, n)))
        owner.append(np.full(n, i))
    pts, owner = np.concatenate(pts), np.concatenate(owner)
    hit_pt, hit_ref = tree.query_nearest(pts, max_distance=MATCH_M, all_matches=False)
    share = np.bincount(owner[hit_pt], minlength=len(lines)) / np.bincount(owner, minlength=len(lines))
    best = np.full(len(lines), -1)
    if len(hit_pt):
        pairs = pd.DataFrame({"line": owner[hit_pt], "ref": hit_ref})
        top = pairs.groupby(["line", "ref"]).size().reset_index().sort_values(0).drop_duplicates("line", keep="last")
        best[top.line.values] = top.ref.values
    best[share < MATCH_SHARE] = -1
    return best


yn = lambda v: str(v).upper().startswith("Y")
uses = [", ".join(u for u, flag in (("hikers", r.hikerpedestrian), ("bikes", r.bicycle), ("horses", r.packsaddle))
                  if yn(flag)) or None for r in off.itertuples()] if len(off) else []
m_off = follow(gu, off)
if water.any():           # a way along a water trail takes nothing from it
    m_off = np.where((m_off >= 0) & water[np.maximum(m_off, 0)], -1, m_off)
m_gate = np.where(gu.kind == "fire road", follow(gu, gated), -1)
gu["official"] = [off.sourceoriginator.iat[i] if i >= 0 else None for i in m_off]
gu["trail_no"] = [None if i < 0 or pd.isna(off.trailnumber.iat[i]) else str(off.trailnumber.iat[i]) for i in m_off]
gu["uses"] = [uses[i] if i >= 0 else None for i in m_off]
gu["name"] = gu["name"].where(gu["name"].notna(), [off.name.iat[i] if i >= 0 else None for i in m_off])
gu["gated"] = [gated.id.iat[i] if i >= 0 else None for i in m_gate]     # USFS road number, e.g. 2N50
gu["off_bike"] = [off.bicycle.iat[i] if i >= 0 and "bicycle" in off else None for i in m_off]   # Y / N / None

# ---- named official trails missing from OSM: parts more than 40 m from any OSM way, at least 400 m long, whose
# median distance to the nearest OSM way is at least 300 m (closer pieces were mostly offset copies of trails OSM
# already has, e.g. the Gabrielino 80-90 m off its OSM line), and not a same-named OSM trail within 150 m ----
add = []
if len(off):
    otree = shapely.STRtree(gu.geometry.values)
    # the 300 m test reads the OSM paths and tracks (as before bike paths and steps joined the layer, 2026-11-25); a piece
    # with its median within 100 m of a bike path or stair is that one's copy (La Conchita Beach, by the coast bike path)
    old_ways = gu.geometry.values[~gu.highway.isin(["cycleway", "steps"]).values]
    old_tree = shapely.STRtree(old_ways)
    new_ways = gu.geometry.values[gu.highway.isin(["cycleway", "steps"]).values]
    new_tree = shapely.STRtree(new_ways) if len(new_ways) else None
    names_n = gu["name"].fillna("").map(norm).values
    lengths = shapely.length(gu.geometry.values)
    old_idx = np.flatnonzero(~gu.highway.isin(["cycleway", "steps"]).values)
    for r in off[off.name.notna()].itertuples():
        wet_trail = bool(water[r.Index])   # a water trail's piece: undrawn, for the parking test only (as before 2026-11-25)
        near = old_tree.query(r.geometry, predicate="dwithin", distance=40)      # (a bike path crossing it cuts nothing)
        rest = r.geometry.difference(shapely.union_all(shapely.buffer(old_ways[near], 40))) if len(near) \
            else r.geometry
        for piece in shapely.get_parts(rest):
            if piece.geom_type != "LineString" or piece.length < 400:
                continue
            sample_pts = shapely.line_interpolate_point(piece, np.linspace(0, piece.length, max(3, int(piece.length // 50))))
            if np.median(old_tree.query_nearest(sample_pts, return_distance=True, all_matches=False)[1]) < 300:
                continue
            if not wet_trail and new_tree is not None and np.median(new_tree.query_nearest(
                    sample_pts, return_distance=True, all_matches=False)[1]) < 100:
                continue
            # OSM has the trail where ways of its name lie within 150 m (the paths and tracks, as before bike paths and
            # steps joined), a quarter of the piece's length or more: an 11 m stub that took the name at a junction left out
            # 1.85 mi of the Browns Tract Trail (2026-11-25). A piece with no name to compare ("-") goes by any such way
            nm_n = norm(r.name)
            close = old_idx[old_tree.query(piece, predicate="dwithin", distance=150)]
            same = close[names_n[close] == nm_n]
            if len(same) and (not nm_n or lengths[same].sum() >= 0.25 * piece.length):
                continue
            add.append(dict(name=r.name, kind="trail", official=r.sourceoriginator, source="official only",
                            trail_no=None if pd.isna(r.trailnumber) else str(r.trailnumber), uses=uses[r.Index],
                            off_bike=getattr(r, "bicycle", None), water_trail=wet_trail, geometry=piece))
if add:
    gu = gpd.GeoDataFrame(pd.concat([gu, gpd.GeoDataFrame(add, crs=CRS)], ignore_index=True), crs=CRS)
    print(f"added {len(add)} official trail pieces missing from OSM, "
          f"{round(sum(a['geometry'].length for a in add) / 1000)} km")

# ---- relief within ~1 km of each way's middle, from 50 m blocks of every region's DEM ----
mid = gu.geometry.interpolate(0.5, normalized=True)
relief = np.full(len(gu), np.nan)
for key in REGIONS:
    p = f"{raw_dir(key)}/dem_10m.tif"
    if not os.path.exists(p):
        continue
    with rasterio.open(p) as src:
        z, T = src.read(1).astype("float32"), src.transform
    z[z < -100] = np.nan
    k = 5
    h, w = z.shape[0] // k * k, z.shape[1] // k * k
    blk = z[:h, :w].reshape(h // k, k, w // k, k)
    hi = maximum_filter(np.nan_to_num(np.nanmax(blk, axis=(1, 3)), nan=-1e4), size=21)
    lo = minimum_filter(np.nan_to_num(np.nanmin(blk, axis=(1, 3)), nan=1e4), size=21)
    rel = hi - lo
    cols, rows = ~T * (mid.x.values, mid.y.values)
    rows, cols = (rows // k).astype(int), (cols // k).astype(int)
    inside = (rows >= 0) & (rows < rel.shape[0]) & (cols >= 0) & (cols < rel.shape[1]) & np.isnan(relief)
    relief[inside] = rel[rows[inside], cols[inside]]

name = gu["name"].fillna("")
mountain = pd.Series(relief, index=gu.index) >= MIN_RELIEF_M
listed = name.ne("") | gu.route.notna() | gu.official.notna() | gu.gated.notna()   # named (any name), routed or official
# a sidepath (trailrules.py): an unnamed footway, path or bike path beside a car road, anywhere (OSM's own sidewalk tags
# are dropped above)
side_c = (~listed & gu.highway.isin(["footway", "path", "cycleway"])).values
sidepath = pd.Series(False, index=gu.index)
sidepath[side_c] = trailrules.beside_road(gu.geometry.values[side_c]) | (gu.is_sidepath.values[side_c] == "yes")
# flat ground: what is named, routed or official, or runs along the water the map draws (trailrules.py)
flat_c = (~mountain & ~listed).values
wet = pd.Series(False, index=gu.index)
wet[flat_c] = trailrules.along_water(gu.geometry.values[flat_c])
keep = mountain | listed | wet
water_piece = gu.get("water_trail", pd.Series(False, index=gu.index)).fillna(False).astype(bool)
# in the layer for the approach times and the parking test, not drawn (06_map.py): sidepaths, water trails' pieces
gu["undrawn"] = sidepath.values | water_piece.values
# the ways the trail rule kept before 2026-11-25 (mountain terrain, a route or an official record, a name like a trail's;
# a bike path only where it follows an official trail, whose dotted copy the layer drew before): the parking test counts
# only these (02e_access.py), so a town lot by a greenway is no trail parking, and a rail trail's lot stays one
gu["old_rule"] = (mountain | gu.route.notna() | gu.official.notna() | gu.gated.notna() |
                  name.str.contains(r"\b(?:trail|fire road|truck trail|motorway)\b", case=False)) & \
    (gu.highway.ne("cycleway") | gu.official.notna())
private_road = (gu.kind == "fire road") & gu.access.isin(["private", "no"]) & ~gu.foot.isin(WALK_OK) & gu.gated.isna()
km_ = gu.length / 1000
print(f"flat ground: kept along the water {round(km_[wet & ~sidepath].sum())} km, dropped {round(km_[~mountain & ~listed & ~wet].sum())} km"
      f" | sidepaths kept undrawn {round(km_[sidepath & keep].sum())} km (on flat ground {round(km_[sidepath & keep & ~mountain].sum())})"
      f" | bike paths kept {round(km_[keep & ~private_road & gu.highway.eq('cycleway')].sum())} km")
gu = gu[keep & ~private_road].copy()
gu["name"] = gu["name"].fillna(gu.route.str.split(", ").str[0])   # an unnamed piece of a named route takes its name
named = gu["name"].notna()
gu["unofficial"] = (gu.kind == "trail") & ~named & gu.official.isna() & gu.route.isna() & gu.highway.ne("cycleway")
gu["closed"] = gu.foot.isin(["no", "private"]) | (gu.access.isin(["no", "private"]) & ~gu.foot.isin(WALK_OK))
# ---- agency designations and current closures (matched like the official lines: 25 m over 60 % of the way) ----
#   USFS trails (EDW TrailNFSPublish): allowed_terra_use digits 1 hiker, 2 pack and saddle, 3 bicycle, 4+ motorized,
#     so "3" in it means bikes allowed; bicycle_restricted holds the dates of an order closing it to bikes
#     ("01/01-12/31" = all year). Many records are "N/A" throughout: no information, not a ban (forest trails are
#     open to bikes unless an order closes them)
#   CA State Parks RecreationalRoutes: TRAILDES "Hike, Bike and Horse" / "Hike and Bike" vs "Hike" / "Hike and Horse"
#   NPS Santa Monica Mountains trail inventory: CU multi-use (MU) vs hikers / horses only (HE, HO); CS existing
#     official (EO) vs existing unofficial (EU)
#   LA County Eaton Fire impacted trails and roads: Status Open / Closed / Closed Vehicles, plus closure areas
# Closures are re-read daily, designations weekly.
EDW_ = "https://apps.fs.usda.gov/arcx/rest/services/EDW"
CSP_ = "https://services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services"
LAC_ = "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Eaton_Fire_Impacted_Trails_and_Roads_WFL1/FeatureServer"
def layer(name, url, fields, key, days=CACHE_DAYS):
    return stack([cached(f"{name}_{k}.geojson", lambda bb=bb: esri_lines(url, bb, fields), days) for k, bb in boxes.items()], key)
fs_tr = layer("usfs_trails_v2", f"{EDW_}/EDW_TrailNFSPublish_01/MapServer/0",
              "objectid,trail_name,trail_no,allowed_terra_use,bicycle_restricted", "objectid")
none = gpd.GeoDataFrame(geometry=[], crs=CRS)
LA = has("la_trail_layers")     # the State Parks, NPS Santa Monica Mountains and Eaton Fire layers exist only there
csp = layer("csp_routes", f"{CSP_}/RecreationalRoutes/FeatureServer/0", "*", "OBJECTID") if LA else none
nps = layer("nps_trail_inventory", f"{CSP_}/NPS_Trail_Inventory__Current_Trail_Usage/FeatureServer/0", "FID,NAME1,CS,CU", "FID") if LA else none
eaton = layer("eaton_lines", f"{LAC_}/14", "OBJECTID,Name,Agency,Status,Line_Type", "OBJECTID", days=1) if LA else none
eaton_areas = layer("eaton_areas", f"{LAC_}/16", "OBJECTID,Agency,Closure_Date", "OBJECTID", days=1) if LA else none
print(f"USFS trails {len(fs_tr)}, State Parks routes {len(csp)}, NPS inventory {len(nps)}, Eaton Fire lines {len(eaton)}, "
      f"closure areas {len(eaton_areas)}")
val = lambda df, m, c: pd.Series([df[c].iat[i] if i >= 0 and c in df else None for i in m], index=gu.index)
m_fs = follow(gu, fs_tr)
atu = val(fs_tr, m_fs, "allowed_terra_use").fillna("").astype(str).str.strip().replace("N/A", "")
b_ban = val(fs_tr, m_fs, "bicycle_restricted").fillna("").astype(str).str.strip().replace("N/A", "")
fs_bike = pd.Series(np.where(b_ban.str.len() > 0, "N", np.where(atu.str.contains("3"), "Y", "")), index=gu.index)
tdes = val(csp, follow(gu, csp), "TRAILDES").fillna("")
csp_bike = pd.Series(np.where(tdes.str.contains("Bike"), "Y", np.where(tdes.isin(["Hike", "Hike and Horse"]), "N", "")),
                     index=gu.index)
m_nps = follow(gu, nps)
cu, cs = val(nps, m_nps, "CU").fillna(""), val(nps, m_nps, "CS").fillna("")
nps_bike = pd.Series(np.where(cu.eq("MU"), "Y", np.where(cu.isin(["HE", "HO"]), "N", "")), index=gu.index)
gu["unofficial"] = gu.unofficial | cs.eq("EU")                       # NPS lists it as an unofficial trail
e_status = val(eaton, follow(gu, eaton), "Status").fillna("")
mid_pts = gu.geometry.interpolate(0.5, normalized=True)
in_area = mid_pts.within(eaton_areas.union_all()) if len(eaton_areas) else pd.Series(False, index=gu.index)
gu["closed_why"] = np.select([e_status.eq("Closed"), in_area], ["Eaton Fire closure (LA County / USFS)",
                                                                 "inside the Eaton Fire closure area"], None)
gu.loc[gu.closed & gu.closed_why.isna(), "closed_why"] = "closed or private (OpenStreetMap)"
gu["closed"] = gu.closed | gu.closed_why.notna()
if len(eaton_areas):   # for the road layer (02e_access.py) and the maps
    eaton_areas.to_crs(4326).to_file(f"{SHARED}/closure_areas.tmp.gpkg", driver="GPKG")
    os.replace(f"{SHARED}/closure_areas.tmp.gpkg", f"{SHARED}/closure_areas.gpkg")

# ---- mountain bikes: one status per way, first rule that applies ----
#   no        in a wilderness (no bikes in any wilderness); the PCT (no bikes anywhere on it); OSM bicycle=no;
#             the agency's trail record says no bikes; closed or private
#   yes       OSM bicycle=yes / designated / permissive; the agency's record says bikes; a fire road outside wilderness
#   unlikely  state-park singletrack (state parks allow bikes on fire roads and designated trails only)
#   likely    a Forest Service system trail with no restriction recorded (forest trails are open to bikes unless an
#             order closes them), or an OSM mountain-bike difficulty (mtb:scale) on it
#   unknown   anything else (mostly unofficial paths)
wild = gpd.read_file(wilderness_path()).to_crs(CRS).union_all()   # downloaded here if 08_hike.py hasn't yet
in_wild = gu.geometry.interpolate(0.5, normalized=True).within(wild)
bik = gu.bicycle.fillna("") if "bicycle" in gu else pd.Series("", index=gu.index)
offb = gu.off_bike.fillna("").astype(str).str.upper()
agency = gu.official.fillna("")
pct = gu.route.fillna("").str.contains("PCT|Pacific Crest", case=False) | \
    gu["name"].fillna("").str.contains("Pacific Crest", case=False)
# the other long trails closed to bikes over their whole length: the Appalachian Trail, and Vermont's Long Trail
at = (gu.route.fillna("") + "|" + gu["name"].fillna("")).str.contains(r"Appalachian (?:National Scenic )?Trail", case=False)
lt = (gu.route.fillna("") + "|" + gu["name"].fillna("")).str.contains(r"\bLong Trail\b(?! Road)")
# National Park Service trails are closed to bikes unless a park designates them (36 CFR 4.30). In LA the Santa
# Monica Mountains inventory above says which are, so the blanket rule is for the other areas (Grand Teton,
# Blue Ridge Parkway, Chattahoochee River NRA)
nps_trail = agency.str.contains("National Park Service|NPS", case=False) & (gu.kind == "trail") & (not LA)
mtb = gu["mtb:scale"] if "mtb:scale" in gu else pd.Series(None, index=gu.index)
rules = [
    (gu.get("water_trail", pd.Series(False, index=gu.index)).fillna(False).astype(bool), "no", "a water trail"),
    (in_wild, "no", "wilderness: no bikes"),
    (pct, "no", "Pacific Crest Trail: no bikes"),
    (at, "no", "Appalachian Trail: no bikes"),
    (lt, "no", "Long Trail: foot travel only"),
    (bik.isin(["no", "dismount", "private"]), "no", "posted no bikes"),
    (offb.str.startswith("N"), "no", "agency: no bikes"),
    (gu.closed, "no", "closed"),
    (fs_bike.eq("N"), "no", "Forest Service: closed to bikes by order"),
    (csp_bike.eq("N"), "no", "State Parks: no bikes"),
    (nps_bike.eq("N"), "no", "NPS: hikers / horses only"),
    (gu.highway.eq("cycleway"), "yes", "bike path"),
    (fs_bike.eq("Y"), "yes", "Forest Service: bikes allowed"),
    (csp_bike.eq("Y"), "yes", "State Parks: bikes allowed"),
    (nps_bike.eq("Y"), "yes", "NPS: multi-use trail"),
    (bik.isin(["yes", "designated", "permissive"]), "yes", "open to bikes"),
    (nps_trail, "no", "National Park Service trail: no bikes unless posted"),
    (offb.str.startswith("Y"), "yes", "agency: open to bikes"),
    (gu.kind == "fire road", "yes", "fire road outside wilderness"),
    (agency.str.contains("State Park", case=False), "unlikely", "state park singletrack: bikes only where posted"),
    (agency.str.contains("Forest Service|USFS", case=False) | mtb.notna(), "likely",
     "forest trail, no bike restriction on record"),
]
gu["bike"] = np.select([c for c, _, _ in rules], [v for _, v, _ in rules], "unknown")
gu["bike_why"] = np.select([c for c, _, _ in rules], [w for _, _, w in rules], "no bike information")
gu["mtb_scale"] = mtb
gu["rank"] = np.select([gu.route.notna() | (named & (gu.kind == "trail")), named, (gu.kind == "trail") & ~gu.unofficial],
                       [1, 2, 3], 4)
cols = ["osm_id", "name", "ref", "kind", "rank", "route", "official", "trail_no", "uses", "gated", "unofficial", "closed_why",
        "closed", "bike", "bike_why", "mtb_scale", "sac_scale", "trail_visibility", "informal", "surface", "access", "foot", "source",
        "highway", "old_rule", "undrawn", "geometry"]
gu = gu[[c for c in cols if c in gu]]
gu.to_crs(4326).to_file(f"{SHARED}/trails.tmp.gpkg", driver="GPKG")
os.replace(f"{SHARED}/trails.tmp.gpkg", f"{SHARED}/trails.gpkg")   # the map build may be reading the old file
km = gu.length / 1000
print("kept", len(gu), "ways,", round(km.sum()), "km | km by rank:", km.groupby(gu["rank"].values).sum().round().to_dict())
print("mountain bikes (km):", km.groupby(gu["bike"].values).sum().round().to_dict())
print("following an official trail:", f"{km[gu.official.notna()].sum() / km.sum():.0%}", "of km | gated USFS fire roads:",
      round(km[gu.gated.notna()].sum()), "km | possibly unofficial:", round(km[gu.unofficial].sum()), "km")
