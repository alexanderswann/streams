"""A lake on a seam between boxes: its pits, the drainage at them and around its outlet in each box, in two builds.
AREA=<area> python seam_look.py <lat,lon> <root> [root2]"""
import sys, os, json
P = "/Users/mac/Fishing"
os.chdir(f"{P}/scripts"); sys.path.insert(0, f"{P}/scripts")
import numpy as np, rasterio, rasterio.features, shapely, pyproj
import config
from flowlib import reservoirs
lat0, lon0 = map(float, sys.argv[1].split(","))
name, ha = "the lake", 0
back = pyproj.Transformer.from_crs(config.CRS, 4326, always_xy=True)
ll = lambda x, y: "%.5f,%.5f" % back.transform(x, y)[::-1]
lakes = reservoirs()
fwd = pyproj.Transformer.from_crs(4326, config.CRS, always_xy=True)
p0 = shapely.Point(*fwd.transform(lon0, lat0))
lg = shapely.make_valid(lakes.geometry.values)
i0 = int(shapely.STRtree(lg).query_nearest(p0)[0])
g = lg[i0]; name = lakes.gnis_name.iloc[i0]
print(f"{name} {g.area / 1e4:.1f} ha, bounds {[round(v) for v in g.bounds]}")
D8 = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}
for root in sys.argv[2:]:
    print("=====", root)
    for box, v in config.REGIONS.items():
        bb = shapely.box(*v["bbox"])
        if not bb.intersects(g.buffer(600)):
            continue
        with rasterio.open(f"{root}/data/derived/{config.AREA}/{box}/flowdir.tif") as src:
            fd, T = src.read(1), src.transform
        with rasterio.open(f"{root}/data/derived/{config.AREA}/{box}/area_km2.tif") as src:
            A = src.read(1)
        H, W = fd.shape
        print(f"-- box {box}: bbox {v['bbox']}, grid bounds x {T.c:.0f}..{T.c + W * T.a:.0f}, y {T.f + H * T.e:.0f}..{T.f:.0f}; lake in box: {g.intersection(bb).area / 1e4:.1f} ha")
        m = rasterio.features.rasterize([(g.buffer(15), 1)], out_shape=fd.shape, transform=T, dtype="uint8").astype(bool)
        rr, cc = np.nonzero(m)
        if not len(rr):
            print("   no lake cells on this grid"); continue
        pits = [(r, c_) for r, c_ in zip(rr, cc) if int(fd[r, c_]) not in D8]
        for r, c_ in pits[:8]:
            x, y = T * (c_ + 0.5, r + 0.5)
            print(f"   dead end in the lake at {ll(x, y)} (value {int(fd[r, c_])}), drainage there {A[r, c_]:.2f} km2")
        if not pits:
            print("   no dead end among the lake's cells on this grid")
        # where the lake's cells lead: follow each to its end, count by end
        ends = {}
        for r, c_ in zip(rr[::7], cc[::7]):
            for _ in range(20000):
                d = D8.get(int(fd[r, c_]))
                if d is None: break
                r2, c2 = r + d[0], c_ + d[1]
                if not (0 <= r2 < H and 0 <= c2 < W): break
                r, c_ = r2, c2
            ends[(r, c_)] = ends.get((r, c_), 0) + 1
        for (r, c_), n in sorted(ends.items(), key=lambda kv: -kv[1])[:4]:
            x, y = T * (c_ + 0.5, r + 0.5)
            edge = r in (0, H - 1) or c_ in (0, W - 1)
            print(f"   {n} of the sampled lake cells end at {ll(x, y)} ({'grid edge' if edge else 'dead end' if int(fd[r, c_]) not in D8 else 'walk limit'}), drainage there {A[r, c_]:.2f} km2")
        # largest drainage within 400 m outside the lake
        win = rasterio.features.rasterize([(g.buffer(400).difference(g.buffer(15)), 1)], out_shape=fd.shape, transform=T, dtype="uint8").astype(bool)
        if win.any():
            k = np.argsort(np.where(win, A, -1).ravel())[::-1][:1]
            r, c_ = divmod(int(k[0]), W); x, y = T * (c_ + 0.5, r + 0.5)
            print(f"   largest drainage within 400 m outside the lake: {A[r, c_]:.2f} km2 at {ll(x, y)}")
    f = f"{root}/data/derived/{config.AREA}/_shared/inflows.json"
    if os.path.exists(f):
        j = json.load(open(f))
        print("   inflows.json keys:", list(j.keys()))
