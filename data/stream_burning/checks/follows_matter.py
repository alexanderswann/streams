"""Where 03b_stitch.py's 'stays on NHD's line' test (follows) moves the hand-over past the first cell that leads on,
replayed on the surfaces of a build from before 2026-11-22. BEFORE=<build root> AREA=<area> python follows_matter.py"""
import sys, importlib.util
# Paths: BEFORE = a build root from before 2026-11-22 (its data/derived/<area>/<box>/flowdir.tif has every lake's pit at
# the cell with the most water; the candidates are replayed on that surface), BEFORE_MAPS = a folder with that build's
# <area>.js map data, BUILD = the build root to read the new routing from, STITCH = the 03b_stitch.py to replay.
import os
P = "/Users/mac/Fishing"
BEFORE = os.environ.get("BEFORE", P)
BEFORE_MAPS = os.environ.get("BEFORE_MAPS", f"{P}/output")
BUILD = os.environ.get("BUILD", P)
STITCH = os.environ.get("STITCH", f"{P}/scripts/03b_stitch.py")
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, rasterio, shapely, pyproj
spec = importlib.util.spec_from_file_location("stitch", STITCH); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from config import *
from flowlib import still_water
back = pyproj.Transformer.from_crs(CRS, 4326, always_xy=True)
real = m.follows
n_lakes = n_far = 0
for box in REGIONS:
    with rasterio.open(f"{BEFORE}/data/derived/{AREA}/{box}/flowdir.tif") as src:
        fd, T = src.read(1), src.transform
    lakes = still_water(tuple(sorted(REGIONS[box]["hu4"])), tuple(REGIONS[box]["bbox"]))
    index = m.outflow_index(m.nhd_lines([box], m.LAKE_LINE_FTYPES + m.BUILT_FTYPES))
    wins, wet, pit = {}, np.zeros(fd.shape, bool), {}
    for k, g in enumerate(lakes.geometry):
        w_ = m.lake_cells(fd, g, T)
        if w_ is not None and w_[2].any():
            r0, c0, mask = w_
            p = np.argwhere((fd[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] == m.PIT) & mask)
            if len(p):
                wins[k] = w_; pit[k] = (int(p[0][0]) + r0, int(p[0][1]) + c0)
                wet[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] |= mask
    for k, cell in pit.items():
        geom = lakes.geometry.iloc[k]
        m.follows = real
        a = m.lake_outlet(fd, geom, T, cell, index, wet)
        if a[0] is None:
            continue
        n_lakes += 1
        m.follows = lambda *q, **kw: True
        b = m.lake_outlet(fd, geom, T, cell, index, wet)
        if b[0] is not None and (a[0], a[1]) != (b[0], b[1]):
            n_far += 1
            x, y = T * (a[0][1] + 0.5, a[0][0] + 0.5); lon, lat = back.transform(x, y)
            name = lakes.gnis_name.iloc[k]
            print(f"  {AREA}/{box} {name if isinstance(name, str) else 'unnamed'} ({geom.area / 1e4:.1f} ha) at {lat:.5f},{lon:.5f}: way out {len(a[1])} cells with the test, {len(b[1])} without; {a[2]}")
m.follows = real
print(f"{AREA}: {n_lakes} lakes at NHD's outlet; the test moves the hand-over at {n_far}")
