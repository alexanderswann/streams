"""Lakes with more than one dead end (pit) among their cells, in a build: python stray_pits.py <build root> (AREA set)"""
import sys, os, json
P = "/Users/mac/Fishing"
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, rasterio, rasterio.features, shapely, pyproj
from config import *
from flowlib import still_water
ROOT = sys.argv[1]
back = pyproj.Transformer.from_crs(CRS, 4326, always_xy=True)
n = 0
for box in REGIONS:
    with rasterio.open(f"{ROOT}/data/derived/{AREA}/{box}/flowdir.tif") as src:
        fd, T = src.read(1), src.transform
    lakes = still_water(tuple(sorted(REGIONS[box]["hu4"])), tuple(REGIONS[box]["bbox"]))
    lab = rasterio.features.rasterize(((g, i + 1) for i, g in enumerate(lakes.geometry)), out_shape=fd.shape, transform=T, fill=0, dtype="int32")
    pr, pc = np.nonzero((fd == 254) & (lab > 0))
    ids, cnt = np.unique(lab[pr, pc], return_counts=True)
    for i, c in zip(ids, cnt):
        if c > 1:
            n += 1
            sel = lab[pr, pc] == i
            pts = ["%.5f,%.5f" % back.transform(*(T * (cc + 0.5, rr + 0.5)))[::-1] for rr, cc in zip(pr[sel], pc[sel])]
            nm = lakes.gnis_name.iloc[i - 1]
            print(f"  {AREA}/{box} {nm if isinstance(nm, str) else 'unnamed'} ({lakes.geometry.iloc[i - 1].area / 1e4:.1f} ha): {c} pits at " + "; ".join(pts[:5]))
print(f"{AREA}: lakes with 2+ pits: {n}")
