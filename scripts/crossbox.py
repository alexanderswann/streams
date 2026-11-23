"""Links where the D8 paths stop short: at the edges between study boxes, and in reservoirs.

Each range's hydrology (03_hydrology.py) sees only its own box, so a creek that crosses into the next box starts
there again with no drainage area. In the Piru & Castaic box the Santa Clara River arrived from the San Gabriel box
with none, so Piru Creek won the trunk and the river's own valley was labelled as a fork. inflows() follows every
basin that drains off an edge two boxes share into the neighbouring box and carries its area across (with whatever
flowed into it from a third box), so 05c_drainages.py can add it along the creek there. 06_map.py uses the same edge
and downhill helpers to give a basin cut by an edge the drainage it continues into.

pysheds can't route water across a big flat lake surface either, so every large reservoir ends its D8 paths in pits
and the creek below the dam starts again near nothing (San Gabriel Reservoir, Castaic, Pyramid, Big Tujunga, Lake
Hemet...). With through_dams, inflows() also carries a reservoir's area to the cell below its dam where the water
goes on. Since 2026-11-22 that is the first cell of the way out 03b_stitch.py lays where NHD's stream network leaves
the lake (lake_outlets.json), for every lake it ends there. For the rest it is found here, on the NHDPlus flowlines
leaving the lake, or for a pond NHDPlus has no flowline for, on the detailed NHD stream line leaving it. Drainages
still end at dams; only areas use this.

A river that enters from outside every box (the Maury above Goshen Pass, Otter Creek, the Chattahoochee below Lake
Lanier, the Snake) started with nothing too. Wherever an NHDPlus V2 line crosses the outer boundary flowing in, at any
size, what it brings that the box's own routing doesn't have is carried in the same way ("outside"), in both
variants: NHDPlus's total at the line's lower end less what the box gathers there, so a river that only brushes the
boundary adds nothing.
"""
import json, os
from collections import defaultdict
import numpy as np, pandas as pd, geopandas as gpd, rasterio, rasterio.windows, shapely, shapely.ops
from config import REGIONS, ROOT, RES, CRS, SHARED_DERIVED, NATIONAL, derived_dir, raw_dir

D8 = {1: (0, 1), 2: (1, 1), 4: (1, 0), 8: (1, -1), 16: (0, -1), 32: (-1, -1), 64: (-1, 0), 128: (-1, 1)}
CACHE = f"{SHARED_DERIVED}/inflows.json"
VERSION = 23
MIN_KM2 = 0.1    # smaller basins draining off an edge or into a lake add nothing worth carrying
OUTSIDE_FOLLOW_M = 15000   # a river entering from outside whose water the routing takes straight back out over the
                           # edge is handed over this far down its mapped line at most
REENTER_M, REENTER_NEAR_M, REENTER_MAX, REENTER_NHD, REENTER_GROW = 200, 300, 5, 0.6, 2.0   # a river whose path
                           # leaves the map where the mapped river stays in: its water goes in again where a path
                           # from the river stays in this far, along NHD's detailed lines (see _build)
OUTFLOW_NEAR_M = 100   # the cell found below a dam lies on the lake's routed way out within this distance of it


def fdir_path(region):
    return f"{derived_dir(region)}/flowdir.tif"


def jump(ptr):
    """Pointer jumping: follow ptr to its fixed point (each round doubles the distance covered)."""
    for _ in range(40):
        pp = ptr[ptr]
        if np.array_equal(pp, ptr):
            return pp
        ptr = pp
    return ptr


def graph(fdir):
    """Downstream neighbour of every cell (flat index) and the outlet cell it drains to. Off-grid cells, sinks and
    flats point at themselves."""
    H, W = fdir.shape
    idx = np.arange(H * W, dtype=np.int32)
    rr, cc = np.divmod(idx, W)
    f = fdir.ravel()
    for code, (dr, dc) in D8.items():
        k = f == code
        rr[k] += dr
        cc[k] += dc
    off = (rr < 0) | (rr >= H) | (cc < 0) | (cc >= W)
    nxt = np.where(off, idx, rr * W + cc).astype(np.int32)
    del idx, rr, cc, off
    return nxt, jump(nxt)


def exit_points(fdir, T, outlets):
    """Where the basins with these outlet cells leave the box: the centre of the first cell outside it (x, y arrays),
    NaN for sinks such as dams and lakes. pysheds keeps flow inside the grid: a stream leaving the box runs along the
    border to a low point and ends in a pit cell there, so outlets on the border also leave the box; step one cell
    straight out from that border."""
    H, W = fdir.shape
    orow, ocol = np.divmod(np.asarray(outlets, dtype=np.int64), W)
    codes = fdir[orow, ocol]
    dd = np.array([D8.get(int(k), (0, 0)) for k in codes], dtype=np.int64).reshape(-1, 2)
    trow, tcol = orow + dd[:, 0], ocol + dd[:, 1]
    off = np.isin(codes, list(D8)) & ((trow < 0) | (trow >= H) | (tcol < 0) | (tcol >= W))
    on_edge = (orow == 0) | (orow == H - 1) | (ocol == 0) | (ocol == W - 1)
    trow = np.where(off, trow, np.where(orow == 0, -1, np.where(orow == H - 1, H, orow)))
    tcol = np.where(off, tcol, np.where(ocol == 0, -1, np.where(ocol == W - 1, W, ocol)))
    leaves = off | on_edge
    ox, oy = T * (tcol + 0.5, trow + 0.5)
    return np.where(leaves, np.round(ox), np.nan), np.where(leaves, np.round(oy), np.nan)


def shared_edges(regions):
    """Edges two boxes share (boxes meet edge to edge), at least 1 km long: {(a, b): MultiLineString}. A basin links
    only across such an edge: streams leaving along a border run to its lowest point, which can be a corner that
    merely overlaps another box (the San Gabriels' south-west corner sits inside the Santa Monica box)."""
    out = {}
    for a in regions:
        for b in regions:
            if a != b:
                seg = shapely.box(*REGIONS[a]["bbox"]).boundary.intersection(shapely.box(*REGIONS[b]["bbox"]).boundary)
                lines = [g for g in getattr(seg, "geoms", [seg]) if g.geom_type == "LineString" and g.length >= 1000]
                if lines:
                    out[(a, b)] = shapely.MultiLineString(lines)
    return out


def neighbours(region, x, y, edges):
    """(neighbour, outward (dx, dy)) for each box whose shared edge with `region` passes within 60 m of (x, y)."""
    pt = shapely.Point(x, y)
    for (a, b), seg in edges.items():
        if a == region and seg.distance(pt) <= 60:
            ca, cb = shapely.box(*REGIONS[a]["bbox"]).centroid, shapely.box(*REGIONS[b]["bbox"]).centroid
            vertical = abs(seg.bounds[2] - seg.bounds[0]) < 1
            yield b, ((np.sign(cb.x - ca.x), 0) if vertical else (0, np.sign(cb.y - ca.y)))


