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
    Every cell of such a lake drains to that outlet, along NHD's lines through the lake where they run (route_lake):
    the flat water's own directions let a path other than the biggest leave the lake on its own. Below the outlet the
    way the water takes is a stream line down to the first stream it meets (outflow_streams), so that the lake's water,
    which crossbox.py puts back in there, lands on the river below the junction, not on a side creek's line.
  - Each box was conditioned with only HALO of its neighbours (03_hydrology.py), so a lake or filled basin reaching
    further across a shared edge can be filled and drained one way on each side, and its water stops in a dead end
    on the edge. mend_seams() conditions a piece of DEM around each such dead end again, whole, and routes it on.

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
LINE_PULL = 5.0      # route_lake: a step through a lake off NHD's lines costs this many steps along them
LAKE_LINE_FTYPES = (460, 558, 334)   # NHD HR StreamRiver, ArtificialPath (lake and river centrelines), Connector
SEAM_KM2 = STREAM_KM2  # a dead end on an edge between two boxes gathering this much is mended (mend_seams)
MEND_R = (300, 3000)   # cells: the piece of DEM conditioned again around it reaches 3 km each way at first, 30 at most
MEND_EDGE = 150        # cells: a band inside the piece's own edges (not the map's), where its paths aren't taken
FLAT_EPS = 1e-9        # as in 03_hydrology.py
PIT, FLAT = 254, 255                                   # pysheds' -2 and -1, as the uint8 flowdir.tif stores them
CODES = (64, 128, 1, 2, 4, 8, 16, 32)                  # N NE E SE S SW W NW, the order pysheds tries them in
CODE_SET = frozenset(CODES)
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


def near_shared_edge(r_, c_, group, where, k=1):
    """True if cell (r_, c_) of the group's grid lies within k cells of an edge its box shares with another box."""
    for b in group:
        bs, bc = where[b]
        if not (bs.start <= r_ < bs.stop and bc.start <= c_ < bc.stop):
            continue
        for o in group:
            if o != b:
                os_, oc = where[o]
                if oc.start - k <= c_ < oc.stop + k and ((os_.stop == bs.start and r_ - bs.start <= k)
                                                         or (os_.start == bs.stop and bs.stop - 1 - r_ <= k)):
                    return True
                if os_.start - k <= r_ < os_.stop + k and ((oc.stop == bc.start and c_ - bc.start <= k)
                                                           or (oc.start == bc.stop and bc.stop - 1 - c_ <= k)):
                    return True
        return False
    return False


def seam_dead_ends(fd, acc, group, where):
    """(row, col) of the cells on an edge two boxes of the group share where paths end (a pit or a flat) with at least
    SEAM_KM2 upstream, the biggest first. A conditioned surface lets water stop only at the map's rim, so a dead end
    on a shared edge is the two boxes' surfaces disagreeing there."""
    thr = int(round(SEAM_KM2 * 1e6 / (RES * RES)))
    found = set()
    for r in group:
        rs, cs = where[r]
        across, down = np.arange(cs.start, cs.stop), np.arange(rs.start, rs.stop)
        for rows, cols, dr, dc in ((np.full(len(across), rs.start), across, -1, 0),
                                   (np.full(len(across), rs.stop - 1), across, 1, 0),
                                   (down, np.full(len(down), cs.start), 0, -1),
                                   (down, np.full(len(down), cs.stop - 1), 0, 1)):
            other = np.zeros(len(rows), bool)                  # the cell beyond the rim lies in another box
            for b in group:
                if b != r:
                    bs, bc = where[b]
                    other |= ((rows + dr >= bs.start) & (rows + dr < bs.stop) & (cols + dc >= bc.start)
                              & (cols + dc < bc.stop))
            k = other & ~np.isin(fd[rows, cols], CODES) & (acc[rows, cols] >= thr)
            found.update(zip(rows[k].tolist(), cols[k].tolist()))
    return sorted(found, key=lambda rc: -int(acc[rc]))


