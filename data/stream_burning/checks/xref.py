"""For classify_short.py's 'water routed elsewhere' reaches: is there an HR line within 2 km upstream-ish (same name, or
any line within 1 km) that the D8 routing misses (hragree.py)? If not, the DEM agrees with NHD HR around the reach and
the shortfall against NHDPlus V2 is V2's network (or a basin with no HR lines to burn).
python xref.py <area> <dir with short_<area>.csv and hr_<area>.csv>"""
import sys, numpy as np, pandas as pd
a, d = sys.argv[1], sys.argv[2]
s = pd.read_csv(f"{d}/short_{a}.csv")
h = pd.read_csv(f"{d}/hr_{a}.csv")
s = s[s.kind == "water routed elsewhere"].copy()
rk = pd.read_csv(f"/Users/mac/Fishing/output/{a}/stream_reaches_ranked.csv", usecols=["sid", "lat", "lon"])
import geopandas as gpd, sys as _s
_s.path.insert(0, "/Users/mac/Fishing/scripts")
import os; os.environ["AREA"] = a
import config
s = s.merge(rk, on="sid", how="left")
p = gpd.GeoSeries(gpd.points_from_xy(s.lon, s.lat), crs=4326).to_crs(config.CRS)
s["x"], s["y"] = p.x.values, p.y.values
miss = h[~h.ok]
near_same, near_any = [], []
for x, y, n in zip(s.x, s.y, s.name):
    dd = np.hypot(miss.x - x, miss.y - y)
    near_same.append(bool(((miss.name == n) & (dd < 5000)).any()))
    near_any.append(bool((dd < 1000).any()))
s["hr_miss_same_name_5km"] = near_same
s["hr_miss_within_1km"] = near_any
s["dem_vs_hr"] = s.hr_miss_same_name_5km | s.hr_miss_within_1km
print(a, "elsewhere reaches:", len(s), "| with a D8 miss of an HR line nearby:", int(s.dem_vs_hr.sum()),
      "| none (V2's network, or no HR line):", int((~s.dem_vs_hr).sum()))
print(s.groupby(["name", "dem_vs_hr"]).size().unstack(fill_value=0).sort_values(False if False in s.dem_vs_hr.values else True, ascending=False).head(12).to_string())
s.to_csv(f"{d}/xref_{a}.csv", index=False)
