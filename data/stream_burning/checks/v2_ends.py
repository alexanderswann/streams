"""Our drainage at the lower end of every NHDPlus V2 line, against its totdasqkm (the drainage V2 gives at that end).
For each StreamRiver / ArtificialPath line of 5+ km2 that isn't a minor divergence (divergence 2: a side channel, where
V2's total counts the whole river), wholly inside the area's boxes and outside the lakes that end paths: the point 90 %
of the way down the line; our channel there is the reach within 60 m with the most drainage (area_full_km2, as scored).
AREA=<area> python v2_ends.py [root|-] [outcsv]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else "/Users/mac/Fishing"
OUT = sys.argv[2] if len(sys.argv) > 2 else None
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely, json
import config
from flowlib import FLOW, reservoirs
rk = pd.read_csv(f"{config.MAP_OUT}/stream_reaches_ranked.csv", low_memory=False, usecols=["sid", "name", "area_km2", "area_full_km2", "fish_score"])
rk = rk[~rk.sid.str.contains(r"\+", regex=True)]
g = pd.concat([gpd.read_file(f"{config.out_dir(r)}/streams_scored.gpkg")[["sid", "geometry"]].to_crs(config.CRS)
               for r in config.REGIONS], ignore_index=True)
g = gpd.GeoDataFrame(g.merge(rk, on="sid"), crs=config.CRS)
g["af"] = g.area_full_km2.fillna(g.area_km2)
v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg").to_crs(config.CRS).drop_duplicates("comid")
v2 = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"]) & (v2.divergence != 2) & (v2.totdasqkm >= 5)]
inside = shapely.union_all([shapely.box(*v["bbox"]) for v in config.REGIONS.values()]).buffer(-200)
wb = reservoirs()
lake_u = shapely.union_all(wb.geometry.values)
pt = []
for geom in v2.geometry:
    ln = shapely.line_merge(geom)
    if ln.geom_type != "LineString":
        ln = shapely.LineString([c for p in ln.geoms for c in p.coords])
    pt.append(ln.interpolate(0.9, normalized=True))
v2 = v2.assign(pt=pt)
v2 = v2[shapely.contains(inside, v2.pt.values) & ~shapely.intersects(lake_u, v2.pt.values)]
tree = shapely.STRtree(g.geometry.values)
ours, nm = [], []
for p in v2.pt:
    idx = tree.query(p, predicate="dwithin", distance=60)
    if len(idx):
        k = idx[np.argmax(g.af.values[idx])]
        ours.append(g.af.values[k]); nm.append(g.name.values[k])
    else:
        ours.append(np.nan); nm.append(None)
v2 = v2.assign(ours=ours, reach_name=nm)
v2["ratio"] = v2.ours / v2.totdasqkm
v2["size"] = pd.cut(v2.totdasqkm, [5, 20, 100, 1000, 1e9], labels=["5-20", "20-100", "100-1000", "1000+"], right=False)
s = v2.groupby("size", observed=False).agg(lines=("ratio", "size"), no_reach=("ours", lambda x: int(x.isna().sum())),
                                            under_half=("ratio", lambda x: int((x < 0.5).sum())),
                                            under_quarter=("ratio", lambda x: int((x < 0.25).sum())),
                                            over_double=("ratio", lambda x: int((x > 2).sum())))
print(f"{config.AREA} ({ROOT}): NHDPlus V2 lines checked {len(v2)}; ours under half of V2 at the line's lower end: "
      f"{int((v2.ratio < 0.5).sum())}, under a quarter {int((v2.ratio < 0.25).sum())}, over double {int((v2.ratio > 2).sum())}, "
      f"no reach within 60 m {int(v2.ours.isna().sum())}")
print(s.T.to_string())
if OUT:
    v2.drop(columns=["geometry", "pt"]).to_csv(OUT, index=False)
