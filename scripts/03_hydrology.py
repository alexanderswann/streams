"""DEM conditioning for one box: fill pits and depressions, resolve flats. The first half of the hydrology; the flow
directions, drainage areas, streams and Strahler orders are worked out for the whole area at once by 03b_stitch.py,
which needs every box of the area conditioned first.

Why two steps. Until 2026-11-19 each box did its whole hydrology alone. A box's rim then acts as a wall: water that
reaches it can't leave (it ran along the border to a low cell and ended there), and a river that crosses into the
next box arrives with no drainage, so its line there started again 100 m to 1.8 km below the edge, as an order-1
creek. No stream on the maps crossed an edge between two boxes (270 dead ends on shared edges over six areas), and
a river running along an edge was cut to pieces. So:
  - Here the box is conditioned together with a HALO of its neighbours' terrain, so that the filled and
    flat-resolved surface near a shared edge is the one the neighbour gets too. Only the box itself is saved
    (dem_cond.tif, in float64: the flat increments are far below float32's steps).
  - 03b_stitch.py takes each cell's direction from the conditioned surfaces of all the boxes side by side, so a
    cell on a shared edge drains straight into the next box.
A box with no neighbour has no halo and comes out as before.

Two things in the conditioning that aren't standard:
  - resolve_flats() runs with a much smaller increment than its default (FLAT_EPS). The default (1e-5 m a cell) piles
    up across a wide flat until the cells stand higher than the next step down, and the flat turns into a pit: 3DEP
    flattens the water surface of every river wide enough to map, in short level steps, so D8 paths died all along
    the big rivers (the White River at 519 km2, the Winooski at 464, the Hoback at 1,136) and each river's drainage
    started again from nothing below. LA's dry channels have no such steps, so it showed there only at reservoirs.
  - Flow paths still end at every lake and reservoir that holds water: see 03b_stitch.py.
  - Flats of filled ground (a swamp, a wetland, a valley flat behind a sill, which the fill levels) are routed along
    NHD HR's channel lines instead of resolve_flats' shortest ways, which drew straight lines across them
    (flatlines.py, 2026-11-22).
"""
import os
import numpy as np, rasterio, rasterio.windows
if not hasattr(np, "in1d"):  # pysheds still calls np.in1d, removed in NumPy 2.4
    np.in1d = np.isin
from pysheds.grid import Grid
from config import *
import flatlines

HALO = 5000          # m of each neighbouring box's terrain conditioned along with this box
FLAT_EPS = 1e-9      # m of rise a cell across a flat; 4 km of flat is 0.4 mm, under any step in the DEM

# the box's DEM with the halo around it, from the DEMs of the area's other boxes where they reach
hx0, hy0, hx1, hy1 = XMIN - HALO, YMIN - HALO, XMAX + HALO, YMAX + HALO
W, H = int(round((hx1 - hx0) / RES)), int(round((hy1 - hy0) / RES))
z = np.full((H, W), np.nan, np.float32)
for r, cfg in REGIONS.items():
    bx = cfg["bbox"]
    ix0, iy0, ix1, iy1 = max(hx0, bx[0]), max(hy0, bx[1]), min(hx1, bx[2]), min(hy1, bx[3])
    p = f"{raw_dir(r)}/dem_10m.tif"
    if ix1 - ix0 < RES or iy1 - iy0 < RES or not os.path.exists(p):
        continue
    with rasterio.open(p) as src:
        win = rasterio.windows.from_bounds(ix0, iy0, ix1, iy1, src.transform).round_offsets().round_lengths()
        d = src.read(1, window=win, masked=True).astype(np.float32).filled(np.nan)
    c0, r0 = int(round((ix0 - hx0) / RES)), int(round((hy1 - iy1) / RES))
    h, w = min(d.shape[0], H - r0), min(d.shape[1], W - c0)
    part = z[r0:r0 + h, c0:c0 + w]
    if r == REGION:
        z[r0:r0 + h, c0:c0 + w] = np.where(np.isnan(d[:h, :w]), part, d[:h, :w])       # the box's own cells win
    else:
        z[r0:r0 + h, c0:c0 + w] = np.where(np.isnan(part), d[:h, :w], part)
# trim to the rows and columns that hold data (no neighbour on a side: no halo there)
rows, cols = np.flatnonzero((~np.isnan(z)).any(axis=1)), np.flatnonzero((~np.isnan(z)).any(axis=0))
z = z[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
T = rasterio.Affine(RES, 0, hx0 + cols[0] * RES, 0, -RES, hy1 - rows[0] * RES)
halo_share = 1 - (XMAX - XMIN) * (YMAX - YMIN) / RES / RES / (~np.isnan(z)).sum()
os.makedirs(DERIVED, exist_ok=True)
tmp = f"{DERIVED}/_halo_dem.tif"
with rasterio.open(tmp, "w", driver="GTiff", height=z.shape[0], width=z.shape[1], count=1, dtype="float32", crs=CRS,
                   transform=T, nodata=-99999.0) as dst:
    dst.write(np.where(np.isnan(z), -99999.0, z), 1)
del z

grid = Grid.from_raster(tmp)
dem = grid.read_raster(tmp)
pit_filled = grid.fill_pits(dem)
flooded = grid.fill_depressions(pit_filled)
# flats of filled ground (swamps, wetlands) routed along NHD HR's channel lines, the rest as resolve_flats has it
inflated = flatlines.resolve(grid, dem, flooded, T, FLAT_EPS, 10000)

# the box itself, cut back out of the halo
c0, r0 = int(round((XMIN - T.c) / RES)), int(round((T.f - YMAX) / RES))
bh, bw = int(round((YMAX - YMIN) / RES)), int(round((XMAX - XMIN) / RES))
core = (slice(r0, r0 + bh), slice(c0, c0 + bw))
with rasterio.open(f"{RAW}/dem_10m.tif") as src:
    prof = src.profile
prof.update(compress="deflate", tiled=True, nodata=None)
def save(name, arr, dtype, **kw):
    with rasterio.open(f"{DERIVED}/{name}.tif", "w", **dict(prof, dtype=dtype, **kw)) as dst:
        dst.write(np.asarray(arr).astype(dtype), 1)
save("dem_cond", np.asarray(inflated)[core], "float64", predictor=1)
save("dem_filled", np.asarray(flooded)[core], "float32")
save("fill_depth", (np.asarray(flooded) - np.asarray(dem))[core], "float32")
os.remove(tmp)
print(f"{REGION}: conditioned {grid.shape[1]} x {grid.shape[0]} cells ({halo_share:.0%} of them halo), kept {bw} x {bh}")
