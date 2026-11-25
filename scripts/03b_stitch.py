"""Hydrology for the whole area at once, from the boxes' conditioned DEMs (03_hydrology.py, run for every box first):
D8 flow direction -> lake outlets -> flow accumulation -> streams -> Strahler order -> the stream lines.  AREA only.

Boxes that share an edge are put side by side (a "group"; a box on its own is a group of one) and treated as one
surface:
  - A cell's direction is the steepest way down among its eight neighbours on the conditioned surface, the same
    rule pysheds uses, with the neighbours across a shared edge taken from the next box. So water crosses the
    edge where the ground says, instead of stopping at the box's rim.
  - Streams start where 0.25 km2 has gathered counting everything upstream in the group, so a creek's line runs on
    across the edge, and its Strahler order carries over. Where NHD names a creek or maps it year-round above that, its
    channel starts where NHD's line starts, on the terrain's own channel (low_channels, LOW_LINES): a line of its own,
    order 1.
  - A lake that holds water still ends the paths that enter it, at the cell where its water leaves (flowlib.
    still_water; "holds water" read off the DEM, at least LEVEL_HA of the outline at one elevation). A lake lying
    across a shared edge now has one outlet, not one in each box. crossbox.py carries the area on past the dam.
    That cell is where NHD's detailed stream network leaves the lake (lake_outlet), not the cell that gathers the
    most water on the DEM, which in 77 lakes of the 12 maps lay 300 m or more from NHD's outlet, at an inflow or at a
    low spot the filled surface spills over (Raquette Lake's 9.1 km away, at South Inlet's mouth). Of several NHD
    outlets the one NHD names is taken (the river's own bed, not the canal beside it), else the one NHDPlus's
    1:100,000 line leaves by, else the one nearest that cell. The cell with the most water stays where NHD has no
    outflow line, where the terrain doesn't let the water out along it, and where NHDPlus and the terrain agree on
    another place than NHD's detailed line (lake_outlet).
    Every cell of such a lake drains to that outlet, along NHD's lines through the lake where they run (route_lake):
    the flat water's own directions let a path other than the biggest leave the lake on its own. Below the outlet the
    way the water takes is a stream line down to the first stream it meets (outflow_streams), so that the lake's water,
    which crossbox.py puts back in there, lands on the river below the junction, not on a side creek's line. That way
    starts on NHD's outflow line, across the dam where there is one, and <area>/_shared/lake_outlets.json hands
    crossbox.py its first cell: until 2026-11-22 crossbox.py looked for the place itself, along NHDPlus's 1:100,000
    line, and put Seventh Lake's water in 555 m from its outlet.
    A lake's other NHD outflow lines that the terrain takes the water on down (its second outlets: Round Lake's, Marsh
    Creek Reservoir's side arms) get a stream line too, from the cell where the terrain takes the water on (side_streams),
    and go to lake_outlets.json's "sides": 05_score.py draws each as a side channel of the creek the lake's outlet
    starts. No water is put in there and no direction changes (step 3 (d)).
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
                 the next box, where that box's line for the same creek begins. low_channel 1: a line started lower
                 along NHD's named or year-round lines, which ends on the stream it runs into (that stream's link isn't
                 cut there)
and <area>/_shared/stitched.json lists the boxes done this way (crossbox.py then takes the crossings as exact).
"""
import json, os, sys
import numpy as np, rasterio, rasterio.features, rasterio.windows, shapely, shapely.ops, geopandas as gpd
from numba import njit
if not hasattr(np, "in1d"):  # pysheds still calls np.in1d, removed in NumPy 2.4
    np.in1d = np.isin
from config import *
from crossbox import shared_edges
from flowlib import still_water, FLOW, MIN_RESERVOIR_KM2

LEVEL_HA = 2
LINE_PULL = 5.0      # route_lake: a step through a lake off NHD's lines costs this many steps along them
WAY_MAX = 300        # m: an NHD outflow line is a lake's outlet when the terrain takes the water on within this far down it
FOLLOW_M, FOLLOW_TOL, FOLLOW_SHARE = 200, 40, 0.8    # the way out is the terrain's from the first cell whose own D8 path
                                                     # stays on NHD's outflow line: this share of its next FOLLOW_M
                                                     # m within FOLLOW_TOL m of the line
LAKE_LINE_FTYPES = (460, 558, 334)   # NHD HR StreamRiver, ArtificialPath (lake and river centrelines), Connector
BUILT_FTYPES = (336, 428)            # NHD HR CanalDitch and Pipeline: a lake's way out where no stream line leaves it
BUILT_MAX = 1000     # m: ... and only one that runs into a stream line within this much pipe or ditch (through a dam)
V_AT = 100           # m: NHDPlus's line leaves a lake "where the terrain does" within this far of the cell with the most water
SIDE_FTYPES = (460, 558)    # a lake's second outlet is a channel NHD maps: StreamRiver, or ArtificialPath through water
LEVEL_TOL = 0.5      # m: a lake whose level (its lidar surface) stands this much above another's is upstream of it
SEAM_KM2 = STREAM_KM2  # a dead end on an edge between two boxes gathering this much is mended (mend_seams)
# Channels start lower along NHD's named and year-round creeks (step 4, low_channels). STREAM_KM2 is where a channel
# starts on the terrain alone, and 05_score.py's floor draws a creek NHD names or maps year-round only down to it; but
# NHD HR names creeks and maps them year-round above that, brook trout headwaters among them: on the 12 maps of
# 2026-11-24, 958 of NHD's 23,200 named stream miles and 5,740 of its 44,200 year-round ones drained under 0.1 sq mi
# where they ran (the Smokies 409 and 2,164, central Vermont 58 and 1,887; audit/scripts/completeness.py). The user
# chose both (2026-11-24). Such a creek's channel now starts where NHD's line starts, on the terrain's own channel:
# going down NHD's line from its upper end (low_heads), the first cell with LOW_MIN_CELLS or more that is the wettest
# within LOW_WIN cells of the line, lies nearest that line and whose D8 path follows NHD, as a lake's way out must
# (FOLLOW_SHARE of its next FOLLOW_M within FOLLOW_TOL of an NHD channel line); the new line runs from there down its
# D8 path to the first stream. One that keeps under LOW_SHARE of its cells near NHD's lines isn't laid, nor one at an
# upper end that is a creek from outside the map (LOW_EDGE). The new lines are links of their own (dem_streams.gpkg's
# low_channel) that end on the stream they run into, which isn't cut there, so no link of the STREAM_KM2 network
# changes; and the Strahler order stays that network's (a channel start lower everywhere would raise every order by
# about one): their cells are order 1. 05_score.py draws one on the floor's own vote (a named or year-round NHD line,
# no canal), as it runs from NHD's line.
LOW_LINES = ("named", "perennial")   # the NHD HR stream lines (StreamRiver) whose channels start lower: named ones and
                                     # year-round ones (FCode 46006)
