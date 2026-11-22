"""Stream lines below lake outlets that the map's size floor leaves off. 05_score.py keeps a stream link when its own
D8 drainage at its lower end is 1 km2 or more; a lake ends its paths at its outlet (03b_stitch.py), so the creek
below starts again near nothing, and its links stay under the floor until they gather 1 km2 of their own, although
they carry the lake's water (crossbox's dam / pond links put it back in below the dam; 05c counts it in
area_full_km2). This lists the links (dem_streams.gpkg) with under 1 km2 of their own and 1 km2 or more with the
linked water, per box: length, the share along an NHD HR stream line, and what the build before drew there
(`old`: a reach of root A within 30 m along half the link or more).
AREA=<area> python outlet_gaps.py [root|-] [rootA for the build before] [outcsv]"""
import sys, os, json
P = "/Users/mac/Fishing"
ROOT = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else P
A = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else None
OUT = sys.argv[3] if len(sys.argv) > 3 else None
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely, rasterio
import config
from crossbox import graph, CACHE
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 400)
cache = json.load(open(CACHE))          # read only: crossbox would rebuild it if a flowdir.tif had changed
rows = []
for r in config.REGIONS:
    d = config.derived_dir(r)
    with rasterio.open(f"{d}/flowdir.tif") as src:
        fd = src.read(1); T = src.transform
    with rasterio.open(f"{d}/area_km2.tif") as src:
        area = src.read(1)
    H, W = fd.shape
    nxt, _ = graph(fd)
    ex = np.zeros(H * W, np.float32)
    for row, col, km2, *_ in cache["full"].get(r, []):
        i = row * W + col
        while True:
            ex[i] += km2
            if nxt[i] == i:
                break
            i = nxt[i]
    ex = ex.reshape(H, W)
    s = gpd.read_file(f"{d}/dem_streams.gpkg")
    s = s[s.length > 0].copy()
    inv = ~T
    def at(arr, x, y):
        c, rr = inv * (x, y)
        return float(arr[int(np.clip(rr, 0, H - 1)), int(np.clip(c, 0, W - 1))])
    ends = [g.coords[-2] if len(g.coords) >= 2 else g.coords[0] for g in s.geometry]
    s["own"] = [at(area, *e) for e in ends]
    s["linked"] = [at(ex, *e) for e in ends]
    s["box"] = r
    rows.append(s[(s.own < 1.0) & (s.own + s.linked >= 1.0)])
g = gpd.GeoDataFrame(pd.concat(rows, ignore_index=True), crs=rows[0].crs).to_crs(config.CRS)
g["len_m"] = g.geometry.length


def share_near(lines, tree, dist):
    out = np.zeros(len(lines))
    for i, ln in enumerate(lines):
        n = max(2, int(ln.length // 25) + 1)
        pts = shapely.line_interpolate_point(ln, np.linspace(0, 1, n), normalized=True)
        out[i] = len(set(tree.query(pts, predicate="dwithin", distance=dist)[0])) / n
    return out


hr = [gpd.read_file(f"{config.raw_dir(r)}/nhd_flowlines.gpkg", columns=["ftype"]) for r in config.REGIONS
      if os.path.exists(f"{config.raw_dir(r)}/nhd_flowlines.gpkg")]
hr = pd.concat([h[h.ftype.isin([460, 558, 334])].to_crs(config.CRS) for h in hr], ignore_index=True)
g["nhd"] = share_near(g.geometry.values, shapely.STRtree(hr.geometry.values), 40).round(2)
new = pd.concat([gpd.read_file(f"{ROOT}/output/{config.AREA}/{r}/streams_scored.gpkg")[["sid", "geometry"]]
                 for r in config.REGIONS], ignore_index=True)
new = gpd.GeoDataFrame(new, crs=4326).to_crs(config.CRS)
g["drawn"] = share_near(g.geometry.values, shapely.STRtree(new.geometry.values), 30).round(2)
g["old"], g["old_fish"], g["old_name"] = np.nan, np.nan, None
if A:
    rk = pd.read_csv(f"{A}/output/{config.AREA}/stream_reaches_ranked.csv", low_memory=False,
                     usecols=["sid", "name", "fish_score", "water_class"])
    old = pd.concat([gpd.read_file(f"{A}/output/{config.AREA}/{r}/streams_scored.gpkg")[["sid", "geometry"]]
                     for r in config.REGIONS], ignore_index=True)
    old = gpd.GeoDataFrame(old, crs=4326).to_crs(config.CRS).merge(rk, on="sid")
    old = old[old.water_class != "reservoir"].reset_index(drop=True)
    to = shapely.STRtree(old.geometry.values)
    g["old"] = share_near(g.geometry.values, to, 30).round(2)
    mids = shapely.line_interpolate_point(g.geometry.values, 0.5, normalized=True)
    q, k = to.query_nearest(mids, max_distance=30, all_matches=False)
    g.iloc[q, g.columns.get_loc("old_fish")] = old.fish_score.values[k]
    g.iloc[q, g.columns.get_loc("old_name")] = old["name"].values[k]
c = g.geometry.to_crs(4326).interpolate(0.5, normalized=True)
g["lat"], g["lon"] = c.y.round(5), c.x.round(5)
km = lambda s: round(float(s.sum()) / 1000, 1)
und = g[g.drawn < 0.5]
print(f"{config.AREA} ({ROOT}): stream links under 1 km2 of their own that carry a lake's water to 1 km2 or more: "
      f"{len(g)}, {km(g.len_m)} km; not drawn as a reach (under half within 30 m of one): {len(und)}, {km(und.len_m)} km; "
      f"of those along an NHD stream line (half or more): {int((und.nhd >= 0.5).sum())}, {km(und.len_m[und.nhd >= 0.5])} km; "
      f"drawn by the build before (half or more, not as a lake reach): {int((und.old >= 0.5).sum())}, "
      f"{km(und.len_m[und.old >= 0.5])} km, of that fish 60+ before {km(und.len_m[(und.old >= 0.5) & (und.old_fish >= 60)])} km")
print(und.sort_values("len_m", ascending=False)[["box", "len_m", "own", "linked", "nhd", "drawn", "old", "old_fish",
                                                 "old_name", "lat", "lon"]].head(40).round(2).to_string(index=False))
if OUT:
    g.drop(columns="geometry").to_csv(OUT, index=False)
