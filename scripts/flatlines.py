"""Flats of filled ground routed along NHD HR's channel lines (03_hydrology.py; 03b_stitch.py where it conditions
a piece of DEM again at a seam).

Filling a depression levels it: a swamp, a wetland, a valley flat behind a sill comes out as one flat surface, and
flat resolution (pysheds' resolve_flats, Barnes et al.) sends its water to the flat's outlet the shortest way: the
ruler-straight lines the maps drew across swamps (the Leicester River across the Otter Creek wetland, seen by the user
on 2026-11-22). NHD HR maps where the channel runs there. So in a flat of filled ground the water runs to the nearest
NHD channel line and along it to an outlet; every other cell keeps the value resolve_flats gives it, so the surface
outside those flats is the same as before, byte for byte. dem_filled.tif and fill_depth.tif (what the drops, profiles
and crossbox.py measure on) don't change; only the routing surface dem_cond.tif does.

  - Lines: StreamRiver (460), ArtificialPath (558) and Connector (334) of every box's nhd_flowlines.gpkg in the area,
    cell by cell in the order NHD digitized them (downstream); not canals, pipelines or coastline. None within EDGE_M
    of the area's outer edge (a line led out over the edge takes the water off the map early: the Deer River and the
    St. Regis in the DEM burn of 2026-11-20).
  - A flat of filled ground: at least FILL_CELLS of its cells were raised FILL_MIN or more by the fill, and they are at
    least FILL_SHARE of it. A river's level water surface (3DEP flattens every wide river in steps) with a few filled
    pockets beside it is not one: routed, its own line could lose to a side line's way out (Otter Creek in a test).
  - Outlets: the cells next to the flat at its level that drain lower (resolve_flats' low edges), and crossings: where
    a line leaves the flat over a rim no more than RISE_MAX above it and comes down to ground at least END_DROP below
    it within WAY_MAX (a sill, a levee, a road over a culvert, which the 10 m DEM holds a few cm above the spill point
    the fill found elsewhere). A crossing's rim cells are stepped down from the flat's level to that ground.
  - Named lines first: from the outlets along the named lines, then along every other line. A line cell's value is
    its distance in cells to an outlet; an unnamed one stands above every named one of its flat, so a named river
    never turns off down an unnamed line. Line cells that reach no outlet count as the rest of the flat.
  - The rest of the flat runs to the nearest line cell that reaches an outlet, or to an outlet: its value is the
    flat's largest line value plus its distance in cells. So water never leaves a line inside the flat.
  - Heights: flat + step x value, the step small enough that the flat stays below every higher cell around it; the
    outlets at the flat's level keep the flat's own height (resolve_flats raised them 2 eps).
  - Left as before: flats of filled ground that hold no NHD line (kettles, urban basins: nothing to follow), and flats
    whose lines reach no outlet (a lake NHD gives no way out, a rim higher than RISE_MAX)."""
import os, functools
import numpy as np, geopandas as gpd, pandas as pd, shapely
from numba import njit
from config import REGIONS, raw_dir, CRS

LINE_FTYPES = (460, 558, 334)
FILL_MIN = 0.05          # m raised by the fill: a cell of levelled ground
FILL_CELLS = 10          # cells of levelled ground (0.1 ha) that make a flat a filled one ...
FILL_SHARE = 0.5         # ... and the share of its cells they must be: a swamp
                         # the fill levelled, not a river's level water surface with a few filled pockets beside it
EDGE_M = 2000.0          # m: no lines this close to the area's outer edge
RISE_MAX = 0.5           # m: the highest rim a line may cross out of its flat (a sill, a levee, a road over a culvert)
WAY_MAX = 200.0          # m: the longest such crossing, from the flat to ground below its level
END_DROP = 1e-4          # m: the crossing comes down to ground this much below the flat's level, so that its stepped
                         # cells fit between the two whatever resolve_flats adds to that ground (at most 3e-5 m)
LINK_MAX = 100.0         # m: an outlet no line cell touches is joined through the flat to the nearest line this close
                         # (NHD's channel passes a few cells off the cell where the DEM's flat spills)
FOLLOW_M, FOLLOW_TOL, FOLLOW_SHARE = 200.0, 40.0, 0.8   # a crossing counts only where the terrain's own D8 path
                         # from the ground it comes down to stays on NHD's lines: this share of its next FOLLOW_M m
                         # within FOLLOW_TOL m of one (03b_stitch.py's test for a lake's way out)