LOW_WIN = 4              # cells (40 m): the channel at a point of NHD's line is the wettest cell this near it
LOW_MIN_CELLS = 100      # cells (1 ha, 2.5 acres): the least a new line's first cell gathers
LOW_REACH_M = 3000       # m: how far down NHD's line from its upper end the first cell is looked for
LOW_SHARE = 0.7          # of a new line's cells within FOLLOW_TOL of NHD's channel lines, or it isn't laid
LOW_MAX_CELLS = 5000     # cells: a new line that meets no stream within this many isn't laid
LOW_EDGE = 30            # cells (300 m): no head whose NHD network above it starts this near the map's edge or outside
                         # it: a creek or river from outside (each box's file holds the lines that reach into it, so
                         # they seem to start at the edge, or below a path through water that does)
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
    resolved with FLAT_EPS, flats of filled ground along NHD HR's lines (flatlines.py). float64, NaN where z has no
    ground."""
    from pysheds.grid import Grid
    from pysheds.sview import Raster, ViewFinder
    import flatlines
    nod = np.float32(-99999.0)
    vf = ViewFinder(affine=Tw, shape=z.shape, crs=CRS, nodata=nod)
    grid = Grid(viewfinder=vf)
    raw = Raster(np.where(np.isnan(z), nod, z), viewfinder=vf)
    flooded = grid.fill_depressions(grid.fill_pits(raw))
    out = flatlines.resolve(grid, raw, flooded, Tw, FLAT_EPS, 10000)       # as 03_hydrology.py does
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


def nhd_lines(group, ftypes=LAKE_LINE_FTYPES):
    """NHD HR stream lines of the group's boxes (each box's nhd_flowlines.gpkg reaches past its box): StreamRiver,
    ArtificialPath and Connector, not canals, pipelines or coastline (or the types given), with their type and name."""
    import pandas as pd
    parts = []
    for r in group:
        p = f"{raw_dir(r)}/nhd_flowlines.gpkg"
        if os.path.exists(p):
            g = gpd.read_file(p, columns=["ftype", "gnis_name"])
            parts.append(g[g.ftype.isin(ftypes)].to_crs(CRS))
    if not parts:
        return gpd.GeoDataFrame({"ftype": [], "gnis_name": []}, geometry=[], crs=CRS)
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


def outflow_index(lines):
    """NHD's lines (nhd_lines, with their ftype and name) as single parts, each part's ftype, an index over them, the
    parts that start at each point, and whether NHD names each part: (parts, ftypes, tree, begins, named)."""
    from collections import defaultdict
    parts, kinds, named = [], [], []
    for g, k, nm in zip(shapely.force_2d(lines.geometry.values), lines.ftype.values, lines.gnis_name.values):
        new = [q for q in getattr(g, "geoms", [g]) if q.geom_type == "LineString" and q.length > 1]
        parts += new
        kinds += [int(k)] * len(new)
        named += [isinstance(nm, str) and bool(nm.strip())] * len(new)
    begins = defaultdict(list)
    for i, q in enumerate(parts):
        begins[(round(q.coords[0][0]), round(q.coords[0][1]))].append(i)
    return parts, kinds, (shapely.STRtree(parts) if parts else None), begins, named


def lake_cells(fd, geom, T):
    """(r0, c0, mask): a lake's cells (centres inside its outline, with ground) in a window of the grid starting at
    (r0, c0), as route_lake takes them; None where the outline lies off the grid."""
    H, W = fd.shape
    gx0, gy0, gx1, gy1 = geom.bounds
    ca, ra = ~T * (gx0, gy1)
    cb, rb = ~T * (gx1, gy0)
    r0, c0 = max(int(np.floor(ra)) - 1, 0), max(int(np.floor(ca)) - 1, 0)
    r1, c1 = min(int(np.ceil(rb)) + 1, H), min(int(np.ceil(cb)) + 1, W)
    if r1 <= r0 or c1 <= c0:
        return None
    mask = rasterio.features.geometry_mask([geom], (r1 - r0, c1 - c0), T * rasterio.Affine.translation(c0, r0),
                                           invert=True) & (fd[r0:r1, c0:c1] > 0)
    return r0, c0, mask


def small_water(hu4, bounds, big):
    """NHD's lakes and ponds under MIN_RESERVOIR_KM2 in `bounds` (this area's CRS), from the given HU4 downloads, less
    those lying in one of `big` (still_water's): the ponds step (f) of run() drains at NHD's outlet, as one, without
    ending their creek there."""
    import pandas as pd, pyogrio
    W_, S_, E_, N_ = gpd.GeoSeries([shapely.box(*bounds)], crs=CRS).to_crs(4269).total_bounds
    parts = []
    for hu in hu4:
        g = f"{NATIONAL}/NHD_H_{hu}_HU4_GPKG.gpkg"
        lyr = next(l for l in pyogrio.list_layers(g)[:, 0] if l.lower() == "nhdwaterbody")
        d = gpd.read_file(g, layer=lyr, bbox=(W_, S_, E_, N_))
        d.columns = [c.lower() if c != "geometry" else c for c in d.columns]
        parts.append(d.to_crs(CRS))
    if not parts:
        return gpd.GeoDataFrame(geometry=[], crs=CRS)
    wb = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    wb = wb[wb.ftype.isin([390, 436]) & (wb.area < MIN_RESERVOIR_KM2 * 1e6)
            & ~wb.gnis_name.fillna("").str.contains("Lagoon")].drop_duplicates("permanent_identifier")
    wb = wb.assign(geometry=shapely.make_valid(wb.geometry.force_2d().values))
    if len(big) and len(wb):
        hit = np.unique(gpd.GeoSeries(big.geometry.values, crs=CRS).sindex.query(wb.geometry.values,
                                                                                  predicate="intersects")[0])
        wb = wb.drop(wb.index[hit])
    return wb[["gnis_name", "geometry"]].reset_index(drop=True)


def leads_back(fd, r, c, win, avoid=(), limit=500000):
    """True if the D8 path from (r, c) runs into the lake whose cells `win` holds (lake_cells), through one of the
    cells in `avoid`, or never ends."""
    r0, c0, mask = win
    H, W = fd.shape
    h, w = mask.shape
    for _ in range(limit):
        if (0 <= r - r0 < h and 0 <= c - c0 < w and mask[r - r0, c - c0]) or (r, c) in avoid:
            return True
        k = int(fd[r, c])
        if k not in CODE_SET:
            return False
        r, c = r + int(DR[k]), c + int(DC[k])
        if not (0 <= r < H and 0 <= c < W):
            return False
    return True


def follows(fd, r, c, T, line, wet):
    """True if the D8 path from (r, c) stays on `line` (NHD's outflow line): FOLLOW_SHARE of its next FOLLOW_M m
    within FOLLOW_TOL m of it, as far as the next lake (`wet`: the cells of the lakes that hold water). A path that
    ends or reaches a lake within three cells counts as following."""
    H, W = fd.shape
    pts = []
    for _ in range(int(FOLLOW_M / RES)):
        k = int(fd[r, c])
        if k not in CODE_SET:
            break
        r, c = r + int(DR[k]), c + int(DC[k])
        if not (0 <= r < H and 0 <= c < W) or fd[r, c] == 0 or wet[r, c]:
            break
        pts.append(shapely.Point(*(T * (c + 0.5, r + 0.5))))
    if len(pts) < 3:
        return True
    return float(np.mean(shapely.distance(line, pts) <= FOLLOW_TOL)) >= FOLLOW_SHARE


def cell_line(a, b):
    """The cells on the straight line from cell a to cell b, both included, each one a neighbour of the last."""
    (r, c), (r1, c1) = a, b
    out = [(r, c)]
    while (r, c) != (r1, c1):
        r += (r1 > r) - (r1 < r)
        c += (c1 > c) - (c1 < c)
        out.append((r, c))
    return out


def nhd_outlets(fd, geom, T, win, index, ftypes, wet):
    """NHD's outlets of a lake: [{exit: the point where an outflow line leaves the water, cells: the grid cells from
    the lake along the line to the first one the terrain takes on from, or None, on_line: whether the terrain's way
    from that cell stays on NHD's line, named: whether NHD names the outflow line, off_map: the line left the map
    before the terrain took the water on}].
    An outflow line is one of NHD's detailed lines of the given types that starts in the lake (within 30 m of its
    outline: the lines are drawn downstream, and one that ends in the lake is an inflow) and ends outside it. A pipe
    or a ditch counts only where NHD's stream network goes on from it within BUILT_MAX (the pipe through Bouquet
    Reservoir's dam, which Bouquet Creek starts from 400 m on; not the Los Angeles Aqueduct's, which leaves the same
    reservoir for 5 km of pipe and took the creek's water with it). It is
    followed from where it leaves the water, half a cell at a time, into the line it runs into where it ends (the
    stream line, where a ditch branches off there too), for
    WAY_MAX m: the first cell outside the lake whose D8 path doesn't lead back into the lake is where the terrain
    takes the water on (the cell right at the shore for 88% of the 1,502 outflow lines on the 12 maps, within 50 m for
    96%: the rest cross a dam or a sill the DEM holds the lake behind). cells is None where there is no such cell
    within WAY_MAX: the terrain doesn't let the water out that way, whatever the line says (a line 30 m from the
    outline that belongs to the next pond; Ferris Lake's outlet stream, which the DEM runs back into the lake for
    800 m).
    A line that starts at the shore or just off it is reached from the lake cell nearest its start, straight, and
    those cells are judged like the ones under the line: a path that comes back through a cell already passed leads
    back as well (below Doaneville Pond's dam the cell under NHD's line drains through the cell between it and the
    pond, and pointing that one at the line closed a loop of three cells).
    A cell of another lake that holds water (`wet`) is where the way out ends in any case: that lake's routing takes
    the water on, and its cells are never pointed along this lake's line.
    The cell taken is the first whose D8 path also stays on NHD's line (follows): below Leonard Pond the first cell
    that leads on leaves NHD's outlet stream within 200 m, and the way out is pointed along the line for another
    110 m, to a cell whose path stays on it (13 of the 348 lakes at NHD's outlet on the north-west Adirondack map).
    Where no cell within WAY_MAX does (NHD's line drawn 50 m beside the channel the DEM has), the first cell that
    leads on is taken, as the terrain has it."""
    parts, kinds, tree, begins, named = index
    if tree is None:
        return []
    r0, c0, mask = win
    H, W = fd.shape
    h, w = mask.shape
    inside = lambda rc: 0 <= rc[0] - r0 < h and 0 <= rc[1] - c0 < w and bool(mask[rc[0] - r0, rc[1] - c0])
    lk = geom.buffer(30)
    nexts = lambda q, seen: sorted((k for k in begins.get((round(q.coords[-1][0]), round(q.coords[-1][1])), []) if k not in seen),
                                   key=lambda k: kinds[k] not in LAKE_LINE_FTYPES)      # the stream line first

    def to_stream(j):           # a pipe or ditch that NHD's stream network goes on from, within BUILT_MAX of built line
        cur, seen, length = parts[j], {j}, parts[j].length
        while length <= BUILT_MAX:
            nx = nexts(cur, seen)
            if not nx or kinds[nx[0]] in LAKE_LINE_FTYPES:
                return bool(nx)
            cur = parts[nx[0]]
            seen.add(nx[0])
            length += cur.length
        return False

    out = []
    for j in tree.query(lk, predicate="intersects"):
        g = parts[j]
        if kinds[j] not in ftypes:
            continue
        if lk.contains(shapely.Point(g.coords[-1])) or not lk.contains(shapely.Point(g.coords[0])):
            continue
        if kinds[j] in BUILT_FTYPES and not to_stream(j):
            continue
        ins = g.intersection(geom)
        t0 = 0.0 if ins.is_empty else max(g.project(shapely.Point(xy)) for q in getattr(ins, "geoms", [ins])
                                          if q.geom_type in ("LineString", "Point") for xy in q.coords)
        # the line from where it leaves the water, with the lines it runs into: far enough to judge a path on
        chain, cur, seen, length = [shapely.ops.substring(g, t0, g.length)], g, {j}, g.length - t0
        while length < WAY_MAX + FOLLOW_M + 100:
            nx = nexts(cur, seen)
            if not nx:
                break
            cur = parts[nx[0]]
            seen.add(nx[0])
            chain.append(cur)
            length += cur.length
        line = shapely.union_all(chain)

        off = []                                        # set where the line leaves the map within WAY_MAX

        def along():                                    # the cells under the line, from where it leaves the water
            gone = 0.0
            for part in chain:
                for d in np.arange(0, part.length, RES / 2):
                    if gone + d > WAY_MAX:
                        return
                    cc, rr = ~T * part.interpolate(d).coords[0]
                    rc = (int(np.floor(rr)), int(np.floor(cc)))
                    if not (0 <= rc[0] < H and 0 <= rc[1] < W) or fd[rc] == 0:
                        off.append(True)                # the line leaves the map first
                        return
                    yield rc
                gone += part.length

        cells, first, found, ended = [], None, None, False
        for rc in along():
            step = [rc]
            if not cells and not inside(rc):            # the line starts at the shore, or up to 30 m off it: from the
                rr, cc = np.nonzero(mask)               # lake cell nearest its start, straight to it
                k = int(np.argmin((rr + r0 - rc[0]) ** 2 + (cc + c0 - rc[1]) ** 2))
                step = cell_line((int(rr[k]) + r0, int(cc[k]) + c0), rc)
            for rc in step:
                if cells and cells[-1] == rc:
                    continue
                cells.append(rc)
                if inside(rc):
                    continue
                back = leads_back(fd, rc[0], rc[1], win, set(cells[:-1]))
                if wet[rc]:                             # the next lake of a chain: its own routing takes the water on
                    found = None if back else len(cells)
                    ended = True
                    break
                if back:
                    continue
                if first is None:
                    first = len(cells)
                if follows(fd, rc[0], rc[1], T, line, wet):
                    found = len(cells)
                    break
            if found is not None or ended:
                break
        n = found if found is not None else first
        out.append(dict(exit=g.interpolate(t0), cells=cells[:n] if n else None, on_line=found is not None, named=named[j],
                        off_map=bool(off) and not n, part=j))
    return out


def mapped_channel(q, index):
    """Whether an outflow line (one of nhd_outlets) is a channel NHD maps, as a lake's second outlet has to be: a
    StreamRiver line, or ArtificialPaths (lines through water) that run into one, with no Connector, canal or pipeline
    on the way. A Connector is NHD's link where the way is unknown or underground: it takes Lake Mathews' water 515 m
    to the MWD Upper Feeder's intake, Castaic Lake's 1.4 km through its dam to the lagoon, Morris Reservoir's into
    canals. At a fork the StreamRiver line is taken first, then an ArtificialPath."""
    parts, kinds, tree, begins, named = index
    j, seen = q["part"], set()
    while kinds[j] == 558:
        seen.add(j)
        end = parts[j].coords[-1]
        nx = [k for k in begins.get((round(end[0]), round(end[1])), []) if k not in seen]
        if not nx:
            return True                                 # ArtificialPaths to the end of the lines this box has
        j = min(nx, key=lambda k: {460: 0, 558: 1}.get(kinds[k], 2))
    return kinds[j] == 460


def nhdplus(group):
    """NHDPlus V2's flowlines (02b_download_flow.py's nhdplus_v2.gpkg) and the same by hydroseq, or None where that
    step hasn't run yet: lake_outlet then goes by NHD's names and the terrain alone. The drivers run it first, and a
    run of this script stops before it writes anything where the file is missing, unless NO_NHDPLUS=1 says to go on."""
    p = f"{FLOW}/nhdplus_v2.gpkg"
    if not os.path.exists(p):
        return None
    v2 = gpd.read_file(p, columns=["hydroseq", "dnhydroseq", "totdasqkm"]).to_crs(CRS)
    v2 = v2[v2.geometry.notna() & ~v2.geometry.is_empty].reset_index(drop=True)
    return v2, v2.drop_duplicates("hydroseq").set_index("hydroseq")


def nhdplus_exit(lake, v2):
    """Where NHDPlus's line leaves a lake: the flowline that drains the most ground among those lying in the lake (a
    quarter of their length or more, as crossbox.py counts them), followed downstream to the one that ends outside
    the lake; its last point inside the outline. None where NHDPlus has no line in the lake, or none that leaves it.
    The 1:100,000 line can leave the outline hundreds of metres from the outlet (550 m at Seventh Lake): it says
    which of NHD's detailed outflow lines the lake drains by, not where the outlet is."""
    if v2 is None:
        return None
    lines, by_seq = v2
    ins = lines.iloc[lines.sindex.query(lake, predicate="intersects")]
    if len(ins):
        ins = ins[ins.geometry.intersection(lake).length >= 0.25 * ins.geometry.length]
    if not len(ins):
        return None
    fl, near = ins.loc[ins.totdasqkm.idxmax()], lake.buffer(30)
    for _ in range(12):
        g = shapely.line_merge(fl.geometry)
        if g.geom_type != "LineString":                 # NHDPlus stores flowlines as (usually one-part) multilines
            g = shapely.LineString([c for part in g.geoms for c in part.coords])
        if not near.contains(shapely.Point(g.coords[-1])):
            inside = g.intersection(lake)
            if inside.is_empty:
                return shapely.Point(g.coords[0])
            return g.interpolate(max(g.project(shapely.Point(c)) for q in getattr(inside, "geoms", [inside])
                                     if q.geom_type in ("LineString", "Point") for c in q.coords))
        if fl.dnhydroseq not in by_seq.index:
            return None
        fl = by_seq.loc[fl.dnhydroseq]
    return None