def downhill(fd, T, x, y, away, steps=600):
    """Cells (row, col, x, y) downhill from (x, y) on a neighbour's grid, once the path has moved more than 25 m away
    from the shared edge (`away` = outward (dx, dy)); nothing if it hasn't within 100 cells. Edge cells first run
    along the border; where a creek really enters the source box from the neighbour, the source's edge cells still
    "exit" there, but the neighbour's water stays on the border instead of heading away."""
    c, r = ~T * (x, y)
    r, c = int(np.floor(r)), int(np.floor(c))
    left = False
    for k in range(steps):
        if not (0 <= r < fd.shape[0] and 0 <= c < fd.shape[1]):
            return
        px, py = T * (c + 0.5, r + 0.5)
        left = left or (px - x) * away[0] + (py - y) * away[1] > 25
        if left:
            yield r, c, px, py
        elif k >= 100:
            return
        st = D8.get(int(fd[r, c]))
        if st is None:
            return
        r, c = r + st[0], c + st[1]


_STITCHED = None
def stitched():
    """The boxes whose flow directions 03b_stitch.py worked out together with their neighbours: a cell on an edge
    they share drains straight into the next box, so a crossing there is exact."""
    global _STITCHED
    if _STITCHED is None:
        p = f"{SHARED_DERIVED}/stitched.json"
        _STITCHED = set(json.load(open(p))) if os.path.exists(p) else set()
    return _STITCHED


def crossing(region, fd, T, x, y, away, radius=10):
    """Cells (row, col, x, y) along a creek entering `region`'s grid at (x, y).
    Across an edge shared by two boxes that 03b_stitch.py routed together: simply the D8 path from that cell (the
    box it leaves points exactly at it).
    Elsewhere (in from outside the map, or boxes still routed alone): downhill() from there; or, where the box's
    own border handling ends the creek in a pit on the edge (a road fill or a low bump just inside leaves the
    border cell lowest: Bouquet Canyon entering the Piru box), from the lowest cell within `radius` cells inside the
    box whose path heads away from the edge."""
    if region in stitched():
        back = shapely.Point(x - away[0] * RES, y - away[1] * RES)
        if any(r != region and shapely.box(*REGIONS[r]["bbox"]).contains(back) for r in stitched()):
            c, r = ~T * (x, y)
            r, c = int(np.floor(r)), int(np.floor(c))
            for _ in range(600):
                if not (0 <= r < fd.shape[0] and 0 <= c < fd.shape[1]):
                    return
                yield (r, c, *(T * (c + 0.5, r + 0.5)))
                st = D8.get(int(fd[r, c]))
                if st is None:
                    return
                r, c = r + st[0], c + st[1]
            return
    path = downhill(fd, T, x, y, away)
    hit = next(path, None)
    if hit is None:
        c, r = ~T * (x, y)
        r, c = int(np.floor(r)), int(np.floor(c))
        r0, c0 = max(r - radius, 0), max(c - radius, 0)
        r1, c1 = min(r + radius + 1, fd.shape[0]), min(c + radius + 1, fd.shape[1])
        if r0 >= r1 or c0 >= c1:
            return
        with rasterio.open(f"{derived_dir(region)}/dem_filled.tif") as src:
            z = src.read(1, window=rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0), masked=True).astype(float)
        for k in np.argsort(z.filled(np.inf), axis=None):
            rr, cc = np.unravel_index(k, z.shape)
            if np.ma.is_masked(z[rr, cc]):
                break
            px, py = T * (c0 + cc + 0.5, r0 + rr + 0.5)
            if (px - x) * away[0] + (py - y) * away[1] <= 0:    # on the edge itself
                continue
            path = downhill(fd, T, px, py, away)
            hit = next(path, None)
            if hit is not None:
                break
    if hit is not None:
        yield hit
        yield from path


def walk(fd, r, c):
    """Flat index of the cell where the D8 path from (r, c) ends (the outlet graph() gives that cell)."""
    H, W = fd.shape
    for _ in range(10 ** 6):
        st = D8.get(int(fd[r, c]))
        if st is None or not (0 <= r + st[0] < H and 0 <= c + st[1] < W):
            break
        r, c = r + st[0], c + st[1]
    return r * W + c


def _path(fd, rc, n):
    """The flat cells of the D8 path from cell rc, or None where it leaves the box within n cells: over its rim, or
    into a pit on its rim (pysheds' way out, as exit_points() reads it). A path that ends inside the box sooner (a lake,
    a sink) stays in."""
    H, W = fd.shape
    r, c = rc
    out = []
    for _ in range(10 ** 6):
        out.append(r * W + c)
        st = D8.get(int(fd[r, c]))
        if st is None:
            rim = r in (0, H - 1) or c in (0, W - 1)
            return None if rim and len(out) < n else out
        if not (0 <= r + st[0] < H and 0 <= c + st[1] < W):
            return out if len(out) >= n else None
        r, c = r + st[0], c + st[1]
    return out


def _key(regions):
    from flowlib import FLOW
    files = [fdir_path(r) for r in regions] + [f"{raw_dir(r)}/nhd_flowlines.gpkg" for r in regions] + [
        f"{FLOW}/reservoirs.gpkg", f"{FLOW}/nhdplus_v2.gpkg", f"{FLOW}/nhdplus_v2_paths.csv", f"{SHARED_DERIVED}/stitched.json",
        f"{SHARED_DERIVED}/lake_outlets.json"]
    return {"version": VERSION, **{f: [os.path.getmtime(f), os.path.getsize(f)] for f in files if os.path.exists(f)}}


def _outflow_lines(region):
    """The box's detailed NHD stream lines (NHD High Resolution, 1:24,000 or better; 02_download_vectors.py), merged
    into single lines, with an index and the lines starting at each point: (lines, tree, begins), or None. Pipelines,
    tunnels, canals and ditches don't count."""
    p = f"{raw_dir(region)}/nhd_flowlines.gpkg"
    if not os.path.exists(p):
        return None
    fl = gpd.read_file(p).to_crs(CRS)
    fl = fl[fl.ftype.isin([460, 558, 334]) & fl.geometry.notna()]
    lines = []
    for g in shapely.line_merge(fl.geometry.force_2d().values):
        lines += [q for q in getattr(g, "geoms", [g]) if q.geom_type == "LineString" and q.length > 1]
    if not lines:
        return None
    begins = defaultdict(list)
    for i, g in enumerate(lines):
        begins[(round(g.coords[0][0]), round(g.coords[0][1]))].append(i)
    return lines, shapely.STRtree(lines), begins


