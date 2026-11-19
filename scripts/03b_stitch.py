"""Hydrology for the whole area at once, from the boxes' conditioned DEMs (03_hydrology.py, run for every box first):
D8 flow direction -> lake outlets -> flow accumulation -> streams -> Strahler order -> the stream lines.  AREA only.

Boxes that share an edge are put side by side (a "group"; a box on its own is a group of one) and treated as one
surface:
  - A cell's direction is the steepest way down among its eight neighbours on the conditioned surface, the same
    rule pysheds uses, with the neighbours across a shared edge taken from the next box. So water crosses the
    edge where the ground says, instead of stopping at the box's rim.
  - Streams start where 0.25 km2 has gathered counting everything upstream in the group, so a creek's line runs on
    across the edge, and its Strahler order carries over.
  - A lake that holds water still ends the paths that enter it, at the cell where its water leaves (flowlib.
    still_water; "holds water" read off the DEM, at least LEVEL_HA of the outline at one elevation). A lake lying
    across a shared edge now has one outlet, not one in each box. crossbox.py carries the area on past the dam.

Each box still gets its own files, as the later steps expect them:
  flowdir.tif    the directions; a cell on a shared edge may point out of the box (crossbox.py follows it)
  area_km2.tif   drainage area, counting every cell upstream in the group, in this box or another. (It used to count
                 this box's cells only; 05_score.py drops creeks under 1 km2, so with that a river's first stretch
                 inside a box was thrown away as a trickle.) What the terrain can't see is still added by
                 crossbox.py (area_streams.csv): rivers that come in from outside every box, and lakes' water past
                 their dams.
  strahler.tif   stream order, 0 off the streams; counted across the group
  dem_streams.gpkg   one line per link between confluences; a line that leaves the box ends on the first cell of
                 the next box, where that box's line for the same creek begins
and <area>/_shared/stitched.json lists the boxes done this way (crossbox.py then takes the crossings as exact).
"""
import json, os, sys
import numpy as np, rasterio, rasterio.features, rasterio.windows, shapely, geopandas as gpd
from numba import njit
if not hasattr(np, "in1d"):  # pysheds still calls np.in1d, removed in NumPy 2.4
    np.in1d = np.isin
from config import *
from crossbox import shared_edges
from flowlib import still_water

STREAM_KM2 = 0.25    # channel initiation (2,500 cells at 10 m)
LEVEL_HA = 2
PIT, FLAT = 254, 255                                   # pysheds' -2 and -1, as the uint8 flowdir.tif stores them
CODES = (64, 128, 1, 2, 4, 8, 16, 32)                  # N NE E SE S SW W NW, the order pysheds tries them in
OFFS = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))
DR, DC = np.zeros(256, np.int64), np.zeros(256, np.int64)
for code, (dr, dc) in zip(CODES, OFFS):
    DR[code], DC[code] = dr, dc


def d8(P):
    """Flow direction of the inner cells of P (conditioned elevations, NaN where there is no ground), as pysheds'
    _d8_flowdir_numba gives it: the first of the steepest neighbours, FLAT where the best is level, PIT where all
    are higher."""
    z = P[1:-1, 1:-1]
    best = np.full(z.shape, -np.inf)
    out = np.zeros(z.shape, np.uint8)
    dd = np.hypot(RES, RES)
    for code, (dr, dc) in zip(CODES, OFFS):
        n = P[1 + dr:P.shape[0] - 1 + dr, 1 + dc:P.shape[1] - 1 + dc]
        with np.errstate(invalid="ignore"):
            s = (z - n) / (dd if dr and dc else RES)
            better = s > best                           # False where the neighbour is NaN
        out[better] = code
        best[better] = s[better]
    out[best == 0] = FLAT
    out[best < 0] = PIT
    out[np.isnan(z)] = 0
    return out