def lake_outlet(fd, geom, T, dem_cell, index, wet, v=None, sides=None):
    """Where a lake's water leaves it, from NHD: (outlet cell, [cells of the way out below it], why), or
    (None, None, why) where the cell that gathers the most water on the DEM (`dem_cell`) stays the outlet. `v` is
    where NHDPlus's line leaves the lake (nhdplus_exit), or None. Where the outlet is NHD's, the lake's other outflow
    lines the terrain takes the water on down go to the list `sides` as (outflow line, status): status "ok" for a
    second outlet (a channel NHD maps whose own way stays on NHD's line, mapped_channel), else why not.
    NHD's detailed network says where a lake drains (nhd_outlets): by a stream line (LAKE_LINE_FTYPES), and where no
    stream line the terrain takes on from leaves the lake, by a pipe or a ditch that a stream line goes on from
    (BUILT_FTYPES): the network goes on through Palisades Dam and Stark Falls Dam as a pipeline, and out of Two Ocean
    Lake by a ditch (six lakes on the 12 maps; an aqueduct or a drain that leads to no stream is no outlet).
    With two or three outflow lines (61 lakes on the 12 maps):
      - the one NHD names is the river's own channel: below Soft Maple Reservoir the Beaver River's bed, beside the
        unnamed power canal 230 m along the dam where the terrain spills the lake (31 of the 61 have one named line);
      - where none or all are named, the one NHDPlus's line leaves by (within WAY_MAX of it): NHD gives Lake Mathews
        a connector through its north dike, where the terrain spills it, and Cajalco Creek on the west, where
        NHDPlus and the two Temescal Creek gauges have its water. The maps before put the water on NHDPlus's line,
        so this is also the outlet they drew (Crooked Lake's, Woodhull Lake's);
      - else the one nearest dem_cell: the terrain says which of NHD's outlets the water spills by.
    D8 sends a lake's water down one way out. The others are its second outlets: run() lays their lines too, and
    05_score.py draws them as side channels of the outlet's creek.
    The DEM's cell stays, and crossbox.py's own search carries the lake's water as before:
      - where NHD has no outflow line: a lake with no outlet;
      - where the terrain doesn't take the water on within WAY_MAX down any of NHD's outflow lines: the DEM's ground
        stands above the lake along them (2.4 m for 830 m below Burntbridge Pond, 67 m below Huckleberry Pond, where
        the line is an inflow drawn the wrong way round);
      - where each of them runs off the map first (Stone Mountain Lake, at the map's edge);
      - where the terrain takes the water on only down another line than the ones NHD names (with no name: than the
        ones NHDPlus's line leaves by): Snake Meadow Brook runs through Tetreault Pond and out of its south end,
        where the DEM's ground stands 1.9 m above the pond 530 m down the brook and every cell before it drains
        back; the DEM spills the pond west, into Fall Brook's valley, where NHD has a second line. Ended there, the
        pond took Snake Meadow Brook's 10.7 km2 to Fall Brook;
      - where NHDPlus's line leaves the lake at dem_cell (within V_AT) and NHD's detailed outflow lines are WAY_MAX
        or more away: two against one on which creek the lake feeds. Livingston Lake and Lens Lake sit on the divide
        between Paul Creek, where the terrain spills them and NHDPlus has them, and Sand Creek and Roaring Branch,
        where NHD's detailed lines send them (Sand Creek across 60 m of ground 3 m above Livingston Lake, which
        stands 5.6 m above the pond NHD draws flowing into it).
    The outlet cell is the last cell of the lake on NHD's line; the way out is the cells after it down to the first
    one the terrain's own D8 path is taken from (often none but that one: the cell at the shore)."""
    win = lake_cells(fd, geom, T)
    if win is None or not win[2].any():
        return None, None, "no cells"
    geom = shapely.make_valid(geom)
    cands = nhd_outlets(fd, geom, T, win, index, LAKE_LINE_FTYPES, wet)
    ok = [q for q in cands if q["cells"]]
    built = ""
    if not ok:                  # no stream line the terrain takes on from: a pipe through the dam, a ditch
        cands += nhd_outlets(fd, geom, T, win, index, BUILT_FTYPES, wet)
        ok = [q for q in cands if q["cells"]]
        built = ", a pipe or ditch"
    if not cands:
        return None, None, "NHD has no outflow line"
    if not ok and all(q["off_map"] for q in cands):     # a lake at the map's edge: its outlet stream runs off the map
        return None, None, "NHD's outflow line leaves the map before the terrain takes the water on"
    if not ok:
        return None, None, f"the terrain takes the water on down none of NHD's outflow lines within {WAY_MAX} m"
    x, y = T * (dem_cell[1] + 0.5, dem_cell[0] + 0.5)
    dem = shapely.Point(x, y)
    near_v = lambda q: v is not None and q["exit"].distance(v) <= WAY_MAX
    # the lake's own outlet stream: the outflow lines NHD names, else the ones NHDPlus's line leaves by
    named = [q for q in cands if q["named"]]
    main = named or [q for q in cands if near_v(q)]
    if main and not any(q["cells"] for q in main):
        return None, None, (f"the terrain takes the water on down none of the outflow lines "
                            + ("NHD names" if named else "NHDPlus's line leaves by") + f" within {WAY_MAX} m, only down "
                            + ("an unnamed one" if named else "another"))
    if (v is not None and not any(near_v(q) for q in ok) and v.distance(dem) <= V_AT
            and all(q["exit"].distance(dem) > WAY_MAX for q in ok)):
        return None, None, (f"NHDPlus's line leaves the lake at the cell with the most water, {WAY_MAX} m or more from "
                            "NHD's detailed outflow line")
    pool = [q for q in main if q["cells"]] or ok
    by_v = [q for q in pool if near_v(q)]
    pick = min(by_v, key=lambda q: q["exit"].distance(v)) if by_v else min(pool, key=lambda q: q["exit"].distance(dem))
    how = ""
    if len(ok) > 1:
        how = (f", the named one of {len(ok)}" if named and len(pool) < len(ok) else
               f", the one of {len(ok)} that NHDPlus's line leaves by" if by_v else f", the nearest of {len(ok)}")
    why = "NHD's outflow line" + built + how + ("" if pick["on_line"] else "; the terrain's way on leaves NHD's line")
    r0, c0, mask = win
    h, w = mask.shape
    lake = lambda rc: 0 <= rc[0] - r0 < h and 0 <= rc[1] - c0 < w and bool(mask[rc[0] - r0, rc[1] - c0])
    seq = pick["cells"]
    last = max(k for k, rc in enumerate(seq[:-1]) if lake(rc))
    # the other lines: not the outlet's own line again (each box's file of lines reaches past the box, so a group of
    # boxes has a line twice) nor one whose way meets the outlet's at the shore (one channel)
    exits, way = [pick["exit"]], set(seq[last + 1:])
    for q in (ok if sides is not None else []):
        if any(q["exit"].distance(e) < 1.0 for e in exits) or way & set(q["cells"]):
            continue
        exits.append(q["exit"])
        channel = index[1][q["part"]] in SIDE_FTYPES and mapped_channel(q, index)
        sides.append((q, "ok" if channel and q["on_line"] else
                      "the terrain's way leaves NHD's line" if channel else "a connector, canal or pipeline"))
    return seq[last], seq[last + 1:], why


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