def _pond_outflow(fd, T, lake, dead, detailed):
    """(row, col) where the water of a lake NHDPlus has no flowline for goes on, from the detailed NHD stream lines:
    a line that starts in the lake and ends outside it is its outflow (they are drawn downstream). Walk down it and the
    lines it runs into, 25 m at a time for up to 3 km, to the first cell whose D8 path doesn't lead back into the
    lake's dead ends; None where no line leaves the lake, or each one leaves the box first."""
    lines, tree, begins = detailed
    H, W = fd.shape
    lk = lake.buffer(30)
    for i in tree.query(lk, predicate="intersects"):
        g = lines[i]
        if not lk.contains(shapely.Point(g.coords[0])) or lk.contains(shapely.Point(g.coords[-1])):
            continue
        length, seen = 0.0, {i}
        while g is not None and length < 3000:
            for d in np.arange(0, g.length, 25.0):
                p = g.interpolate(d)
                if lk.contains(p):
                    continue
                c, r = ~T * (p.x, p.y)
                r, c = int(np.floor(r)), int(np.floor(c))
                if not (0 <= r < H and 0 <= c < W):
                    length = 1e9                    # this brook leaves the box first
                    break
                if walk(fd, r, c) not in dead:
                    return r, c
            length += g.length
            nx = [j for j in begins.get((round(g.coords[-1][0]), round(g.coords[-1][1])), []) if j not in seen]
            g = lines[nx[0]] if nx else None
            seen.update(nx[:1])
    return None


def _lake_tops(region, W):
    """{a lake's outlet cell (flat index): (row, col) of the first cell of its way out}, from 03b_stitch.py's
    lake_outlets.json: the lakes it ended at NHD's outlet, where it laid the way out along NHD's outflow line."""
    p = f"{SHARED_DERIVED}/lake_outlets.json"
    if not os.path.exists(p):
        return {}
    with open(p) as f:
        return {int(pr) * W + int(pc): (int(tr), int(tc)) for pr, pc, tr, tc in json.load(f).get("tops", {}).get(region, [])}


def _dam_links(fd, T, sinks, lakes, v2, by_seq, detailed=None, ponds=None, pond_dead=None, tops=None, closed=None):
    """{sink outlet: (row, col)} for dead ends inside a reservoir: the cell below its dam where the water goes on.
    Where 03b_stitch.py ended the lake at NHD's outlet, that is the first cell of the way out it laid there (`tops`,
    from _lake_tops): one step decides where a lake drains. Until 2026-11-22 this function looked for the place
    itself for every lake, as it still does for the rest:
    NHDPlus says whether the lake has an outflow and where: its outlet flowline (the most drainage inside the lake)
    and the flowlines below it. Walk down them from where the outlet flowline leaves the lake, 50 m at a time for up to
    3 km, to the first cell whose D8 path doesn't lead back into the lake's dead ends. A dead end counts for a lake
    within 400 m (Lake Mathews' is 338 m outside its outline). Lakes with no outflow (Baldwin Lake) and dead ends
    away from lakes (desert fans, gravel pits, the sea) stay closed.
    NHDPlus (1:100,000) doesn't have the brooks most small ponds sit on, and below such a pond the brook's drainage
    started again from nothing (66 ponds over six areas on 2026-11-19, 35 of them in north-east Connecticut), so its
    size and flow were low for a stretch. Where NHDPlus has no flowline in the lake, or its lines find no way on, the
    box's detailed NHD stream lines (`detailed`, from _outflow_lines) give it: _pond_outflow(). A lake whose NHDPlus
    outflow leaves the box first stays closed. 05c_drainages.py used these lines for the drainage names only."""
    if not sinks:
        return {}
    pts = gpd.GeoDataFrame({"o": list(sinks)}, geometry=gpd.points_from_xy(*zip(*sinks.values())), crs=CRS)
    # each dead end belongs to its nearest lake (the bigger one where it lies in two), so a pond beside a reservoir
    # can't claim the reservoir's dead ends
    hit = gpd.sjoin_nearest(pts, gpd.GeoDataFrame({"km2": lakes.area}, geometry=lakes.geometry, crs=CRS),
                            max_distance=400, distance_col="dist")
    hit = hit.sort_values(["dist", "km2"], ascending=[True, False]).drop_duplicates("o")
    H, W = fd.shape
    out = {}
    for li, grp in hit.groupby("index_right"):
        lake = lakes.geometry.iloc[li]
        dead = set(grp.o)
        entry, done = None, False
        ins = v2[v2.intersects(lake)]
        ins = ins[ins.geometry.intersection(lake).length >= 0.25 * ins.length]   # silted-up Matilija: 49 %
        known = next((tops[o] for o in sorted(dead) if o in tops), None) if tops else None
        if known:               # a pond still counts as one where NHDPlus has no flowline in it
            if not len(ins) and ponds is not None:
                ponds.append(known)
                pond_dead.update(dead)
            out.update({o: known for o in dead})
            continue
        lines = []
        if len(ins):
            fl = ins.loc[ins.totdasqkm.idxmax()]
            g = shapely.line_merge(fl.geometry)
            if g.geom_type != "LineString":             # NHDPlus stores flowlines as (usually one-part) multilines
                g = shapely.LineString([c for part in g.geoms for c in part.coords])
            inside = g.intersection(lake)
            t_end = max(g.project(shapely.Point(c)) for p in getattr(inside, "geoms", [inside]) for c in p.coords)
            lines = [shapely.ops.substring(g, t_end, g.length)]
            seq, length = fl.dnhydroseq, 0.0
            while seq in by_seq.index and length < 3000:
                below = by_seq.loc[seq]
                lines.append(below.geometry)
                length += below.geometry.length
                seq = below.dnhydroseq
        for ln in lines:
            for part in getattr(ln, "geoms", [ln]):
                if part.is_empty or part.geom_type != "LineString":
                    continue
                for d in np.arange(0, part.length, 50.0):
                    p = part.interpolate(d)
                    if lake.contains(p):
                        continue
                    c, r = ~T * (p.x, p.y)
                    r, c = int(np.floor(r)), int(np.floor(c))
                    if not (0 <= r < H and 0 <= c < W):
                        done = True                     # the creek leaves the box first: leave it closed
                        break
                    if walk(fd, r, c) not in dead:
                        entry, done = (r, c), True
                        break
                if done:
                    break
            if done:
                break
        if entry is None and not done and detailed is not None:    # no NHDPlus way on, and none that leaves the box
            entry = _pond_outflow(fd, T, lake, dead, detailed)
            if entry and ponds is not None:
                ponds.append(entry)
                pond_dead.update(dead)
        if entry:
            out.update({o: entry for o in dead})
        elif closed is not None:        # its water goes nowhere: no way on found, or the creek leaves the box first
            name = lakes.gnis_name.iloc[li]
            closed.append((name if isinstance(name, str) else "unnamed", round(lake.area / 1e4, 1), len(dead)))
    return out


