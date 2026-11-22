"""After the rebuild: does the installed build equal the measured scratch build? Per box, flowdir / area_km2 /
strahler (03b), knickpoints (04 / 04b), streams_scored (05_score: sids and geometry), area_streams (05c) and
flow_streams' water classes (05b) of the project against the scratch root.
AREA=<area> python verify_install.py <scratch root> [hydro]
With `hydro`, only 03b's rasters and the drops: for a scratch root measured before a later change to the reaches
(05_score.py's floor, 2026-11-21), whose reach tables no longer compare."""
import sys, os
R = sys.argv[1]
HYDRO = len(sys.argv) > 2 and sys.argv[2] == "hydro"
P = "/Users/mac/Fishing"
sys.path.insert(0, f"{P}/scripts"); os.chdir(f"{P}/scripts")
import numpy as np, pandas as pd, geopandas as gpd, rasterio, config
out = []
for b in config.REGIONS:
    row = [b]
    for f in ("flowdir", "area_km2", "strahler"):
        a = rasterio.open(f"{P}/data/derived/{config.AREA}/{b}/{f}.tif").read(1)
        c = rasterio.open(f"{R}/data/derived/{config.AREA}/{b}/{f}.tif").read(1)
        row.append(f"{f} " + ("=" if np.array_equal(a, c) else f"DIFF {int((a != c).sum())}"))
    for f in ("knickpoints", "knickpoints_bigcreek"):
        a = gpd.read_file(f"{P}/data/derived/{config.AREA}/{b}/{f}.gpkg"); c = gpd.read_file(f"{R}/data/derived/{config.AREA}/{b}/{f}.gpkg")
        row.append(f"{f} " + ("=" if a.drop(columns="geometry").equals(c.drop(columns="geometry")) else f"DIFF {len(a)}/{len(c)}"))
    if HYDRO:
        out.append(" | ".join(row))
        continue
    a = gpd.read_file(f"{P}/output/{config.AREA}/{b}/streams_scored.gpkg"); c = gpd.read_file(f"{R}/output/{config.AREA}/{b}/streams_scored.gpkg")
    same = len(a) == len(c) and (a.sid.values == c.sid.values).all() and a.geometry.equals(c.geometry)
    row.append("reaches " + ("=" if same else f"DIFF {len(a)}/{len(c)}"))
    a = pd.read_csv(f"{P}/output/{config.AREA}/{b}/area_streams.csv"); c = pd.read_csv(f"{R}/output/{config.AREA}/{b}/area_streams.csv")
    row.append("areas " + ("=" if a.equals(c) else "DIFF"))
    a = pd.read_csv(f"{P}/output/{config.AREA}/{b}/flow_streams.csv", low_memory=False)[["sid", "water_class", "dry_cfs"]]
    c = pd.read_csv(f"{R}/output/{config.AREA}/{b}/flow_streams.csv", low_memory=False)[["sid", "water_class", "dry_cfs"]]
    row.append("flows " + ("=" if a.equals(c) else f"DIFF {int((a.water_class.values != c.water_class.values).sum()) if len(a) == len(c) else 'rows'}"))
    out.append(" | ".join(row))
print(config.AREA); print("\n".join("  " + o for o in out))