def side_streams(fd, stream, tops, max_cells=3000):
    """Make the way a lake's second outlet takes a stream line, from the cell where the terrain takes the water on down
    to the first stream cell it meets, as outflow_streams does below the outlet: the cells below a lake gather little
    ground of their own, and without it the channel had no line until it had gathered STREAM_KM2. Changes stream in
    place; returns km of line added."""
    H, W = fd.shape
    added = 0
    for r, c in tops:
        for _ in range(max_cells):
            if stream[r, c]:
                break
            stream[r, c] = True
            added += 1
            k = int(fd[r, c])
            if k not in CODE_SET:
                break
            r, c = r + int(DR[k]), c + int(DC[k])
            if not (0 <= r < H and 0 <= c < W):
                break
    return round(added * RES / 1000, 1)


@njit(cache=True)
def low_best(acc, rr, cc, k):
    """low_channels: for each point (rr, cc) of the grid, the wettest cell within k cells of it (row, col, cells; -1 off
    the grid)."""
    H, W = acc.shape
    n = rr.size
    br, bc, bv = np.full(n, -1, np.int64), np.full(n, -1, np.int64), np.full(n, -1, np.int64)
    for i in range(n):
        for r in range(max(rr[i] - k, 0), min(rr[i] + k + 1, H)):
            for c in range(max(cc[i] - k, 0), min(cc[i] + k + 1, W)):
                if acc[r, c] > bv[i]:
                    bv[i], br[i], bc[i] = acc[r, c], r, c
    return br, bc, bv


@njit(cache=True)
def low_walk(fd, stream, order, acc, thr, r, c, maxn, DR, DC, out_r, out_c):
    """low_channels: the cells of the D8 path from (r, c) to the first stream cell (end 1), the first cell of a line
    laid lower already (2: order > 0 off the streams), a pit or the grid's edge (3), maxn cells (4), or a cell gathering
    thr or more that carries no stream (5: a lake whose water leaves the map, step 4). Returns (n, end): out[:n] are
    the path's own cells, and out[n] the cell it ends on for ends 1 and 2."""
    H, W = fd.shape
    n = 0
    while n < maxn:
        if stream[r, c] or order[r, c] > 0:
            out_r[n], out_c[n] = r, c
            return n, (1 if stream[r, c] else 2)
        if acc[r, c] >= thr:
            return n, 5
        out_r[n], out_c[n] = r, c
        n += 1
        k = fd[r, c]
        if DR[k] == 0 and DC[k] == 0:
            return n, 3
        r2, c2 = r + DR[k], c + DC[k]
        if r2 < 0 or r2 >= H or c2 < 0 or c2 >= W or fd[r2, c2] == 0:
            return n, 3
        r, c = r2, c2
    return n, 4