def raw_dem(group, where, rows, cols):
    """The boxes' own DEMs (dem_10m.tif, as 03_hydrology.py reads them) over rows x cols of the group's grid, NaN
    where no box has ground."""
    z = np.full((rows.stop - rows.start, cols.stop - cols.start), np.nan, np.float32)
    for b in group:
        bs, bc = where[b]
        r0, r1, c0, c1 = max(rows.start, bs.start), min(rows.stop, bs.stop), max(cols.start, bc.start), min(cols.stop, bc.stop)
        if r0 < r1 and c0 < c1:
            with rasterio.open(f"{raw_dir(b)}/dem_10m.tif") as src:
                d = src.read(1, window=rasterio.windows.Window(c0 - bc.start, r0 - bs.start, c1 - c0, r1 - r0), masked=True)
            z[r0 - rows.start:r1 - rows.start, c0 - cols.start:c1 - cols.start] = d.astype(np.float32).filled(np.nan)
    return z


def condition(z, Tw):
    """A piece of DEM conditioned the way 03_hydrology.py conditions a box: pits and depressions filled, flats
    resolved with FLAT_EPS. float64, NaN where z has no ground."""
    from pysheds.grid import Grid
    from pysheds.sview import Raster, ViewFinder
    nod = np.float32(-99999.0)
    vf = ViewFinder(affine=Tw, shape=z.shape, crs=CRS, nodata=nod)
    grid = Grid(viewfinder=vf)
    flooded = grid.fill_depressions(grid.fill_pits(Raster(np.where(np.isnan(z), nod, z), viewfinder=vf)))
    out = np.asarray(grid.resolve_flats(flooded, eps=FLAT_EPS, max_iter=10000), np.float64)
    out[np.isnan(z)] = np.nan
    return out


def path_end(fd, r, c):
    """Where the D8 path from (r, c) stops: (row, col, True if it runs round a loop)."""
    H, W = fd.shape
    seen = set()
    while True:
        k = int(fd[r, c])
        if k not in CODE_SET:
            return r, c, False
        r2, c2 = r + int(DR[k]), c + int(DC[k])
        if not (0 <= r2 < H and 0 <= c2 < W) or fd[r2, c2] == 0:
            return r, c, False
        if (r2, c2) in seen:
            return r2, c2, True
        seen.add((r, c))
        r, c = r2, c2


def leaves_map(fd, r, c):
    """True for a cell where water leaves the map: on the group's rim, or beside cells with no ground."""
    H, W = fd.shape
    return r in (0, H - 1) or c in (0, W - 1) or bool((fd[r - 1:r + 2, c - 1:c + 2] == 0).any())


