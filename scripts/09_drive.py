"""Drive time and distance from HOME (config.py, ZIP 90404) to every trailhead found by 08_hike.py.

Road network = regional OSM highways (motorway..secondary, cached) + all open drivable roads in the study areas.
Today's full closures (07_road_closures.py) are cut out. Free-flow speeds by road class, slowed on winding
roads; no traffic, so LA rush hour can add a lot.
"""
import os, time, json, requests, numpy as np, pandas as pd, geopandas as gpd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import Point
from config import REGIONS, CRS, ROOT, MAP_OUT, SHARED, HOME

KMH = {"motorway": 100, "motorway_link": 60, "trunk": 80, "trunk_link": 50, "primary": 60, "primary_link": 40,
       "secondary": 50, "secondary_link": 35, "tertiary": 45, "unclassified": 35, "residential": 30, "service": 15}
WINDING = 1.3          # sinuosity above which a road counts as a mountain road
WINDING_FACTOR = 0.75  # speed multiplier on winding roads
SNAP_M = 400

major_path = f"{SHARED}/osm_major_roads.gpkg"
# Major roads for every study area plus HOME, padded 0.15 degrees; re-downloaded when the areas outgrow the cache
from shapely.geometry import box as _box
_W, _S, _E, _N = gpd.GeoSeries([_box(*v["bbox"]) for v in REGIONS.values()], crs=CRS).to_crs(4326).total_bounds
W, S = min(_W, HOME["lon"]) - 0.15, min(_S, HOME["lat"]) - 0.15
E, N = max(_E, HOME["lon"]) + 0.15, max(_N, HOME["lat"]) + 0.15
ext_path = major_path + ".extent.json"
ext = json.load(open(ext_path)) if os.path.exists(ext_path) else None
if not os.path.exists(major_path) or ext is None or not (ext[0] <= W and ext[1] <= S and ext[2] >= E and ext[3] >= N):
    q = f"""[out:json][timeout:600];
    way["highway"~"^(motorway|trunk|primary|secondary)(_link)?$"]({S},{W},{N},{E}); out geom;"""
    for attempt in range(6):
        url = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")[attempt % 2]
        try:
            r = requests.post(url, data={"data": q}, timeout=900,
                              headers={"User-Agent": "la-stream-analysis/0.1 (personal GIS project)"})
            if r.ok:
                break
        except requests.RequestException:
            pass
        time.sleep(20 * (attempt + 1))
    r.raise_for_status()
    feats = [{"type": "Feature", "properties": {"highway": el["tags"].get("highway"), "name": el["tags"].get("name"),
              "oneway": el["tags"].get("oneway")},
              "geometry": {"type": "LineString", "coordinates": [[g["lon"], g["lat"]] for g in el["geometry"]]}}
             for el in r.json()["elements"] if el["type"] == "way"]
    gpd.GeoDataFrame.from_features(feats, crs=4326).to_crs(CRS).to_file(major_path)
    json.dump([W, S, E, N], open(ext_path, "w"))
major = gpd.read_file(major_path)

local = []
for r in REGIONS:
    rd = gpd.read_file(f"{ROOT}/data/raw/{r}/osm_roads.gpkg")
    local.append(rd[~rd.access.isin(["private", "no"]) & ~rd.motor_vehicle.isin(["no", "private"])
                    & rd.highway.isin(KMH.keys())])
roads = pd.concat([major[["highway", "name", "geometry"]]] + [l[["highway", "name", "geometry"]] for l in local],
                  ignore_index=True)
roads = gpd.GeoDataFrame(roads, crs=CRS)
if os.path.exists(f"{MAP_OUT}/road_closures.gpkg"):
    cl = gpd.read_file(f"{MAP_OUT}/road_closures.gpkg").to_crs(CRS)
    cl = cl[(cl.severity == "full closure") & (cl.when == "active now")]
    if len(cl):
        roads["geometry"] = roads.geometry.difference(cl.buffer(25).union_all())
        roads = roads[~roads.is_empty].explode(index_parts=False)
print("road ways", len(roads))

# graph: every vertex is a node (shared coordinates join ways); edge weight = minutes
xs, ys, a_idx, b_idx, mins, dist = [], [], [], [], [], []
coords = []
for geom, cls in zip(roads.geometry, roads.highway):
    c = np.round(np.asarray(geom.coords)[:, :2], 1)
    if len(c) < 2:
        continue
    seg = np.hypot(*np.diff(c, axis=0).T)
    crow = np.hypot(*(c[-1] - c[0]))
    v = KMH.get(cls, 30) * (WINDING_FACTOR if crow > 0 and seg.sum() / crow > WINDING and seg.sum() > 500 else 1)
    coords.append(c)
    mins.append(seg / 1000 / v * 60)
    dist.append(seg)
allc = np.vstack(coords)
uniq, inv = np.unique(allc, axis=0, return_inverse=True)
inv = inv.ravel()
pos = 0
for c in coords:
    n = len(c)
    a_idx.append(inv[pos:pos + n - 1]); b_idx.append(inv[pos + 1:pos + n]); pos += n
a, b, w, d = map(np.concatenate, (a_idx, b_idx, mins, dist))
M = len(uniq)
A = coo_matrix((np.r_[w, w], (np.r_[a, b], np.r_[b, a])), shape=(M, M)).tocsr()
D = coo_matrix((np.r_[d, d], (np.r_[a, b], np.r_[b, a])), shape=(M, M)).tocsr()
tree = cKDTree(uniq)
home = gpd.GeoSeries([Point(HOME["lon"], HOME["lat"])], crs=4326).to_crs(CRS).iloc[0]
hd, hi = tree.query([home.x, home.y])
t_min, pred = dijkstra(A, indices=hi, return_predecessors=True)
print(f"graph nodes {M:,}; home snapped {hd:.0f} m; reachable {np.isfinite(t_min).mean():.0%}")

def path_km(j):
    km, k = 0.0, j
    while pred[k] >= 0:
        km += D[pred[k], k]; k = pred[k]
    return km / 1000

# Some trailheads sit on road pieces that only connect through streets outside the downloaded areas.
# Snap those to the nearest reachable node within FAR_SNAP_M and add the gap at GAP_KMH, flagged approximate.
FAR_SNAP_M, GAP_KMH = 2000, 25
reach_idx = np.flatnonzero(np.isfinite(t_min))
rtree = cKDTree(uniq[reach_idx])
for r in REGIONS:
    th = gpd.read_file(f"{MAP_OUT}/{r}/trailheads.gpkg")
    pts = np.c_[th.geometry.x, th.geometry.y]
    dd, ii = tree.query(pts)
    ok = (dd < SNAP_M) & np.isfinite(t_min[ii])
    fd, fi = rtree.query(pts)
    fi = reach_idx[fi]
    far = ~ok & (fd < FAR_SNAP_M)
    node = np.where(ok, ii, fi)
    gap = np.where(ok, 0.0, fd)
    use = ok | far
    th["drive_min"] = np.where(use, np.round(t_min[node] + gap / 1000 / GAP_KMH * 60), np.nan)
    th["drive_km"] = [round(path_km(j) + g / 1000, 1) if u else np.nan for j, g, u in zip(node, gap, use)]
    th["drive_approx"] = far
    th.to_file(f"{MAP_OUT}/{r}/trailheads.gpkg")
    print(f"{REGIONS[r]['label']}: {use.sum()}/{len(th)} trailheads routed ({far.sum()} approximate); drive {np.nanmin(th.drive_min):.0f}–"
          f"{np.nanmax(th.drive_min):.0f} min (median {np.nanmedian(th.drive_min):.0f})")