def low_heads(group, inside):
    """low_channels: NHD HR's lines of the group's boxes (each once: a box's file reaches past the box) as single parts,
    and for each upper end of the network of LOW_LINES lines (a part whose start is no such part's end, nor the end of a
    path through water or a connector that one leads into: a river that runs on below a lake or a wide stretch, where
    NHD's stream line starts again, has no upper end there) NHD's line from there down LOW_REACH_M m, on along the part
    that starts where it ends with the same name (none, for an unnamed head), never into another creek: (heads, each
    head's parts as places in the next, the channel lines' parts: for the tests that a cell is on the head's own line
    and that a path follows NHD; and how many heads were left out because NHD's network above them, through any of its
    channel lines, starts where inside(x, y) is False: a creek from outside the map)."""
    import pandas as pd
    parts = [gpd.read_file(p, columns=["ftype", "fcode", "gnis_name"]).to_crs(CRS)
             for p in (f"{raw_dir(r)}/nhd_flowlines.gpkg" for r in group) if os.path.exists(p)]
    if not parts:
        return [], [], [], 0
    nl = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    nl = nl[nl.geometry.notna() & ~nl.geometry.is_empty]
    nl = nl[~nl.geometry.to_wkb().duplicated()]
    one, kind, name, qual = [], [], [], []
    for g, ft, fc, nm in zip(shapely.force_2d(nl.geometry.values), nl.ftype.values, nl.fcode.values,
                             nl.gnis_name.values):
        nm = nm.strip() if isinstance(nm, str) and nm.strip() else None
        q_ = ft == 460 and (("named" in LOW_LINES and nm is not None) or ("perennial" in LOW_LINES and fc == 46006))
        for p in getattr(g, "geoms", [g]):
            if p.geom_type == "LineString" and p.length > 1:
                one.append(p)
                kind.append(int(ft))
                name.append(nm)
                qual.append(bool(q_))
    key = lambda xy: (round(xy[0]), round(xy[1]))
    begins, ends, ends_q, at = {}, {}, set(), {}
    for i, p in enumerate(one):
        if kind[i] in LAKE_LINE_FTYPES:
            begins.setdefault(key(p.coords[0]), []).append(i)
            ends.setdefault(key(p.coords[-1]), []).append(i)
            at[i] = len(at)
        if qual[i]:
            ends_q.add(key(p.coords[-1]))
    # whether NHD's network above part i, through any of its channel lines, starts outside the map or near its edge
    def from_outside(i, cap=2000):
        stack, seen_ = [i], {i}
        while stack:
            j = stack.pop()
            if not inside(*one[j].coords[0]):
                return True
            for k in ends.get(key(one[j].coords[0]), []):
                if k not in seen_:
                    seen_.add(k)
                    stack.append(k)
            if len(seen_) > cap:
                return True
        return False
    through = {}                                        # paths through water and connectors, by their start
    for i, p in enumerate(one):
        if kind[i] in (558, 334):
            through.setdefault(key(p.coords[0]), []).append(i)
    stack = list(ends_q)
    while stack:
        for i in through.get(stack.pop(), []):
            e_ = key(one[i].coords[-1])
            if e_ not in ends_q:
                ends_q.add(e_)
                stack.append(e_)
    heads, own, n_out = [], [], 0
    for i, p in enumerate(one):
        if not qual[i] or key(p.coords[0]) in ends_q:
            continue
        if from_outside(i):
            n_out += 1
            continue
        seq, L, j, seen = [np.asarray(p.coords)], p.length, i, [i]
        while L < LOW_REACH_M:
            nxt = [k for k in begins.get(key(one[j].coords[-1]), []) if k not in seen and name[k] == name[i]]
            if not nxt:
                break
            j = nxt[0]
            seen.append(j)
            seq.append(np.asarray(one[j].coords)[1:])
            L += one[j].length
        heads.append(shapely.LineString(np.concatenate(seq)))
        own.append({at[k] for k in seen})
    return heads, own, [p for p, k in zip(one, kind) if k in LAKE_LINE_FTYPES], n_out


def low_channels(fd, acc, stream, order, T, group):
    """Lays the lines whose channels start lower than STREAM_KM2 along NHD's LOW_LINES lines (see LOW_LINES): marks
    their cells order 1 in `order`, in place. Returns (heads of such lines, lines laid, cells laid, {why: heads with
    none})."""
    H, W = fd.shape
    thr = int(round(STREAM_KM2 * 1e6 / (RES * RES)))
    inv = ~T
    def inside(x, y):                                   # on the map's ground, LOW_EDGE cells or more from its edge
        c_, r_ = inv * (x, y)
        r_, c_ = int(np.floor(r_)), int(np.floor(c_))
        return (LOW_EDGE <= r_ < H - LOW_EDGE and LOW_EDGE <= c_ < W - LOW_EDGE
                and bool(fd[r_ - LOW_EDGE:r_ + LOW_EDGE + 1, c_ - LOW_EDGE:c_ + LOW_EDGE + 1].all()))
    heads, own, chan, n_out = low_heads(group, inside)
    if not heads:
        return n_out, 0, 0, ({"NHD's network above it starts at the map's edge or outside it": n_out} if n_out else {})
    tree = shapely.STRtree(chan)
    def on_nhd(rr, cc):                                 # each cell's centre within FOLLOW_TOL of an NHD channel line
        x, y = T * (cc + 0.5, rr + 0.5)
        on = np.zeros(len(rr), bool)
        on[tree.query(shapely.points(x, y), predicate="dwithin", distance=FOLLOW_TOL)[0]] = True
        return on
    out_r, out_c = np.zeros(LOW_MAX_CELLS + 1, np.int64), np.zeros(LOW_MAX_CELLS + 1, np.int64)
    laid, cells = 0, 0
    why = {"NHD's network above it starts at the map's edge or outside it": n_out} if n_out else {}
    for line, own_ in zip(heads, own):
        pts = shapely.line_interpolate_point(line, np.arange(0.0, min(line.length, LOW_REACH_M), RES))
        cc, rr = inv * (shapely.get_x(pts), shapely.get_y(pts))
        rr, cc = np.floor(rr).astype(np.int64), np.floor(cc).astype(np.int64)
        br, bc, bv = low_best(acc, rr, cc, LOW_WIN)
        w_ = "no cell gathers enough near NHD's line"
        for k in range(len(bv)):
            if bv[k] < LOW_MIN_CELLS:
                continue
            r0, c0 = br[k], bc[k]
            if stream[r0, c0] or order[r0, c0] or bv[k] >= thr:
                w_ = "NHD's line meets a stream first"
                break
            if int(tree.query_nearest(shapely.Point(*(T * (c0 + 0.5, r0 + 0.5))))[0]) not in own_:
                w_ = "the wettest cell near NHD's line lies on another line"     # a creek or river beside its head
                continue
            n, end = low_walk(fd, stream, order, acc, thr, r0, c0, int(FOLLOW_M / RES), DR, DC, out_r, out_c)
            if n >= 3 and on_nhd(out_r[:n], out_c[:n]).mean() < FOLLOW_SHARE:
                w_ = "no cell whose path follows NHD's line"
                continue
            n, end = low_walk(fd, stream, order, acc, thr, r0, c0, LOW_MAX_CELLS, DR, DC, out_r, out_c)
            if end == 4:
                w_ = f"meets no stream within {LOW_MAX_CELLS * RES / 1000:g} km"
            elif n < 2:
                w_ = "NHD's line meets a stream first"
            elif on_nhd(out_r[:n], out_c[:n]).mean() < LOW_SHARE:
                w_ = "the line would run off NHD's lines"
            else:
                order[out_r[:n], out_c[:n]] = 1
                laid += 1
                cells += n
                w_ = None
            break
        if w_:
            why[w_] = why.get(w_, 0) + 1
    return len(heads) + n_out, laid, cells, why