def _down_river(g, t, seq, by_seq, max_m, step=50.0):
    """Points every `step` m down a mapped river, up to max_m: from t m along its NHDPlus line g, then on down the
    lines below it (dnhydroseq `seq` and on)."""
    lines, length = [shapely.ops.substring(g, t, g.length)], g.length - t
    while seq in by_seq.index and length < max_m:
        nx_ = by_seq.loc[seq]
        lines.append(nx_.geometry)
        length += nx_.geometry.length
        seq = nx_.dnhydroseq
    gone = 0.0
    for ln in lines:
        for part in getattr(ln, "geoms", [ln]):
            if part.is_empty or part.geom_type != "LineString":
                continue
            for d_ in np.arange(step, part.length, step):
                if gone + d_ > max_m:
                    return
                yield part.interpolate(d_)
            gone += part.length


def _at_outflow(region, fd, links, km2):
    """_dam_links' cells below the dams, moved to the top of each lake's routed way out where they lie on it.
    _dam_links finds the cell where a lake's water goes on along NHDPlus's (1:100,000) or NHD's outlet line: the first
    point outside the lake whose D8 path doesn't lead back into it. That cell sits 20-250 m from the lake and often
    beside the channel, so its path joined the river's own line (03b_stitch.py's outflow line, from the cell below the
    outlet pit) some way down: a median 40-120 m on the 12 maps, 300 m or more at about 60 outlets (the Snake below
    Palisades Dam 700 m, the Gros Ventre below Lower Slide Lake 560 m). Above that point the river read only its own
    few cells: the stretch between a dam and the next lake could read 0 km2 (the Raquette's 54 m between Rainbow Falls
    and Five Falls reservoirs), which showed once 05_score.py cut the links at lake shores (2026-11-21).
    The routed way out is the D8 path from the outlet pit's steepest-descent neighbour on the conditioned DEM (what
    03b_stitch.py's directions held there before it made the outlet a pit). A lake's outlet is its dead end holding the
    most water (`km2`: dead end -> km2). The water is put in at the top of that line where the cell found lies within
    OUTFLOW_NEAR_M of it and its own path joins it: the same channel. Where it doesn't (the routing spills Stillwater
    Reservoir over a saddle 450 m from its dam, and Raquette Lake south over the Brown's Tract carry), NHD's cell
    stands, as before."""
    p = f"{derived_dir(region)}/dem_cond.tif"
    if not links or not os.path.exists(p):
        return links
    H, W = fd.shape
    groups = defaultdict(list)
    for o, rc in links.items():
        groups[tuple(rc)].append(o)
    out = dict(links)

    def line(r, c, n=600):
        cells = []
        for _ in range(n):
            cells.append((r, c))
            st = D8.get(int(fd[r, c]))
            if st is None or not (0 <= r + st[0] < H and 0 <= c + st[1] < W):
                break
            r, c = r + st[0], c + st[1]
        return cells

    with rasterio.open(p) as src:
        for (lr, lc), dead in groups.items():
            o = max(dead, key=lambda q: km2.get(q, 0.0))
            pr, pc = divmod(int(o), W)
            if int(fd[pr, pc]) in D8 or not (0 < pr < H - 1 and 0 < pc < W - 1):
                continue
            z = src.read(1, window=rasterio.windows.Window(pc - 1, pr - 1, 3, 3)).astype(float)
            best, nb = 0.0, None
            for dr, dc in ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)):   # 03b_stitch.py's order
                s = (z[1, 1] - z[1 + dr, 1 + dc]) / (RES * (2 ** 0.5 if dr and dc else 1.0))
                if s > best:
                    best, nb = s, (pr + dr, pc + dc)
            if nb is None or walk(fd, *nb) in set(dead):        # no way out on the DEM, or one leading back into the lake
                continue
            way = line(*nb)
            a = np.array(way)
            if np.hypot(a[:, 0] - lr, a[:, 1] - lc).min() * RES > OUTFLOW_NEAR_M:
                continue
            on = set(way)
            if any(rc in on for rc in line(lr, lc)):
                for q in dead:
                    out[q] = nb
    return out


