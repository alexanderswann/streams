"""Recall of the drop detectors against mapped waterfalls, for every range of one area: pass 1 (04_knickpoints.py), and
pass 1 with the big-creek pass (04b_bigcreek_steps.py), split by drainage size at the fall.

A mapped fall counts as found when a detected drop lies within 200 m of it. Mapped falls are the known falls in
05_score.py's known_falls.gpkg that OpenStreetMap or the NHD lists, rapids and swimming holes left out. Since
2026-11-19 those come from 02f_known_falls.py, which merges every source's point for one fall into one row and lists the
sources' labels in `src` ("OpenStreetMap · USGS GNIS · Wikidata"), so a fall counts when either label is among them. A
second line covers every precisely placed known fall, whatever its source (curated guidebook points, the NPS...). CDFW
fish-passage barriers that no other source lists (cascades, bedrock chutes, boulder jams: often no drop a 10 m DEM can
show) are reported on their own line.
Run from scripts/:  AREA=<area> ../.venv/bin/python ../data/validate.py
"""
import sys, os, importlib, numpy as np, rasterio, geopandas as gpd, pandas as pd
from rasterio.windows import Window
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import config

MAPPED = {"OpenStreetMap", "USGS NHD"}      # 02f's labels for OSM and NHD points (its SRC_LABEL)
CDFW = "CDFW barrier survey"
NOT_FALLS = {"rapids", "swimming hole"}

rows = []
for reg in config.REGIONS:
    os.environ["REGION"] = reg
    importlib.reload(config)
    if not os.path.exists(f"{config.OUT}/known_falls.gpkg"):
        continue
    p1 = gpd.read_file(f"{config.DERIVED}/knickpoints.gpkg")
    p2 = gpd.read_file(f"{config.DERIVED}/knickpoints_bigcreek.gpkg")
    kf = gpd.read_file(f"{config.OUT}/known_falls.gpkg").to_crs(config.CRS)
    kinds = kf["kind"] if "kind" in kf else pd.Series("waterfall", index=kf.index)
    precise = kf["precise"] if "precise" in kf else pd.Series(False, index=kf.index)
    with rasterio.open(f"{config.DERIVED}/area_km2.tif") as src:
        for g, n, s, k, pr in zip(kf.geometry, kf.name, kf.src, kinds, precise):
            r, c = src.index(g.x, g.y)
            if not (0 <= r < src.height and 0 <= c < src.width):
                continue
            r0, c0 = max(r - 5, 0), max(c - 5, 0)            # biggest channel within 50 m
            a = float(src.read(1, window=Window(c0, r0, min(c + 6, src.width) - c0, min(r + 6, src.height) - r0)).max())
            labels = set(str(s).split(" · "))
            rows.append(dict(region=config.LABEL, name=n, src=s, kind=k, precise=bool(pr), area=a,
                             mapped=bool(labels & MAPPED) and k not in NOT_FALLS, cdfw_only=labels == {CDFW},
                             d1=p1.distance(g).min() if len(p1) else np.inf,
                             d2=p2.distance(g).min() if len(p2) else np.inf))
df = pd.DataFrame(rows)
if df.empty:
    sys.exit(f"{config.AREA}: no known falls in any range")
df["big"] = df.area >= 10
df["hit1"] = df.d1 < 200
df["hit"] = df.hit1 | (df.d2 < 200)
mapped = df[df.mapped]
placed = df[df.precise & ~df.cdfw_only & ~df.kind.isin(NOT_FALLS)]


def line(d):
    return f"pass 1: {int(d.hit1.sum())} / {len(d)} | pass 1 + big-creek pass: {int(d.hit.sum())} / {len(d)}"


print(f"{config.AREA}: mapped falls (OpenStreetMap or NHD among the sources), all ranges")
print("  on creeks >= 10 km2:   ", line(mapped[mapped.big]))
print("  on smaller drainages:  ", line(mapped[~mapped.big]))
print("  all:                   ", line(mapped))
print("\nby range:")
print(mapped.groupby("region").agg(falls=("hit", "size"), pass1=("hit1", "sum"), both=("hit", "sum")).to_string())
missed = mapped[mapped.big & mapped.name.notna() & ~mapped.hit]
print("\nnamed mapped falls on big creeks that both passes miss:", "none" if missed.empty else "")
if len(missed):
    print(missed[["region", "name", "area", "d1", "d2"]].round(0).to_string(index=False))
print("\nevery precisely placed known fall, any source:", line(placed))
print("CDFW fish-passage barriers no other source lists (not in the figures above):", line(df[df.cdfw_only]))