def held_below(fd, acc, starts, stops, max_cells=10 ** 6):
    """{flat cell: cells of drainage}: the water that reaches each cell through the lake outlets in `starts` (flat
    cells), followed down the D8 path from each outlet, with what that outlet gathers (acc) added to every cell on the
    way, up to and including the next outlet in `stops` (which hands on its own, everything above it included) or the
    end of the path. With every lake outlet a pit this water would stop at the outlets: it is what the area raster
    holds beyond that, cell by cell, where paths from several lakes meet the sum."""
    H, W = fd.shape
    out = {}
    for o in starts:
        amt = int(acc.flat[o])
        if amt <= 0:
            continue
        r, c = divmod(int(o), W)
        for _ in range(max_cells):
            k = int(fd[r, c])
            if k not in CODE_SET:
                break
            r, c = r + int(DR[k]), c + int(DC[k])
            if not (0 <= r < H and 0 <= c < W):
                break
            i = r * W + c
            out[i] = out.get(i, 0) + amt
            if i in stops:
                break
    return out


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
    n_wet = n_routed = n_nhd = 0
    through = []                                        # lakes that flow on at an edge between two boxes
    tops, kept, far, loose = [], [], [], []             # lake_outlets.json and the log: see the lake loop
    sides, side_ok, side_not, side_seen = [], [], {}, set()     # second outlets (step d): lake_outlets.json, the log
    outflow = []                                        # (row, col, direction) of each pitted lake's outlet
    off_map = []                                        # lakes whose water leaves the map through their own surface
    opened = []                                         # (outlet cell, flat; a pond) of the lakes whose water goes on (e)
    # the ponds step (f) drains at NHD's outlet: read before the lake step, which runs for them too
    ponds = small_water(tuple(sorted({h for r in group for h in REGIONS[r]["hu4"]})), (x0, y0, x1, y1), lakes)
    if len(lakes) or len(ponds):
        level, best = {}, {}
        for r in (group if len(lakes) else []):
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
        index = outflow_index(nhd_lines(group, LAKE_LINE_FTYPES + BUILT_FTYPES))
        v2 = nhdplus(group)
        if v2 is None:                                  # only with NO_NHDPLUS=1: without it the run stopped at its start
            print("NOTE: no NHDPlus lines (02b_download_flow.py) and NO_NHDPLUS is set: lakes with several outflow lines "
                  "go by NHD's names and the terrain alone; run 03b_stitch.py again once they are there")

        def box_of(r__, c__):
            return next((b for b in group if where[b][0].start <= r__ < where[b][0].stop
                         and where[b][1].start <= c__ < where[b][1].stop), None)

        # (a) every lake ends at the cell with the most water, as all of them did until 2026-11-22
        pitted = []                                     # (lake, its place in `outflow`) of the lakes ended in a pit
        wet = np.zeros(fd.shape, bool)                  # the cells of the lakes that hold water
        for i, (a, r_, c_) in best.items():
            if most.get(i, 0) * RES * RES / 1e4 < LEVEL_HA:
                continue
            win_ = lake_cells(fd, lakes.geometry.iloc[i - 1], T)
            if win_ is not None:
                wet[win_[0]:win_[0] + win_[2].shape[0], win_[1]:win_[1] + win_[2].shape[1]] |= win_[2]
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
                through.append(i)                       # unless (b) ends it at NHD's outlet, away from the edge
                continue
            outflow.append((r_, c_, int(fd[r_, c_])))     # the way its water takes out of the lake, before the pit
            fd[r_, c_] = PIT
            pitted.append((i, len(outflow) - 1))
            n_wet += 1
        # (b) then at NHD's outlet, where NHD has one the terrain takes the water on from (lake_outlet). Decided for
        # every lake on the one surface (a) leaves, before any is moved: taken one by one as they came, a lake whose
        # outflow line runs through the next pond of a chain was judged on that pond's flat water, which led back
        # into it until the pond was routed itself (Rainbow Lake, Fish Creek Ponds and Grass Pond stayed 1-2 km from
        # their outlets that way)
        moves = []
        for i, k in pitted + [(i, None) for i in through]:
            r_, c_ = best[i][1], best[i][2]
            geom, name = lakes.geometry.iloc[i - 1], lakes.gnis_name.iloc[i - 1]
            name = name if isinstance(name, str) else "unnamed"
            sides_ = []
            cell, way, why = lake_outlet(fd, geom, T, (r_, c_), index, wet, nhdplus_exit(shapely.make_valid(geom), v2),
                                         sides_)
            if cell is not None:
                rc_, cc_ = cell
                edge = (not (0 < rc_ < H - 1 and 0 < cc_ < W - 1 and (fd[rc_ - 1:rc_ + 2, cc_ - 1:cc_ + 2] > 0).all())
                        or near_shared_edge(rc_, cc_, group, where) or box_of(rc_, cc_) is None
                        or box_of(*way[0]) != box_of(rc_, cc_))
                if edge:      # crossbox.py carries a lake past its dam only within one box: as before for these
                    cell, way, why = None, None, "NHD's outlet lies on an edge between two boxes or on the map's edge"
            if cell is not None:
                moves.append((i, k, geom, name, cell, way, why, sides_))
            elif why != "NHD has no outflow line":
                x_, y_ = T * (c_ + 0.5, r_ + 0.5)
                kept.append((box_of(r_, c_), name, round(geom.area / 1e4, 1), why, round(x_), round(y_)))
        # (c) the lakes taken to NHD's outlet: routed there, the way out pointed along NHD's line to the cell the
        # terrain goes on from (a dam's crest, a sill, the head of a side channel), the outlet a pit
        for i, k, geom, name, cell, way, why, _ in moves:
            r_, c_ = best[i][1], best[i][2]
            if k is not None:           # the cell with the most water is no dead end any more. Where the lake's cells
                fd[r_, c_] = outflow[k][2]      # don't all join NHD's outlet through the lake (two pieces at this
            route_lake(fd, geom, cell, T, lines)        # cell size), that piece flows on as the terrain has it
            for k_, rc in enumerate(way[:-1]):
                fd[rc] = CODE_OF[(way[k_ + 1][0] - rc[0] + 1) * 3 + (way[k_ + 1][1] - rc[1] + 1)]
            out_ = (cell[0], cell[1], int(CODE_OF[(way[0][0] - cell[0] + 1) * 3 + (way[0][1] - cell[1] + 1)]))
            if k is None:                               # it flowed on at an edge between two boxes; NHD's outlet is off it
                outflow.append(out_)
                through.remove(i)
                n_wet += 1
            else:
                outflow[k] = out_
            fd[cell] = PIT
            n_nhd += 1
            b_ = box_of(*cell)
            tops.append((b_, cell[0] - where[b_][0].start, cell[1] - where[b_][1].start,
                         way[0][0] - where[b_][0].start, way[0][1] - where[b_][1].start))
            if "leaves NHD's line" in why:
                loose.append((name, round(geom.area / 1e4, 1)))
            d_ = RES * float(np.hypot(cell[0] - r_, cell[1] - c_))
            if d_ >= 300:
                far.append((name, round(geom.area / 1e4, 1), round(d_), RES * (len(way) - 1), why))
        # each way out was judged before any lake was moved: none may lead back into its lake now that all are
        back_i = {i for i, k, geom, name, cell, way, why, _ in moves
                  if leads_back(fd, way[0][0], way[0][1], lake_cells(fd, geom, T))}
        back = [name for i, k, geom, name, cell, way, why, _ in moves if i in back_i]
        if back:
            print("  WARNING: the way out leads back into the lake, which carries its water nowhere: " + ", ".join(back))
        # (d) a lake's second outlets: its other outflow lines the terrain takes the water on down, by the outlet's own
        # test (lake_outlet's `sides`; judged with it on the surface of (a)). D8 sends a lake's water down one way out,
        # and until 2026-11-22 the maps drew one of the others only by accident, where crossbox.py put the water in
        # away from the outlet (13 at 9 lakes went when it stopped: Round Lake's, Marsh Creek Reservoir's side arms).
        # Each is drawn from the cell where the terrain takes the water on: its line is laid here (side_streams) and
        # 05_score.py keeps it as a side channel of the outlet's creek, scored on the water the lake passes on there.
        # No water is put in: no line carries a lake's water twice. Checked on this surface, now every lake is moved:
        # the way must not lead back into its lake, and must not run up into a lake standing higher (Middle Flow's
        # line to Sand Creek climbs 6 m into Livingston Lake: NHD draws the inflow from it the wrong way round)
        lvl = {}
        for (i_, v_), n_ in level.items():
            if n_ > lvl.get(i_, (0, 0.0))[0]:
                lvl[i_] = (n_, v_ / 100)
        lake_at = lambda rc: next(iter(int(j_) + 1 for j_ in lakes.sindex.query(
            shapely.Point(*(T * (rc[1] + 0.5, rc[0] + 0.5))), predicate="within")), 0)
        for i, k, geom, name, cell, way, why, sides_ in moves:
            win_ = lake_cells(fd, geom, T)
            ha = round(geom.area / 1e4, 1)
            for q, status in sides_:
                top = tuple(int(x_) for x_ in q["cells"][-1])
                if status == "ok" and leads_back(fd, top[0], top[1], win_):
                    status = "the way leads back into the lake"
                if status == "ok":
                    r__, c__ = top
                    for _ in range(4):                  # the way's first cells (follows: within three a lake counts)
                        if wet[r__, c__] and lake_at((r__, c__)) not in (0, i):
                            j_ = lake_at((r__, c__))
                            up_ = lvl.get(j_, (0, np.nan))[1] - lvl.get(i, (0, np.nan))[1]
                            other = lakes.gnis_name.iloc[j_ - 1]
                            other = other if isinstance(other, str) else "an unnamed lake"
                            status = (f"it runs up into {other}, {up_:.1f} m above the lake: an inflow drawn the wrong way"
                                      if up_ > LEVEL_TOL else f"it runs into {other} at once: nothing to draw")
                            break
                        k_ = int(fd[r__, c__])
                        if k_ not in CODE_SET:
                            break
                        r__, c__ = r__ + int(DR[k_]), c__ + int(DC[k_])
                        if not (0 <= r__ < H and 0 <= c__ < W):
                            break
                if status == "ok" and top in side_seen:
                    status = "the same cell as another outflow line of the lake"
                if status != "ok":
                    side_not.setdefault(status if "runs" not in status else status.split(":")[1].strip(), []).append(
                        f"{name} ({ha:g} ha)" + (f": {status.split(':')[0]}" if "runs" in status else ""))
                    continue
                side_seen.add(top)
                b_, mb_ = box_of(*top), box_of(*way[0])
                sides.append((b_, dict(top=[top[0] - where[b_][0].start, top[1] - where[b_][1].start],
                                       main=[way[0][0] - where[mb_][0].start, way[0][1] - where[mb_][1].start],
                                       main_box=mb_, lake=name, ha=ha, exit=[round(q["exit"].x), round(q["exit"].y)])))
                side_ok.append(f"{name} ({ha:g} ha)")
        # (e) the water goes on at the outlet (2026-11-22, the audit's finding 6). Until then every lake ended its water in
        # a pit at its outlet cell and its way out started in the next cell; crossbox.py carried the water across, and
        # every later step found it again (the drops and the size floor added it, 05b_flow.py jumped the pit, 06_map.py
        # drew straight joins across 935 dams, drew 59 mi of line below dams and ponds and raised the stream order of
        # 5,970 reaches whose count had started again at 1 below a lake). Now a lake taken to NHD's outlet points its
        # outlet at the first cell of its way out, so its water, its stream line and its order run on. The pit stays at
        # a lake whose outlet stays at the cell with the most water (no outflow line in NHD, or one the terrain refuses:
        # crossbox.py still carries those as before) and at one whose way out leads back into it.
        opened = []                                     # (outlet cell, flat; a pond: NHDPlus has no line through it)
        for i, k, geom, name, cell, way, why, _ in moves:
            if i in back_i:
                continue
            fd[cell] = CODE_OF[(way[0][0] - cell[0] + 1) * 3 + (way[0][1] - cell[1] + 1)]
            pond = False
            if v2 is not None:
                lk_ = shapely.make_valid(geom)
                ins = v2[0].iloc[v2[0].sindex.query(lk_, predicate="intersects")]
                pond = not len(ins) or not (ins.geometry.intersection(lk_).length >= 0.25 * ins.geometry.length).any()
            opened.append((cell[0] * W + cell[1], pond))
        # (f) ponds drain at NHD's outlet as one, without ending their creek (2026-11-23). still_water() takes NHD's
        # lakes of MIN_RESERVOIR_KM2 or more; a smaller pond kept the D8 directions the terrain step gave its flat water.
        # Where that flat has two ways out, part of the pond went each way: flatlines.py sends the part near NHD's line
        # out along it, and the rest still spills where the filled surface does. At North Teton Creek Lake (Jackson,
        # 1.5 ha) the halves, 0.17 and 0.09 km2, stayed apart for 230 m, each under the channel start, and the map had
        # no outlet creek. A pond NHD maps an outflow from is now routed as the lakes above are, by the same test
        # (lake_outlet): every cell to NHD's outlet along NHD's lines through it (route_lake), the way out pointed along
        # NHD's line to the cell the terrain takes the water on from. Its outlet is no pit and no outlet of (e): the
        # water goes on down the creek, and no line, crossbox link or held water is added. A pond's other outflow lines
        # the terrain takes the water on down are its second outlets, judged as the lakes' in (d): where the pond's
        # water now goes down NHD's outlet, NHD's other channel keeps its line, as a side channel (Ampersand Brook's
        # east channel below Stony Creek Ponds, the LA washes: lost on the first build without them).
        n_pond = n_back = n_pside = 0
        far_p = []
        for n_seen, g_ in enumerate(ponds.geometry.values):
            win_ = lake_cells(fd, g_, T)
            if win_ is None or win_[2].sum() < 2:
                continue
            r0_, c0_, m_ = win_
            rr_, cc_ = np.nonzero(m_)
            j_ = int(np.argmax(acc[r0_ + rr_, c0_ + cc_]))
            best_ = (r0_ + int(rr_[j_]), c0_ + int(cc_[j_]))
            sides_p = []
            cell, way, why = lake_outlet(fd, g_, T, best_, index, wet, nhdplus_exit(g_, v2), sides_p)
            if cell is None:
                continue
            if (not (0 < cell[0] < H - 1 and 0 < cell[1] < W - 1) or near_shared_edge(cell[0], cell[1], group, where)
                    or box_of(*cell) is None or box_of(*way[0]) != box_of(*cell)):
                continue
            h_, w_ = m_.shape
            saved, saved_way = fd[r0_:r0_ + h_, c0_:c0_ + w_].copy(), [(rc, int(fd[rc])) for rc in [cell] + list(way)]
            route_lake(fd, g_, cell, T, lines)
            for k_, rc in enumerate(way[:-1]):
                fd[rc] = CODE_OF[(way[k_ + 1][0] - rc[0] + 1) * 3 + (way[k_ + 1][1] - rc[1] + 1)]
            fd[cell] = CODE_OF[(way[0][0] - cell[0] + 1) * 3 + (way[0][1] - cell[1] + 1)]
            if leads_back(fd, way[-1][0], way[-1][1], lake_cells(fd, g_, T)):     # its water must go on: undone
                fd[r0_:r0_ + h_, c0_:c0_ + w_] = saved
                for rc, v_ in saved_way:
                    fd[rc] = v_
                n_back += 1
                continue
            n_pond += 1
            win_p = lake_cells(fd, g_, T)
            name_p = ponds.gnis_name.iloc[n_seen] if isinstance(ponds.gnis_name.iloc[n_seen], str) else "unnamed"
            for q, status in sides_p:                   # its second outlets, by (d)'s tests
                top = tuple(int(x_) for x_ in q["cells"][-1])
                if status == "ok" and leads_back(fd, top[0], top[1], win_p):
                    status = "the way leads back into the lake"
                if status == "ok":
                    r__, c__ = top
                    for _ in range(4):                  # a way that runs into a lake that holds water within three
                        if wet[r__, c__]:               # cells has nothing to draw
                            status = "it runs into a lake at once"
                            break
                        k_ = int(fd[r__, c__])
                        if k_ not in CODE_SET:
                            break
                        r__, c__ = r__ + int(DR[k_]), c__ + int(DC[k_])
                        if not (0 <= r__ < H and 0 <= c__ < W):
                            break
                if status == "ok" and top in side_seen:
                    status = "the same cell as another outflow line of the lake"
                b_, mb_ = box_of(*top), box_of(*way[0])
                if status != "ok" or b_ is None or mb_ is None:
                    continue
                side_seen.add(top)
                sides.append((b_, dict(top=[top[0] - where[b_][0].start, top[1] - where[b_][1].start],
                                       main=[way[0][0] - where[mb_][0].start, way[0][1] - where[mb_][1].start],
                                       main_box=mb_, lake=name_p, ha=round(g_.area / 1e4, 1),
                                       exit=[round(q["exit"].x), round(q["exit"].y)])))
                n_pside += 1
            d_ = RES * float(np.hypot(cell[0] - best_[0], cell[1] - best_[1]))
            if d_ >= 100:
                x_, y_ = T * (cell[1] + 0.5, cell[0] + 0.5)
                far_p.append(f"{ponds.gnis_name.iloc[n_seen] if isinstance(ponds.gnis_name.iloc[n_seen], str) else 'unnamed'}"
                             f" ({g_.area / 1e4:.1f} ha, {d_:.0f} m, at {x_:.0f},{y_:.0f})")
        print(f"ponds under {MIN_RESERVOIR_KM2 * 100:g} ha drained at NHD's outlet: {n_pond} of {len(ponds)}, {len(far_p)} of "
              f"them 100 m or more from the cell with the most water; {n_back} left as they were (the way led back); "
              f"{n_pside} second outlets of ponds laid as side channels")
        if far_p:
            print("  moved 100 m or more: " + "; ".join(far_p))
        del wet
        acc, more = accumulate(fd, DR, DC)
        if more:                                        # a flowing-on lake's outlet pointing back into the lake
            fd[acc < 0] = PIT
            acc, _ = accumulate(fd, DR, DC)
            loops += more
    # The water that came through those outlets (held_km2.tif): all of it (band 1) and what came through a pond NHDPlus
    # has no line for (band 2; 05c_drainages.py picks forks and names on the area without it, as before). The later steps
    # that mean "what the creek's own ground below the lakes gives" (05b_flow.py's natural-flow model in LA, scoring.py's
    # below-a-dam rule, watertemp.py's lake term) read area_edge_km2, which 05c takes as the area less band 1.
    o_all = [o for o, _ in opened]
    o_pond = [o for o, pd_ in opened if pd_]
    held = held_below(fd, acc, o_all, set(o_all))
    held_pond = held_below(fd, acc, o_pond, set(o_pond))
    if opened:
        print(f"  {len(opened)} lakes pass their water on at the outlet ({len(o_pond)} ponds NHDPlus has no line for); "
              f"{len(held):,} cells below them hold it")
    # 4. streams and their orders, across the group
    stream = acc >= int(round(STREAM_KM2 * 1e6 / (RES * RES)))      # in cells: no float copy of a 250-million-cell grid
    n_out = outflow_streams(fd, stream, outflow)
    n_side = side_streams(fd, stream, [(e["top"][0] + where[b_][0].start, e["top"][1] + where[b_][1].start)
                                       for b_, e in sides])
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
    # ... and the channels that start lower along NHD's named and year-round lines: order 1, off `stream` (low_channels)
    n_lh, n_low, c_low, why_low = low_channels(fd, acc, stream, order, T, group) if LOW_LINES else (0, 0, 0, {})
    print(f"{' + '.join(group)}: {W} x {H} cells, {int(stream.sum())} stream cells, max order {int(order.max())}, "
          f"{n_wet} of {len(lakes)} lakes end paths at their outlet ({n_nhd} at NHD's outlet, {len(far)} of them 300 m "
          f"or more from the cell with the most water; {n_routed} routed to it along NHD's lines; "
          f"{n_out} km of stream line added below outlets)"
          + (f" ({len(through)} more flow on: outlet on an edge between boxes: "
             + ", ".join(n if isinstance(n, str) else "unnamed" for n in lakes.gnis_name.iloc[[i - 1 for i in through]]) + ")"
             if through else "")
          + (f", {len(off_map)} drain off the map through their water and carry no stream lines ("
             + ", ".join(n if isinstance(n, str) else "unnamed" for n in lakes.gnis_name.iloc[[i - 1 for i in off_map]]) + ")"
             if off_map else "")
          + (f", {loops} cells on loops ended in pits" if loops else ""))
    for name, ha, d_, across, why in sorted(far, key=lambda q: -q[2]):
        print(f"  outlet moved to NHD's: {name} ({ha:g} ha), {d_:,} m from the cell with the most water"
              + (f", {across} m of way out across a dam or sill" if across else "") + f" ({why})")
    for _, name, ha, why, x_, y_ in kept:
        print(f"  outlet left at the cell with the most water: {name} ({ha:g} ha) at ({x_}, {y_}): {why}")
    if loose:
        print(f"  below {len(loose)} outlets the terrain's way on leaves NHD's outflow line within {FOLLOW_M} m, and is "
              "taken as the terrain has it: " + ", ".join(f"{n} ({ha:g} ha)" for n, ha in sorted(loose, key=lambda q: -q[1])))
    if side_ok:
        print(f"  second outlets laid as side channels: {len(side_ok)} ({n_side} km of stream line added): "
              + ", ".join(side_ok))
    for why_, names_ in side_not.items():
        print(f"  other outflow lines the terrain takes the water on down, not second outlets ({why_}): " + ", ".join(names_))
    if n_lh:
        print(f"  channels started lower along NHD's {' or '.join(LOW_LINES)} lines: {n_low} of {n_lh} upper ends, "
              f"{c_low * RES / 1000:.1f} km of line (order 1); none at the others: "
              + ", ".join(f"{k} {v}" for k, v in sorted(why_low.items(), key=lambda q: -q[1])))
    # 5. each box's files
    from pysheds.grid import Grid
    from pysheds.sview import Raster, ViewFinder
    import pandas as pd
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
        hb = np.zeros((2, sl[0].stop - sl[0].start, sl[1].stop - sl[1].start), np.float32)
        for band, d_ in enumerate((held, held_pond)):
            if d_:
                ix = np.fromiter(d_.keys(), np.int64, len(d_))
                vv = np.fromiter(d_.values(), np.float64, len(d_))
                rr_, cc_ = np.divmod(ix, W)
                inb = (rr_ >= sl[0].start) & (rr_ < sl[0].stop) & (cc_ >= sl[1].start) & (cc_ < sl[1].stop)
                hb[band, rr_[inb] - sl[0].start, cc_[inb] - sl[1].start] = vv[inb] * (RES * RES) / 1e6
        with rasterio.open(f"{derived_dir(r)}/held_km2.tif", "w", **dict(prof, dtype="float32", count=2)) as dst:
            dst.write(hb)
        del hb
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
        # the lines laid lower along NHD's named and year-round lines (step 4) are taken apart, so that each is a link
        # of its own that ends on the stream it runs into, and no link of the STREAM_KM2 network is cut where one
        # comes in
        lp = np.zeros((h + 2, w + 2), bool)
        lp[rr0 - R0:rr1 - R0, cc0 - C0:cc1 - C0] = (order[rr0:rr1, cc0:cc1] > 0) & ~stream[rr0:rr1, cc0:cc1]
        for m_ in (sp, lp):
            m_[1, 1:-1] &= fp[0, 1:-1] > 0
            m_[-2, 1:-1] &= fp[-1, 1:-1] > 0
            m_[1:-1, 1] &= fp[1:-1, 0] > 0
            m_[1:-1, -2] &= fp[1:-1, -1] > 0
        fp[~np.isin(fp, CODES)] = 0
        Tp = T * rasterio.Affine.translation(C0, R0)
        grid = Grid(viewfinder=ViewFinder(affine=Tp, shape=fp.shape, crs=CRS, nodata=0))
        vf, parts_ = (lambda nd: ViewFinder(affine=Tp, shape=fp.shape, crs=CRS, nodata=nd)), []
        for m_ in (sp, lp):
            if m_ is lp and not lp.any():
                continue
            net = grid.extract_river_network(Raster(fp, viewfinder=vf(0)), Raster(m_, viewfinder=vf(False)),
                                             dirmap=CODES)
            if net["features"]:
                g_ = gpd.GeoDataFrame.from_features(net["features"], crs=CRS)
                parts_.append(g_.assign(low_channel=int(m_ is lp)))
        del lp
        g = (gpd.GeoDataFrame(pd.concat(parts_, ignore_index=True), crs=CRS) if parts_
             else gpd.GeoDataFrame({"low_channel": []}, geometry=[], crs=CRS))
        ex = g.geometry.apply(lambda ln: not (boxes[r][0] <= ln.coords[-1][0] < boxes[r][2] and boxes[r][1] < ln.coords[-1][1] <= boxes[r][3]))
        n_on = int(ex.sum())
        g.to_file(f"{derived_dir(r)}/dem_streams.gpkg")
        print(f"  {r}: stream cells {int(st.sum())}, links {len(g)} ({int(g.low_channel.sum())} started lower along "
              f"NHD's lines), max order {int(od.max())}, {n_on} lines run on into the next box")
    wet_ = {r: [] for r in group}
    for o, pd_ in opened:
        rr_, cc_ = divmod(o, W)
        b_ = next((b for b in group if where[b][0].start <= rr_ < where[b][0].stop and where[b][1].start <= cc_ < where[b][1].stop), None)
        if b_ is not None:
            wet_[b_].append([rr_ - where[b_][0].start, cc_ - where[b_][1].start, int(pd_)])
    return (left, {r: [list(map(int, q[1:])) for q in tops if q[0] == r] for r in group},
            {r: [list(q[1:]) for q in kept if q[0] == r] for r in group},
            {r: [e for b_, e in sides if b_ == r] for r in group}, wet_)


