"""How far build B's stream lines moved from build A's: B's reaches sampled every 10 m, each point's distance to the
nearest A reach; km of B's lines more than 20 / 50 m from any A line, by B's drainage size.
AREA=<area> python moved.py <rootA|-> <rootB>"""
import sys, os
A = sys.argv[1] if sys.argv[1] != "-" else "/Users/mac/Fishing"
B = sys.argv[2]
sys.path.insert(0, f"{B}/scripts"); os.chdir(f"{B}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
def lines(root):
    g = pd.concat([gpd.read_file(f"{root}/output/{config.AREA}/{r}/streams_scored.gpkg")[["sid", "area_km2", "geometry"]]
                   for r in config.REGIONS], ignore_index=True)
    return gpd.GeoDataFrame(g, crs=4326).to_crs(config.CRS)
a, b = lines(A), lines(B)
tree = shapely.STRtree(a.geometry.values)
rows = []
for sid, ak, g in zip(b.sid, b.area_km2, b.geometry):
    n = max(int(g.length // 10), 1)
    pts = shapely.line_interpolate_point(g, np.linspace(0, g.length, n + 1))
    idx, d = tree.query_nearest(pts, return_distance=True, all_matches=False)
    rows.append((sid, ak, g.length, float((d > 20).mean()), float((d > 50).mean())))
t = pd.DataFrame(rows, columns=["sid", "area_km2", "len_m", "f20", "f50"])
t["size"] = pd.cut(t.area_km2, [0, 10, 100, 1e9], labels=["1-10 km2", "10-100", "100+"])
s = t.groupby("size", observed=False).apply(lambda x: pd.Series(dict(km=round(x.len_m.sum() / 1000, 1),
        km_moved_20m=round((x.len_m * x.f20).sum() / 1000, 1), km_moved_50m=round((x.len_m * x.f50).sum() / 1000, 1))))
print(f"{config.AREA}: B's lines against A's ({B} vs {A})")
print(s.to_string())
print("total km", round(t.len_m.sum() / 1000, 1), "| moved 20+ m", round((t.len_m * t.f20).sum() / 1000, 1),
      "| 50+ m", round((t.len_m * t.f50).sum() / 1000, 1))
