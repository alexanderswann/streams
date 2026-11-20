"""Reaches named after the NHDPlus line they lie on (40 m) that carry under a quarter of that line's drainage
(area_full_km2 against totdasqkm, lines of 20+ km2): side channels, stubs, channels through lake flats, and creeks
whose upper basin the 10 m DEM routes elsewhere. AREA=<area> python short_named.py"""
import sys, os, json
ROOT = os.environ.get("ROOT", "/Users/mac/Fishing"); sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import geopandas as gpd, pandas as pd, numpy as np, config
from flowlib import FLOW
rk = pd.read_csv(f"{config.ROOT}/output/{config.AREA}/stream_reaches_ranked.csv", low_memory=False)
rk = rk[~rk.sid.str.contains(r"\+", regex=True)]
g = pd.concat([gpd.read_file(f"{config.out_dir(r)}/streams_scored.gpkg")[["sid", "geometry"]].to_crs(config.CRS)
               for r in config.REGIONS], ignore_index=True)
g = gpd.GeoDataFrame(g.merge(rk[["sid", "name", "area_km2", "area_full_km2", "water_class", "fish_score", "len_m"]], on="sid"),
                     crs=config.CRS)
v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg").to_crs(config.CRS)
v2 = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"])]
mid = g.assign(geometry=g.geometry.interpolate(0.5, normalized=True))
j = gpd.sjoin_nearest(mid[["sid", "geometry"]], v2[["gnis_name", "totdasqkm", "geometry"]], max_distance=40,
                      distance_col="d").drop_duplicates("sid")
g = g.merge(j[["sid", "gnis_name", "totdasqkm"]], on="sid", how="left")
same = g.name.notna() & (g.name == g.gnis_name) & (g.totdasqkm >= 20)
low = same & (g.area_full_km2.fillna(g.area_km2) < 0.25 * g.totdasqkm)
out = g[low & g.water_class.ne("reservoir")]
print(json.dumps(dict(area=config.AREA, reaches=len(g), named_on_their_line=int(same.sum()), under_quarter=int(low.sum()),
                      outside_lakes=len(out), km=round(out.len_m.sum() / 1000, 1),
                      fish_60_plus=int((out.fish_score >= 60).sum()),
                      top=out.groupby("name").size().sort_values(ascending=False).head(4).to_dict())))
