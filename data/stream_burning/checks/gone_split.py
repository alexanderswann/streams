"""Line the older published map drew by default that the newer doesn't (nothing within 40 m), in stretches of 300+ m
on reaches that weren't lake pieces: how much lies along an NHD stream line (60%+ of the gone part within 60 m of a
StreamRiver, ArtificialPath or Connector line) and how big the creek was. Both versions from the folders of <area>.js
taken from the site commits (git -C publish/alexanderswann.github.io show <commit>:streams/<area>/map3d_data.js), so a
rebuild in output/ can't leak in. Goes with drawn_cmp.py, which gives the totals.
AREA=<area> python gone_split.py <old dir> <new dir> <out dir>"""
import sys, os, json, glob
P = "/Users/mac/Fishing"
sys.path.insert(0, f"{P}/scripts"); os.chdir(f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
a = config.AREA
OLD, NEW = sys.argv[1], sys.argv[2]
def load(p, key):
    t = open(p).read()
    F = json.loads(t[t.index("{"):t.rindex("}") + 1]).get(key, {"features": []})["features"]
    F = [f for f in F if f["geometry"]["type"] == "LineString" and len(f["geometry"]["coordinates"]) > 1]
    g = gpd.GeoSeries([shapely.LineString([c[:2] for c in f["geometry"]["coordinates"]]) for f in F], crs=4326).to_crs(config.CRS).values
    return F, g
Fo, Go = load(f"{OLD}/{a}.js", "streams"); Fn, Gn = load(f"{NEW}/{a}.js", "streams")
parts = []
for r in config.REGIONS:
    p = f"{config.raw_dir(r)}/nhd_flowlines.gpkg"
    if os.path.exists(p):
        g = gpd.read_file(p, columns=["ftype"])
        parts.append(g[g.ftype.isin([460, 558, 334]) & g.geometry.notna()].to_crs(config.CRS))
NG = pd.concat(parts, ignore_index=True).geometry.values
L = shapely.length(Go); n = np.maximum(1, np.ceil(L / 50.0).astype(int))
idx = np.repeat(np.arange(len(Go)), n); first = np.cumsum(n) - n
frac = (np.arange(len(idx)) - first[idx] + 0.5) / n[idx]
Pts = shapely.line_interpolate_point(Go[idx], frac * L[idx]); seg = L[idx] / n[idx]
def near(P_, G, d):
    hit = np.zeros(len(P_), bool)
    if len(G) and len(P_):
        hit[np.unique(shapely.STRtree(G).query(P_, predicate="dwithin", distance=d)[0])] = True
    return hit
gone = ~near(Pts, Gn, 40.0)
onn = np.zeros(len(Pts), bool); onn[gone] = near(Pts[gone], NG, 60.0)
gm = np.bincount(idx, weights=np.where(gone, seg, 0), minlength=len(Go))
gn = np.bincount(idx, weights=np.where(gone & onn, seg, 0), minlength=len(Go))
rows = []
for i in np.flatnonzero(gm >= 300):
    q = Fo[i]["properties"]
    if str(q.get("fl", "")).endswith("reservoir"):
        continue
    fs = q.get("fs") if isinstance(q.get("fs"), (int, float)) else -1
    sqmi = float(q.get("a") or 0) / 2.58999
    rows.append(dict(area=a, mi=gm[i] / 1609.344, on_nhd=gn[i] >= 0.6 * gm[i], big=sqmi >= 0.8, f60=fs >= 60, name=q.get("n"), sqmi=round(sqmi, 2),
                     fish=fs, lat=q.get("y"), lon=q.get("x")))
t = pd.DataFrame(rows)
os.makedirs(sys.argv[3], exist_ok=True)
t.to_csv(f"{sys.argv[3]}/{a}.csv", index=False)
print(a, "all gone line", round(float(np.where(gone, seg, 0).sum()) / 1609.344, 1), "mi | stretches of 300+ m not lake pieces:", len(t), round(t.mi.sum(), 1) if len(t) else 0, "mi")
