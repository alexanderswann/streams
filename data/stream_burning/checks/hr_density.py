"""For the flagged reaches: the km of HR stream line upstream (NHD HR's own network) of the HR line under the reach,
per km2 of the reach's DEM drainage, against the same ratio for all reaches of the area (a typical drainage density).
A reach whose ratio is typical drains what NHD HR says it should; only NHDPlus V2 disagrees.
python hr_density.py <area> <dir>"""
import sys, os
a, d = sys.argv[1], sys.argv[2]
os.environ["AREA"] = a
sys.path.insert(0, "/Users/mac/Fishing/scripts"); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir("/Users/mac/Fishing/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely, config
from hragree import network, hr_lines
hr = hr_lines(config)
succ, up = network(hr)
hr["up_km"] = up
rk = pd.read_csv(f"{config.MAP_OUT}/stream_reaches_ranked.csv", low_memory=False)
g = pd.concat([gpd.read_file(f"{config.out_dir(r)}/streams_scored.gpkg")[["sid", "geometry"]].to_crs(config.CRS)
               for r in config.REGIONS], ignore_index=True)
g = gpd.GeoDataFrame(g.merge(rk[["sid", "name", "area_km2", "area_full_km2"]], on="sid"), crs=config.CRS)
g = g[g.name.notna()]
mid = g.assign(geometry=g.geometry.interpolate(0.5, normalized=True))
j = gpd.sjoin_nearest(mid, hr[["gnis_name", "up_km", "geometry"]], max_distance=30).drop_duplicates("sid")
j = j[j.name == j.gnis_name]
j["af"] = j.area_full_km2.fillna(j.area_km2)
j["dens"] = j.up_km / j.af
s = pd.read_csv(f"{d}/xref_{a}.csv")
f = j[j.sid.isin(s.sid)].merge(s[["sid", "totdasqkm", "dem_vs_hr"]], on="sid")
f["v2_dens"] = f.up_km / f.totdasqkm
lo, md, hi = j.dens.quantile([0.1, 0.5, 0.9])
print(f"{a}: HR km per DEM km2 over all named reaches: p10 {lo:.2f}, median {md:.2f}, p90 {hi:.2f}")
print(f"  flagged 'elsewhere' reaches on their HR line: {len(f)}; HR km per DEM km2 median {f.dens.median():.2f} "
      f"(within p10-p90: {int(f.dens.between(lo, hi).sum())}); HR km per NHDPlus V2 km2 median {f.v2_dens.median():.2f} "
      f"(within p10-p90: {int(f.v2_dens.between(lo, hi).sum())})")
print(f.groupby("name").agg(n=("sid", "size"), dem_km2=("af", "median"), v2_km2=("totdasqkm", "median"), hr_up_km=("up_km", "median"),
                           dens=("dens", "median"), v2_dens=("v2_dens", "median")).round(2).sort_values("n", ascending=False).head(12).to_string())
