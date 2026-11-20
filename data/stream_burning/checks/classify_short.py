"""Classify short_named.py's reaches (named after the NHDPlus line they lie on, under a quarter of its drainage, outside
lakes): side channel (NHDPlus minor divergence, or a reach of the same name within 300 m carries at least half the
line's drainage) against the rest (the river's water is routed elsewhere: what a burn could fix).
AREA=<area> python classify_short.py [root]   (root: a scratch copy of the project; default the project)"""
import sys, os, json
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/Users/mac/Fishing"
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import geopandas as gpd, pandas as pd, numpy as np, config, shapely
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
j = gpd.sjoin_nearest(mid[["sid", "geometry"]], v2[["gnis_name", "totdasqkm", "divergence", "comid", "geometry"]], max_distance=40,
                      distance_col="d").drop_duplicates("sid")
g = g.merge(j[["sid", "gnis_name", "totdasqkm", "divergence", "comid"]], on="sid", how="left")
g["af"] = g.area_full_km2.fillna(g.area_km2)
same = g.name.notna() & (g.name == g.gnis_name) & (g.totdasqkm >= 20)
low = same & (g.af < 0.25 * g.totdasqkm)
out = g[low & g.water_class.ne("reservoir")].copy()
# a reach of the same name within 300 m carrying at least half the line's drainage: the main arm is beside it
big = g[g.name.notna() & (g.af > 0)]
tree = shapely.STRtree(big.geometry.values)
side = []
for geom, nm, tot in zip(out.geometry, out.name, out.totdasqkm):
    idx = tree.query(geom, predicate="dwithin", distance=300)
    side.append(bool(((big.name.values[idx] == nm) & (big.af.values[idx] >= 0.5 * tot)).any()))
out["main_beside"] = side
out["kind"] = np.where(out.divergence == 2, "minor divergence",
                       np.where(out.main_beside, "side arm (main arm beside)", "water routed elsewhere"))
s = out.groupby("kind").agg(n=("sid", "size"), km=("len_m", lambda x: round(x.sum() / 1000, 1)),
                            fish60=("fish_score", lambda x: int((x >= 60).sum())))
res = dict(area=config.AREA, total=len(out), **{k: dict(r) for k, r in s.iterrows()},
           elsewhere_top=out[out.kind == "water routed elsewhere"].groupby("name").size().sort_values(ascending=False).head(6).to_dict())
print(json.dumps(res, default=int))
out.drop(columns="geometry").to_csv(f"{os.environ.get('OUTDIR', '/tmp')}/short_{config.AREA}.csv", index=False)