def _build(regions):
    from flowlib import FLOW, reservoirs, level_paths
    from config import SHARED
    # the reservoir list leaves out lagoons (it's for coastal ones), but Castaic's water ends in Castaic Lagoon, the
    # afterbay below the dam; a coastal lagoon has no flowline below it, so it stays closed anyway
    lag = [gpd.read_file(g, layer="NHDWaterbody", where="gnis_name LIKE '%Lagoon%' AND ftype IN (390, 436)")
           for g in sorted({f"{NATIONAL}/NHD_H_{h}_HU4_GPKG.gpkg" for v in REGIONS.values() for h in v["hu4"]})]
    lag = [l.to_crs(CRS)[["gnis_name", "geometry"]] for l in lag if len(l)]
    lakes = pd.concat([reservoirs()[["gnis_name", "geometry"]], *lag], ignore_index=True)
    lakes = gpd.GeoDataFrame(lakes, geometry=lakes.geometry.force_2d(), crs=CRS)
    v2 = gpd.read_file(f"{FLOW}/nhdplus_v2.gpkg", columns=["comid", "hydroseq", "dnhydroseq", "totdasqkm", "ftype", "gnis_name",
                                                           "streamcalc"]).to_crs(CRS)
    by_seq = v2.drop_duplicates("hydroseq").set_index("hydroseq")
    edges = shared_edges(regions)
    fds, exits, own, links = {}, {}, {}, []      # own: (region, outlet) -> its basin km2; links: (src, region, row, col, kind)
    ponds, pond_dead = [], set()                  # the cells below the ponds whose way on comes from the detailed lines
    n_moved = n_top = 0                           # dead ends whose water goes on from the top of the routed way out
    put_in = defaultdict(list)                    # per box: (x, y of a lake's dead end, row, col where its water goes on)
    closed = []                                   # lakes whose dead ends are carried nowhere: (name, ha, dead ends)
    for r in regions:
        with rasterio.open(fdir_path(r)) as src:
            fds[r] = (src.read(1), src.transform)
        fd, T = fds[r]
        H, W = fd.shape
        _, outlet = graph(fd)
        uo, n = np.unique(outlet, return_counts=True)
        del outlet
        km2 = n * RES * RES / 1e6
        ox, oy = exit_points(fd, T, uo)
        orow, ocol = np.divmod(uo, W)
        if r in stitched():
            # Routed together with its neighbours (03b_stitch.py): area_km2.tif already counts the cells upstream in
            # the other boxes. So a basin that leaves over an edge hands on nothing of its own (the next box has it),
            # only what came into it from outside the map or over a dam; and a lake's dead end holds everything the
            # raster has there, wherever it fell.
            with rasterio.open(f"{derived_dir(r)}/area_km2.tif") as src:
                km2 = np.maximum(km2, src.read(1).ravel()[uo].astype(float))
        exit_ = ~np.isnan(ox) & (km2 >= MIN_KM2)
        sink = ((orow > 0) & (orow < H - 1) & (ocol > 0) & (ocol < W - 1) & ~np.isin(fd[orow, ocol], list(D8))
                & (km2 >= MIN_KM2))
        exits[r] = {int(o): (float(x), float(y)) for o, x, y in zip(uo[exit_], ox[exit_], oy[exit_])}
        own.update({(r, int(o)): float(a) for o, a in zip(uo[sink], km2[sink])})
        own.update({(r, int(o)): (0.0 if r in stitched() else float(a)) for o, a in zip(uo[exit_ & ~sink], km2[exit_ & ~sink])})
        sinks = {int(o): T * (c + 0.5, rr + 0.5) for o, rr, c in zip(uo[sink], orow[sink], ocol[sink])}
        tops = _lake_tops(r, W)
        below = _dam_links(fd, T, sinks, lakes, v2, by_seq, _outflow_lines(r), ponds, pond_dead, tops, closed)
        top_cells = set(tops.values())
        at_top = {o for o, rc in below.items() if tuple(rc) in top_cells}       # 03b's: already at the top of the way out
        n_top += len(at_top)
        moved = _at_outflow(r, fd, {o: rc for o, rc in below.items() if o not in at_top},
                            {int(o): float(a) for o, a in zip(uo[sink], km2[sink])})
        n_moved += sum(tuple(moved[o]) != tuple(below[o]) for o in moved)
        moved.update({o: below[o] for o in at_top})
        # a lake that passes its water on at its outlet (03b_stitch.py, since 2026-11-22) has no dead end and no link,
        # but a river from outside the map that comes in through it goes in where the lake's water goes on (below)
        for o, (tr_, tc_) in tops.items():
            if o not in sinks:
                orr, occ = divmod(int(o), W)
                put_in[r].append((*(T * (occ + 0.5, orr + 0.5)), int(tr_), int(tc_)))
        for o, (row, col) in moved.items():
            links.append(((r, o), r, row, col, "pond" if o in pond_dead else "dam"))
            put_in[r].append((*sinks[o], int(row), int(col)))
        # A lake's water put in on a path that leaves the box goes on with it, however little ground that path gathers
        # itself. A basin under MIN_KM2 is no exit otherwise, and the water stopped at the box's edge: Grass Pond's
        # 6 km2, put in 80 m from the wilmington box's south edge, never reached Grass Pond Outlet in the next box
        # (seven lakes on the 12 maps, six of them before the put-ins moved to the lakes' own outlets; 2026-11-22)
        for rc in {(int(row), int(col)) for row, col in moved.values()}:
            e = int(walk(fd, *rc))
            if e not in exits[r] and (r, e) not in own:
                x_, y_ = exit_points(fd, T, [e])
                if not np.isnan(x_[0]):
                    exits[r][e] = (float(x_[0]), float(y_[0]))
                    own[(r, e)] = 0.0 if r in stitched() else float(km2[np.searchsorted(uo, e)])
    # each exit -> the cell in the neighbouring box where its creek heads away from the edge
    for r in regions:
        for o, (x, y) in exits[r].items():
            for b, away in neighbours(r, x, y, edges):
                hit = next(crossing(b, *fds[b], x, y, away), None)
                if hit:
                    links.append(((r, o), b, hit[0], hit[1], "edge"))
                    break
    # Rivers entering from outside every box: every NHDPlus line that crosses the outer boundary flowing in, whatever
    # its size (until 2026-11-22 only rivers of 10 km2 or more that brought 10 km2 and a quarter of their drainage: the
    # French River at Webster, the Chattooga's East Fork and every creek under 10 km2 came in with nothing). Main paths
    # only: NHDPlus gives the minor arm of a split river the whole river's drainage (the Santa Ana's two arms at the
    # Santa Ana Mountains box, 2,502 and 2,500 km2), and its water is the main arm's.
    boxes = {r: shapely.box(*REGIONS[r]["bbox"]) for r in regions}
    union = shapely.unary_union(list(boxes.values()))
    main = v2[v2.ftype.isin(["StreamRiver", "ArtificialPath"]) & (v2.streamcalc != 0)]
    up_km2 = main.groupby("dnhydroseq").totdasqkm.sum()          # what the lines above bring in at a line's top
    heads = set(level_paths().query("uphydroseq == 0").hydroseq)  # lines with nothing above them
    dn = dict(zip(main.hydroseq, main.dnhydroseq))
    below_ = {}
    def below(hs):
        """NHDPlus line hs and the lines below it, as far as the area's download of the network goes."""
        if hs not in below_:
            out_, h = set(), hs
            while h in dn and h not in out_:
                out_.add(h)
                h = dn[h]
            below_[hs] = out_
        return below_[hs]
    riv = main[main.intersects(union.boundary)]
    found, traces, skipped, reenter = [], [], defaultdict(int), []
    # what the edge links already bring in, per link: a river weaving along the boxes' edges (the Santa Clara at
    # Fillmore) comes in from the neighbouring box and from outside within a few km, and must count once
    edge_links = [l for l in links if l[4] == "edge"]
    into_e, tot_e = defaultdict(list), {}
    for src, b_, row_, col_, _ in edge_links:
        into_e[(b_, walk(fds[b_][0], row_, col_))].append(src)
    def carried(key, path=frozenset()):
        if key not in tot_e:
            tot_e[key] = own.get(key, 0.0) + sum(carried(s_, path | {key}) for s_ in into_e.get(key, [])
                                                 if s_ not in path and s_ != key)
        return tot_e[key]
    def area_at(b, rc):
        with rasterio.open(f"{derived_dir(b)}/area_km2.tif") as src:
            return float(src.read(1, window=rasterio.windows.Window(int(rc[1]), int(rc[0]), 1, 1))[0, 0])
    # upstream lines first (NHDPlus numbers a line's hydrologic sequence above the line below it), so the water of a
    # river that comes in twice is taken where it first comes in
    for f in riv.sort_values("hydroseq", ascending=False).itertuples():
        g = f.geometry if f.geometry.geom_type == "LineString" else max(f.geometry.geoms, key=lambda q: q.length)
        g = shapely.LineString([c[:2] for c in g.coords])                # flowlines are digitised downstream
        cut = g.intersection(union.boundary)
        # every place it comes in: a line can start outside, or come in, leave and come back (the Snake below Jackson
        # Lake weaves across the north edge at Moran; East Canada Creek runs down the speculator box's west edge)
        for k, t in enumerate(sorted(g.project(q) for q in getattr(cut, "geoms", [cut]) if q.geom_type == "Point")):
            pt, inner = g.interpolate(t), g.interpolate(min(t + 15, g.length))
            if union.contains(g.interpolate(max(t - 15, 0))) or not union.contains(inner):
                continue                                         # going out, or along the edge
            b = next((r for r in regions if boxes[r].contains(inner)), None)
            if b is None:
                continue
            x0, y0, x1, y1 = REGIONS[b]["bbox"]
            away = min(((abs(pt.x - x0), (1, 0)), (abs(pt.x - x1), (-1, 0)), (abs(pt.y - y0), (0, 1)), (abs(pt.y - y1), (0, -1))))[1]
            fd_b, T_b = fds[b]
            Hh, Ww = fd_b.shape
            def cell(q):
                c_, r_ = ~T_b * (q.x, q.y)
                r_, c_ = int(np.floor(r_)), int(np.floor(c_))
                return (r_, c_) if 0 <= r_ < Hh and 0 <= c_ < Ww else None
            kind, hit = "outside", None
            lake = lakes[lakes.distance(pt) <= 150]
            if len(lake):        # the river comes in through a reservoir (the Chattahoochee in Lake Lanier): its water
                lk = lake.geometry.union_all()                   # goes on below the dam. Follow the mapped river down
                kind = "dam"                                     # to the first cell outside the lake (up to 25 km)
                for q in _down_river(g, t, f.dnhydroseq, by_seq, 25000):
                    if cell(q) is None:                          # it leaves the box before the dam: not carried
                        break
                    if lk.distance(q) > 60:
                        hit = cell(q)
                        break
                if hit is None:
                    skipped["into a lake whose water leaves the map"] += 1
                    continue
                # ... and goes in where that lake's own water does: the top of its way out (03b_stitch.py's, since
                # 2026-11-22). The first point of NHDPlus's line past the lake lies beside that channel as often as on
                # it, and the first reach below the dam read the lake's water without the river's (Little Neshaminy Creek
                # below Bradford Reservoir 2.7 km2 for NHDPlus's 28; a 115 m stub beside the Hiwassee below Chatuge Dam)
                at = [(np.hypot(row_ - hit[0], col_ - hit[1]), (row_, col_)) for x_, y_, row_, col_ in put_in.get(b, [])
                      if lk.distance(shapely.Point(x_, y_)) <= 400]
                if at:
                    hit = min(at)[1]
            else:
                # A flat river surface cut by the box edge drains back out through the edge (the edge is the lowest way
                # out the routing can see): the Snake's 2,112 km2 came in at Moran and left again 1 km on, and at Webster
                # the French River's 156 km2 found no cell to go in at. Where the path from the entry leaves the map
                # again within 3 km, hand the water over further down the mapped river instead: the first point, 50 m
                # at a time for up to OUTSIDE_FOLLOW_M, whose path doesn't leave the map within 3 km of it (a path into
                # the next box goes on), unless it leaves within 1 km of where the mapped river does (the East Fork
                # Little Pigeon clips the Smokies' north edge for 1.2 km). A river that leaves the box first only
                # brushes it.
                down = list(_down_river(g, t, f.dnhydroseq, by_seq, OUTSIDE_FOLLOW_M))
                gone = next((q for q in down if not union.contains(q)), None)
                def back_out(rc, q):
                    """The path from cell rc leaves the map within 3 km of point q, where the mapped river doesn't."""
                    ex, ey = exit_points(fd_b, T_b, [walk(fd_b, *rc)])
                    e = None if np.isnan(ex[0]) else shapely.Point(ex[0], ey[0])
                    return (e is not None and not union.contains(e) and e.distance(q) < 3000
                            and (gone is None or e.distance(gone) > 1000))
                hit = next(crossing(b, fd_b, T_b, pt.x, pt.y, away), None)
                hit = hit and hit[:2]
                if hit is None or back_out(hit, shapely.Point(T_b * (hit[1] + 0.5, hit[0] + 0.5))):
                    hit = None
                    for q in down:
                        rc = cell(q)
                        if rc is None:
                            break
                        if not back_out(rc, q):
                            hit = rc
                            break
                if hit is None:
                    skipped["brushes the box"] += 1
                    continue
            i_, mine = hit[0] * Ww + hit[1], []
            for _ in range(200000):
                mine.append(i_)
                st_ = D8.get(int(fd_b.flat[i_]))
                if st_ is None:
                    break
                r2, c2 = i_ // Ww + st_[0], i_ % Ww + st_[1]
                if not (0 <= r2 < Hh and 0 <= c2 < Ww):
                    break
                i_ = r2 * Ww + c2
            # What the river brings that the box doesn't have. NHDPlus gives a line's total at its lower end: less what
            # the box's own routing gathers there (taken 100 m above the end, on the river's path where it passes within
            # 150 m, and before the path meets a stream NHDPlus has joining only further down), so the box's own creeks
            # and banks above it count once. Else (the path strays from the line, or the line ends past the map): its
            # drainage where it crosses, from what the lines above bring in and its own catchment in proportion to the
            # length above the crossing (the line's total where the lines above lie outside the area's download of
            # NHDPlus), less what the routing has at the cell it goes on from. A river that only brushes the boundary
            # adds nothing either way.
            tot_, more = float(f.totdasqkm), None
            q = g.interpolate(g.length - 100)
            if kind == "outside" and g.length - t > 200 and union.contains(q):
                pr, pc = np.divmod(np.asarray(mine[:int((g.length - t) * 2 / RES) + 50]), Ww)
                with rasterio.open(f"{derived_dir(b)}/area_km2.tif") as src:
                    win = src.read(1, window=rasterio.windows.Window(pc.min(), pr.min(), pc.max() - pc.min() + 1,
                                                                     pr.max() - pr.min() + 1))
                a_ = win[pr - pr.min(), pc - pc.min()].astype(float)
                px, py = T_b * (pc + 0.5, pr + 0.5)
                d_ = np.where(np.maximum.accumulate(a_ > tot_), np.inf, np.hypot(px - q.x, py - q.y))
                j = int(np.argmin(d_))
                if d_[j] <= 150:
                    more = tot_ - a_[j]
            if more is None:
                up = float(up_km2.get(f.hydroseq, 0.0)) or (0.0 if f.hydroseq in heads else tot_)
                up = min(up, tot_)
                more = up + (tot_ - up) * t / g.length - area_at(b, hit)
            more -= sum(carried(src_) for src_, b_, row_, col_, _ in edge_links
                        if b_ == b and np.hypot(row_ - hit[0], col_ - hit[1]) * RES < 3000)
            # ... and the water of a river taken before that NHDPlus has above this one (the same river coming in again,
            # or a creek joining it outside), where its path meets this one's. A creek NHDPlus has joining it inside the
            # box is its own water (the Chattooga's East Fork joins the river 0.6 km below where it comes in; until
            # 2026-11-22 any river whose path this one met within 1.5 km took its water away)
            more -= sum(a_ for b_, tr_, a_, hs_ in traces
                        if b_ == b and f.hydroseq in below(hs_) and not tr_.isdisjoint(mine))
            if more < MIN_KM2:
                skipped["the box's routing already carries it"] += 1
                continue
            key = ("outside", int(f.comid), k)
            own[key] = more
            links.append((key, b, int(hit[0]), int(hit[1]), kind))     # "dam": only in the through-dams totals
            traces.append((b, set(mine), more, f.hydroseq))
            found.append((f.gnis_name if isinstance(f.gnis_name, str) else "unnamed river", b, round(more, 2),
                          round(pt.x), round(pt.y), int(f.comid), kind))
            if kind == "outside" and down:
                reenter.append((f, b, k, mine, more, down, g))             # (second pass, below)
    # A river can stay in the map where its path doesn't: the path leaves over the map's edge while the mapped river
    # runs on inside, and that stretch had neither the river's water nor a line (Minister Creek on the SE PA map: in
    # where its NHDPlus line crosses the north edge, its path out again 350 m on, the creek inside for 800 m more; live
    # drew it from where its path comes back in). What left the box there, the river's water and what the box gathered
    # on the way, goes in again at the first point down the mapped river, 50 m at a time while the river is still in
    # this box and on its own lines (NHDPlus's drainage there at most REENTER_GROW times the line's that came in: a
    # bigger river it has run into carries its water already: a tributary's 145 km2 went in again on a braid of the
    # Santa Ana River beside the drawn river on the first try), whose path stays in the map for REENTER_M, runs along
    # NHD's detailed lines (REENTER_NHD of its first REENTER_M within 30 m: NHDPlus's lines can lie 100 m off near an
    # edge) and meets the path of no water taken in already (so no other put-in loses water to it, and none counts
    # twice); and so on where that path leaves early too, each time further down the river. Biggest rivers first
    # (2026-11-23).
    taken = defaultdict(set)
    for b_, tr_, *_ in traces:
        taken[b_] |= tr_
    nhd_hr = {}
    for f, b, k, mine, more, down, g in sorted(reenter, key=lambda e: -e[4]):
        fd_b, T_b = fds[b]
        chain, seq = [(g, float(f.totdasqkm))], f.dnhydroseq      # the lines down the river, with their drainage
        while seq in by_seq.index and len(chain) < 500 and sum(l_.length for l_, _ in chain[1:]) < OUTSIDE_FOLLOW_M:
            nx_ = by_seq.loc[seq]
            chain.append((nx_.geometry, float(nx_.totdasqkm)))
            seq = nx_.dnhydroseq
        on_ = shapely.STRtree([l_ for l_, _ in chain]).nearest(shapely.points([(q_.x, q_.y) for q_ in down]))
        km2_down = np.array([chain[i][1] for i in on_])
        Hh, Ww = fd_b.shape
        if b not in nhd_hr:
            nhd_hr[b] = _outflow_lines(b)
        def along(p2):
            if nhd_hr[b] is None:
                return False
            rr, cc = np.divmod(np.asarray(p2[:int(REENTER_M / RES) + 1]), Ww)
            pts = shapely.points(np.column_stack(T_b * (cc + 0.5, rr + 0.5)))
            near = nhd_hr[b][1].query(pts, predicate="dwithin", distance=30)[0]
            return len(np.unique(near)) >= REENTER_NHD * len(pts)
        path_, back, j_at = mine, more, -1
        for n_ in range(1, REENTER_MAX + 1):
            ex_, ey_ = exit_points(fd_b, T_b, [path_[-1]])
            if np.isnan(ex_[0]):
                break                                            # it ends in the box (a lake, a sink)
            e_ = shapely.Point(ex_[0], ey_[0])
            if union.contains(e_):
                break                                            # into the next box, where 03b's routing goes on
            j0 = int(np.argmin([q_.distance(e_) for q_ in down]))
            if down[j0].distance(e_) > REENTER_NEAR_M:
                break                                            # it leaves away from the mapped river
            back += area_at(b, divmod(path_[-1], Ww))
            again = None
            for j in range(max(j0, j_at) + 1, len(down)):
                q_ = down[j]
                c_, r_ = ~T_b * (q_.x, q_.y)
                r_, c_ = int(np.floor(r_)), int(np.floor(c_))
                if not (union.contains(q_) and 0 <= r_ < Hh and 0 <= c_ < Ww):
                    break                                        # the river has left this box too
                if km2_down[j] > REENTER_GROW * float(f.totdasqkm):
                    break                                        # it has run into a bigger river
                p2 = _path(fd_b, (r_, c_), int(REENTER_M / RES) + 1)
                if p2 is not None and taken[b].isdisjoint(p2) and along(p2):
                    again = ((r_, c_), p2, q_, j)
                    break
            if again is None:
                break
            rc, path_, q_, j_at = again
            taken[b] |= set(path_)
            key2 = ("outside", int(f.comid), k, n_)
            own[key2] = back
            links.append((key2, b, int(rc[0]), int(rc[1]), "outside"))
            found.append((f.gnis_name if isinstance(f.gnis_name, str) else "unnamed river", b, round(back, 2),
                          round(q_.x), round(q_.y), int(f.comid), "again"))
    if found:
        big = sorted(found, key=lambda q: -q[2])
        print(f"crossbox: {len(found)} rivers entering from outside the boxes, {sum(q[2] for q in found):,.0f} km2 carried in "
              f"(not carried: {', '.join(f'{v} {k}' for k, v in skipped.items()) or 'none'}); the biggest: "
              + ", ".join(f"{n} -> {b} {a:,.0f}" for n, b, a, *_ in big[:14]))
    out = {}
    # edge: across edges and in from outside; full: also past dams and ponds; full_dams: past dams but not the ponds
    # NHDPlus has no flowline for (05c_drainages.py picks forks and drainage names on it, as before those were carried)
    for variant in ("edge", "full", "full_dams"):
        use = [l for l in links if variant == "full" or (variant == "full_dams" and l[4] != "pond")
               or l[4] in ("edge", "outside")]
        into = defaultdict(list)
        for src, b, row, col, _ in use:
            into[(b, walk(fds[b][0], row, col))].append(src)
        total = {}
        def tot(key, path=frozenset()):
            """A basin's own area plus everything flowing into it (a loop along a border counts once)."""
            if key not in total:
                total[key] = own.get(key, 0.0) + sum(tot(s, path | {key}) for s in into.get(key, [])
                                                     if s not in path and s != key)
            return total[key]
        ent = defaultdict(list)
        for src, b, row, col, kind in use:
            ent[b].append([int(row), int(col), round(tot(src), 3), src[0], kind])
        out[variant] = {r: ent.get(r, []) for r in regions}
        if variant == "full":
            # every place a creek's line breaks, for crossings(): where it leaves its box (edge links only), the
            # cell it goes on from in the next one (or below the dam, or inside the outer boundary) and what it carries
            out["cross"] = [[src[0], *(exits.get(src[0], {}).get(src[1], (None, None)) if kind == "edge" else (None, None)),
                             b, int(row), int(col), round(tot(src), 3), kind] for src, b, row, col, kind in use]
    dams = [l for l in links if l[4] in ("dam", "pond")]
    print(f"crossbox: {sum(l[4] == 'edge' for l in links)} edge links, {len(dams)} reservoir dead ends carried past "
          f"their dams ({len(ponds)} ponds NHDPlus has no flowline for, by the detailed NHD stream line leaving them; "
          f"{n_top} put in at the top of the way out 03b_stitch.py laid at NHD's outlet, {n_moved} more moved to the "
          f"top of the lake's routed way out)")
    if closed:        # never listed before 2026-11-22: 59 pitted lakes of the 12 maps passed nothing on, unseen
        print(f"crossbox: {len(closed)} lakes whose dead ends are carried nowhere (NHD shows no way out of them, or it "
              "leaves the box first): " + ", ".join(f"{n} ({ha:g} ha)" for n, ha, _ in sorted(closed, key=lambda q: -q[1])))
    # the dead ends themselves, for dam_links(): {region: [[dead-end cell, row, col of the cell below the dam]]}
    out["dams"] = {r: [[int(src[1]), int(row), int(col)] for src, b, row, col, kind in dams
                       if b == r and src[0] == r] for r in regions}
    # the rivers carried in from outside, for checks: [name, box, km2, x, y where it crosses, NHDPlus comid, kind]
    out["outside"] = [list(q) for q in found]
    return out


