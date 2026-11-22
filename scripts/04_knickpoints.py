"""Find abrupt in-channel elevation drops (waterfall / cascade candidates) and their plunge-pool bases.

1. For every channel cell, slope over the next WIN m downstream (D8 path, filled DEM).
2. Contiguous runs of steep cells (>= STEP_SLOPE) along the flow path = one step.
3. Step drop = elevation top -> base, where base is the end of the steep run (the plunge pool).
4. Compare the step's slope with the channel REACH m above (main-stem donor) and below.
   A real knickpoint is much steeper than both neighbours; a uniformly steep gully is not.
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from shapely.geometry import Point
from config import *

WIN = 30            # m, window for the per-cell slope
REACH = 200         # m, neighbouring reach used for the knick ratio
MIN_AREA = 1.0      # km^2, smaller drainages rarely hold water/fish
STEP_SLOPE = 0.25   # per-cell slope that counts as "steep" (≈14°)
MIN_DROP = 8        # m

src = rasterio.open(f"{RAW}/dem_10m.tif")
z = src.read(1).astype("float64").ravel()
zf = rasterio.open(f"{DERIVED}/dem_filled.tif").read(1).astype("float64").ravel()
fdir = rasterio.open(f"{DERIVED}/flowdir.tif").read(1)
area = rasterio.open(f"{DERIVED}/area_km2.tif").read(1).ravel()
# A channel's size counts the water that reaches it from elsewhere, as the reaches' areas do (crossbox.py: over a dam,
# past a pond, across a box edge, in from outside the map). A lake ends its D8 paths at its outlet (03b_stitch.py),
# so the river below starts again near nothing, and on its own area alone its first stretch was no channel here until
# 1 km2 had gathered again: Rainbow Falls on the Raquette, two steps of 14.5 and 15.3 m in the bypassed channel 700 m
# below Rainbow Falls Dam, was found only while a path leaked out of the reservoir beside the dam (4.3 km2), and went
# when every lake cell was sent to the outlet (03b_stitch.route_lake, 2026-11-21). A drop's area_km2 is this size.
import crossbox
area = area + crossbox.carried_km2(REGION)
fill = rasterio.open(f"{DERIVED}/fill_depth.tif").read(1).ravel()
H, W = fdir.shape
N = H * W

# downstream pointer + step length
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

# main-stem upstream pointer: the donor with the largest drainage area
chan = np.flatnonzero(area >= MIN_AREA * 0.25)
up = np.arange(N)
srt = chan[np.argsort(area[chan])]  # ascending, so the largest donor writes last
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

# group contiguous steep cells along the flow path (union-find on cell -> downstream)
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
    # base = where the steep run's last window lands (slope30 looks WIN m ahead)
    low = m[np.argmin(zf[m])]
    base, _ = walk(np.array([low]), WIN, down, down_len)
    base = base[0]
    # along-channel run length top -> base
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
    rows.append(dict(
        top_idx=int(top), base_idx=int(base),
        drop_m=round(drop, 1), run_m=round(run, 0),
        step_slope=round(step_slope, 2), max_slope=round(float(slope30[m].max()), 2),
        slope_above=round(float(above), 3) if np.isfinite(above) else None,
        slope_below=round(float(below), 3) if np.isfinite(below) else None,
        knick_ratio=round(float(step_slope / ref), 1),
        area_km2=round(float(area[top]), 2), elev_m=round(float(z[top]), 0),
        fill_max_m=round(float(fill[m].max()), 1)))

df = pd.DataFrame(rows)
T = src.transform
def xy(idx):
    rr, cc = np.divmod(idx, W)
    return T * (cc + 0.5, rr + 0.5)
df["geometry"] = [Point(xy(i)) for i in df.top_idx]
df["pool_x"], df["pool_y"] = zip(*[xy(i) for i in df.base_idx])
g = gpd.GeoDataFrame(df, crs=CRS)
# Classify the shape of the drop
g["kind"] = np.select(
    [(g.max_slope >= 0.6) & (g.knick_ratio >= 2.5),
     g.knick_ratio >= 1.8],
    ["waterfall-like step", "cascade / knickpoint"], "steep reach")
# A drop in a filled depression may be a barrier's: a dam, culvert embankment or bridge deck raises the channel at the
# lip, and the DEM fill behind it is about as deep as the barrier is tall. So take the fill off the drop: when what is
# left would still pass this detector's own bar, the step is the channel's, and only the barrier part is suspect. The
# rim of a gorge narrower than a 10 m cell raises the lip the same way, and that is where falls are (Santa Paula
# Creek's, 26 m from a mapped waterfall, was set aside on 2.1 m of fill under a 16 m drop).
g["artifact_risk"] = (g.fill_max_m > 2) & (g.drop_m - g.fill_max_m < MIN_DROP)
g.to_file(f"{DERIVED}/knickpoints.gpkg")
print(len(g), "drops;", g.kind.value_counts().to_dict(), "| artifact risk", int(g.artifact_risk.sum()))
print(g[g.kind != "steep reach"].sort_values("drop_m", ascending=False).head(15)[
    ["kind", "drop_m", "run_m", "max_slope", "slope_above", "slope_below", "knick_ratio", "area_km2", "elev_m"]])
