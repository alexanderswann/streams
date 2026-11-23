"""Second pass: short falls and plunge pools on large creeks.

Pass 1 (04_knickpoints.py) needs >= 8 m of drop at >= 25% slope, which a 10 m DEM only shows for tall falls.
On big, gentle creeks a 3-6 m fall shows up as a few metres of *extra* drop over 20-40 m compared with the
creek's trend. This pass looks only at channels draining >= BIG_AREA km^2 and flags cells where:
  - drop over WIN m >= MIN_DROP
  - local slope >= RATIO x the creek's trend (steeper of the REACH m above / below), or RATIO_BIG x it where the
    excess drop is BIG_EXCESS or more
  - excess drop (drop minus what the trend predicts over that distance) >= MIN_EXCESS
The pool signal is the depression depth just below the step (filled minus raw DEM).
"""
import numpy as np, rasterio, geopandas as gpd, pandas as pd
from shapely.geometry import Point
from config import *
from flowpath import pointers, walk, group_runs, run_length

BIG_AREA = 10.0     # km^2
WIN = 30            # m
REACH = 200         # m
MIN_DROP = 3.0      # m over WIN
MIN_EXCESS = 2.5    # m above the creek trend (ordinary step-pool steps run ~2 m)
RATIO = 2.5         # local slope / trend slope
BIG_EXCESS = 4.0    # m above the trend: a step this far above it needs only RATIO_BIG x the trend's slope. The ratio
RATIO_BIG = 2.25    # keeps ordinary steep reaches out, and 4 m above the trend isn't ordinary. Rice's Falls (30 ft, The
                    # Branch): 7.4 m over 42 m, 4.4 m above the trend, at 2.49 x it once the swamp routing
                    # (flatlines.py) took the pool above it along NHD's line. All 12 maps, 2026-11-23 (pub_9f6e867):
                    # 5 more precisely placed known falls found (Rice's; Bear Creek and Bemis Camp falls, Smokies;
                    # Stick and Lower Stick falls, north Georgia), none lost; 04b steps 2,046 -> 2,073. Tried on the
                    # trial's rasters: 2.0 x and 3.5 m found no more falls, for 18 and 54 more steps
MIN_TREND = 0.005   # floor for the trend slope on very flat reaches
POOL_LOOK = 60      # m below the base searched for a depression

src = rasterio.open(f"{RAW}/dem_10m.tif")
z = src.read(1).astype("float64").ravel()
zf = rasterio.open(f"{DERIVED}/dem_filled.tif").read(1).astype("float64").ravel()
fdir = rasterio.open(f"{DERIVED}/flowdir.tif").read(1)
area = rasterio.open(f"{DERIVED}/area_km2.tif").read(1).ravel()
# with the water that reaches each channel from elsewhere (over a dam, past a pond, in from outside the map), as in
# 04_knickpoints.py: a river below a dam is a big creek from the dam on, not from where 10 km2 has gathered again
import crossbox
area = area + crossbox.carried_km2(REGION)
fill = rasterio.open(f"{DERIVED}/fill_depth.tif").read(1).ravel()
H, W = fdir.shape
down, step, up = pointers(fdir, area, BIG_AREA * 0.25)
down_len = lambda a, b: step[a]
up_len = lambda a, b: step[b]

def slope_over(start, dist, ptr, length, upstream):
    end, d = walk(start, dist, ptr, length)
    ok = np.isfinite(d) & (d > 0)
    dz = (zf[end] - zf[start]) if upstream else (zf[start] - zf[end])
    return end, np.where(ok, dz / np.where(ok, d, 1), np.nan), np.where(ok, d, np.nan)

cells = np.flatnonzero(area >= BIG_AREA)
land, s_loc, d_loc = slope_over(cells, WIN, down, down_len, upstream=False)
_, s_above, _ = slope_over(cells, REACH, up, up_len, upstream=True)
_, s_below, _ = slope_over(land, REACH, down, down_len, upstream=False)
trend = np.fmax(np.fmax(np.nan_to_num(s_above, nan=0), np.nan_to_num(s_below, nan=0)), MIN_TREND)
drop = s_loc * d_loc
excess = drop - trend * d_loc
flag_c = ((drop >= MIN_DROP) & (excess >= MIN_EXCESS)
          & ((s_loc >= RATIO * trend) | ((excess >= BIG_EXCESS) & (s_loc >= RATIO_BIG * trend))))
