"""Burn depths on a mountain window, scored on drops: 04_knickpoints.py's detector (copied as is into knick()) run on
each depth's directions and areas, with the unburned filled DEM for the elevations (as installed, the burn would touch
only dem_cond). Recall of the window's mapped falls (OSM / NHD, 200 m, as data/validate.py), the drops found, and HR
agreement (hragree). AREA=.. REGION=.. python window_drops.py x0 y0 x1 y1 depth [depth ...]"""
import sys, os, importlib, time
H_ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, "/Users/mac/Fishing/scripts"); sys.path.insert(0, H_); sys.path.insert(0, f"{H_}/../checks")
os.chdir("/Users/mac/Fishing/scripts")
import numpy as np, rasterio, rasterio.windows, shapely, pandas as pd, geopandas as gpd
import config, burnlib, hragree
from flowlib import still_water
from pysheds.grid import Grid
from pysheds.sview import Raster, ViewFinder
st = importlib.import_module("03b_stitch")
RES = config.RES
WIN, REACH, MIN_AREA, STEP_SLOPE, MIN_DROP = 30, 200, 1.0, 0.25, 8


def knick(z, zf, fdir, area, fill):
    """04_knickpoints.py's detection, unchanged, on arrays: returns (top_idx, drop_m, kind) rows."""
    z, zf, area, fill = z.ravel(), zf.ravel(), area.ravel(), fill.ravel()
    H, W = fdir.shape
    N = H * W
    codes = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}
    r, c = np.indices((H, W))
    down = np.arange(N)
    step = np.zeros(N)
    for code, (dr, dc) in codes.items():
        m = (fdir == code).ravel()
        rr, cc = r.ravel()[m] + dr, c.ravel()[m] + dc
        ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
        idx = np.flatnonzero(m)[ok]
        down[idx] = rr[ok] * W + cc[ok]
        step[idx] = RES * np.hypot(dr, dc)
    chan = np.flatnonzero(area >= MIN_AREA * 0.25)
    up = np.arange(N)
    srt = chan[np.argsort(area[chan])]
    recv = down[srt]
    keep = recv != srt
    up[recv[keep]] = srt[keep]

    def walk(start, dist, ptr, length):
        cur, d = start.copy(), np.zeros(len(start))
        for _ in range(int(dist / RES) + 2):
            go = d < dist
            if not go.any():
                break
            nxt = ptr[cur[go]]
            moved = nxt != cur[go]
            add = np.where(moved, length(cur[go], nxt), np.inf)
            d[go] += add
            cur[go] = np.where(moved, nxt, cur[go])
        return cur, d
    down_len = lambda a, b: step[a]
    up_len = lambda a, b: step[b]
    cells = np.flatnonzero(area >= MIN_AREA)
    dn, dd = walk(cells, WIN, down, down_len)
    s30 = np.where(np.isfinite(dd), (zf[cells] - zf[dn]) / np.where(np.isfinite(dd), dd, 1), 0)
    steep = np.zeros(N, bool)
    steep[cells[s30 >= STEP_SLOPE]] = True
    slope30 = np.zeros(N)
    slope30[cells] = s30
    sc = np.flatnonzero(steep)
    lab = {i: i for i in sc}
    def find(i):
        while lab[i] != i:
            lab[i] = lab[lab[i]]
            i = lab[i]
        return i
    for i in sc:
        j = down[i]
        if j != i and steep[j]:
            lab[find(i)] = find(j)
    groups = {}
    for i in sc:
        groups.setdefault(find(i), []).append(i)
    rows = []
    for members in groups.values():
        m = np.array(members)
        top = m[np.argmax(zf[m])]
        low = m[np.argmin(zf[m])]
        base, _ = walk(np.array([low]), WIN, down, down_len)
        base = base[0]
        j, run = top, 0.0
        for _ in range(5000):
            if j == base or down[j] == j:
                break
            run += step[j]; j = down[j]
        drop = zf[top] - zf[base]
        if drop < MIN_DROP or run <= 0:
            continue
        a, ad = walk(np.array([top]), REACH, up, up_len)
        b, bd = walk(np.array([base]), REACH, down, down_len)
        above = (zf[a[0]] - zf[top]) / ad[0] if np.isfinite(ad[0]) and ad[0] > 0 else np.nan
        below = (zf[base] - zf[b[0]]) / bd[0] if np.isfinite(bd[0]) and bd[0] > 0 else np.nan
        step_slope = drop / run
        ref = np.nanmax([above, below, 0.03]) if not (np.isnan(above) and np.isnan(below)) else 0.03
        mx = float(slope30[m].max()); kr = step_slope / ref
        kind = "waterfall-like step" if (mx >= 0.6 and kr >= 2.5) else ("cascade / knickpoint" if kr >= 1.8 else "steep reach")
        rows.append(dict(top_idx=int(top), drop_m=round(drop, 1), kind=kind, area_km2=round(float(area[top]), 2),
                         fill_max_m=round(float(fill[m].max()), 1)))
    return pd.DataFrame(rows)


