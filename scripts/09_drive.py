"""Drive time and distance from HOME (config.py, ZIP 90404) to every trailhead found by 08_hike.py.

Road network = regional OSM highways (motorway..secondary, cached) + all open drivable roads in the study areas.
Today's full closures (07_road_closures.py) are cut out. Free-flow speeds by road class, slowed on winding
roads; no traffic, so LA rush hour can add a lot.
"""
import os, time, json, requests, numpy as np, pandas as pd, geopandas as gpd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, connected_components
from scipy.spatial import cKDTree
from shapely.geometry import Point
from config import REGIONS, CRS, ROOT, MAP_OUT, SHARED, HOME, raw_dir

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
    rd = gpd.read_file(f"{raw_dir(r)}/osm_roads.gpkg")
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
# One edge per pair of nodes. Every motorway-to-secondary road inside a study box is in the regional file and in that
# range's own file, and a road crossing between two boxes is in both of theirs. The sparse matrices below add up
# repeated entries, so those segments counted twice: drive times and distances came out 1.2-1.7x too long. Keep the
# fastest copy of each segment.
ea, eb = np.minimum(a, b), np.maximum(a, b)
order = np.lexsort((w, eb, ea))
ea, eb, w, d = ea[order], eb[order], w[order], d[order]
once = np.r_[True, (ea[1:] != ea[:-1]) | (eb[1:] != eb[:-1])] & (ea != eb)
print(f"road segments {int(once.sum()):,} ({int((~once).sum()):,} repeats of a segment from another file dropped)")
a, b, w, d = ea[once], eb[once], w[once], d[once]
M = len(uniq)
tree = cKDTree(uniq)
home = gpd.GeoSeries([Point(HOME["lon"], HOME["lat"])], crs=4326).to_crs(CRS).iloc[0]
hd, hi = tree.query([home.x, home.y])


def solve(a, b, w, d):
    """Minutes and distance matrices, and the fastest times and their predecessors from HOME."""
    A = coo_matrix((np.r_[w, w], (np.r_[a, b], np.r_[b, a])), shape=(M, M)).tocsr()
    D = coo_matrix((np.r_[d, d], (np.r_[a, b], np.r_[b, a])), shape=(M, M)).tocsr()
    return (A, D) + dijkstra(A, indices=hi, return_predecessors=True)


A, D, t_min, pred = solve(a, b, w, d)
print(f"graph nodes {M:,}; home snapped {hd:.0f} m; reachable {np.isfinite(t_min).mean():.0%}")

# Roads that leave a study box and join the network only through local streets outside every box (Bautista Road in
# the San Jacintos) are islands the graph can't reach. Each island that holds trailheads is joined to the reachable
# network across its narrowest gap (up to BRIDGE_M), driven at GAP_KMH; its trailheads are flagged approximate.
FAR_SNAP_M, GAP_KMH, BRIDGE_M = 2000, 25, 3000
ths = {r: gpd.read_file(f"{MAP_OUT}/{r}/trailheads.gpkg") for r in REGIONS}
snap = {r: tree.query(np.c_[th.geometry.x, th.geometry.y]) for r, th in ths.items()}
_, comp = connected_components(A, directed=False)
bridged = np.zeros(M, bool)
for _ in range(4):
    reached = np.isfinite(t_min)
    islands = {int(c) for dd, ii in snap.values() for c in np.unique(comp[ii[(dd < SNAP_M) & ~reached[ii]]])}
    reach_idx = np.flatnonzero(reached)
    rtree = cKDTree(uniq[reach_idx])
    na, nb, ng = [], [], []
    for c in islands:
        nodes = np.flatnonzero(comp == c)
        g, j = rtree.query(uniq[nodes])
        k = int(np.argmin(g))
        if g[k] <= BRIDGE_M:
            na.append(nodes[k]); nb.append(reach_idx[j[k]]); ng.append(g[k])
            bridged[nodes] = True
    if not na:
        break
    ng = np.array(ng)
    a, b, w, d = np.r_[a, na], np.r_[b, nb], np.r_[w, ng / 1000 / GAP_KMH * 60], np.r_[d, ng]
    A, D, t_min, pred = solve(a, b, w, d)
    print(f"joined {len(na)} road islands with trailheads across gaps of {ng.min():.0f}-{ng.max():.0f} m")

# distance along each fastest route: add each node's last leg to its predecessor's total, nearest nodes first
has = np.flatnonzero(pred >= 0)
leg_km = np.zeros(M)
leg_km[has] = np.asarray(D[pred[has], has]).ravel() / 1000
km = np.zeros(M)
for j in np.argsort(t_min)[:int(np.isfinite(t_min).sum())]:
    if pred[j] >= 0:
        km[j] = km[pred[j]] + leg_km[j]

# Some trailheads sit on road pieces that only connect through streets outside the downloaded areas.
# Snap those to the nearest reachable node within FAR_SNAP_M and add the gap at GAP_KMH, flagged approximate.
reach_idx = np.flatnonzero(np.isfinite(t_min))
rtree = cKDTree(uniq[reach_idx])
for r in REGIONS:
    th = ths[r]
    pts = np.c_[th.geometry.x, th.geometry.y]
    dd, ii = snap[r]
    ok = (dd < SNAP_M) & np.isfinite(t_min[ii])
    fd, fi = rtree.query(pts)
    fi = reach_idx[fi]
    far = ~ok & (fd < FAR_SNAP_M)
    node = np.where(ok, ii, fi)
    gap = np.where(ok, 0.0, fd)
    use = ok | far
    th["drive_min"] = np.where(use, np.round(t_min[node] + gap / 1000 / GAP_KMH * 60), np.nan)
    th["drive_km"] = np.where(use, np.round(km[node] + gap / 1000, 1), np.nan)
    th["drive_approx"] = far | (use & bridged[node])
    th.to_file(f"{MAP_OUT}/{r}/trailheads.gpkg")
    print(f"{REGIONS[r]['label']}: {use.sum()}/{len(th)} trailheads routed ({int(th.drive_approx.sum())} approximate); drive {np.nanmin(th.drive_min):.0f}–"
          f"{np.nanmax(th.drive_min):.0f} min (median {np.nanmedian(th.drive_min):.0f})")
