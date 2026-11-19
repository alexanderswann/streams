"""Recall of pass 1 / pass 2 / combined against mapped falls, split by drainage size at the fall."""
import sys; sys.path.insert(0, "/Users/mac/Fishing/scripts")
import os, importlib, numpy as np, rasterio, geopandas as gpd, pandas as pd
rows = []
for reg in ("san_gabriel", "santa_monica", "san_bernardino"):
    os.environ["REGION"] = reg
    import config; importlib.reload(config)
    p1 = gpd.read_file(f"{config.DERIVED}/knickpoints.gpkg")
    p2 = gpd.read_file(f"{config.DERIVED}/knickpoints_bigcreek.gpkg")
    kf = gpd.read_file(f"{config.OUT}/known_falls.gpkg").to_crs(26911)
    src = rasterio.open(f"{config.DERIVED}/area_km2.tif"); ar = src.read(1)
    for g, n in zip(kf.geometry, kf.name):
        r, c = src.index(g.x, g.y)
        a = ar[max(r-5,0):r+6, max(c-5,0):c+6].max()  # biggest channel within 50 m
        rows.append(dict(region=reg, name=n, area=a, d1=p1.distance(g).min(), d2=p2.distance(g).min() if len(p2) else np.inf))
df = pd.DataFrame(rows)
df["big"] = df.area >= 10
df["hit1"], df["hit2"] = df.d1 < 200, df.d2 < 200
df["hit"] = df.hit1 | df.hit2
print(df.groupby("big")[["hit1", "hit2", "hit"]].agg(["sum", "count"]).to_string())
print("\nnamed falls on big creeks:")
print(df[df.big & df.name.notna()][["region", "name", "area", "d1", "d2"]].round(0).to_string())
print("\ntotal recall: pass1", int(df.hit1.sum()), "| pass1+2", int(df.hit.sum()), "of", len(df))