@functools.lru_cache(1)
def lines():
    parts = []
    for r in REGIONS:
        p = f"{raw_dir(r)}/nhd_flowlines.gpkg"
        if os.path.exists(p):
            g = gpd.read_file(p, columns=["ftype", "gnis_name"])
            parts.append(g[g.ftype.isin(LINE_FTYPES)].to_crs(CRS))
    g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=CRS)
    g = g[~g.geometry.is_empty & g.geometry.notna()]
    wkb = g.geometry.normalize().to_wkb()
    return g[~pd.Series(wkb).duplicated().values].reset_index(drop=True)


@functools.lru_cache(1)
def inner():
    """The area's boxes less EDGE_M along its outer edge (edges between boxes are inside)."""
    return shapely.union_all([shapely.box(*v["bbox"]) for v in REGIONS.values()]).buffer(-EDGE_M)


def sequences(shape, transform):
    """Every line's cells in the order NHD digitized them (downstream), as flat arrays: rows, cols, the start of
    each line's run (with a last entry for the end), and whether the line has a name. Cells within EDGE_M of the
    area's outer edge are dropped."""
    H, W = shape
    x0, y1 = transform.c, transform.f
    x1, y0 = x0 + W * transform.a, y1 + H * transform.e
    g = lines()
    g = g[g.intersects(shapely.box(x0, y0, x1, y1))]
    keep = inner()
    R, C, S, N = [], [], [0], []
    for geom, nm in zip(g.geometry.values, g.gnis_name.values):
        named = isinstance(nm, str) and nm.strip() != ""
        for part in getattr(geom, "geoms", [geom]):
            if part.geom_type != "LineString" or part.length < 1:
                continue
            p = shapely.line_interpolate_point(part, np.arange(0.0, part.length + 2.5, 2.5).clip(max=part.length))
            xs, ys = shapely.get_x(p), shapely.get_y(p)
            ins = shapely.contains_xy(keep, xs, ys)
            c = np.floor((xs - x0) / transform.a).astype(np.int64)
            r = np.floor((ys - y1) / transform.e).astype(np.int64)
            ok = ins & (r >= 0) & (r < H) & (c >= 0) & (c < W)
            r, c = r[ok], c[ok]
            if len(r) < 2:
                continue
            dup = np.r_[False, (r[1:] == r[:-1]) & (c[1:] == c[:-1])]
            r, c = r[~dup], c[~dup]
            R.append(r); C.append(c); S.append(S[-1] + len(r)); N.append(np.full(len(r), named))
    if not R:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(1, np.int64), np.zeros(0, bool)
    return np.concatenate(R), np.concatenate(C), np.array(S, np.int64), np.concatenate(N)


@njit(cache=True)
def _crossings(z, lab, qual, drains, sr, sc, ss, rise_max, way_max_cells, end_drop, near, follow_cells, follow_share):
    """Where a line leaves a filled flat over a rim (cells above the flat's level that don't drain at it) and comes
    down to ground below the flat's level within way_max_cells, rising no more than rise_max: the rim cells in order,
    as (flat label, start, end) runs into the returned arrays. Only where the water then goes on along NHD's lines: its
    D8 path (steepest descent) from the first rim cell, over the rim as resolve() steps it down and on over the terrain,
    keeps follow_share of its next follow_cells cells on `near` (cells within FOLLOW_TOL of a line). Otherwise NHD's line leaves over the rim but
    the terrain beyond falls another way (Alder Brook's headwater wetland in central Vermont: its line leaves the flat
    over a 0.3 m rim, the 10 m DEM beyond falls east to the Lamoille, and the crossing sent 19 km2 of Alder Brook
    there instead of out the flat's own spill point into Alder Brook)."""
    H, W = z.shape
    pr = np.empty(ss[-1], np.int64); pc = np.empty(ss[-1], np.int64)
    runs = np.empty((ss[-1], 4), np.int64)       # label, first, last (exclusive) index into pr/pc, end cell index
    n, m = 0, 0
    for s in range(len(ss) - 1):
        a, b = ss[s], ss[s + 1]
        for i in range(a, b - 1):
            r, c = sr[i], sc[i]
            L = lab[r, c]
            if L == 0 or not qual[L]:
                continue
            r2, c2 = sr[i + 1], sc[i + 1]
            if lab[r2, c2] == L or z[r2, c2] <= z[r, c]:
                continue                       # still in the flat, or straight onto an outlet or lower ground
            F = z[r, c]
            j = i + 1
            top = F
            while j < b and j - i - 1 < way_max_cells and z[sr[j], sc[j]] > F:
                if z[sr[j], sc[j]] > top:
                    top = z[sr[j], sc[j]]
                if lab[sr[j], sc[j]] == L:
                    break
                j += 1
            if j >= b or j - i - 1 >= way_max_cells or lab[sr[j], sc[j]] == L or z[sr[j], sc[j]] > F - end_drop:
                continue
            if top - F > rise_max:
                continue
            # the way the water takes from the flat once the rim is stepped down (the rim cells from just under the
            # flat's level to the ground the line comes down to, as resolve() lays them): steepest descent from the
            # first rim cell, the rim at its stepped heights, the rest as the terrain is
            nr = j - i - 1
            lo = z[sr[j], sc[j]]
            rr, cc = sr[i + 1], sc[i + 1]
            steps, on = 0, 0
            for _ in range(follow_cells):
                hr = z[rr, cc]
                for q in range(i + 1, j):
                    if sr[q] == rr and sc[q] == cc:
                        hr = F - (F - lo) * (q - i) / (nr + 1)
                        break
                best, kb = 0.0, -1
                for k in range(8):
                    r3, c3 = rr + DR[k], cc + DC[k]
                    if r3 < 0 or c3 < 0 or r3 >= H or c3 >= W:
                        continue
                    h3 = z[r3, c3]
                    for q in range(i + 1, j):
                        if sr[q] == r3 and sc[q] == c3:
                            h3 = F - (F - lo) * (q - i) / (nr + 1)
                            break
                    sl = (hr - h3) / (1.4142135623730951 if DR[k] != 0 and DC[k] != 0 else 1.0)
                    if sl > best:
                        best, kb = sl, k
                if kb < 0:
                    break                       # a flat or a pit: the path ends there
                rr, cc = rr + DR[kb], cc + DC[kb]
                steps += 1
                if near[rr, cc]:
                    on += 1
            if steps >= 3 and on < follow_share * steps:
                continue
            first = n
            for k in range(i + 1, j):
                pr[n] = sr[k]; pc[n] = sc[k]; n += 1
            runs[m, 0] = L; runs[m, 1] = first; runs[m, 2] = n; runs[m, 3] = j
            m += 1
    return pr[:n], pc[:n], runs[:m]


