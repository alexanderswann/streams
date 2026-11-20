"""Drops against known falls (data/validate.py's rule: a fall counts as found when a detected drop lies within 200 m),
with 02f's source names (validate.py still filters on "OSM" / "NHD", which 02f no longer writes, so it finds none):
all known falls of the area, and those mapped by OpenStreetMap or USGS NHD; pass 1 (04) and pass 1 + the big-creek
pass (04b). Also the drops by kind and the waterfall candidates by status (05_score). AREA=<area> python falls.py [root|-]"""
import sys, os
ROOT = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else "/Users/mac/Fishing"
sys.path.insert(0, f"{ROOT}/scripts"); os.chdir(f"{ROOT}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, shapely
import config
kf = gpd.read_file(f"{config.SHARED}/known_falls.gpkg").to_crs(config.CRS)
inside = shapely.union_all([shapely.box(*v["bbox"]) for v in config.REGIONS.values()])
kf = kf[kf.within(inside)].reset_index(drop=True)
p1 = pd.concat([gpd.read_file(f"{ROOT}/data/derived/{config.AREA}/{r}/knickpoints.gpkg") for r in config.REGIONS], ignore_index=True)
p2 = pd.concat([gpd.read_file(f"{ROOT}/data/derived/{config.AREA}/{r}/knickpoints_bigcreek.gpkg") for r in config.REGIONS], ignore_index=True)
p1, p2 = gpd.GeoDataFrame(p1, crs=config.CRS), gpd.GeoDataFrame(p2, crs=config.CRS)
t1, t2 = shapely.STRtree(p1.geometry.values), shapely.STRtree(p2.geometry.values)
d1 = np.array([t1.query_nearest(g, return_distance=True)[1][0] if len(p1) else np.inf for g in kf.geometry])
d2 = np.array([t2.query_nearest(g, return_distance=True)[1][0] if len(p2) else np.inf for g in kf.geometry])
kf["hit1"], kf["hit"] = d1 < 200, (d1 < 200) | (d2 < 200)
mapped = kf.src.str.contains("OpenStreetMap|USGS NHD", regex=True)
wc = pd.concat([gpd.read_file(f"{ROOT}/output/{config.AREA}/{r}/waterfall_candidates.gpkg") for r in config.REGIONS], ignore_index=True)
print(f"{config.AREA} ({ROOT}): known falls {len(kf)}: found pass 1 {int(kf.hit1.sum())}, both passes {int(kf.hit.sum())} | "
      f"OSM/NHD-mapped {int(mapped.sum())}: pass 1 {int(kf.hit1[mapped].sum())}, both {int(kf.hit[mapped].sum())}")
print(f"  drops: pass 1 {len(p1)} {p1.kind.value_counts().to_dict()}; big-creek pass {len(p2)}")
if "status" in wc:
    print("  waterfall candidates by status:", wc.status.value_counts().to_dict())