@njit(cache=True)
def accumulate(fd, DR, DC):
    """Cells draining through each cell (itself included), and how many cells sit on a loop (never released)."""
    H, W = fd.shape
    indeg = np.zeros((H, W), np.uint8)
    for r in range(H):
        for c in range(W):
            k = fd[r, c]
            if k and (DR[k] or DC[k]):
                r2, c2 = r + DR[k], c + DC[k]
                if 0 <= r2 < H and 0 <= c2 < W and fd[r2, c2]:
                    indeg[r2, c2] += 1
    acc = np.zeros((H, W), np.int32)
    for r in range(H):
        for c in range(W):
            if fd[r, c]:
                acc[r, c] = 1
    for r0 in range(H):
        for c0 in range(W):
            if fd[r0, c0] == 0 or indeg[r0, c0] != 0:
                continue
            r, c = r0, c0
            while True:
                indeg[r, c] = 255                       # released
                k = fd[r, c]
                if not (DR[k] or DC[k]):
                    break
                r2, c2 = r + DR[k], c + DC[k]
                if not (0 <= r2 < H and 0 <= c2 < W) or fd[r2, c2] == 0:
                    break
                acc[r2, c2] += acc[r, c]
                indeg[r2, c2] -= 1
                if indeg[r2, c2] != 0:
                    break
                r, c = r2, c2
    loops = 0
    for r in range(H):
        for c in range(W):
            if fd[r, c] and indeg[r, c] != 255:
                loops += 1
                acc[r, c] = -1
    return acc, loops


@njit(cache=True)
def strahler(fd, stream, DR, DC):
    """Stream order of the stream cells, by the rule pysheds' stream_order applies (kept, so the orders mean what
    they did before): 1 at a head; one more than the streams that meet where two or more meet and all have the same
    order, else the highest of them. (Strahler's own rule also steps up where two of the highest meet a lower one;
    pysheds' doesn't.) A stream cell where the path ends (a pit: a lake's outlet) counts as meeting itself, as in
    pysheds, so it is one above a single stream that ends there."""
    H, W = fd.shape
    indeg = np.zeros((H, W), np.uint8)
    for r in range(H):
        for c in range(W):
            k = fd[r, c]
            if stream[r, c] and (DR[k] or DC[k]):
                r2, c2 = r + DR[k], c + DC[k]
                if 0 <= r2 < H and 0 <= c2 < W and stream[r2, c2]:
                    indeg[r2, c2] += 1
    order = np.zeros((H, W), np.uint8)
    top = np.zeros((H, W), np.uint8)
    low = np.full((H, W), 255, np.uint8)
    cnt = indeg.copy()
    for r0 in range(H):
        for c0 in range(W):
            if not stream[r0, c0] or indeg[r0, c0] != 0:
                continue
            r, c = r0, c0
            while True:
                indeg[r, c] = 255
                k = fd[r, c]
                ends = not (DR[k] or DC[k])
                if cnt[r, c] == 0:
                    order[r, c] = 1
                elif low[r, c] == top[r, c] and (cnt[r, c] >= 2 or ends):
                    order[r, c] = top[r, c] + 1
                else:
                    order[r, c] = top[r, c]
                if ends:
                    break
                r2, c2 = r + DR[k], c + DC[k]
                if not (0 <= r2 < H and 0 <= c2 < W) or not stream[r2, c2]:
                    break
                top[r2, c2] = max(top[r2, c2], order[r, c])
                low[r2, c2] = min(low[r2, c2], order[r, c])
                indeg[r2, c2] -= 1
                if indeg[r2, c2] != 0:
                    break
                r, c = r2, c2
    return order


def groups():
    """Boxes that share an edge, as sets (connected through shared edges)."""
    done = [r for r in REGIONS if os.path.exists(f"{derived_dir(r)}/dem_cond.tif")]
    link = {r: {r} for r in done}
    for a, b in shared_edges(done):
        merged = link[a] | link[b]
        for r in merged:
            link[r] = merged
    out = []
    for r in done:
        if link[r] not in out:
            out.append(link[r])
    return [sorted(g, key=list(REGIONS).index) for g in out]


