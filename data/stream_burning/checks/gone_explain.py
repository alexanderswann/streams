"""For each stretch the older map draws and the newer doesn't (300+ m with no new line within 40 m, not a lake piece):
how far away the nearest line of the newer map runs along the gone part, and what it carries.
own_sqmi_now is the most ground the newer build's own routing gathers anywhere along the gone part (its area_km2
rasters, <build root>/data/derived): under 0.39 sq mi the creek there is below the map's floor once the lake's water
no longer lands on it, so the older line was a put-in path.
AREA=<area> python gone_explain.py <old dir> <new dir> <build root of the newer> [min sq mi]"""
import sys, os, json
P = "/Users/mac/Fishing"
sys.path.insert(0, f"{P}/scripts"); os.chdir(f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
a = config.AREA
OLD, NEW = sys.argv[1], sys.argv[2]
ROOT = sys.argv[3]
MIN = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
import rasterio
RAS = {}
for r_ in config.REGIONS:
    src_ = rasterio.open(f"{ROOT}/data/derived/{a}/{r_}/area_km2.tif")
    RAS[r_] = (src_, shapely.box(*src_.bounds))
def own_now(points):
    best = 0.0
    for r_, (src_, bx) in RAS.items():
        xy = [(p.x, p.y) for p in points if bx.contains(p)]
        if xy:
            best = max(best, max(float(v[0]) for v in src_.sample(xy)))
    return best
def load(p, key):
    t = open(p).read()
    F = json.loads(t[t.index("{"):t.rindex("}") + 1]).get(key, {"features": []})["features"]
    F = [f for f in F if f["geometry"]["type"] == "LineString" and len(f["geometry"]["coordinates"]) > 1]
    g = gpd.GeoSeries([shapely.LineString([c[:2] for c in f["geometry"]["coordinates"]]) for f in F], crs=4326).to_crs(config.CRS).values
    return F, g
Fo, Go = load(f"{OLD}/{a}.js", "streams"); Fn, Gn = load(f"{NEW}/{a}.js", "streams"); Fl, Gl = load(f"{NEW}/{a}.js", "streams_lake")
parts = []
for r in config.REGIONS:
    p = f"{config.raw_dir(r)}/nhd_flowlines.gpkg"
    if os.path.exists(p):
        g = gpd.read_file(p, columns=["ftype"]); parts.append(g[g.ftype.isin([460, 558, 334]) & g.geometry.notna()].to_crs(config.CRS))
NG = pd.concat(parts, ignore_index=True).geometry.values
tn, tl, tg = shapely.STRtree(Gn), (shapely.STRtree(Gl) if len(Gl) else None), shapely.STRtree(NG)
rows = []
for i, g in enumerate(Go):
    q = Fo[i]["properties"]
    if str(q.get("fl", "")).endswith("reservoir"):
        continue
    n = max(1, int(np.ceil(g.length / 25)))
    pts = shapely.line_interpolate_point(g, (np.arange(n) + 0.5) / n, normalized=True)
    hit = np.zeros(n, bool); hit[np.unique(tn.query(pts, predicate="dwithin", distance=40)[0])] = True
    gone_m = (~hit).sum() * g.length / n
    sqmi = float(q.get("a") or 0) / 2.58999
    if gone_m < 300 or sqmi < MIN:
        continue
    gp = pts[~hit]
    k, d = tn.query_nearest(gp, max_distance=400, return_distance=True, all_matches=False)
    dist = np.full(len(gp), np.nan); dist[k[0]] = d
    na = np.full(len(gp), np.nan); na[k[0]] = [float(Fn[j]["properties"].get("a") or 0) / 2.58999 for j in k[1]]
    onn = np.zeros(len(gp), bool); onn[np.unique(tg.query(gp, predicate="dwithin", distance=60)[0])] = True
    inl = np.zeros(len(gp), bool)
    if tl is not None:
        inl[np.unique(tl.query(gp, predicate="dwithin", distance=40)[0])] = True
    mid = gpd.GeoSeries([gp[len(gp) // 2]], crs=config.CRS).to_crs(4326).iloc[0]
    rows.append(dict(area=a, gone_mi=round(gone_m / 1609.344, 2), name=q.get("n"), old_sqmi=round(sqmi, 2), old_fish=q.get("fs"), on_nhd=f"{onn.mean():.0%}",
                     nearest_new_m=(round(float(np.nanmedian(dist))) if np.isfinite(dist).any() else None), within_100m=f"{np.mean(dist <= 100):.0%}",
                     new_sqmi_there=(round(float(np.nanmedian(na)), 2) if np.isfinite(na).any() else None), now_lake_layer=f"{inl.mean():.0%}",
                     own_sqmi_now=round(own_now(list(gp)) / 2.58999, 2),
                     lat=round(mid.y, 5), lon=round(mid.x, 5)))
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_rows", 200)
t = pd.DataFrame(rows)
if len(t):
    print(t.sort_values("gone_mi", ascending=False).to_string(index=False))
    os.makedirs(f"{os.path.dirname(os.path.abspath(NEW))}/gone_explain", exist_ok=True)
    t.to_csv(f"{os.path.dirname(os.path.abspath(NEW))}/gone_explain/{a}.csv", index=False)