def inflows(region, through_dams=False, ponds=True):
    """[(row, col, km2, from_region, kind)]: where water from elsewhere enters `region`'s grid and how much drainage
    area it brings: from neighbouring boxes ("edge"), and with through_dams also from above a reservoir ("dam").
    The edge-only totals leave out any water that came over a dam; ponds=False leaves out what came past a pond NHDPlus
    has no flowline for (the detailed NHD stream line's way on). Built for every box at once and cached until a
    flowdir.tif, the reservoir list, the NHDPlus network or a box's NHD stream lines change."""
    key = "edge" if not through_dams else "full" if ponds else "full_dams"
    return [tuple(e) for e in _data()[key].get(region, [])]


def carried_km2(region):
    """Drainage area (km2) that reaches each cell of `region`'s grid from elsewhere, as a flat array: every
    inflows(region, through_dams=True) entry's area, added all the way down its D8 path (over a dam, past a pond,
    across a box edge, in from outside the map). 05c_drainages.py adds the same to each reach's own area
    (area_full_km2); 05_score.py's 1 km2 floor counts it, so the creek below a lake's outlet is drawn from the outlet."""
    with rasterio.open(fdir_path(region)) as src:
        fd = src.read(1)
    W = fd.shape[1]
    nxt, _ = graph(fd)
    ex = np.zeros(fd.size, np.float32)
    for row, col, km2, *_ in inflows(region, through_dams=True):
        i = row * W + col
        while True:
            ex[i] += km2
            if nxt[i] == i:
                break
            i = nxt[i]
    return ex