def mend_seams(fd, acc, group, where, T):
    """Mend, in fd, the dead ends that a lake or filled basin lying across an edge between two boxes leaves on that
    edge. 03_hydrology.py conditions each box with only HALO of its neighbours around it, so a lake (or the flat that
    filling a reservoir's basin to its spill level makes) reaching further than that is filled and drained one way by
    one box and another way by the other. Where the two meet, one side can stand a few cm above the other, and the
    water stops in a pit on the edge, short of the outlet: crossbox.py can't carry it past the dam, and the river
    below starts again near nothing (2026-11-19: the Snake below Jackson Lake and Palisades Reservoir until those boxes
    were laid out again; in adk_northwest the Raquette below Raquette Pond, whose side in the long_lake box was filled
    6 cm above its side in the tupper box, and below Carry Falls Reservoir, and Grass Pond's outlet).
    For each dead end a piece of the raw DEM around it is conditioned again, whole, as 03_hydrology.py would, and the
    cells whose direction that changes, joined to the dead end, take the new directions. The piece grows (MEND_R)
    while those cells reach the band along its own edges (the basin goes on past it, or the piece's edge bent the
    paths). The new directions are kept only if the dead end's water then runs out of the cells re-routed, without a
    loop: off the map, or on to a dead end further down that has its own mend (the Raquette below Raquette Pond
    meets Carry Falls'). Dead ends left after a pass that mended others are tried once more.
    Returns [(row, col, km2 gathered, km across the piece, cells re-routed, mended)]."""
    from scipy import ndimage
    H, W = fd.shape
    eight = np.ones((3, 3), bool)

    def mend(r, c):
        R = MEND_R[0]
        while True:
            rows, cols = slice(max(r - R, 0), min(r + R + 1, H)), slice(max(c - R, 0), min(c + R + 1, W))
            P = np.full((rows.stop - rows.start + 2, cols.stop - cols.start + 2), np.nan)
            P[1:-1, 1:-1] = condition(raw_dem(group, where, rows, cols), T * rasterio.Affine.translation(cols.start, rows.start))
            nd = d8(P)
            del P
            view = fd[rows, cols]
            e = (MEND_EDGE if rows.start > 0 else 0, nd.shape[0] - (MEND_EDGE if rows.stop < H else 0),
                 MEND_EDGE if cols.start > 0 else 0, nd.shape[1] - (MEND_EDGE if cols.stop < W else 0))
            inner = np.zeros(nd.shape, bool)
            inner[e[0]:e[1], e[2]:e[3]] = True
            lab, _ = ndimage.label(inner & (nd != view) & np.isin(nd, CODES), structure=eight)
            rr, cc = r - rows.start, c - cols.start
            ids = np.unique(lab[max(rr - 1, 0):rr + 2, max(cc - 1, 0):cc + 2])
            comp = np.isin(lab, ids[ids > 0])
            del lab, inner
            reach = ((e[0] > 0 and comp[e[0]].any()) or (e[1] < nd.shape[0] and comp[e[1] - 1].any())
                     or (e[2] > 0 and comp[:, e[2]].any()) or (e[3] < nd.shape[1] and comp[:, e[3] - 1].any()))
            if comp.any() and (not reach or R >= MEND_R[1]):
                old = view[comp]
                view[comp] = nd[comp]
                er, ec, loop = path_end(fd, r, c)
                near = ndimage.binary_dilation(comp, structure=eight, iterations=2)
                inside = rows.start <= er < rows.stop and cols.start <= ec < cols.stop and near[er - rows.start, ec - cols.start]
                if not loop and (leaves_map(fd, er, ec) or not inside):
                    return (2 * R + 1) * RES / 1000, int(comp.sum()), True
                view[comp] = old                                # its water still stops in the cells re-routed
            if R >= MEND_R[1]:
                return (2 * R + 1) * RES / 1000, 0, False
            R = min(2 * R, MEND_R[1])

    out, todo = {}, seam_dead_ends(fd, acc, group, where)
    for attempt in range(2):
        for r, c in todo:
            if int(fd[r, c]) in CODE_SET:
                if not out.get((r, c), (0, 0, False))[2]:
                    out[(r, c)] = (0.0, 0, True)                # mended along with another
                continue
            out[(r, c)] = mend(r, c)
        left = [rc for rc in todo if not out[rc][2]]
        if not left or len(left) == len(todo):
            break
        todo = left
    return [(r, c, float(acc[r, c]) * RES * RES / 1e6, *v) for (r, c), v in out.items()]


CODE_OF = np.zeros(9, np.uint8)                         # the code for a step (dr, dc), at (dr + 1) * 3 + dc + 1
for code, (dr, dc) in zip(CODES, OFFS):
    CODE_OF[(dr + 1) * 3 + dc + 1] = code


def nhd_lines(group):
    """NHD HR stream lines of the group's boxes (each box's nhd_flowlines.gpkg reaches past its box): StreamRiver,
    ArtificialPath and Connector, not canals, pipelines or coastline."""
    import pandas as pd
    parts = []
    for r in group:
        p = f"{raw_dir(r)}/nhd_flowlines.gpkg"
        if os.path.exists(p):
            g = gpd.read_file(p, columns=["ftype"])
            parts.append(g[g.ftype.isin(LAKE_LINE_FTYPES)].to_crs(CRS))
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs=CRS)
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    return g[g.geometry.notna() & ~g.geometry.is_empty].reset_index(drop=True)