def run(group):
    boxes = {r: REGIONS[r]["bbox"] for r in group}
    x0, y0 = min(b[0] for b in boxes.values()), min(b[1] for b in boxes.values())
    x1, y1 = max(b[2] for b in boxes.values()), max(b[3] for b in boxes.values())
    H, W = int(round((y1 - y0) / RES)), int(round((x1 - x0) / RES))
    T = rasterio.Affine(RES, 0, x0, 0, -RES, y1)
    where = {}
    for r, b in boxes.items():
        r0, c0 = int(round((y1 - b[3]) / RES)), int(round((b[0] - x0) / RES))
        where[r] = (slice(r0, r0 + int(round((b[3] - b[1]) / RES))), slice(c0, c0 + int(round((b[2] - b[0]) / RES))))
    # 1. directions, box by box, each with a ring of one cell from its neighbours' conditioned surfaces
    fd = np.zeros((H, W), np.uint8)
    for r in group:
        sl = where[r]
        h, w = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        P = np.full((h + 2, w + 2), np.nan)
        with rasterio.open(f"{derived_dir(r)}/dem_cond.tif") as src:
            P[1:-1, 1:-1] = src.read(1)
        for n in group:
            if n == r:
                continue
            ns = where[n]
            rr0, rr1 = max(sl[0].start - 1, ns[0].start), min(sl[0].stop + 1, ns[0].stop)
            cc0, cc1 = max(sl[1].start - 1, ns[1].start), min(sl[1].stop + 1, ns[1].stop)
            if rr0 >= rr1 or cc0 >= cc1:
                continue
            with rasterio.open(f"{derived_dir(n)}/dem_cond.tif") as src:
                d = src.read(1, window=rasterio.windows.Window(cc0 - ns[1].start, rr0 - ns[0].start, cc1 - cc0, rr1 - rr0))
            P[rr0 - sl[0].start + 1:rr1 - sl[0].start + 1, cc0 - sl[1].start + 1:cc1 - sl[1].start + 1] = d
        fd[sl] = d8(P)
        del P
    # 2. loops: only where two boxes' conditioned surfaces disagree across their edge; ended in a pit
    acc, loops = accumulate(fd, DR, DC)
    if loops:
        fd[acc < 0] = PIT
        acc, _ = accumulate(fd, DR, DC)
    # 3. lakes that hold water end the paths at their outlet: the cell inside with the most water
    lakes = still_water(tuple(sorted({h for r in group for h in REGIONS[r]["hu4"]})), (x0, y0, x1, y1))
    n_wet = 0
    if len(lakes):
        level, best = {}, {}
        for r in group:
            sl = where[r]
            shape = (sl[0].stop - sl[0].start, sl[1].stop - sl[1].start)
            Tb = T * rasterio.Affine.translation(sl[1].start, sl[0].start)
            lab = rasterio.features.rasterize(((g, i + 1) for i, g in enumerate(lakes.geometry)), out_shape=shape,
                                              transform=Tb, fill=0, dtype="int32")
            inl = lab > 0
            if not inl.any():
                continue
            with rasterio.open(f"{raw_dir(r)}/dem_10m.tif") as src:
                zz = np.round(src.read(1)[inl].astype(np.float64), 2)
            ids, a = lab[inl], acc[sl][inl]
            rr, cc = np.nonzero(inl)
            pair, n = np.unique(np.stack([ids, np.round(zz * 100).astype(np.int64)]), axis=1, return_counts=True)
            for i, v, k in zip(pair[0], pair[1], n):
                level[(int(i), int(v))] = level.get((int(i), int(v)), 0) + int(k)
            o = np.lexsort((a, ids))                    # by lake, then by water: the last of each lake is its most
            last = np.r_[np.flatnonzero(np.diff(ids[o])), len(o) - 1]
            for j in o[last]:
                if int(ids[j]) not in best or a[j] > best[int(ids[j])][0]:
                    best[int(ids[j])] = (int(a[j]), sl[0].start + int(rr[j]), sl[1].start + int(cc[j]))
        most = {}
        for (i, v), k in level.items():
            most[i] = max(most.get(i, 0), k)
        for i, (a, r_, c_) in best.items():
            if most.get(i, 0) * RES * RES / 1e4 < LEVEL_HA:
                continue
            ring = fd[max(r_ - 1, 0):r_ + 2, max(c_ - 1, 0):c_ + 2]
            if 0 < r_ < H - 1 and 0 < c_ < W - 1 and (ring > 0).all():      # one on the rim leaves the map anyway
                fd[r_, c_] = PIT
                n_wet += 1
        acc, _ = accumulate(fd, DR, DC)
    # 4. streams and their orders, across the group
    stream = acc >= int(round(STREAM_KM2 * 1e6 / (RES * RES)))      # in cells: no float copy of a 250-million-cell grid
    order = strahler(fd, stream, DR, DC)
    print(f"{' + '.join(group)}: {W} x {H} cells, {int(stream.sum())} stream cells, max order {int(order.max())}, "
          f"{n_wet} of {len(lakes)} lakes end paths at their outlet" + (f", {loops} cells on loops ended in pits" if loops else ""))
    # 5. each box's files
    from pysheds.grid import Grid
    from pysheds.sview import Raster, ViewFinder
    for r in group:
        sl = where[r]
        f, st, od = fd[sl], stream[sl], order[sl]
        with rasterio.open(f"{raw_dir(r)}/dem_10m.tif") as src:
            prof = src.profile
        prof.update(compress="deflate", tiled=True, nodata=None)
        for name, arr, dt in (("flowdir", f, "uint8"), ("area_km2", acc[sl] * (RES * RES) / 1e6, "float32"), ("strahler", od, "uint8")):
            with rasterio.open(f"{derived_dir(r)}/{name}.tif", "w", **dict(prof, dtype=dt)) as dst:
                dst.write(arr.astype(dt), 1)
        # The lines: pysheds on the box with a ring of one cell of its neighbours around it. pysheds leaves the
        # outermost ring of cells out of the lines' starts but lets a line end there: so a line that leaves the box
        # ends on the first cell of the next box, exactly where that box's line for the same creek starts. On a side
        # with no neighbour the box's own rim is left out instead, as it always was.
        h, w = f.shape
        fp, sp = np.zeros((h + 2, w + 2), np.int64), np.zeros((h + 2, w + 2), bool)
        R0, C0 = sl[0].start - 1, sl[1].start - 1
        rr0, rr1, cc0, cc1 = max(R0, 0), min(R0 + h + 2, H), max(C0, 0), min(C0 + w + 2, W)
        fp[rr0 - R0:rr1 - R0, cc0 - C0:cc1 - C0] = fd[rr0:rr1, cc0:cc1]
        sp[rr0 - R0:rr1 - R0, cc0 - C0:cc1 - C0] = stream[rr0:rr1, cc0:cc1]
        sp[1, 1:-1] &= fp[0, 1:-1] > 0
        sp[-2, 1:-1] &= fp[-1, 1:-1] > 0
        sp[1:-1, 1] &= fp[1:-1, 0] > 0
        sp[1:-1, -2] &= fp[1:-1, -1] > 0
        fp[~np.isin(fp, CODES)] = 0
        Tp = T * rasterio.Affine.translation(C0, R0)
        grid = Grid(viewfinder=ViewFinder(affine=Tp, shape=fp.shape, crs=CRS, nodata=0))
        net = grid.extract_river_network(Raster(fp, viewfinder=ViewFinder(affine=Tp, shape=fp.shape, crs=CRS, nodata=0)),
                                         Raster(sp, viewfinder=ViewFinder(affine=Tp, shape=fp.shape, crs=CRS, nodata=False)),
                                         dirmap=CODES)
        g = gpd.GeoDataFrame.from_features(net["features"], crs=CRS)
        ex = g.geometry.apply(lambda ln: not (boxes[r][0] <= ln.coords[-1][0] < boxes[r][2] and boxes[r][1] < ln.coords[-1][1] <= boxes[r][3]))
        n_on = int(ex.sum())
        g.to_file(f"{derived_dir(r)}/dem_streams.gpkg")
        print(f"  {r}: stream cells {int(st.sum())}, links {len(g)}, max order {int(od.max())}, {n_on} lines run on into the next box")


if __name__ == "__main__":
    only = set(sys.argv[1:])                            # box names: just the groups that hold one of them
    done = []
    for group in groups():
        if only and not only & set(group):
            continue
        run(group)
        done += group
    path = f"{SHARED_DERIVED}/stitched.json"
    old = json.load(open(path)) if os.path.exists(path) else []
    os.makedirs(SHARED_DERIVED, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(sorted(set(old) | set(done)), fh)
