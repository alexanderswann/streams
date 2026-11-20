"""Burn depths on a window, scored by hragree.check (D8 misses of NHD HR lines inside the window, 300 m in from its
edges). No lake rule here (paths run through lakes); lines in lakes are left out of the check as in hragree.
AREA=.. REGION=.. python window_hr.py x0 y0 x1 y1 depth [depth ...]"""
import sys, os, importlib, time
H_ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/Users/mac/Fishing/scripts"); sys.path.insert(0, H_); sys.path.insert(0, f"{H_}/../checks")
os.chdir("/Users/mac/Fishing/scripts")
import numpy as np, rasterio, rasterio.windows, shapely, pandas as pd
import config, burnlib, hragree
from flowlib import still_water
st = importlib.import_module("03b_stitch")
x0, y0, x1, y1 = map(float, sys.argv[1:5])
depths = [float(d) for d in sys.argv[5:]]
with rasterio.open(f"{config.RAW}/dem_10m.tif") as src:
    win = rasterio.windows.from_bounds(x0, y0, x1, y1, src.transform).round_offsets().round_lengths()
    z = src.read(1, window=win, masked=True).astype(np.float32).filled(np.nan)
    T = src.window_transform(win)
hr = hragree.hr_lines(config)
hr = hr[hr.intersects(shapely.box(x0, y0, x1, y1).buffer(3000))].reset_index(drop=True)
inside = shapely.box(x0 + 300, y0 + 300, x1 - 300, y1 - 300)
lakes = still_water(tuple(config.HU4), (x0, y0, x1, y1))
lake_u = shapely.union_all(lakes.geometry.values) if len(lakes) else shapely.Polygon()
D = os.environ.get("OUTDIR", "/tmp")
res = {}
for d in depths:
    t0 = time.time()
    P = np.full((z.shape[0] + 2, z.shape[1] + 2), np.nan)
    P[1:-1, 1:-1] = st.condition(burnlib.burn(z, T, d), T)
    fd = st.d8(P)
    del P
    acc, loops = st.accumulate(fd, st.DR, st.DC)
    t = hragree.check(fd, acc, T, hr, inside, lake_u, st.CODE_SET, st.DR, st.DC, config.RES)
    t.to_csv(f"{D}/whr_{d:g}.csv", index=False)
    np.save(f"{D}/fd_{d:g}.npy", fd)
    res[d] = t
    print(hragree.summary(t, f"depth {d:g} m ({time.time() - t0:.0f} s, loops {loops})"))
base = res[depths[0]].set_index("i").ok
for d in depths[1:]:
    o = res[d].set_index("i").ok
    print(f"depth {d:g}: fixed {int((~base & o).sum())}, broken {int((base & ~o).sum())} (against depth {depths[0]:g})")