def lead_ins(region, lines, put_ins, max_cells=800):
    """Lines from where water from elsewhere goes in to `region`'s stream lines: the D8 path from each put-in cell
    ((row, col, km2, ...) as inflows() gives them; the biggest first) to the first vertex of `lines` (03b_stitch.py's
    stream lines, whose vertices sit on cell corners) or of a lead-in already laid, max_cells cells at most (8 km, as
    06_map.py drew them through). A put-in on a line gives none. 05_score.py makes each one a link of its own.
    A path ends where it reaches a lake whose water leaves the map (03b_stitch.py's lakes_off_map.gpkg), which carries
    no stream lines: the creeks around it end at its shore. On the first try three lead-ins ran 4-10 km across Lake
    Champlain off the High Peaks map (two more off central Vermont's), and the creeks on the shore whose way down met
    one took the flow of the lake's main line instead of the Boquet River's line by their mouths (05b_flow.py): two
    near Willsboro read drier, one of them "usually flows" -> "mostly dry" (2026-11-22)."""
    with rasterio.open(fdir_path(region)) as src:
        fd, T = src.read(1), src.transform
    H, W = fd.shape
    off = np.zeros((H, W), bool)
    p_off = f"{derived_dir(region)}/lakes_off_map.gpkg"
    if os.path.exists(p_off):
        from rasterio import features as rio_features
        g_off = gpd.read_file(p_off).to_crs(CRS).geometry
        if len(g_off):
            off = rio_features.rasterize(((g, 1) for g in g_off), out_shape=(H, W), transform=T, fill=0,
                                         dtype="uint8") > 0
    on = {(round(x, 1), round(y, 1)) for g in lines for x, y, *_ in g.coords}
    out = []
    for r, c, *_ in sorted(put_ins, key=lambda e: -e[2]):
        pts = []
        for _ in range(max_cells):
            if off[r, c]:
                break
            p = tuple(round(v, 1) for v in T * (c, r))
            pts.append(p)
            st = D8.get(int(fd[r, c]))
            if p in on or st is None or not (0 <= r + st[0] < H and 0 <= c + st[1] < W):
                break
            r, c = r + st[0], c + st[1]
        if len(pts) >= 2:
            out.append(shapely.LineString(pts))
            on.update(pts)
    return out


def dam_links(region):
    """{dead-end cell (flat index): (row, col)}: for every dead end in a lake or reservoir of `region` whose water
    goes on, the cell below the dam where it does (in the same box). 05c_drainages.py uses it to give a pond's
    basin the drainage its outflow joins. From the same cache as inflows()."""
    return {int(o): (int(r), int(c)) for o, r, c in _data().get("dams", {}).get(region, [])}


def crossings():
    """[(from box, exit x, exit y, into box, row, col, km2, kind)]: every link where a creek's D8 path stops and goes
    on elsewhere: across an edge two boxes share ("edge": the exit is the centre of the first cell outside the box
    it leaves), below a dam ("dam") or in from outside every box ("outside"); the last two have no exit. km2 is
    the drainage it carries, with everything upstream. 06_map.py draws the creek through with it."""
    return [tuple(e) for e in _data().get("cross", [])]


def _data():
    regions = [r for r in REGIONS if os.path.exists(fdir_path(r))]
    key = _key(regions)
    data = None
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            data = json.load(f)
        if data.get("key") != key:
            data = None
    if data is None:
        data = {"key": key, **_build(regions)}
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        tmp = CACHE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, CACHE)
    return data
