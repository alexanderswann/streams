"""Recall of the drop detectors against mapped waterfalls, for every range: pass 1 (04_knickpoints.py), and pass 1
with the big-creek pass (04b_bigcreek_steps.py), split by drainage size at the fall.

A mapped fall counts as found when a detected drop lies within 200 m of it. Mapped falls are OpenStreetMap waterfalls
and NHD falls. The CDFW fish-passage barriers that 05_score.py also puts in known_falls.gpkg (cascades, bedrock
chutes, boulder jams: often no drop a 10 m DEM can show) are reported on their own line.
Run from scripts/:  ../.venv/bin/python ../data/validate.py
"""
import sys, os, importlib, numpy as np, rasterio, geopandas as gpd, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import config

rows = []
for reg in config.REGIONS:
    os.environ["REGION"] = reg
    importlib.reload(config)
    if not os.path.exists(f"{config.OUT}/known_falls.gpkg"):
        continue
    p1 = gpd.read_file(f"{config.DERIVED}/knickpoints.gpkg")
    p2 = gpd.read_file(f"{config.DERIVED}/knickpoints_bigcreek.gpkg")
    kf = gpd.read_file(f"{config.OUT}/known_falls.gpkg").to_crs(config.CRS)
    with rasterio.open(f"{config.DERIVED}/area_km2.tif") as src:
        ar = src.read(1)
        for g, n, s in zip(kf.geometry, kf.name, kf.src):
            r, c = src.index(g.x, g.y)
            if not (0 <= r < ar.shape[0] and 0 <= c < ar.shape[1]):
                continue
            a = ar[max(r - 5, 0):r + 6, max(c - 5, 0):c + 6].max()  # biggest channel within 50 m
            rows.append(dict(region=config.LABEL, name=n, src=s, area=a, d1=p1.distance(g).min() if len(p1) else np.inf,
                             d2=p2.distance(g).min() if len(p2) else np.inf))
df = pd.DataFrame(rows)
df["big"] = df.area >= 10
df["hit1"] = df.d1 < 200
df["hit"] = df.hit1 | (df.d2 < 200)
mapped = df[df.src.isin(["OSM", "NHD"])]


def line(d):
    return f"pass 1: {int(d.hit1.sum())} / {len(d)} | pass 1 + big-creek pass: {int(d.hit.sum())} / {len(d)}"


print("Mapped falls (OSM + NHD), all ranges")
print("  on creeks >= 10 km2:   ", line(mapped[mapped.big]))
print("  on smaller drainages:  ", line(mapped[~mapped.big]))
print("  all:                   ", line(mapped))
print("\nby range:")
print(mapped.groupby("region").agg(falls=("hit", "size"), pass1=("hit1", "sum"), both=("hit", "sum")).to_string())
missed = mapped[mapped.big & mapped.name.notna() & ~mapped.hit]
print("\nnamed mapped falls on big creeks that both passes miss:", "none" if missed.empty else "")
if len(missed):
    print(missed[["region", "name", "area", "d1", "d2"]].round(0).to_string(index=False))
print("\nCDFW fish-passage barriers (not in the figures above):", line(df[df.src == "CDFW"]))