DR = np.array([-1, -1, 0, 1, 1, 1, 0, -1])
DC = np.array([0, 1, 1, 1, 0, -1, -1, -1])


@njit(cache=True)
def _flats(z, ok):
    """Flat cells (no lower neighbour, not a pit: an equal one) and cells with a lower neighbour, as resolve_flats
    finds them (the grid's rim counts as draining)."""
    H, W = z.shape
    flat = np.zeros((H, W), np.bool_)
    drains = np.zeros((H, W), np.bool_)
    for r in range(H):
        for c in range(W):
            if r == 0 or c == 0 or r == H - 1 or c == W - 1:
                drains[r, c] = True
                continue
            if not ok[r, c]:
                continue
            lower = False
            pit = True
            for k in range(8):
                v = z[r + DR[k], c + DC[k]]
                d = z[r, c] - v
                if d > 0:
                    lower = True
                if not (d < 0):
                    pit = False
            drains[r, c] = lower
            flat[r, c] = (not lower) and (not pit)
    return flat, drains


@njit(cache=True)
def _nearest(lab, line, named, L, orow, ocol, kmax, want_named, seen, prev, dist, qr, qc):
    """Breadth first through flat L from the cells next to outlet (orow, ocol), kmax cells at most: the nearest
    (named) line cell as row * W + col, or -1. prev holds the way back (local to the outlet)."""
    H, W = lab.shape
    o = kmax + 1
    seen[:, :] = False
    n = 0
    for k in range(8):
        rr, cc = orow + DR[k], ocol + DC[k]
        a, b = rr - orow + o, cc - ocol + o
        if lab[rr, cc] == L and not seen[a, b]:
            seen[a, b] = True
            prev[a, b] = -1
            dist[a, b] = 1
            qr[n] = rr; qc[n] = cc; n += 1
    h = 0
    while h < n:
        rr, cc = qr[h], qc[h]; h += 1
        a, b = rr - orow + o, cc - ocol + o
        if line[rr, cc] and (named[rr, cc] or not want_named):
            return rr * W + cc
        if dist[a, b] >= kmax:
            continue
        for k in range(8):
            r2, c2 = rr + DR[k], cc + DC[k]
            if r2 < 1 or c2 < 1 or r2 >= H - 1 or c2 >= W - 1:
                continue
            a2, b2 = r2 - orow + o, c2 - ocol + o
            if lab[r2, c2] == L and not seen[a2, b2]:
                seen[a2, b2] = True
                prev[a2, b2] = rr * W + cc
                dist[a2, b2] = dist[a, b] + 1
                qr[n] = r2; qc[n] = c2; n += 1
    return -1


