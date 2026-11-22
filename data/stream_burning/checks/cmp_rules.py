"""Which lakes' outlet decision differs between two versions of 03b_stitch.py, replayed on the surfaces of one build:
the way to see what a change to the lake-outlet rule does on every map before any map is rebuilt (minutes for all 12).
The build must be one from before 2026-11-22 (every lake's dead end at the cell with the most water), or the lakes the
old version already moved are replayed from their moved dead ends.
Both versions must be from 2026-11-22 or later (they need outflow_index and lake_outlet).
BEFORE=<build root> AREA=<area> python cmp_rules.py <old 03b_stitch.py> <new 03b_stitch.py>"""
import sys, os, importlib.util
BEFORE = os.environ["BEFORE"]
P = "/Users/mac/Fishing"
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, rasterio, shapely, pyproj
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
MA, MB = load(sys.argv[1], "stitch_a"), load(sys.argv[2], "stitch_b")
from config import *
from flowlib import still_water
back = pyproj.Transformer.from_crs(CRS, 4326, always_xy=True)
n = nd = 0
V2 = {}
for box in REGIONS:
    with rasterio.open(f"{BEFORE}/data/derived/{AREA}/{box}/flowdir.tif") as src:
        fd, T = src.read(1), src.transform
    lakes = still_water(tuple(sorted(REGIONS[box]["hu4"])), tuple(REGIONS[box]["bbox"]))
    ia = MA.outflow_index(MA.nhd_lines([box], MA.LAKE_LINE_FTYPES + MA.BUILT_FTYPES))
    ib = MB.outflow_index(MB.nhd_lines([box], MB.LAKE_LINE_FTYPES + MB.BUILT_FTYPES))
    wins, wet, pit = {}, np.zeros(fd.shape, bool), {}
    for k, g in enumerate(lakes.geometry):
        w_ = MA.lake_cells(fd, g, T)
        if w_ is not None and w_[2].any():
            r0, c0, mask = w_
            p = np.argwhere((fd[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] == MA.PIT) & mask)
            if len(p):
                pit[k] = (int(p[0][0]) + r0, int(p[0][1]) + c0)
                wet[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] |= mask
    for k, cell in pit.items():
        geom = lakes.geometry.iloc[k]
        def decide(M, idx):
            if hasattr(M, "nhdplus_exit"):
                return M.lake_outlet(fd, geom, T, cell, idx, wet, M.nhdplus_exit(shapely.make_valid(geom), V2.setdefault(M.__name__, M.nhdplus([box]))))
            return M.lake_outlet(fd, geom, T, cell, idx, wet)
        a = decide(MA, ia); b = decide(MB, ib)
        n += 1
        if (a[0], a[1], a[2]) != (b[0], b[1], b[2]):
            nd += 1
            name = lakes.gnis_name.iloc[k]
            def where(q):
                if q[0] is None: return "terrain's cell"
                x, y = T * (q[0][1] + 0.5, q[0][0] + 0.5); lon, lat = back.transform(x, y)
                return f"{lat:.5f},{lon:.5f} +{len(q[1])} cells"
            print(f"  {AREA}/{box} {name if isinstance(name, str) else 'unnamed'} ({geom.area / 1e4:.1f} ha): {where(a)} [{a[2]}]  ->  {where(b)} [{b[2]}]")
print(f"{AREA}: {n} lakes, {nd} differ")