x0, y0, x1, y1 = map(float, sys.argv[1:5])
depths = [float(d) for d in sys.argv[5:]]
with rasterio.open(f"{config.RAW}/dem_10m.tif") as src:
    win = rasterio.windows.from_bounds(x0, y0, x1, y1, src.transform).round_offsets().round_lengths()
    z = src.read(1, window=win, masked=True).astype(np.float32).filled(np.nan)
    T = src.window_transform(win)
# the unburned filled surface (as 03_hydrology.py's dem_filled / fill_depth)
nod = np.float32(-99999.0)
vf = ViewFinder(affine=T, shape=z.shape, crs=config.CRS, nodata=nod)
grid = Grid(viewfinder=vf)
zf = np.asarray(grid.fill_depressions(grid.fill_pits(Raster(np.where(np.isnan(z), nod, z), viewfinder=vf))), np.float64)
fill = (zf - np.where(np.isnan(z), nod, z)).astype(np.float32)
kf = gpd.read_file(f"{config.SHARED}/known_falls.gpkg").to_crs(config.CRS)
kf = kf[kf.src.str.contains("OpenStreetMap|USGS NHD", regex=True) & kf.within(shapely.box(x0 + 300, y0 + 300, x1 - 300, y1 - 300))]
print(f"window {z.shape}, mapped falls inside {len(kf)}")
hr = hragree.hr_lines(config)
hr = hr[hr.intersects(shapely.box(x0, y0, x1, y1).buffer(3000))].reset_index(drop=True)
inside = shapely.box(x0 + 300, y0 + 300, x1 - 300, y1 - 300)
lakes = still_water(tuple(config.HU4), (x0, y0, x1, y1))
lake_u = shapely.union_all(lakes.geometry.values) if len(lakes) else shapely.Polygon()
D = os.environ.get("OUTDIR", "/tmp")
out = {}
for d in depths:
    t0 = time.time()
    P = np.full((z.shape[0] + 2, z.shape[1] + 2), np.nan)
    P[1:-1, 1:-1] = st.condition(burnlib.burn(z, T, d), T)
    fd = st.d8(P)
    del P
    acc, loops = st.accumulate(fd, st.DR, st.DC)
    area = acc.astype(np.float64) * RES * RES / 1e6
    k = knick(np.nan_to_num(z, nan=-99999.0).astype(np.float64), zf, fd, area, fill)
    rr, cc = np.divmod(k.top_idx.values, z.shape[1])
    xs, ys = T * (cc + 0.5, rr + 0.5)
    k["geometry"] = gpd.points_from_xy(xs, ys)
    k = gpd.GeoDataFrame(k, crs=config.CRS)
    dist = np.array([k.distance(g).min() if len(k) else np.inf for g in kf.geometry])
    t = hragree.check(fd, acc, T, hr, inside, lake_u, st.CODE_SET, st.DR, st.DC, RES)
    out[d] = (k, dist, t)
    k.to_file(f"{D}/drops_{d:g}.gpkg")
    print(f"depth {d:g} m ({time.time() - t0:.0f} s): drops {len(k)} ({k.kind.value_counts().to_dict()}); mapped falls "
          f"with a drop within 200 m: {int((dist < 200).sum())} / {len(kf)}; HR misses {int((~t.ok).sum())} of {len(t)}")
k0 = out[depths[0]][0]
for d in depths[1:]:
    k = out[d][0]
    new = k[[k0.distance(g).min() > 50 for g in k.geometry]] if len(k0) else k
    gone = k0[[k.distance(g).min() > 50 for g in k0.geometry]] if len(k) else k0
    print(f"depth {d:g}: drops with none of depth {depths[0]:g}'s within 50 m: {len(new)} "
          f"({new.kind.value_counts().to_dict()}, max {new.drop_m.max() if len(new) else 0} m); "
          f"depth {depths[0]:g}'s drops lost: {len(gone)} ({gone.kind.value_counts().to_dict()})")