flag = np.zeros(H * W, bool)
flag[cells[np.nan_to_num(flag_c, nan=0).astype(bool)]] = True
print("flagged cells", int(flag.sum()))

rows = []
for m in group_runs(flag, down):
    top = m[np.argmax(zf[m])]
    low = m[np.argmin(zf[m])]
    base = walk(np.array([low]), WIN, down, down_len)[0][0]
    run = run_length(top, base, down, step)
    gdrop = zf[top] - zf[base]
    if run <= 0 or gdrop < MIN_DROP:
        continue
    _, a, _ = slope_over(np.array([top]), REACH, up, up_len, upstream=True)
    _, b, _ = slope_over(np.array([base]), REACH, down, down_len, upstream=False)
    gtrend = max(np.nan_to_num(a[0], nan=0), np.nan_to_num(b[0], nan=0), MIN_TREND)
    gexcess = gdrop - gtrend * run
    if gexcess < MIN_EXCESS:
        continue
    j, d, pool = base, 0.0, 0.0
    while d <= POOL_LOOK and down[j] != j:
        pool = max(pool, fill[j]); d += step[j]; j = down[j]
    rows.append(dict(
        top_idx=int(top), base_idx=int(base),
        drop_m=round(float(gdrop), 1), excess_drop_m=round(float(gexcess), 1), run_m=round(float(run), 0),
        step_slope=round(float(gdrop / run), 2), max_slope=round(float(np.nanmax(s_loc[np.isin(cells, m)])), 2),
        slope_above=round(float(a[0]), 3) if np.isfinite(a[0]) else None,
        slope_below=round(float(b[0]), 3) if np.isfinite(b[0]) else None,
        knick_ratio=round(float((gdrop / run) / gtrend), 1),
        area_km2=round(float(area[top]), 2), elev_m=round(float(z[top]), 0),
        fill_max_m=round(float(fill[m].max()), 1), pool_depth_m=round(float(pool), 1)))

# the columns named, so a box with no candidate at all (the small Buffalo Fork box, 2026-11-19) still writes its file
df = pd.DataFrame(rows, columns=["top_idx", "base_idx", "drop_m", "excess_drop_m", "run_m", "step_slope", "max_slope",
                                 "slope_above", "slope_below", "knick_ratio", "area_km2", "elev_m", "fill_max_m",
                                 "pool_depth_m"])
# numbers even when empty: an empty column is text to pandas, and the file's text fields made the box's drops text
df = df.astype({c: ("int64" if c.endswith("_idx") else "float64") for c in df.columns})
T = src.transform
def xy(idx):
    rr, cc = np.divmod(idx, W)
    return T * (cc + 0.5, rr + 0.5)
pools = [xy(i) for i in df.base_idx]
df["pool_x"], df["pool_y"] = [p[0] for p in pools], [p[1] for p in pools]
g = gpd.GeoDataFrame(df, geometry=[Point(xy(i)) for i in df.top_idx], crs=CRS)
g["kind"] = "short fall / pool (big creek)"
g["pass"] = 2
# A fill-raised step *at* the drop (not in the pool below) may be a dam, bridge deck or DEM seam's. The fill is about
# that barrier's height, so it only makes the drop an artifact when the drop or its excess, less the fill, misses this
# pass's bar (as in 04_knickpoints.py: the Middlebury River's gorge fall, 12.1 m with 9.6 m excess, was set aside on
# 2.2 m of fill)
g["artifact_risk"] = (g.fill_max_m > 2) & ((g.drop_m - g.fill_max_m < MIN_DROP) | (g.excess_drop_m - g.fill_max_m < MIN_EXCESS))

# drop anything pass 1 already found
p1 = gpd.read_file(f"{DERIVED}/knickpoints.gpkg")
if len(p1) and len(g):
    g = g[g.distance(p1.geometry.union_all()) > 100]
g.to_file(f"{DERIVED}/knickpoints_bigcreek.gpkg")
print(len(g), "big-creek short falls | artifact risk", int(g.artifact_risk.sum()),
      "| with pool >= 0.5 m", int((g.pool_depth_m >= 0.5).sum()))
print(g.sort_values("excess_drop_m", ascending=False).head(12)[
    ["drop_m", "excess_drop_m", "run_m", "knick_ratio", "slope_above", "slope_below", "area_km2", "elev_m",
     "pool_depth_m"]].to_string())