def route_lake(fd, geom, outlet, T, lines):
    """Send every cell of a lake that holds water to its outlet cell (row, col of the group's grid), along NHD's lines
    through the lake where they run: a least-cost path over the lake's cells (8 neighbours), a step off the lines
    costing LINE_PULL steps along them. Before, only the path that gathered the most water ended at the outlet; the
    flat water's own directions (resolve_flats) let any other path leave the lake on its own, beside the outlet:
    Pilgrim Creek crossed Jackson Lake to the dam next to the Snake's outlet cell, so the line below the dam was
    Pilgrim Creek's and the map named the river there after it. Cells not joined to the outlet through the lake keep
    their directions. Changes fd in place; returns the number of cells re-routed."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    H, W = fd.shape
    gx0, gy0, gx1, gy1 = geom.bounds
    ca, ra = ~T * (gx0, gy1)
    cb, rb = ~T * (gx1, gy0)
    r0, c0 = max(int(np.floor(ra)) - 1, 0), max(int(np.floor(ca)) - 1, 0)
    r1, c1 = min(int(np.ceil(rb)) + 1, H), min(int(np.ceil(cb)) + 1, W)
    ro, co = outlet[0] - r0, outlet[1] - c0
    if r1 <= r0 or c1 <= c0 or not (0 <= ro < r1 - r0 and 0 <= co < c1 - c0):
        return 0
    shape = (r1 - r0, c1 - c0)
    Tw = T * rasterio.Affine.translation(c0, r0)
    view = fd[r0:r1, c0:c1]
    lake = rasterio.features.geometry_mask([geom], shape, Tw, invert=True) & (view > 0)
    lake[ro, co] = True
    on = np.zeros(shape, bool)
    if len(lines):
        near = lines.geometry.values[lines.sindex.query(geom, predicate="intersects")]
        if len(near):
            on = rasterio.features.rasterize(((g, 1) for g in near), out_shape=shape, transform=Tw, fill=0,
                                             dtype="uint8").astype(bool) & lake
    cells = np.flatnonzero(lake)
    n = len(cells)
    if n < 2:
        return 0
    idx = np.full(shape[0] * shape[1], -1, np.int64)
    idx[cells] = np.arange(n)
    cost = np.where(on.ravel()[cells], 1.0, LINE_PULL)
    rr, cc = np.divmod(cells, shape[1])
    src, dst, wt = [], [], []
    for dr, dc in ((0, 1), (1, 1), (1, 0), (1, -1)):        # each pair of neighbours once
        r2, c2 = rr + dr, cc + dc
        ok = (r2 < shape[0]) & (c2 >= 0) & (c2 < shape[1])
        j = np.full(n, -1, np.int64)
        j[ok] = idx[r2[ok] * shape[1] + c2[ok]]
        a_ = np.flatnonzero(j >= 0)
        b_ = j[a_]
        src.append(a_)
        dst.append(b_)
        wt.append((cost[a_] + cost[b_]) / 2 * (np.sqrt(2.0) if dr and dc else 1.0))
    g = coo_matrix((np.concatenate(wt), (np.concatenate(src), np.concatenate(dst))), shape=(n, n)).tocsr()
    _, pred = dijkstra(g, directed=False, indices=int(idx[ro * shape[1] + co]), return_predecessors=True)
    k = np.flatnonzero(pred >= 0)                         # every cell reached; the outlet itself has none
    if not len(k):
        return 0
    p = pred[k]
    view[rr[k], cc[k]] = CODE_OF[(rr[p] - rr[k] + 1) * 3 + (cc[p] - cc[k] + 1)]
    return len(k)


def outflow_streams(fd, stream, outflow, max_cells=3000):
    """Make the way a pitted lake's water takes below its outlet a stream line, down to the first stream cell it meets.
    The cells below a dam gather little ground of their own, so the river had no line there: the lake's water, which
    crossbox.py puts back in below the outlet, ran down to the first line it met and was counted on that whole link,
    a side creek's included (Lower Slide Lake's 1,500 km2 on a 2.7 km creek beside the Gros Ventre). With a line of
    its own the outflow meets that creek at a junction, and the water lands on the river below it. Changes stream in
    place; returns km of line added."""
    H, W = fd.shape
    added = 0
    for r_, c_, code in outflow:
        if code not in CODE_SET:
            continue
        r, c = r_ + int(DR[code]), c_ + int(DC[code])
        for _ in range(max_cells):
            if not (0 <= r < H and 0 <= c < W) or stream[r, c]:
                break
            k = int(fd[r, c])
            if k not in CODE_SET:
                break
            stream[r, c] = True
            added += 1
            r, c = r + int(DR[k]), c + int(DC[k])
    return round(added * RES / 1000, 1)


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
    # 2b. dead ends on an edge between two boxes, where a lake or filled basin across it was conditioned two ways
    mended = mend_seams(fd, acc, group, where, T) if len(group) > 1 else []
    if mended:
        acc, more = accumulate(fd, DR, DC)
        if more:
            fd[acc < 0] = PIT
            acc, _ = accumulate(fd, DR, DC)
            loops += more
        for r_, c_, km2, side, n, ok in mended:
            x_, y_ = T * (c_ + 0.5, r_ + 0.5)
            print(f"  dead end on an edge between boxes at ({x_:.0f}, {y_:.0f}), {km2:,.1f} km2: "
                  + (f"mended, {n:,} cells re-routed (DEM conditioned again {side:.0f} km across)" if ok
                     else f"NOT mended (DEM conditioned again up to {side:.0f} km across)"))
    # A dead end where an edge between boxes meets the map's own edge is water leaving the map (crossbox.py reads a
    # dead end on the rim so), not water stranded short of an outlet: central Vermont's west edge meets the line
    # between two of its boxes in Lake Champlain, where the lake's flat water stops in the corner cell (2026-11-20).
    def on_map_edge(r_, c_):
        ring = fd[max(r_ - 1, 0):r_ + 2, max(c_ - 1, 0):c_ + 2]
        return not (0 < r_ < H - 1 and 0 < c_ < W - 1 and (ring > 0).all())
    left = []
    for r_, c_ in (seam_dead_ends(fd, acc, group, where) if len(group) > 1 else []):
        x_, y_ = T * (c_ + 0.5, r_ + 0.5)
        km2 = float(acc[r_, c_]) * RES * RES / 1e6
        if on_map_edge(r_, c_):
            print(f"  dead end at ({x_:.0f}, {y_:.0f}), {km2:,.1f} km2, where an edge between boxes meets the map's "
                  "edge: the water leaves the map there")
        else:
            left.append((x_, y_, km2))
    # 3. lakes that hold water end the paths at their outlet: the cell inside with the most water
    lakes = still_water(tuple(sorted({h for r in group for h in REGIONS[r]["hu4"]})), (x0, y0, x1, y1))
    # A lake lying across an edge between two boxes used to lose its outlet when the two boxes conditioned it
    # differently (Jackson Lake and Palisades Reservoir, Raquette Pond, Carry Falls: 2b now mends it). A dam that sits
    # right at the edge can still keep crossbox.py from carrying the lake on: check the drainage below it.
    if len(lakes) and len(group) > 1:
        seam = shapely.union_all(list(shared_edges(group).values()))
        across = lakes[lakes.intersects(seam)]
        if len(across):
            print("note: lakes across an edge between two boxes (check the drainage below each dam against NHDPlus): "
                  + ", ".join(f"{n if isinstance(n, str) else 'unnamed'} ({a / 1e4:.0f} ha)" for n, a in zip(across.gnis_name, across.area)))
    n_wet = n_through = n_routed = 0
    outflow = []                                        # (row, col, direction) of each pitted lake's outlet
    off_map = []                                        # lakes whose water leaves the map through their own surface
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
        lines = nhd_lines(group)
        for i, (a, r_, c_) in best.items():
            if most.get(i, 0) * RES * RES / 1e4 < LEVEL_HA:
                continue
            # one whose water gathers most on the map's rim leaves the map through its own surface (step 4)
            ring = fd[max(r_ - 1, 0):r_ + 2, max(c_ - 1, 0):c_ + 2]
            if not (0 < r_ < H - 1 and 0 < c_ < W - 1 and (ring > 0).all()):
                off_map.append(i)
                continue
            # every cell of the lake drains to its outlet, along NHD's lines through it where they run
            n_routed += route_lake(fd, lakes.geometry.iloc[i - 1], (r_, c_), T, lines) > 0
            # A lake whose water leaves it on an edge between two boxes flows on instead: crossbox.py reads a dead end
            # on a box's rim as water leaving the box, and carries a lake past its dam only within one box (Raquette
            # Pond's water leaves it 13 m from the tupper box, through tupper's sliver of the pond)
            if near_shared_edge(r_, c_, group, where):
                n_through += 1
                continue
            outflow.append((r_, c_, int(fd[r_, c_])))     # the way its water takes out of the lake, before the pit
            fd[r_, c_] = PIT
            n_wet += 1
        acc, more = accumulate(fd, DR, DC)
        if more:                                        # a flowing-on lake's outlet pointing back into the lake
            fd[acc < 0] = PIT
            acc, _ = accumulate(fd, DR, DC)
            loops += more
    # 4. streams and their orders, across the group
    stream = acc >= int(round(STREAM_KM2 * 1e6 / (RES * RES)))      # in cells: no float copy of a 250-million-cell grid
    n_out = outflow_streams(fd, stream, outflow)
    # A lake whose water leaves the map through its own surface (the cell where most of its water gathers lies on the
    # map's rim) has no outlet in the map to end the paths at. Its flat water drained to the rim along dozens of
    # parallel paths, which the maps drew as made-up creeks across it, and the drainages painted it in strips of the
    # creeks around it: Lake Champlain in the Adirondack maps (1,113 km of such lines in one box), Tellico, Hartwell
    # and Elsinore lakes, 33 lakes over the 12 areas (measured 2026-11-20, when central Vermont's west edge moved to
    # the middle of Lake Champlain). Its water now carries no stream: the creeks end at its shore, and
    # 05c_drainages.py treats it as the sea (lakes_off_map.gpkg, step 5). The lakes layer (05d_lakes.py) draws it.
    for i in off_map:
        g_ = lakes.geometry.iloc[i - 1]
        ca, ra = ~T * (g_.bounds[0], g_.bounds[3])
        cb, rb = ~T * (g_.bounds[2], g_.bounds[1])
        r0_, r1_ = max(int(np.floor(ra)), 0), min(int(np.ceil(rb)), H)
        c0_, c1_ = max(int(np.floor(ca)), 0), min(int(np.ceil(cb)), W)
        if r1_ > r0_ and c1_ > c0_:
            wet = rasterio.features.geometry_mask([g_], (r1_ - r0_, c1_ - c0_), T * rasterio.Affine.translation(c0_, r0_),
                                                  invert=True)
            stream[r0_:r1_, c0_:c1_] &= ~wet
            del wet
    order = strahler(fd, stream, DR, DC)
    print(f"{' + '.join(group)}: {W} x {H} cells, {int(stream.sum())} stream cells, max order {int(order.max())}, "
          f"{n_wet} of {len(lakes)} lakes end paths at their outlet ({n_routed} routed to it along NHD's lines; "
          f"{n_out} km of stream line added below outlets)"
          + (f" ({n_through} more flow on: outlet on an edge between boxes)" if n_through else "")
          + (f", {len(off_map)} drain off the map through their water and carry no stream lines ("
             + ", ".join(n if isinstance(n, str) else "unnamed" for n in lakes.gnis_name.iloc[[i - 1 for i in off_map]]) + ")"
             if off_map else "")
          + (f", {loops} cells on loops ended in pits" if loops else ""))
    # 5. each box's files
    from pysheds.grid import Grid
    from pysheds.sview import Raster, ViewFinder
    for r in group:
        sl = where[r]
        f, st, od = fd[sl], stream[sl], order[sl]
        with rasterio.open(f"{raw_dir(r)}/dem_10m.tif") as src:
            prof = src.profile
        prof.update(compress="deflate", tiled=True, nodata=None)
        # (the cell count as float64 before it is multiplied: as int32, cells x 100 m2 wraps past 2,147 km2, which made
        # the Snake's drainage negative from the Hoback down and 05_score.py threw those 40 km away as a trickle)
        area = acc[sl].astype(np.float64) * (RES * RES) / 1e6
        assert area.min() >= 0, f"{r}: negative drainage area"
        for name, arr, dt in (("flowdir", f, "uint8"), ("area_km2", area, "float32"), ("strahler", od, "uint8")):
            with rasterio.open(f"{derived_dir(r)}/{name}.tif", "w", **dict(prof, dtype=dt)) as dst:
                dst.write(arr.astype(dt), 1)
        # the lakes in this box whose water leaves the map (step 4), for 05c_drainages.py
        p_off = f"{derived_dir(r)}/lakes_off_map.gpkg"
        here = [i - 1 for i in off_map if lakes.geometry.iloc[i - 1].intersects(shapely.box(*boxes[r]))]
        if here:
            lakes.iloc[here][["gnis_name", "geometry"]].to_file(p_off + ".tmp", driver="GPKG")
            os.replace(p_off + ".tmp", p_off)
        elif os.path.exists(p_off):
            os.remove(p_off)
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
    return left


if __name__ == "__main__":
    only = set(sys.argv[1:])                            # box names: just the groups that hold one of them
    done, left = [], []
    for group in groups():
        if only and not only & set(group):
            continue
        left += run(group)
        done += group
    path = f"{SHARED_DERIVED}/stitched.json"
    old = json.load(open(path)) if os.path.exists(path) else []
    os.makedirs(SHARED_DERIVED, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(sorted(set(old) | set(done)), fh)
    if left:      # the files are written; the exit status marks the run FAILED in the run_*.sh logs
        print("FAILED: dead ends left on edges between boxes, where water stops short of its outlet: "
              + ", ".join(f"({x:.0f}, {y:.0f}) {a:,.1f} km2" for x, y, a in left))
        sys.exit(1)
