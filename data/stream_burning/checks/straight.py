"""Straight runs in the drawn stream lines: the flat-resolution artefact (a D8 path held to one direction for hundreds
of metres across a wetland or lake flat). Per reach, runs of consecutive segments in one D8 direction; km of lines in
runs of 300 m or more, outside and inside the lakes that end paths. AREA=<area> python straight.py [root|-]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else "/Users/mac/Fishing"
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
from flowlib import reservoirs
g = pd.concat([gpd.read_file(f"{ROOT}/output/{config.AREA}/{r}/streams_scored.gpkg")[["sid", "area_km2", "geometry"]]
               for r in config.REGIONS], ignore_index=True)
g = gpd.GeoDataFrame(g, crs=4326).to_crs(config.CRS)
lake_u = shapely.union_all(reservoirs().geometry.values)
shapely.prepare(lake_u)
runs = []
for sid, a, ln in zip(g.sid, g.area_km2, g.geometry):
    v = np.asarray(ln.coords)
    if len(v) < 3:
        continue
    d = np.diff(v, axis=0)
    seg = np.hypot(d[:, 0], d[:, 1])
    ang = np.round(np.degrees(np.arctan2(d[:, 1], d[:, 0])) / 45).astype(int) % 8
    start = 0
    for k in range(1, len(ang) + 1):
        if k == len(ang) or ang[k] != ang[start]:
            L = seg[start:k].sum()
            if L >= 300:
                p = shapely.Point(v[(start + k) // 2])
                runs.append((sid, a, L, bool(lake_u.contains(p))))
            start = k
t = pd.DataFrame(runs, columns=["sid", "area_km2", "len_m", "in_lake"])
print(f"{config.AREA} ({ROOT}): straight runs of 300+ m: outside lakes {int((~t.in_lake).sum())} runs, "
      f"{t[~t.in_lake].len_m.sum() / 1000:.1f} km ({t[~t.in_lake & (t.area_km2 >= 10)].len_m.sum() / 1000:.1f} km on 10+ km2); "
      f"in lakes {int(t.in_lake.sum())} runs, {t[t.in_lake].len_m.sum() / 1000:.1f} km; of {g.length.sum() / 1000:.0f} km drawn")
