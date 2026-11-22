"""Which step of the lake-outlet rule decides each lake: 03b_stitch.lake_outlet replayed on the surfaces of one build,
every lake that ends its paths there, counted by the reason it gives.
The build must be one from before 2026-11-22 (every lake's dead end at the cell with the most water); on a later
build the lakes already moved are judged from their moved dead ends. Lakes whose water runs on across an edge
between two boxes have no dead end on those surfaces and are not counted.
With BUILD (a build root made with that 03b_stitch.py) each lake is marked `in_build` where the build's
lake_outlets.json has a dead end at the replayed outlet cell: the replay judges each box alone, the build judges the
boxes of a group together, so a few lakes by a box edge come out differently and are left out of the counts.
BEFORE=<build root> [BUILD=<build root>] [STITCH=<03b_stitch.py>] AREA=<area> python rule_tally.py [out.csv]"""
import sys, os, importlib.util
P = "/Users/mac/Fishing"
BEFORE = os.environ["BEFORE"]
STITCH = os.environ.get("STITCH", f"{P}/scripts/03b_stitch.py")
BUILD = os.environ.get("BUILD")
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import json
import numpy as np, pandas as pd, rasterio, shapely, pyproj
spec = importlib.util.spec_from_file_location("stitch_tally", STITCH); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
from config import *
from flowlib import still_water
back = pyproj.Transformer.from_crs(CRS, 4326, always_xy=True)
built = json.load(open(f"{BUILD}/data/derived/{AREA}/_shared/lake_outlets.json")) if BUILD else None
rows = []
for box in REGIONS:
    with rasterio.open(f"{BEFORE}/data/derived/{AREA}/{box}/flowdir.tif") as src:
        fd, T = src.read(1), src.transform
    lakes = still_water(tuple(sorted(REGIONS[box]["hu4"])), tuple(REGIONS[box]["bbox"]))
    index = M.outflow_index(M.nhd_lines([box], M.LAKE_LINE_FTYPES + M.BUILT_FTYPES))
    v2 = M.nhdplus([box])
    wet, pit = np.zeros(fd.shape, bool), {}
    for k, g in enumerate(lakes.geometry):
        w_ = M.lake_cells(fd, g, T)
        if w_ is not None and w_[2].any():
            r0, c0, mask = w_
            p = np.argwhere((fd[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] == M.PIT) & mask)
            if len(p):
                pit[k] = (int(p[0][0]) + r0, int(p[0][1]) + c0)
                wet[r0:r0 + mask.shape[0], c0:c0 + mask.shape[1]] |= mask
    ends = {(int(r_), int(c_)) for r_, c_, *_ in built["tops"].get(box, [])} if built else set()
    for k, cell in pit.items():
        geom = lakes.geometry.iloc[k]
        out, way, why = M.lake_outlet(fd, geom, T, cell, index, wet, M.nhdplus_exit(shapely.make_valid(geom), v2))
        x, y = T * (cell[1] + 0.5, cell[0] + 0.5)
        moved = 0.0
        if out is not None:
            ox, oy = T * (out[1] + 0.5, out[0] + 0.5); moved = float(np.hypot(ox - x, oy - y))
        step = ("left at the terrain's cell: " + why) if out is None else (
            "NHD's name" if "the named one of" in why else "NHDPlus's line" if "NHDPlus's line leaves by" in why else
            "nearest the terrain's cell" if "the nearest of" in why else "one outflow line")
        lon, lat = back.transform(x, y)
        name = lakes.gnis_name.iloc[k]
        rows.append(dict(area=AREA, box=box, lake=name if isinstance(name, str) else "unnamed", ha=round(geom.area / 1e4, 1), step=step,
                         pipe="a pipe or ditch" in why, moved_m=round(moved),
                         in_build=(out is not None and (int(out[0]), int(out[1])) in ends) if built else None, why=why, lat=round(lat, 5), lon=round(lon, 5)))
t = pd.DataFrame(rows)
if len(sys.argv) > 1:
    t.to_csv(sys.argv[1], index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 150)
print(f"{AREA}: {len(t)} lakes end their paths on these surfaces")
print(t.groupby("step").agg(lakes=("ha", "size"), moved_300m=("moved_m", lambda s: int((s >= 300).sum()))).to_string())
if built:
    n_tops = sum(len(v) for v in built["tops"].values())
    print(f"the build ends {n_tops} lakes at NHD's outlet; the replay finds {int(t.in_build.sum())} of them: "
          + ", ".join(f"{k} {v}" for k, v in t[t.in_build.astype(bool)].groupby("step").size().items()))