@njit(cache=True)
def _connect(z, drains, lab, qual, line, named, xlab, nlab, kmax):
    """Flats whose lines lead to none of their outlets. NHD's channel can pass a cell or two off the cell where the
    DEM's flat spills (the Leicester River 2 cells off the only outlet of the Otter Creek wetland: none of its lines
    led out, and the whole flat took the shortest ways to that outlet, ruler-straight). So in a qualifying flat where
    no outlet touches a named line, the shortest way through the flat (kmax cells at most) from each of its low edges
    to the nearest named line cell becomes named line; in one where no outlet touches any line (and no named way was
    made), the way to the nearest line cell becomes line. Only from low edges, not from crossings: a crossing is on
    its own line, and a named river joined to a side line's crossing would leave the flat by it. Returns how many ways
    of each length (cells) were made."""
    H, W = z.shape
    touch_named = np.zeros(nlab + 1, np.bool_)
    touch_line = np.zeros(nlab + 1, np.bool_)
    made = np.zeros(nlab + 1, np.bool_)
    # which flats have an outlet (a low edge or a crossing's first rim cell) that a (named) line cell touches
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            L = lab[r, c]
            if L == 0 or not qual[L] or not line[r, c]:
                continue
            for k in range(8):
                rr, cc = r + DR[k], c + DC[k]
                if (drains[rr, cc] and z[rr, cc] == z[r, c]) or xlab[rr, cc] == L:
                    touch_line[L] = True
                    if named[r, c]:
                        touch_named[L] = True
    side = 2 * kmax + 3
    seen = np.zeros((side, side), np.bool_)
    prev = np.zeros((side, side), np.int64)
    dist = np.zeros((side, side), np.int32)
    qr = np.empty(side * side, np.int64)
    qc = np.empty(side * side, np.int64)
    lens = np.zeros(kmax + 2, np.int64)
    o = kmax + 1
    for want_named in (True, False):
        for r in range(1, H - 1):
            for c in range(1, W - 1):
                L = lab[r, c]
                if L == 0 or not qual[L]:
                    continue
                if want_named and touch_named[L]:
                    continue
                if not want_named and (touch_line[L] or made[L]):
                    continue
                for k in range(8):
                    orow, ocol = r + DR[k], c + DC[k]
                    if not (drains[orow, ocol] and z[orow, ocol] == z[r, c]):
                        continue
                    if orow < 1 or ocol < 1 or orow >= H - 1 or ocol >= W - 1:
                        continue
                    done = False                 # this outlet already joined (a cell next to it is a line of L)
                    for k2 in range(8):
                        rr, cc = orow + DR[k2], ocol + DC[k2]
                        if lab[rr, cc] == L and line[rr, cc] and (named[rr, cc] or not want_named):
                            done = True
                    if done:
                        continue
                    t = _nearest(lab, line, named, L, orow, ocol, kmax, want_named, seen, prev, dist, qr, qc)
                    if t < 0:
                        continue
                    m = 0
                    i = prev[t // W - orow + o, t % W - ocol + o]
                    while i >= 0:
                        rr, cc = i // W, i % W
                        line[rr, cc] = True
                        if want_named:
                            named[rr, cc] = True
                        m += 1
                        i = prev[rr - orow + o, cc - ocol + o]
                    made[L] = True
                    lens[min(m, kmax + 1)] += 1
    return lens


@njit(cache=True)
def _join(lab, line, val, kmax, qr, qc):
    """Line pieces the walk along the lines didn't reach: NHD's line broken inside its flat by a hummock, a bank or a
    road the fill left above the flat's level, so the walk stopped there and the rest of the line counted as the rest
    of the flat (its water took the shortest way to the nearest reached line, straight). From every reached line cell,
    breadth first through the flat's cells not yet reached, kmax cells at most; a line cell met is joined: the way
    there becomes line, rising one step a cell from the reached cell, and its piece is walked on from it. Rounds until
    no piece is joined. qr, qc: work queues (H * W). Returns how many pieces were joined."""
    H, W = lab.shape
    dist = np.zeros((H, W), np.int16)            # cells from the nearest reached line cell, this round (0: not met)
    back = np.full((H, W), -1, np.int8)          # the direction (index into DR, DC) a cell was met from
    joined = 0
    while True:
        n = 0
        for r in range(1, H - 1):
            for c in range(1, W - 1):
                L = lab[r, c]
                if L == 0 or not line[r, c] or val[r, c] <= 0:
                    continue
                for k in range(8):
                    rr, cc = r + DR[k], c + DC[k]
                    if lab[rr, cc] == L and val[rr, cc] == 0:
                        qr[n] = r; qc[n] = c; n += 1
                        dist[r, c] = -1          # a source
                        break
        if n == 0:
            break
        h = 0
        hits = 0
        ends = n                                  # where the hits are kept: after the queue, from the far end
        top_ = qr.shape[0]
        while h < n:
            r, c = qr[h], qc[h]; h += 1
            L = lab[r, c]
            d = 0 if dist[r, c] < 0 else dist[r, c]
            if d >= kmax:
                continue
            for k in range(8):
                rr, cc = r + DR[k], c + DC[k]
                if rr < 1 or cc < 1 or rr >= H - 1 or cc >= W - 1:
                    continue
                if lab[rr, cc] != L or val[rr, cc] != 0 or dist[rr, cc] != 0:
                    continue
                dist[rr, cc] = d + 1
                back[rr, cc] = k
                if line[rr, cc]:                  # an unreached line cell: a piece to join; the walk doesn't go past it
                    top_ -= 1
                    qr[top_] = rr; qc[top_] = cc; hits += 1
                else:
                    qr[n] = rr; qc[n] = cc; n += 1
        # join the pieces met, nearest first (the queue's end holds them in the order met)
        nj = 0
        for i in range(qr.shape[0] - 1, top_ - 1, -1):
            ur, uc = qr[i], qc[i]
            if val[ur, uc] != 0:
                continue                           # its piece was walked from another join this round
            # the way back to the reached cell
            m = 0
            r, c = ur, uc
            while dist[r, c] > 0:
                k = back[r, c]
                r, c = r - DR[k], c - DC[k]
                m += 1
            # values up from the reached cell to the line cell met
            base = val[r, c]
            cells_r = np.empty(m, np.int64); cells_c = np.empty(m, np.int64)
            r, c = ur, uc
            j = m - 1
            while dist[r, c] > 0:
                cells_r[j] = r; cells_c[j] = c; j -= 1
                k = back[r, c]
                r, c = r - DR[k], c - DC[k]
            for j in range(m):
                r, c = cells_r[j], cells_c[j]
                if val[r, c] > 0:
                    base = val[r, c]
                    continue
                base += 1
                val[r, c] = base
                line[r, c] = True
            # walk the piece on from the joined cell
            qr2 = 0
            # reuse the front of the queue: this round's breadth-first part is done
            qr[0] = ur; qc[0] = uc; n2 = 1
            while qr2 < n2:
                r, c = qr[qr2], qc[qr2]; qr2 += 1
                L = lab[r, c]
                for k in range(8):
                    rr, cc = r + DR[k], c + DC[k]
                    if lab[rr, cc] == L and line[rr, cc] and val[rr, cc] == 0:
                        val[rr, cc] = val[r, c] + 1
                        if n2 < top_:
                            qr[n2] = rr; qc[n2] = cc; n2 += 1
            nj += 1
        # clear this round's marks
        dist[:, :] = 0
        back[:, :] = -1
        joined += nj
        if nj == 0:
            break
    return joined


@njit(cache=True)
def _route(z, flat, drains, lab, qual, line, named, nlab, xlab, kjoin, bar):
    """Values for the cells of qualifying flats whose lines reach an outlet: line cells their distance along the lines
    to an outlet (1 = next to one), other cells the flat's largest line distance plus their distance in cells to the
    nearest such line cell or outlet. 0 elsewhere. Also each label's largest value and whether it was routed."""
    H, W = z.shape
    val = np.zeros((H, W), np.int32)
    used = np.zeros(nlab + 1, np.bool_)
    dmax = np.zeros(nlab + 1, np.int32)
    qr = np.empty(H * W, np.int32)
    qc = np.empty(H * W, np.int32)
    n = 0
    # named line cells next to an outlet of their own flat: an outlet is a cell at the same level that drains lower,
    # or the first rim cell of a crossing out of the flat
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            L = lab[r, c]
            if L == 0 or not qual[L] or not named[r, c]:
                continue
            for k in range(8):
                rr, cc = r + DR[k], c + DC[k]
                if (drains[rr, cc] and z[rr, cc] == z[r, c]) or xlab[rr, cc] == L:
                    val[r, c] = 1
                    qr[n] = r; qc[n] = c; n += 1
                    used[L] = True
                    dmax[L] = max(dmax[L], 1)
                    break
    # along the named lines, within the flat
    h = 0
    while h < n:
        r, c = qr[h], qc[h]; h += 1
        L = lab[r, c]
        for k in range(8):
            rr, cc = r + DR[k], c + DC[k]
            if lab[rr, cc] == L and named[rr, cc] and val[rr, cc] == 0:
                val[rr, cc] = val[r, c] + 1
                dmax[L] = max(dmax[L], val[rr, cc])
                qr[n] = rr; qc[n] = cc; n += 1
    # then every other line cell, from the outlets and the named lines reached: they stand above every named line
    # cell of their flat, so the water of a named river never turns off down an unnamed line
    m0 = 0
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            L = lab[r, c]
            if L == 0 or not qual[L] or not line[r, c] or val[r, c] > 0:
                continue
            for k in range(8):
                rr, cc = r + DR[k], c + DC[k]
                if (drains[rr, cc] and z[rr, cc] == z[r, c]) or xlab[rr, cc] == L or (lab[rr, cc] == L and val[rr, cc] > 0):
                    val[r, c] = -1                 # placed below, once each flat's largest named distance is known
                    qr[m0] = r; qc[m0] = c; m0 += 1
                    used[L] = True
                    break
    for i in range(m0):
        r, c = qr[i], qc[i]
        val[r, c] = dmax[lab[r, c]] + 1
    h = 0
    n = m0
    while h < n:
        r, c = qr[h], qc[h]; h += 1
        L = lab[r, c]
        for k in range(8):
            rr, cc = r + DR[k], c + DC[k]
            if lab[rr, cc] == L and line[rr, cc] and val[rr, cc] == 0:
                val[rr, cc] = val[r, c] + 1
                qr[n] = rr; qc[n] = cc; n += 1
    # pieces of line the walk didn't reach, joined through the flat to the reached ones
    nj = _join(lab, line, val, kjoin, qr, qc)
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            L = lab[r, c]
            if L > 0 and val[r, c] > dmax[L]:
                dmax[L] = val[r, c]
    # the rest of each routed flat: distance in cells to the nearest routed line cell or outlet
    dist = np.zeros((H, W), np.int32)
    m = 0
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            L = lab[r, c]
            if L == 0 or not used[L] or val[r, c] > 0:
                continue
            near = False
            for k in range(8):
                rr, cc = r + DR[k], c + DC[k]
                if (lab[rr, cc] == L and val[rr, cc] > 0) or (drains[rr, cc] and z[rr, cc] == z[r, c]) or xlab[rr, cc] == L:
                    near = True
                    break
            if near:
                dist[r, c] = 1
                qr[m] = r; qc[m] = c; m += 1
    h = 0
    while h < m:
        r, c = qr[h], qc[h]; h += 1
        L = lab[r, c]
        for k in range(8):
            rr, cc = r + DR[k], c + DC[k]
            if lab[rr, cc] == L and val[rr, cc] == 0 and dist[rr, cc] == 0:
                dist[rr, cc] = dist[r, c] + 1
                qr[m] = rr; qc[m] = cc; m += 1
    top = np.zeros(nlab + 1, np.int32)
    for r in range(H):
        for c in range(W):
            L = lab[r, c]
            if L == 0 or not used[L]:
                continue
            if val[r, c] == 0:
                if dist[r, c] == 0:       # a cell of the flat no outlet reaches: leave it to resolve_flats
                    continue
                d_ = dist[r, c]
                # near a walked line (kjoin cells), the shortest way to it; farther, resolve_flats' own order
                # (towards the flat's outlets, away from higher ground), as before: water far from NHD's lines
                # takes no new straight way across the flat
                val[r, c] = dmax[L] + (d_ if d_ <= kjoin else kjoin + max(bar[r, c], 1))
            top[L] = max(top[L], val[r, c])
    return val, used, top


@njit(cache=True)
def _margin(z, lab, used, nlab):
    """For each routed flat, how far below its lowest higher neighbour it stands."""
    H, W = z.shape
    mg = np.full(nlab + 1, np.inf)
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            L = lab[r, c]
            if L == 0 or not used[L]:
                continue
            for k in range(8):
                d = z[r + DR[k], c + DC[k]] - z[r, c]
                if d > 0 and d < mg[L]:
                    mg[L] = d
    return mg


@njit(cache=True)
def _exits(z, drains, lab, use):
    """The outlets of the routed flats: cells at a routed flat's level, next to it, that drain lower."""
    H, W = z.shape
    ex = np.zeros((H, W), np.bool_)
    for r in range(1, H - 1):
        for c in range(1, W - 1):
            L = lab[r, c]
            if L == 0 or not use[L]:
                continue
            for k in range(8):
                rr, cc = r + DR[k], c + DC[k]
                if drains[rr, cc] and z[rr, cc] == z[r, c]:
                    ex[rr, cc] = True
    return ex


@njit(cache=True)
def _leaves(out, ok, lab, runs, pr, pc, use, sr, sc, ss, follow_cells, tol_cells, follow_share):
    """For each crossing of a routed flat, whether the water leaving by it then leaves the line it crossed by: its D8
    path on the finished surface (every flat routed), from the crossing's first rim cell, through every flat it comes
    down into and follow_cells on past the last (as far as that line goes), keeps less than follow_share of its steps
    within tol_cells of the line. The rim alone can't tell: past it a line can come down into another flat whose own
    way out is elsewhere (Alder Brook's headwater wetland, central Vermont: NHD's line leaves over a 0.15 m rim into
    a lower flat, which the fill drains east; the water went 150 m down the line, then east to the Lamoille, 19 km2 of
    Alder Brook with it, instead of out the upper flat's own spill point into Alder Brook)."""
    H, W = out.shape
    bad = np.zeros(runs.shape[0], np.bool_)
    for t in range(runs.shape[0]):
        L, i0, i1, j = runs[t, 0], runs[t, 1], runs[t, 2], runs[t, 3]
        if not use[L] or i1 <= i0:
            continue
        q = np.searchsorted(ss, j, side="right") - 1          # the line's cells (a sample each): ss[q] .. ss[q + 1]
        a, b = ss[q], ss[q + 1]
        k_max = b - j                                          # the line goes on this many cells past the ground below
        if k_max < 3:
            continue
        lo_s = max(a, j - (i1 - i0) - 2)
        hi_s = b
        rr, cc = pr[i0], pc[i0]
        steps, on, after = 0, 0, 0
        while steps < k_max and after < follow_cells:
            best, kb = 0.0, -1
            for k in range(8):
                r3, c3 = rr + DR[k], cc + DC[k]
                if r3 < 0 or c3 < 0 or r3 >= H or c3 >= W or not ok[r3, c3]:
                    continue
                sl = (out[rr, cc] - out[r3, c3]) / (1.4142135623730951 if DR[k] != 0 and DC[k] != 0 else 1.0)
                if sl > best:
                    best, kb = sl, k
            if kb < 0:
                break
            rr, cc = rr + DR[kb], cc + DC[kb]
            steps += 1
            after = 0 if lab[rr, cc] > 0 else after + 1
            for u in range(lo_s, hi_s):
                if abs(sr[u] - rr) <= tol_cells and abs(sc[u] - cc) <= tol_cells:
                    on += 1
                    break
        if steps >= 3 and on < follow_share * steps:
            bad[t] = True
    return bad


def resolve(grid, dem, flooded, transform, eps, max_iter, stats=None):
    """resolve_flats(flooded) with the flats of filled ground routed along NHD HR's lines. dem: the DEM before the
    fill (pysheds Raster or array, NaN or nodata where no ground); returns a float64 array."""
    from skimage.measure import label
    out = np.asarray(grid.resolve_flats(flooded, eps=eps, max_iter=max_iter), np.float64).copy()
    z = np.asarray(flooded, np.float64)
    raw = np.asarray(dem, np.float64)
    nod = getattr(flooded, "nodata", None)
    ok = np.isfinite(z) & np.isfinite(raw)
    if nod is not None and np.isfinite(nod):
        ok &= (z != nod) & (raw != nod)
    zz = np.where(ok, z, np.nanmax(np.where(ok, z, -np.inf)) + 1.0)
    flat, drains = _flats(zz, ok)
    lab, nlab = label(flat, connectivity=2, return_num=True)
    lab = lab.astype(np.int32)
    filled = ok & ((z - raw) >= FILL_MIN)
    nf = np.bincount(lab[filled & flat], minlength=nlab + 1)
    qual = (nf >= FILL_CELLS) & (nf >= FILL_SHARE * np.bincount(lab.ravel(), minlength=nlab + 1))
    del filled
    qual[0] = False
    sr, sc, ss, sn = sequences(z.shape, transform)
    line = np.zeros(z.shape, bool)
    line[sr, sc] = True                          # the lines' cells, as the crossings walk them
    line &= flat
    named = np.zeros(z.shape, bool)
    named[sr[sn], sc[sn]] = True
    named &= flat
    from scipy.ndimage import binary_dilation
    near = np.zeros(z.shape, bool)
    near[sr, sc] = True
    tol = int(round(FOLLOW_TOL / abs(transform.a)))
    near = binary_dilation(near, structure=np.ones((2 * tol + 1, 2 * tol + 1), bool))
    pr, pc, runs = _crossings(zz, lab, qual, drains, sr, sc, ss, RISE_MAX, int(WAY_MAX / abs(transform.a)), END_DROP,
                              near, int(FOLLOW_M / abs(transform.a)), FOLLOW_SHARE)
    # one crossing per rim cell: a later one that shares a cell with one already taken is dropped (the same line
    # digitized twice, or two lines over one sill)
    taken = np.zeros(z.shape, bool)
    keep = []
    for k, (L, i0, i1, j) in enumerate(runs):
        cells = (pr[i0:i1], pc[i0:i1])
        if i1 > i0 and not taken[cells].any() and not taken[sr[j], sc[j]]:
            taken[cells] = True
            keep.append(k)
    runs = runs[keep] if len(keep) else runs[:0]
    # resolve_flats' own order on the flats (its rise over the flat's level, in steps of eps)
    bar = np.zeros(z.shape, np.int32)
    fo = flat & ok
    bar[fo] = np.minimum(np.rint((out[fo] - zz[fo]) / eps), 2 ** 30).astype(np.int32)
    del fo
    lvl = np.zeros(nlab + 1)
    rr, cc = np.nonzero(lab > 0)
    lvl[lab[rr, cc]] = zz[rr, cc]
    del rr, cc
    floor = np.spacing(np.abs(lvl)) * 8
    base = out
    line0, named0 = line, named
    dropped = 0
    # routed, then each crossing checked on the finished surface; the ones whose water leaves NHD's lines are dropped
    # and the flats routed again, until none is (each round drops one at least)
    while True:
        line, named = line0.copy(), named0.copy()           # the links and joins below add to them
        xlab = np.zeros(z.shape, np.int32)
        for L, i0, i1, _ in runs:
            xlab[pr[i0], pc[i0]] = L             # a crossing's first rim cell: an outlet of its flat
        # outlets that NHD's lines pass a few cells off: joined to the nearest (named) line through the flat
        links = _connect(zz, drains, lab, qual, line, named, xlab, nlab, int(LINK_MAX / abs(transform.a)))
        val, used, top = _route(zz, flat, drains, lab, qual, line, named, nlab, xlab, int(LINK_MAX / abs(transform.a)), bar)
        mg = _margin(zz, lab, used, nlab)
        F = np.flatnonzero(used)
        step = np.full(nlab + 1, eps)
        # the flat stays below its lowest higher neighbour, and each step still shows on a float64 height
        step[F] = np.minimum(eps, 0.5 * mg[F] / np.maximum(top[F], 1))
        skip = np.zeros(nlab + 1, bool)
        skip[F] = step[F] < floor[F]
        use = used & ~skip
        out = base.copy()
        sel = (val > 0) & use[lab]
        out[sel] = zz[sel] + step[lab[sel]] * val[sel]
        # the outlets at the flat's own level: resolve_flats raised them 2 eps, which a routed flat's first line cell
        # (1 step) would stand below
        ex = _exits(zz, drains, lab, use) & ok
        out[ex] = zz[ex]
        # the crossings of routed flats: their rim cells stepped down from just under the flat's level to just over
        # the ground they come down to (END_DROP below the flat at least, so there is room)
        nx = 0
        applied = np.zeros(z.shape, bool)
        for L, i0, i1, j in runs:
            if not use[L]:
                continue
            cells = (pr[i0:i1], pc[i0:i1])
            hi = float(lvl[L])
            lo = float(out[sr[j], sc[j]])
            n_ = i1 - i0
            out[cells] = hi - (hi - lo) * np.arange(1, n_ + 1) / (n_ + 1)
            applied[cells] = True
            nx += 1
        bad = (_leaves(out, ok, lab, runs, pr, pc, use, sr, sc, ss, int(FOLLOW_M / abs(transform.a)), tol, FOLLOW_SHARE)
               if len(runs) else np.zeros(0, bool))
        if not bad.any():
            break
        dropped += int(bad.sum())
        runs = runs[~bad]
    del base, bar, near
    if stats is not None:
        stats.update(crossings_dropped=dropped, links=int(links.sum()), link_cells=int((links * np.arange(len(links))).sum()), flats=int(nlab), filled_flats=int(qual.sum()), routed=int(use.sum()), skipped=int(skip.sum()),
                     cells=int(sel.sum()), line_cells=int((sel & line).sum()), crossings=int(nx),
                     crossing_cells=int(applied.sum()))
        if stats.get("masks") is True:
            stats["crossings_list"] = [(int(L), int(i1 - i0), float(zz[pr[i0:i1], pc[i0:i1]].max() - lvl[L]))
                                       for L, i0, i1, j in runs if use[L] and i1 > i0]
        if stats.get("masks"):
            stats["masks"] = dict(routed=sel, filled_flat=qual[lab] & (lab > 0), line=line, exits=ex, crossing=applied,
                                  named=named, xlab=xlab > 0, val=val, lab=lab)
    return out