if __name__ == "__main__":
    only = set(sys.argv[1:])                            # box names: just the groups that hold one of them
    # NHDPlus's lines have to be there before anything is written. Without them the lakes whose outflow lines NHD
    # doesn't name drain by the nearest line instead of the one NHDPlus leaves by (9 lakes on the 12 maps of
    # 2026-11-22, Lake Mathews among them), and a failed download would move them with only a note in a log.
    no_v2 = not os.path.exists(f"{FLOW}/nhdplus_v2.gpkg")
    if no_v2 and not os.environ.get("NO_NHDPLUS"):
        sys.exit(f"03b_stitch.py stopped, nothing written: {FLOW}/nhdplus_v2.gpkg is missing. NHDPlus's lines say which "
                 f"of a lake's outflow lines it drains by. Run AREA={AREA} 02b_download_flow.py first (run_base.sh and "
                 "run_rebuild_a.sh do), or set NO_NHDPLUS=1 to go on without them: a lake with several outflow lines "
                 "that NHD doesn't name then takes the one nearest the cell with the most water.")
    done, left, tops, kept, sides, wet = [], [], {}, {}, {}, {}
    for group in groups():
        if only and not only & set(group):
            continue
        left_, tops_, kept_, sides_, wet_ = run(group)
        left += left_
        tops.update(tops_)
        kept.update(kept_)
        sides.update(sides_)
        wet.update(wet_)
        done += group
    # the lakes' outlets, for crossbox.py: "tops" {box: [[outlet row, col, row, col of the first cell of the way out]]}
    # in each box's own grid; and "kept" {box: [[name, ha, why, x, y]]}, the lakes left at the cell with the most water
    # though NHD has an outflow line. For 05_score.py, "sides" {box: [{top: [row, col] where the terrain takes the
    # water on down a second outlet, main: [row, col] of the first cell of the lake's way out in its box main_box,
    # lake: its name, ha, exit: x, y where the outflow line leaves the lake}]}
    path = f"{SHARED_DERIVED}/lake_outlets.json"
    os.makedirs(SHARED_DERIVED, exist_ok=True)
    old = json.load(open(path)) if os.path.exists(path) else {"tops": {}, "kept": {}}
    old["tops"] = {**{b: v for b, v in old.get("tops", {}).items() if b not in done}, **tops}
    old["kept"] = {**{b: v for b, v in old.get("kept", {}).items() if b not in done}, **kept}
    old["sides"] = {**{b: v for b, v in old.get("sides", {}).items() if b not in done}, **sides}
    # "wet": {box: [[row, col, pond]]}, the outlets that pass their water on (step e): no pit marks them any more
    old["wet"] = {**{b: v for b, v in old.get("wet", {}).items() if b not in done}, **wet}
    with open(path + ".tmp", "w") as fh:
        json.dump(old, fh)
    os.replace(path + ".tmp", path)
    path = f"{SHARED_DERIVED}/stitched.json"
    old = json.load(open(path)) if os.path.exists(path) else []
    os.makedirs(SHARED_DERIVED, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(sorted(set(old) | set(done)), fh)
    if no_v2:
        print("NOTE: this routing was made WITHOUT NHDPlus's lines (NO_NHDPLUS=1): lakes with several outflow lines that "
              "NHD doesn't name drain by the nearest one. Run 02b_download_flow.py and this script again.")
    if left:      # the files are written; the exit status marks the run FAILED in the run_*.sh logs
        print("FAILED: dead ends left on edges between boxes, where water stops short of its outlet: "
              + ", ".join(f"({x:.0f}, {y:.0f}) {a:,.1f} km2" for x, y, a in left))
        sys.exit(1)
